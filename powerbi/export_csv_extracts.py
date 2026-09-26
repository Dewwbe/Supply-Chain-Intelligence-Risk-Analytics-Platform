"""Exports every warehouse table the Power BI semantic model needs into
powerbi/data/*.csv (Phase 10).

Why CSV instead of a live Postgres connection: PostgreSQL.Database(...)
made Power BI Desktop refuse to open this model with "A composite model
cannot be used with entity based query sources" — confirmed (after 3
failed attempts at fixing the M query itself, including
Value.NativeQuery, and after removing every calculated table from the
model, which ruled out the initial "composite model" theory) that the
live connector itself is what Desktop classifies as an "entity based"
source, not any particular way of querying it. supplier_risk_scores,
the one table already sourced from a CSV via Csv.Document/File.Contents,
never hit this error across any of those attempts — that's the evidence
this works. Losing live-refresh-from-Postgres for a guaranteed-to-open
model is the right trade here.

Exports via `docker exec ... psql \copy`, not a network connection to
DATABASE_URL's host port — on this project's dev machine a native Windows
postgres.exe service also listens on 5432 (docker ps shows the container
"healthy" and correctly credentialed, but connections via the host port
were silently landing on the native service instead, failing auth for a
user that only exists in the container). Going straight through the
container's own process sidesteps that port conflict entirely, and
doesn't depend on knowing whichever host port is currently mapped.

Run (Windows, Docker container running: `docker compose up -d postgres`):
    python powerbi/export_csv_extracts.py [container_name]
Then in Desktop: Refresh — it re-reads these CSVs, not Postgres directly.
Re-run this script after `make etl` to pick up new data.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

OUT_DIR = Path(__file__).resolve().parent / "data"
DEFAULT_CONTAINER = "supply-chain-intelligence-risk-analytics-platform-postgres-1"

TABLES = [
    "dim_date",
    "dim_location",
    "dim_product",
    "dim_supplier",
    "dim_warehouse",
    "dim_customer",
    "dim_store",
    "dim_transport",
    "fact_sales",
    "fact_inventory",
    "fact_shipments",
    "fact_purchase_orders",
    "fact_returns",
]

# dim_date is the only table with boolean columns. \copy emits Postgres's
# own boolean text ('t'/'f'), which Power Query's type-logical conversion
# doesn't recognize (it expects TRUE/FALSE) -- every row failed that
# conversion as a result. Cast to text explicitly instead of `SELECT *`.
SELECTS = {
    "dim_date": (
        "SELECT date_key, full_date, day_of_week, month, quarter, year, "
        "CASE WHEN is_weekend THEN 'TRUE' ELSE 'FALSE' END AS is_weekend, "
        "CASE WHEN is_uae_holiday THEN 'TRUE' ELSE 'FALSE' END AS is_uae_holiday, "
        "season_label "
        "FROM warehouse.dim_date"
    ),
}


def main() -> None:
    container = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_CONTAINER
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for table in TABLES:
        out_path = OUT_DIR / f"{table}.csv"
        select = SELECTS.get(table, f"SELECT * FROM warehouse.{table}")
        query = f"\\copy ({select}) TO STDOUT WITH CSV HEADER"
        with open(out_path, "wb") as f:
            subprocess.run(
                [
                    "docker",
                    "exec",
                    # PGOPTIONS forces ISO (YYYY-MM-DD) date output for
                    # this session -- \copy otherwise emits dates in the
                    # session's default locale format (observed as
                    # DD/M/YYYY here), which Power Query's type-date
                    # conversion misreads for any day-of-month above 12.
                    "-e",
                    "PGOPTIONS=-c datestyle=ISO,YMD",
                    container,
                    "psql",
                    "-U",
                    "gulfmart",
                    "-d",
                    "gulfmart_analytics",
                    "-c",
                    query,
                ],
                stdout=f,
                check=True,
            )
        rows = sum(1 for _ in open(out_path, encoding="utf-8")) - 1
        print(f"  {table}: {rows:,} rows -> {out_path}")
    print(f"\nDone. {len(TABLES)} CSVs written to {OUT_DIR}")


if __name__ == "__main__":
    main()
