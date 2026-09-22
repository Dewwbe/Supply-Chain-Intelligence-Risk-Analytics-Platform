from src.api.routers.scenario import ScenarioRequest
from src.scenario_model.engine import run_scenario


def test_zero_change_returns_baseline_shape():
    payload = ScenarioRequest(
        demand_change_pct=0, lead_time_change_pct=0, transport_cost_change_pct=0
    )
    result = run_scenario(payload)
    assert result.stockout_rate > 0
    assert 0 <= result.fill_rate <= 1
    assert result.projected_inventory_aed > 0


def test_higher_demand_increases_revenue_at_risk():
    baseline = run_scenario(
        ScenarioRequest(demand_change_pct=0, lead_time_change_pct=0, transport_cost_change_pct=0)
    )
    stressed = run_scenario(
        ScenarioRequest(demand_change_pct=20, lead_time_change_pct=20, transport_cost_change_pct=0)
    )
    assert stressed.revenue_at_risk_aed >= baseline.revenue_at_risk_aed
