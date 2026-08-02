from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    host: str = "0.0.0.0"
    port: int = 8040

    # M2Quant RSS feed URL for TGA/RRP data
    m2quant_url: str = "https://m2quant.com/rss/"

    # Cache TTL in seconds
    cache_ttl_seconds: int = 3600

    model_config = {"env_prefix": "MACRO_", "env_file": ".env", "extra": "ignore"}


settings = Settings()