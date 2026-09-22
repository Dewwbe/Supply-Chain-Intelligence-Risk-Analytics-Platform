def test_kpi_summary_ok(client):
    response = client.get("/api/v1/kpis/summary")
    assert response.status_code == 200
    body = response.json()
    assert "revenue_aed" in body


def test_kpi_summary_is_cached_on_second_call(client, monkeypatch):
    from src.api.routers import kpis

    calls = {"n": 0}
    original = kpis._compute_kpi_summary

    def counting_compute():
        calls["n"] += 1
        return original()

    monkeypatch.setattr(kpis, "_compute_kpi_summary", counting_compute)

    client.get("/api/v1/kpis/summary")
    client.get("/api/v1/kpis/summary")

    # Cache may already hold a value from a prior test run in-process;
    # assert it was not recomputed twice within this test.
    assert calls["n"] <= 1
