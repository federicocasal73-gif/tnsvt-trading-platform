"""Tests para lst-account-bootstrap."""
import io
import json
import sys
import urllib.error
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

import pytest

_PARENT_DIR = str(Path(__file__).resolve().parent.parent)
if _PARENT_DIR not in sys.path:
    sys.path.insert(0, _PARENT_DIR)

import main as main_mod

find_existing_account = main_mod.find_existing_account
main = main_mod.main
wait_for_account_manager = main_mod.wait_for_account_manager
_get = main_mod._get
_post = main_mod._post
_MODULE_NAME = "main"


BASE = "http://account-manager:8510"
TENANT = "00000000-0000-0000-0000-000000000001"
HEADERS = {"X-Tenant-ID": TENANT}


def _http_resp(status, body, *, raise_=False):
    """Build a context-managed response mock."""
    cm = MagicMock()
    cm.__enter__.return_value.read.return_value = (
        json.dumps(body) if isinstance(body, (dict, list)) else body
    ).encode("utf-8")
    cm.__enter__.return_value.status = status
    if raise_:
        err = urllib.error.HTTPError(
            url="http://x", code=status, msg="err", hdrs={}, fp=io.BytesIO(
                (json.dumps(body) if isinstance(body, (dict, list)) else body).encode("utf-8")
            ),
        )
        return err
    return cm


def test_get_returns_200():
    with patch("main.urllib.request.urlopen", return_value=_http_resp(200, {"ok": True})):
        status, body = _get(f"{BASE}/health", HEADERS)
    assert status == 200
    assert body == {"ok": True}


def test_get_handles_http_error():
    with patch("main.urllib.request.urlopen", return_value=_http_resp(500, {"error": "boom"}, raise_=True)):
        status, body = _get(f"{BASE}/health", HEADERS)
    assert status == 500


def test_get_handles_connection_error():
    with patch("main.urllib.request.urlopen", side_effect=ConnectionError("nope")):
        status, body = _get(f"{BASE}/health", HEADERS)
    assert status == 0
    assert "nope" in body


def test_post_returns_201():
    with patch("main.urllib.request.urlopen", return_value=_http_resp(201, {"id": "abc"})):
        status, body = _post(f"{BASE}/api/v1/accounts", {"login": 1}, HEADERS)
    assert status == 201
    assert body == {"id": "abc"}


def test_post_handles_http_error():
    with patch("main.urllib.request.urlopen", return_value=_http_resp(409, {"error": "duplicate"}, raise_=True)):
        status, body = _post(f"{BASE}/api/v1/accounts", {"login": 1}, HEADERS)
    assert status == 409
    assert body == {"error": "duplicate"}


def test_wait_for_account_manager_returns_true():
    with patch("main._get", return_value=(200, {"status": "ok"})):
        assert wait_for_account_manager(BASE, HEADERS, retries=3, delay=0.01) is True


def test_wait_for_account_manager_returns_false_on_timeout():
    with patch("main._get", return_value=(503, {"status": "down"})):
        assert wait_for_account_manager(BASE, HEADERS, retries=2, delay=0.01) is False


def test_find_existing_account_match():
    body = {
        "accounts": [
            {"id": "uuid-1", "login": 123, "server": "X"},
            {"id": "uuid-2", "login": 12345678, "server": "YourBroker-MT5"},
        ]
    }
    with patch("main._get", return_value=(200, body)):
        assert find_existing_account(BASE, HEADERS, TENANT, 12345678, "YourBroker-MT5") == "uuid-2"


def test_find_existing_account_no_match():
    body = {"accounts": [{"id": "uuid-1", "login": 999, "server": "X"}]}
    with patch("main._get", return_value=(200, body)):
        assert find_existing_account(BASE, HEADERS, TENANT, 12345678, "YourBroker-MT5") is None


def test_find_existing_account_handles_non_dict():
    with patch("main._get", return_value=(200, [])):
        assert find_existing_account(BASE, HEADERS, TENANT, 1, "X") is None


def test_find_existing_account_handles_login_as_string():
    body = {"accounts": [{"id": "uuid-2", "login": "12345678", "server": "YourBroker-MT5"}]}
    with patch("main._get", return_value=(200, body)):
        assert find_existing_account(BASE, HEADERS, TENANT, 12345678, "YourBroker-MT5") == "uuid-2"


def test_main_missing_credentials_returns_1(monkeypatch):
    monkeypatch.setenv("LST_LOGIN", "")
    monkeypatch.setenv("LST_SERVER", "")
    monkeypatch.setenv("LST_PASSWORD", "")
    monkeypatch.setenv("ACCOUNT_MANAGER_URL", BASE)
    monkeypatch.setenv("LST_TENANT_ID", TENANT)
    assert main() == 1


