"""
Signal Copier - MT5 Executor
"""
import asyncio
import json
import logging
import math
import os
from pathlib import Path
import MetaTrader5 as mt5

logger = logging.getLogger("SignalCopier.Executor")


_PARTIAL_CFG_FILE = Path(os.getenv("BOT_DATA_DIR", r"D:\TradingBotMT5")) / "partial_configs.json"


def _persist_partial_configs(cfg: dict) -> None:
    """Serializa partial_configs a disco para sobrevivir reinicios."""
    try:
        _PARTIAL_CFG_FILE.parent.mkdir(parents=True, exist_ok=True)
        _PARTIAL_CFG_FILE.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    except Exception as e:
        logger.debug(f"persist_partial_configs error: {e}")


def _load_partial_configs() -> dict:
    """Carga partial_configs desde disco."""
    if not _PARTIAL_CFG_FILE.exists():
        return {}
    try:
        return json.loads(_PARTIAL_CFG_FILE.read_text(encoding="utf-8") or "{}")
    except Exception as e:
        logger.warning(f"load_partial_configs error: {e}")
        return {}


class MT5Executor:
    def __init__(self):
        self.connected = False
        self.last_order_ticket = None
        self._last_symbol = ""
        self.partial_configs = _load_partial_configs()
        if self.partial_configs:
            logger.info(f"Restaurados {len(self.partial_configs)} cierres parciales desde disco")

    def connect(self) -> bool:
        try:
            if not mt5.initialize():
                logger.error("MT5 no inicializado")
                return False
            
            info = mt5.account_info()
            if not info:
                logger.error("No se pudo obtener info de cuenta")
                return False
            
            logger.info(f"Conectado a MT5: {info.server} | Balance: ${info.balance:.2f}")
            self.connected = True
            return True
            
        except Exception as e:
            logger.error(f"Error conectando a MT5: {e}")
            return False

    def disconnect(self):
        if self.connected:
            mt5.shutdown()
            self.connected = False

    async def execute_trade(self, signal: dict) -> bool:
        """Ejecuta una orden en MT5"""
        if not self.connected:
            if not self.connect():
                return False

        try:
            symbol = signal.get("symbol")
            action = signal.get("action")

            if action == "CLOSE":
                return await self._close_positions(symbol)

            # Auto-seleccionar símbolo
            if not self._ensure_symbol(symbol):
                return False

            lot = signal.get("lot") or self._get_default_lot(symbol)
            price_info = self._get_price(symbol)

            if not price_info:
                return False

            from config import settings
            spread_points = price_info.get("spread_points", 0)
            max_spread = settings.MAX_SPREAD_POINTS
            if max_spread > 0 and spread_points > max_spread:
                logger.warning(
                    f"BLOQUEADO por spread: {symbol} spread={spread_points:.1f}pts > max={max_spread:.0f}pts"
                )
                return False

            price = signal.get("price")
            if not price:
                price = price_info["ask"] if action == "BUY" else price_info["bid"]

            order_type = mt5.ORDER_TYPE_BUY if action == "BUY" else mt5.ORDER_TYPE_SELL
            self._last_symbol = symbol

            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": lot,
                "type": order_type,
                "price": price_info["ask"] if action == "BUY" else price_info["bid"],
                "deviation": 10,
                "magic": 20260706,
                "comment": f"SignalCopier",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": self._get_filling_mode(),
            }

            if signal.get("sl"):
                request["sl"] = signal["sl"]

            if signal.get("tp") and len(signal["tp"]) > 0:
                request["tp"] = signal["tp"][0]

            # Si tiene precio rango, usar precio promedio
            if signal.get("price_range"):
                mid = (signal["price_range"][0] + signal["price_range"][1]) / 2
                request["price"] = mid
                logger.info(f"Usando precio rango: {mid}")

            logger.info(f"Enviando orden: {action} {lot} {symbol} @ {request['price']}")
            
            result = await asyncio.get_event_loop().run_in_executor(
                None, lambda: mt5.order_send(request)
            )

            if result is None:
                logger.error("order_send devolvió None")
                return False

            if result.retcode != mt5.TRADE_RETCODE_DONE:
                logger.error(f"Error MT5 [{result.retcode}]: {result.comment}")
                return False

            self.last_order_ticket = int(result.order)
            logger.info(f"Orden ejecutada: Ticket #{result.order} | Precio: {result.price}")

            from config import settings
            has_scaleout = settings.SCALEOUT_ENABLED and settings.SCALEOUT_LEVELS
            has_multi_tp = len(signal.get("tp", [])) > 1
            if has_multi_tp or has_scaleout:
                await self._setup_partial_closes(symbol, result.order, signal)

            return True

        except Exception as e:
            logger.error(f"Error ejecutando trade: {e}", exc_info=True)
            return False

    async def _close_positions(self, symbol: str = None) -> bool:
        """Cierra posiciones abiertas"""
        try:
            positions = mt5.positions_get(symbol=symbol) if symbol else mt5.positions_get()
            if not positions:
                logger.info("No hay posiciones para cerrar")
                return True

            for pos in positions:
                close_type = mt5.ORDER_TYPE_SELL if pos.type == 0 else mt5.ORDER_TYPE_BUY
                price = mt5.symbol_info_tick(pos.symbol).bid if pos.type == 0 else mt5.symbol_info_tick(pos.symbol).ask

                request = {
                    "action": mt5.TRADE_ACTION_DEAL,
                    "symbol": pos.symbol,
                    "volume": pos.volume,
                    "type": close_type,
                    "position": pos.ticket,
                    "price": price,
                    "deviation": 10,
                    "magic": 20260706,
                    "comment": "Close",
                    "type_time": mt5.ORDER_TIME_GTC,
                    "type_filling": self._get_filling_mode(),
                }

                result = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: mt5.order_send(request)
                )

                if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                    logger.info(f"Posición cerrada: Ticket #{pos.ticket}")
                else:
                    logger.error(f"Error cerrando #{pos.ticket}: {result.comment if result else 'None'}")

            return True

        except Exception as e:
            logger.error(f"Error cerrando posiciones: {e}")
            return False

    def _get_pip_value(self, symbol: str) -> float:
        """Retorna el valor de 1 pip en términos de precio para el símbolo."""
        sym_info = mt5.symbol_info(symbol)
        if not sym_info:
            return 0.0001
        return sym_info.point * 10

    def _calculate_scaleout_levels(
        self, total_volume: float, entry_price: float, action: str, symbol: str
    ) -> tuple:
        """Calcula niveles de scale-out desde la config.

        Usa floor() sobre lot_step para que volumenes den siempre
        valores limpios en microlotes (0.01).

        Returns:
            (tp_levels, percentages, volumes, is_scaleout)
        """
        from config import settings

        if not settings.SCALEOUT_ENABLED:
            return [], [], [], []

        levels_config = settings.SCALEOUT_LEVELS
        if not levels_config:
            return [], [], [], []

        sym_info = mt5.symbol_info(symbol)
        min_lot = sym_info.volume_min if sym_info else 0.01
        lot_step = sym_info.volume_step if sym_info else 0.01
        pip_value = self._get_pip_value(symbol)
        digits = sym_info.digits if sym_info else 5

        remaining = total_volume
        tp_levels = []
        percentages = []
        volumes = []
        is_scaleout = []

        for i, level in enumerate(levels_config):
            pips = int(level["pips"])
            pct = float(level["percent"])

            close_vol = math.floor(remaining * pct / 100 / lot_step) * lot_step
            close_vol = max(min_lot, close_vol)

            remaining_levels_after = len(levels_config) - len(tp_levels) - 1
            min_for_signal = min_lot * 1
            max_close = remaining - min_for_signal - (min_lot * remaining_levels_after)
            close_vol = min(close_vol, max_close)

            if close_vol < min_lot:
                continue

            if action == "BUY":
                tp_price = entry_price + pip_value * pips
            else:
                tp_price = entry_price - pip_value * pips

            tp_price = round(tp_price, digits)
            actual_pct = round(close_vol / total_volume * 100, 1)

            tp_levels.append(tp_price)
            percentages.append(actual_pct)
            volumes.append(close_vol)
            is_scaleout.append(True)
            remaining -= close_vol

        return tp_levels, percentages, volumes, is_scaleout

    async def _setup_partial_closes(self, symbol: str, order_ticket: int, signal: dict):
        """
        Configura cierres parciales combinando scale-out (por pips) + TP de la señal.
        Los scale-out se ejecutan primeros, luego los TP de la señal.
        """
        try:
            await asyncio.sleep(2)

            positions = mt5.positions_get(symbol=symbol)
            if not positions:
                return

            position = None
            for pos in positions:
                if pos.ticket == order_ticket or (pos.symbol == symbol and pos.magic == 20260706):
                    position = pos
                    break

            if not position:
                position = positions[-1]

            total_volume = position.volume
            entry = signal.get("price") or position.price_open
            action = "BUY" if position.type == mt5.ORDER_TYPE_BUY else "SELL"

            # 1. Calcular niveles de scale-out
            so_tp, so_pct, so_vol, so_flag = self._calculate_scaleout_levels(
                total_volume, entry, action, symbol
            )

            # 2. Calcular niveles de TP de la senal (sobre volumen restante)
            remaining = total_volume - sum(so_vol)
            tp_list = signal.get("tp", [])
            tp_percentages = signal.get("tp_percentages", [100])

            sig_tp = []
            sig_pct = []
            sig_vol = []

            if remaining >= 0.01 and tp_list:
                sym_info = mt5.symbol_info(symbol)
                min_vol = sym_info.volume_min if sym_info else 0.01

                for i, (tp_price, pct) in enumerate(zip(tp_list, tp_percentages)):
                    close_vol = round(remaining * pct / 100, 2)

                    if close_vol < min_vol:
                        close_vol = min_vol

                    if i == len(tp_list) - 1:
                        already = sum(
                            round(remaining * p / 100, 2) for p in tp_percentages[:i]
                        )
                        close_vol = round(remaining - already, 2)

                    if close_vol >= min_vol:
                        sig_tp.append(tp_price)
                        sig_pct.append(pct)
                        sig_vol.append(close_vol)

            # 3. Combinar: scale-out levels primero, luego signal TP
            all_tp = so_tp + sig_tp
            all_pct = so_pct + sig_pct
            all_vol = so_vol + sig_vol
            all_flag = so_flag + [False] * len(sig_tp)

            if not all_tp:
                return

            self.partial_configs[int(position.ticket)] = {
                "symbol": symbol,
                "action": action,
                "entry_price": entry,
                "tp_levels": all_tp,
                "percentages": all_pct,
                "volumes": all_vol,
                "original_volume": total_volume,
                "executed_indices": [],
                "is_scaleout": all_flag,
                "channel": signal.get("channel", ""),
            }
            _persist_partial_configs(self.partial_configs)

            logger.info(f"Cierres parciales configurados para ticket #{position.ticket}:")
            so_count = len(so_tp)
            for i, (tp, vol) in enumerate(zip(all_tp, all_vol)):
                label = f"SC{i+1}" if i < so_count else f"TP{i+1-so_count}"
                logger.info(f"  {label} @ {tp}: {vol} ({all_pct[i]}%)")

        except Exception as e:
            logger.error(f"Error configurando cierres parciales: {e}")

    def _ensure_symbol(self, symbol: str) -> bool:
        """Asegura que el símbolo esté disponible"""
        info = mt5.symbol_info(symbol)
        if info is None:
            # Buscar variaciones
            variations = [
                symbol, symbol + ".Raw", symbol + ".r", symbol + ".m",
                symbol.replace("USD", ""), symbol + "USD",
            ]
            for var in variations:
                info = mt5.symbol_info(var)
                if info is not None:
                    logger.info(f"Símbolo encontrado: {var}")
                    return True
            
            logger.error(f"Símbolo no encontrado: {symbol}")
            return False

        if not info.visible:
            if not mt5.symbol_select(symbol, True):
                logger.error(f"No se pudo seleccionar {symbol}")
                return False

        return True

    def _get_price(self, symbol: str) -> dict:
        """Obtiene precio actual"""
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            logger.error(f"No se pudo obtener precio de {symbol}")
            return None

        sym_info = mt5.symbol_info(symbol)
        point = sym_info.point if sym_info else 0.00001
        spread_points = (tick.ask - tick.bid) / point if point > 0 else 0

        return {
            "bid": tick.bid,
            "ask": tick.ask,
            "spread": spread_points / 10 if "JPY" not in symbol else spread_points / 100,
            "spread_points": spread_points,
        }

    def _get_default_lot(self, symbol: str) -> float:
        """Calcula lote según modo configurado"""
        from config import settings

        info = mt5.account_info()
        sym_info = mt5.symbol_info(symbol)

        if not info or not sym_info:
            return 0.01

        balance = info.balance
        min_lot = sym_info.volume_min
        max_lot = sym_info.volume_max
        lot_step = sym_info.volume_step

        if settings.LOT_MODE == "percent":
            risk_amount = balance * (settings.LOT_RISK_PERCENT / 100)
            tick_value = sym_info.trade_tick_value
            tick_size = sym_info.trade_tick_size

            if tick_value > 0 and tick_size > 0:
                lot = risk_amount / (tick_value * 100)
            else:
                lot = risk_amount / 10000
        else:
            lot = settings.LOT_SIZE

        lot = max(min_lot, min(lot, max_lot))
        lot = round(lot / lot_step) * lot_step
        lot = round(lot, 2)

        logger.info(f"Lot calculado: {lot} (modo={settings.LOT_MODE}, balance=${balance:.2f})")
        return lot

    def _get_filling_mode(self) -> int:
        """Retorna modo de filling compatible (FOK con fallback IOC)"""
        try:
            info = mt5.symbol_info(self._last_symbol)
            if info and info.filling_mode:
                modes = info.filling_mode
                if modes & mt5.SYMBOL_FILLING_FOK:
                    return mt5.ORDER_FILLING_FOK
                if modes & mt5.SYMBOL_FILLING_IOC:
                    return mt5.ORDER_FILLING_IOC
        except Exception:
            pass
        return mt5.ORDER_FILLING_FOK


