"""
Playbook generator — Construye acciones operativas por sesion de trading.

Inputs:
- bias (BULLISH/BEARISH/NEUTRAL)
- master_score (0..100)
- horizon_scores (M5/H1/H4/D1)
- candles (OHLCV)
- atr

Outputs:
- drivers[]: 5 categorias con estado (aligned/divergent/unknown)
- price_range: zona barata / justa / cara con %
- playbook_daily: action + zone + invalidation
- playbook_intraday: action + entry + stop + targets
- divergences[]: macro (dias) / H1 (horas) / M5 (minutos)
"""
from __future__ import annotations

import logging
from typing import Dict, List, Optional

logger = logging.getLogger("Orchestrator.Playbook")


# ─── Drivers ──────────────────────────────────────────────────────

def compute_drivers(bias: str, horizon_scores: Dict) -> List[dict]:
    """5 drivers categoricos: Inflacion, Posiciones, FX Asia, Funding, Volumen.

    Cada driver tiene: name, status (aligned/divergent/unknown), detail.
    """
    drivers: List[dict] = []

    # 1. Inflacion: BULLISH = alineado (FED dovish), BEARISH = risky
    drivers.append({
        "name": "Inflacion",
        "status": "aligned" if bias == "BULLISH" else ("divergent" if bias == "BEARISH" else "neutral"),
        "detail": "FED dovish favorece el oro" if bias == "BULLISH"
                  else "FED hawkish presiona el oro" if bias == "BEARISH"
                  else "Sin senal clara de inflacion",
    })

    # 2. Posiciones: derivado de H4 direction
    h4 = horizon_scores.get("H4", {})
    h4_score = h4.get("score", 50) if isinstance(h4, dict) else 50
    if h4_score >= 60:
        status = "aligned"
    elif h4_score <= 40:
        status = "divergent"
    else:
        status = "neutral"
    drivers.append({
        "name": "Posiciones",
        "status": status,
        "detail": f"H4 score {h4_score:.0f}/100",
    })

    # 3. FX Asia: derivado de M5 (trading session asiatica)
    m5 = horizon_scores.get("M5", {})
    m5_score = m5.get("score", 50) if isinstance(m5, dict) else 50
    drivers.append({
        "name": "FX Asia",
        "status": "aligned" if m5_score >= 55 else ("divergent" if m5_score <= 45 else "neutral"),
        "detail": f"M5 score {m5_score:.0f}/100 (sesion Asia)",
    })

    # 4. Funding: derivado de D1 (tendencia macro)
    d1 = horizon_scores.get("D1", {})
    d1_score = d1.get("score", 50) if isinstance(d1, dict) else 50
    drivers.append({
        "name": "Funding",
        "status": "aligned" if d1_score >= 60 else ("divergent" if d1_score <= 40 else "neutral"),
        "detail": f"D1 score {d1_score:.0f}/100 (tendencia diaria)",
    })

    # 5. Volumen: derivado de H1 (intradia momentum)
    h1 = horizon_scores.get("H1", {})
    h1_score = h1.get("score", 50) if isinstance(h1, dict) else 50
    drivers.append({
        "name": "Volumen",
        "status": "aligned" if h1_score >= 55 else ("divergent" if h1_score <= 45 else "neutral"),
        "detail": f"H1 score {h1_score:.0f}/100 (intradia momentum)",
    })

    return drivers


# ─── Price range ──────────────────────────────────────────────────


def compute_price_range(candles: List[dict], current_price: float) -> dict:
    """Calcula zona barata / justa / cara del precio en su rango.

    Usa las ultimas N velas para definir el rango. El midpoint es el fair value.
    """
    if not candles or current_price <= 0:
        return {
            "current": current_price,
            "low": current_price,
            "high": current_price,
            "midpoint": current_price,
            "zone": "fair",
            "barata_pct": 0.0,
            "cara_pct": 0.0,
        }

    highs = [float(c["high"]) for c in candles if c.get("high")]
    lows = [float(c["low"]) for c in candles if c.get("low")]
    if not highs or not lows:
        return {
            "current": current_price,
            "low": current_price,
            "high": current_price,
            "midpoint": current_price,
            "zone": "fair",
            "barata_pct": 0.0,
            "cara_pct": 0.0,
        }

    range_low = min(lows)
    range_high = max(highs)
    midpoint = (range_low + range_high) / 2.0

    if range_high == range_low:
        zone = "fair"
        barata_pct = 0.0
        cara_pct = 0.0
    else:
        position = (current_price - range_low) / (range_high - range_low)
        barata_pct = max(0.0, 1.0 - position) * 100
        cara_pct = position * 100
        if position < 0.3:
            zone = "barata"
        elif position > 0.7:
            zone = "cara"
        else:
            zone = "fair"

    return {
        "current": round(current_price, 5),
        "low": round(range_low, 5),
        "high": round(range_high, 5),
        "midpoint": round(midpoint, 5),
        "zone": zone,
        "barata_pct": round(barata_pct, 1),
        "cara_pct": round(cara_pct, 1),
    }


