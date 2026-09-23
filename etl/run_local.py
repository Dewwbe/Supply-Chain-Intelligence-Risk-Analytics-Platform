"""One-shot local ETL entrypoint — `make etl` / `python -m etl.run_local`.

Mirrors `airflow/dags/gulfmart_pipeline.py`'s task order (extract ->
validate -> transform -> load -> quality report) but runs sequentially in
one process, passing data directly between steps instead of via Airflow.
Per docs/implementation_plan.md's suggested Week 3 order, the Airflow DAG
is wired up last, once this script works — this is that script.
"""

from __future__ import annotations

import sys

from etl.extract import dataco, olist, uae_open_data
from etl.load import run as load_run
from etl.transform import spark_transform
from etl.validate import generate_quality_report, run_all_checks
from src.common.logging import configure_logging, get_logger
from src.data_quality.checks import CRITICAL

logger = get_logger(__name__)


def main() -> int:
    configure_logging()

    logger.info("etl_extract_start")
    olist_frames = olist.run()
    dataco_frames = dataco.run()
    uae_trade_frames = uae_open_data.run()

    logger.info("etl_transform_start")
    sales_lines = spark_transform.run(olist_frames, dataco_frames)

    logger.info("etl_validate_start")
    issues = run_all_checks(sales_lines)
    n_critical = sum(1 for i in issues if i.severity == CRITICAL)
    if n_critical:
        logger.warning("etl_validate_critical_issues", n_critical=n_critical)

    logger.info("etl_load_start")
    load_run(
        sales_lines=sales_lines,
        olist_frames=olist_frames,
        dataco_frames=dataco_frames,
        uae_trade_frames=uae_trade_frames,
    )

    logger.info("etl_quality_report_start")
    generate_quality_report(sales_lines)

    logger.info("etl_done", rows=len(sales_lines), critical_issues=n_critical)
    return 0


if __name__ == "__main__":
    sys.exit(main())
