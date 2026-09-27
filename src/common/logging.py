"""Structured logging configuration shared by the API, ETL and Airflow tasks.

Every log line is one JSON object on stdout, including lines from libraries
that use the standard `logging` module (uvicorn, SQLAlchemy): they're routed
through the same structlog processors, so a log aggregator never has to parse
two formats. Nothing in `src/` or `etl/` uses print() (enforced by ruff's T20
rule in pyproject.toml).
"""

from __future__ import annotations

import logging
import sys
from typing import Any, cast

import structlog

_SHARED_PROCESSORS: list[Any] = [
    structlog.contextvars.merge_contextvars,
    structlog.stdlib.add_log_level,
    structlog.stdlib.add_logger_name,
    structlog.processors.TimeStamper(fmt="iso", utc=True),
    structlog.processors.StackInfoRenderer(),
]


class _StdoutHandler(logging.StreamHandler):  # type: ignore[type-arg]
    """Writes to whatever `sys.stdout` is at emit time, not at creation time,
    so a replaced stdout (test capture, a redirecting supervisor) never leaves
    the handler holding a closed stream."""

    @property
    def stream(self) -> Any:
        return sys.stdout

    @stream.setter
    def stream(self, _value: Any) -> None:
        pass


def configure_logging(level: str = "INFO") -> None:
    """Emit JSON lines for structlog and stdlib loggers alike.

    Called once at process start (API startup, ETL entrypoint, DAG init).
    Safe to call again: handlers are replaced, not duplicated.
    """
    log_level = getattr(logging, level.upper(), logging.INFO)

    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            *_SHARED_PROCESSORS,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=_SHARED_PROCESSORS,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
    )
    handler = _StdoutHandler()
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(log_level)

    # uvicorn installs its own plain-text handlers; hand its records to the
    # root JSON handler instead. Its access log is disabled because the API's
    # request-logging middleware already emits one richer line per request.
    for name in ("uvicorn", "uvicorn.error"):
        uvicorn_logger = logging.getLogger(name)
        uvicorn_logger.handlers = []
        uvicorn_logger.propagate = True
    logging.getLogger("uvicorn.access").disabled = True


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Return a named structured logger."""
    return cast(structlog.stdlib.BoundLogger, structlog.get_logger(name))
