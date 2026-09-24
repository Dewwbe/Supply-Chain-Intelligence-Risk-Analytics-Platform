"""Date standardization and `dim_date` population.

`season_label`/`is_uae_holiday` are populated from `src/common/uae_calendar.py`
(Phase 5) — real published Ramadan/Eid/National Day dates plus disclosed
Summer/Back-to-school/Year-end window definitions, covering 2015-2018 (the
years Olist+DataCo actually span). This only labels calendar days; whether
any of these categories actually correlates with demand is a question for
the hypothesis tests in notebooks/02_sales_eda.ipynb, never assumed here
(docs/business_requirements.md §7).
"""

from __future__ import annotations

import pandas as pd
from src.common.uae_calendar import is_uae_public_holiday, season_label


def parse_dates(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """Return a copy of `df` with `columns` parsed to pandas datetime (invalid -> NaT)."""
    df = df.copy()
    for col in columns:
        df[col] = pd.to_datetime(df[col], errors="coerce")
    return df


def date_key(value: pd.Timestamp) -> int | None:
    """Convert a timestamp to the warehouse.dim_date surrogate key (YYYYMMDD)."""
    if pd.isna(value):
        return None
    return int(value.strftime("%Y%m%d"))


def build_dim_date(start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    """Build one row per calendar day in [start, end] for warehouse.dim_date."""
    dates = pd.date_range(start.normalize(), end.normalize(), freq="D")
    return pd.DataFrame(
        {
            "date_key": [date_key(d) for d in dates],
            "full_date": dates.date,
            "day_of_week": dates.dayofweek,
            "month": dates.month,
            "quarter": dates.quarter,
            "year": dates.year,
            "is_weekend": dates.dayofweek.isin([4, 5]),  # UAE weekend: Fri/Sat
            "is_uae_holiday": [is_uae_public_holiday(d) for d in dates],
            "season_label": [season_label(d) for d in dates],
        }
    )
