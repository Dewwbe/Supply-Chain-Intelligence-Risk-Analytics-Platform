"""Reader for the UAE FCSA trade dataflow.

`read_trade()` reads the file `etl/extract/download_raw.py` (Phase 1)
already fetched to `data/raw/uae_trade/uae_trade.csv`. `fetch_latest()` is
an explicit, opt-in re-pull of that file via the throttled HTTP client —
this module is "the only one using src/common/http.py's throttled client"
(etl/README.md) because it is the sole external API this pipeline polls;
it is not called by `run()` automatically, since Phase 1 already fetched
the data once and re-fetching on every ETL run would poll the UAE Open
Data portal far more than needed.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from src.common.http import ThrottledClient
from src.common.logging import get_logger

logger = get_logger(__name__)

RAW_DIR = Path("data/raw/uae_trade")
FILENAME = "uae_trade.csv"


def read_trade(raw_dir: Path = RAW_DIR) -> pd.DataFrame:
    """Read the UAE FCSA DF_TRADE_EXP_COUNTRY_MTH export dataflow."""
    return pd.read_csv(raw_dir / FILENAME)


def fetch_latest(url: str, raw_dir: Path = RAW_DIR) -> Path:
    """Re-pull the trade CSV from `url` via the throttled client, overwriting the local copy.

    Opt-in only — see module docstring. Not part of `run()`.
    """
    raw_dir.mkdir(parents=True, exist_ok=True)
    dest_path = raw_dir / FILENAME
    client = ThrottledClient()
    try:
        logger.info("uae_trade_refresh_start", url=url)
        response = client.get(url)
        dest_path.write_bytes(response.content)
        logger.info("uae_trade_refresh_done", url=url, bytes=len(response.content))
    finally:
        client.close()
    return dest_path


def run(raw_dir: Path = RAW_DIR) -> dict[str, pd.DataFrame]:
    """Read the UAE trade table, keyed to match the other extract.run() shapes."""
    df = read_trade(raw_dir)
    logger.info("uae_trade_read", table="trade", rows=len(df))
    return {"trade": df}
