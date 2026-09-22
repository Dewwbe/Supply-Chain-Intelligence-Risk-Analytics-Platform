"""FastAPI application entrypoint.

Run locally with: uvicorn src.api.main:app --reload
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from src.api.core.config import get_settings
from src.api.middleware.rate_limit import limiter
from src.api.routers import health, kpis, scenario
from src.common.logging import configure_logging, get_logger

settings = get_settings()
configure_logging(settings.log_level)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    logger.info("api_startup", environment=settings.environment)
    yield
    logger.info("api_shutdown")


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)

# Rate limiting wired at the app level, but individual routes opt in via
# @limiter.limit(...) — health/docs routes are unaffected.
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]  # slowapi's handler is typed for RateLimitExceeded specifically, narrower than Starlette's generic Exception signature
app.add_middleware(SlowAPIMiddleware)

app.include_router(health.router)
app.include_router(kpis.router, prefix=settings.api_v1_prefix)
app.include_router(scenario.router, prefix=settings.api_v1_prefix)
