"""
Handler: Weekly Poll — Encuesta semanal de sentimiento por instrumento.

Cada lunes a las 9:00 ART publica 5 encuestas (BTCUSD, XAUUSD, EURUSD,
DXY, NAS100) con botones inline, opciones:
  🟢 Alcista | 🔴 Bajista | 🟡 Rango | ⚪ Afuera

Cada encuesta se persiste en el bridge (CommunityDB, tabla surveys) y los
votos se registran por usuario (idempotente). Los botones inline reemplazan
a los polls nativos de Telegram (que eran anónimos y sin user_id).

Loop independiente con cleanup de duplicados.
Comando admin /encuesta para forzar manualmente.
"""
import asyncio
import logging
import time
from datetime import datetime, timedelta

import pytz
import requests
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes
from config import settings
from bot.bridge_auth import bridge_headers
from bot.constants import (
    TNSVT_BRAND_LINE,
    TNSVT_SHORT_DISCLAIMER,
    POLL_INSTRUMENTS,
    POLL_OPTIONS,
    WEEKLY_POLL_HOUR,
)

logger = logging.getLogger("Bot.Handlers.WeeklyPoll")

ART = pytz.timezone("America/Argentina/Buenos_Aires")

_last_publish_iso: str | None = None

# Retry para crear encuestas en el bridge (aguanta reinicios del bridge).
_SURVEY_RETRIES = 3
_SURVEY_RETRY_DELAY = 30


def _community_api() -> str:
    return settings.COMMUNITY_API_URL


def _create_survey(symbol: str, target: int) -> str | None:
    """Crea la encuesta en el bridge y devuelve el survey_id.

    Reintenta con backoff (3 intentos, 30s entre ellos) para aguantar
    ventanas cortas de indisponibilidad del bridge (por ejemplo si se
    reinicia justo en el horario de publicación). Si los 3 fallan, se
    devuelve None y el caller hace fallback a texto plano.
    """
    payload = {
        "title": f"¿Cómo ves {symbol} esta semana?",
        "options": POLL_OPTIONS,
        "channel_id": target,
        "created_by": None,
    }
    last_exc = None
    for attempt in range(1, _SURVEY_RETRIES + 1):
        try:
            resp = requests.post(
                f"{_community_api()}/surveys",
                json=payload,
                headers=bridge_headers(),
                timeout=8,
            )
            if resp.status_code == 200:
                data = resp.json()
                return data.get("survey", {}).get("id")
            logger.warning(
                f"weekly_poll: crear survey {symbol} -> {resp.status_code} (intento {attempt}/{_SURVEY_RETRIES})"
            )
        except Exception as e:
            last_exc = e
            logger.error(
                f"weekly_poll: error creando survey {symbol} (intento {attempt}/{_SURVEY_RETRIES}): {e}"
            )
        if attempt < _SURVEY_RETRIES:
            time.sleep(_SURVEY_RETRY_DELAY)
    if last_exc:
        logger.error(f"weekly_poll: sin retry exitoso para {symbol}: {last_exc}")
    return None


def _poll_keyboard(survey_id: str) -> InlineKeyboardMarkup:
    rows = []
    for idx, option in enumerate(POLL_OPTIONS):
        rows.append([
            InlineKeyboardButton(option, callback_data=f"poll:v:{survey_id}:{idx}"),
        ])
    return InlineKeyboardMarkup(rows)


def _next_monday_9am(now_art: datetime) -> datetime:
    """Próximo lunes 9:00 ART. Si hoy es lunes y ya pasó, devuelve el siguiente."""
    target = now_art.replace(
        hour=WEEKLY_POLL_HOUR, minute=0, second=0, microsecond=0,
    )
    days_ahead = (0 - now_art.weekday()) % 7
    if days_ahead == 0 and now_art >= target:
        days_ahead = 7
    return target + timedelta(days=days_ahead)


def _is_monday_9am_window(now_art: datetime) -> bool:
    """True si estamos dentro de la ventana de 5 min para publicar."""
    if now_art.weekday() != 0:
        return False
    target_hour = now_art.replace(
        hour=WEEKLY_POLL_HOUR, minute=0, second=0, microsecond=0,
    )
    return target_hour <= now_art < target_hour + timedelta(minutes=5)


