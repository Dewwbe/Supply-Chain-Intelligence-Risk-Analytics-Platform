"""Anomaly endpoint.

Cached per domain: detection scans a domain's full history with 3 methods
(Isolation Forest included), and that history only changes after an ETL run.
Filters (severity, method, limit) are applied to the cached domain result,
so they never trigger a recompute. Rate-limited at the *expensive* tier,
since a cold cache for all 5 domains is a multi-second full-history scan.
"""

from enum import Enum
from functools import partial

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel

from src.anomaly_detection.service import METRICS, domain_anomalies
from src.api.core.cache import get_cache
from src.api.core.config import get_settings
from src.api.middleware.rate_limit import EXPENSIVE_LIMIT, limiter

router = APIRouter(prefix="/anomalies", tags=["anomalies"])
settings = get_settings()


class AnomalyMetric(str, Enum):
    """Must match anomaly_detection.data.DOMAINS (asserted in the unit tests)."""

    daily_sales = "daily_sales"
    inventory_change = "inventory_change"
    shipment_delay = "shipment_delay"
    transport_cost = "transport_cost"
    supplier_lead_time = "supplier_lead_time"


class Severity(str, Enum):
    any = "any"
    low = "Low"
    medium = "Medium"
    high = "High"


class Method(str, Enum):
    iqr = "IQR"
    zscore = "Z-Score"
    isolation_forest = "Isolation Forest"


class Anomaly(BaseModel):
    anomaly_id: str
    date: str
    entity: str
    metric: str
    method: str
    expected_value: float
    actual_value: float
    anomaly_score: float
    severity: str


class AnomalyPage(BaseModel):
    total_matching: int
    returned: int
    items: list[Anomaly]


@router.get("", response_model=AnomalyPage)
@limiter.limit(EXPENSIVE_LIMIT)
def anomalies(
    request: Request,
    metric: AnomalyMetric | None = Query(default=None, description="Domain; all 5 if omitted"),
    severity: Severity = Query(default=Severity.high, description="'any' for all"),
    method: Method | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
) -> AnomalyPage:
    """Flagged points across daily sales, inventory changes, shipment delays,
    transport costs and supplier lead times, highest anomaly score first.
    Defaults to High severity only — the rows worth a person's attention.
    """
    cache = get_cache()
    metrics = [metric.value] if metric is not None else list(METRICS)
    rows = [
        row
        for m in metrics
        for row in cache.get_or_compute(
            f"anomalies:{m}",
            settings.anomaly_cache_ttl_seconds,
            partial(domain_anomalies, m),
        )
    ]
    if severity is not Severity.any:
        rows = [r for r in rows if r["severity"] == severity.value]
    if method is not None:
        rows = [r for r in rows if r["method"] == method.value]
    rows.sort(key=lambda r: r["anomaly_score"], reverse=True)
    page = rows[:limit]
    return AnomalyPage(
        total_matching=len(rows), returned=len(page), items=[Anomaly(**r) for r in page]
    )
