"""
Handler: /zona SYMBOL — Análisis técnico de un par puntual

Devuelve:
  - Score AMB (0-100) + clasificación (AAA+ ... D)
  - Bias general (ALCISTA / BAJISTA / NEUTRAL)
  - Tendencia por TF (M15/H1/H4/D1)
  - Estructura (HH/HL o LH/LL)
  - Soportes/Resistencias cercanos
  - Indicadores (RSI/MACD/EMA)
  - Recomendación textual
"""
import logging
from telegram import Update
from telegram.ext import ContextTypes

from bot.analytics.amb_engine import AMBEngine, Bias

logger = logging.getLogger("Bot.Handlers.Zona")

_engine = AMBEngine()


def _tf_emoji_simple(tf: str) -> str:
    return {
        "M15": "⏱️", "H1": "⚡", "H4": "⚡", "D1": "📅",
    }.get(tf, "📊")


def _bias_arrow(bias: Bias) -> str:
    if bias == Bias.BULLISH:
        return "🟢 ALCISTA"
    if bias == Bias.BEARISH:
        return "🔴 BAJISTA"
    if bias == Bias.NEUTRAL:
        return "⚪ NEUTRAL"
    return "🚫 NO TRADE"


async def zona(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Analisis profundo de un simbolo particular"""
    try:
        user = update.effective_user

        if not context.args:
            await update.message.reply_text(
                "🎯 *Análisis por Par*\n\n"
                "Uso: `/zona SYMBOL`\n"
                "Ejemplos:\n"
                "• `/zona XAUUSD`\n"
                "• `/zona EURUSD`\n"
                "• `/zona US30`",
                parse_mode="Markdown",
            )
            return

        symbol = context.args[0].upper().strip()

        await update.message.reply_text(
            f"🔄 Analizando *{symbol}* en 8 timeframes...",
            parse_mode="Markdown",
        )

        result = await _engine.analyze(symbol)

        lines = [
            f"🎯 *Análisis de Zona: {result.symbol}*",
            "━━━━━━━━━━━━━━━━━━━━━━━",
            "",
            f"🏆 *Clasificación:* {result.classification.value} ({result.weighted_score}/100)",
            f"📐 *Bias general:* {_bias_arrow(result.bias)}",
        ]

        if result.macro_alert:
            lines.append("")
            lines.append("🚫 *MACRO RED ALERT — VIX alto, evitar operar*")

        lines.append("")
        lines.append("━━━ *Jerarquía Temporal* ━━━")

        for r in result.timeframe_results:
            emoji = _tf_emoji_simple(r.timeframe)
            arrow = _bias_arrow(r.bias)
            weight = 0
            if r.timeframe == "MACRO":
                weight = 25
            elif r.timeframe in ("WEEKLY", "DAILY"):
                weight = 20
            elif r.timeframe == "H4":
                weight = 15
            elif r.timeframe == "H1":
                weight = 10
            elif r.timeframe == "M15":
                weight = 5
            lines.append(
                f"{emoji} *{r.timeframe}*: {arrow} ({r.score}/100) [{weight}%]"
            )

        lines.append("")
        lines.append("━━━ *Indicadores* ━━━")
        structure_tf = next((r for r in result.timeframe_results if r.timeframe == "H4"), None)
        if structure_tf and structure_tf.details:
            det = structure_tf.details
            if "rsi" in det:
                rsi_val = det["rsi"]
                rsi_signal = "🟢 Alcista" if rsi_val > 50 else "🔴 Bajista" if rsi_val < 50 else "⚪ Neutral"
                lines.append(f"📊 RSI(H4): `{rsi_val:.1f}` → {rsi_signal}")

            if "trend" in det:
                lines.append(f"📈 Estructura: _{det['trend']}_")

        lines.append("")
        lines.append("━━━ *Recomendación* ━━━")
        if result.recommendation:
            lines.append(result.recommendation)
        else:
            bias_word = "COMPRA" if result.bias == Bias.BULLISH else "VENTA" if result.bias == Bias.BEARISH else "ESPERA"
            lines.append(f"📋 Dirección dominante: *{bias_word}*")

        if result.entry_price:
            lines.append("")
            lines.append(f"💰 Entry sugerido: `{result.entry_price}`")
        if result.sl:
            lines.append(f"🛑 SL: `{result.sl}`")
        if result.tp1:
            lines.append(f"🎯 TP1: `{result.tp1}`")
        if result.tp2:
            lines.append(f"🎯 TP2: `{result.tp2}`")
        if result.rr_ratio:
            viable = "✅ viable" if result.rr_viable else "❌ <2:1"
            lines.append(f"📐 RR: `1:{result.rr_ratio:.1f}` {viable}")

        if result.errors:
            lines.append("")
            lines.append("⚠️ *Advertencias:*")
            for e in result.errors[:3]:
                lines.append(f"  • `{e}`")

        lines.append("")
        lines.append(f"📡 Fuente: AMB Engine · {result.weighted_score}/100")

        await update.message.reply_text(
            "\n".join(lines), parse_mode="Markdown",
        )
        logger.info(
            f"/zona {symbol} -> score={result.weighted_score} "
            f"classification={result.classification.value} bias={result.bias.value}"
        )
    except Exception as e:
        logger.error(f"Error en /zona: {e}", exc_info=True)
        await update.message.reply_text(
            f"⚠️ Error analizando símbolo: {str(e)[:100]}"
        )


async def zshorthand(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Atajo /z = /zona"""
    await zona(update, context)
