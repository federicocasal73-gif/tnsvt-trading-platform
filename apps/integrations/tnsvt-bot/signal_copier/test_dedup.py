"""Test del dedup de notificaciones trade_blocked (modulo notify_dedup)."""
import os
import tempfile
import time

from notify_dedup import (
    _key_str,
    get_dedup_secs,
    load_recent,
    save_recent,
    should_dedup_blocked_notif,
    should_dedup_blocked_notif_persistent,
)


def test_first_call_not_dedup():
    recent = {}
    is_dedup, _ = should_dedup_blocked_notif(recent, "XAUUSD", "BUY", "news", 300, now_ts=1000.0)
    assert is_dedup is False
    assert recent[_key_str("XAUUSD", "BUY", "news")] == 1000.0


def test_duplicate_within_window_deduped():
    recent = {}
    should_dedup_blocked_notif(recent, "XAUUSD", "BUY", "news", 300, now_ts=1000.0)
    is_dedup, _ = should_dedup_blocked_notif(recent, "XAUUSD", "BUY", "news", 300, now_ts=1030.0)
    assert is_dedup is True


def test_after_window_not_deduped():
    recent = {}
    should_dedup_blocked_notif(recent, "XAUUSD", "BUY", "news", 300, now_ts=1000.0)
    is_dedup, _ = should_dedup_blocked_notif(recent, "XAUUSD", "BUY", "news", 300, now_ts=1301.0)
    assert is_dedup is False
    assert recent[_key_str("XAUUSD", "BUY", "news")] == 1301.0


def test_different_reasons_not_deduped():
    recent = {}
    is_dedup1, _ = should_dedup_blocked_notif(recent, "XAUUSD", "BUY", "news", 300, now_ts=1000.0)
    is_dedup2, _ = should_dedup_blocked_notif(recent, "XAUUSD", "BUY", "risk", 300, now_ts=1001.0)
    assert is_dedup1 is False
    assert is_dedup2 is False
    assert len(recent) == 2


def test_different_symbols_not_deduped():
    recent = {}
    should_dedup_blocked_notif(recent, "XAUUSD", "BUY", "news", 300, now_ts=1000.0)
    is_dedup, _ = should_dedup_blocked_notif(recent, "EURUSD", "BUY", "news", 300, now_ts=1001.0)
    assert is_dedup is False


def test_different_actions_not_deduped():
    recent = {}
    should_dedup_blocked_notif(recent, "XAUUSD", "BUY", "news", 300, now_ts=1000.0)
    is_dedup, _ = should_dedup_blocked_notif(recent, "XAUUSD", "SELL", "news", 300, now_ts=1001.0)
    assert is_dedup is False


def test_empty_reason_uses_empty_string():
    recent = {}
    should_dedup_blocked_notif(recent, "XAUUSD", "BUY", "", 300, now_ts=1000.0)
    is_dedup, _ = should_dedup_blocked_notif(recent, "XAUUSD", "BUY", "", 300, now_ts=1001.0)
    assert is_dedup is True


def test_window_boundary_exactly_at_dedup_secs():
    recent = {}
    should_dedup_blocked_notif(recent, "XAUUSD", "BUY", "news", 300, now_ts=1000.0)
    is_dedup, _ = should_dedup_blocked_notif(recent, "XAUUSD", "BUY", "news", 300, now_ts=1300.0)
    assert is_dedup is False


def test_zero_dedup_secs_means_no_dedup():
    recent = {}
    should_dedup_blocked_notif(recent, "XAUUSD", "BUY", "news", 0, now_ts=1000.0)
    is_dedup, _ = should_dedup_blocked_notif(recent, "XAUUSD", "BUY", "news", 0, now_ts=1000.0001)
    assert is_dedup is False


def test_post_failure_does_not_extend_window():
    recent = {}
    should_dedup_blocked_notif(recent, "XAUUSD", "BUY", "news", 300, now_ts=1000.0)
    is_dedup, _ = should_dedup_blocked_notif(recent, "XAUUSD", "BUY", "news", 300, now_ts=1060.0)
    assert is_dedup is True
    assert recent[_key_str("XAUUSD", "BUY", "news")] == 1000.0


def test_many_accounts_independent():
    recent = {}
    should_dedup_blocked_notif(recent, "XAUUSD", "BUY", "news", 300, now_ts=1000.0)
    should_dedup_blocked_notif(recent, "BTCUSD", "BUY", "news", 300, now_ts=1001.0)
    should_dedup_blocked_notif(recent, "XAUUSD", "SELL", "news", 300, now_ts=1002.0)
    should_dedup_blocked_notif(recent, "XAUUSD", "BUY", "risk", 300, now_ts=1003.0)
    assert len(recent) == 4
    is_dedup1, _ = should_dedup_blocked_notif(recent, "XAUUSD", "BUY", "news", 300, now_ts=1004.0)
    is_dedup2, _ = should_dedup_blocked_notif(recent, "BTCUSD", "BUY", "news", 300, now_ts=1004.0)
    assert is_dedup1 is True
    assert is_dedup2 is True


def _tmp_file():
    d = tempfile.mkdtemp()
    return os.path.join(d, "dedup.json")


def test_save_and_load_roundtrip():
    path = _tmp_file()
    save_recent({_key_str("XAUUSD", "BUY", "news"): 1000.0}, path)
    loaded = load_recent(path)
    assert loaded == {_key_str("XAUUSD", "BUY", "news"): 1000.0}


def test_load_missing_file_returns_empty():
    assert load_recent(_tmp_file()) == {}


def test_persistent_survives_restart():
    path = _tmp_file()
    is_dedup1, _ = should_dedup_blocked_notif_persistent(
        "XAUUSD", "BUY", "news", 300, now_ts=1000.0, path=path
    )
    assert is_dedup1 is False
    # Simula reinicio: nueva dict en memoria, pero mismo archivo.
    is_dedup2, _ = should_dedup_blocked_notif_persistent(
        "XAUUSD", "BUY", "news", 300, now_ts=1001.0, path=path
    )
    assert is_dedup2 is True


def test_persistent_different_reason_not_deduped():
    path = _tmp_file()
    should_dedup_blocked_notif_persistent("XAUUSD", "BUY", "news", 300, now_ts=1000.0, path=path)
    is_dedup, _ = should_dedup_blocked_notif_persistent(
        "XAUUSD", "BUY", "risk", 300, now_ts=1001.0, path=path
    )
    assert is_dedup is False


def test_get_dedup_secs_default(monkeypatch):
    monkeypatch.delenv("BLOCKED_NOTIF_DEDUP_SECS", raising=False)
    assert get_dedup_secs() == 86400


def test_get_dedup_secs_from_env(monkeypatch):
    monkeypatch.setenv("BLOCKED_NOTIF_DEDUP_SECS", "120")
    assert get_dedup_secs() == 120


def test_get_dedup_secs_invalid_falls_back(monkeypatch):
    monkeypatch.setenv("BLOCKED_NOTIF_DEDUP_SECS", "not-a-number")
    assert get_dedup_secs() == 86400
