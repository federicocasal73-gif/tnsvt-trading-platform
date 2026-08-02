from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "liquidity-engine"
    host: str = "0.0.0.0"
    port: int = 8050

    nats_url: str = "nats://localhost:4222"
    nats_stream: str = "tnsvt"
    nats_subject_lst: str = "tnsvt.lst.signal"

    mt5_connector_url: str = "http://localhost:8007"
    symbols: list[str] = ["XAUUSD"]
    timeframes: list[str] = ["M1", "M5", "M15"]

    lst_interval_seconds: int = 60

    model_config = {"env_prefix": "LST_", "env_file": ".env"}