class MT5Monitor:
    """Monitor de posiciones para cierres parciales"""

    def __init__(self, executor: MT5Executor, tnsvt_client=None):
        self.running = False
        self.executor = executor
        self.tnsvt_client = tnsvt_client

    async def start(self):
        self.running = True
        logger.info("Monitor de posiciones iniciado")

        while self.running:
            try:
                await asyncio.sleep(3)

                if not self.executor.partial_configs:
                    continue

                positions = mt5.positions_get(magic=20260706) or []
                open_tickets = {int(p.ticket) for p in positions}

                for ticket_str in list(self.executor.partial_configs.keys()):
                    ticket = int(ticket_str)
                    if ticket not in open_tickets:
                        self.executor.partial_configs.pop(ticket_str, None)
                        _persist_partial_configs(self.executor.partial_configs)
                        logger.info(f"Ticket #{ticket} ya no existe, removido de cierres parciales")
                        continue

                    pos = next((p for p in positions if int(p.ticket) == ticket), None)
                    if pos:
                        await self._check_partial_close(pos)

            except Exception as e:
                logger.error(f"Error en monitor: {e}")

    async def _check_partial_close(self, position):
        """Verifica si hay que cerrar parcial según niveles TP y scale-out."""
        ticket = int(position.ticket)
        config = self.executor.partial_configs.get(ticket)
        if not config:
            return

        symbol = config["symbol"]
        action = config["action"]
        tick = mt5.symbol_info_tick(symbol)
        if not tick:
            return

        is_scaleout_list = config.get("is_scaleout", [])
        so_count = sum(1 for s in is_scaleout_list if s)
        current_price = tick.bid if action == "BUY" else tick.ask

        for i in range(len(config["tp_levels"])):
            if i in config["executed_indices"]:
                continue

            tp_level = config["tp_levels"][i]
            tp_hit = (
                (action == "BUY" and current_price >= tp_level)
                or (action == "SELL" and current_price <= tp_level)
            )

            if not tp_hit:
                continue

            close_volume = config["volumes"][i]
            remaining_volume = position.volume

            if close_volume > remaining_volume:
                close_volume = remaining_volume

            close_type = mt5.ORDER_TYPE_SELL if action == "BUY" else mt5.ORDER_TYPE_BUY
            close_price = mt5.symbol_info_tick(symbol).bid if action == "BUY" else mt5.symbol_info_tick(symbol).ask
            if not close_price:
                continue

            label = f"SC{i+1}" if (i < so_count) else f"TP{i+1-so_count}"

            close_request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": close_volume,
                "type": close_type,
                "position": ticket,
                "price": close_price,
                "deviation": 10,
                "magic": 20260706,
                "comment": label,
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }

            result = await asyncio.get_event_loop().run_in_executor(
                None, lambda: mt5.order_send(close_request)
            )

            if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                config["executed_indices"].append(i)

                pct = config["percentages"][i]
                is_so = i < so_count
                label_type = "SC" if is_so else "TP"
                logger.info(
                    f"{label} ejecutado: {symbol} ticket #{ticket} "
                    f"@{tp_level} vol={close_volume} ({pct}%) (${result.price:.2f})"
                )

                if self.tnsvt_client and self.tnsvt_client.enabled:
                    pnl_hit = 0.0
                    try:
                        from datetime import datetime, timedelta
                        deals = mt5.history_deals_get(
                            datetime.now() - timedelta(hours=1),
                            datetime.now(),
                            position=ticket,
                        ) or []
                        for d in deals:
                            if d.entry == mt5.DEAL_ENTRY_OUT and abs(d.volume - close_volume) < 0.001:
                                pnl_hit = float(getattr(d, "profit", 0) or 0)
                                break
                    except Exception:
                        pass
                    self.tnsvt_client.log_trade(
                        symbol=symbol,
                        action="CLOSE" if action == "BUY" else "CLOSE",
                        price=close_price,
                        result=f"{label_type}_PARTIAL:{pct}%",
                        pnl=pnl_hit,
                        channel=config.get("channel", ""),
                        volume=close_volume,
                        notes=f"{label}: {pct}% vol={close_volume} ticket={ticket}",
                    )

                if i >= so_count:
                    signal_already_executed = any(
                        idx in config["executed_indices"]
                        for idx in range(i)
                        if idx >= so_count
                    )
                    if not signal_already_executed:
                        await asyncio.sleep(0.5)
                        sl_request = {
                            "action": mt5.TRADE_ACTION_SLTP,
                            "symbol": symbol,
                            "position": ticket,
                            "sl": config["entry_price"],
                            "tp": 0,
                        }
                        sl_result = await asyncio.get_event_loop().run_in_executor(
                            None, lambda: mt5.order_send(sl_request)
                        )
                        if sl_result and sl_result.retcode == mt5.TRADE_RETCODE_DONE:
                            logger.info(f"SL movido a breakeven ({config['entry_price']}) para ticket #{ticket}")
                        else:
                            logger.warning(f"SL a breakeven falló para ticket #{ticket}: {sl_result}")
            else:
                err = result.comment if result else "order_send returned None"
                logger.warning(f"{label} falló para ticket #{ticket}: {err}")

        executed_count = len(config["executed_indices"])
        total_count = len(config["tp_levels"])
        if executed_count >= total_count:
            self.executor.partial_configs.pop(ticket, None)
            _persist_partial_configs(self.executor.partial_configs)
            logger.info(f"Todos los niveles ejecutados para ticket #{ticket}")
        elif len(config["executed_indices"]) > 0:
            # Persistir progreso de indices ejecutados
            _persist_partial_configs(self.executor.partial_configs)

    def stop(self):
        self.running = False
        logger.info("Monitor de posiciones detenido")
