# ETL

- `extract/` — one reader module per source (olist.py, dataco.py, m5.py, uae_open_data.py).
  `uae_open_data.py` is the only one using `src/common/http.py`'s throttled client.
- `validate/` — schema, null, PK/FK, negative-value and date-sanity checks;
  writes to a `data_quality_report` table/CSV, never fails silently.
- `transform/` — pandas for small/medium tables; `spark_transform.py` for
  the Olist+DataCo join and feature engineering (see README §6).
- `load/` — idempotent upserts: raw -> staging -> warehouse.

Run the whole thing locally with `make etl`; in deployment it's orchestrated
by `airflow/dags/gulfmart_pipeline.py`.
