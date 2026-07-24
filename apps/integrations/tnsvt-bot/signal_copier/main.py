"""
Signal Copier - Main v2 (con integracion TNSVT)
"""
import asyncio
import json
import logging
import os
import sys
import time
from pathlib import Path

import requests

ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(ROOT_DIR / "scripts"))

from telethon import TelegramClient, events
from config import settings
from signal_copier.parser import SignalParserV3
from signal_copier.executor import MT5Executor, MT5Monitor
from signal_copier.risk_manager import RiskManager
from signal_copier.news_filter import NewsFilter
from signal_copier.database import init_db, log_trade, update_trade_pnl, update_last_trade
from tnsvt_client import TNSVTClient

logging.basicConfig(
    format="%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("signal_copier.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("SignalCopier")

parser = SignalParserV3()
executor = MT5Executor()
risk_manager = RiskManager()
news_filter = NewsFilter()
tnsvt_client = TNSVTClient()
mt5_monitor = MT5Monitor(executor, tnsvt_client=tnsvt_client)

pending_signals = {}

TRADE_MAP_FILE = ROOT_DIR / "var" / "tnsvt_trade_map.json"
MT5_STATUS_FILE = ROOT_DIR / "var" / "mt5_status.json"
PENDING_SIGNALS_FILE = ROOT_DIR / "var" / "pending_signals.json"
CMD_REQUESTS_FILE = Path(r"D:\TradingBotMT5") / "cmd_requests.json"
CMD_RESPONSES_FILE = Path(r"D:\TradingBotMT5") / "cmd_responses.json"

try:
    TRADE_MAP_FILE.parent.mkdir(parents=True, exist_ok=True)
except Exception:
    pass

trade_map: dict = {}
if TRADE_MAP_FILE.exists():
    try:
        trade_map = json.loads(TRADE_MAP_FILE.read_text(encoding="utf-8") or "{}")
        logger.info(f"Cargados {len(trade_map)} mapeos ticket→trade_id")
    except Exception as e:
        logger.warning(f"No se pudo cargar trade_map: {e}")
        trade_map = {}


def save_trade_map():
    try:
        TRADE_MAP_FILE.write_text(json.dumps(trade_map, indent=2), encoding="utf-8")
    except Exception as e:
        logger.debug(f"Error guardando trade_map: {e}")


def _save_pending_signals():
    try:
        PENDING_SIGNALS_FILE.parent.mkdir(parents=True, exist_ok=True)
        PENDING_SIGNALS_FILE.write_text(json.dumps(pending_signals, indent=2), encoding="utf-8")
    except Exception as e:
        logger.debug(f"Error guardando pending_signals: {e}")


def _load_pending_signals() -> dict:
    if PENDING_SIGNALS_FILE.exists():
        try:
            data = json.loads(PENDING_SIGNALS_FILE.read_text(encoding="utf-8") or "{}")
            logger.info(f"Cargadas {len(data)} senales pendientes desde archivo")
            return data
        except Exception as e:
            logger.warning(f"No se pudo cargar pending_signals: {e}")
    return {}


def _log_to_bridge(signal: dict, result: str, channel: str = "",
                   pnl: float = 0, ticket: int = 0, log_to_bridge=True, **extra):
    """Helper: loguea a DB local + opcionalmente al TNSVT bridge.

    Garantiza que TODO intento de trade (bloqueado, exitoso, fallido,
    cierre parcial) quede registrado en la base del bridge para que
    el dashboard \"Por Canal\" / \"Por Símbolo\" lo refleje.

    Args:
        log_to_bridge: Si False, solo registra en DB local (para el
                       path success donde luego se llama manualmente
                       tnsvt_client.log_trade con result='OPEN').
    """
    log_trade(
        signal.get("symbol", ""),
        signal.get("action", ""),
        signal.get("price"),
        signal.get("sl"),
        signal.get("tp"),
        result,
        ticket=ticket,
        channel=channel,
    )
    if log_to_bridge and tnsvt_client.enabled:
        tnsvt_client.log_trade(
            symbol=signal.get("symbol", ""),
            action=signal.get("action", ""),
            price=signal.get("price"),
            sl=signal.get("sl"),
            tp=signal.get("tp"),
            result=result,
            pnl=pnl,
            channel=channel,
            **extra,
        )


def _notify_bot(event_type: str, signal: dict, ticket: int = 0,
                channel: str = "", pnl: float = 0, result: str = "",
                reason: str = "") -> None:
    """Encola un evento de trade en el bridge-api para que el bot lo publique al grupo.

    Fire-and-forget: si falla (timeout, bridge caído), solo se loguea un warning
    y el flujo del signal_copier continúa sin bloquearse.
    """
    try:
        payload = {
            "type": event_type,
            "symbol": signal.get("symbol", ""),
            "action": signal.get("action", ""),
            "price": signal.get("price"),
            "sl": signal.get("sl"),
            "tp": signal.get("tp") or [],
            "ticket": str(ticket or 0),
            "channel": channel,
        }
        if pnl:
            payload["pnl"] = pnl
        if result:
            payload["result"] = result
        if reason:
            payload["reason"] = reason

        bridge_url = "http://localhost:8522/api/v1/bridge/events"
        requests.post(bridge_url, json=payload, timeout=3)
        logger.debug(f"_notify_bot: {event_type} {payload.get('symbol')}")
    except Exception as e:
        logger.debug(f"_notify_bot failed (non-fatal): {e}")


client = TelegramClient(
    "signal_copier/session",
    settings.TELETHON_API_ID,
    settings.TELETHON_API_HASH,
)


@client.on(events.NewMessage)
async def handler(event):
    try:
        chat = await event.get_chat()
        chat_name = getattr(chat, "title", getattr(chat, "username", "Unknown"))

        is_monitored = False
        for mon_channel in settings.CHANNELS_TO_MONITOR:
            if mon_channel.lower() in chat_name.lower():
                is_monitored = True
                break

        if not is_monitored:
            return

        logger.info(f"Nuevo mensaje en: {chat_name}")
        logger.info(f"Contenido: {event.raw_text}")

        pending = pending_signals.get(chat_name)
        signal = parser.parse_message(event.raw_text, pending)

        if signal.get("is_update") and pending:
            logger.info(f"Actualizando SL/TP a senal pendiente: {pending.get('symbol')}")

            if signal.get("sl"):
                pending["sl"] = signal["sl"]
            if signal.get("tp"):
                for tp in signal["tp"]:
                    if tp not in pending.get("tp", []):
                        pending.setdefault("tp", []).append(tp)

            if parser.has_sl_tp(pending):
                logger.info(f"Senal completa, ejecutando: {pending['action']} {pending['symbol']}")
                pending_signals.pop(chat_name, None)
                _save_pending_signals()
                await execute_signal(pending, chat_name)
            else:
                logger.info("SL/TP actualizado, esperando mas datos")
                pending_signals[chat_name] = pending
                _save_pending_signals()
            return

        if parser.is_valid_signal(signal):
            logger.info(f"Senal detectada: {signal['action']} {signal['symbol']}")

            log_trade(
                signal["symbol"],
                signal["action"],
                signal.get("price"),
                signal.get("sl"),
                signal.get("tp"),
                "SEÑAL DETECTADA",
                channel=chat_name,
            )

            if signal["action"] == "CLOSE":
                logger.info("Senal CLOSE, ejecutando cierre directo...")
                await execute_signal(signal, chat_name)
            elif parser.has_sl_tp(signal):
                logger.info("Senal completa, ejecutando...")
                await execute_signal(signal, chat_name)
            else:
                logger.info("Senal sin SL/TP, guardando como pendiente...")
                pending_signals[chat_name] = signal
                _save_pending_signals()
                await event.reply(
                    f"✅ Senal recibida: {signal['action']} {signal['symbol']}\n"
                    f"⏳ Esperando SL/TP...\n"
                    f"📝 Envia SL y TP en el proximo mensaje"
                )
        else:
            logger.debug("No se detecto senal valida")

    except Exception as e:
        logger.error(f"Error procesando mensaje: {e}", exc_info=True)


async def execute_signal(signal: dict, channel: str):
    """Ejecuta una senal completa (incluye senales CLOSE)"""
    try:
        if signal.get("action") == "CLOSE":
            logger.info(f"Ejecutando cierre de {signal['symbol']}...")
            success = await executor.execute_trade(signal)

            result_msg = "CLOSED" if success else "ERROR_CLOSE"
            last_ticket = executor.last_order_ticket or 0
            update_last_trade(
                signal["symbol"],
                signal["action"],
                result_msg,
                ticket=last_ticket,
                pnl=0,
            )

            _log_to_bridge(signal, result_msg, channel=channel, ticket=last_ticket, log_to_bridge=False)

            if tnsvt_client.enabled and success:
                trade_entry = {
                    "symbol": signal["symbol"],
                    "action": signal["action"],
                    "channel": channel,
                    "opened_at": asyncio.get_event_loop().time(),
                }
                trade_id = tnsvt_client.log_trade(
                    symbol=signal["symbol"],
                    action=signal["action"],
                    price=signal.get("price"),
                    sl=signal.get("sl"),
                    tp=signal.get("tp"),
                    result="CLOSE",
                    channel=channel,
                )
                if trade_id:
                    trade_entry["trade_id"] = trade_id
                trade_map[str(last_ticket)] = trade_entry
                save_trade_map()
                logger.debug(f"Mapeo de cierre guardado: ticket {last_ticket}")

            return

        if news_filter.enabled:
            blocked, reason = news_filter.should_block_trade()
            if blocked:
                logger.warning(f"BLOQUEADO por noticias: {reason}")
                _log_to_bridge(signal, f"BLOQUEADO: {reason}", channel=channel)
                _notify_bot("trade_blocked", signal, channel=channel, reason=f"news: {reason}")
                return

        can_open_now, reason_time = risk_manager.can_open_now()
        if not can_open_now:
            logger.warning(f"BLOQUEADO por horario: {reason_time}")
            _log_to_bridge(signal, f"BLOQUEADO: {reason_time}", channel=channel)
            _notify_bot("trade_blocked", signal, channel=channel, reason=reason_time)
            return

        sym = signal.get("symbol", "")
        act = signal.get("action", "")
        corr_ok, corr_reason = risk_manager.check_correlation(sym, act)
        if not corr_ok:
            logger.warning(f"BLOQUEADO por correlacion: {corr_reason}")
            _log_to_bridge(signal, f"BLOQUEADO: {corr_reason}", channel=channel)
            _notify_bot("trade_blocked", signal, channel=channel, reason=corr_reason)
            return

        can_trade, reason = risk_manager.can_open_trade()
        if not can_trade:
            logger.warning(f"BLOQUEADO por riesgo: {reason}")
            _log_to_bridge(signal, f"BLOQUEADO: {reason}", channel=channel)
            _notify_bot("trade_blocked", signal, channel=channel, reason=f"risk: {reason}")
            return

        success = await executor.execute_trade(signal)

        result_msg = "OK" if success else "ERROR"
        _log_to_bridge(signal, result_msg, channel=channel, log_to_bridge=not success)

        if success:
            risk_manager.increment_trades_today()
            await risk_manager.check_trailing_stop_async(signal["symbol"])
            _notify_bot(
                "trade_open", signal,
                ticket=executor.last_order_ticket or 0,
                channel=channel,
            )

            await risk_manager.check_trailing_stop_async(signal["symbol"])

            trade_id = tnsvt_client.log_trade(
                symbol=signal["symbol"],
                action=signal["action"],
                price=signal.get("price"),
                sl=signal.get("sl"),
                tp=signal.get("tp"),
                result="OPEN",
                channel=channel,
            )
            if trade_id:
                logger.info(f"Auto-journal en TNSVT: trade #{trade_id}")
                last_ticket = executor.last_order_ticket
                if last_ticket:
                    trade_map[str(last_ticket)] = {
                        "trade_id": trade_id,
                        "symbol": signal["symbol"],
                        "action": signal["action"],
                        "channel": channel,
                        "opened_at": asyncio.get_event_loop().time(),
                    }
                    save_trade_map()
                    logger.debug(f"Mapeo guardado: ticket {last_ticket} -> trade #{trade_id}")

    except Exception as e:
        logger.error(f"Error ejecutando senal: {e}", exc_info=True)


async def mt5_trade_monitor():
    """Monitorea trades abiertos en MT5 y cuando se cierran, actualiza TNSVT con PnL."""
    import MetaTrader5 as mt5

    while True:
        try:
            await asyncio.sleep(10)

            if not tnsvt_client.enabled or not executor.connected:
                continue

            if not trade_map:
                continue

            try:
                positions = mt5.positions_get(magic=20260706) or []
            except Exception:
                positions = []

            open_tickets = {int(p.ticket) for p in positions}

            closed_tickets = []
            for ticket_str in list(trade_map.keys()):
                ticket = int(ticket_str)
                if ticket not in open_tickets:
                    closed_tickets.append(ticket_str)

            if not closed_tickets:
                continue

            for ticket_str in closed_tickets:
                entry = trade_map.pop(ticket_str, None)
                if not entry:
                    continue

                trade_id = entry.get("trade_id")
                if not trade_id:
                    continue

                try:
                    from datetime import datetime, timedelta

                    since = datetime.now() - timedelta(days=7)
                    deals = mt5.history_deals_get(since, datetime.now(), position=int(ticket_str)) or []
                except Exception as e:
                    logger.debug(f"history_deals_get error: {e}")
                    deals = []

                pnl = 0.0
                result_label = "CLOSED"
                for d in deals:
                    if getattr(d, "position", None) == int(ticket_str) and d.entry == mt5.DEAL_ENTRY_OUT:
                        pnl += float(getattr(d, "profit", 0) or 0)
                        pnl += float(getattr(d, "swap", 0) or 0)
                        pnl += float(getattr(d, "commission", 0) or 0)

                if pnl > 0:
                    result_label = "WIN"
                elif pnl < 0:
                    result_label = "LOSS"
                else:
                    result_label = "BREAKEVEN"

                risk_manager.update_pnl(pnl)
                update_trade_pnl(int(ticket_str), pnl, result_label)

                _notify_bot(
                    "trade_close",
                    {
                        "symbol": entry.get("symbol", ""),
                        "action": entry.get("action", ""),
                        "price": 0,
                        "sl": None,
                        "tp": [],
                    },
                    ticket=int(ticket_str),
                    channel=entry.get("channel", ""),
                    pnl=pnl,
                    result=result_label,
                )

                ok = tnsvt_client.update_trade(
                    trade_id=trade_id,
                    result=result_label,
                    pnl=pnl,
                )

                if ok:
                    logger.info(
                        f"Trade #{trade_id} (ticket {ticket_str}) cerrado: "
                        f"{result_label} PnL=${pnl:+.2f}"
                    )
                else:
                    logger.warning(f"No se pudo actualizar trade #{trade_id} en TNSVT")

            save_trade_map()

        except Exception as e:
            logger.error(f"Error en mt5_trade_monitor: {e}", exc_info=True)


async def trailing_stop_loop():
    """Ajusta el SL de posiciones abiertas cada 3 segundos.

    ANTES: el trailing se ejecutaba solo cuando llegaba una NUEVA senal
    para el mismo simbolo (bug). Esto dejaba al SL congelado si no
    llegaban mas senales — riesgo alto.

    AHORA: corre continuo y revisa TODAS las posiciones con magic=20260706.
    Flujo: BE primero (mover SL a entry) → trailing (perseguir precio).

    Solo activa si RISK_TRAILING_STOP=true.
    """
    import MetaTrader5 as mt5

    while True:
        try:
            await asyncio.sleep(3)

            if not executor.connected:
                continue

            cfg = risk_manager.config
            if not cfg.get("trailing_stop"):
                continue

            try:
                positions = mt5.positions_get(magic=20260706) or []
            except Exception:
                continue

            if not positions:
                continue

            trailing_start = float(cfg.get("trailing_start", 50))
            trailing_step = float(cfg.get("trailing_step", 10))
            be_enabled = cfg.get("breakeven_enabled", False)
            be_pips = float(cfg.get("breakeven_pips", 8.0))

            adjusted = 0
            for pos in positions:
                symbol = pos.symbol
                try:
                    tick = mt5.symbol_info_tick(symbol)
                    if not tick:
                        continue

                    if pos.type == mt5.ORDER_TYPE_BUY:
                        current_price = tick.bid
                        profit_points = current_price - pos.price_open
                        entry_price = pos.price_open
                    else:
                        current_price = tick.ask
                        profit_points = pos.price_open - current_price
                        entry_price = pos.price_open

                    current_sl = pos.sl if pos.sl else 0.0

                    # --- FASE 0: Break Even ---
                    # Si BE activado, profit >= BE pips, y SL no esta en entry:
                    # mover SL a entry (una sola vez)
                    if be_enabled and profit_points >= be_pips:
                        if pos.type == mt5.ORDER_TYPE_BUY:
                            be_sl = entry_price
                        else:
                            be_sl = entry_price

                        be_needed = (
                            current_sl == 0.0
                            or (pos.type == mt5.ORDER_TYPE_BUY and abs(current_sl - entry_price) > 0.00001 and current_sl < entry_price)
                            or (pos.type == mt5.ORDER_TYPE_SELL and abs(current_sl - entry_price) > 0.00001 and current_sl > entry_price)
                        )
                        if be_needed:
                            be_request = {
                                "action": mt5.TRADE_ACTION_SLTP,
                                "symbol": symbol,
                                "position": pos.ticket,
                                "sl": be_sl,
                                "tp": pos.tp,
                            }
                            be_result = await asyncio.get_event_loop().run_in_executor(
                                None, lambda: mt5.order_send(be_request)
                            )
                            if be_result and be_result.retcode == mt5.TRADE_RETCODE_DONE:
                                adjusted += 1
                                logger.info(
                                    f"BE: {symbol} #{pos.ticket} "
                                    f"SL {current_sl:.5f} -> {be_sl:.5f} (entry) "
                                    f"profit={profit_points:.5f}"
                                )
                                current_sl = be_sl
                            elif be_result:
                                logger.debug(f"BE fallo {symbol} #{pos.ticket}: retcode={be_result.retcode}")

                    # --- FASE 1: Trailing Stop (solo si profit >= trailing_start) ---
                    if profit_points < trailing_start:
                        continue

                    if pos.type == mt5.ORDER_TYPE_BUY:
                        new_sl = current_price - trailing_step
                    else:
                        new_sl = current_price + trailing_step

                    should_move = (
                        current_sl == 0.0
                        or (pos.type == mt5.ORDER_TYPE_BUY and new_sl > current_sl)
                        or (pos.type == mt5.ORDER_TYPE_SELL and new_sl < current_sl)
                    )
                    if not should_move:
                        continue

                    request = {
                        "action": mt5.TRADE_ACTION_SLTP,
                        "symbol": symbol,
                        "position": pos.ticket,
                        "sl": new_sl,
                        "tp": pos.tp,
                    }

                    result = await asyncio.get_event_loop().run_in_executor(
                        None, lambda: mt5.order_send(request)
                    )
                    if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                        adjusted += 1
                        logger.info(
                            f"trailing: {symbol} #{pos.ticket} "
                            f"SL {current_sl:.5f} -> {new_sl:.5f} "
                            f"(profit={profit_points:.5f})"
                        )
                    elif result:
                        logger.debug(
                            f"trailing: {symbol} #{pos.ticket} "
                            f"fallo retcode={result.retcode}"
                        )
                except Exception as e:
                    logger.debug(f"trailing pos error {symbol}: {e}")
                    continue

            if adjusted:
                logger.debug(f"trailing_stop_loop: ajustadas {adjusted} posiciones")
        except Exception as e:
            logger.error(f"trailing_stop_loop error: {e}", exc_info=True)


async def time_exit_loop():
    """Loop de cierre temporal. Corre cada 60s y cierra posiciones que:
    - Excedieron RISK_MAX_HOLD_HOURS (maximo tiempo abiertas)
    - Estan abiertas en viernes >= 17 ART (cierre semanal)
    """
    from signal_copier.time_exit import (
        get_positions_to_close_by_hold,
        get_positions_to_close_friday,
    )
    import MetaTrader5 as mt5

    while True:
        try:
            await asyncio.sleep(60)

            if not executor.connected:
                continue

            cfg = risk_manager.config

            # 1. Cierre por tiempo maximo
            hold_items = get_positions_to_close_by_hold(cfg)
            for item in hold_items:
                logger.warning(
                    f"time_exit: cerrando {item['symbol']} #{item['ticket']} "
                    f"por {item['reason']}"
                )
                await executor._close_positions(item["symbol"])
                _notify_bot("trade_blocked", {"symbol": item["symbol"]},
                            channel="time_exit", reason=item["reason"])

            # 2. Cierre por viernes
            fri_items = get_positions_to_close_friday(cfg)
            for item in fri_items:
                logger.warning(
                    f"time_exit: cerrando {item['symbol']} #{item['ticket']} "
                    f"por {item['reason']}"
                )
                await executor._close_positions(item["symbol"])
                _notify_bot("trade_blocked", {"symbol": item["symbol"]},
                            channel="time_exit", reason=item["reason"])

        except Exception as e:
            logger.error(f"time_exit_loop error: {e}", exc_info=True)


async def news_closer():
    """Cierra posiciones antes de noticias de alto impacto"""
    while True:
        try:
            await asyncio.sleep(15)

            if not news_filter.enabled:
                continue

            positions_to_close = news_filter.get_positions_to_close()
            for item in positions_to_close:
                symbol = item["symbol"]
                reason = item["reason"]
                logger.info(f"Cerrando posiciones por noticias: {symbol} - {reason}")
                await executor._close_positions(symbol)

        except Exception as e:
            logger.error(f"Error en news_closer: {e}")


async def config_watcher():
    """Vigila cambios en la configuracion y recarga automaticamente"""
    trigger_file = ROOT_DIR / "config" / "reload.trigger"
    last_modified = 0

    while True:
        try:
            await asyncio.sleep(2)

            if trigger_file.exists():
                current_mtime = trigger_file.stat().st_mtime
                if current_mtime > last_modified:
                    last_modified = current_mtime
                    logger.info("Configuracion cambiada, recargando...")

                    settings.reload()
                    risk_manager.reload_config()
                    news_filter.reload_config()

                    try:
                        trigger_file.unlink()
                    except Exception:
                        pass

                    logger.info("Configuracion recargada exitosamente")

        except Exception as e:
            logger.error(f"Error en config_watcher: {e}")


_cached_telegram_bot = ""
_cached_bot_username = ""


async def tnsvt_heartbeat():
    """Envia heartbeat periodico a TNSVT (1 HTTP call, cachea campos previos)"""
    global _cached_telegram_bot, _cached_bot_username

    while True:
        try:
            await asyncio.sleep(30)

            if not tnsvt_client.enabled:
                continue

            status = risk_manager.get_status()
            status["service"] = "signal_copier"
            status["running"] = True
            status["channels"] = settings.CHANNELS_TO_MONITOR
            status["mt5_connected"] = executor.connected
            status["news_filter"] = news_filter.enabled
            if _cached_telegram_bot:
                status["telegram_bot"] = _cached_telegram_bot
            if _cached_bot_username:
                status["bot_username"] = _cached_bot_username

            resp = tnsvt_client.send_heartbeat(status)
            if resp and isinstance(resp, dict):
                prev_status = resp.get("status", {})
                if prev_status.get("telegram_bot"):
                    _cached_telegram_bot = prev_status["telegram_bot"]
                if prev_status.get("bot_username"):
                    _cached_bot_username = prev_status["bot_username"]

        except Exception as e:
            logger.debug(f"TNSVT heartbeat error: {e}")


async def mt5_status_writer():
    """Escribe estado completo de MT5 a archivo compartido para el dashboard y /historial.

    Tambien escribe los archivos legacy (account_snapshot.json y positions_snapshot.json)
    en D:\\TradingBotMT5 que consume el frontend Vite — el mt5_multi_snapshot.py
    original no convive con esta conexion MT5 (sesion unica), asi que ahora
    el signal_copier hace ambos roles.
    """
    while True:
        try:
            await asyncio.sleep(5)
            MT5_STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
            from datetime import datetime
            import MetaTrader5 as mt5

            data = {
                "connected": executor.connected,
                "timestamp": datetime.now().isoformat(),
            }

            if executor.connected:
                try:
                    info = mt5.account_info()
                    if info:
                        data["balance"] = round(info.balance, 2)
                        data["equity"] = round(info.equity, 2)
                        data["margin"] = round(info.margin, 2)
                        data["free_margin"] = round(info.margin_free, 2)
                        data["profit"] = round(info.profit, 2)
                        data["leverage"] = info.leverage
                        data["currency"] = info.currency
                        data["server"] = info.server
                        data["login"] = info.login
                    positions = mt5.positions_get() or []
                    data["open_positions"] = len(positions)
                    data["positions"] = []
                    legacy_positions = []
                    for p in positions:
                        pos = {
                            "ticket": p.ticket,
                            "symbol": p.symbol,
                            "type": "BUY" if p.type == 0 else "SELL",
                            "volume": p.volume,
                            "open_price": p.price_open,
                            "current_price": p.price_current,
                            "profit": round(p.profit, 2),
                            "sl": p.sl,
                            "tp": p.tp,
                        }
                        data["positions"].append(pos)
                        legacy_positions.append({
                            "ticket": p.ticket,
                            "symbol": p.symbol,
                            "type": "BUY" if p.type == 0 else "SELL",
                            "volume": p.volume,
                            "price_open": p.price_open,
                            "price_current": p.price_current,
                            "profit": round(p.profit, 2),
                            "sl": p.sl,
                            "tp": p.tp,
                            "magic": p.magic,
                        })
                except Exception:
                    legacy_positions = []

            MT5_STATUS_FILE.write_text(json.dumps(data), encoding="utf-8")

            # Escribir los snapshots legacy que consume el frontend Vite.
            # El path base es configurable via BOT_DATA_DIR (default D:\TradingBotMT5).
            bot_data_dir = Path(os.getenv("BOT_DATA_DIR", r"D:\TradingBotMT5"))
            bot_data_dir.mkdir(parents=True, exist_ok=True)

            if executor.connected and "balance" in data:
                legacy_account = {
                    "balance": data.get("balance"),
                    "equity": data.get("equity"),
                    "margin": data.get("margin"),
                    "free_margin": data.get("free_margin"),
                    "profit": data.get("profit"),
                    "leverage": data.get("leverage"),
                    "currency": data.get("currency"),
                    "server": data.get("server"),
                    "name": data.get("server", "Unknown"),
                    "login": data.get("login"),
                    "open_positions": data.get("open_positions", 0),
                    "updated_at": data.get("timestamp"),
                }
                (bot_data_dir / "account_snapshot.json").write_text(
                    json.dumps(legacy_account, indent=2), encoding="utf-8"
                )
                (bot_data_dir / "positions_snapshot.json").write_text(
                    json.dumps(legacy_positions, indent=2), encoding="utf-8"
                )
        except Exception:
            pass


async def cmd_worker():
    """Lee cmd_requests.json (escrito por el bot Telegram o bridge-api) y los ejecuta.

    Comandos soportados:
      - "close_symbol": cierra todas las posiciones del symbol dado en MT5.
    """
    logger.info("cmd_worker iniciado (poll 3s)")
    while True:
        try:
            await asyncio.sleep(3)
            if not CMD_REQUESTS_FILE.exists():
                continue

            try:
                with open(CMD_REQUESTS_FILE, encoding="utf-8") as f:
                    requests_list = json.load(f)
            except Exception:
                # Archivo transitorio (se esta escribiendo); reintentar
                await asyncio.sleep(1)
                continue

            if not isinstance(requests_list, list):
                requests_list = []

            pending = [r for r in requests_list if isinstance(r, dict)]
            if not pending:
                continue

            responses = []
            for req in pending:
                action = req.get("action")
                ts = req.get("ts", 0)
                age = time.time() - ts if ts else 999

                # Ignorar entries muy viejas (>5 min) — alguien no las proceso
                if age > 300:
                    continue

                if action == "close_symbol":
                    symbol = req.get("symbol", "").upper()
                    if symbol and executor.connected:
                        try:
                            n = await executor._close_positions(symbol)
                            responses.append({
                                "request_id": req.get("request_id"),
                                "action": action,
                                "symbol": symbol,
                                "closed": n,
                                "status": "ok" if n else "no_positions",
                                "completed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                            })
                            logger.info(f"cmd_worker: cerrado {symbol}, status={n}")

                            _notify_bot(
                                "trade_close",
                                {
                                    "symbol": symbol,
                                    "action": "CLOSE",
                                    "price": 0,
                                    "sl": None,
                                    "tp": [],
                                },
                                ticket=0,
                                channel=req.get("by_user", "manual"),
                                pnl=0,
                                result=f"CERRADO POR ADMIN ({n})",
                            )
                        except Exception as e:
                            responses.append({
                                "request_id": req.get("request_id"),
                                "action": action,
                                "symbol": symbol,
                                "status": "error",
                                "error": str(e)[:200],
                                "completed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                            })
                            logger.warning(f"cmd_worker close error: {e}")
                    else:
                        responses.append({
                            "request_id": req.get("request_id"),
                            "action": action,
                            "symbol": symbol,
                            "status": "skipped",
                            "reason": "MT5 no conectado" if not executor.connected else "sin symbol",
                            "completed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                        })

            if responses:
                # Acumular responses sin pisar las anteriores (el bot puede estar polling)
                try:
                    existing_responses = []
                    if CMD_RESPONSES_FILE.exists():
                        with open(CMD_RESPONSES_FILE, encoding="utf-8") as f:
                            existing_responses = json.load(f)
                    if not isinstance(existing_responses, list):
                        existing_responses = []

                    existing_responses.extend(responses)
                    # Mantener solo los últimos 100 responses para no crecer infinito
                    existing_responses = existing_responses[-100:]

                    with open(CMD_RESPONSES_FILE, "w", encoding="utf-8") as f:
                        json.dump(existing_responses, f, ensure_ascii=False, indent=2)

                    # Limpiar requests ya procesados
                    with open(CMD_REQUESTS_FILE, "w", encoding="utf-8") as f:
                        f.write("[]")
                    logger.info(f"cmd_worker: {len(responses)} comandos procesados")
                except Exception as e:
                    logger.warning(f"cmd_worker write response: {e}")
        except Exception as e:
            logger.warning(f"cmd_worker loop error: {e}")


async def main():
    logger.info("=" * 50)
    logger.info("Terminal Financiera Pro - Copiador de Senales v2")
    logger.info("=" * 50)

    init_db()

    mt5_connected = executor.connect()
    if not mt5_connected:
        logger.warning("MT5 no disponible. El copiador escuchara pero NO ejecutara trades.")

    # Restaurar senales pendientes desde archivo
    global pending_signals
    pending_signals = _load_pending_signals()

    # Sincronizar trade_map con posiciones abiertas de MT5
    if mt5_connected:
        try:
            import MetaTrader5 as mt5
            positions = mt5.positions_get(magic=20260706) or []
            synced = 0
            for p in positions:
                ticket_str = str(p.ticket)
                if ticket_str not in trade_map:
                    trade_map[ticket_str] = {
                        "trade_id": None,
                        "symbol": p.symbol,
                        "action": "BUY" if p.type == 0 else "SELL",
                        "channel": "(restored)",
                        "opened_at": time.time(),
                    }
                    synced += 1
            if synced:
                save_trade_map()
                logger.info(f"sync: {synced} posiciones MT5 agregadas a trade_map")
        except Exception as e:
            logger.warning(f"sync MT5 positions error: {e}")

    logger.info(f"Canales monitoreados: {settings.CHANNELS_TO_MONITOR}")
    logger.info(f"News Filter: {'ON' if news_filter.enabled else 'OFF'}")
    logger.info(f"TNSVT Bridge: {'ON' if tnsvt_client.enabled else 'OFF'}")

    if tnsvt_client.enabled:
        if tnsvt_client.test_connection():
            logger.info(f"TNSVT conectado: {tnsvt_client.base_url}")
        else:
            logger.warning(f"TNSVT no disponible: {tnsvt_client.base_url}")

    logger.info("Conectando a Telegram...")
    await client.connect()

    if not await client.is_user_authorized():
        logger.info("Sesion no autorizada. Ejecuta: python login_telegram.py")
        return

    me = await client.get_me()
    logger.info(f"Conectado como: {me.first_name} (@{me.username})")
    logger.info("Copiador escuchando... Presiona Ctrl+C para detener.")

    asyncio.create_task(config_watcher())
    asyncio.create_task(news_closer())
    asyncio.create_task(tnsvt_heartbeat())
    asyncio.create_task(mt5_trade_monitor())
    asyncio.create_task(mt5_status_writer())
    asyncio.create_task(cmd_worker())
    asyncio.create_task(trailing_stop_loop())
    asyncio.create_task(time_exit_loop())
    if mt5_connected:
        asyncio.create_task(mt5_monitor.start())

    await client.run_until_disconnected()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Detenido por el usuario")
    except Exception as e:
        logger.error(f"Error inesperado: {e}", exc_info=True)
