"""/api/v1/kpis against the real warehouse (skipped unless it's loaded)."""

import pytest

pytestmark = pytest.mark.warehouse


def test_kpi_summary_ok(client):
    response = client.get("/api/v1/kpis")
    assert response.status_code == 200
    body = response.json()
    assert body["revenue_aed"] > 0
    assert 0 < body["fill_rate"] <= 1


def test_kpi_summary_is_cached_on_second_call(client, monkeypatch):
    from src.api.routers import kpis

    calls = {"n": 0}
    original = kpis._compute_kpi_summary

    def counting_compute():
        calls["n"] += 1
        return original()

    monkeypatch.setattr(kpis, "_compute_kpi_summary", counting_compute)

    client.get("/api/v1/kpis")
    client.get("/api/v1/kpis")
    assert calls["n"] == 1
