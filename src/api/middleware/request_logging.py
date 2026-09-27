"""One structured log line per request, with a request ID for correlation.

The ID comes from the caller's `X-Request-ID` header when present (so a
gateway's trace ID carries through), otherwise a new one is generated; it's
echoed back on the response and bound into every log line emitted while the
request is being handled.
"""

from __future__ import annotations

import time
import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from src.common.logging import get_logger

logger = get_logger("src.api.access")
REQUEST_ID_HEADER = "X-Request-ID"


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get(REQUEST_ID_HEADER) or uuid.uuid4().hex
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)

        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            logger.exception(
                "request_failed",
                method=request.method,
                path=request.url.path,
                duration_ms=round((time.perf_counter() - start) * 1000, 1),
            )
            raise
        response.headers[REQUEST_ID_HEADER] = request_id
        logger.info(
            "request",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=round((time.perf_counter() - start) * 1000, 1),
            client=request.client.host if request.client else None,
        )
        return response
