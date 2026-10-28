"""Database engine, session factory and initialisation."""
from __future__ import annotations

from collections.abc import Generator
from datetime import UTC, datetime

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import settings


def _make_engine():
    url = settings.database_url
    if url.startswith("sqlite"):
        # SQLite is single-writer; a static single connection avoids
        # "database is locked" issues across threads in dev and tests.
        return create_engine(
            url,
            connect_args={"check_same_thread": False},
            poolclass=__import__("sqlalchemy.pool", fromlist=["StaticPool"]).StaticPool,
        )
    return create_engine(url)


engine = _make_engine()


@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_connection, _record):  # pragma: no cover - engine plumbing
    if engine.url.drivername.startswith("sqlite"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()


class Base(DeclarativeBase):
    pass


SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def utcnow() -> datetime:
    """Naive UTC timestamps everywhere (consistent for SQLite storage)."""
    return datetime.now(UTC).replace(tzinfo=None)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_all() -> None:
    from . import models  # noqa: F401  (ensures models are registered)
    Base.metadata.create_all(bind=engine)


def init_db() -> None:
    create_all()
    from .seed import seed_if_empty
    seed_if_empty()
