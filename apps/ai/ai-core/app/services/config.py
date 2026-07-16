"""Configuration loaded from environment variables."""
from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AI_CORE_", env_file=".env", extra="ignore")

    env: str = Field(default="development")
    port: int = Field(default=8200)
    log_level: str = Field(default="INFO")

    # ─── Postgres ─────────────────────────────────────────────────────────────
    postgres_host: str = Field(default="postgres")
    postgres_port: int = Field(default=5432)
    postgres_db: str = Field(default="tnsvt")
    postgres_user: str = Field(default="tnsvt")
    postgres_password: str = Field(default="tnsvt")
    postgres_schema: str = Field(default="ai")

    # ─── Redis ────────────────────────────────────────────────────────────────
    redis_host: str = Field(default="redis")
    redis_port: int = Field(default=6379)
    redis_password: str = Field(default="")
    redis_db: int = Field(default=3)

    # ─── NATS ─────────────────────────────────────────────────────────────────
    nats_url: str = Field(default="nats://nats:4222")
    nats_subject_in: str = Field(default="trading.signal.received")
    nats_subject_out: str = Field(default="trading.signal.scored")
    nats_stream: str = Field(default="TRADING_SIGNALS")
    nats_consumer: str = Field(default="ai-core-scorer")

    # ─── Ollama ───────────────────────────────────────────────────────────────
    ollama_url: str = Field(default="http://ollama:11434")
    ollama_model: str = Field(default="llama3.2:3b")
    ollama_timeout_sec: float = Field(default=10.0)
    ollama_enabled: bool = Field(default=True)

    # ─── Scoring ──────────────────────────────────────────────────────────────
    score_execute_threshold: float = Field(default=70.0)
    score_monitor_threshold: float = Field(default=50.0)
    score_min_confidence: float = Field(default=0.40)

    def postgres_dsn(self) -> str:
        return f"postgresql://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"

    def redis_url(self) -> str:
        auth = f":{self.redis_password}@" if self.redis_password else ""
        return f"redis://{auth}{self.redis_host}:{self.redis_port}/{self.redis_db}"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()