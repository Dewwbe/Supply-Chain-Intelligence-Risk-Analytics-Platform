import math

import pytest
from src.api.routers.scenario import ScenarioRequest
from src.scenario_model.data import BaselineMetrics
from src.scenario_model.engine import _implied_safety_stock, run_scenario


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


def _no_change() -> ScenarioRequest:
    return ScenarioRequest(demand_change_pct=0, lead_time_change_pct=0, transport_cost_change_pct=0)


def test_zero_change_returns_baseline_shape():
    baseline = _synthetic_baseline()
    result = run_scenario(_no_change(), baseline=baseline)
    assert result.stockout_rate > 0
    assert 0 <= result.fill_rate <= 1
    assert result.projected_inventory_aed > 0


def test_zero_change_reproduces_the_real_baseline_stockout_rate():
    # The safety stock is calibrated specifically so that 0% change on every
    # parameter reproduces the real observed baseline — this is the model's
    # core correctness property, not an incidental one.
    baseline = _synthetic_baseline(stockout_rate=0.068)
    result = run_scenario(_no_change(), baseline=baseline)
    assert result.stockout_rate == pytest.approx(0.068, abs=0.001)
    assert result.baseline_stockout_rate == pytest.approx(0.068)


def test_higher_demand_increases_revenue_at_risk():
    baseline = _synthetic_baseline()
    base_result = run_scenario(_no_change(), baseline=baseline)
    stressed = run_scenario(
        ScenarioRequest(demand_change_pct=20, lead_time_change_pct=20, transport_cost_change_pct=0),
        baseline=baseline,
    )
    assert stressed.revenue_at_risk_aed >= base_result.revenue_at_risk_aed


def test_higher_demand_alone_increases_stockout_rate():
    # This is the bug the old hardcoded stub had backwards: it *divided* by
    # demand_factor, so higher demand looked safer. More demand pulling on
    # the same safety stock must increase stockout risk, not decrease it.
    baseline = _synthetic_baseline()
    base_result = run_scenario(_no_change(), baseline=baseline)
    higher_demand = run_scenario(
        ScenarioRequest(demand_change_pct=30, lead_time_change_pct=0, transport_cost_change_pct=0),
        baseline=baseline,
    )
    assert higher_demand.stockout_rate > base_result.stockout_rate


def test_longer_lead_time_alone_increases_stockout_rate():
    baseline = _synthetic_baseline()
    base_result = run_scenario(_no_change(), baseline=baseline)
    longer_lead_time = run_scenario(
        ScenarioRequest(demand_change_pct=0, lead_time_change_pct=50, transport_cost_change_pct=0),
        baseline=baseline,
    )
    assert longer_lead_time.stockout_rate > base_result.stockout_rate


def test_lower_demand_decreases_stockout_rate():
    baseline = _synthetic_baseline()
    base_result = run_scenario(_no_change(), baseline=baseline)
    lower_demand = run_scenario(
        ScenarioRequest(demand_change_pct=-20, lead_time_change_pct=0, transport_cost_change_pct=0),
        baseline=baseline,
    )
    assert lower_demand.stockout_rate < base_result.stockout_rate


def test_transport_cost_change_only_affects_transport_cost_not_stockout():
    baseline = _synthetic_baseline()
    base_result = run_scenario(_no_change(), baseline=baseline)
    cost_up = run_scenario(
        ScenarioRequest(demand_change_pct=0, lead_time_change_pct=0, transport_cost_change_pct=40),
        baseline=baseline,
    )
    assert cost_up.projected_transport_cost_aed > base_result.projected_transport_cost_aed
    assert cost_up.stockout_rate == pytest.approx(base_result.stockout_rate)


def test_result_includes_baseline_and_scenario_side_by_side():
    baseline = _synthetic_baseline()
    result = run_scenario(
        ScenarioRequest(demand_change_pct=10, lead_time_change_pct=0, transport_cost_change_pct=0),
        baseline=baseline,
    )
    assert result.baseline_inventory_aed == pytest.approx(baseline.inventory_value_aed)
    assert result.baseline_transport_cost_aed == pytest.approx(baseline.transport_cost_aed)
    assert result.projected_inventory_aed != result.baseline_inventory_aed


def test_stockout_and_fill_rate_are_complementary():
    baseline = _synthetic_baseline()
    result = run_scenario(
        ScenarioRequest(demand_change_pct=15, lead_time_change_pct=10, transport_cost_change_pct=0),
        baseline=baseline,
    )
    assert result.stockout_rate + result.fill_rate == pytest.approx(1.0)


def test_implied_safety_stock_handles_zero_std():
    baseline = _synthetic_baseline(daily_demand_std_units=0.0)
    safety_stock = _implied_safety_stock(baseline)
    assert safety_stock == baseline.avg_daily_demand_units * baseline.avg_lead_time_days


def test_extreme_stockout_rates_do_not_raise():
    # norm.ppf(1) / norm.ppf(0) are +/-inf; the clamp inside
    # _implied_safety_stock must keep this finite.
    for rate in (0.0, 1.0):
        baseline = _synthetic_baseline(stockout_rate=rate)
        safety_stock = _implied_safety_stock(baseline)
        assert math.isfinite(safety_stock)
