.PHONY: setup infra up down reset download-data etl api test test-unit lint format typecheck ci migrate profile report

# --- environment ------------------------------------------------------------
setup:            ## venv + all dev dependencies + git hooks
	python -m venv .venv
	. .venv/bin/activate && pip install -r requirements.txt
	. .venv/bin/activate && pre-commit install

# --- services (docker-compose.yml) ---------------------------------------------
infra:            ## postgres + redis only (for local ETL / dev server)
	docker compose up -d --wait postgres redis

up:               ## postgres + redis + api, built from source
	docker compose up -d --build --wait

down:
	docker compose down

reset:            ## also deletes the database volume (re-runs schema + seeds on next start)
	docker compose down -v

# --- data -----------------------------------------------------------------
download-data:    ## Olist + DataCo via Kaggle (needs KAGGLE_* in .env)
	python -m etl.extract.download_raw --all

etl:              ## extract -> validate -> transform -> load the warehouse
	python -m etl.run_local

migrate:          ## only for a non-Docker Postgres; the container applies these itself
	for f in database/schema/*.sql database/seed/*.sql; do psql "$$DATABASE_URL" -f $$f; done

profile:
	jupyter nbconvert --to notebook --execute --inplace notebooks/01_data_profiling.ipynb

report:           ## Phase 11 executive report (PDF)
	python reports/executive_report/build_report.py

# --- app ---------------------------------------------------------------------
api:              ## dev server with auto-reload on http://localhost:8000/docs
	uvicorn src.api.main:app --reload

# --- quality (same commands as .github/workflows/ci.yml) ------------------------
lint:
	ruff check .
	black --check .

format:
	ruff check --fix .
	black .

typecheck:
	mypy src

test:
	pytest -rs --cov=src --cov-fail-under=80

test-unit:
	pytest tests/unit

ci: lint typecheck test
