"""Engine/session management. Engine is created lazily so tests can override settings."""
from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Iterator, Optional

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.db.models import Base

log = logging.getLogger(__name__)

_engine: Optional[Engine] = None
_SessionLocal: Optional[sessionmaker] = None


def get_engine() -> Engine:
    global _engine, _SessionLocal
    if _engine is None:
        s = get_settings()
        if s.is_sqlite:
            _engine = create_engine(s.sqlalchemy_url, connect_args={"check_same_thread": False})

            @event.listens_for(_engine, "connect")
            def _fk_on(dbapi_conn, _):  # SQLite needs FK enforcement switched on for ON DELETE CASCADE
                dbapi_conn.execute("PRAGMA foreign_keys=ON")
        else:
            _engine = create_engine(
                s.sqlalchemy_url,
                pool_size=s.db_pool_size,
                max_overflow=s.db_max_overflow,
                pool_pre_ping=True,  # Neon suspends idle computes and drops connections
                pool_recycle=240,
                # Neon's pooled (pgbouncer) endpoints: avoid server-side prepared statements.
                connect_args={"prepare_threshold": None, "connect_timeout": 15},
            )
        _SessionLocal = sessionmaker(bind=_engine, autoflush=False, expire_on_commit=False)
    return _engine


def get_sessionmaker() -> sessionmaker:
    get_engine()
    assert _SessionLocal is not None
    return _SessionLocal


def reset_engine() -> None:
    """Dispose the engine (used by tests when settings change)."""
    global _engine, _SessionLocal
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _SessionLocal = None


def init_db() -> None:
    if get_settings().auto_create_tables:
        Base.metadata.create_all(get_engine())
        log.info("Database tables ensured")


@contextmanager
def session_scope() -> Iterator[Session]:
    """Transactional scope for background jobs (outside the request lifecycle)."""
    session = get_sessionmaker()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_db() -> Iterator[Session]:
    """FastAPI dependency."""
    session = get_sessionmaker()()
    try:
        yield session
    finally:
        session.close()
