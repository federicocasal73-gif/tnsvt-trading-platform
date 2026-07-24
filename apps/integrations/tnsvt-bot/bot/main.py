"""
Terminal Financiera Pro - Bot de Telegram
"""
import asyncio
import logging
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(ROOT_DIR / "scripts"))

from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ChatMemberHandler
from config import settings
from bot.services import trading_economics
from bot.services.tnsvt_status import send_bot_heartbeat
from bot.handlers import start, calendar, news, signals, admin, historial, statshoy, canales, cuentas, cerrar, greetings, reports, analisis, zona
from bot.watchdog import watchdog_loop
from bot.callbacks import button_router
from bot.events_watcher import events_watcher_loop
from bot.calendar_watchdog import calendar_watchdog_loop

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
    bot_username = "terminalfinancieraproTNSVT_bot"
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
    """Hook post-init: arranca heartbeat + watchdog + reports + events_watcher + calendar en background."""
    app.bot_data["heartbeat_task"] = asyncio.create_task(tnsvt_heartbeat_loop(app))
    app.bot_data["watchdog_task"] = asyncio.create_task(watchdog_loop(app))
    app.bot_data["events_task"] = asyncio.create_task(events_watcher_loop(app))
    app.bot_data["calendar_task"] = asyncio.create_task(_run_daily_calendar(app))
    app.bot_data["calendar_watchdog_task"] = asyncio.create_task(calendar_watchdog_loop(app))

    app.bot_data["report_task"] = asyncio.create_task(_run_reports(app))

    logger.info(
        "AMB Engine, reports, events_watcher, calendar_job, calendar_watchdog "
        "y handlers de privacidad activados"
    )


async def _run_reports(app):
    """Schedule daily and weekly reports."""
    from bot.handlers.reports import _send_report
    import pytz
    from datetime import datetime, timedelta

    ART = pytz.timezone("America/Argentina/Buenos_Aires")

    while True:
        now_art = datetime.now(ART)
        tomorrow = now_art + timedelta(days=1)
        next_daily = ART.localize(
            datetime(tomorrow.year, tomorrow.month, tomorrow.day, 23, 59, 0)
        )
        secs_daily = (next_daily - now_art).total_seconds()
        await asyncio.sleep(secs_daily)

        try:
            await _send_report(app.bot, period="daily")
        except Exception as e:
            logger.error(f"Reporte diario: {e}")

        now_art = datetime.now(ART)
        if now_art.weekday() == 6:
            try:
                await _send_report(app.bot, period="weekly")
            except Exception as e:
                logger.error(f"Reporte semanal: {e}")


async def _run_daily_calendar(app):
    """Publica el calendario económico en el grupo cada día a las 8:00 ART.

    Solo eventos ALTO impacto (🔴) + MEDIO (🟡) de los próximos 3 días.
    """
    import pytz
    from datetime import datetime, timedelta
    from bot.handlers.calendar import calendariosolo
    from bot.analytics.calendar import format_calendar_text

    ART = pytz.timezone("America/Argentina/Buenos_Aires")

    while True:
        try:
            now_art = datetime.now(ART)
            next_run = ART.localize(
                datetime(now_art.year, now_art.month, now_art.day, 8, 0, 0)
            )
            if next_run <= now_art:
                next_run = next_run + timedelta(days=1)

            secs = (next_run - now_art).total_seconds()
            logger.info(
                f"calendar_job: proxima corrida en {secs/3600:.1f}h ({next_run})"
            )
            await asyncio.sleep(secs)

            try:
                events = await calendariosolo(None, None)
                if not events:
                    logger.warning("calendar_job: sin eventos ALTO, no publico")
                    continue

                high = [e for e in events if e.get("impact_level", 0) == 3]
                text = format_calendar_text(high, max_events=10)

                msg = (
                    "📅 *CALENDARIO ECONÓMICO — Próximos eventos ALTO impacto*\n"
                    "━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"{text}\n"
                    "\n_Publicado automáticamente todos los días a las 8:00 ART_"
                )

                await app.bot.send_message(
                    chat_id=settings.BOT_GROUP_ID,
                    text=msg,
                    parse_mode="Markdown",
                )
                logger.info(f"calendar_job: publicado {len(high)} eventos ALTO")
            except Exception as e:
                logger.error(f"calendar_job: error publicando: {e}")
        except Exception as e:
            logger.error(f"_run_daily_calendar loop error: {e}")
            await asyncio.sleep(60)


async def post_shutdown(app):
    """Hook post-shutdown: cancela tasks de heartbeat + watchdog + reports + events."""
    for key in ("heartbeat_task", "watchdog_task", "report_task", "events_task", "calendar_task", "calendar_watchdog_task"):
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

    try:
        from bot.analytics.calendar import get_calendar_events
        logger.info("AMB Calendar service initialized")
    except Exception as e:
        logger.warning(f"AMB Calendar no disponible: {e}")

    try:
        from bot.analytics.macro_filter import check_macro_alert
        logger.info("AMB Macro Filter initialized")
    except Exception as e:
        logger.warning(f"AMB Macro Filter no disponible: {e}")


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

    # Status dashboard
    from bot.handlers.status import status_command
    app.add_handler(CommandHandler("status", status_command))

    # Analytics (stats por canal/simbolo)
    from bot.handlers.analytics import stats_canal, stats_simbolo
    app.add_handler(CommandHandler("stats_canal", stats_canal))
    app.add_handler(CommandHandler("stats_simbolo", stats_simbolo))

    # Comandos nuevos (multi-cuenta + UI con botones)
    app.add_handler(CommandHandler("statshoy", statshoy.statshoy))
    app.add_handler(CommandHandler("canales", canales.canales))
    app.add_handler(CommandHandler("cerrar", cerrar.cerrar))
    app.add_handler(CommandHandler("cuentas", cuentas.cuentas))

    # Análisis técnico (AMB Engine)
    app.add_handler(CommandHandler("analisis", analisis.analisis))
    app.add_handler(CommandHandler("reporte", analisis.reporte))
    app.add_handler(CommandHandler("r", analisis.r_atajo))
    app.add_handler(CommandHandler("grafico", analisis.grafico))
    app.add_handler(CommandHandler("zona", zona.zona))
    app.add_handler(CommandHandler("z", zona.zshorthand))

    # Greeting handler (nuevos miembros en grupo + DM a admin)
    app.add_handler(ChatMemberHandler(greetings.greet_new_member, ChatMemberHandler.CHAT_MEMBER))

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
