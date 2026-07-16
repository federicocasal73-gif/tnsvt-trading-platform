"""Configuration loaded from environment variables."""
from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="REGIME_DETECTOR_", env_file=".env", extra="ignore")

    env: str = Field(default="development")
    port: int = Field(default=8201)
    log_level: str = Field(default="INFO")

    # ─── Postgres ─────────────────────────────────────────────────────────
    postgres_host: str = Field(default="postgres")
    postgres_port: int = Field(default=5432)
    postgres_db: str = Field(default="tnsvt")
    postgres_user: str = Field(default="tnsvt")
    postgres_password: str = Field(default="tnsvt")
    postgres_schema: str = Field(default="ai")

    # ─── Redis ─────────────────────────────────────────────────────────────
    redis_host: str = Field(default="redis")
    redis_port: int = Field(default=6379)
    redis_password: str = Field(default="")
    redis_db: int = Field(default=4)

    # ─── NATS ──────────────────────────────────────────────────────────────
    nats_url: str = Field(default="nats://nats:4222")
    nats_subject_in: str = Field(default="marketdata.tick.*")
    nats_subject_out: str = Field(default="ai.regime.snapshot")
    nats_stream: str = Field(default="MARKETDATA")
    nats_consumer: str = Field(default="regime-detector")

    # ─── Classification ──────────────────────────────────────────────────
    min_closes_required: int = Field(default=30)
    publish_on_change_only: bool = Field(default=True)
    min_dwell_updates: int = Field(default=3)
    transition_threshold: float = Field(default=0.20)
    classify_interval_sec: float = Field(default=5.0)

    def postgres_dsn(self) -> str:
        return f"postgresql://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"

    def redis_url(self) -> str:
        auth = f":{self.redis_password}@" if self.redis_password else ""
        return f"redis://{auth}{self.redis_host}:{self.redis_port}/{self.redis_db}"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()