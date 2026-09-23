"""Transform the raw DataCo table into the common sales-line shape.

Grain: DataCo already ships at one-row-per-order-line-item, so this is a
column mapping + standardization pass, not a join — unlike Olist, which
needs the multi-table Spark join in `spark_transform.py`.
"""

from __future__ import annotations

import pandas as pd
from etl.transform.currency import convert_to_aed
from etl.transform.dates import parse_dates
from etl.transform.master_data import (
    assign_emirate,
    standardize_category_name,
    standardize_delivery_status,
    standardize_order_status,
    standardize_shipping_mode,
)
from etl.transform.olist_transform import SALES_LINE_COLUMNS

SOURCE_SYSTEM = "dataco"
ORIGINAL_CURRENCY = "USD"


def build_sales_lines(shipments: pd.DataFrame) -> pd.DataFrame:
    """Produce the common sales-line DataFrame for DataCo (see olist_transform.SALES_LINE_COLUMNS)."""
    df = parse_dates(shipments, ["order date (DateOrders)", "shipping date (DateOrders)"])
    region_source = "dataco:" + df["Order Region"].fillna("UNKNOWN")

    out = pd.DataFrame(
        {
            "source_system": SOURCE_SYSTEM,
            "order_id": df["Order Id"].astype(str),
            "order_line_item_id": df["Order Item Id"].astype(str),
            "order_date": df["order date (DateOrders)"],
            "customer_source_id": df["Order Customer Id"].astype(str),
            "product_source_id": df["Product Card Id"].astype(str),
            "product_name": df["Product Name"],
            "product_category": df["Category Name"].apply(standardize_category_name),
            "quantity": df["Order Item Quantity"],
            "unit_price_aed": df["Order Item Product Price"].apply(
                lambda v: convert_to_aed(v, ORIGINAL_CURRENCY)
            ),
            "sales_amount_aed": df["Sales"].apply(lambda v: convert_to_aed(v, ORIGINAL_CURRENCY)),
            "original_currency": ORIGINAL_CURRENCY,
            "original_amount": df["Sales"],
            "region_source": region_source,
            "emirate": region_source.apply(assign_emirate),
            "order_status": df["Order Status"].apply(standardize_order_status),
            "delivery_status": df["Delivery Status"].apply(standardize_delivery_status),
            "shipping_mode": df["Shipping Mode"].apply(standardize_shipping_mode),
            "scheduled_ship_days": df["Days for shipment (scheduled)"],
            "real_ship_days": df["Days for shipping (real)"],
            "source_department": df["Department Name"],
        }
    )
    return out[SALES_LINE_COLUMNS]
