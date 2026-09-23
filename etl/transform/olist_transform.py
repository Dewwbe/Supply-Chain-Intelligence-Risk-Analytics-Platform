"""Transform raw Olist tables into the common sales-line shape.

Grain: one row per order line item (matches Olist's own `order_items`
grain — each unit is already its own row, so `quantity` is always 1 here).
The multi-table join (orders + order_items + products + customers +
category translation) is the "large join" done in Spark — see
`spark_transform.py`. This module holds the pure mapping/standardization
logic so it's unit-testable without a Spark session.
"""

from __future__ import annotations

import pandas as pd
from etl.transform.currency import convert_to_aed
from etl.transform.dates import parse_dates
from etl.transform.master_data import (
    assign_emirate,
    derive_delivery_status_from_dates,
    standardize_category_name,
    standardize_order_status,
)

SOURCE_SYSTEM = "olist"
ORIGINAL_CURRENCY = "BRL"

SALES_LINE_COLUMNS = [
    "source_system",
    "order_id",
    "order_line_item_id",
    "order_date",
    "customer_source_id",
    "product_source_id",
    "product_name",
    "product_category",
    "quantity",
    "unit_price_aed",
    "sales_amount_aed",
    "original_currency",
    "original_amount",
    "region_source",
    "emirate",
    "order_status",
    "delivery_status",
    "shipping_mode",
    "scheduled_ship_days",
    "real_ship_days",
    "source_department",  # DataCo only — feeds dim_supplier/fact_shipments; None for Olist
]


def translate_categories(
    products: pd.DataFrame, category_translation: pd.DataFrame
) -> pd.DataFrame:
    """Join products to their English category name, standardized to Title Case.

    Falls back to the raw Portuguese name (still standardized) when a
    category has no translation row, rather than dropping the product.
    """
    merged = products.merge(category_translation, on="product_category_name", how="left")
    english = merged["product_category_name_english"].fillna(merged["product_category_name"])
    merged["product_category"] = english.map(standardize_category_name)
    return merged


def join_sources(
    orders: pd.DataFrame,
    order_items: pd.DataFrame,
    products: pd.DataFrame,
    customers: pd.DataFrame,
    category_translation: pd.DataFrame,
) -> pd.DataFrame:
    """Pandas fallback for the 4-way Olist join. Prefer `spark_transform.join_olist`
    for the real pipeline (see its docstring) — this exists so `build_sales_lines`
    and unit tests don't require a Spark session.
    """
    orders = parse_dates(
        orders,
        [
            "order_purchase_timestamp",
            "order_delivered_customer_date",
            "order_estimated_delivery_date",
        ],
    )
    products = translate_categories(products, category_translation)

    return (
        order_items.merge(orders, on="order_id", how="inner")
        .merge(products, on="product_id", how="left")
        .merge(customers, on="customer_id", how="left")
    )


def finalize_sales_lines(df: pd.DataFrame) -> pd.DataFrame:
    """Map an already-joined wide Olist DataFrame to the common sales-line shape.

    `df` must carry the columns produced by `join_sources` (or the Spark
    equivalent in `spark_transform.join_olist`) — this function only does
    standardization/mapping, no joining, so it works identically whether
    the join was done in pandas or Spark.
    """
    is_cancelled = df["order_status"] == "canceled"
    region_source = "olist:" + df["customer_state"].fillna("UNKNOWN")

    out = pd.DataFrame(
        {
            "source_system": SOURCE_SYSTEM,
            "order_id": df["order_id"],
            "order_line_item_id": df["order_item_id"].astype(str),
            "order_date": df["order_purchase_timestamp"],
            "customer_source_id": df["customer_id"],
            "product_source_id": df["product_id"],
            # Olist has no real product name field (only category + dimensions);
            # this is a derived display label, not an observed product name.
            "product_name": df["product_category"].fillna("Unknown")
            + " - "
            + df["product_id"].str[:8],
            "product_category": df["product_category"].fillna("Unknown"),
            "quantity": 1,
            "unit_price_aed": df["price"].apply(lambda v: convert_to_aed(v, ORIGINAL_CURRENCY)),
            "sales_amount_aed": df["price"].apply(lambda v: convert_to_aed(v, ORIGINAL_CURRENCY)),
            "original_currency": ORIGINAL_CURRENCY,
            "original_amount": df["price"],
            "region_source": region_source,
            "emirate": region_source.apply(assign_emirate),
            "order_status": df["order_status"].apply(standardize_order_status),
            "delivery_status": [
                derive_delivery_status_from_dates(delivered, estimated, cancelled)
                for delivered, estimated, cancelled in zip(
                    df["order_delivered_customer_date"],
                    df["order_estimated_delivery_date"],
                    is_cancelled,
                    strict=False,
                )
            ],
            "shipping_mode": None,
            "scheduled_ship_days": None,
            "real_ship_days": None,
            "source_department": None,
        }
    )
    return out[SALES_LINE_COLUMNS]


def build_sales_lines(
    orders: pd.DataFrame,
    order_items: pd.DataFrame,
    products: pd.DataFrame,
    customers: pd.DataFrame,
    category_translation: pd.DataFrame,
) -> pd.DataFrame:
    """Pandas-only convenience: join_sources + finalize_sales_lines.

    Used by unit tests and as a non-Spark fallback; the real pipeline uses
    `spark_transform.join_olist` for the join instead (see its docstring).
    """
    joined = join_sources(orders, order_items, products, customers, category_translation)
    return finalize_sales_lines(joined)
