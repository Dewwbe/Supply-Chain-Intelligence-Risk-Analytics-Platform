"""Scenario simulation endpoint.

The scenario *result* is deliberately NOT cached — each call is a distinct
what-if calculation, so a cached answer would be wrong for the next inputs.
The *baseline* it's measured against IS cached: it's 5 warehouse queries
that return the same numbers until the next ETL run, and without caching
every slider movement in a client would repeat them. Rate-limited at the
default tier.
"""

from dataclasses import asdict

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from src.api.core.cache import get_cache
from src.api.core.config import get_settings
from src.api.middleware.rate_limit import DEFAULT_LIMIT, limiter

router = APIRouter(prefix="/scenario", tags=["scenario"])
settings = get_settings()
BASELINE_CACHE_KEY = "scenario:baseline"


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
@limiter.limit(DEFAULT_LIMIT)
def simulate(request: Request, payload: ScenarioRequest) -> ScenarioResult:
    """Run the baseline-vs-scenario calculation.

    Applies the requested deltas to the real warehouse baseline
    (src/scenario_model/data.py) through the statistical model in
    src/scenario_model/engine.py — every number returned is produced by
    that model, never hardcoded here.
    """
    from src.scenario_model.data import BaselineMetrics, load_baseline
    from src.scenario_model.engine import run_scenario

    baseline = get_cache().get_or_compute(
        BASELINE_CACHE_KEY, settings.kpi_cache_ttl_seconds, lambda: asdict(load_baseline())
    )
    return run_scenario(payload, BaselineMetrics(**baseline))
