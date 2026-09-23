"""Synthetic fact_purchase_orders — supplier -> warehouse restocking, which
neither Olist nor DataCo records at all (they only have outbound
customer orders). Sized off each product's real sales velocity so
high-turnover products get more/larger restock orders, not an arbitrary
constant — "distributions derived from the real datasets" per
docs/business_requirements.md §5.

Scoped to DataCo rows only, since `dim_supplier` (departments) and
`source_department` only exist for DataCo (see etl/README.md).
"""

from __future__ import annotations

import pandas as pd
from etl.synthesize.product_cost import assign_unit_cost
from etl.synthesize.rng import hash_choice, hash_to_range, hash_to_unit
from etl.synthesize.supplier_terms import assign_lead_time_days

AVG_UNITS_PER_ORDER = 25
CANCELLED_RATE = 0.05
DELIVERED_STATUSES = ["Delivered", "Completed"]


def _po_source_id(supplier_source_id: str, product_source_id: str, emirate: str, index: int) -> str:
    # emirate is part of the group key (a product can sell in multiple
    # emirates) and must be part of the id, or two groups collide on the
    # same po_source_id within one insert batch.
    return f"PO-{supplier_source_id}-{product_source_id}-{emirate.replace(' ', '_')}-{index}"


def build_purchase_orders(sales_lines: pd.DataFrame) -> pd.DataFrame:
    """One row per synthetic restock order, grouped by (supplier, product, emirate)."""
    dataco = sales_lines[sales_lines["source_system"] == "dataco"].copy()
    dataco["supplier_source_id"] = "DEPT-" + dataco["source_department"].astype(str)

    grouped = dataco.groupby(["supplier_source_id", "product_source_id", "emirate"]).agg(
        total_quantity=("quantity", "sum"),
        min_date=("order_date", "min"),
        max_date=("order_date", "max"),
        category=("product_category", "first"),
    )

    rows = []
    for (supplier_source_id, product_source_id, emirate), group in grouped.iterrows():
        n_orders = max(1, round(group.total_quantity / AVG_UNITS_PER_ORDER))
        span_days = max(1, (group.max_date - group.min_date).days)
        for i in range(n_orders):
            key = f"{supplier_source_id}:{product_source_id}:{emirate}:{i}"
            offset_days = round(hash_to_range(f"po_offset:{key}", 0, span_days))
            order_date = group.min_date + pd.Timedelta(days=offset_days)
            lead_days = assign_lead_time_days(supplier_source_id)
            expected_delivery = order_date + pd.Timedelta(days=lead_days)

            is_cancelled = hash_to_unit(f"po_cancelled:{key}") < CANCELLED_RATE
            if is_cancelled:
                order_status = "Cancelled"
                actual_delivery = None
            else:
                order_status = hash_choice(f"po_status:{key}", DELIVERED_STATUSES)
                delivery_variance_days = round(hash_to_range(f"po_variance:{key}", -2, 5))
                actual_delivery = expected_delivery + pd.Timedelta(days=delivery_variance_days)

            quantity = max(
                1,
                round(
                    hash_to_range(
                        f"po_qty:{key}", AVG_UNITS_PER_ORDER * 0.5, AVG_UNITS_PER_ORDER * 1.5
                    )
                ),
            )

            rows.append(
                {
                    "po_source_id": _po_source_id(
                        supplier_source_id, product_source_id, emirate, i
                    ),
                    "supplier_source_id": supplier_source_id,
                    "product_source_id": product_source_id,
                    "emirate": emirate,
                    "order_date": order_date,
                    "expected_delivery_date": expected_delivery,
                    "actual_delivery_date": actual_delivery,
                    "order_status": order_status,
                    "quantity": quantity,
                }
            )

    result = pd.DataFrame(rows)
    if result.empty:
        return result
    category_by_product = dataco.drop_duplicates("product_source_id").set_index(
        "product_source_id"
    )["product_category"]
    unit_price_by_product = dataco.drop_duplicates("product_source_id").set_index(
        "product_source_id"
    )["unit_price_aed"]
    result["unit_cost"] = result["product_source_id"].map(
        lambda p: assign_unit_cost(category_by_product[p], unit_price_by_product[p])
    )
    result["total_cost"] = (result["quantity"] * result["unit_cost"]).round(2)
    return result
