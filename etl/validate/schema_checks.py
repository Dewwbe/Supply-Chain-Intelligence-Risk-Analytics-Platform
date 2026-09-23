"""Row-level data-quality checks for Phase 2, reusing Phase 1's
src/data_quality/checks.py rather than re-implementing null/negative-value/
duplicate/outlier detection.
"""

from __future__ import annotations

import pandas as pd
from src.data_quality.checks import DatasetSpec, DQIssue, run_all_checks

SALES_LINES_SPEC = DatasetSpec(
    name="sales_lines",
    required_fields=[
        "source_system",
        "order_id",
        "order_line_item_id",
        "order_date",
        "product_source_id",
        "quantity",
        "unit_price_aed",
        "sales_amount_aed",
        "emirate",
        "order_status",
    ],
    id_columns=["source_system", "order_id", "order_line_item_id"],
    non_negative_columns=["quantity", "unit_price_aed", "sales_amount_aed", "original_amount"],
    outlier_columns=["sales_amount_aed"],
)


def check_sales_lines(sales_lines: pd.DataFrame) -> list[DQIssue]:
    """Run Phase 1's generic checks against the unified sales-lines frame."""
    return run_all_checks(sales_lines, SALES_LINES_SPEC)
