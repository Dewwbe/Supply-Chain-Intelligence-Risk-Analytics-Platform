.PHONY: setup db-up db-down migrate download-data profile etl api test lint format typecheck

setup:
	python -m venv .venv
	. .venv/bin/activate && pip install -r requirements.txt
	. .venv/bin/activate && pre-commit install

db-up:
	docker compose up -d postgres redis

db-down:
	docker compose down

migrate:
	for f in database/schema/*.sql; do \
		psql "$$DATABASE_URL" -f $$f; \
	done

download-data:
	python -m etl.extract.download_raw --all

profile:
	jupyter nbconvert --to notebook --execute --inplace notebooks/01_data_profiling.ipynb

etl:
	python -m etl.run_local

api:
	uvicorn src.api.main:app --reload

test:
	pytest

lint:
	ruff check src tests

format:
	black src tests

typecheck:
	mypy src
