"""Phase 2 validation entrypoints.

`run_all_checks()` and `generate_quality_report()` take an optional
pre-computed sales-lines DataFrame (that's what `etl/run_local.py` passes,
to avoid recomputing the Spark join). Called with no arguments — as
`airflow/dags/gulfmart_pipeline.py` does — they recompute it themselves via
`etl.transform.spark_transform.run()`, so both callers work without needing
Airflow XCom to carry a large DataFrame between tasks.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from etl.validate.referential import run_all as run_referential_checks
from etl.validate.schema_checks import check_sales_lines
from src.common.db import get_engine
from src.common.logging import get_logger
from src.data_quality.checks import DQIssue
from src.data_quality.report import build_quality_report, save_issues, save_report

logger = get_logger(__name__)

REPORT_DIR = Path("reports/data_quality")


def _sales_lines(sales_lines: pd.DataFrame | None) -> pd.DataFrame:
    if sales_lines is not None:
        return sales_lines
    from etl.transform import spark_transform

    return spark_transform.run()


def run_all_checks(sales_lines: pd.DataFrame | None = None) -> list[DQIssue]:
    """Run every Phase 2 check (schema + referential) against the sales-lines frame."""
    df = _sales_lines(sales_lines)
    issues = [*check_sales_lines(df), *run_referential_checks(df)]
    logger.info("phase2_validation_done", n_issues=len(issues), n_rows=len(df))
    return issues


def generate_quality_report(sales_lines: pd.DataFrame | None = None) -> None:
    """Write the Phase 2 data-quality report (CSV/MD + a staging DB table)."""
    from src.data_quality.profiler import profile_dataframe

    df = _sales_lines(sales_lines)
    issues = run_all_checks(df)
    profile = profile_dataframe(df, "sales_lines")

    report_df = build_quality_report([profile], {"sales_lines": issues})
    csv_path, md_path = save_report(report_df, REPORT_DIR)
    issues_path = save_issues({"sales_lines": issues}, REPORT_DIR)
    logger.info("phase2_report_saved", csv=str(csv_path), md=str(md_path), issues=str(issues_path))

    report_df.to_sql(
        "data_quality_report", get_engine(), schema="staging", if_exists="replace", index=False
    )
