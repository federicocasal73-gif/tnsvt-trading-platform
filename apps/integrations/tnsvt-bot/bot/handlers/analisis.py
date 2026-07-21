"""
Handler: /analisis, /r SYMBOL, /reporte SYMBOL, /grafico

Integrates with AMB engine for multi-timeframe analysis.
"""
import logging
from telegram import Update
from telegram.ext import ContextTypes
from bot.analytics.amb_engine import AMBEngine

logger = logging.getLogger("Bot.Handlers.Analisis")

_engine = AMBEngine()


async def analisis(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/analisis — Panorama completo multi-timeframe de 5 pares principales."""
    symbols = ["EURUSD", "GBPUSD", "XAUUSD", "US30", "BTCUSD"]

    try:
        await update.message.reply_text("🔄 Analizando mercado multi-timeframe...")

        lines = ["📊 *Panorama Multi-Timeframe*", ""]
        for sym in symbols:
            result = await _engine.analyze(sym)
            emoji = "🟢" if result.bias.value == "ALCISTA" else ("🔴" if result.bias.value == "BAJISTA" else "⚪")
            lines.append(
                f"{emoji} *{sym}*: {result.classification.value} ({result.weighted_score}/100) · {result.bias.value}"
            )

        lines.append("")
        lines.append("💡 Usá `/r SIMBOLO` para análisis detallado")
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Error en /analisis: {e}")
        await update.message.reply_text("⚠️ Error al generar panorama de mercado.")


async def reporte(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/reporte SIMBOLO — Análisis multi-timeframe detallado."""
    symbol = _get_symbol(context)
    if not symbol:
        await update.message.reply_text(
            "📊 Usá: `/reporte EURUSD`\n"
            "Ejemplo: `/reporte XAUUSD`",
            parse_mode="Markdown",
        )
        return

    try:
        await update.message.reply_text(f"🔄 Analizando {symbol.upper()}...")
        result = await _engine.analyze(symbol.upper())
        text = _engine.format_analysis(result)
        await update.message.reply_text(text, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Error en /reporte {symbol}: {e}")
        await update.message.reply_text(f"⚠️ Error al analizar {symbol}.")


async def r_atajo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/r SIMBOLO — Atajo rápido para /reporte."""
    await reporte(update, context)


async def grafico(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/grafico — Equity curve link."""
    await update.message.reply_text(
        "📈 *Gráfico de Equity Curve*\n\n"
        "Abrí la Terminal Vite:\n"
        "http://localhost:5180/grafico\n\n"
        "O usá `/reporte SIMBOLO` para análisis técnico.",
        parse_mode="Markdown",
    )


def _get_symbol(context: ContextTypes.DEFAULT_TYPE) -> str:
    if context.args and len(context.args) > 0:
        return context.args[0].upper().strip()
    return ""
