"""Per-dataset quality-check configuration for Phase 1 profiling.

Column names below reflect the public Kaggle dataset versions named in
`docs/data_dictionary.md` (Olist Brazilian E-Commerce, DataCo Smart Supply
Chain) at the time this was written. Kaggle dataset revisions occasionally
change column casing/spacing — verify each spec's `required_fields` /
`id_columns` against the actual downloaded CSV header (`df.columns.tolist()`
in `notebooks/01_data_profiling.ipynb`) before trusting the checks, and
adjust here if a column has moved. This file is the single place those
adjustments happen — checks.py and the notebook should not hardcode column
names.
"""

from __future__ import annotations

from src.data_quality.checks import DatasetSpec

DATASET_SPECS: dict[str, DatasetSpec] = {
    "olist_orders": DatasetSpec(
        name="olist_orders",
        required_fields=["order_id", "customer_id", "order_status", "order_purchase_timestamp"],
        id_columns=["order_id"],
        date_order_pairs=[
            ("order_purchase_timestamp", "order_delivered_customer_date"),
            ("order_purchase_timestamp", "order_estimated_delivery_date"),
        ],
    ),
    "olist_order_items": DatasetSpec(
        name="olist_order_items",
        required_fields=["order_id", "order_item_id", "product_id", "price"],
        id_columns=["order_id", "order_item_id"],
        non_negative_columns=["price", "freight_value"],
        outlier_columns=["price", "freight_value"],
    ),
    "olist_products": DatasetSpec(
        name="olist_products",
        required_fields=["product_id"],
        id_columns=["product_id"],
        non_negative_columns=["product_weight_g", "product_price"],
    ),
    "dataco_shipments": DatasetSpec(
        name="dataco_shipments",
        required_fields=["Order Id", "Order Item Quantity", "Order Status", "Delivery Status"],
        id_columns=["Order Id", "Order Item Id"],
        non_negative_columns=["Order Item Quantity", "Sales", "Order Item Product Price"],
        date_order_pairs=[("order date (DateOrders)", "shipping date (DateOrders)")],
        outlier_columns=["Sales", "Order Item Product Price", "Benefit per order"],
    ),
    "uae_trade": DatasetSpec(
        # FCSA SDMX dataflow DF_TRADE_EXP_COUNTRY_MTH: UAE monthly non-oil
        # exports by destination country, in AED. HS_SECTION/HS_CHAPTER are
        # always "_Z" in this dataflow (no commodity breakdown).
        name="uae_trade",
        required_fields=["REF_AREA", "COUNTRY", "TIME_PERIOD", "OBS_VALUE"],
        id_columns=["COUNTRY", "TIME_PERIOD", "TRADE_TYPE"],
        non_negative_columns=["OBS_VALUE"],
        outlier_columns=["OBS_VALUE"],
    ),
    "uae_cpi": DatasetSpec(
        name="uae_cpi",
        required_fields=[],
        id_columns=[],
    ),
}
