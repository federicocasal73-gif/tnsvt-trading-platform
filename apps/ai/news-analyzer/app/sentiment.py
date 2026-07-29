"""
Sentiment — keyword-based scoring (no LLM required).

Genera un score -1..+1 a partir de palabras clave en el titulo + descripcion.

Categorias de palabras:
- POSITIVE (alcista): rally, surge, climb, gain, beat, strong, growth, climb, recover, etc.
- NEGATIVE (bajista): plunge, drop, fall, miss, weak, decline, slump, cut, recession, etc.
- HAWKISH (FED): rate hike, hawkish, raise, higher, strong economy
- DOVISH (FED): rate cut, dovish, lower, easing, weak economy

Combina los matches con pesos y devuelve un score final + label.
"""
from __future__ import annotations

import re
from typing import Tuple

# Palabras positivas (alcistas para activos de riesgo)
POSITIVE_KEYWORDS = {
    "rally": 0.5, "surges": 0.5, "surge": 0.5, "climbs": 0.4, "climb": 0.4,
    "gains": 0.3, "gain": 0.3, "rises": 0.3, "rise": 0.3, "jumps": 0.4,
    "beats": 0.4, "beat": 0.4, "strong": 0.2, "growth": 0.3, "grow": 0.3,
    "recover": 0.3, "recovery": 0.3, "rebound": 0.3, "boost": 0.3,
    "optimism": 0.4, "optimistic": 0.4, "bullish": 0.5, "upgrade": 0.3,
    "outperform": 0.4, "highest": 0.3, "record high": 0.5, "soar": 0.5,
    "expansion": 0.3, "improvement": 0.3, "above": 0.1, "exceeds": 0.4,
    "exceeded": 0.4, "win": 0.3, "wins": 0.3, "positive": 0.3,
    "demand": 0.2, "boosted": 0.3, "rising": 0.3,
}

# Palabras negativas (bajistas)
NEGATIVE_KEYWORDS = {
    "plunge": 0.6, "plunges": 0.6, "drop": 0.4, "drops": 0.4,
    "fall": 0.4, "falls": 0.4, "fell": 0.4, "miss": 0.4, "misses": 0.4,
    "weak": 0.3, "weakness": 0.3, "decline": 0.4, "declines": 0.4,
    "slump": 0.5, "slumps": 0.5, "cut": 0.3, "cuts": 0.3, "recession": 0.6,
    "fear": 0.4, "fears": 0.4, "panic": 0.5, "crash": 0.6, "crisis": 0.5,
    "downgrade": 0.4, "underperform": 0.4, "lowest": 0.4, "record low": 0.6,
    "contraction": 0.4, "deteriorate": 0.4, "deterioration": 0.4,
    "below": 0.2, "warns": 0.3, "warning": 0.3, "concern": 0.3,
    "concerns": 0.3, "risk": 0.2, "loss": 0.4, "losses": 0.4,
    "layoffs": 0.4, "unemployment": 0.3, "default": 0.5, "bankruptcy": 0.6,
    "selloff": 0.5, "sell-off": 0.5, "tumbling": 0.5, "tumble": 0.5,
    "down": 0.2, "lower": 0.2, "negative": 0.3, "soft": 0.2,
}

# Palabras FED hawkish (alcistas para USD, bajistas para oro/riesgo)
HAWKISH_KEYWORDS = {
    "rate hike": 0.6, "rate hikes": 0.6, "rate-hike": 0.6, "hawkish": 0.6,
    "hike": 0.3, "hikes": 0.3, "raise rates": 0.6, "raises rates": 0.6,
    "rate increase": 0.6, "higher rates": 0.5, "tighten": 0.4, "tightening": 0.4,
    "strong economy": 0.4, "inflation rises": 0.4, "sticky inflation": 0.4,
    "hawk": 0.4, "hawks": 0.4, "restrictive": 0.4, "above target": 0.3,
    "delay cuts": 0.5, "no cuts": 0.5, "pause cuts": 0.5,
}

# Palabras FED dovish (bajistas para USD, alcistas para oro/riesgo)
DOVISH_KEYWORDS = {
    "rate cut": 0.6, "rate cuts": 0.6, "rate-cut": 0.6, "dovish": 0.6,
    "cut rates": 0.6, "cuts rates": 0.6, "lower rates": 0.5, "easing": 0.5,
    "ease": 0.4, "easy": 0.3, "weak economy": 0.4, "recession risk": 0.5,
    "dove": 0.4, "dovishness": 0.5, "pivot": 0.4, "rate reduction": 0.5,
    "rate decreases": 0.5, "stimulus": 0.4, "qe": 0.3, "quantitative easing": 0.4,
    "accommodative": 0.4, "below target": 0.3, "recession fears": 0.5,
    "recession concerns": 0.5,
}

# Negadores (invierte polaridad en la oracion)
NEGATORS = {"not", "no", "never", "without", "isn't", "wasn't", "won't", "doesn't", "didn't"}


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower().strip())


def _count_hits(text: str, keywords: dict) -> float:
    """Cuenta hits de palabras clave, considerando negadores."""
    score = 0.0
    for kw, weight in keywords.items():
        if kw in text:
            idx = text.find(kw)
            # Verifica negador cerca (palabra anterior)
            pre = text[:idx].strip().split()
            if pre and pre[-1].rstrip(".,;:!?") in NEGATORS:
                # Negado: invierte signo y atenua peso
                score -= weight * 0.5
            else:
                score += weight
    return score


def score_sentiment(title: str, description: str = "") -> Tuple[float, str]:
    """Devuelve (score, label) donde score esta en [-1, +1]."""
    full = _normalize(f"{title} {description}")

    pos = _count_hits(full, POSITIVE_KEYWORDS)
    neg = _count_hits(full, NEGATIVE_KEYWORDS)
    hawk = _count_hits(full, HAWKISH_KEYWORDS)
    dove = _count_hits(full, DOVISH_KEYWORDS)

    # Combinar: positivos/negativos pesan mas que hawkish/dovish
    # (hawkish/dovish ajusta el score pero no domina)
    raw = pos - neg + 0.5 * (dove - hawk)

    # Normalizar a -1..+1 con curva tanh para saturar
    import math
    score = math.tanh(raw)

    if score >= 0.25:
        label = "POSITIVE"
    elif score <= -0.25:
        label = "NEGATIVE"
    else:
        label = "NEUTRAL"

    return score, label


def score_to_stars(score: float) -> int:
    """Convierte score -1..+1 a 0-4 stars (xaucharts style).

    4 stars = muy positivo (alcista fuerte)
    0 stars = muy negativo (bajista fuerte)
    """
    if score >= 0.6:
        return 4
    if score >= 0.25:
        return 3
    if score <= -0.6:
        return 0
    if score <= -0.25:
        return 1
    return 2