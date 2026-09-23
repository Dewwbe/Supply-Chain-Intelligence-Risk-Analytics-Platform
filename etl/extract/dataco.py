"""Reader for the DataCo Smart Supply Chain dataset.

Parses `data/raw/dataco/DataCoSupplyChainDataset.csv` into a DataFrame. The
public CSV is latin-1 encoded, not UTF-8 — see notebooks/01_data_profiling.ipynb
where this was first confirmed.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from src.common.logging import get_logger

logger = get_logger(__name__)

RAW_DIR = Path("data/raw/dataco")
FILENAME = "DataCoSupplyChainDataset.csv"


def read_shipments(raw_dir: Path = RAW_DIR) -> pd.DataFrame:
    """Read the DataCo dataset (one row per order line item)."""
    return pd.read_csv(raw_dir / FILENAME, encoding="latin-1", low_memory=False)


def run(raw_dir: Path = RAW_DIR) -> dict[str, pd.DataFrame]:
    """Read the DataCo table, keyed to match the shape of etl.extract.olist.run()."""
    df = read_shipments(raw_dir)
    logger.info("dataco_read", table="shipments", rows=len(df))
    return {"shipments": df}