def test_main_non_integer_login_returns_1(monkeypatch):
    monkeypatch.setenv("LST_LOGIN", "not-a-number")
    monkeypatch.setenv("LST_SERVER", "X")
    monkeypatch.setenv("LST_PASSWORD", "p")
    monkeypatch.setenv("ACCOUNT_MANAGER_URL", BASE)
    monkeypatch.setenv("LST_TENANT_ID", TENANT)
    assert main() == 1


def test_main_account_manager_unreachable_returns_1(monkeypatch):
    monkeypatch.setenv("LST_LOGIN", "12345678")
    monkeypatch.setenv("LST_SERVER", "YourBroker-MT5")
    monkeypatch.setenv("LST_PASSWORD", "secret")
    monkeypatch.setenv("ACCOUNT_MANAGER_URL", BASE)
    monkeypatch.setenv("LST_TENANT_ID", TENANT)
    monkeypatch.setenv("LST_ACCOUNT_ID_FILE", "/tmp/nonexistent_path_for_test")
    with patch("main.wait_for_account_manager", return_value=False):
        assert main() == 1


def test_main_existing_account_writes_file(monkeypatch, capsys):
    import tempfile, os
    fd, out_path = tempfile.mkstemp(prefix="lst_", suffix=".txt")
    os.close(fd)
    try:
        body = {
            "accounts": [
                {"id": "uuid-existing", "login": 12345678, "server": "YourBroker-MT5"}
            ]
        }
        monkeypatch.setenv("LST_LOGIN", "12345678")
        monkeypatch.setenv("LST_SERVER", "YourBroker-MT5")
        monkeypatch.setenv("LST_PASSWORD", "secret")
        monkeypatch.setenv("ACCOUNT_MANAGER_URL", BASE)
        monkeypatch.setenv("LST_TENANT_ID", TENANT)
        monkeypatch.setenv("LST_ACCOUNT_ID_FILE", out_path)
        with patch("main.wait_for_account_manager", return_value=True):
            with patch("main._get", return_value=(200, body)):
                rc = main()
        assert rc == 0
        with open(out_path) as f:
            assert f.read() == "uuid-existing"
        assert "uuid-existing" in capsys.readouterr().out
    finally:
        try:
            os.unlink(out_path)
        except OSError:
            pass


def test_main_creates_new_account(monkeypatch):
    import tempfile, os
    fd, out_path = tempfile.mkstemp(prefix="lst_", suffix=".txt")
    os.close(fd)
    try:
        monkeypatch.setenv("LST_LOGIN", "12345678")
        monkeypatch.setenv("LST_SERVER", "YourBroker-MT5")
        monkeypatch.setenv("LST_PASSWORD", ")fxG$G(B4D")
        monkeypatch.setenv("LST_BROKER", "YourBroker")
        monkeypatch.setenv("LST_ALIAS", "lst-main")
        monkeypatch.setenv("ACCOUNT_MANAGER_URL", BASE)
        monkeypatch.setenv("LST_TENANT_ID", TENANT)
        monkeypatch.setenv("LST_ACCOUNT_ID_FILE", out_path)
        with patch("main.wait_for_account_manager", return_value=True):
            with patch("main._get", return_value=(200, {"accounts": []})):
                with patch("main._post", return_value=(201, {"id": "uuid-new"})) as post_mock:
                    rc = main()
        assert rc == 0
        with open(out_path) as f:
            assert f.read() == "uuid-new"
        sent_body = post_mock.call_args.args[1]
        assert sent_body["login"] == 12345678
        assert sent_body["server"] == "YourBroker-MT5"
        assert sent_body["broker"] == "YourBroker"
    finally:
        try:
            os.unlink(out_path)
        except OSError:
            pass


def test_main_create_failure_returns_1(monkeypatch):
    import tempfile, os
    fd, out_path = tempfile.mkstemp(prefix="lst_", suffix=".txt")
    os.close(fd)
    try:
        monkeypatch.setenv("LST_LOGIN", "12345678")
        monkeypatch.setenv("LST_SERVER", "YourBroker-MT5")
        monkeypatch.setenv("LST_PASSWORD", "secret")
        monkeypatch.setenv("ACCOUNT_MANAGER_URL", BASE)
        monkeypatch.setenv("LST_TENANT_ID", TENANT)
        monkeypatch.setenv("LST_ACCOUNT_ID_FILE", out_path)
        with patch("main.wait_for_account_manager", return_value=True):
            with patch("main._get", return_value=(200, {"accounts": []})):
                with patch("main._post", return_value=(500, {"error": "boom"})):
                    rc = main()
        assert rc == 1
        with open(out_path) as f:
            assert f.read() == ""
    finally:
        try:
            os.unlink(out_path)
        except OSError:
            pass
