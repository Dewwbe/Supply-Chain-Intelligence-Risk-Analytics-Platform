"""Reader for the Olist Brazilian E-Commerce dataset.

Parses the CSVs `etl/extract/download_raw.py` fetched into
`data/raw/olist/` into DataFrames. Does not clean, standardize, or validate
— that's `etl/transform/olist_transform.py` and `etl/validate/`.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from src.common.logging import get_logger

logger = get_logger(__name__)

RAW_DIR = Path("data/raw/olist")


def read_orders(raw_dir: Path = RAW_DIR) -> pd.DataFrame:
    """Read olist_orders_dataset.csv."""
    return pd.read_csv(raw_dir / "olist_orders_dataset.csv")


def read_order_items(raw_dir: Path = RAW_DIR) -> pd.DataFrame:
    """Read olist_order_items_dataset.csv."""
    return pd.read_csv(raw_dir / "olist_order_items_dataset.csv")


def read_products(raw_dir: Path = RAW_DIR) -> pd.DataFrame:
    """Read olist_products_dataset.csv."""
    return pd.read_csv(raw_dir / "olist_products_dataset.csv")


def read_customers(raw_dir: Path = RAW_DIR) -> pd.DataFrame:
    """Read olist_customers_dataset.csv."""
    return pd.read_csv(raw_dir / "olist_customers_dataset.csv")


def read_category_translation(raw_dir: Path = RAW_DIR) -> pd.DataFrame:
    """Read product_category_name_translation.csv (has a UTF-8 BOM)."""
    return pd.read_csv(raw_dir / "product_category_name_translation.csv", encoding="utf-8-sig")


def run(raw_dir: Path = RAW_DIR) -> dict[str, pd.DataFrame]:
    """Read every Olist table used by this pipeline, keyed by table name."""
    frames = {
        "orders": read_orders(raw_dir),
        "order_items": read_order_items(raw_dir),
        "products": read_products(raw_dir),
        "customers": read_customers(raw_dir),
        "category_translation": read_category_translation(raw_dir),
    }
    for name, df in frames.items():
        logger.info("olist_read", table=name, rows=len(df))
    return frames
