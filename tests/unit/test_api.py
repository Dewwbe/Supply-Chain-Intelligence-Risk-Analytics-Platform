"""API behaviour with the warehouse-backed services stubbed out.

Covers what each route returns, which routes cache and which deliberately
don't, rate-limit tiers (and /health's exemption), error mapping, and the
request-ID header. Real-warehouse behaviour is in tests/integration.
"""

from __future__ import annotations

import pytest
from sqlalchemy.exc import OperationalError
from src.anomaly_detection.data import DOMAINS
from src.api.routers import anomalies, forecast, inventory, kpis, scenario, suppliers
from src.forecasting.service import InsufficientHistoryError, ProductNotFoundError
from src.scenario_model.data import BaselineMetrics

KPI = {
    "revenue_aed": 100.0,
    "total_units_sold": 10,
    "gross_margin_aed": 30.0,
    "average_order_value_aed": 50.0,
    "inventory_value_aed": 20.0,
    "stockout_rate": 0.1,
    "fill_rate": 0.9,
    "supplier_otd": 0.4,
    "average_lead_time_days": 3.5,
    "inventory_turnover": 12.0,
}
SUPPLIER = {
    "supplier": "Book Shop Supplier",
    "risk_score": 54.49,
    "risk_level": "High",
    "shipment_count": 405,
    "on_time_rate": 0.425,
    "average_lead_time_days": 3.39,
    "lead_time_std_days": 1.69,
    "po_count": 16,
    "cancellation_rate": 0.125,
    "cost_variability": 0.0,
    "defect_rate": 0.022,
}
WAREHOUSE = {
    "products_tracked": 10,
    "products_out_of_stock": 1,
    "inventory_value_aed": 1000.0,
    "stockout_rate": 0.1,
    "fill_rate": 0.9,
}
INVENTORY = {
    "network": {"warehouse": "Network", **WAREHOUSE},
    "warehouses": [
        {"warehouse": "Dubai Distribution Center", **WAREHOUSE},
        {"warehouse": "Ajman Distribution Center", **WAREHOUSE},
    ],
}
FORECAST = {
    "product_id": "365",
    "model": "Seasonal Naive",
    "season_length": 52,
    "history_weeks": 145,
    "last_observed_week": "2017-10-08",
    "confidence": 0.8,
    "points": [{"week_ending": "2017-10-15", "forecast": 5.0, "lower": 4.0, "upper": 6.0}],
}
BASELINE = BaselineMetrics(
    avg_daily_demand_units=236.5,
    daily_demand_std_units=86.5,
    avg_lead_time_days=3.5,
    stockout_rate=0.139,
    inventory_value_aed=2_827_125.84,
    transport_cost_aed=460_689.23,
    revenue_aed=2_475_802.17,
)


def _anomaly(metric: str, score: float, severity: str = "High", method: str = "IQR") -> dict:
    return {
        "anomaly_id": f"{metric}|{method}|{score}",
        "date": "2017-01-01",
        "entity": "Network",
        "metric": metric,
        "method": method,
        "expected_value": 1.0,
        "actual_value": 9.0,
        "anomaly_score": score,
        "severity": severity,
    }


class Counter:
    """Wraps a stub so a test can assert how many times it actually ran."""

    def __init__(self, result):
        self.result = result
        self.calls = 0

    def __call__(self, *args, **kwargs):
        self.calls += 1
        return self.result(*args, **kwargs) if callable(self.result) else self.result


# --- health -------------------------------------------------------------------


def test_health_is_never_rate_limited(client):
    statuses = {client.get("/health").status_code for _ in range(80)}
    assert statuses == {200}


def test_readiness_ok_when_warehouse_is_loaded_and_cache_answers(client, monkeypatch):
    from src.api.routers import health

    monkeypatch.setattr(health, "warehouse_is_loaded", lambda: True)
    response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready", "database": "ok", "cache": "ok (memory)"}


def test_readiness_503_on_an_empty_warehouse(client, monkeypatch):
    from src.api.routers import health

    monkeypatch.setattr(health, "warehouse_is_loaded", lambda: False)
    response = client.get("/health/ready")
    assert response.status_code == 503
    assert response.json()["database"].startswith("empty")


def test_readiness_503_when_database_is_down(client, monkeypatch):
    from src.api.routers import health

    def down():
        raise OperationalError("SELECT 1", {}, Exception("connection refused"))

    monkeypatch.setattr(health, "warehouse_is_loaded", down)
    response = client.get("/health/ready")
    assert response.status_code == 503
    assert response.json()["database"] == "unavailable"


# --- warehouse guard ------------------------------------------------------------------


@pytest.fixture
def real_guard():
    """Re-enable the guard that tests/unit/conftest.py bypasses."""
    from src.api.core.dependencies import require_loaded_warehouse
    from src.api.main import app

    override = app.dependency_overrides.pop(require_loaded_warehouse)
    yield
    app.dependency_overrides[require_loaded_warehouse] = override


