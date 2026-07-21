"""
Signal Copier - Main v2 (con integracion TNSVT)
"""
import asyncio
import json
import logging
import sys
import time
from pathlib import Path

ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR))

from telethon import TelegramClient, events
from config import settings
from signal_copier.parser import SignalParser
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

parser = SignalParser()
executor = MT5Executor()
mt5_monitor = MT5Monitor(executor)
risk_manager = RiskManager()
news_filter = NewsFilter()
tnsvt_client = TNSVTClient()

pending_signals = {}

TRADE_MAP_FILE = ROOT_DIR / "var" / "tnsvt_trade_map.json"
MT5_STATUS_FILE = ROOT_DIR / "var" / "mt5_status.json"
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
            logger.info(f"Actualizando SL/TP a senal pendiente: {pending['symbol']}")

            if signal.get("sl"):
                pending["sl"] = signal["sl"]
            if signal.get("tp"):
                pending["tp"] = signal["tp"]

            if parser.has_sl_tp(pending):
                logger.info(f"Senal completa, ejecutando: {pending['action']} {pending['symbol']}")
                pending_signals.pop(chat_name, None)
                await execute_signal(pending, chat_name)
            else:
                logger.info("SL/TP actualizado, esperando mas datos")
                pending_signals[chat_name] = pending
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
            log_trade(
                signal["symbol"],
                signal["action"],
                signal.get("price"),
                signal.get("sl"),
                signal.get("tp"),
                result_msg,
                ticket=last_ticket,
                channel=channel,
            )

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
                log_trade(
                    signal["symbol"],
                    signal["action"],
                    signal.get("price"),
                    signal.get("sl"),
                    signal.get("tp"),
                    f"BLOQUEADO: {reason}",
                    channel=channel,
                )
                return

        can_trade, reason = risk_manager.can_open_trade()
        if not can_trade:
            logger.warning(f"BLOQUEADO por riesgo: {reason}")
            log_trade(
                signal["symbol"],
                signal["action"],
                signal.get("price"),
                signal.get("sl"),
                signal.get("tp"),
                f"BLOQUEADO: {reason}",
                channel=channel,
            )
            return

        success = await executor.execute_trade(signal)

        result_msg = "OK" if success else "ERROR"
        log_trade(
            signal["symbol"],
            signal["action"],
            signal.get("price"),
            signal.get("sl"),
            signal.get("tp"),
            result_msg,
            channel=channel,
        )

        if success:
            await risk_manager.check_trailing_stop_async(signal["symbol"])

            if tnsvt_client.enabled:
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
    """Escribe estado completo de MT5 a archivo compartido para el dashboard y /historial"""
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
                    for p in positions:
                        data["positions"].append({
                            "ticket": p.ticket,
                            "symbol": p.symbol,
                            "type": "BUY" if p.type == 0 else "SELL",
                            "volume": p.volume,
                            "open_price": p.price_open,
                            "current_price": p.price_current,
                            "profit": round(p.profit, 2),
                            "sl": p.sl,
                            "tp": p.tp,
                        })
                except Exception:
                    pass

            MT5_STATUS_FILE.write_text(json.dumps(data), encoding="utf-8")
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
                # Escribir responses + limpiar requests
                try:
                    with open(CMD_RESPONSES_FILE, "w", encoding="utf-8") as f:
                        json.dump(responses, f, ensure_ascii=False, indent=2)
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
