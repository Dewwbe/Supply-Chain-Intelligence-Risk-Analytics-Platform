"""Shared route dependencies.

`require_loaded_warehouse` guards every analytics router: on a fresh clone
the stack is up before the ETL has run, and the KPI/risk/forecast code would
otherwise fail on empty tables with an opaque 500. A positive answer is
cached (the warehouse doesn't un-load itself), so the check costs one query
per cache TTL, not one per request.
"""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import text

from src.api.core.cache import get_cache
from src.api.core.config import get_settings
from src.common.db import get_engine

CACHE_KEY = "warehouse:loaded"
NOT_LOADED_DETAIL = (
    "The warehouse is empty. Load it with `python -m etl.run_local` (see setup.md), then retry."
)


def warehouse_is_loaded() -> bool:
    with get_engine().connect() as conn:
        return bool(
            conn.execute(text("SELECT EXISTS (SELECT 1 FROM warehouse.fact_sales)")).scalar()
        )


def require_loaded_warehouse() -> None:
    cache = get_cache()
    if cache.get(CACHE_KEY):
        return
    if not warehouse_is_loaded():
        raise HTTPException(status_code=503, detail=NOT_LOADED_DETAIL)
    cache.set(CACHE_KEY, True, get_settings().kpi_cache_ttl_seconds)