def test_empty_warehouse_is_a_503_with_instructions(client, monkeypatch, real_guard):
    from src.api.core import dependencies

    monkeypatch.setattr(dependencies, "warehouse_is_loaded", lambda: False)
    response = client.get("/api/v1/kpis")
    assert response.status_code == 503
    assert "etl.run_local" in response.json()["detail"]


def test_loaded_warehouse_check_is_cached(client, monkeypatch, real_guard):
    from src.api.core import dependencies

    checks = Counter(True)
    monkeypatch.setattr(dependencies, "warehouse_is_loaded", checks)
    monkeypatch.setattr(kpis, "_compute_kpi_summary", lambda: kpis.KpiSummary(**KPI))
    client.get("/api/v1/kpis")
    client.get("/api/v1/inventory")  # different route, same cached answer
    assert checks.calls == 1


# --- kpis ---------------------------------------------------------------------


def test_kpis_root_and_summary_alias_return_the_same_payload(client, monkeypatch):
    monkeypatch.setattr(kpis, "_compute_kpi_summary", lambda: kpis.KpiSummary(**KPI))
    assert client.get("/api/v1/kpis").json() == KPI
    assert client.get("/api/v1/kpis/summary").json() == KPI


def test_kpis_are_computed_once_then_served_from_cache(client, monkeypatch):
    stub = Counter(lambda: kpis.KpiSummary(**KPI))
    monkeypatch.setattr(kpis, "_compute_kpi_summary", stub)
    for _ in range(3):
        assert client.get("/api/v1/kpis").status_code == 200
    assert stub.calls == 1


def test_warehouse_outage_is_a_503_not_a_500(client, monkeypatch):
    def down():
        raise OperationalError("SELECT", {}, Exception("could not connect to server"))

    monkeypatch.setattr(kpis, "_compute_kpi_summary", down)
    response = client.get("/api/v1/kpis")
    assert response.status_code == 503
    assert "could not connect" not in response.text  # internals never leak to clients


# --- suppliers / inventory ---------------------------------------------------------


def test_supplier_risk_returns_scores_with_their_drivers(client, monkeypatch):
    stub = Counter({"weights": {"late_delivery_rate": 0.25}, "suppliers": [SUPPLIER]})
    monkeypatch.setattr(suppliers, "supplier_risk_report", stub)
    body = client.get("/api/v1/suppliers/risk").json()
    client.get("/api/v1/suppliers/risk")
    assert body["suppliers"][0]["cancellation_rate"] == 0.125
    assert stub.calls == 1


def test_inventory_returns_network_and_every_warehouse(client, monkeypatch):
    monkeypatch.setattr(inventory, "compute_inventory_status", lambda: INVENTORY)
    body = client.get("/api/v1/inventory").json()
    assert body["network"]["warehouse"] == "Network"
    assert len(body["warehouses"]) == 2


def test_inventory_warehouse_filter_is_case_insensitive(client, monkeypatch):
    stub = Counter(INVENTORY)
    monkeypatch.setattr(inventory, "compute_inventory_status", stub)
    body = client.get("/api/v1/inventory", params={"warehouse": "dubai DISTRIBUTION center"})
    assert [w["warehouse"] for w in body.json()["warehouses"]] == ["Dubai Distribution Center"]
    client.get("/api/v1/inventory", params={"warehouse": "Ajman Distribution Center"})
    assert stub.calls == 1  # filtering reuses the cached report


def test_inventory_unknown_warehouse_is_404_listing_valid_names(client, monkeypatch):
    monkeypatch.setattr(inventory, "compute_inventory_status", lambda: INVENTORY)
    response = client.get("/api/v1/inventory", params={"warehouse": "Mars"})
    assert response.status_code == 404
    assert "Dubai Distribution Center" in response.json()["detail"]


# --- forecast -----------------------------------------------------------------------


def test_forecast_is_cached_per_product_model_and_horizon(client, monkeypatch):
    stub = Counter(lambda product_id, horizon, model: FORECAST)
    monkeypatch.setattr(forecast, "forecast_product", stub)
    client.get("/api/v1/forecast", params={"product_id": "365"})
    client.get("/api/v1/forecast", params={"product_id": "365"})
    client.get("/api/v1/forecast", params={"product_id": "365", "model": "ets"})
    client.get("/api/v1/forecast", params={"product_id": "365", "horizon": 4})
    assert stub.calls == 3


def test_forecast_rejects_unknown_model_and_out_of_range_horizon(client):
    assert client.get("/api/v1/forecast?product_id=1&model=prophet").status_code == 422
    assert client.get("/api/v1/forecast?product_id=1&horizon=53").status_code == 422
    assert client.get("/api/v1/forecast").status_code == 422  # product_id is required


@pytest.mark.parametrize(
    ("error", "status"),
    [(ProductNotFoundError("x"), 404), (InsufficientHistoryError("3 weeks"), 422)],
)
def test_forecast_maps_domain_errors_to_http_status(client, monkeypatch, error, status):
    def fail(*_args):
        raise error

    monkeypatch.setattr(forecast, "forecast_product", fail)
    assert client.get("/api/v1/forecast", params={"product_id": "x"}).status_code == status


