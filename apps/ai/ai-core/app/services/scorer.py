"""Signal scorer: combines technical heuristics with Ollama LLM qualitative analysis.

Produces a `SignalScore` payload with score [0,100], confidence [0,1], decision
(EXECUTE / MONITOR / REJECT) and a brief LLM-generated explanation.
"""
from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from typing import Any

import structlog

log = structlog.get_logger("ai-core.scorer")

_SYSTEM_PROMPT = (
    "You are a disciplined quantitative trading analyst. "
    "Given a trading signal's structure, reply in <=2 sentences with a concrete "
    "verdict (risk, conviction, key caveat). Be terse. No emojis. No preambles."
)


class SignalScorer:
    def __init__(self, settings, ollama) -> None:
        self._settings = settings
        self._ollama = ollama
        self._model_version = f"{settings.ollama_model}-scorer-v1"

    async def score(self, signal: dict[str, Any]) -> dict[str, Any]:
        features = self._extract_features(signal)
        technical = self._technical_score(features)
        llm_result = await self._llm_analyze(signal, features)
        final_score = self._combine(technical, llm_result)
        confidence = self._confidence(technical, llm_result)
        decision = self._decide(final_score, confidence)

        return {
            "id": str(uuid.uuid4()),
            "symbol": signal.get("symbol", "UNKNOWN"),
            "action": signal.get("action", "buy").lower(),
            "score": round(final_score, 2),
            "confidence": round(confidence, 3),
            "decision": decision,
            "llm_summary": llm_result.get("response") if llm_result.get("available") else None,
            "features": features,
            "model_version": self._model_version,
            "scored_at": datetime.now(timezone.utc).isoformat(),
        }

    # ─── Feature extraction ─────────────────────────────────────────────────
    def _extract_features(self, s: dict[str, Any]) -> dict[str, Any]:
        entry = float(s.get("entry_price") or 0.0)
        sl = float(s.get("stop_loss") or 0.0)
        tp = float(s.get("take_profit") or 0.0)
        lot = float(s.get("lot_size") or 0.0)

        risk = abs(entry - sl) if entry > 0 and sl > 0 else 0.0
        reward = abs(tp - entry) if entry > 0 and tp > 0 else 0.0
        rr_ratio = (reward / risk) if risk > 0 else 0.0
        risk_pct = (risk / entry * 100.0) if entry > 0 else 0.0

        return {
            "rr_ratio": round(rr_ratio, 3),
            "risk_pct": round(risk_pct, 3),
            "lot_size": lot,
            "has_sl": sl > 0,
            "has_tp": tp > 0,
            "source_confidence": float(s.get("confidence") or 0.0),
            "symbol_hash": hashlib.sha1((s.get("symbol") or "").encode("utf-8")).hexdigest()[:8],
        }

    # ─── Technical heuristic score [0,100] ──────────────────────────────────
    def _technical_score(self, f: dict[str, Any]) -> float:
        score = 50.0
        rr = f["rr_ratio"]
        if rr >= 3.0:
            score += 30
        elif rr >= 2.0:
            score += 20
        elif rr >= 1.0:
            score += 10
        else:
            score -= 15

        if not f["has_sl"]:
            score -= 35
        if not f["has_tp"]:
            score -= 10

        if 0.5 <= f["risk_pct"] <= 2.0:
            score += 10
        elif f["risk_pct"] > 5.0:
            score -= 10

        src_conf = f["source_confidence"]
        if src_conf >= 80:
            score += 5
        elif src_conf and src_conf < 30:
            score -= 10

        return max(0.0, min(100.0, score))

    # ─── LLM qualitative analysis ───────────────────────────────────────────
    async def _llm_analyze(self, signal: dict, features: dict) -> dict[str, Any]:
        prompt = self._build_prompt(signal, features)
        result = await self._ollama.generate(prompt=prompt, system=_SYSTEM_PROMPT)
        return result

    def _build_prompt(self, s: dict, f: dict) -> str:
        return (
            f"Symbol: {s.get('symbol', '?')}\n"
            f"Action: {s.get('action', '?').upper()}\n"
            f"Entry: {s.get('entry_price')}\n"
            f"SL: {s.get('stop_loss')}\n"
            f"TP: {s.get('take_profit')}\n"
            f"Lot: {s.get('lot_size')}\n"
            f"R/R: {f['rr_ratio']}\n"
            f"Risk %: {f['risk_pct']}\n"
            f"Source: {s.get('source', 'unknown')}\n\n"
            "Verdict:"
        )

    # ─── Combination ────────────────────────────────────────────────────────
    def _combine(self, technical: float, llm: dict) -> float:
        if not llm.get("available"):
            return technical
        bonus = self._llm_bonus(llm.get("response", ""))
        return max(0.0, min(100.0, technical * 0.7 + bonus))

    def _llm_bonus(self, response: str) -> float:
        text = response.lower()
        score = 50.0
        if any(w in text for w in ("strong", "high conviction", "excellent", "solid")):
            score += 25
        if any(w in text for w in ("weak", "risky", "avoid", "poor")):
            score -= 25
        if "risk" in text:
            score -= 5
        if "trend" in text or "momentum" in text:
            score += 5
        return max(0.0, min(100.0, score))

    # ─── Confidence [0,1] ───────────────────────────────────────────────────
    def _confidence(self, technical: float, llm: dict) -> float:
        base = abs(technical - 50.0) / 50.0
        if llm.get("available"):
            return round(min(1.0, base * 0.6 + 0.4), 3)
        return round(base * 0.7, 3)

    # ─── Decision ───────────────────────────────────────────────────────────
    def _decide(self, score: float, confidence: float) -> str:
        if confidence < self._settings.score_min_confidence:
            return "REJECT"
        if score >= self._settings.score_execute_threshold:
            return "EXECUTE"
        if score >= self._settings.score_monitor_threshold:
            return "MONITOR"
        return "REJECT"