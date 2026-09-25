"""Verifies that the *composed* DAX scenario formulas in
powerbi/dax_measures.dax (Implied Safety Stock, Scenario Stockout Rate)
reproduce src/scenario_model/engine.py's output exactly, not just that
their underlying normal-distribution approximations are individually
accurate (see test_dax_normal_approximations.py for that). Each function
below is a literal transcription of its DAX measure, using the verified
Acklam/Zelen-Severo approximations, so a passing test here is evidence the
DAX measures — as actually composed — match the Python engine, not just
that the ingredients are each fine in isolation.
"""

from __future__ import annotations

import pytest
from src.api.routers.scenario import ScenarioRequest
from src.scenario_model.data import BaselineMetrics
from src.scenario_model.engine import _implied_safety_stock, run_scenario
from tests.unit.test_dax_normal_approximations import acklam_norm_sinv, zelen_severo_norm_sdist


def _synthetic_baseline(**overrides) -> BaselineMetrics:
    defaults = {
        "avg_daily_demand_units": 500.0,
        "daily_demand_std_units": 80.0,
        "avg_lead_time_days": 4.0,
        "stockout_rate": 0.068,
        "inventory_value_aed": 7_800_000.0,
        "transport_cost_aed": 1_200_000.0,
        "revenue_aed": 42_000_000.0,
    }
    defaults.update(overrides)
    return BaselineMetrics(**defaults)


def dax_implied_safety_stock(baseline: BaselineMetrics) -> float:
    """Transcription of the `Implied Safety Stock` DAX measure."""
    mean = baseline.avg_daily_demand_units * baseline.avg_lead_time_days
    std = baseline.daily_demand_std_units * baseline.avg_lead_time_days**0.5
    rate = min(max(baseline.stockout_rate, 0.0001), 0.9999)
    p = 1 - rate
    z = acklam_norm_sinv(p)
    return mean + z * std


def dax_scenario_stockout_rate(
    baseline: BaselineMetrics, demand_change_pct: float, lead_time_change_pct: float
) -> float:
    """Transcription of the `Scenario Stockout Rate` DAX measure."""
    demand_factor = 1 + demand_change_pct / 100
    lead_time_factor = 1 + lead_time_change_pct / 100
    scenario_mean = (
        baseline.avg_daily_demand_units
        * demand_factor
        * (baseline.avg_lead_time_days * lead_time_factor)
    )
    scenario_std = (
        baseline.daily_demand_std_units
        * demand_factor
        * (baseline.avg_lead_time_days * lead_time_factor) ** 0.5
    )
    safety_stock = dax_implied_safety_stock(baseline)
    if scenario_std <= 0:
        return 0.0 if safety_stock >= scenario_mean else 1.0
    z = (safety_stock - scenario_mean) / scenario_std
    phi = zelen_severo_norm_sdist(z)
    return min(max(1 - phi, 0.0), 1.0)


@pytest.mark.parametrize("stockout_rate", [0.01, 0.068, 0.14, 0.3, 0.5])
def test_dax_implied_safety_stock_matches_engine(stockout_rate):
    baseline = _synthetic_baseline(stockout_rate=stockout_rate)
    assert dax_implied_safety_stock(baseline) == pytest.approx(
        _implied_safety_stock(baseline), abs=1e-6
    )


@pytest.mark.parametrize(
    "demand_pct,lead_time_pct,cost_pct",
    [
        (0, 0, 0),
        (10, 0, 0),
        (30, 0, 0),
        (-20, 0, 0),
        (0, 50, 0),
        (0, -30, 0),
        (0, 0, 40),
        (30, 50, 40),
        (-20, -30, -20),
    ],
)
def test_dax_scenario_stockout_rate_matches_engine(demand_pct, lead_time_pct, cost_pct):
    baseline = _synthetic_baseline()
    payload = ScenarioRequest(
        demand_change_pct=demand_pct,
        lead_time_change_pct=lead_time_pct,
        transport_cost_change_pct=cost_pct,
    )
    engine_result = run_scenario(payload, baseline=baseline)
    dax_result = dax_scenario_stockout_rate(baseline, demand_pct, lead_time_pct)
    assert dax_result == pytest.approx(engine_result.stockout_rate, abs=1e-3)
