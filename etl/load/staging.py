"""Idempotent raw -> staging load: TRUNCATE + bulk insert per table.

Staging is a full-refresh mirror of the latest extract (not incremental),
so "idempotent" here means "re-running with the same input yields the same
staging contents" — simpler and sufficient, since staging isn't the layer
that needs upsert-by-natural-key (that's `warehouse.py`).
"""

from __future__ import annotations

import pandas as pd
from etl.transform.dates import parse_dates
from sqlalchemy import text
from src.common.db import get_engine
from src.common.logging import get_logger

logger = get_logger(__name__)

# DataCo's raw column names -> staging.dataco_shipments columns.
_DATACO_RENAME = {
    "Order Id": "order_id",
    "Order Item Id": "order_item_id",
    "order date (DateOrders)": "order_date",
    "shipping date (DateOrders)": "shipping_date",
    "Order Status": "order_status",
    "Delivery Status": "delivery_status",
    "Shipping Mode": "shipping_mode",
    "Days for shipping (real)": "days_for_shipping_real",
    "Days for shipment (scheduled)": "days_for_shipment_scheduled",
    "Order Customer Id": "customer_id",
    "Order Region": "order_region",
    "Order Country": "order_country",
    "Category Name": "category_name",
    "Department Name": "department_name",
    "Order Item Quantity": "order_item_quantity",
    "Sales": "sales",
    "Order Item Product Price": "order_item_product_price",
}

_UAE_TRADE_RENAME = {
    "REF_AREA": "ref_area",
    "COUNTRY": "country",
    "TRADE_TYPE": "trade_type",
    "TIME_PERIOD": "time_period",
    "OBS_VALUE": "obs_value",
}


def _truncate_and_insert(df: pd.DataFrame, table: str) -> None:
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE TABLE staging.{table}"))
        # chunksize keeps rows*columns comfortably under Postgres's 65535
        # bind-parameter-per-statement limit for our largest tables.
        df.to_sql(table, conn, schema="staging", if_exists="append", index=False, chunksize=1000)
    logger.info("staging_loaded", table=table, rows=len(df))


def load_olist(frames: dict[str, pd.DataFrame]) -> None:
    """Load the Olist extract dict (see etl.extract.olist.run()) into staging.*."""
    orders = parse_dates(
        frames["orders"],
        [
            "order_purchase_timestamp",
            "order_approved_at",
            "order_delivered_carrier_date",
            "order_delivered_customer_date",
            "order_estimated_delivery_date",
        ],
    )
    _truncate_and_insert(orders, "olist_orders")

    order_items = parse_dates(frames["order_items"], ["shipping_limit_date"])
    _truncate_and_insert(order_items, "olist_order_items")

    products = frames["products"][
        [
            "product_id",
            "product_category_name",
            "product_weight_g",
            "product_length_cm",
            "product_height_cm",
            "product_width_cm",
        ]
    ]
    _truncate_and_insert(products, "olist_products")

    customers = frames["customers"].copy()
    customers["customer_zip_code_prefix"] = customers["customer_zip_code_prefix"].astype(str)
    _truncate_and_insert(customers, "olist_customers")


def load_dataco(frames: dict[str, pd.DataFrame]) -> None:
    """Load the DataCo extract dict (see etl.extract.dataco.run()) into staging.dataco_shipments."""
    df = frames["shipments"].rename(columns=_DATACO_RENAME)
    columns = list(_DATACO_RENAME.values())
    df = parse_dates(df[columns], ["order_date", "shipping_date"]).copy()
    for col in ["order_id", "order_item_id", "customer_id"]:
        df[col] = df[col].astype(str)
    _truncate_and_insert(df, "dataco_shipments")


def load_uae_trade(frames: dict[str, pd.DataFrame]) -> None:
    """Load the UAE trade extract dict (see etl.extract.uae_open_data.run()) into staging.uae_trade."""
    df = frames["trade"].rename(columns=_UAE_TRADE_RENAME)
    df = df[list(_UAE_TRADE_RENAME.values())].copy()
    df["country"] = df["country"].astype(str)
    _truncate_and_insert(df, "uae_trade")


def load_staging(
    olist_frames: dict[str, pd.DataFrame],
    dataco_frames: dict[str, pd.DataFrame],
    uae_trade_frames: dict[str, pd.DataFrame],
) -> None:
    """Load every source's extract dict into its staging tables."""
    load_olist(olist_frames)
    load_dataco(dataco_frames)
    load_uae_trade(uae_trade_frames)
