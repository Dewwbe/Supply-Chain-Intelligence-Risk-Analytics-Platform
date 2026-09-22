"""KPI endpoints.

Cached (see core/cache.py) because these read from the warehouse, which
refreshes once a day via Airflow — recomputing on every request is wasted
work. Rate-limited because they're part of /api/v1/* (see middleware/rate_limit.py).
"""

from fastapi import APIRouter, Request
from pydantic import BaseModel

from src.api.core.cache import get_cache
from src.api.core.config import get_settings
from src.api.middleware.rate_limit import limiter

router = APIRouter(prefix="/kpis", tags=["kpis"])
settings = get_settings()


class KpiSummary(BaseModel):
    revenue_aed: float
    gross_margin_aed: float
    stockout_rate: float
    fill_rate: float
    supplier_otd: float


def _compute_kpi_summary() -> KpiSummary:
    """Placeholder for the real warehouse query.

    In the finished project this executes the query in
    sql/07_kpi/executive_summary.sql against the analytics schema.
    """
    return KpiSummary(
        revenue_aed=0.0,
        gross_margin_aed=0.0,
        stockout_rate=0.0,
        fill_rate=0.0,
        supplier_otd=0.0,
    )


@router.get("/summary", response_model=KpiSummary)
@limiter.limit(settings.rate_limit_default)
def kpi_summary(request: Request) -> KpiSummary:
    cache = get_cache()
    cached = cache.get("kpi:summary")
    if cached is not None:
        return KpiSummary(**cached)

    result = _compute_kpi_summary()
    cache.set("kpi:summary", result.model_dump(), settings.kpi_cache_ttl_seconds)
    return result
