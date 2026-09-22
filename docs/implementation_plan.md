# Implementation Plan

Twelve-week build order. Each phase produces a committed, working artifact —
never skip ahead to Power BI before the warehouse exists.

| Week | Phase | Deliverable | Key files |
|---|---|---|---|
| 1 | Business requirements + KPI dictionary | Stakeholder needs, KPI definitions | `docs/business_requirements.md`, `docs/kpi_dictionary.md` |
| 2 | Data acquisition + profiling | Olist, DataCo, UAE trade/CPI downloaded; `01_data_profiling.ipynb` run | `data/raw/`, `notebooks/01_data_profiling.ipynb` |
| 3 | ETL + PostgreSQL | Raw → staging → warehouse load working end-to-end | `etl/`, `database/schema/` |
| 4 | Star schema + SQL analytics | 30–40 queries, dims/facts finalized | `sql/`, `database/schema/warehouse.sql` |
| 5 | Python EDA + statistics | Hypothesis tests documented (H0/H1/test/p/interpretation) | `notebooks/02_sales_eda.ipynb`–`05_logistics_analysis.ipynb` |
| 6–7 | Forecasting | 4 models compared with time-based split, MAE/RMSE/MAPE/WAPE + intervals | `src/forecasting/` |
| 8 | Supplier risk + anomaly detection | Weighted risk score; IQR/Z-score/Isolation Forest | `src/supplier_risk/`, `src/anomaly_detection/` |
| 9 | Scenario engine | Demand/lead-time/cost simulator with baseline vs scenario output | `src/scenario_model/` |
| 10 | Power BI + DAX + Excel | 5-page report, validated against Excel workbook | `powerbi/`, `excel/` |
| 11 | Executive report | 10–15 page PDF, evidence-based recommendations | `reports/` |
| 12 | Software hardening | Tests, Docker, CI, Airflow DAG, docs pass | `tests/`, `.github/workflows/`, `airflow/dags/` |

## Definition of done, per phase

- **ETL (wk 3):** `make etl` runs clean on a fresh clone; failed-row counts
  logged, not silently dropped.
- **SQL (wk 4):** every query has a one-line business question as a comment
  header; window-function queries reviewed for correctness on a known slice.
- **Forecasting (wk 6–7):** no model is declared "winner" before the
  evaluation table (§17 of the original spec) is complete; split is
  time-based, never random.
- **Risk/anomaly (wk 8):** risk score is interpretable (documented weights),
  ML comparison is optional and clearly labeled as such.
- **Power BI (wk 10):** every DAX measure traces to a KPI in
  `docs/kpi_dictionary.md` — no orphan measures.
- **Software (wk 12):** `make test` and the CI pipeline both pass on a clean
  clone with no local state.

## Suggested order inside a week (example: Week 3, ETL)

1. Write `etl/extract/` readers for each source (Olist CSVs, DataCo CSV, UAE
   Open Data API).
2. Write `etl/validate/` checks (schema, nulls, PK uniqueness, negative
   values, date sanity) — fail loud, log to `data_quality_report`.
3. Write `etl/transform/` (pandas for small tables, `spark_transform.py` for
   the Olist+DataCo join).
4. Write `etl/load/` (idempotent upserts into `staging`, then `warehouse`).
5. Wire it into `airflow/dags/gulfmart_pipeline.py` last, once the one-shot
   script (`make etl`) works.
