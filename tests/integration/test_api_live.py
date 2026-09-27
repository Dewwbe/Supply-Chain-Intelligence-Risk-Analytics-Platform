"""Every /api/v1 route end to end against the real, loaded warehouse.

Asserts cross-endpoint consistency rather than exact figures, so the tests
stay valid after an ETL re-run: the inventory route and the KPI route must
agree on the same network totals, because both implement the same
docs/kpi_dictionary.md definitions against the same tables.
"""

import pytest

pytestmark = pytest.mark.warehouse


def test_inventory_network_totals_match_the_headline_kpis(client):
    kpis = client.get("/api/v1/kpis").json()
    network = client.get("/api/v1/inventory").json()["network"]
    assert network["inventory_value_aed"] == pytest.approx(kpis["inventory_value_aed"], abs=0.01)
    assert network["stockout_rate"] == pytest.approx(kpis["stockout_rate"], abs=1e-4)
    assert network["fill_rate"] == pytest.approx(kpis["fill_rate"], abs=1e-4)


def test_supplier_risk_lists_every_supplier_riskiest_first(client):
    suppliers = client.get("/api/v1/suppliers/risk").json()["suppliers"]
    scores = [s["risk_score"] for s in suppliers]
    assert len(suppliers) >= 2
    assert scores == sorted(scores, reverse=True)
    assert all(s["risk_level"] in {"Low", "Medium", "High", "Critical"} for s in suppliers)


def test_forecast_for_the_top_product(client):
    product = client.get("/api/v1/forecast/products", params={"limit": 1}).json()[0]
    body = client.get(
        "/api/v1/forecast", params={"product_id": product["product_id"], "horizon": 4}
    ).json()
    assert len(body["points"]) == 4
    assert all(p["lower"] <= p["forecast"] <= p["upper"] for p in body["points"])


def test_anomalies_for_one_domain(client):
    body = client.get(
        "/api/v1/anomalies", params={"metric": "daily_sales", "severity": "any", "limit": 5}
    ).json()
    assert body["returned"] == min(5, body["total_matching"])
    assert all(item["metric"] == "daily_sales" for item in body["items"])


def test_zero_change_scenario_reproduces_the_baseline(client):
    body = client.post(
        "/api/v1/scenario/simulate",
        json={"demand_change_pct": 0, "lead_time_change_pct": 0, "transport_cost_change_pct": 0},
    ).json()
    assert body["stockout_rate"] == pytest.approx(body["baseline_stockout_rate"], abs=1e-4)
    assert body["projected_inventory_aed"] == pytest.approx(body["baseline_inventory_aed"])


def test_readiness_reports_ready(client):
    assert client.get("/health/ready").json()["database"] == "ok"