def test_forecast_uses_the_expensive_rate_limit_tier(client, monkeypatch):
    monkeypatch.setattr(forecast, "forecast_product", lambda *_: FORECAST)
    statuses = [
        client.get("/api/v1/forecast", params={"product_id": "365"}).status_code for _ in range(11)
    ]
    assert statuses[:10] == [200] * 10
    assert statuses[10] == 429


def test_forecastable_products_listing(client, monkeypatch):
    product = {
        "product_id": "365",
        "product_name": "Rip Deck",
        "total_quantity": 73698,
        "weeks_of_history": 143,
    }
    monkeypatch.setattr(forecast, "list_forecastable_products", lambda n: [product] * n)
    response = client.get("/api/v1/forecast/products", params={"limit": 2})
    assert response.json() == [product, product]


# --- anomalies -------------------------------------------------------------------------


def test_anomaly_metric_enum_matches_the_detection_pipeline():
    assert {m.value for m in anomalies.AnomalyMetric} == set(DOMAINS)


def test_anomalies_default_to_high_severity_sorted_by_score(client, monkeypatch):
    rows = {
        "daily_sales": [_anomaly("daily_sales", 3.0), _anomaly("daily_sales", 9.0, "Low")],
        "transport_cost": [_anomaly("transport_cost", 5.0)],
    }
    monkeypatch.setattr(anomalies, "domain_anomalies", lambda m: rows.get(m, []))
    body = client.get("/api/v1/anomalies").json()
    assert [i["anomaly_score"] for i in body["items"]] == [5.0, 3.0]
    assert body["total_matching"] == 2


def test_anomaly_filters_and_limit(client, monkeypatch):
    rows = [
        _anomaly("daily_sales", 1.0, "Low", "Z-Score"),
        _anomaly("daily_sales", 2.0, "High", "Z-Score"),
        _anomaly("daily_sales", 3.0, "High", "IQR"),
    ]
    monkeypatch.setattr(anomalies, "domain_anomalies", lambda m: rows)
    body = client.get(
        "/api/v1/anomalies",
        params={"metric": "daily_sales", "severity": "any", "method": "Z-Score", "limit": 1},
    ).json()
    assert body["total_matching"] == 2
    assert body["returned"] == 1
    assert body["items"][0]["anomaly_score"] == 2.0


def test_anomalies_cache_each_domain_separately(client, monkeypatch):
    stub = Counter(lambda m: [_anomaly(m, 1.0)])
    monkeypatch.setattr(anomalies, "domain_anomalies", stub)
    client.get("/api/v1/anomalies", params={"metric": "daily_sales"})
    client.get("/api/v1/anomalies", params={"metric": "daily_sales", "severity": "any"})
    assert stub.calls == 1
    client.get("/api/v1/anomalies")  # all 5: 4 new domains computed, daily_sales reused
    assert stub.calls == len(DOMAINS)


# --- scenario ----------------------------------------------------------------------------


def test_scenario_results_are_not_cached_but_the_baseline_is(client, monkeypatch):
    from src.scenario_model import data as scenario_data

    loads = Counter(BASELINE)
    monkeypatch.setattr(scenario_data, "load_baseline", loads)
    payload = {"demand_change_pct": 0, "lead_time_change_pct": 0, "transport_cost_change_pct": 0}
    first = client.post("/api/v1/scenario/simulate", json=payload).json()
    second = client.post(
        "/api/v1/scenario/simulate", json={**payload, "demand_change_pct": 10}
    ).json()

    assert loads.calls == 1  # baseline cached
    assert first["stockout_rate"] == pytest.approx(0.139, abs=1e-3)  # calibration holds
    assert second["stockout_rate"] > first["stockout_rate"]  # fresh result per input


def test_scenario_rejects_out_of_range_inputs(client):
    payload = {"demand_change_pct": 99, "lead_time_change_pct": 0, "transport_cost_change_pct": 0}
    assert client.post("/api/v1/scenario/simulate", json=payload).status_code == 422


def test_scenario_router_models_are_the_ones_the_engine_returns():
    assert scenario.ScenarioResult.model_fields.keys() >= {"stockout_rate", "revenue_at_risk_aed"}


# --- cross-cutting ----------------------------------------------------------------------


def test_request_id_is_generated_and_echoed(client):
    generated = client.get("/health").headers["X-Request-ID"]
    assert len(generated) == 32
    echoed = client.get("/health", headers={"X-Request-ID": "trace-123"})
    assert echoed.headers["X-Request-ID"] == "trace-123"


def test_every_analytics_route_is_versioned(client):
    paths = client.get("/openapi.json").json()["paths"]
    analytics = [p for p in paths if not p.startswith("/health")]
    assert analytics and all(p.startswith("/api/v1/") for p in analytics)
    for route in ("kpis", "suppliers/risk", "inventory", "forecast", "anomalies", "scenario"):
        assert any(p.startswith(f"/api/v1/{route}") for p in paths), route
