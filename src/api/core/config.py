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

    # Caching (KPI / forecast endpoints only — see README "Software layer")
    cache_backend: str = Field(default="memory")  # "memory" | "redis"
    redis_url: str = Field(default="redis://localhost:6379/0")
    kpi_cache_ttl_seconds: int = Field(default=300)
    forecast_cache_ttl_seconds: int = Field(default=3600)

    # Rate limiting (applied to /api/v1/* only, not /health)
    rate_limit_default: str = Field(default="60/minute")

    # Outbound throttling for external data pulls (etl/extract/uae_open_data.py)
    external_api_rate_per_second: float = Field(default=2.0)

    log_level: str = Field(default="INFO")


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance (loaded once per process)."""
    return Settings()
