"""Exception handlers that turn infrastructure failures into clear HTTP errors.

A warehouse that's down, not yet loaded, or unreachable is a 503 (the service
is temporarily unable to answer), not an opaque 500 with a stack trace — the
detail is logged server-side, never leaked to the client.
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from sqlalchemy.exc import SQLAlchemyError

from src.common.logging import get_logger

logger = get_logger(__name__)


async def warehouse_unavailable_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error(
        "warehouse_unavailable",
        path=request.url.path,
        error_type=type(exc).__name__,
        error=str(exc).splitlines()[0] if str(exc) else "",
    )
    return JSONResponse(
        status_code=503,
        content={"detail": "The analytics warehouse is unavailable. Try again shortly."},
    )


async def rate_limit_handler(request: Request, exc: Exception) -> JSONResponse:
    limit = exc.detail if isinstance(exc, RateLimitExceeded) else ""
    logger.warning("rate_limited", path=request.url.path, limit=limit)
    return JSONResponse(
        status_code=429,
        content={"detail": f"Rate limit exceeded: {limit}"},
        headers={"Retry-After": "60"},
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(SQLAlchemyError, warehouse_unavailable_handler)
    app.add_exception_handler(RateLimitExceeded, rate_limit_handler)