# ─── Playbooks ───────────────────────────────────────────────────


def compute_playbook_daily(
    bias: str,
    master_score: float,
    candles_h4: List[dict],
    atr: float,
) -> dict:
    """Playbook diario (swing/posicion)."""
    if not candles_h4 or atr <= 0:
        return {
            "horizon": "D1",
            "title": "Esperar confirmacion",
            "action": "Sin datos suficientes",
            "zone": "—",
            "invalidation": "—",
            "size_pct": 0.0,
            "horizon_days": "—",
        }

    last = candles_h4[-1]
    entry = float(last["close"])

    if bias == "BULLISH":
        sl = entry - atr * 1.5
        tp1 = entry + atr * 2.5
        tp2 = entry + atr * 4.0
        action = "Ventas selectivas en retrocesos (sesgo alcista)"
        zone = f"Rally {entry - atr:.2f} - {entry:.2f} (38-61% del impulso, vela rechazo)"
        invalidation = f"Cierre D1 bajo swing high reciente + DXY recuperando fuerza"
        size_pct = 0.5
    elif bias == "BEARISH":
        sl = entry + atr * 1.5
        tp1 = entry - atr * 2.5
        tp2 = entry - atr * 4.0
        action = "Compras selectivas en retrocesos (sesgo bajista)"
        zone = f"Rebote {entry:.2f} - {entry + atr:.2f} (38-61% del impulso, vela rechazo)"
        invalidation = f"Cierre D1 sobre swing low reciente + ETF inflows positivos"
        size_pct = 0.5
    else:
        return {
            "horizon": "D1",
            "title": "Neutro - esperar",
            "action": "Sin sesgo claro, mantenerse al margen",
            "zone": "—",
            "invalidation": "—",
            "size_pct": 0.0,
            "horizon_days": "—",
        }

    return {
        "horizon": "D1",
        "title": "Sesgo alcista" if bias == "BULLISH" else "Sesgo bajista",
        "action": action,
        "zone": zone,
        "entry": round(entry, 5),
        "sl": round(sl, 5),
        "tp1": round(tp1, 5),
        "tp2": round(tp2, 5),
        "invalidation": invalidation,
        "size_pct": size_pct,
        "horizon_days": "dias a semanas",
    }


def compute_playbook_intraday(
    bias: str,
    master_score: float,
    candles_h1: List[dict],
    atr: float,
) -> dict:
    """Playbook intradia (sesion actual)."""
    if not candles_h1 or atr <= 0:
        return {
            "horizon": "H1",
            "title": "Sin datos",
            "action": "Esperar vela H1",
            "entry": None,
            "stop": None,
            "tp1": None,
            "tp2": None,
            "size_pct": 0.0,
        }

    last = candles_h1[-1]
    entry = float(last["close"])

    if bias == "BULLISH":
        sl = entry - atr * 1.0
        tp1 = entry + atr * 1.5
        tp2 = entry + atr * 2.5
        action = "Venta en rally hacia resistencia H1 (no perseguir el precio abajo)"
        entry_desc = f"Rally H1 a resistencia, VWAP sesion o OB bajista con vela rechazo"
        invalidation = "Sobre swing high H1 (o sobre el OB)"
        size_pct = 0.5
    elif bias == "BEARISH":
        sl = entry + atr * 1.0
        tp1 = entry - atr * 1.5
        tp2 = entry - atr * 2.5
        action = "Compra en caida hacia soporte H1 (no perseguir el precio arriba)"
        entry_desc = f"Caida H1 a soporte, VWAP sesion o OB alcista con vela rechazo"
        invalidation = "Bajo swing low H1 (o bajo el OB)"
        size_pct = 0.5
    else:
        return {
            "horizon": "H1",
            "title": "Neutro - esperar breakout",
            "action": "Mercado sin direccion clara. Esperar ruptura de rango H1.",
            "entry": None,
            "stop": None,
            "tp1": None,
            "tp2": None,
            "size_pct": 0.0,
        }

    return {
        "horizon": "H1",
        "title": "Alcista fuerte" if bias == "BULLISH" else "Bajista fuerte",
        "action": action,
        "entry": round(entry, 5),
        "entry_detail": entry_desc,
        "stop": round(sl, 5),
        "tp1": round(tp1, 5),
        "tp2": round(tp2, 5),
        "size_pct": size_pct,
        "invalidation": invalidation,
        "reglas": "Nunca arrastrar SL sin break-even +1R. Mueve SL a BE en +1R. Evita entradas 15 min antes/después de noticias rojas. Max 3 perdidas consecutivas y paras el dia.",
    }


