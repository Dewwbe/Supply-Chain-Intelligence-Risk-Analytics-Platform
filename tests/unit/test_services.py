"""Service and data-access logic with the warehouse reads replaced by small frames.

Each test hands the code the rows its SQL would have returned, so the
arithmetic (KPI definitions, aggregation, JSON shaping) is exercised for real
without a database. The SQL itself is exercised in tests/integration.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from src.anomaly_detection import data as anomaly_data
from src.anomaly_detection import service as anomaly_service
from src.eda import data_access
from src.forecasting import data as forecast_data
from src.forecasting import service as forecast_service
from src.kpi import inventory as inventory_kpi
from src.kpi import summary as kpi_summary
from src.scenario_model import data as scenario_data
from src.supplier_risk import service as supplier_service


def _no_engine(monkeypatch, *modules):
    for module in modules:
        monkeypatch.setattr(module, "get_engine", lambda: None)


# --- KPI summary --------------------------------------------------------------------


def test_kpi_summary_definitions(monkeypatch):
    frames = {
        "fs.sales_amount": pd.DataFrame(
            {
                "sales_amount": [100.0, 50.0, 30.0],
                "quantity": [2, 1, 3],
                "order_id": ["A", "A", "B"],
                "unit_cost": [20.0, 10.0, 5.0],
            }
        ),
        "fi.opening_stock": pd.DataFrame(
            {
                "date": pd.to_datetime(["2020-01-01", "2020-01-02", "2020-01-01", "2020-01-02"]),
                "product_key": [1, 1, 2, 2],
                "opening_stock": [10, 8, 5, 0],
                "received_quantity": [0, 0, 0, 0],
                "sold_quantity": [2, 8, 5, 0],
                "closing_stock": [8, 0, 0, 0],
                "unit_cost": [20.0, 20.0, 10.0, 10.0],
            }
        ),
        "demand_quantity": pd.DataFrame(
            {
                "product_key": [1, 1, 2, 2],
                "date": pd.to_datetime(["2020-01-01", "2020-01-02", "2020-01-01", "2020-01-02"]),
                "demand_quantity": [2, 10, 5, 3],
            }
        ),
        "lead_time_days": pd.DataFrame(
            {
                "lead_time_days": [2.0, 4.0, np.nan],
                "actual_delivery_date_key": [20200103, 20200110, np.nan],
                "expected_delivery_date_key": [20200105, 20200105, 20200105],
            }
        ),
    }

    def fake_read(query, *_args, **_kwargs):
        return next(frame.copy() for marker, frame in frames.items() if marker in query)

    monkeypatch.setattr(kpi_summary, "get_engine", lambda: None)
    monkeypatch.setattr(kpi_summary.pd, "read_sql_query", fake_read)

    s = kpi_summary.compute_kpi_summary()
    assert s.total_revenue_aed == 180.0
    assert s.total_units_sold == 6
    assert s.gross_margin_aed == pytest.approx(180 - (40 + 10 + 15))
    assert s.average_order_value_aed == 90.0
    assert s.stockout_rate == 0.75
    assert s.fill_rate == pytest.approx(15 / 20)  # fulfilled / demanded, not a stock proxy
    assert s.inventory_value_aed == 0.0  # every product's latest closing stock is zero
    assert s.supplier_otd == 0.5
    assert s.average_lead_time_days == 3.0


# --- inventory status ---------------------------------------------------------------


def test_inventory_status_aggregates_network_from_warehouse_sums(monkeypatch):
    rows = pd.DataFrame(
        {
            "warehouse_name": ["Ajman", "Dubai"],
            "products_tracked": [2, 3],
            "product_days": [100, 300],
            "stockout_days": [10, 60],
            "units_fulfilled": [90.0, 240.0],
            "units_demanded": [100.0, 300.0],
            "inventory_value": [1000.0, 3000.0],
            "products_out_of_stock": [0, 2],
        }
    )
    monkeypatch.setattr(inventory_kpi, "get_engine", lambda: None)
    monkeypatch.setattr(inventory_kpi.pd, "read_sql_query", lambda *_a, **_k: rows)

    report = inventory_kpi.compute_inventory_status()
    network = report["network"]
    assert network["products_tracked"] == 5
    assert network["stockout_rate"] == 0.175  # 70 / 400 product-days, not a mean of rates
    assert network["fill_rate"] == 0.825  # 330 / 400 units
    assert network["inventory_value_aed"] == 4000.0
    assert [w["warehouse"] for w in report["warehouses"]] == ["Ajman", "Dubai"]
    assert report["warehouses"][0]["fill_rate"] == 0.9


def test_inventory_status_handles_zero_denominators():
    empty = pd.Series(
        {
            "products_tracked": 0,
            "product_days": 0,
            "stockout_days": 0,
            "units_fulfilled": 0,
            "units_demanded": 0,
            "inventory_value": None,
            "products_out_of_stock": None,
        }
    )
    status = inventory_kpi._status("Empty", empty)
    assert (status.stockout_rate, status.fill_rate, status.inventory_value_aed) == (0.0, 0.0, 0.0)


# --- forecasting -----------------------------------------------------------------------


def _weekly(n: int) -> pd.Series:
    index = pd.date_range("2016-01-03", periods=n, freq="W")
    return pd.Series(100 + 10 * np.sin(np.arange(n) / 4), index=index)


def test_forecast_product_returns_horizon_points_with_ordered_intervals(monkeypatch):
    monkeypatch.setattr(forecast_data, "load_weekly_demand", lambda _pid: _weekly(120))
    result = forecast_service.forecast_product("365", horizon=6, model="seasonal_naive")
    assert result["season_length"] == 52
    assert result["history_weeks"] == 120
    assert len(result["points"]) == 6
    assert all(p["lower"] <= p["forecast"] <= p["upper"] for p in result["points"])
    assert result["points"][0]["week_ending"] > result["last_observed_week"]


def test_forecast_product_errors(monkeypatch):
    monkeypatch.setattr(forecast_data, "load_weekly_demand", lambda _pid: pd.Series(dtype=float))
    with pytest.raises(forecast_service.ProductNotFoundError):
        forecast_service.forecast_product("nope", 4, "seasonal_naive")

    monkeypatch.setattr(forecast_data, "load_weekly_demand", lambda _pid: _weekly(3))
    with pytest.raises(forecast_service.InsufficientHistoryError):
        forecast_service.forecast_product("new", 4, "seasonal_naive")


def test_list_forecastable_products(monkeypatch):
    frame = pd.DataFrame(
        {
            "product_source_id": [365],
            "product_name": ["Rip Deck"],
            "total_quantity": [73698],
            "weeks_span": [143],
        }
    )
    monkeypatch.setattr(forecast_data, "select_top_products", lambda n: frame)
    assert forecast_service.list_forecastable_products(1) == [
        {
            "product_id": "365",
            "product_name": "Rip Deck",
            "total_quantity": 73698,
            "weeks_of_history": 143,
        }
    ]


def test_forecast_data_loaders(monkeypatch):
    _no_engine(monkeypatch, forecast_data)
    daily = pd.DataFrame({"date": pd.to_datetime(["2020-01-01", "2020-01-04"]), "quantity": [3, 5]})
    monkeypatch.setattr(forecast_data.pd, "read_sql_query", lambda *_a, **_k: daily)

    series = forecast_data.load_daily_demand("1")
    assert list(series) == [3, 0, 0, 5]  # zero-filled across its own range
    assert forecast_data.load_weekly_demand("1").sum() == 8
    assert not forecast_data.select_top_products(n=1).empty

    monkeypatch.setattr(
        forecast_data.pd,
        "read_sql_query",
        lambda *_a, **_k: pd.DataFrame({"date": pd.to_datetime([]), "quantity": []}),
    )
    assert forecast_data.load_daily_demand("unknown").empty


# --- supplier risk --------------------------------------------------------------------


def test_supplier_risk_report_joins_scores_and_drivers(monkeypatch):
    features = pd.DataFrame(
        {
            "supplier_name": ["Risky  Supplier", "Steady Supplier"],
            "shipment_count": [100, 200],
            "on_time_rate": [0.30, 0.60],
            "average_lead_time_days": [4.0, 3.0],
            "lead_time_std_days": [2.0, 1.0],
            "po_count": [10, 20],
            "cancellation_rate": [0.2, 0.0],
            "cost_variability": [1.0, 0.1],
            "defect_rate": [0.05, 0.01],
        }
    )
    monkeypatch.setattr(supplier_service, "compute_supplier_features", lambda: features)
    report = supplier_service.supplier_risk_report()
    first, second = report["suppliers"]
    assert first["supplier"] == "Risky Supplier"  # riskiest first, whitespace normalised
    assert first["risk_score"] == 100.0 and second["risk_score"] == 0.0
    assert first["po_count"] == 10 and isinstance(first["po_count"], int)
    assert sum(report["weights"].values()) == pytest.approx(1.0)


# --- anomalies --------------------------------------------------------------------------


def test_domain_anomalies_are_json_ready_and_sorted(monkeypatch):
    flagged = pd.DataFrame(
        {
            "anomaly_id": ["a", "b"],
            "date": pd.to_datetime(["2017-01-01", "2017-01-02"]),
            "entity": ["Network", "Network"],
            "metric": ["daily_sales", "daily_sales"],
            "method": ["IQR", "IQR"],
            "expected_value": [1.0, 1.0],
            "actual_value": [5.0, 9.0],
            "anomaly_score": [2.0, 7.0],
            "severity": ["Medium", "High"],
        }
    )
    monkeypatch.setattr(anomaly_service, "detect_domain", lambda _m: flagged)
    rows = anomaly_service.domain_anomalies("daily_sales")
    assert [r["anomaly_id"] for r in rows] == ["b", "a"]
    assert rows[0]["date"] == "2017-01-02"


def test_anomaly_domain_loaders_shape_each_population(monkeypatch):
    sales = pd.DataFrame(
        {"order_date": pd.to_datetime(["2020-01-01"] * 2), "sales_amount": [5.0, 7.0]}
    )
    inventory = pd.DataFrame(
        {
            "warehouse_name": ["W"] * 3,
            "date": pd.to_datetime(["2020-01-01", "2020-01-02", "2020-01-03"]),
            "closing_stock": [10, 7, 12],
        }
    )
    shipments = pd.DataFrame(
        {
            "order_date": pd.to_datetime(["2020-01-01", "2020-01-02"]),
            "supplier_name": ["S", "S"],
            "carrier_name": ["C", "C"],
            "actual_delivery_date": pd.to_datetime(["2020-01-05", None]),
            "expected_delivery_date": pd.to_datetime(["2020-01-04", "2020-01-06"]),
            "transport_cost": [50.0, None],
            "actual_lead_time_days": [4.0, None],
        }
    )
    monkeypatch.setattr(anomaly_data, "load_sales_detail", lambda: sales)
    monkeypatch.setattr(anomaly_data, "load_inventory_detail", lambda: inventory)
    monkeypatch.setattr(anomaly_data, "load_shipment_detail", lambda: shipments)

    assert anomaly_data.load_daily_sales()["value"].tolist() == [12.0]
    assert anomaly_data.load_daily_inventory_change()["value"].tolist() == [-3.0, 5.0]
    assert anomaly_data.load_shipment_delays()["value"].tolist() == [1]
    assert anomaly_data.load_transport_costs()["entity"].tolist() == ["C"]
    assert anomaly_data.load_supplier_lead_times()["value"].tolist() == [4.0]


# --- EDA data access / scenario baseline ----------------------------------------------------


def test_eda_loaders_query_the_warehouse(monkeypatch):
    _no_engine(monkeypatch, data_access)
    seen: list[str] = []

    def fake_read(query, *_a, **_k):
        seen.append(query)
        return pd.DataFrame(
            {
                "order_date": pd.to_datetime(["2020-01-01"]),
                "expected_delivery_date": pd.to_datetime(["2020-01-04"]),
                "actual_delivery_date": pd.to_datetime(["2020-01-03"]),
            }
        )

    monkeypatch.setattr(data_access.pd, "read_sql_query", fake_read)
    for loader in (
        data_access.load_sales_detail,
        data_access.load_inventory_detail,
        data_access.load_shipment_detail,
        data_access.load_purchase_orders_detail,
        data_access.load_returns_detail,
    ):
        assert isinstance(loader(), pd.DataFrame)
    assert not data_access.run_sql_file("07_kpi/executive_summary.sql").empty
    assert "fill_rate" in seen[-1]  # the file's real SQL was sent
    assert all("warehouse." in q for q in seen)


def test_load_baseline_combines_each_sources_recent_window(monkeypatch):
    window = pd.DataFrame(
        {"max_date": pd.to_datetime(["2020-03-31"]), "min_date": pd.to_datetime(["2020-01-01"])}
    )
    frames = {
        "MAX(d)": window,
        "SUM(fs.quantity) AS units": pd.DataFrame(
            {
                "date": pd.to_datetime(["2020-01-01", "2020-01-02"]),
                "units": [10, 20],
                "revenue": [100.0, 200.0],
            }
        ),
        "DISTINCT ON": pd.DataFrame({"closing_stock": [5, 0], "unit_cost": [10.0, 3.0]}),
        "fi.closing_stock, dp.unit_cost": pd.DataFrame(
            {"date": pd.to_datetime(["2020-01-01"]), "closing_stock": [0], "unit_cost": [1.0]}
        ),
        "lead_time_days": pd.DataFrame({"lead_time_days": [2.0, 4.0]}),
        "total_cost": pd.DataFrame({"total_cost": [75.0]}),
    }

    def fake_read(query, *_a, **_k):
        return next(frame.copy() for marker, frame in frames.items() if marker in query)

    _no_engine(monkeypatch, scenario_data)
    monkeypatch.setattr(scenario_data.pd, "read_sql_query", fake_read)
    baseline = scenario_data.load_baseline()
    assert baseline.avg_daily_demand_units == 15.0
    assert baseline.avg_lead_time_days == 3.0
    assert baseline.inventory_value_aed == 50.0
    assert baseline.transport_cost_aed == 75.0
    assert baseline.revenue_aed == 300.0
    assert baseline.stockout_rate == 1.0
