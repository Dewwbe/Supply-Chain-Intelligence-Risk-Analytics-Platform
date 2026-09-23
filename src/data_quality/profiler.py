"""Generic dataset profiling: shape, dtypes, missingness, duplicates, numeric stats.

Deliberately dataset-agnostic — it describes whatever DataFrame it's given.
Dataset-specific rules (required fields, valid ranges, date ordering) live in
`checks.py` instead, driven by `dataset_specs.py`.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd


@dataclass
class NumericSummary:
    """Min/max/mean/median/std for one numeric column."""

    min: float
    max: float
    mean: float
    median: float
    std: float


@dataclass
class DatasetProfile:
    """Profile result for a single DataFrame."""

    dataset_name: str
    n_rows: int
    n_cols: int
    dtypes: dict[str, str]
    missing_count: dict[str, int]
    missing_pct: dict[str, float]
    n_duplicate_rows: int
    n_unique: dict[str, int]
    numeric_summary: dict[str, NumericSummary] = field(default_factory=dict)

    @property
    def overall_missing_pct(self) -> float:
        """Average missing-value percentage across all columns."""
        if not self.missing_pct:
            return 0.0
        return sum(self.missing_pct.values()) / len(self.missing_pct)


def profile_dataframe(df: pd.DataFrame, dataset_name: str) -> DatasetProfile:
    """Profile row/column counts, dtypes, missingness, duplicates, and numeric stats.

    Args:
        df: the DataFrame to profile.
        dataset_name: label used in the resulting profile and downstream report.

    Returns:
        A `DatasetProfile` describing `df`.
    """
    n_rows = len(df)
    missing_count = df.isna().sum().to_dict()
    missing_pct = {
        col: (count / n_rows * 100 if n_rows else 0.0) for col, count in missing_count.items()
    }
    dtypes = {col: str(dtype) for col, dtype in df.dtypes.items()}
    n_unique = df.nunique(dropna=True).to_dict()

    numeric_cols = df.select_dtypes(include="number").columns
    numeric_summary: dict[str, NumericSummary] = {}
    for col in numeric_cols:
        series = df[col].dropna()
        if series.empty:
            continue
        numeric_summary[col] = NumericSummary(
            min=float(series.min()),
            max=float(series.max()),
            mean=float(series.mean()),
            median=float(series.median()),
            std=float(series.std()) if len(series) > 1 else 0.0,
        )

    return DatasetProfile(
        dataset_name=dataset_name,
        n_rows=n_rows,
        n_cols=df.shape[1],
        dtypes=dtypes,
        missing_count={k: int(v) for k, v in missing_count.items()},
        missing_pct=missing_pct,
        n_duplicate_rows=int(df.duplicated().sum()),
        n_unique={k: int(v) for k, v in n_unique.items()},
        numeric_summary=numeric_summary,
    )


def profile_to_frame(profile: DatasetProfile) -> pd.DataFrame:
    """Flatten a `DatasetProfile` into a per-column DataFrame for display/export."""
    rows = []
    for col in profile.dtypes:
        summary = profile.numeric_summary.get(col)
        rows.append(
            {
                "column": col,
                "dtype": profile.dtypes[col],
                "missing_count": profile.missing_count[col],
                "missing_pct": round(profile.missing_pct[col], 2),
                "n_unique": profile.n_unique[col],
                "min": summary.min if summary else None,
                "max": summary.max if summary else None,
                "mean": summary.mean if summary else None,
                "median": summary.median if summary else None,
                "std": summary.std if summary else None,
            }
        )
    return pd.DataFrame(rows)
