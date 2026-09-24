"""Real baseline metrics for the scenario engine — replaces the old
hardcoded `_baseline()` stub. Every figure here comes from the warehouse,
over the most recent `BASELINE_WINDOW_DAYS` of data actually present (this
is historical demo data, not live, so "current" means the last window of
what exists, not today's date).

Each source table gets its **own** "recent window", anchored to that
table's own max date — not one shared window anchored to `fact_sales`.
`fact_shipments` only has DataCo rows (Phase 2), which end about a year
before Olist's later dates; a window anchored to the combined `fact_sales`
max date would land entirely after DataCo's last shipment and silently
return an empty shipment/lead-time picture (this happened during
development — `avg_lead_time_days` came back NaN — hence anchoring
per-source instead of once globally).
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
from sqlalchemy.engine import Engine

from src.common.db import get_engine

BASELINE_WINDOW_DAYS = 90


@dataclass
class BaselineMetrics:
    avg_daily_demand_units: float
    daily_demand_std_units: float
    avg_lead_time_days: float
    stockout_rate: float
    inventory_value_aed: float
    transport_cost_aed: float
    revenue_aed: float


def _recent_window(
    engine: Engine, date_subquery: str, window_days: int
) -> tuple[pd.Timestamp, pd.Timestamp]:
    """max(date) and max(date) - window_days for whatever `date_subquery` selects."""
    bounds = pd.read_sql_query(
        f"SELECT MAX(d) AS max_date, MAX(d) - %(window)s AS min_date FROM ({date_subquery}) AS t(d)",
        engine,
        params={"window": window_days},
        parse_dates=["max_date", "min_date"],
    )
    return bounds.loc[0, "min_date"], bounds.loc[0, "max_date"]


def load_baseline(window_days: int = BASELINE_WINDOW_DAYS) -> BaselineMetrics:
    """Load real current-state figures from the warehouse."""
    engine = get_engine()

    sales_min, sales_max = _recent_window(
        engine,
        "SELECT dd.full_date FROM warehouse.fact_sales fs "
        "JOIN warehouse.dim_date dd ON dd.date_key = fs.date_key",
        window_days,
    )
    daily_demand = pd.read_sql_query(
        """
        SELECT dd.full_date AS date, SUM(fs.quantity) AS units, SUM(fs.sales_amount) AS revenue
        FROM warehouse.fact_sales fs
        JOIN warehouse.dim_date dd ON dd.date_key = fs.date_key
        WHERE dd.full_date BETWEEN %(min_date)s AND %(max_date)s
        GROUP BY dd.full_date
        """,
        engine,
        params={"min_date": sales_min, "max_date": sales_max},
        parse_dates=["date"],
    )

    inventory_min, inventory_max = _recent_window(
        engine,
        "SELECT dd.full_date FROM warehouse.fact_inventory fi "
        "JOIN warehouse.dim_date dd ON dd.date_key = fi.date_key",
        window_days,
    )
    inventory = pd.read_sql_query(
        """
        SELECT dd.full_date AS date, fi.closing_stock, dp.unit_cost
        FROM warehouse.fact_inventory fi
        JOIN warehouse.dim_product dp ON dp.product_key = fi.product_key
        JOIN warehouse.dim_date dd ON dd.date_key = fi.date_key
        WHERE dd.full_date BETWEEN %(min_date)s AND %(max_date)s
        """,
        engine,
        params={"min_date": inventory_min, "max_date": inventory_max},
        parse_dates=["date"],
    )
    inventory["value"] = inventory["closing_stock"] * inventory["unit_cost"]
    # total portfolio value held *per day* (summed across products/warehouses),
    # then averaged across the window — not the average of individual rows,
    # which would understate the real total by orders of magnitude.
    daily_inventory_value = inventory.groupby("date")["value"].sum()

    shipments_min, shipments_max = _recent_window(
        engine,
        "SELECT dd.full_date FROM warehouse.fact_shipments fsh "
        "JOIN warehouse.dim_date dd ON dd.date_key = fsh.order_date_key",
        window_days,
    )
    lead_time = pd.read_sql_query(
        """
        SELECT (actual_date.full_date - order_date.full_date) AS lead_time_days
        FROM warehouse.fact_shipments fsh
        JOIN warehouse.dim_date order_date ON order_date.date_key = fsh.order_date_key
        JOIN warehouse.dim_date actual_date ON actual_date.date_key = fsh.actual_delivery_date_key
        WHERE order_date.full_date BETWEEN %(min_date)s AND %(max_date)s
        """,
        engine,
        params={"min_date": shipments_min, "max_date": shipments_max},
    )
    transport_cost = pd.read_sql_query(
        """
        SELECT SUM(fsh.transport_cost) AS total_cost
        FROM warehouse.fact_shipments fsh
        JOIN warehouse.dim_date order_date ON order_date.date_key = fsh.order_date_key
        WHERE order_date.full_date BETWEEN %(min_date)s AND %(max_date)s
        """,
        engine,
        params={"min_date": shipments_min, "max_date": shipments_max},
    )

    return BaselineMetrics(
        avg_daily_demand_units=float(daily_demand["units"].mean()),
        daily_demand_std_units=float(daily_demand["units"].std() or 0.0),
        avg_lead_time_days=float(lead_time["lead_time_days"].mean()),
        stockout_rate=float((inventory["closing_stock"] == 0).mean()),
        inventory_value_aed=float(daily_inventory_value.mean()),
        transport_cost_aed=float(transport_cost.loc[0, "total_cost"] or 0.0),
        revenue_aed=float(daily_demand["revenue"].sum()),
    )
