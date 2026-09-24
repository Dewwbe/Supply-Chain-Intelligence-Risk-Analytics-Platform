"""Train/test splitting for forecasting — chronological only.

There is deliberately no random-split option anywhere in this module (not
even as an opt-in parameter): a random split leaks future information into
training for a time series and would silently invalidate every metric in
`evaluate.py`. Per docs/implementation_plan.md: "split is time-based, never
random."
"""

from __future__ import annotations

import pandas as pd


def time_based_split(series: pd.Series, test_size: int) -> tuple[pd.Series, pd.Series]:
    """Split `series` into (train, test), test being the last `test_size` points.

    Raises:
        ValueError: if `series` doesn't have enough points to leave a
            non-trivial training set.
    """
    if test_size <= 0:
        raise ValueError("test_size must be positive")
    if test_size >= len(series):
        raise ValueError(
            f"test_size ({test_size}) must be smaller than the series length ({len(series)})"
        )
    return series.iloc[:-test_size], series.iloc[-test_size:]
