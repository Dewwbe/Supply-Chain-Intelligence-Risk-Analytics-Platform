"""Data access for demand forecasting: product selection and weekly series.

Only real `fact_sales` quantities are used here — forecasting is
demonstrative PUBLIC data, no synthetic component (docs/business_requirements.md
§7: "Forecasting... models are demonstrative at this data volume").
"""

from __future__ import annotations

import pandas as pd

from src.common.db import get_engine

MIN_WEEKS_OF_HISTORY = 100  # enough for ~2 full annual cycles at weekly grain


def select_top_products(n: int = 8, min_weeks: int = MIN_WEEKS_OF_HISTORY) -> pd.DataFrame:
    """Top `n` products by total quantity sold, restricted to products with at
    least `min_weeks` of history — a short-lived best-seller doesn't have enough
    history for weekly seasonal modeling, however high its volume.
    """
    query = """
        SELECT
            dp.product_source_id,
            dp.product_name,
            SUM(fs.quantity) AS total_quantity,
            MIN(dd.full_date) AS min_date,
            MAX(dd.full_date) AS max_date,
            (MAX(dd.full_date) - MIN(dd.full_date)) / 7 AS weeks_span
        FROM warehouse.fact_sales fs
        JOIN warehouse.dim_product dp ON dp.product_key = fs.product_key
        JOIN warehouse.dim_date dd ON dd.date_key = fs.date_key
        GROUP BY dp.product_source_id, dp.product_name
        HAVING (MAX(dd.full_date) - MIN(dd.full_date)) / 7 >= %(min_weeks)s
        ORDER BY total_quantity DESC
        LIMIT %(n)s
    """
    return pd.read_sql_query(
        query,
        get_engine(),
        params={"min_weeks": min_weeks, "n": n},
        parse_dates=["min_date", "max_date"],
    )


def load_daily_demand(product_source_id: str) -> pd.Series:
    """Daily quantity sold for one product, 0-filled over its own observed date range."""
    query = """
        SELECT dd.full_date AS date, SUM(fs.quantity) AS quantity
        FROM warehouse.fact_sales fs
        JOIN warehouse.dim_product dp ON dp.product_key = fs.product_key
        JOIN warehouse.dim_date dd ON dd.date_key = fs.date_key
        WHERE dp.product_source_id = %(product_source_id)s
        GROUP BY dd.full_date
        ORDER BY dd.full_date
    """
    df = pd.read_sql_query(
        query, get_engine(), params={"product_source_id": product_source_id}, parse_dates=["date"]
    )
    daily = df.set_index("date")["quantity"]
    full_range = pd.date_range(daily.index.min(), daily.index.max(), freq="D")
    return daily.reindex(full_range, fill_value=0)


def to_weekly(daily: pd.Series) -> pd.Series:
    """Resample a daily series to weekly totals (week ending Sunday)."""
    return daily.resample("W").sum()


def load_weekly_demand(product_source_id: str) -> pd.Series:
    """Weekly quantity sold for one product — the grain every model in this
    package forecasts at. Daily demand is noisy (many zero-sale days even
    for a top seller) and 143 weeks gives ~2.7 annual cycles for seasonal
    models; daily would give ~1000 points but far less usable seasonal
    signal, so weekly is the forecasting grain per the Phase 6 spec.
    """
    return to_weekly(load_daily_demand(product_source_id))
