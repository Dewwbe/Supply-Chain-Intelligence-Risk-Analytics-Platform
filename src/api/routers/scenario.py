"""Scenario simulation endpoint.

Deliberately NOT cached — each call is a distinct what-if calculation
(different demand/lead-time/cost inputs), so caching would return stale or
wrong answers. Still rate-limited as part of /api/v1/*.
"""

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from src.api.core.config import get_settings
from src.api.middleware.rate_limit import limiter

router = APIRouter(prefix="/scenario", tags=["scenario"])
settings = get_settings()


class ScenarioRequest(BaseModel):
    demand_change_pct: float = Field(ge=-20, le=30)
    lead_time_change_pct: float = Field(ge=-30, le=50)
    transport_cost_change_pct: float = Field(ge=-20, le=40)


class ScenarioResult(BaseModel):
    """Baseline vs. scenario, side by side — every `baseline_*` field is the
    real current warehouse figure (src/scenario_model/data.py); every other
    field is what the model projects under the requested change.
    """

    baseline_inventory_aed: float
    projected_inventory_aed: float
    baseline_transport_cost_aed: float
    projected_transport_cost_aed: float
    baseline_stockout_rate: float
    stockout_rate: float
    baseline_fill_rate: float
    fill_rate: float
    baseline_revenue_at_risk_aed: float
    revenue_at_risk_aed: float


@router.post("/simulate", response_model=ScenarioResult)
@limiter.limit(settings.rate_limit_default)
def simulate(request: Request, payload: ScenarioRequest) -> ScenarioResult:
    """Run the baseline-vs-scenario calculation.

    Loads the real baseline from the warehouse (src/scenario_model/data.py)
    and applies the requested deltas through the statistical model in
    src/scenario_model/engine.py — every number returned is produced by
    that model, never hardcoded here.
    """
    from src.scenario_model.engine import run_scenario

    return run_scenario(payload)
