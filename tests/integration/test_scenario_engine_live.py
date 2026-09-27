"""Integration test for the scenario engine's real-data path — needs a
running Postgres with the warehouse populated (`make db-up && make etl`).
Skipped otherwise, per docs/coding_standards.md.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text
from src.api.routers.scenario import ScenarioRequest
from src.common.db import get_engine
from src.scenario_model.data import load_baseline
from src.scenario_model.engine import run_scenario


def _db_available() -> bool:
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _db_available(), reason="Postgres not reachable")


def test_load_baseline_returns_sane_real_values():
    baseline = load_baseline()
    assert baseline.avg_daily_demand_units > 0
    assert baseline.avg_lead_time_days > 0
    assert 0 <= baseline.stockout_rate <= 1
    assert baseline.inventory_value_aed > 0
    assert baseline.revenue_aed > 0


def test_run_scenario_end_to_end_against_real_baseline():
    payload = ScenarioRequest(
        demand_change_pct=15, lead_time_change_pct=10, transport_cost_change_pct=-5
    )
    result = run_scenario(payload)  # no injected baseline -> hits the real DB
    assert result.baseline_inventory_aed > 0
    assert result.projected_inventory_aed > result.baseline_inventory_aed
    assert 0 <= result.stockout_rate <= 1


def test_scenario_endpoint_returns_baseline_and_scenario(client):
    response = client.post(
        "/api/v1/scenario/simulate",
        json={"demand_change_pct": 10, "lead_time_change_pct": 0, "transport_cost_change_pct": 0},
    )
    assert response.status_code == 200
    body = response.json()
    for field in [
        "baseline_inventory_aed",
        "projected_inventory_aed",
        "baseline_stockout_rate",
        "stockout_rate",
        "baseline_fill_rate",
        "fill_rate",
        "baseline_revenue_at_risk_aed",
        "revenue_at_risk_aed",
    ]:
        assert field in body


def test_scenario_endpoint_rejects_out_of_range_parameters(client):
    response = client.post(
        "/api/v1/scenario/simulate",
        json={"demand_change_pct": 999, "lead_time_change_pct": 0, "transport_cost_change_pct": 0},
    )
    assert response.status_code == 422
