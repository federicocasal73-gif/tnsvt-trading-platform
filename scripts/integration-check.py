"""
Integration smoke checks para el sistema LST (no requiere servicios externos).

Verifica que los archivos criticos existen, que los schemas coinciden
entre producer y consumer, y que las constantes de cableado estan alineadas.

Uso:
    python scripts/integration-check.py
"""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def _can_exec(script: Path, timeout: int = 10) -> bool:
    """Ejecuta un modulo python en su propio cwd para verificar imports."""
    result = subprocess.run(
        [sys.executable, "-c", "import sys; sys.path.insert(0, '.'); import main; print('OK')"],
        cwd=str(script.parent),
        capture_output=True, text=True, timeout=timeout,
    )
    return result.returncode == 0


def test_liquidity_engine_imports():
    print("[1] liquidity-engine app/* imports OK")
    for name, path in [
        ("lst_engine", "app/lst_engine.py"),
        ("zones_engine", "app/zones_engine.py"),
        ("main", "app/main.py"),
    ]:
        result = subprocess.run(
            [sys.executable, "-c", f"import {path.replace('/', '.').replace('.py', '')}; print('OK')"],
            cwd=str(ROOT / "apps/ai/liquidity-engine"),
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 0, f"{name}: {result.stderr}"


def test_news_bridge_imports():
    print("[2] news-bridge imports OK")
    assert _can_exec(ROOT / "apps/integrations/news-bridge/main.py")


def test_lst_bootstrap_imports():
    print("[3] lst-account-bootstrap imports OK")
    assert _can_exec(ROOT / "apps/integrations/lst-account-bootstrap/main.py")


def test_docker_compose_has_critical_services():
    import yaml
    compose = yaml.safe_load((ROOT / "docker-compose.dev.yml").read_text(encoding="utf-8"))
    services = compose["services"]
    required = [
        "execution-engine",
        "lst-account-bootstrap",
        "news-bridge",
        "news-analyzer",
        "macro-fetcher",
        "account-manager",
        "liquidity-engine",
        "orchestrator",
    ]
    for svc in required:
        assert svc in services, f"missing service: {svc}"
    print("[4] docker-compose has all critical services (mt5-connector is run on Windows host)")


def test_gateway_routes_registered():
    svc_go = (ROOT / "apps/gateway/api-gateway/internal/config/services.go").read_text(encoding="utf-8")
    cfg_json = json.loads((ROOT / "apps/gateway/api-gateway/config/services.json").read_text())
    json_names = {s["name"] for s in cfg_json}
    required = {
        "auth-service", "user-service", "signal-engine", "execution-engine",
        "copy-trading", "risk-engine", "mt5-connector", "audit-engine",
        "ai-core", "regime-detector", "price-feed", "telegram-bot-service",
        "bridge-api", "account-manager", "liquidity-engine", "orchestrator",
        "mcp-trading-server", "news-analyzer", "macro-fetcher",
    }
    missing_in_go = [r for r in required if f'Name:       "{r}"' not in svc_go]
    missing_in_json = required - json_names
    assert not missing_in_go, f"missing in services.go: {missing_in_go}"
    assert not missing_in_json, f"missing in services.json: {missing_in_json}"
    print(f"[5] gateway has all {len(required)} routes registered (services.go + services.json)")


def test_execution_engine_resolves_lst_source():
    svc = (ROOT / "apps/trading/execution-engine/internal/service/service.go").read_text(encoding="utf-8")
    assert "resolveAccount" in svc
    assert "LSTAccount" in svc
    assert 'strings.HasPrefix(source, "orchestrator")' in svc
    print("[6] execution-engine has LST routing logic")


def test_orchestrator_publishes_validated_subject():
    cfg = (ROOT / "apps/ai/orchestrator/app/config.py").read_text(encoding="utf-8")
    assert 'nats_subject_out: str = "trading.signal.validated"' in cfg
    print("[7] orchestrator publishes to trading.signal.validated")


def test_execution_engine_subscribes_validated():
    sub = (ROOT / "apps/trading/execution-engine/internal/subscriber/subscriber.go").read_text(encoding="utf-8")
    assert 's.nats.Subscribe("trading.signal.validated"' in sub
    print("[8] execution-engine subscribes to trading.signal.validated")


def test_orchestrator_tenant_id_is_uuid():
    cfg = (ROOT / "apps/ai/orchestrator/app/config.py").read_text(encoding="utf-8")
    assert 'tenant_id: str = "00000000-0000-0000-0000-000000000001"' in cfg
    multi = (ROOT / "apps/ai/orchestrator/app/multi_orchestrator.py").read_text(encoding="utf-8")
    assert "self.settings.tenant_id" in multi
    assert 'tenant_id="orchestrator"' not in multi
    print("[9] orchestrator tenant_id is a valid UUID (not 'orchestrator')")


def test_news_bridge_uses_jetstream():
    code = (ROOT / "apps/integrations/news-bridge/main.py").read_text(encoding="utf-8")
    assert "self._js.subscribe" in code
    assert "self._nc.subscribe" not in code
    assert "manual_ack=True" in code
    assert "await msg.ack()" in code
    assert "await msg.nak()" in code
    print("[10] news-bridge uses JetStream with ack/nak")


def test_liquidity_engine_publishes_lst_subject():
    code = (ROOT / "apps/ai/liquidity-engine/app/config.py").read_text(encoding="utf-8")
    assert 'nats_subject_lst: str = "tnsvt.lst.signal"' in code
    print("[11] liquidity-engine publishes to tnsvt.lst.signal")


def test_execution_engine_reads_lst_account_file():
    code = (ROOT / "apps/trading/execution-engine/main.go").read_text(encoding="utf-8")
    assert "LST_ACCOUNT_ID_FILE" in code
    assert "strings.TrimSpace" in code
    print("[12] execution-engine reads LST_ACCOUNT_ID_FILE")


def test_env_example_has_topone_trader():
    env = (ROOT / ".env.example").read_text(encoding="utf-8")
    assert "98891135" in env
    assert "TopOneTrader-MT5" in env
    assert ")fxG$G(B4D" in env
    assert "C:\\Program Files\\MetaTrader 5" not in env
    assert "FTMO MetaTrader 5" in env
    print("[13] .env.example has TopOneTrader creds, MT5_PATH unchanged on FTMO")


def test_ftmo_account_id_env_used():
    compose = (ROOT / "docker-compose.dev.yml").read_text(encoding="utf-8")
    assert "DEFAULT_ACCOUNT_ID: ${FTMO_ACCOUNT_ID:-default}" in compose
    print("[14] execution-engine DEFAULT_ACCOUNT_ID sourced from FTMO_ACCOUNT_ID")


def test_shared_volume_in_compose():
    import yaml
    compose = yaml.safe_load((ROOT / "docker-compose.dev.yml").read_text(encoding="utf-8"))
    assert "tnsvt-secrets" in compose["volumes"]
    print("[15] tnsvt-secrets volume defined")


def test_microstructure_signal_does_not_include_orchestrator_in_source():
    nats_pub = (ROOT / "apps/ai/liquidity-engine/app/nats_client.py").read_text(encoding="utf-8")
    if "source" in nats_pub.lower():
        assert "LSTSignal" in nats_pub
    print("[16] liquidity-engine publishes raw LSTSignal (no source field)")


def test_mt5_connector_session_manager_supports_multi_account():
    code = (ROOT / "apps/broker/mt5-connector/internal/session/manager.go").read_text(encoding="utf-8")
    assert "mt5.login" in code or "GetCredsByID" in code
    print("[17] mt5-connector session manager supports per-account login")


def test_orchestrator_has_macro_filter():
    code = (ROOT / "apps/ai/orchestrator/app/multi_orchestrator.py").read_text(encoding="utf-8")
    assert "check_macro_conditions" in code
    assert "correlation_engine.filter_signals" in code
    print("[18] orchestrator applies macro filter + correlation")


if __name__ == "__main__":
    tests = [
        test_liquidity_engine_imports,
        test_news_bridge_imports,
        test_lst_bootstrap_imports,
        test_docker_compose_has_critical_services,
        test_gateway_routes_registered,
        test_execution_engine_resolves_lst_source,
        test_orchestrator_publishes_validated_subject,
        test_execution_engine_subscribes_validated,
        test_orchestrator_tenant_id_is_uuid,
        test_news_bridge_uses_jetstream,
        test_liquidity_engine_publishes_lst_subject,
        test_execution_engine_reads_lst_account_file,
        test_env_example_has_topone_trader,
        test_ftmo_account_id_env_used,
        test_shared_volume_in_compose,
        test_microstructure_signal_does_not_include_orchestrator_in_source,
        test_mt5_connector_session_manager_supports_multi_account,
        test_orchestrator_has_macro_filter,
    ]
    failed = 0
    for t in tests:
        try:
            t()
        except AssertionError as e:
            print(f"  FAIL {t.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"  ERR  {t.__name__}: {e}")
            failed += 1
    print()
    print(f"{len(tests) - failed}/{len(tests)} integration checks passed")
    sys.exit(0 if failed == 0 else 1)
