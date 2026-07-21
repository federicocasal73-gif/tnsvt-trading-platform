"""
AMB Engine — Absolute Multi-Timeframe Bias Engine

Core analytical engine that determines directional bias across 8 timeframes
using Price Action + SMC as primary, traditional indicators as secondary.
"""
import asyncio
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

logger = logging.getLogger("Bot.AMB")


class Bias(Enum):
    BULLISH = "ALCISTA"
    BEARISH = "BAJISTA"
    NEUTRAL = "NEUTRAL"
    NO_TRADE = "NO TRADE"


class Classification(Enum):
    AAA_PLUS = "AAA+"
    AA_PLUS = "AA+"
    A_PLUS = "A+"
    BBB = "BBB"
    BB = "BB"
    B_PLUS = "B+"
    CCC = "CCC"
    CC = "CC"
    C = "C"
    D = "D"
    NO_TRADE = "NO TRADE"


TF_WEIGHTS = {
    "MACRO": 0.25,
    "WEEKLY": 0.20,
    "DAILY": 0.20,
    "H4": 0.15,
    "H1": 0.10,
    "M15": 0.05,
    "M5": 0.03,
    "M1": 0.02,
}

TF_ORDER = ["MACRO", "WEEKLY", "DAILY", "H4", "H1", "M15", "M5", "M1"]


CLASSIFICATION_THRESHOLDS = [
    (92, Classification.AAA_PLUS),
    (85, Classification.AA_PLUS),
    (75, Classification.A_PLUS),
    (65, Classification.BBB),
    (55, Classification.BB),
    (45, Classification.B_PLUS),
    (35, Classification.CCC),
    (25, Classification.CC),
    (15, Classification.C),
    (5, Classification.D),
    (0, Classification.NO_TRADE),
]


def classify_score(score: int) -> Classification:
    for threshold, cls in CLASSIFICATION_THRESHOLDS:
        if score >= threshold:
            return cls
    return Classification.NO_TRADE


def bias_from_score(score: int) -> Bias:
    if score >= 65:
        return Bias.BULLISH
    elif score >= 35:
        return Bias.NEUTRAL
    elif score >= 5:
        return Bias.BEARISH
    return Bias.NO_TRADE


@dataclass
class TFResult:
    timeframe: str
    score: int
    bias: Bias
    details: dict = field(default_factory=dict)


@dataclass
class AnalysisResult:
    symbol: str
    timeframe_results: list[TFResult]
    weighted_score: int
    classification: Classification
    bias: Bias
    rr_ratio: Optional[float] = None
    rr_viable: bool = False
    macro_alert: bool = False
    recommendation: str = ""
    entry_price: Optional[float] = None
    tp1: Optional[float] = None
    tp2: Optional[float] = None
    sl: Optional[float] = None
    errors: list[str] = field(default_factory=list)


