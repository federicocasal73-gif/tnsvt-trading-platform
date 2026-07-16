"""Tests for the signal scorer heuristics (no LLM/network required)."""
import asyncio
import os
import sys

import pytest

# Allow running from anywhere
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

from services.config import Settings  # noqa: E402
from services.ollama_client import OllamaClient  # noqa: E402
from services.scorer import SignalScorer  # noqa: E402


@pytest.fixture
def settings() -> Settings:
    s = Settings()
    s.ollama_enabled = False  # don't actually call Ollama in tests
    return s


@pytest.fixture
def scorer(settings) -> SignalScorer:
    return SignalScorer(settings, OllamaClient(settings))


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def test_extract_features_high_rr(scorer):
    f = scorer._extract_features({
        "symbol": "EURUSD",
        "action": "buy",
        "entry_price": 1.1000,
        "stop_loss": 1.0950,
        "take_profit": 1.1150,
        "lot_size": 0.10,
        "confidence": 85,
    })
    assert f["rr_ratio"] == pytest.approx(3.0, abs=0.01)
    assert f["risk_pct"] == pytest.approx(0.455, abs=0.01)
    assert f["has_sl"] is True
    assert f["has_tp"] is True


def test_technical_score_strong_setup(scorer):
    features = {"rr_ratio": 3.0, "risk_pct": 1.0, "lot_size": 0.1, "has_sl": True, "has_tp": True, "source_confidence": 85}
    score = scorer._technical_score(features)
    assert score >= 80


def test_technical_score_no_sl_penalised(scorer):
    features = {"rr_ratio": 2.0, "risk_pct": 1.0, "lot_size": 0.1, "has_sl": False, "has_tp": True, "source_confidence": 50}
    score = scorer._technical_score(features)
    assert score < 50


def test_decide_executes_high_score(scorer):
    assert scorer._decide(82.0, 0.7) == "EXECUTE"
    assert scorer._decide(60.0, 0.5) == "MONITOR"
    assert scorer._decide(20.0, 0.5) == "REJECT"
    assert scorer._decide(95.0, 0.1) == "REJECT"  # low confidence


def test_llm_bonus_extracts_keywords(scorer):
    assert scorer._llm_bonus("Strong setup with high conviction.") > 50
    assert scorer._llm_bonus("Risky and avoid this trade.") < 50
    assert scorer._llm_bonus("Trending market supports momentum.") > 50


def test_confidence_higher_when_llm_available(scorer):
    c_without_llm = scorer._confidence(75.0, {"available": False})
    c_with_llm = scorer._confidence(75.0, {"available": True})
    assert c_with_llm >= c_without_llm


def test_score_full_flow_without_llm(scorer):
    signal = {
        "id": "00000000-0000-0000-0000-000000000001",
        "tenant_id": "00000000-0000-0000-0000-000000000001",
        "symbol": "EURUSD",
        "action": "buy",
        "entry_price": 1.1000,
        "stop_loss": 1.0950,
        "take_profit": 1.1150,
        "lot_size": 0.10,
        "confidence": 80,
        "source": "telegram",
    }
    result = _run(scorer.score(signal))
    assert result["symbol"] == "EURUSD"
    assert result["action"] == "buy"
    assert 0 <= result["score"] <= 100
    assert 0 <= result["confidence"] <= 1
    assert result["decision"] in {"EXECUTE", "MONITOR", "REJECT"}
    assert "model_version" in result
    assert "scored_at" in result