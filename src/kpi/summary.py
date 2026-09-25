"""Ground-truth KPI computation (Phase 10 — Power BI & Excel).

Every field here traces to a row in `docs/kpi_dictionary.md` and mirrors a
formula already established elsewhere in this project
(`sql/07_kpi/executive_summary.sql`'s revenue/margin/stockout/fill/OTD
logic, `sql/03_inventory/03_inventory_turnover_by_product.sql`'s turnover
logic). This module exists so the Power BI DAX measures (`powerbi/`) and
the Excel cross-check formulas (`excel/`) have one independently computed,
authoritative number per KPI to be verified against — the SQL/DAX/Excel
are the actual deliverables, this is the answer key, not a replacement.

All figures are network-wide, all-time aggregates (no date filtering) —
slicing by date/category/etc. is exactly what the BI layer's own filter
context (DAX CALCULATE/ALLSELECTED, Excel PivotTable filters) is for, not
something to bake into a fixed Python window.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from src.common.db import get_engine


@dataclass
class KpiSummary:
    total_revenue_aed: float
    total_units_sold: int
    gross_margin_aed: float
    average_order_value_aed: float
    inventory_value_aed: float
    stockout_rate: float
    fill_rate: float
    supplier_otd: float
    average_lead_time_days: float
    inventory_turnover: float


def compute_kpi_summary() -> KpiSummary:
    """Load real, current, network-wide KPI figures from the warehouse."""
    engine = get_engine()

    sales = pd.read_sql_query(
        """
        SELECT fs.sales_amount, fs.quantity, fs.order_id, dp.unit_cost
        FROM warehouse.fact_sales fs
        JOIN warehouse.dim_product dp ON dp.product_key = fs.product_key
        """,
        engine,
    )
    total_revenue = float(sales["sales_amount"].sum())
    total_units_sold = int(sales["quantity"].sum())
    gross_margin = float((sales["sales_amount"] - sales["unit_cost"] * sales["quantity"]).sum())
    average_order_value = total_revenue / sales["order_id"].nunique()
    cogs = float((sales["quantity"] * sales["unit_cost"]).sum())

    inventory = pd.read_sql_query(
        """
        SELECT dd.full_date AS date, fi.product_key, fi.opening_stock, fi.received_quantity,
               fi.sold_quantity, fi.closing_stock, dp.unit_cost
        FROM warehouse.fact_inventory fi
        JOIN warehouse.dim_product dp ON dp.product_key = fi.product_key
        JOIN warehouse.dim_date dd ON dd.date_key = fi.date_key
        """,
        engine,
        parse_dates=["date"],
    )
    stockout_rate = float((inventory["closing_stock"] == 0).mean())

    # Same unmet-demand proxy as executive_summary.sql: stock that should
    # have depleted via sales beyond what was actually recorded as sold.
    unmet = (
        inventory["opening_stock"] - inventory["closing_stock"] - inventory["received_quantity"]
    ).clip(lower=0)
    fill_rate = float(inventory["sold_quantity"].sum() / (inventory["sold_quantity"] + unmet).sum())

    # Inventory Value is a balance-sheet-style snapshot, not a sum across
    # every historical day (that would count the same stock many times
    # over). It must be taken *per product's own* most recent date, not one
    # shared global max date: Phase 3's simulator scopes each of the 502
    # products to its own observed sales date range, so those end dates are
    # scattered (confirmed: only 2 of 502 products share the true global
    # max date) — filtering on one shared date would silently price almost
    # the entire portfolio at zero, the same class of bug already caught
    # and fixed per-source in src/scenario_model/data.py for Phase 9.
    latest_per_product = inventory.loc[inventory.groupby("product_key")["date"].idxmax()]
    inventory_value = float(
        (latest_per_product["closing_stock"] * latest_per_product["unit_cost"]).sum()
    )

    # Average inventory value: total portfolio value *per day*
    # (opening/closing average, valued at cost), then averaged across days
    # — not a flat row-level mean, which would misweight products with
    # more or fewer days of history (the same bug fixed in
    # src/scenario_model/data.py for Phase 9's inventory_value_aed).
    inventory["daily_avg_value"] = (
        (inventory["opening_stock"] + inventory["closing_stock"]) / 2 * inventory["unit_cost"]
    )
    daily_avg_inventory_value = inventory.groupby("date")["daily_avg_value"].sum()
    avg_inventory_value = float(daily_avg_inventory_value.mean())
    inventory_turnover = cogs / avg_inventory_value if avg_inventory_value else 0.0

    shipments = pd.read_sql_query(
        """
        SELECT
            (actual_date.full_date - order_date.full_date) AS lead_time_days,
            fsh.actual_delivery_date_key,
            fsh.expected_delivery_date_key
        FROM warehouse.fact_shipments fsh
        JOIN warehouse.dim_date order_date ON order_date.date_key = fsh.order_date_key
        LEFT JOIN warehouse.dim_date actual_date ON actual_date.date_key = fsh.actual_delivery_date_key
        """,
        engine,
    )
    average_lead_time = float(shipments["lead_time_days"].mean())
    otd_eligible = shipments["actual_delivery_date_key"].notna()
    on_time = shipments["actual_delivery_date_key"] <= shipments["expected_delivery_date_key"]
    supplier_otd = float((on_time & otd_eligible).sum() / otd_eligible.sum())

    return KpiSummary(
        total_revenue_aed=round(total_revenue, 2),
        total_units_sold=total_units_sold,
        gross_margin_aed=round(gross_margin, 2),
        average_order_value_aed=round(average_order_value, 2),
        inventory_value_aed=round(inventory_value, 2),
        stockout_rate=round(stockout_rate, 4),
        fill_rate=round(fill_rate, 4),
        supplier_otd=round(supplier_otd, 4),
        average_lead_time_days=round(average_lead_time, 2),
        inventory_turnover=round(inventory_turnover, 2),
    )
