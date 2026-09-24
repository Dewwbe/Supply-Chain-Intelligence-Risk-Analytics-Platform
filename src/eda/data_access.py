"""Data access for the Phase 4 EDA notebooks.

Row-level pulls join facts to their dimensions once, here, so every
notebook works from the same shape instead of re-deriving joins ad hoc.
`run_sql_file` reuses the Phase 3 `sql/` query library directly — most of
the pre-aggregated charts in the notebooks are one of those files, not a
duplicate query written in pandas.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.common.db import get_engine

# Repo-root-relative, not CWD-relative — notebooks run from notebooks/, not
# the repo root, so a bare Path("sql") would resolve to notebooks/sql/.
SQL_ROOT = Path(__file__).resolve().parents[2] / "sql"


def run_sql_file(relative_path: str) -> pd.DataFrame:
    """Execute a query from sql/<relative_path> and return it as a DataFrame."""
    sql_text = (SQL_ROOT / relative_path).read_text(encoding="utf-8")
    return pd.read_sql_query(sql_text, get_engine())


def load_sales_detail() -> pd.DataFrame:
    """One row per sold line item, with the dimension attributes EDA needs."""
    query = """
        SELECT
            fs.sales_key,
            fs.source_system,
            fs.order_id,
            dd.full_date AS order_date,
            dd.year,
            dd.month,
            dd.day_of_week,
            dd.is_weekend,
            dp.product_source_id,
            dp.product_name,
            dp.category,
            dp.unit_cost,
            dl.emirate,
            COALESCE(dc.customer_segment, 'Unclassified') AS customer_segment,
            ds.store_type,
            fs.quantity,
            fs.unit_price,
            fs.discount,
            fs.sales_amount,
            fs.order_status,
            fs.delivery_status
        FROM warehouse.fact_sales fs
        JOIN warehouse.dim_date dd ON dd.date_key = fs.date_key
        JOIN warehouse.dim_product dp ON dp.product_key = fs.product_key
        LEFT JOIN warehouse.dim_location dl ON dl.location_key = fs.location_key
        LEFT JOIN warehouse.dim_customer dc ON dc.customer_key = fs.customer_key
        LEFT JOIN warehouse.dim_store ds ON ds.store_key = fs.store_key
    """
    return pd.read_sql_query(query, get_engine(), parse_dates=["order_date"])


def load_inventory_detail() -> pd.DataFrame:
    """One row per (product, warehouse, date) inventory snapshot."""
    query = """
        SELECT
            dd.full_date AS date,
            dp.product_source_id,
            dp.product_name,
            dp.category,
            dp.unit_cost,
            dw.warehouse_name,
            dl.emirate,
            fi.opening_stock,
            fi.received_quantity,
            fi.sold_quantity,
            fi.closing_stock
        FROM warehouse.fact_inventory fi
        JOIN warehouse.dim_date dd ON dd.date_key = fi.date_key
        JOIN warehouse.dim_product dp ON dp.product_key = fi.product_key
        JOIN warehouse.dim_warehouse dw ON dw.warehouse_key = fi.warehouse_key
        LEFT JOIN warehouse.dim_location dl ON dl.location_key = dw.location_key
    """
    return pd.read_sql_query(query, get_engine(), parse_dates=["date"])


def load_shipment_detail() -> pd.DataFrame:
    """One row per DataCo shipment, with real lead time computed from joined DATE values
    (not the raw date_key, which is a YYYYMMDD integer, not a day count)."""
    query = """
        SELECT
            fsh.shipment_key,
            ds.supplier_key,
            ds.supplier_name,
            ds.standard_lead_time_days,
            dw.warehouse_name,
            dl.emirate,
            dp.product_source_id,
            dp.category,
            order_date.full_date AS order_date,
            expected_date.full_date AS expected_delivery_date,
            actual_date.full_date AS actual_delivery_date,
            (actual_date.full_date - order_date.full_date) AS actual_lead_time_days,
            (actual_date.full_date <= expected_date.full_date) AS on_time,
            fsh.quantity,
            fsh.transport_mode,
            dt.carrier_name,
            dt.avg_cost_per_km,
            fsh.transport_cost
        FROM warehouse.fact_shipments fsh
        JOIN warehouse.dim_supplier ds ON ds.supplier_key = fsh.supplier_key
        JOIN warehouse.dim_warehouse dw ON dw.warehouse_key = fsh.warehouse_key
        LEFT JOIN warehouse.dim_location dl ON dl.location_key = dw.location_key
        JOIN warehouse.dim_product dp ON dp.product_key = fsh.product_key
        JOIN warehouse.dim_date order_date ON order_date.date_key = fsh.order_date_key
        LEFT JOIN warehouse.dim_date expected_date ON expected_date.date_key = fsh.expected_delivery_date_key
        LEFT JOIN warehouse.dim_date actual_date ON actual_date.date_key = fsh.actual_delivery_date_key
        LEFT JOIN warehouse.dim_transport dt ON dt.transport_key = fsh.transport_key
    """
    return pd.read_sql_query(
        query,
        get_engine(),
        parse_dates=["order_date", "expected_delivery_date", "actual_delivery_date"],
    )


def load_purchase_orders_detail() -> pd.DataFrame:
    """One row per synthetic purchase order (see etl/synthesize/purchase_orders.py)."""
    query = """
        SELECT
            fpo.po_key,
            ds.supplier_name,
            dp.category,
            order_date.full_date AS order_date,
            fpo.order_status,
            fpo.quantity,
            fpo.unit_cost,
            fpo.total_cost
        FROM warehouse.fact_purchase_orders fpo
        JOIN warehouse.dim_supplier ds ON ds.supplier_key = fpo.supplier_key
        JOIN warehouse.dim_product dp ON dp.product_key = fpo.product_key
        JOIN warehouse.dim_date order_date ON order_date.date_key = fpo.order_date_key
    """
    return pd.read_sql_query(query, get_engine(), parse_dates=["order_date"])


def load_returns_detail() -> pd.DataFrame:
    """One row per synthetic return (see etl/synthesize/returns.py), joined back to its sale.

    `product_supplier` picks one supplier per product (DISTINCT ON) — a
    product can have many fact_shipments rows, and joining on product_key
    directly would fan out one return into several duplicate rows.
    """
    query = """
        WITH product_supplier AS (
            SELECT DISTINCT ON (product_key) product_key, supplier_key
            FROM warehouse.fact_shipments
            ORDER BY product_key, shipment_key
        )
        SELECT
            fr.return_key,
            fs.source_system,
            dp.category,
            ds.supplier_name,
            return_date.full_date AS return_date,
            fr.reason,
            fr.returned_quantity,
            fr.refund_amount
        FROM warehouse.fact_returns fr
        JOIN warehouse.fact_sales fs ON fs.sales_key = fr.sales_key
        JOIN warehouse.dim_product dp ON dp.product_key = fs.product_key
        JOIN warehouse.dim_date return_date ON return_date.date_key = fr.return_date_key
        LEFT JOIN product_supplier ON product_supplier.product_key = fs.product_key
        LEFT JOIN warehouse.dim_supplier ds ON ds.supplier_key = product_supplier.supplier_key
    """
    return pd.read_sql_query(query, get_engine(), parse_dates=["return_date"])
