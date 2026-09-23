# ETL

- `extract/download_raw.py` — Phase 1 data acquisition: fetches raw files
  onto disk under `data/raw/` (Kaggle CLI for Olist/DataCo/M5, throttled
  HTTP for UAE Open Data). Run via `make download-data`. It does not parse
  or validate anything — see `notebooks/01_data_profiling.ipynb` for that.
- `extract/{olist,dataco,uae_open_data}.py` (Phase 2) — one reader module
  per source, parsing the files `download_raw.py` fetched into DataFrames
  for the pipeline. `m5.py` isn't implemented yet — M5 is pulled in Phase 6
  (see `etl/extract/download_raw.py`'s `phase1_core=False`). `uae_open_data.py`
  is the only module using `src/common/http.py`'s throttled client, and only
  via its opt-in `fetch_latest()` — the default `run()` reads the file Phase 1
  already downloaded, so routine ETL runs don't re-poll the UAE Open Data
  portal.
- `transform/` — `dates.py`/`currency.py`/`master_data.py` hold the pure
  standardization logic (parseable dates, FX-to-AED, MDM alias tables +
  the synthetic emirate assignment — see `docs/data_dictionary.md`).
  `olist_transform.py`/`dataco_transform.py` map each source into one
  common "sales line" shape. `spark_transform.py` is the one PySpark
  entrypoint (see root README §4): it does the actual Olist 4-way join
  (orders + order_items + products + customers) in Spark, then unions the
  result with DataCo into the unified sales-lines table.
- `validate/` — `schema_checks.py` reuses Phase 1's `src/data_quality/`
  (nulls, negative values, impossible dates, duplicates, outliers) against
  the sales-lines table; `referential.py` adds the FK-style checks Phase 1
  didn't need (emirate/source_system membership, natural-key nullness).
  `generate_quality_report()` writes both the CSV/MD report and a
  `staging.data_quality_report` table.
- `load/` — `staging.py` does an idempotent raw -> staging load
  (TRUNCATE + insert; staging is a full-refresh mirror, not incremental).
  `warehouse.py` does the staging -> warehouse upserts
  (`INSERT ... ON CONFLICT DO UPDATE` on each table's natural key), then
  resolves surrogate keys for the fact tables.

## Known scope limits (Phase 2)

- `fact_inventory` isn't populated — neither Olist nor DataCo has stock-level
  data, and fabricating it isn't in scope here (see docs/implementation_plan.md).
- `fact_shipments` is DataCo-only — Olist has no scheduled/real shipping-day
  columns. `dim_supplier` (from DataCo's 11 departments) and `dim_warehouse`
  (5 rows, one per emirate) are both disclosed relabelings, same convention
  as the emirate assignment — see `docs/data_dictionary.md`.
- `transport_cost` on `fact_shipments` is always `NULL` — DataCo has no cost
  column to source it from.
- `staging.uae_trade` is loaded but not yet joined into the star schema —
  that's Phase 4 (SQL analytics / macro correlation).

## Local dev note (Windows)

Running `spark_transform.py` locally on Windows needs:
- `JAVA_HOME` pointed at JDK 17 (Spark 3.5.x doesn't work with newer JDKs —
  you'll see `getSubject is supported only if a security manager is allowed`).
- `PYSPARK_PYTHON`/`PYSPARK_DRIVER_PYTHON` set to the venv's `python.exe`
  (otherwise the Python worker fails to start and you'll see
  `SocketTimeoutException: Accept timed out`).
- The `winutils.exe`/`HADOOP_HOME` warning at startup is harmless for local
  file access at this project's scale; ignore it.

None of this affects CI: the test suite doesn't exercise `spark_transform.py`
directly (`tests/unit/test_transform_shape.py` covers `olist_transform.py`/
`dataco_transform.py`'s pure logic instead), so no JVM is needed there. The
Dockerfile currently builds the FastAPI service only (`src/`, no `etl/`, no
JDK) — running the full ETL pipeline in a container is a Phase 12 hardening
item, not done yet.

Run the whole thing locally with `make etl` (`python -m etl.run_local`); in
deployment it's orchestrated by `airflow/dags/gulfmart_pipeline.py`.
