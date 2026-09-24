"""Scenario simulation engine (Phase 9).

Every output is produced from `BaselineMetrics` (real warehouse data, see
`data.py`) run through an explicit statistical model — nothing here is a
hardcoded report number.

**The model**: demand during the lead-time window is treated as
approximately normal, mean = avg_daily_demand * lead_time,
std = daily_demand_std * sqrt(lead_time) (the standard result for summing
`lead_time` roughly-independent daily demands). Stock-out happens when that
demand exceeds the stock on hand at the reorder point ("safety stock").
Rather than guessing a safety-stock number, it's *calibrated* from the real
observed baseline stockout rate: the safety stock is whatever value would
make this same formula reproduce the real current stockout rate at 0%
change on every parameter. A scenario then asks "if demand/lead-time
change but the safety stock policy doesn't, what stockout rate follows?" —
holding the policy fixed is what makes this a scenario about the inputs,
not a silent policy change.

Transport cost and inventory value scale with volume (`demand_factor`) and
their own direct lever (`cost_factor`/`lead_time_factor`) — see inline
comments for why each uses the factors it does.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from scipy.stats import norm

from src.scenario_model.data import BaselineMetrics, load_baseline

if TYPE_CHECKING:
    from src.api.routers.scenario import ScenarioRequest, ScenarioResult


def _implied_safety_stock(baseline: BaselineMetrics) -> float:
    """The stock-on-hand level (in units) that reproduces the real observed
    stockout rate under baseline demand/lead-time — see module docstring.
    """
    mean = baseline.avg_daily_demand_units * baseline.avg_lead_time_days
    std = baseline.daily_demand_std_units * math.sqrt(max(baseline.avg_lead_time_days, 0))
    if std <= 0:
        return mean
    rate = min(max(baseline.stockout_rate, 1e-4), 1 - 1e-4)  # keep ppf finite at the extremes
    z = norm.ppf(1 - rate)
    return float(mean + z * std)


def run_scenario(
    payload: ScenarioRequest, baseline: BaselineMetrics | None = None
) -> ScenarioResult:
    """Baseline vs scenario, side by side — see `ScenarioResult`."""
    from src.api.routers.scenario import ScenarioResult

    baseline = baseline if baseline is not None else load_baseline()

    demand_factor = 1 + payload.demand_change_pct / 100
    lead_time_factor = 1 + payload.lead_time_change_pct / 100
    cost_factor = 1 + payload.transport_cost_change_pct / 100

    safety_stock = _implied_safety_stock(baseline)
    scenario_mean = (
        baseline.avg_daily_demand_units
        * demand_factor
        * (baseline.avg_lead_time_days * lead_time_factor)
    )
    scenario_std = (
        baseline.daily_demand_std_units
        * demand_factor
        * math.sqrt(max(baseline.avg_lead_time_days * lead_time_factor, 0))
    )

    if scenario_std > 0:
        stockout_rate = 1 - norm.cdf(safety_stock, loc=scenario_mean, scale=scenario_std)
    else:
        stockout_rate = 0.0 if safety_stock >= scenario_mean else 1.0
    stockout_rate = min(max(float(stockout_rate), 0.0), 1.0)
    fill_rate = 1 - stockout_rate

    # More demand + a longer lead-time window both require holding more
    # stock to cover the same exposure; transport cost scales with the
    # shipped volume (demand_factor) and its own rate lever (cost_factor).
    projected_inventory = baseline.inventory_value_aed * demand_factor * lead_time_factor
    projected_transport_cost = baseline.transport_cost_aed * demand_factor * cost_factor
    projected_revenue = baseline.revenue_aed * demand_factor
    revenue_at_risk = projected_revenue * stockout_rate

    baseline_fill_rate = 1 - baseline.stockout_rate
    baseline_revenue_at_risk = baseline.revenue_aed * baseline.stockout_rate

    return ScenarioResult(
        baseline_inventory_aed=round(baseline.inventory_value_aed, 2),
        projected_inventory_aed=round(projected_inventory, 2),
        baseline_transport_cost_aed=round(baseline.transport_cost_aed, 2),
        projected_transport_cost_aed=round(projected_transport_cost, 2),
        baseline_stockout_rate=round(baseline.stockout_rate, 4),
        stockout_rate=round(stockout_rate, 4),
        baseline_fill_rate=round(baseline_fill_rate, 4),
        fill_rate=round(fill_rate, 4),
        baseline_revenue_at_risk_aed=round(baseline_revenue_at_risk, 2),
        revenue_at_risk_aed=round(revenue_at_risk, 2),
    )
