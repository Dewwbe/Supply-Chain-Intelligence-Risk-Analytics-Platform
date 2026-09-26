"""Phase 2 load entrypoint: raw -> staging -> warehouse.

`run()` takes optional pre-computed inputs (that's what `etl/run_local.py`
passes, to avoid re-extracting/re-transforming). Called with no arguments —
as `airflow/dags/gulfmart_pipeline.py` does — it re-derives everything
itself, the same self-sufficiency pattern as `etl.validate`.
"""

from __future__ import annotations

import pandas as pd
from etl.load.staging import load_staging
from etl.load.warehouse import load_warehouse
from src.common.logging import get_logger

logger = get_logger(__name__)


def run(
    sales_lines: pd.DataFrame | None = None,
    olist_frames: dict[str, pd.DataFrame] | None = None,
    dataco_frames: dict[str, pd.DataFrame] | None = None,
    uae_trade_frames: dict[str, pd.DataFrame] | None = None,
) -> None:
    """Load staging tables from the raw extracts, then upsert the warehouse from sales_lines."""
    if olist_frames is None or dataco_frames is None or uae_trade_frames is None:
        from etl.extract import dataco, olist, uae_open_data

        olist_frames = olist_frames or olist.run()
        dataco_frames = dataco_frames or dataco.run()
        uae_trade_frames = uae_trade_frames or uae_open_data.run()

    if sales_lines is None:
        from etl.transform import spark_transform

        sales_lines = spark_transform.run()

    load_staging(olist_frames, dataco_frames, uae_trade_frames)
    load_warehouse(sales_lines)
    logger.info("etl_load_done", rows=len(sales_lines))
