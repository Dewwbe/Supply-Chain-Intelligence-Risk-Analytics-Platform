"""Scenario simulation engine (Phase 10 of the implementation plan).

This is a stub that defines the contract; the real version replaces
`_baseline()` with a warehouse query and applies the percentage deltas to
inventory requirement, transport cost, stockout probability and fill rate
using the relationships derived in notebooks/09_scenario_analysis.ipynb.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.api.routers.scenario import ScenarioRequest, ScenarioResult


def _baseline() -> dict[str, float]:
    """Placeholder baseline figures; replace with a warehouse query."""
    return {
        "inventory_aed": 7_800_000.0,
        "transport_cost_aed": 1_200_000.0,
        "stockout_rate": 0.068,
        "fill_rate": 0.942,
        "revenue_aed": 42_000_000.0,
    }


def run_scenario(payload: ScenarioRequest) -> ScenarioResult:
    from src.api.routers.scenario import ScenarioResult

    base = _baseline()
    demand_factor = 1 + payload.demand_change_pct / 100
    lead_time_factor = 1 + payload.lead_time_change_pct / 100
    cost_factor = 1 + payload.transport_cost_change_pct / 100

    projected_inventory = base["inventory_aed"] * demand_factor * lead_time_factor
    projected_transport_cost = base["transport_cost_aed"] * cost_factor * demand_factor
    stockout_rate = min(0.99, base["stockout_rate"] * lead_time_factor / demand_factor)
    fill_rate = max(0.0, 1 - stockout_rate)
    revenue_at_risk = base["revenue_aed"] * stockout_rate

    return ScenarioResult(
        projected_inventory_aed=round(projected_inventory, 2),
        projected_transport_cost_aed=round(projected_transport_cost, 2),
        stockout_rate=round(stockout_rate, 4),
        fill_rate=round(fill_rate, 4),
        revenue_at_risk_aed=round(revenue_at_risk, 2),
    )
