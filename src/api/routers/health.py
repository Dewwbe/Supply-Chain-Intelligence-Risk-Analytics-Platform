"""Liveness and readiness endpoints. Deliberately exempt from rate limiting.

- `/health` — liveness: the process is up. Never touches a dependency, so a
  slow database can't make an orchestrator restart a healthy container.
- `/health/ready` — readiness: the warehouse answers *and is loaded*, and
  the cache backend is usable. Returns 503 until all are true — e.g. while
  Postgres starts, or on a fresh clone before the ETL has run.
"""

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from src.api.core.cache import get_cache
from src.api.core.dependencies import warehouse_is_loaded
from src.common.logging import get_logger

router = APIRouter(tags=["health"])
logger = get_logger(__name__)


class HealthResponse(BaseModel):
    status: str


class ReadinessResponse(BaseModel):
    status: str
    database: str
    cache: str


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get(
    "/health/ready",
    response_model=ReadinessResponse,
    responses={503: {"model": ReadinessResponse}},
)
def ready() -> JSONResponse:
    try:
        database = "ok" if warehouse_is_loaded() else "empty (run the ETL)"
    except Exception as exc:  # any failure means "not ready", whatever the driver raised
        logger.warning("readiness_database_failed", error=str(exc).splitlines()[0])
        database = "unavailable"

    cache = get_cache()
    cache_status = f"ok ({cache.backend})" if cache.ping() else f"unavailable ({cache.backend})"

    ok = database == "ok" and cache_status.startswith("ok")
    body = ReadinessResponse(
        status="ready" if ok else "not_ready", database=database, cache=cache_status
    )
    return JSONResponse(status_code=200 if ok else 503, content=body.model_dump())
