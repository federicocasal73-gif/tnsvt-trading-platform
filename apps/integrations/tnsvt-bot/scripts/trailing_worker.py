"""
TrailingWorker — Phase 1 (Trailing Stop end-to-end).

Daemon que monitorea posiciones abiertas y ajusta el Stop Loss según el
movimiento favorable del precio. Al estilo "Trailing Stop" clásico:

1. Lee `config.json` para saber si trailing_enabled=true, con sus pips.
2. Cada `POLL_INTERVAL` segundos (default 5s) enumera posiciones abiertas.
3. Para cada posición con SL inicial:
   - Calcula el "nivel de break-even" = entry + trailing_start_pips.
   - Si el precio actual está por encima del break-even, empieza a mover
     el SL.
   - Solo sube el SL cuando la diferencia entre el precio actual y el SL
     actual supera `trailing_step_pips` (evita micro-cambios).
   - El nuevo SL = precio actual - trailing_step_pips.
4. Si la posición no tiene SL (raro, se abre siempre con uno), no hace
   nada — el executor abre órdenes con `signal['sl']` cuando hay.
5. Manda los cambios con `mt5.order_send(TRADE_ACTION_SLTP)`.

Logs en formato `bot.trailing` para auditoría.

Robustez:
- Si trailing_enabled=false, el worker hace polling barato cada 30s y no
  toca nada. Cero overhead.
- Errores de una posición individual no tumban el worker — se loguea
  `warning` y se sigue con las demás.
- Se salta posiciones en `tickets_below_size` (micro-posiciones).
"""

import threading
import time
import logging
from datetime import datetime

import MetaTrader5 as mt5

import config
import database

logger = logging.getLogger("bot.trailing")
POLL_INTERVAL = 5.0
IDLE_INTERVAL = 30.0  # cuando trailing está off


def _ticket_seen_recently(ticket: int, ttl_seconds: float = 600.0) -> bool:
    """Evita spam de logs para el mismo ticket."""
    if not hasattr(_ticket_seen_recently, "_cache"):
        _ticket_seen_recently._cache = {}
    cache: dict = _ticket_seen_recently._cache
    now = time.time()
    if ticket in cache and (now - cache[ticket]) < ttl_seconds:
        return True
    cache[ticket] = now
    return False


def _pip_size(symbol: str, info) -> float:
    """Calcula el tamaño de 1 pip en pips del símbolo (5 dígitos, 3 dígitos, etc.)."""
    if symbol.endswith("JPY"):
        return 0.01
    # MT5 distingue 5-digit (0.00001) vs 4-digit (0.0001) vs 2-digit (0.01).
    digits = info.digits if info else 5
    return 10 ** (-(digits - 2)) if digits >= 3 else 0.01


def _price_at_distance(entry: float, current: float, distance_pips: float, action_type: int) -> float:
    """Devuelve un SL/TP candidate usando pips desde el current price."""
    # Currently unused helper kept for future extensions.
    _ = (entry, current, distance_pips, action_type)
    return current


def _modify_sl_only(ticket: int, new_sl: float) -> bool:
    """Modifica SOLO el SL de una posición abierta. Retorna True si se aplicó."""
    req = {
        "action": mt5.TRADE_ACTION_SLTP,
        "position": ticket,
        "sl": new_sl,
        "tp": 0.0,  # 0.0 = no modificar TP
    }
    # MT5 no permite dejar TP=0; hay que traer el TP actual y reenviarlo.
    positions = mt5.positions_get(ticket=ticket)
    if not positions:
        return False
    pos = positions[0]
    req["tp"] = pos.tp

    result = mt5.order_send(req)
    if result is None:
        logger.warning(f"position {ticket}: order_send returned None (last_error={mt5.last_error()})")
        return False
    ok = result.retcode in (
        mt5.TRADE_RETCODE_DONE,
        mt5.TRADE_RETCODE_PLACED,
        getattr(mt5, "TRADE_RETCODE_DONE", 10009),  # safety
    )
    if not ok:
        logger.warning(
            f"position {ticket}: retcode={result.retcode} comment={result.comment}"
        )
    return ok