# ─── Divergencias ────────────────────────────────────────────────


def compute_divergences(horizon_scores: Dict) -> List[dict]:
    """Detecta divergencias entre timeframes.

    Compara scores de M5, H1, H4, D1 con el master score. Si hay diferencias
    mayores a 15 puntos, hay divergencia.
    """
    master_score = sum(
        h.get("score", 50) * w
        for h, w in [
            (horizon_scores.get("M5", {}), 0.05),
            (horizon_scores.get("H1", {}), 0.15),
            (horizon_scores.get("H4", {}), 0.25),
            (horizon_scores.get("D1", {}), 0.30),
        ]
    ) / 0.75  # normalize

    divergences: List[dict] = []

    # Macro vs M5
    m5 = horizon_scores.get("M5", {})
    m5_score = m5.get("score", 50) if isinstance(m5, dict) else 50
    diff_m5 = master_score - m5_score
    if abs(diff_m5) > 15:
        divergences.append({
            "timeframe": "Macro vs M5",
            "type": "macro_fuerte" if diff_m5 > 0 else "m5_fuerte",
            "score": round(diff_m5, 1),
            "detail": f"Macro {master_score:.0f} vs M5 {m5_score:.0f} ({diff_m5:+.0f})",
        })

    # H1 vs H4
    h1 = horizon_scores.get("H1", {})
    h1_score = h1.get("score", 50) if isinstance(h1, dict) else 50
    h4 = horizon_scores.get("H4", {})
    h4_score = h4.get("score", 50) if isinstance(h4, dict) else 50
    diff_h1h4 = h1_score - h4_score
    if abs(diff_h1h4) > 15:
        divergences.append({
            "timeframe": "H1 vs H4",
            "type": "h1_fuerte" if diff_h1h4 > 0 else "h4_fuerte",
            "score": round(diff_h1h4, 1),
            "detail": f"H1 {h1_score:.0f} vs H4 {h4_score:.0f} ({diff_h1h4:+.0f})",
        })

    # D1 vs M5
    d1 = horizon_scores.get("D1", {})
    d1_score = d1.get("score", 50) if isinstance(d1, dict) else 50
    diff_d1m5 = d1_score - m5_score
    if abs(diff_d1m5) > 20:
        divergences.append({
            "timeframe": "D1 vs M5",
            "type": "d1_fuerte" if diff_d1m5 > 0 else "m5_fuerte",
            "score": round(diff_d1m5, 1),
            "detail": f"D1 {d1_score:.0f} vs M5 {m5_score:.0f} ({diff_d1m5:+.0f})",
        })

    return divergences


# ─── Narrativa ───────────────────────────────────────────────────


def build_narrative(
    bias: str,
    master_score: float,
    symbol: str,
    drivers: List[dict],
    price_range: dict,
) -> str:
    """Construye un parrafo narrativo estilo xaucharts 'Veredicto del dia'."""
    aligned = sum(1 for d in drivers if d["status"] == "aligned")
    divergent = sum(1 for d in drivers if d["status"] == "divergent")

    return (
        f"El {symbol} hoy esta {'alcista' if bias == 'BULLISH' else 'bajista' if bias == 'BEARISH' else 'neutral'} "
        f"(score {master_score:.0f}/100). {aligned} drivers alineados, {divergent} divergentes. "
        f"Precio en zona {price_range['zone']} ({price_range['cara_pct']:.0f}% hacia arriba del rango). "
        f"Recomendacion: seguir sesgo con stops ajustados a ATR."
    )