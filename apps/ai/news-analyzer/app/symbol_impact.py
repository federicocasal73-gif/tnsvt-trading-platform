"""
Symbol Impact — mapea 'como reacciona el oro' / EURUSD / etc. segun la noticia.

Basado en principios de mercado:
- Hawkish FED (rate hike) → USD+, oro-, EUR-, riesgo-
- Dovish FED (rate cut)   → USD-, oro+, EUR+, riesgo+
- Geopolitica tensa       → USD-, oro+, petroleo+, riesgo mixto
- DXY alto                → EUR-, oro-, riesgo-
- DXY bajo                → EUR+, oro+, riesgo+
- Inflacion alta          → USD+ (FED tights), oro+
- Inflacion baja          → USD- (FED eases), oro mixto
- Empleo fuerte           → USD+ (hawkish), oro-
- Empleo debil            → USD- (dovish), oro+

Para cada noticia, devuelve reaction por simbolo.
"""
from __future__ import annotations

from typing import Dict, List


def impact_for_symbols(
    categories: List[str], sentiment_score: float, title: str = ""
) -> Dict[str, str]:
    """Devuelve reaction por simbolo segun categorias + sentiment.

    Returns dict: {"XAUUSD": "Alcista (FED dovish)", "EURUSD": "Alcista", ...}
    """
    out: Dict[str, str] = {}
    title_l = title.lower()

    is_hawkish = any(kw in title_l for kw in [
        "rate hike", "hawkish", "rate increase", "hike", "higher rates",
        "tighten", "tightening", "sticky inflation", "delay cuts",
    ])
    is_dovish = any(kw in title_l for kw in [
        "rate cut", "dovish", "cuts rates", "lower rates", "easing",
        "weak economy", "recession", "pivot", "stimulus",
    ])
    is_geo = "Geopolitica" in categories
    is_inflation = "Inflacion" in categories
    is_macro_strong = "Macro" in categories and sentiment_score >= 0.3
    is_macro_weak = "Macro" in categories and sentiment_score <= -0.3
    is_politics = "Politica" in categories
    is_dollar = "Dolar" in categories

    # ---- XAUUSD (oro) ----
    if is_hawkish:
        out["XAUUSD"] = "Bajista (FED hawkish presiona al oro)"
    elif is_dovish:
        out["XAUUSD"] = "Alcista (FED dovish, menor costo de oportunidad)"
    elif is_geo:
        out["XAUUSD"] = "Alcista (refugio seguro por tension geopolitica)"
    elif is_inflation and sentiment_score > 0:
        out["XAUUSD"] = "Alcista (cobertura contra inflacion)"
    elif is_dollar:
        out["XAUUSD"] = "Bajista (USD fuerte encarece el oro)"
    else:
        out["XAUUSD"] = "Neutral (sin catalizador claro)"

    # ---- EURUSD ----
    if is_hawkish:
        out["EURUSD"] = "Bajista (USD fuerte)"
    elif is_dovish:
        out["EURUSD"] = "Alcista (USD debilita)"
    elif is_geo:
        out["EURUSD"] = "Bajista (USD gana vuelo a refugio)"
    else:
        out["EURUSD"] = "Neutral"

    # ---- DXY ----
    if is_hawkish:
        out["DXY"] = "Alcista (hawkish fortalece al USD)"
    elif is_dovish:
        out["DXY"] = "Bajista (dovish debilita al USD)"
    elif is_geo:
        out["DXY"] = "Alcista (refugio en USD)"
    elif is_inflation and sentiment_score > 0:
        out["DXY"] = "Alcista (FED hawkish)"
    else:
        out["DXY"] = "Neutral"

    # ---- NAS100 ----
    if is_hawkish:
        out["NAS100"] = "Bajista (mayor costo de capital)"
    elif is_dovish:
        out["NAS100"] = "Alcista (mas liquidez)"
    elif is_macro_strong:
        out["NAS100"] = "Alcista (economia fuerte)"
    elif is_macro_weak:
        out["NAS100"] = "Bajista (recesion risk-off)"
    elif is_geo:
        out["NAS100"] = "Bajista (risk-off tech)"
    else:
        out["NAS100"] = "Neutral"

    # ---- BTCUSD ----
    if is_hawkish:
        out["BTCUSD"] = "Bajista (liquidez se contrae)"
    elif is_dovish:
        out["BTCUSD"] = "Alcista (liquidez + risk-on)"
    elif is_geo:
        out["BTCUSD"] = "Mixto (puede ir a digital gold o a cash)"
    elif is_inflation and sentiment_score > 0:
        out["BTCUSD"] = "Alcista (cobertura contra inflacion)"
    else:
        out["BTCUSD"] = "Neutral"

    # ---- WTI/BRENT (petroleo) ----
    if is_geo:
        out["WTI"] = "Alcista (riesgo geopolitico sobre suministro)"
        out["BRENT"] = "Alcista (mismo motivo)"
    elif is_macro_strong:
        out["WTI"] = "Alcista (demanda)"
        out["BRENT"] = "Alcista (demanda)"
    elif is_macro_weak:
        out["WTI"] = "Bajista (demanda cae)"
        out["BRENT"] = "Bajista"
    else:
        out["WTI"] = "Neutral"
        out["BRENT"] = "Neutral"

    return out