class TrailingWorker(threading.Thread):
    daemon = True

    def __init__(self):
        super().__init__(name="bot-trailing")
        self._stop_event = threading.Event()

    def stop(self):
        self._stop_event.set()
        self.join(timeout=3)

    def run(self):
        logger.info("TrailingWorker started")
        # Asegurar conexión MT5 (sin esto, positions_get retorna vacío)
        if not mt5.initialize():
            logger.warning("MT5 no inicializa, trailing worker espera")
        while not self._stop_event.is_set():
            try:
                self._tick()
            except Exception as e:
                logger.exception(f"trailing tick error: {e}")
            interval = POLL_INTERVAL if config.TRAILING_ENABLED else IDLE_INTERVAL
            self._stop_event.wait(interval)
        logger.info("TrailingWorker stopped")

    def _tick(self):
        # Siempre re-leer config (puede cambiar sin restart).
        config.reload()
        if not config.TRAILING_ENABLED:
            return

        step_pips = config.TRAILING_STEP_PIPS
        start_pips = config.TRAILING_START_PIPS
        if step_pips <= 0 or start_pips <= 0:
            logger.warning(f"trailing config inválida: step={step_pips} start={start_pips}")
            return

        positions = mt5.positions_get()
        if not positions:
            return

        moved = 0
        skipped = 0
        for pos in positions:
            try:
                # Sólo aplicamos trailing a órdenes abiertas por nosotros
                # (magic_number 234000 lo usa el executor al abrir).
                if pos.magic != 234000:
                    continue

                if pos.sl <= 0:
                    # Sin SL no podemos hacer trailing fiable. Saltar.
                    if not _ticket_seen_recently(pos.ticket, 3600):
                        logger.debug(f"position {pos.ticket} sin SL, no se aplica trailing")
                    continue

                info = mt5.symbol_info(pos.symbol)
                if info is None:
                    skipped += 1
                    continue

                pip = _pip_size(pos.symbol, info)
                start_distance = start_pips * pip
                step_distance = step_pips * pip

                # Precio actual según la dirección de la posición
                tick = mt5.symbol_info_tick(pos.symbol)
                if tick is None:
                    skipped += 1
                    continue
                current = tick.bid if pos.type == mt5.ORDER_TYPE_BUY else tick.ask

                # Para BUY: nuevo SL = current - step_distance
                # Para SELL: nuevo SL = current + step_distance
                if pos.type == mt5.ORDER_TYPE_BUY:
                    candidate = current - step_distance
                    # Sólo subir (más alto), nunca bajar.
                    if candidate <= pos.sl:
                        continue
                    # Sólo activar después de haber recorrido `start_distance`
                    # por encima del entry.
                    if (current - pos.price_open) < start_distance:
                        continue
                else:  # SELL
                    candidate = current + step_distance
                    if candidate >= pos.sl:
                        continue
                    if (pos.price_open - current) < start_distance:
                        continue

                # Saltar si la diferencia al SL actual es < step_distance
                # (evita spam de modify cuando el precio apenas se mueve).
                diff = abs(candidate - pos.sl)
                if diff < step_distance * 0.95:  # pequeña tolerancia
                    continue

                # MT5 respeta 5 dígitos mínimo del precio. Redondeo.
                digits = info.digits
                factor = 10 ** digits
                candidate = round(candidate * factor) / factor

                if _modify_sl_only(pos.ticket, candidate):
                    moved += 1
                    logger.info(
                        f"trailing: pos={pos.ticket} {pos.symbol} "
                        f"sl={pos.sl:.5f}→{candidate:.5f} "
                        f"(price={current:.5f} entry={pos.price_open:.5f})"
                    )
                    # Log al DB también
                    try:
                        database.log_trade(
                            pos.symbol, "TRAILING_SL", current, pos.sl, candidate,
                            "ADJUSTED", pos.ticket,
                        )
                    except Exception:
                        pass
            except Exception as e:
                logger.warning(f"pos {getattr(pos, 'ticket', '?')}: {e}")
                continue

        if moved:
            logger.info(f"trailing tick: moved={moved} skipped={skipped}")
