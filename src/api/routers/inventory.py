"""Inventory status endpoint.

Cached: one aggregate query over ~180k inventory rows joined to daily sales
demand, answering with 6 rows that only change after an ETL run.
Rate-limited at the default tier.
"""

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from src.api.core.cache import get_cache
from src.api.core.config import get_settings
from src.api.middleware.rate_limit import DEFAULT_LIMIT, limiter
from src.kpi.inventory import compute_inventory_status

router = APIRouter(prefix="/inventory", tags=["inventory"])
settings = get_settings()
CACHE_KEY = "inventory:status"


class InventoryStatus(BaseModel):
    warehouse: str
    products_tracked: int
    products_out_of_stock: int
    inventory_value_aed: float
    stockout_rate: float
    fill_rate: float


class InventoryReport(BaseModel):
    network: InventoryStatus
    warehouses: list[InventoryStatus]


@router.get("", response_model=InventoryReport)
@limiter.limit(DEFAULT_LIMIT)
def inventory_status(
    request: Request,
    warehouse: str | None = Query(
        default=None, description="Exact warehouse name, e.g. 'Dubai Distribution Center'"
    ),
) -> InventoryReport:
    """Network-wide and per-warehouse stockout rate, fill rate, current
    inventory value, and how many tracked products are out of stock today.
    """
    report = InventoryReport(
        **get_cache().get_or_compute(
            CACHE_KEY, settings.kpi_cache_ttl_seconds, compute_inventory_status
        )
    )
    if warehouse is None:
        return report
    matches = [w for w in report.warehouses if w.warehouse.lower() == warehouse.lower()]
    if not matches:
        known = ", ".join(w.warehouse for w in report.warehouses)
        raise HTTPException(404, f"Unknown warehouse '{warehouse}'. Known: {known}")
    return InventoryReport(network=report.network, warehouses=matches)
