"""Integration test for the Phase 10 ground-truth KPI module — needs a
running Postgres with the warehouse populated (`make db-up && make etl`).
Skipped otherwise, per docs/coding_standards.md.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text
from src.common.db import get_engine
from src.kpi.summary import compute_kpi_summary


def _db_available() -> bool:
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _db_available(), reason="Postgres not reachable")


def test_compute_kpi_summary_returns_sane_real_values():
    summary = compute_kpi_summary()
    assert summary.total_revenue_aed > 0
    assert summary.total_units_sold > 0
    assert summary.gross_margin_aed != 0
    assert summary.average_order_value_aed > 0
    assert summary.inventory_value_aed > 0
    assert 0 <= summary.stockout_rate <= 1
    assert 0 <= summary.fill_rate <= 1
    assert 0 <= summary.supplier_otd <= 1
    assert summary.average_lead_time_days > 0
    assert summary.inventory_turnover > 0


def test_summary_matches_the_reference_sql():
    # sql/07_kpi/executive_summary.sql is the reference every implementation
    # traces to; the Python ground truth must agree with it on every KPI they
    # share, so a formula fixed in one place can't silently drift in the other.
    from pathlib import Path

    sql_path = Path(__file__).parents[2] / "sql" / "07_kpi" / "executive_summary.sql"
    with get_engine().connect() as conn:
        row = conn.execute(text(sql_path.read_text(encoding="utf-8"))).mappings().one()

    summary = compute_kpi_summary()
    assert summary.total_revenue_aed == pytest.approx(float(row["revenue_aed"]), abs=0.01)
    assert summary.gross_margin_aed == pytest.approx(float(row["gross_margin_aed"]), abs=0.01)
    assert summary.stockout_rate == pytest.approx(float(row["stockout_rate"]), abs=1e-4)
    assert summary.fill_rate == pytest.approx(float(row["fill_rate"]), abs=1e-4)
    assert summary.supplier_otd == pytest.approx(float(row["supplier_otd"]), abs=1e-4)


def test_inventory_value_matches_the_scenario_engines_baseline():
    # Both modules independently compute "current total inventory value" by
    # taking each product's own latest available snapshot (not one shared
    # date) — they should agree exactly, not just be in the same ballpark.
    from src.scenario_model.data import load_baseline

    summary = compute_kpi_summary()
    baseline = load_baseline()
    assert summary.inventory_value_aed == pytest.approx(baseline.inventory_value_aed, rel=1e-6)
