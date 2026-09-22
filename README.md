# UAE Supply Chain Data & Decision Intelligence Platform

**Simulated client:** GulfMart Retail Group (UAE) — a fictional retail/e-commerce
company across Dubai, Abu Dhabi, Sharjah, Ajman and Ras Al Khaimah.

**Purpose:** an end-to-end data engineering and decision-intelligence
platform, built as a real engagement rather than a Kaggle notebook: business
requirements → data → ETL → warehouse → analytics → ML → BI → decisions. It
pairs a full analytics core (star schema, SQL, Python EDA, forecasting,
Power BI) with a software engineering layer (FastAPI service, pytest,
Docker, GitHub Actions, Airflow) so it demonstrates both data engineering
and software engineering skills in one project.

Data sources are a documented mix of **public** (Olist, DataCo, M5, UAE Open
Data), **synthetic** (inventory, purchase orders, warehouses — generated from
distributions derived from the real datasets), and **derived** (KPIs,
risk scores, forecasts). This is stated explicitly, not implied.

---

## 1. Architecture

```
                         PUBLIC DATA SOURCES
                                 |
              +------------------+------------------+
              |                  |                  |
           Olist              DataCo               M5
        (transactions)     (logistics)        (forecasting)
              |                  |                  |
              +------------------+------------------+
                                 |
                    UAE Open Data (trade, CPI) -----+
                                 |                   |
                          Airflow-orchestrated       |
                               ETL (Python)          |
                                 |                   |
                    +------------+------------+      |
                    |                         |      |
              pandas/SQL path          PySpark path  |
              (row-level, small)     (large joins,    |
                                     feature eng.)    |
                    |                         |      |
                    +------------+------------+      |
                                 |                    |
                        DATA QUALITY ENGINE  <--------+
                                 |
                        PostgreSQL (raw -> staging -> warehouse -> analytics)
                                 |
                          STAR SCHEMA
                                 |
              +------------------+------------------+
              |                  |                  |
        SQL Analytics       Python ML          Risk Analytics
      (KPIs, trends)   (forecast, anomaly)   (supplier risk score)
              |                  |                  |
              +------------------+------------------+
                                 |
                    +------------+-------------+
                    |                          |
              FastAPI service            Power BI / DAX / Excel
        (rate-limited, cached)        (Executive / Ops / Risk pages)
                    |                          |
                    +------------+-------------+
                                 |
                       Executive report + recommendations
```

## 2. Full repository layout

```
uae-supply-chain-intelligence/
├── data/{raw,processed,external}      # never committed except .gitkeep — see .gitignore
├── database/{schema,seed,migrations}  # DDL, star schema, seed/reference data
├── etl/{extract,transform,validate,load}
├── sql/01_data_quality … 07_kpi       # 30–40 analysis queries
├── notebooks/                         # profiling, EDA, modelling notebooks
├── src/
│   ├── api/                           # FastAPI service (see §3)
│   ├── forecasting/                   # Seasonal Naive, ETS, SARIMA, XGBoost
│   ├── anomaly_detection/             # IQR, Z-score, Isolation Forest
│   ├── supplier_risk/                 # weighted risk score
│   ├── scenario_model/                # demand/lead-time/cost simulator
│   └── common/                        # shared config, logging, db session
├── airflow/dags/                      # orchestration
├── powerbi/ excel/ reports/           # BI + management deliverables
├── tests/{unit,integration}
├── docs/                              # architecture, KPI & data dictionaries, backlog
├── .github/workflows/ci.yml           # lint, type-check, test, build
├── Dockerfile, docker-compose.yml
├── pyproject.toml, requirements.txt
├── .pre-commit-config.yaml
├── .env.example
└── Makefile
```

## 3. Software layer: what got rate limiting / caching / throttling, and why

Per the "don't add tech for keywords" rule this project holds itself to,
these controls are applied only where a real problem exists, not everywhere:

- **Rate limiting** (`slowapi`, in `src/api/middleware/rate_limit.py`) is
  applied to the public analytics endpoints (`/api/v1/*`) because they sit
  behind a KPI/forecast recompute path that is not free to call repeatedly.
  It is **not** applied to `/health`.
- **Caching** (`src/api/core/cache.py`, in-process TTL cache with a Redis
  backend swap-in) is applied to `/api/v1/kpis` and `/api/v1/forecast`
  specifically, because those recompute from the warehouse and are read far
  more often than the underlying data changes (daily ETL). It is **not**
  applied to `/api/v1/scenario`, which is intentionally a live, per-request
  calculation.
- **Throttling of outbound calls** (`src/common/http.py`, a token-bucket
  wrapper) is applied only in `etl/extract/` when pulling from UAE Open
  Data's public API, to stay within its fair-use limits — it is not applied
  to local file reads (Olist/DataCo/M5 are downloaded once, not polled).

## 4. Why PySpark and Airflow are here, and why Hadoop isn't

- **PySpark** is used in exactly one place — `etl/transform/spark_transform.py`
  — for the join/aggregate step across the Olist + DataCo transaction volumes
  where a distributed engine is a defensible choice, not decoration. Small,
  single-table cleaning stays in pandas.
- **Airflow** orchestrates the daily pipeline (`airflow/dags/gulfmart_pipeline.py`)
  to demonstrate automated, scheduled workflows for moving and processing
  data end to end.
- **Hadoop** is deliberately omitted: nothing in this architecture needs a
  distributed filesystem at this data volume, and adding it would be
  resume-keyword padding rather than an architectural decision — the kind of
  thing this project is designed to avoid (see `docs/architecture.md` §"technology
  justification").

## 5. Getting started

```bash
git clone <repo-url> && cd uae-supply-chain-intelligence
cp .env.example .env
make setup        # creates venv, installs deps, installs pre-commit hooks
make db-up         # starts PostgreSQL via docker-compose
make migrate       # applies database/schema/*.sql
make etl           # runs the Airflow-less one-shot ETL for local dev
make api           # runs FastAPI locally on :8000
make test          # pytest, unit + integration
```

Full 12-week build plan: [`docs/implementation_plan.md`](docs/implementation_plan.md)
Coding standards: [`docs/coding_standards.md`](docs/coding_standards.md)
Data/KPI dictionaries: [`docs/data_dictionary.md`](docs/data_dictionary.md), [`docs/kpi_dictionary.md`](docs/kpi_dictionary.md)
