"""KPI endpoints.

Cached (see core/cache.py) because these read from the warehouse, which
refreshes once a day via Airflow — recomputing on every request is wasted
work. Rate-limited at the default tier (see middleware/rate_limit.py).
"""

from fastapi import APIRouter, Request
from pydantic import BaseModel

from src.api.core.cache import get_cache
from src.api.core.config import get_settings
from src.api.middleware.rate_limit import DEFAULT_LIMIT, limiter
from src.kpi.summary import compute_kpi_summary

router = APIRouter(prefix="/kpis", tags=["kpis"])
settings = get_settings()
CACHE_KEY = "kpi:summary"


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


@router.get("", response_model=KpiSummary, summary="Headline KPIs (all-time, network-wide)")
@router.get("/summary", response_model=KpiSummary, include_in_schema=False)
@limiter.limit(DEFAULT_LIMIT)
def kpi_summary(request: Request) -> KpiSummary:
    data = get_cache().get_or_compute(
        CACHE_KEY, settings.kpi_cache_ttl_seconds, lambda: _compute_kpi_summary().model_dump()
    )
    return KpiSummary(**data)
