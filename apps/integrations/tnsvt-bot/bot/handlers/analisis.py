"""
Handler: /analisis, /veredicto SIMBOLO, /reporte SIMBOLO, /grafico

F1 (CORE): /veredicto y /analisis consumen GET /api/v1/orchestrator/analysis/{symbol}
para mostrar el veredicto maestro multi-horizonte + playbook al usuario del bot.
"""
import logging
import httpx

from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger("Bot.Handlers.Analisis")

ORCHESTRATOR_URL = "http://localhost:8060"
GATEWAY_URL = "http://localhost:8000"
REQUEST_TIMEOUT = 12.0


async def _fetch_analysis(symbol: str) -> dict | None:
    """Consulta el orchestrator y devuelve el dict de analysis completo."""
    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as c:
            # Gateway route -> /api/v1/orchestrator/analysis/{symbol}
            for base in (GATEWAY_URL, ORCHESTRATOR_URL):
                try:
                    r = await c.get(f"{base}/api/v1/orchestrator/analysis/{symbol}")
                    if r.status_code == 200:
                        return r.json()
                except Exception:
                    continue
    except Exception as e:
        logger.error(f"_fetch_analysis error: {e}")
    return None


def _format_analysis(a: dict) -> str:
    """Formatea el payload de /analysis como mensaje Telegram."""
    symbol = a.get("symbol", "?")
    bias = a.get("master_bias", "NEUTRAL")
    score = a.get("master_score", 50)

    bias_emoji = "🟢" if bias == "BULLISH" else ("🔴" if bias == "BEARISH" else "⚪")
    bias_label = "ALCISTA" if bias == "BULLISH" else ("BAJISTA" if bias == "BEARISH" else "NEUTRAL")

    lines = [
        f"{bias_emoji} *Veredicto del Día — {symbol}*",
        f"_{bias_label}_ · Score: *{score:.0f}/100*",
        "",
    ]

    # Multi-horizonte
    horizons = a.get("horizons", {})
    if horizons:
        lines.append("*Multi-Horizonte:*")
        for tf in ("M5", "H1", "H4", "D1"):
            if tf in horizons:
                h = horizons[tf]
                tb = "🟢" if h.get("bias") == "BULLISH" else ("🔴" if h.get("bias") == "BEARISH" else "⚪")
                lines.append(f"  {tf}: {tb} {h.get('score', 0):.0f}/100")
        lines.append("")

    # Drivers
    drivers = a.get("drivers", [])
    aligned = sum(1 for d in drivers if d.get("status") == "aligned")
    divergent = sum(1 for d in drivers if d.get("status") == "divergent")
    if drivers:
        lines.append(f"*Drivers:* {aligned} alineados, {divergent} divergentes")
        lines.append("")

    # Price range
    pr = a.get("price_range", {})
    if pr and pr.get("current"):
        zone = pr.get("zone", "fair")
        zone_label = {"barata": "🟢 BARATA", "fair": "⚪ FAIR", "cara": "🔴 CARA"}.get(zone, zone)
        lines.append(
            f"*Precio:* `{pr.get('current', 0):.2f}` · Zona {zone_label} "
            f"({pr.get('cara_pct', 0):.0f}% hacia arriba)"
        )
        lines.append("")

    # Playbook intradia
    pbi = a.get("playbook_intraday", {})
    if pbi and pbi.get("action"):
        lines.append(f"*🎯 Intradía:* {pbi.get('title', '—')}")
        lines.append(f"  → {pbi.get('action', '—')}")
        if pbi.get("entry") is not None:
            lines.append(
                f"  Entry `{pbi['entry']:.2f}` · SL `{pbi.get('stop', 0):.2f}` · "
                f"TP1 `{pbi.get('tp1', 0):.2f}`"
            )
        if pbi.get("invalidation"):
            lines.append(f"  _Invalidación:_ {pbi['invalidation']}")
        lines.append("")

    # Playbook diario
    pbd = a.get("playbook_daily", {})
    if pbd and pbd.get("action"):
        lines.append(f"*📊 Diario:* {pbd.get('title', '—')}")
        lines.append(f"  → {pbd.get('action', '—')}")
        if pbd.get("entry") is not None:
            lines.append(
                f"  Entry `{pbd['entry']:.2f}` · SL `{pbd.get('sl', 0):.2f}` · "
                f"TP1 `{pbd.get('tp1', 0):.2f}`"
            )
        lines.append("")

    # Macro risk
    macro = a.get("macro", {})
    if macro.get("risk_off"):
        lines.append(f"⚠️ _Macro risk-off:_ {(macro.get('reasons') or ['—'])[:2][0] if macro.get('reasons') else '—'}")

    return "\n".join(lines)


# ─── Comandos ────────────────────────────────────────────────────


async def analisis(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/analisis — Panorama multi-timeframe de 5 pares principales.

    Versión F1: usa el endpoint /analysis/{symbol} del orchestrator.
    """
    symbols = ["EURUSD", "GBPUSD", "XAUUSD", "US30", "BTCUSD"]

    try:
        await update.message.reply_text("🔄 Analizando mercado...")

        lines = ["📊 *Panorama Multi-Timeframe*", ""]
        for sym in symbols:
            data = await _fetch_analysis(sym)
            if not data:
                lines.append(f"❌ {sym}: sin datos")
                continue
            emoji = "🟢" if data.get("master_bias") == "BULLISH" else (
                "🔴" if data.get("master_bias") == "BEARISH" else "⚪"
            )
            score = data.get("master_score", 50)
            bias = data.get("master_bias", "NEUTRAL")
            lines.append(f"{emoji} *{sym}*: {score:.0f}/100 · {bias}")

        lines.append("")
        lines.append("💡 Usá `/veredicto SIMBOLO` para análisis detallado")
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Error en /analisis: {e}")
        await update.message.reply_text("⚠️ Error al generar panorama de mercado.")


async def veredicto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/veredicto SIMBOLO — Veredicto maestro multi-horizonte para un símbolo."""
    symbol = _get_symbol(context)
    if not symbol:
        await update.message.reply_text(
            "📊 *Uso:* `/veredicto SIMBOLO`\n"
            "Ejemplos: `/veredicto XAUUSD`, `/veredicto EURUSD`",
            parse_mode="Markdown",
        )
        return

    try:
        await update.message.reply_text(f"🔄 Analizando {symbol.upper()}...")
        data = await _fetch_analysis(symbol.upper())
        if not data:
            await update.message.reply_text(
                f"⚠️ No se pudo analizar {symbol.upper()}. "
                "Verificá que orchestrator (:8060) esté corriendo.",
                parse_mode="Markdown",
            )
            return
        text = _format_analysis(data)
        await update.message.reply_text(text, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Error en /veredicto {symbol}: {e}")
        await update.message.reply_text(f"⚠️ Error al analizar {symbol}.")


async def reporte(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/reporte SIMBOLO — Alias de /veredicto (compatibilidad)."""
    await veredicto(update, context)


async def r_atajo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/r SIMBOLO — Atajo de /veredicto."""
    await veredicto(update, context)


async def grafico(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/grafico — Link a equity curve en la Terminal."""
    await update.message.reply_text(
        "📈 *Gráfico de Equity Curve*\n\n"
        "Abrí la Terminal Vite:\n"
        "http://localhost:5180/grafico\n\n"
        "O usá `/veredicto SIMBOLO` para análisis multi-timeframe.",
        parse_mode="Markdown",
    )


def _get_symbol(context: ContextTypes.DEFAULT_TYPE) -> str:
    if context.args and len(context.args) > 0:
        return context.args[0].upper().strip()
    return ""