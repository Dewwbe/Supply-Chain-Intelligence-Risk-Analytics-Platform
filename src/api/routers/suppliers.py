"""Supplier risk endpoint.

Cached: scoring loads the full shipment, purchase-order and returns history
(~220k rows) to produce 11 rows that only change after an ETL run.
Rate-limited at the default tier.
"""

from fastapi import APIRouter, Request
from pydantic import BaseModel

from src.api.core.cache import get_cache
from src.api.core.config import get_settings
from src.api.middleware.rate_limit import DEFAULT_LIMIT, limiter
from src.supplier_risk.service import supplier_risk_report

router = APIRouter(prefix="/suppliers", tags=["suppliers"])
settings = get_settings()
CACHE_KEY = "suppliers:risk"


class SupplierRisk(BaseModel):
    supplier: str
    risk_score: float
    risk_level: str
    shipment_count: int
    on_time_rate: float
    average_lead_time_days: float
    lead_time_std_days: float
    po_count: int
    cancellation_rate: float
    cost_variability: float
    defect_rate: float


class SupplierRiskReport(BaseModel):
    weights: dict[str, float]
    suppliers: list[SupplierRisk]


@router.get("/risk", response_model=SupplierRiskReport)
@limiter.limit(DEFAULT_LIMIT)
def supplier_risk(request: Request) -> SupplierRiskReport:
    """Risk score (0-100) and level per supplier, riskiest first, with the
    metrics behind each score. Scores are min-max normalised across the
    current supplier base, so "High" means worst-in-group, not an absolute bar.
    """
    data = get_cache().get_or_compute(
        CACHE_KEY, settings.kpi_cache_ttl_seconds, supplier_risk_report
    )
    return SupplierRiskReport(**data)
