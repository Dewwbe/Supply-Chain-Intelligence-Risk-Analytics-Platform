# Coding Standards

## Python
- **Formatting:** `black` (line length 100), enforced in CI and pre-commit.
- **Linting:** `ruff` (replaces flake8 + isort + several plugins).
- **Type checking:** `mypy --strict` on `src/`; notebooks and `etl/` scripts
  are exempt but should still carry type hints where practical.
- **Docstrings:** Google style, required on every public function/class in
  `src/`.
- **Imports:** absolute imports from `src.*`; no wildcard imports.
- **Config:** never hardcode connection strings, credentials, or API keys —
  use `src/common/config.py` (pydantic `BaseSettings`, reads `.env`).
- **Logging:** structured logging via `src/common/logging.py`
  (`structlog`); no bare `print()` in `src/` or `etl/`.

## SQL
- Snake_case identifiers, one statement per file under `sql/<domain>/`.
- Every query file starts with a comment: business question it answers.
- No `SELECT *` in committed queries.

## Git / commits
- Conventional commits (`feat:`, `fix:`, `docs:`, `refactor:`, `test:`,
  `chore:`).
- No direct commits to `main`; feature branches + PR, even solo — this is
  what the CI pipeline is for.
- `.env`, credentials, and `data/raw` are gitignored; never force-add them.

## Testing
- `pytest`, target ≥80% coverage on `src/`.
- Unit tests mock external I/O; integration tests use a disposable test
  database (`docker-compose.test.yml` or testcontainers).
- Every bug fix ships with a regression test.

## API design (`src/api/`)
- Versioned routes (`/api/v1/...`).
- Pydantic models for every request/response — no raw dicts.
- Errors return a consistent JSON shape (`src/api/core/errors.py`), never a
  bare stack trace.
- Rate limiting, caching and throttling are applied selectively — see
  README §5 — not blanket-applied to every route.

## Reviews
- Self-review checklist before merging: tests pass, lint clean, docstrings
  present, no secrets, migration reversible.
