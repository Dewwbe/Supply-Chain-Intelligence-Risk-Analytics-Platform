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
from src.kpi.summary import compute_kpi_summary

router = APIRouter(prefix="/kpis", tags=["kpis"])
settings = get_settings()


class KpiSummary(BaseModel):
    revenue_aed: float
    total_units_sold: int
    gross_margin_aed: float
    average_order_value_aed: float
    inventory_value_aed: float
    stockout_rate: float
    fill_rate: float
    supplier_otd: float
    average_lead_time_days: float
    inventory_turnover: float


def _compute_kpi_summary() -> KpiSummary:
    """Real warehouse-computed KPIs — see src/kpi/summary.py, the same
    ground-truth module the Power BI DAX measures and Excel workbook
    (Phase 10) are cross-checked against.
    """
    summary = compute_kpi_summary()
    return KpiSummary(
        revenue_aed=summary.total_revenue_aed,
        total_units_sold=summary.total_units_sold,
        gross_margin_aed=summary.gross_margin_aed,
        average_order_value_aed=summary.average_order_value_aed,
        inventory_value_aed=summary.inventory_value_aed,
        stockout_rate=summary.stockout_rate,
        fill_rate=summary.fill_rate,
        supplier_otd=summary.supplier_otd,
        average_lead_time_days=summary.average_lead_time_days,
        inventory_turnover=summary.inventory_turnover,
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
