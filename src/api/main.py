"""FastAPI application entrypoint.

Run locally with: uvicorn src.api.main:app --reload
Interactive docs: http://localhost:8000/docs

Every analytics route is versioned under /api/v1. Rate limiting and caching
are applied per route, not globally — see middleware/rate_limit.py and
core/cache.py for which routes get which, and why.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI

from src.api.core.config import get_settings
from src.api.core.dependencies import require_loaded_warehouse
from src.api.core.errors import register_exception_handlers
from src.api.middleware.rate_limit import limiter
from src.api.middleware.request_logging import RequestLoggingMiddleware
from src.api.routers import anomalies, forecast, health, inventory, kpis, scenario, suppliers
from src.common.logging import configure_logging, get_logger

API_VERSION = "1.0.0"

settings = get_settings()
configure_logging(settings.log_level)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    logger.info(
        "api_startup",
        environment=settings.environment,
        version=API_VERSION,
        cache_backend=settings.cache_backend,
    )
    yield
    logger.info("api_shutdown")


app = FastAPI(
    title=settings.app_name,
    version=API_VERSION,
    description=(
        "Versioned REST API over the GulfMart supply chain warehouse: KPIs, supplier "
        "risk, inventory status, demand forecasts, anomalies and what-if scenarios."
    ),
    lifespan=lifespan,
)

app.state.limiter = limiter
register_exception_handlers(app)
app.add_middleware(RequestLoggingMiddleware)

app.include_router(health.router)
for router in (
    kpis.router,
    suppliers.router,
    inventory.router,
    forecast.router,
    anomalies.router,
    scenario.router,
):
    app.include_router(
        router,
        prefix=settings.api_v1_prefix,
        dependencies=[Depends(require_loaded_warehouse)],
    )
