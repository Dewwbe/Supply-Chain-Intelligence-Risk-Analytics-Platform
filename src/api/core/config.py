"""Centralized application configuration.

All environment-dependent values are read here, once, via pydantic's
BaseSettings. Nothing else in the codebase should call os.environ directly.
"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings, populated from environment variables / .env."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "GulfMart Supply Chain Intelligence API"
    environment: str = Field(default="development")
    api_v1_prefix: str = "/api/v1"

    database_url: str = Field(
        default="postgresql+psycopg://gulfmart:gulfmart@localhost:5432/gulfmart_analytics"
    )

    # Caching — warehouse-backed reads only, never per-request what-if
    # results (see README "Rate limiting, caching, throttling").
    cache_backend: str = Field(default="memory")  # "memory" | "redis"
    redis_url: str = Field(default="redis://localhost:6379/0")
    kpi_cache_ttl_seconds: int = Field(default=300)
    forecast_cache_ttl_seconds: int = Field(default=3600)
    anomaly_cache_ttl_seconds: int = Field(default=3600)

    # Rate limiting — per route, /api/v1/* only; /health is never limited.
    rate_limit_default: str = Field(default="60/minute")
    # Routes whose cache miss runs a model fit or a full-history scan.
    rate_limit_expensive: str = Field(default="10/minute")

    # Outbound throttling for external data pulls (etl/extract/uae_open_data.py)
    external_api_rate_per_second: float = Field(default=2.0)

    log_level: str = Field(default="INFO")

    # Kaggle credentials for etl/extract/download_raw.py (optional here: the
    # CLI also accepts ~/.kaggle/kaggle.json or real environment variables).
    kaggle_username: str = Field(default="")
    kaggle_key: str = Field(default="")


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance (loaded once per process)."""
    return Settings()
