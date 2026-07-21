"""
Terminal Financiera Pro - Bot de Telegram
"""
import asyncio
import logging
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR))

from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler
from config import settings
from bot.services import trading_economics
from bot.services.tnsvt_status import send_bot_heartbeat
from bot.handlers import start, calendar, news, signals, admin, historial, statshoy, canales, cuentas, cerrar
from bot.watchdog import watchdog_loop
from bot.callbacks import button_router

logging.basicConfig(
    format="%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("bot.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("Bot")


async def tnsvt_heartbeat_loop(bot_app):
    """Loop asincrono que envia heartbeat a TNSVT cada 30s."""
    bot_username = "telegram_bot"
    try:
        me = await bot_app.bot.get_me()
        if me and me.username:
            bot_username = me.username
    except Exception as e:
        logger.debug(f"No se pudo obtener bot username: {e}")

    logger.info(f"TNSVT heartbeat loop iniciado (bot=@{bot_username})")

    while True:
        try:
            ok = send_bot_heartbeat(bot_username)
            if ok:
                logger.debug("TNSVT heartbeat OK")
            else:
                logger.debug("TNSVT heartbeat no enviado")
        except Exception as e:
            logger.error(f"Heartbeat error: {e}")
        await asyncio.sleep(30)


async def post_init(app):
    """Hook post-init: arranca heartbeat + watchdog en background."""
    app.bot_data["heartbeat_task"] = asyncio.create_task(tnsvt_heartbeat_loop(app))
    app.bot_data["watchdog_task"] = asyncio.create_task(watchdog_loop(app))


async def post_shutdown(app):
    """Hook post-shutdown: cancela tasks de heartbeat + watchdog."""
    for key in ("heartbeat_task", "watchdog_task"):
        task = app.bot_data.get(key)
        if task:
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass


def initialize_services():
    warnings = settings.validate_trading()
    for w in warnings:
        logger.warning(w)

    try:
        trading_economics.init()
    except Exception as e:
        logger.warning(f"TradingEconomics no disponible: {e}")


def create_application():
    app = ApplicationBuilder().token(settings.BOT_TOKEN).post_init(post_init).post_shutdown(post_shutdown).build()

    # Menu principal
    app.add_handler(CommandHandler("start", start.start))
    app.add_handler(CommandHandler("help", start.start))

    # Mercados y cripto
    app.add_handler(CommandHandler("mercados", calendar.mercados))
    app.add_handler(CommandHandler("cripto", calendar.cripto))

    # Noticias
    app.add_handler(CommandHandler("noticias", news.noticias))
    app.add_handler(CommandHandler("ipc", news.ipc))
    app.add_handler(CommandHandler("morgan", news.morgan))

    # Calendario y datos
    app.add_handler(CommandHandler("calendario", calendar.calendario))
    app.add_handler(CommandHandler("datos", news.datos))

    # Señales
    app.add_handler(CommandHandler("senales", signals.senales))

    # Admin
    app.add_handler(CommandHandler("resumen", admin.resumen))
    app.add_handler(CommandHandler("stats", admin.stats))

    # Historial
    app.add_handler(CommandHandler("historial", historial.historial))

    # Comandos nuevos (multi-cuenta + UI con botones)
    app.add_handler(CommandHandler("statshoy", statshoy.statshoy))
    app.add_handler(CommandHandler("canales", canales.canales))
    app.add_handler(CommandHandler("cerrar", cerrar.cerrar))
    app.add_handler(CommandHandler("cuentas", cuentas.cuentas))

    # Callback query handler (los botones inline llaman callbacks aca)
    app.add_handler(CallbackQueryHandler(button_router))

    logger.info("Handlers registrados")
    return app


def main():
    logger.info("=" * 50)
    logger.info("Terminal Financiera Pro - Bot de Telegram")
    logger.info("=" * 50)

    try:
        initialize_services()
    except Exception as e:
        logger.error(f"Error inicializando servicios: {e}")

    app = create_application()

    logger.info("Bot iniciado - Esperando mensajes...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
