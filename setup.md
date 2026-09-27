# Setup

From a fresh clone to a running, loaded API in 9 commands. The
[README](README.md#download-and-run) has the short version; this page adds
prerequisites, what each step does, verification, optional components and
troubleshooting.

## 1. Prerequisites

| Tool | Version | Why |
|---|---|---|
| Git | any | clone the repo |
| Python | 3.11 | ETL, API, tests, notebooks |
| Docker Desktop (or Docker Engine + Compose v2.24+) | recent | PostgreSQL, Redis and the API containers |
| Java | 17 | PySpark runs the ETL's Olist join (`etl/transform/spark_transform.py`) |
| Kaggle account | free | API token to download the Olist and DataCo datasets |

Optional: Power BI Desktop (Windows) for the `.pbip` report, Microsoft Excel
(Windows) to rebuild the validation workbooks, Microsoft Edge to render the
executive report PDF.

**Kaggle token:** kaggle.com → *Settings* → *API* → *Create New Token*. Put
the username and key in `.env` (step 3); the download step passes them to
the Kaggle CLI. `~/.kaggle/kaggle.json` also works.

## 2. Clone to running

```bash
git clone https://github.com/Dewwbe/Supply-Chain-Intelligence-Risk-Analytics-Platform.git   # 1
cd Supply-Chain-Intelligence-Risk-Analytics-Platform                                        # 2
cp .env.example .env              # 3  then set KAGGLE_USERNAME / KAGGLE_KEY
python -m venv .venv              # 4
source .venv/bin/activate         # 5  Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt   # 6
docker compose up -d --wait postgres redis    # 7  schema + reference seeds applied on first start
python -m etl.extract.download_raw --all && python -m etl.run_local   # 8  download, then load the warehouse
docker compose up -d --build --wait api       # 9
```

Windows PowerShell: use `copy .env.example .env` for step 3. If activation is
blocked, run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once.

| Step | What happens |
|---|---|
| 7 | Starts Postgres 16 and Redis 7. On the first start (empty volume), `database/docker-init.sh` applies `database/schema/*.sql` and then the reference seeds in `database/seed/*.sql`. The warehouse's foreign keys depend on those seeds. |
| 8 | Downloads Olist and DataCo into `data/raw/` (about 300 MB unzipped), then runs extract → validate → transform (pandas + Spark) → load → data-quality report. The UAE trade/CPI sources need a hand-supplied URL, so they are skipped with a warning; nothing downstream depends on them. Expect several minutes. |
| 9 | Builds the API image (non-root, with a health check) and starts it on the compose network, using Redis as its shared cache. |

## 3. Verify

```bash
curl http://localhost:8000/health         # {"status":"ok"}                          liveness
curl http://localhost:8000/health/ready   # {"status":"ready","database":"ok",...}   readiness
curl http://localhost:8000/api/v1/kpis    # headline KPIs from the loaded warehouse
```

Open **http://localhost:8000/docs** for the interactive API. Every endpoint
can be tried from the browser there.

Readiness returns **503** with `"database": "empty (run the ETL)"` until
step 8 has run. The analytics routes return the same 503, with instructions,
not a crash.

## 4. Everyday commands

| Command | Does |
|---|---|
| `make api` | Dev server with auto-reload (uses `.env`, i.e. `localhost` Postgres/Redis) |
| `make test` | Full test suite with the ≥80% coverage gate, exactly as CI runs it |
| `make ci` | lint → type-check → test, the same gates as `.github/workflows/ci.yml` |
| `make format` | ruff --fix + black |
| `make down` / `make reset` | Stop the stack / also delete the database volume (re-inits on the next start) |
| `pre-commit install` | Run black, ruff, mypy and hygiene hooks on every commit |

Tests that need a loaded warehouse (`@pytest.mark.warehouse`) or Redis
(`@pytest.mark.redis`) skip automatically when those aren't reachable, so
`pytest` works on a laptop with nothing running.

## 5. Optional components

| Component | How |
|---|---|
| Power BI report | Run `python powerbi/export_csv_extracts.py`, then open `powerbi/GulfMart Supply Chain.pbip` in Power BI Desktop (see `powerbi/README.md`) |
| Excel validation workbooks | `python excel/build_kpi_validation.py` and `python excel/build_scenario_analysis.py` (Windows + Excel) |
| Executive report PDF | `make report` (needs the Power BI CSV extract and Microsoft Edge) |
| Notebooks | `jupyter lab`, then open `notebooks/01…09` in order |
| Airflow | Separate virtualenv: `pip install -r requirements-airflow.txt --constraint <URL in that file>`. `python -m etl.run_local` runs the same task order without it. |
| UAE trade data | `python -m etl.extract.download_raw --dataset uae_trade --url <UAE Open Data CSV URL>` |

## 6. Configuration

All settings are read once from environment variables or `.env` by
`src/api/core/config.py`. See `.env.example` for every variable and its
default. The ones you're most likely to change:

| Variable | Default | Notes |
|---|---|---|
| `DATABASE_URL` | `postgresql+psycopg://gulfmart:gulfmart@localhost:5432/gulfmart_analytics` | host-side URL; the `api` container overrides it to reach `postgres` |
| `POSTGRES_PORT` / `REDIS_PORT` / `API_PORT` | 5432 / 6379 / 8000 | host ports published by docker-compose.yml |
| `CACHE_BACKEND` | `memory` | `redis` for a cache shared across API workers (the container uses redis) |
| `RATE_LIMIT_DEFAULT` / `RATE_LIMIT_EXPENSIVE` | 60/minute / 10/minute | per client IP; the expensive tier covers forecast and anomalies |
| `LOG_LEVEL` | INFO | all logs are JSON lines on stdout |

## 7. Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `password authentication failed for user "gulfmart"` from the host (ETL, tests, `make api`), while `docker compose ps` shows Postgres healthy | Another Postgres, often a native Windows service, owns port 5432 and is answering instead of the container. Set `POSTGRES_PORT=5433` in `.env`, update `DATABASE_URL` to `…@localhost:5433/…`, then `docker compose up -d postgres`. |
| `port is already allocated` on `docker compose up` | Change `POSTGRES_PORT`, `REDIS_PORT` or `API_PORT` in `.env`. |
| Readiness shows `"database": "empty (run the ETL)"` | Run step 8. |
| `401 Unauthorized` from Kaggle | Token missing or expired. Set `KAGGLE_USERNAME`/`KAGGLE_KEY` in `.env`, or regenerate the token. |
| `JAVA_GATEWAY_EXITED` / `Java not found` during the ETL | Install Java 17 and make sure `java -version` works in the same shell (set `JAVA_HOME` if needed). |
| Seeds or schema missing after changing SQL files | Init scripts run only on an empty volume. `make reset` then `make infra` re-applies them (this deletes loaded data). |
| `429 Rate limit exceeded` | Wait a minute, or raise `RATE_LIMIT_*` in `.env` for local use. |
| `docker-init.sh: not found` or `bad interpreter` | The script was checked out with CRLF line endings. `.gitattributes` prevents this on a fresh clone. On an existing clone, run `git add --renormalize .` and check out again. |