async def _publish_polls(app, context=None) -> None:
    """Publica 5 encuestas con botones inline en el grupo."""
    target = settings.BOT_GROUP_ID
    if not target:
        logger.warning("weekly_poll: BOT_GROUP_ID no configurado")
        return

    bot = app.bot if hasattr(app, "bot") else context.bot

    header = (
        f"📊 *ENCUESTA SEMANAL — Sentimiento de mercado*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🗓 Semana del {datetime.now(ART).strftime('%d/%m/%Y')}\n"
        f"🎯 Votá tu visión para los próximos 5 días.\n"
        f"👆 Tocá una opción para votar.\n\n"
        f"{TNSVT_SHORT_DISCLAIMER}"
    )

    try:
        await bot.send_message(
            chat_id=target,
            text=header,
            parse_mode="Markdown",
            disable_notification=False,
        )
        logger.info("weekly_poll: header publicado")
    except Exception as e:
        logger.error(f"weekly_poll: fallo publicando header: {e}")

    polls_ok = 0
    polls_fail = 0

    for symbol in POLL_INSTRUMENTS:
        question = f"📊 ¿Cómo ves *{symbol}* esta semana?"
        try:
            survey_id = _create_survey(symbol, target)
            if not survey_id:
                raise RuntimeError("no survey_id del bridge")
            await bot.send_message(
                chat_id=target,
                text=(
                    f"{question}\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"Elegí tu visión para los próximos 5 días:"
                ),
                parse_mode="Markdown",
                reply_markup=_poll_keyboard(survey_id),
            )
            polls_ok += 1
            logger.info(f"weekly_poll: encuesta {symbol} publicada (survey={survey_id})")
        except Exception as e:
            polls_fail += 1
            logger.warning(
                f"weekly_poll: fallo publicando encuesta {symbol}: {e}"
            )
            try:
                fallback = (
                    f"📊 *Encuesta semanal — {symbol}*\n"
                    f"¿Cómo ves *{symbol}* esta semana?\n"
                    f"• 🟢 Alcista\n• 🔴 Bajista\n• 🟡 Rango\n• ⚪ Afuera\n"
                    f"_Respondé en el chat_"
                )
                await bot.send_message(
                    chat_id=target,
                    text=fallback,
                    parse_mode="Markdown",
                )
            except Exception as e2:
                logger.error(f"weekly_poll: fallback tambien fallo: {e2}")

        await asyncio.sleep(0.5)

    logger.info(
        f"weekly_poll: completo OK={polls_ok}/{len(POLL_INSTRUMENTS)} FAIL={polls_fail}"
    )


async def weekly_poll_loop(app):
    """Loop asincrono. Duerme hasta el próximo lunes 9:00 ART y publica."""
    logger.info(
        f"weekly_poll_loop arrancado (instrumentos={POLL_INSTRUMENTS})"
    )

    global _last_publish_iso

    while True:
        try:
            now_art = datetime.now(ART)
            next_run = _next_monday_9am(now_art)
            secs = (next_run - now_art).total_seconds()
            logger.info(
                f"weekly_poll: proxima corrida en {secs/3600:.1f}h ({next_run})"
            )
            await asyncio.sleep(secs)

            now_iso = datetime.now(ART).isoformat()
            if _last_publish_iso and _is_within_last_24h(_last_publish_iso):
                logger.debug(
                    f"weekly_poll: ya publicado hoy ({_last_publish_iso}), skip"
                )
                await asyncio.sleep(60)
                continue

            await _publish_polls(app)
            _last_publish_iso = now_iso

        except Exception as e:
            logger.error(f"weekly_poll_loop tick error: {e}")
            await asyncio.sleep(300)


def _is_within_last_24h(iso_str: str) -> bool:
    try:
        last = datetime.fromisoformat(iso_str)
        if last.tzinfo is None:
            last = ART.localize(last)
        return (datetime.now(ART) - last) < timedelta(hours=24)
    except Exception:
        return False


