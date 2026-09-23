"""Dataset-specific data-quality checks.

Covers the five checks required in Phase 1: nulls in required fields,
invalid values (e.g. negative quantity), impossible dates (delivery before
order), duplicate IDs, and outliers. Each check is independent and returns
`DQIssue` records rather than raising, so one bad column never stops the
rest of the profile — every failure is reported, not swallowed.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

CRITICAL = "critical"
WARNING = "warning"


@dataclass
class DatasetSpec:
    """Declares what "valid" means for one dataset, used to drive checks."""

    name: str
    required_fields: list[str] = field(default_factory=list)
    id_columns: list[str] = field(default_factory=list)
    non_negative_columns: list[str] = field(default_factory=list)
    date_order_pairs: list[tuple[str, str]] = field(default_factory=list)
    outlier_columns: list[str] = field(default_factory=list)


@dataclass
class DQIssue:
    """One data-quality finding."""

    dataset: str
    check: str
    column: str | None
    severity: str
    count: int
    detail: str


def check_required_nulls(df: pd.DataFrame, spec: DatasetSpec) -> list[DQIssue]:
    """Flag nulls in columns that must always be populated."""
    issues = []
    for col in spec.required_fields:
        if col not in df.columns:
            issues.append(
                DQIssue(spec.name, "required_null", col, CRITICAL, len(df), "column missing")
            )
            continue
        n_missing = int(df[col].isna().sum())
        if n_missing:
            issues.append(
                DQIssue(
                    spec.name,
                    "required_null",
                    col,
                    CRITICAL,
                    n_missing,
                    f"{n_missing} nulls in required field",
                )
            )
    return issues


def check_negative_values(df: pd.DataFrame, spec: DatasetSpec) -> list[DQIssue]:
    """Flag negative values in columns that should never be negative (quantity, price, cost)."""
    issues = []
    for col in spec.non_negative_columns:
        if col not in df.columns:
            continue
        n_negative = int((pd.to_numeric(df[col], errors="coerce") < 0).sum())
        if n_negative:
            issues.append(
                DQIssue(
                    spec.name,
                    "negative_value",
                    col,
                    CRITICAL,
                    n_negative,
                    f"{n_negative} negative values",
                )
            )
    return issues


def check_impossible_dates(df: pd.DataFrame, spec: DatasetSpec) -> list[DQIssue]:
    """Flag rows where an end date precedes its start date (e.g. delivery before order)."""
    issues = []
    for start_col, end_col in spec.date_order_pairs:
        if start_col not in df.columns or end_col not in df.columns:
            continue
        start = pd.to_datetime(df[start_col], errors="coerce")
        end = pd.to_datetime(df[end_col], errors="coerce")
        n_impossible = int(((end < start) & start.notna() & end.notna()).sum())
        if n_impossible:
            issues.append(
                DQIssue(
                    spec.name,
                    "impossible_date",
                    f"{end_col} < {start_col}",
                    CRITICAL,
                    n_impossible,
                    f"{n_impossible} rows with {end_col} before {start_col}",
                )
            )
    return issues


def check_duplicate_ids(df: pd.DataFrame, spec: DatasetSpec) -> list[DQIssue]:
    """Flag duplicate values on the column(s) that should uniquely identify a row."""
    issues: list[DQIssue] = []
    cols = [c for c in spec.id_columns if c in df.columns]
    if not cols:
        return issues
    n_duplicate = int(df.duplicated(subset=cols).sum())
    if n_duplicate:
        issues.append(
            DQIssue(
                spec.name,
                "duplicate_id",
                ", ".join(cols),
                CRITICAL,
                n_duplicate,
                f"{n_duplicate} duplicate rows on {cols}",
            )
        )
    return issues


def detect_outliers_iqr(
    df: pd.DataFrame, spec: DatasetSpec, multiplier: float = 1.5
) -> list[DQIssue]:
    """Flag values outside `multiplier` * IQR from Q1/Q3, per configured column."""
    issues = []
    for col in spec.outlier_columns:
        if col not in df.columns:
            continue
        series = pd.to_numeric(df[col], errors="coerce").dropna()
        if series.empty:
            continue
        q1, q3 = series.quantile(0.25), series.quantile(0.75)
        iqr = q3 - q1
        lower, upper = q1 - multiplier * iqr, q3 + multiplier * iqr
        n_outliers = int(((series < lower) | (series > upper)).sum())
        if n_outliers:
            issues.append(
                DQIssue(
                    spec.name,
                    "outlier_iqr",
                    col,
                    WARNING,
                    n_outliers,
                    f"{n_outliers} values outside [{lower:.2f}, {upper:.2f}]",
                )
            )
    return issues


def detect_outliers_zscore(
    df: pd.DataFrame, spec: DatasetSpec, threshold: float = 3.0
) -> list[DQIssue]:
    """Flag values with |z-score| above `threshold`, per configured column."""
    issues = []
    for col in spec.outlier_columns:
        if col not in df.columns:
            continue
        series = pd.to_numeric(df[col], errors="coerce").dropna()
        if series.empty or series.std() == 0:
            continue
        z = (series - series.mean()) / series.std()
        n_outliers = int((z.abs() > threshold).sum())
        if n_outliers:
            issues.append(
                DQIssue(
                    spec.name,
                    "outlier_zscore",
                    col,
                    WARNING,
                    n_outliers,
                    f"{n_outliers} values with |z| > {threshold}",
                )
            )
    return issues


def run_all_checks(df: pd.DataFrame, spec: DatasetSpec) -> list[DQIssue]:
    """Run every check for `spec` against `df` and return the combined issue list."""
    return [
        *check_required_nulls(df, spec),
        *check_negative_values(df, spec),
        *check_impossible_dates(df, spec),
        *check_duplicate_ids(df, spec),
        *detect_outliers_iqr(df, spec),
        *detect_outliers_zscore(df, spec),
    ]
