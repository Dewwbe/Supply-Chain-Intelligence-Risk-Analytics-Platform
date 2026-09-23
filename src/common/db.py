"""Shared SQLAlchemy engine/session access, used by etl/load and src/api.

Nothing else should call `create_engine` directly — the URL comes from
`Settings.database_url` (src/api/core/config.py), never hardcoded.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.api.core.config import get_settings


@lru_cache
def get_engine() -> Engine:
    """Return a cached SQLAlchemy engine for the configured database."""
    return create_engine(get_settings().database_url, pool_pre_ping=True)


@lru_cache
def _session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine())


@contextmanager
def session_scope() -> Iterator[Session]:
    """Yield a Session, committing on success and rolling back on error."""
    session = _session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