class AMBEngine:
    def __init__(self):
        self._cache = {}

    async def analyze(self, symbol: str) -> AnalysisResult:
        errors = []

        macro_check = await self._check_macro_alert()
        if macro_check.get("red_alert"):
            result = AnalysisResult(
                symbol=symbol,
                timeframe_results=[],
                weighted_score=0,
                classification=Classification.NO_TRADE,
                bias=Bias.NO_TRADE,
                macro_alert=True,
                recommendation="🚫 MACRO RED ALERT — VIX > 35. No se permiten operaciones.",
                errors=["RED_ALERT: VIX > 35"],
            )
            logger.warning(f"MACRO RED ALERT activo para {symbol}")
            return result

        tf_results = []
        for tf in TF_ORDER:
            try:
                score = await self._score_timeframe(symbol, tf)
                bias = bias_from_score(score)
                tf_results.append(TFResult(timeframe=tf, score=score, bias=bias))
            except Exception as e:
                logger.error(f"Error scoring {tf} for {symbol}: {e}")
                tf_results.append(TFResult(timeframe=tf, score=0, bias=Bias.NEUTRAL, details={"error": str(e)}))
                errors.append(f"{tf}: {e}")

        weighted = self._calculate_weighted(tf_results)
        classification = classify_score(weighted)
        bias = bias_from_score(weighted)

        result = AnalysisResult(
            symbol=symbol,
            timeframe_results=tf_results,
            weighted_score=weighted,
            classification=classification,
            bias=bias,
            macro_alert=False,
            errors=errors,
        )

        self._apply_rr_filter(result)
        self._build_recommendation(result)
        return result

    async def _check_macro_alert(self) -> dict:
        try:
            from bot.analytics.macro_filter import check_macro_alert
            return await check_macro_alert()
        except ImportError:
            return {"red_alert": False, "vix": None}
        except Exception as e:
            logger.error(f"macro_filter error: {e}")
            return {"red_alert": False, "vix": None}

    async def _score_timeframe(self, symbol: str, tf: str) -> int:
        pa_score = await self._score_price_action(symbol, tf)
        smc_score = await self._score_smc(symbol, tf)
        ind_score = await self._score_indicators(symbol, tf)
        structure_score = await self._score_structure(symbol, tf)

        score = int(pa_score * 0.30 + smc_score * 0.25 + structure_score * 0.25 + ind_score * 0.20)
        return max(0, min(100, score))

    async def _score_price_action(self, symbol: str, tf: str) -> float:
        try:
            from bot.analytics.patterns.price_action import evaluate_price_action
            return await evaluate_price_action(symbol, tf)
        except ImportError:
            return 50.0
        except Exception as e:
            logger.debug(f"price_action error {symbol} {tf}: {e}")
            return 50.0

    async def _score_smc(self, symbol: str, tf: str) -> float:
        try:
            from bot.analytics.patterns.smc import evaluate_smc
            return await evaluate_smc(symbol, tf)
        except ImportError:
            return 50.0
        except Exception as e:
            logger.debug(f"smc error {symbol} {tf}: {e}")
            return 50.0

    async def _score_indicators(self, symbol: str, tf: str) -> float:
        try:
            from bot.analytics.indicator_wrappers import score_indicators
            return await score_indicators(symbol, tf)
        except ImportError:
            return 50.0
        except Exception as e:
            logger.debug(f"indicators error {symbol} {tf}: {e}")
            return 50.0

    async def _score_structure(self, symbol: str, tf: str) -> float:
        try:
            from bot.analytics.indicator_wrappers import score_structure
            return await score_structure(symbol, tf)
        except ImportError:
            return 50.0
        except Exception as e:
            logger.debug(f"structure error {symbol} {tf}: {e}")
            return 50.0

    def _calculate_weighted(self, results: list[TFResult]) -> int:
        total = 0.0
        for r in results:
            weight = TF_WEIGHTS.get(r.timeframe, 0)
            total += r.score * weight
        return int(round(total))

    def _apply_rr_filter(self, result: AnalysisResult) -> None:
        if result.rr_ratio is not None and result.rr_ratio < 2.0:
            result.rr_viable = False
            if result.weighted_score > 0:
                result.weighted_score = 0
                result.classification = Classification.NO_TRADE
                result.bias = Bias.NO_TRADE
        else:
            result.rr_viable = True

    def _build_recommendation(self, result: AnalysisResult) -> None:
        if result.macro_alert:
            result.recommendation = "🚫 MACRO RED ALERT — No operar"
            return

        if result.classification in (Classification.NO_TRADE, Classification.D, Classification.C):
            result.recommendation = "🚫 NO TRADE — Evitar este símbolo"
            return

        if result.classification in (Classification.CC, Classification.CCC):
            result.recommendation = "⚠️ Alta precaución — Solo si RR excepcional"
            return

        entry_tf = self._find_entry_tf(result)
        bias_word = "COMPRA" if result.bias == Bias.BULLISH else "VENTA"

        result.recommendation = (
            f"✅ {bias_word} en {entry_tf}\n"
        )
        if result.tp1:
            result.recommendation += f"🎯 TP1: {result.tp1}"
        if result.tp2:
            result.recommendation += f" | TP2: {result.tp2}"
        if result.sl:
            result.recommendation += f"\n🛑 SL: {result.sl}"
        if result.rr_ratio:
            result.recommendation += f"\n📐 RR: 1:{result.rr_ratio:.1f} → {'✅' if result.rr_viable else '❌'}"

    def _find_entry_tf(self, result: AnalysisResult) -> str:
        for r in reversed(result.timeframe_results):
            if r.timeframe in ("M15", "M5", "M1", "H1") and r.score >= 55:
                return r.timeframe
        return "M15"

    def format_analysis(self, result: AnalysisResult) -> str:
        lines = [
            f"📊 *Análisis Técnico: {result.symbol}*",
            "━━━━━━━━━━━━━━━━━━━━━━━",
            "",
            f"🏆 *Clasificación:* {result.classification.value} ({result.weighted_score}/100)",
            f"📐 *Bias general:* {result.bias.value}",
            "",
            "━━━ *Jerarquía Temporal* ━━━",
        ]

        for r in result.timeframe_results:
            emoji = self._tf_emoji(r.timeframe)
            weight = TF_WEIGHTS.get(r.timeframe, 0) * 100
            lines.append(
                f"{emoji} {r.timeframe:<7}: {r.bias.value:<8} ({r.score}/100) [{weight:.0f}%]"
            )

        lines.append("")
        lines.append("━━━ *Recomendación* ━━━")
        lines.append(result.recommendation)

        if result.errors:
            lines.append("")
            lines.append("⚠️ *Errores:*")
            for e in result.errors:
                lines.append(f"  • {e}")

        return "\n".join(lines)

    @staticmethod
    def _tf_emoji(tf: str) -> str:
        emojis = {
            "MACRO": "🌍", "WEEKLY": "📅", "DAILY": "📅",
            "H4": "⚡", "H1": "⚡", "M15": "⏱️", "M5": "⏱️", "M1": "⏱️",
        }
        return emojis.get(tf, "📊")
