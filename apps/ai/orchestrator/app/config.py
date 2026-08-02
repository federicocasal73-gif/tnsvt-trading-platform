from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "orchestrator"
    host: str = "0.0.0.0"
    port: int = 8060

    nats_url: str = "nats://localhost:4222"
    nats_stream: str = "tnsvt"
    nats_subject_in: str = "tnsvt.lst.signal"
    nats_subject_out: str = "trading.signal.validated"

    tenant_id: str = "00000000-0000-0000-0000-000000000001"

    mt5_connector_url: str = "http://localhost:8007"

    symbols: list[str] = ["XAUUSD", "EURUSD", "GBPUSD", "USDCHF"]
    timeframes: list[str] = ["M15", "H1", "H4"]

    poll_interval_seconds: int = 30
    history_window: int = 100

    correlation_threshold: float = 0.7
    coint_enabled: bool = True

    account_balance: float = 10000.0
    risk_per_trade: float = 0.01
    max_drawdown: float = 0.15
    max_positions: int = 3

    atr_period: int = 14
    sl_atr_multiplier: float = 1.5
    tp_atr_multiplier: float = 2.5

    model_config = {"env_prefix": "ORCH_", "env_file": ".env"}