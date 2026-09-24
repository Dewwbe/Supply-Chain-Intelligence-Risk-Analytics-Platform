"""Real historical Ramadan (Gregorian) date ranges, for the seasonality
hypothesis test in notebooks/02_sales_eda.ipynb.

These are widely published Gregorian equivalents of the Islamic lunar
calendar (commonly cited estimates; the exact start can shift by a day
depending on local moon sighting, which is why a range is used, not a
single date). This is a real calendrical fact being looked up, not
fabricated data — unlike `dim_date.is_uae_holiday`/`season_label`, which
were deliberately left unset in `etl/transform/dates.py` because *that*
would require assuming effects, not just dates. Only the years actually
covered by Olist+DataCo (2015-2018) are listed.
"""

from __future__ import annotations

import pandas as pd

RAMADAN_RANGES: list[tuple[str, str]] = [
    ("2015-06-18", "2015-07-16"),
    ("2016-06-06", "2016-07-05"),
    ("2017-05-27", "2017-06-24"),
    ("2018-05-16", "2018-06-14"),
]


def is_ramadan(date: pd.Timestamp) -> bool:
    """Whether `date` falls within a published Ramadan date range."""
    for start, end in RAMADAN_RANGES:
        if pd.Timestamp(start) <= date <= pd.Timestamp(end):
            return True
    return False


def label_ramadan(dates: pd.Series) -> pd.Series:
    """Vectorized `is_ramadan` over a Series of dates, returning 'Ramadan'/'Non-Ramadan'."""
    return dates.apply(lambda d: "Ramadan" if is_ramadan(d) else "Non-Ramadan")
