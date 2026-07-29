"""
Horizon Analyzer — calcula bias + score 0-100 por timeframe (M5/H1/H4/D1).

Para cada timeframe:
- EMA slope (tendencia)
- RSI-14 (momento)
- MACD histogram (fuerza del momentum)
- ATR ratio (volatilidad normalizada)

Devuelve un score 0-100 y un bias (BULLISH/BEARISH/NEUTRAL).
El score master es la suma ponderada de los horizontes.

Ponderaciones (xaucharts-style):
  M5   -> 0.05 (scalping, ruido corto)
  H1   -> 0.15 (intradia)
  H4   -> 0.25 (swing)
  D1   -> 0.30 (direccion diaria)
  Macro-> 0.25 (risk-off desde macro_filter)
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class HorizonScore:
    timeframe: str
    bias: str  # BULLISH / BEARISH / NEUTRAL
    score: float  # 0..100
    components: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "timeframe": self.timeframe,
            "bias": self.bias,
            "score": round(self.score, 1),
            "components": {k: round(v, 4) for k, v in self.components.items()},
        }


@dataclass
class SymbolBias:
    symbol: str
    horizons: Dict[str, HorizonScore]
    master_bias: str  # BULLISH / BEARISH / NEUTRAL
    master_score: float  # 0..100

    def to_dict(self) -> Dict:
        return {
            "symbol": self.symbol,
            "master_bias": self.master_bias,
            "master_score": round(self.master_score, 1),
            "horizons": {tf: h.to_dict() for tf, h in self.horizons.items()},
        }


WEIGHTS = {
    "M5": 0.05,
    "M15": 0.08,
    "H1": 0.15,
    "H4": 0.25,
    "D1": 0.30,
    "MACRO": 0.25,
}

NEUTRAL_BAND_LOW = 40.0
NEUTRAL_BAND_HIGH = 60.0
STRONG_BAND = 70.0


# ─── Indicadores (sin numpy, solo python puro) ─────────────────────────


def _ema(closes: List[float], period: int) -> List[float]:
    if not closes or period <= 0:
        return []
    k = 2.0 / (period + 1)
    out = [closes[0]]
    for c in closes[1:]:
        out.append(c * k + out[-1] * (1 - k))
    return out


def _rsi(closes: List[float], period: int = 14) -> float:
    if len(closes) < period + 1:
        return 50.0
    gains: List[float] = []
    losses: List[float] = []
    for i in range(1, len(closes)):
        delta = closes[i] - closes[i - 1]
        gains.append(max(delta, 0))
        losses.append(max(-delta, 0))
    avg_g = sum(gains[:period]) / period
    avg_l = sum(losses[:period]) / period
    for i in range(period, len(gains)):
        avg_g = (avg_g * (period - 1) + gains[i]) / period
        avg_l = (avg_l * (period - 1) + losses[i]) / period
    if avg_l == 0:
        return 100.0 if avg_g > 0 else 50.0
    rs = avg_g / avg_l
    return 100.0 - (100.0 / (1 + rs))


def _macd_hist(closes: List[float]) -> float:
    if len(closes) < 35:
        return 0.0
    ema12 = _ema(closes, 12)
    ema26 = _ema(closes, 26)
    macd_line = [a - b for a, b in zip(ema12[-len(ema26):], ema26)]
    signal = _ema(macd_line, 9)
    if not signal:
        return 0.0
    return macd_line[-1] - signal[-1]


def _atr_norm(candles: List[dict], period: int = 14) -> float:
    """ATR normalizado por precio (0..1 aprox)."""
    if len(candles) < period + 1:
        return 0.0
    trs: List[float] = []
    for i in range(1, len(candles)):
        h = candles[i]["high"]
        l = candles[i]["low"]
        pc = candles[i - 1]["close"]
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    atr = sum(trs[-period:]) / period
    last_close = candles[-1].get("close", 0.0)
    if last_close <= 0:
        return 0.0
    return atr / last_close


def _classify(score: float) -> str:
    """Clasifica score en BULLISH / BEARISH / NEUTRAL.

    Bandas:
    - score >= 70 (or <= 30) → BULLISH (o BEARISH)
    - 60..70 (or 30..40) → sesgo moderado
    - 40..60 → NEUTRAL puro
    """
    if score >= STRONG_BAND:
        return "BULLISH"
    if score <= (100 - STRONG_BAND):
        return "BEARISH"
    if NEUTRAL_BAND_LOW <= score <= NEUTRAL_BAND_HIGH:
        return "NEUTRAL"
    if score > NEUTRAL_BAND_HIGH:
        return "BULLISH"
    return "BEARISH"


def _score_from_components(
    ema_score: float, rsi: float, macd_hist: float, atr_norm: float
) -> float:
    """Combina componentes en score 0-100 (50 = neutral).

    Mapeos:
    - EMA slope (-1..+1) -> 0..100 (centro 50)
    - RSI (0..100) -> 0..100 (centro 50)
    - MACD hist normalizado por ATR -> 0..100 (centro 50)
    """
    # EMA: -1..+1 → 0..100 (centro 50)
    ema_part = max(0.0, min(100.0, 50.0 + ema_score * 30.0))

    # RSI: 0..100 → score directo (RSI 70+ alcista fuerte, 30- bajista fuerte)
    rsi_part = max(0.0, min(100.0, rsi))

    # MACD: hist en unidades de precio; normalizado por ATR para tener
    # magnitud comparable entre símbolos
    macd_part = 50.0
    if atr_norm > 0 and atr_norm > 1e-9:
        norm = macd_hist / atr_norm  # hist vs ATR (en mismas unidades)
        # mapeo: -2..+2 → 10..90 (centro 50)
        macd_part = max(0.0, min(100.0, 50.0 + norm * 20.0))

    # Weighted average
    score = (
        ema_part * 0.40
        + rsi_part * 0.30
        + macd_part * 0.30
    )
    return max(0.0, min(100.0, score))


def analyze_horizon(candles: List[dict], timeframe: str) -> HorizonScore:
    """Calcula bias + score 0-100 para un timeframe especifico."""
    if not candles or len(candles) < 20:
        return HorizonScore(timeframe=timeframe, bias="NEUTRAL", score=50.0)

    closes = [float(c["close"]) for c in candles]

    ema20 = _ema(closes, 20)
    ema50 = _ema(closes, 50) if len(closes) >= 50 else ema20

    if len(ema20) < 5 or len(ema50) < 1:
        return HorizonScore(timeframe=timeframe, bias="NEUTRAL", score=50.0)

    ema20_recent = ema20[-5:]
    ema50_recent = ema50[-1]
    ema_diff = (ema20_recent[-1] - ema50_recent) / ema50_recent if ema50_recent else 0
    ema_slope = (ema20_recent[-1] - ema20_recent[0]) / ema20_recent[0] if ema20_recent[0] else 0

    ema_score = max(-1.0, min(1.0, ema_diff * 100 + ema_slope * 50))

    rsi = _rsi(closes, 14)
    macd_h = _macd_hist(closes)
    atr_n = _atr_norm(candles, 14)

    score = _score_from_components(ema_score, rsi, macd_h, atr_n)
    bias = _classify(score)

    return HorizonScore(
        timeframe=timeframe,
        bias=bias,
        score=score,
        components={
            "ema_diff": ema_diff,
            "ema_slope": ema_slope,
            "rsi": rsi,
            "macd_hist": macd_h,
            "atr_norm": atr_n,
        },
    )


def combine_horizons(
    symbol: str, horizons: Dict[str, HorizonScore]
) -> SymbolBias:
    """Combina scores por timeframe con pesos + calcula master bias/score."""
    if not horizons:
        return SymbolBias(symbol=symbol, horizons={}, master_bias="NEUTRAL", master_score=50.0)

    weighted = 0.0
    total_w = 0.0
    for tf, h in horizons.items():
        w = WEIGHTS.get(tf, 0.0)
        if w == 0:
            continue
        weighted += h.score * w
        total_w += w

    master_score = weighted / total_w if total_w > 0 else 50.0

    if master_score >= 65:
        master_bias = "BULLISH"
    elif master_score <= 35:
        master_bias = "BEARISH"
    else:
        master_bias = "NEUTRAL"

    return SymbolBias(
        symbol=symbol,
        horizons=horizons,
        master_bias=master_bias,
        master_score=master_score,
    )