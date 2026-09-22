"""Structured logging configuration shared by the API, ETL and Airflow tasks."""

import logging
import sys
from typing import cast

import structlog


def configure_logging(level: str = "INFO") -> None:
    """Configure structlog + stdlib logging to emit JSON lines.

    Called once at process start (API startup, ETL entrypoint, DAG init).
    """
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, level.upper(), logging.INFO),
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper(), logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Return a named structured logger."""
    return cast(structlog.stdlib.BoundLogger, structlog.get_logger(name))