async def force_poll_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando admin /encuesta — fuerza publicación manual de polls."""
    user_id = update.effective_user.id if update.effective_user else 0
    admins = settings.BOT_ADMIN_IDS or []
    if not admins or user_id not in admins:
        await update.message.reply_text(
            "❌ Solo el admin puede forzar la encuesta semanal."
        )
        return

    await update.message.reply_text("🔄 Publicando encuestas semanales...")
    global _last_publish_iso
    _last_publish_iso = None
    await _publish_polls(context.application, context=context)
    await update.message.reply_text(
        f"✅ {len(POLL_INSTRUMENTS)} encuestas publicadas."
    )


# ─── Voto desde botón inline ─────────────────────────────────────────

def _register_vote(survey_id: str, user_id: int, chat_id, option_idx: int):
    """Registra el voto en el bridge. Devuelve (status, survey) o (None, None)."""
    try:
        resp = requests.post(
            f"{_community_api()}/surveys/{survey_id}/vote",
            json={
                "user_id": user_id,
                "chat_id": chat_id,
                "option_selected": option_idx,
            },
            headers=bridge_headers(),
            timeout=8,
        )
        if resp.status_code != 200:
            logger.warning(
                f"weekly_poll: voto {user_id} en {survey_id} -> {resp.status_code}: {resp.text[:120]}"
            )
            return None, None
        return resp.json().get("result", {}), resp.json().get("survey")
    except Exception as e:
        logger.error(f"weekly_poll: error registrando voto {user_id}: {e}")
        return None, None


async def poll_vote_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback `poll:v:{survey_id}:{option_idx}` — registra y confirma el voto."""
    query = update.callback_query
    data = (query.data or "").strip()

    parts = data.split(":")
    if len(parts) < 3:
        await query.answer("⚠️ Encuesta inválida", show_alert=True)
        return

    survey_id = parts[1]
    try:
        option_idx = int(parts[2])
    except ValueError:
        await query.answer("⚠️ Opción inválida", show_alert=True)
        return

    user = query.from_user
    user_id = user.id if user else 0
    chat_id = query.message.chat_id if query.message else None

    try:
        await query.answer()
    except Exception:
        pass

    # Refrescar encuesta para validar activa y opciones
    try:
        resp = requests.get(f"{_community_api()}/surveys/{survey_id}", headers=bridge_headers(), timeout=8)
        survey = resp.json().get("survey") if resp.status_code == 200 else None
    except Exception:
        survey = None

    if not survey:
        await query.answer("⚠️ No se encontró la encuesta", show_alert=True)
        return

    if not survey.get("is_active"):
        await query.answer("⛔ Encuesta cerrada", show_alert=True)
        return

    options = survey.get("options", [])
    if not (0 <= option_idx < len(options)):
        await query.answer("⚠️ Opción fuera de rango", show_alert=True)
        return

    status, _ = _register_vote(survey_id, user_id, chat_id, option_idx)
    if not status:
        await query.answer("⚠️ No se pudo guardar tu voto. Intentalo de nuevo.", show_alert=True)
        return

    votes = _format_vote_counts(survey_id, options)
    changed = "actualizado" if status.get("status") == "updated" else "registrado"
    text = (
        f"📊 *{survey.get('title', 'Encuesta')}*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{votes}\n"
        f"✅ Voto {changed}."
    )
    try:
        await query.edit_message_text(text=text, parse_mode="Markdown")
    except Exception as e:
        logger.debug(f"poll_vote: edit fallo: {e}")


def _format_vote_counts(survey_id: str, options: list[str]) -> str:
    """Arma líneas con opción + recuento actual desde el bridge."""
    try:
        resp = requests.get(f"{_community_api()}/surveys/{survey_id}", headers=bridge_headers(), timeout=8)
        survey = resp.json().get("survey") if resp.status_code == 200 else None
    except Exception:
        survey = None
    if not survey:
        return "\n".join(f"• {o}" for o in options)

    counts = {}
    for v in survey.get("votes", []):
        counts[v.get("option_selected")] = v.get("count", 0)

    lines = []
    for idx, opt in enumerate(options):
        c = counts.get(idx, 0)
        bar = "█" * min(c, 12) if c else ""
        lines.append(f"{opt}\n   {bar} {c} voto{'s' if c != 1 else ''}")
    return "\n".join(lines)
