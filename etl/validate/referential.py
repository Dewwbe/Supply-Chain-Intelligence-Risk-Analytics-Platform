"""Referential-integrity checks that Phase 1's src/data_quality/checks.py
didn't need: does every standardized value actually resolve to something
the warehouse's reference tables (or FK targets) will accept? These run
before load, so a bad row is caught here with a readable message instead of
as a raw Postgres FK-violation error during `etl/load`.

Returns the same `DQIssue` shape as src/data_quality/checks.py so both
flow into one report.
"""

from __future__ import annotations

import pandas as pd
from src.data_quality.checks import CRITICAL, DQIssue

VALID_EMIRATES = {"Dubai", "Abu Dhabi", "Sharjah", "Ajman", "Ras Al Khaimah"}


def check_membership(
    df: pd.DataFrame,
    column: str,
    valid_values: set[str],
    dataset: str,
    check_name: str,
) -> list[DQIssue]:
    """Flag rows whose (non-null) `column` value isn't in `valid_values` — a would-be FK violation."""
    if column not in df.columns:
        return [DQIssue(dataset, check_name, column, CRITICAL, len(df), "column missing")]
    present = df[column].dropna()
    bad = present[~present.isin(valid_values)]
    if bad.empty:
        return []
    return [
        DQIssue(
            dataset,
            check_name,
            column,
            CRITICAL,
            len(bad),
            f"{len(bad)} values not in the allowed set, e.g. {sorted(bad.unique())[:5]}",
        )
    ]


def check_natural_key_not_null(
    df: pd.DataFrame, key_columns: list[str], dataset: str
) -> list[DQIssue]:
    """Flag rows with a null natural-key component — these can't be upserted."""
    issues = []
    for col in key_columns:
        n_null = int(df[col].isna().sum())
        if n_null:
            issues.append(
                DQIssue(
                    dataset,
                    "natural_key_null",
                    col,
                    CRITICAL,
                    n_null,
                    f"{n_null} rows have a null natural-key component",
                )
            )
    return issues


def run_all(sales_lines: pd.DataFrame, dataset: str = "sales_lines") -> list[DQIssue]:
    """Run every referential check against the unified sales-lines frame."""
    return [
        *check_natural_key_not_null(
            sales_lines, ["source_system", "order_id", "order_line_item_id"], dataset
        ),
        *check_membership(sales_lines, "emirate", VALID_EMIRATES, dataset, "fk_emirate"),
        *check_membership(
            sales_lines, "source_system", {"olist", "dataco"}, dataset, "fk_source_system"
        ),
    ]
