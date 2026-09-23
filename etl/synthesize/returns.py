"""Synthetic fact_returns — neither Olist nor DataCo records actual returns.

Samples a per-category return rate in [2%, 12%] (docs/kpi_dictionary.md's
"Return Rate" KPI already expected this table) against real fact_sales
lines: which lines are "returned" is synthetic, but the sales line itself,
its quantity and its amount are real.
"""

from __future__ import annotations

import pandas as pd
from etl.synthesize.rng import hash_choice, hash_to_range, hash_to_unit

MIN_RETURN_RATE = 0.02
MAX_RETURN_RATE = 0.12
MIN_DELAY_DAYS = 3
MAX_DELAY_DAYS = 20

REASONS = [
    "Defective item",
    "Wrong item shipped",
    "No longer needed",
    "Found better price",
    "Arrived too late",
]


def assign_return_rate(category: str) -> float:
    """Deterministic return rate for a product category."""
    return hash_to_range(f"return_rate:{category}", MIN_RETURN_RATE, MAX_RETURN_RATE)


def build_returns(sales_lines: pd.DataFrame) -> pd.DataFrame:
    """Sample returned lines from `sales_lines` (the common Phase 2 shape).

    Returns a DataFrame keyed by (source_system, order_id, order_line_item_id)
    so the loader can resolve it to the already-upserted fact_sales.sales_key.
    """
    df = sales_lines.copy()
    return_rate = df["product_category"].apply(assign_return_rate)
    key = df["source_system"] + ":" + df["order_id"] + ":" + df["order_line_item_id"]
    is_returned = key.apply(lambda k: hash_to_unit(f"is_returned:{k}")) < return_rate
    returned = df[is_returned].copy()
    if returned.empty:
        return returned.assign(return_date=[], reason=[], returned_quantity=[], refund_amount=[])

    returned_key = (
        returned["source_system"]
        + ":"
        + returned["order_id"]
        + ":"
        + returned["order_line_item_id"]
    )
    delay_days = returned_key.apply(
        lambda k: round(hash_to_range(f"return_delay:{k}", MIN_DELAY_DAYS, MAX_DELAY_DAYS))
    )
    returned["return_date"] = returned["order_date"] + pd.to_timedelta(delay_days, unit="D")
    returned["reason"] = returned_key.apply(lambda k: hash_choice(f"return_reason:{k}", REASONS))
    returned["returned_quantity"] = returned["quantity"]
    returned["refund_amount"] = returned["sales_amount_aed"]
    return returned[
        [
            "source_system",
            "order_id",
            "order_line_item_id",
            "return_date",
            "reason",
            "returned_quantity",
            "refund_amount",
        ]
    ]
