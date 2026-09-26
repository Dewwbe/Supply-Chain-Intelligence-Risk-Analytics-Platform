"""Synthetic fact_inventory — the one real simulator in this package.

Neither Olist nor DataCo tracks stock levels at all. Scoped to the top
`TOP_N_PRODUCTS` products by total quantity sold (not all ~33k products):
long-tail SKUs with a handful of lifetime sales don't produce meaningful
stockout/turnover analytics, and simulating daily stock for all of them
would be ~30M+ rows for no analytical benefit — a stated scope limit, not
a silent drop (see docs/data_dictionary.md).

Each product is assigned one primary warehouse (same weighted-emirate-hash
pattern as `etl/transform/master_data.assign_emirate`), then walked
day-by-day over its own observed sales date range with a simple (s, S)
reorder-point policy. `sold_quantity` each day comes from real, aggregated
`fact_sales` quantities — only the stock-level bookkeeping is simulated.
"""

from __future__ import annotations

import pandas as pd
from etl.synthesize.rng import hash_to_range
from etl.transform.master_data import assign_emirate

TOP_N_PRODUCTS = 500

# (s, S) policy expressed as multiples of average daily demand.
REORDER_POINT_DAYS = 7
TARGET_STOCK_DAYS = 30
INITIAL_STOCK_DAYS = 14
MIN_LEAD_DAYS = 3
MAX_LEAD_DAYS = 14


def _select_top_products(sales_lines: pd.DataFrame) -> pd.DataFrame:
    totals = (
        sales_lines.groupby("product_source_id")
        .agg(
            total_quantity=("quantity", "sum"),
            min_date=("order_date", "min"),
            max_date=("order_date", "max"),
        )
        .reset_index()
    )
    return totals.sort_values("total_quantity", ascending=False).head(TOP_N_PRODUCTS)


def _simulate_one_product(product_source_id: str, daily_sold: pd.Series) -> pd.DataFrame:
    """Walk `daily_sold` (a full-range, 0-filled daily Series) forward with an (s, S) policy."""
    avg_daily_demand = max(daily_sold.mean(), 0.1)
    reorder_point = avg_daily_demand * REORDER_POINT_DAYS
    target_stock = avg_daily_demand * TARGET_STOCK_DAYS
    lead_time_days = round(
        hash_to_range(f"inv_lead_time:{product_source_id}", MIN_LEAD_DAYS, MAX_LEAD_DAYS)
    )

    stock = avg_daily_demand * INITIAL_STOCK_DAYS
    pending_arrival_day: int | None = None
    pending_qty = 0.0

    records = []
    for day_index, (date, sold_demand) in enumerate(daily_sold.items()):
        opening = stock
        received = pending_qty if pending_arrival_day == day_index else 0.0
        available = opening + received
        sold = min(available, sold_demand)
        closing = available - sold

        if closing <= reorder_point and pending_arrival_day is None:
            pending_qty = max(target_stock - closing, avg_daily_demand)
            pending_arrival_day = day_index + lead_time_days
        if pending_arrival_day == day_index:
            pending_arrival_day = None
            pending_qty = 0.0

        records.append(
            {
                "product_source_id": product_source_id,
                "date": date,
                "opening_stock": round(opening),
                "received_quantity": round(received),
                "sold_quantity": round(sold),
                "closing_stock": round(closing),
            }
        )
        stock = closing
    return pd.DataFrame(records)


def build_inventory(sales_lines: pd.DataFrame) -> pd.DataFrame:
    """Build the fact_inventory rows for the top products (see module docstring)."""
    top_products = _select_top_products(sales_lines)
    sales_by_day = sales_lines.groupby(
        ["product_source_id", sales_lines["order_date"].dt.normalize()]
    )["quantity"].sum()

    frames = []
    for row in top_products.itertuples():
        date_range = pd.date_range(row.min_date.normalize(), row.max_date.normalize(), freq="D")
        daily_sold = (
            sales_by_day.loc[row.product_source_id]
            if row.product_source_id in sales_by_day.index.get_level_values(0)
            else pd.Series(dtype=float)
        )
        daily_sold = daily_sold.reindex(date_range, fill_value=0.0)
        frames.append(_simulate_one_product(row.product_source_id, daily_sold))

    result = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    if result.empty:
        return result
    result["warehouse_emirate"] = result["product_source_id"].apply(
        lambda p: assign_emirate(f"inventory_warehouse:{p}")
    )
    return result
