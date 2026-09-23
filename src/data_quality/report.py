"""Builds and saves the Phase 1 data-quality report table.

One row per dataset: rows, columns, missing %, duplicate rows, critical/
warning issue counts, and a verdict — the exact table required by the PRD's
Phase 1 deliverable.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.data_quality.checks import CRITICAL, DQIssue
from src.data_quality.profiler import DatasetProfile

FAIL = "FAIL"
WARN = "WARN"
PASS = "PASS"


def _verdict(issues: list[DQIssue]) -> str:
    """FAIL if any critical issue exists, WARN if only warnings exist, else PASS."""
    if any(issue.severity == CRITICAL for issue in issues):
        return FAIL
    if issues:
        return WARN
    return PASS


def build_quality_report(
    profiles: list[DatasetProfile], issues_by_dataset: dict[str, list[DQIssue]]
) -> pd.DataFrame:
    """Assemble the summary data-quality report table.

    Args:
        profiles: one `DatasetProfile` per dataset.
        issues_by_dataset: dataset name -> list of `DQIssue` found for it.

    Returns:
        A DataFrame with columns: dataset, rows, columns, missing_pct,
        duplicate_rows, critical_issues, warning_issues, verdict.
    """
    rows = []
    for profile in profiles:
        issues = issues_by_dataset.get(profile.dataset_name, [])
        rows.append(
            {
                "dataset": profile.dataset_name,
                "rows": profile.n_rows,
                "columns": profile.n_cols,
                "missing_pct": round(profile.overall_missing_pct, 2),
                "duplicate_rows": profile.n_duplicate_rows,
                "critical_issues": sum(i.count for i in issues if i.severity == CRITICAL),
                "warning_issues": sum(i.count for i in issues if i.severity != CRITICAL),
                "verdict": _verdict(issues),
            }
        )
    return pd.DataFrame(rows)


def save_report(report_df: pd.DataFrame, out_dir: Path) -> tuple[Path, Path]:
    """Write the report as both CSV and Markdown, creating `out_dir` if needed.

    Returns:
        (csv_path, markdown_path)
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / "data_quality_report.csv"
    md_path = out_dir / "data_quality_report.md"

    report_df.to_csv(csv_path, index=False)
    md_path.write_text(
        "# Data Quality Report — Phase 1\n\n" + report_df.to_markdown(index=False) + "\n",
        encoding="utf-8",
    )
    return csv_path, md_path


def save_issues(issues_by_dataset: dict[str, list[DQIssue]], out_dir: Path) -> Path:
    """Write every individual issue (one row per finding) to a CSV for drill-down."""
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "data_quality_issues.csv"
    rows = [
        {
            "dataset": i.dataset,
            "check": i.check,
            "column": i.column,
            "severity": i.severity,
            "count": i.count,
            "detail": i.detail,
        }
        for issues in issues_by_dataset.values()
        for i in issues
    ]
    pd.DataFrame(rows).to_csv(path, index=False)
    return path
