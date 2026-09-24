"""
Database engine and session management.

Key changes vs v0.1:
- SQLite PRAGMAs enabled on every connection: foreign_keys, WAL,
  synchronous=NORMAL, busy_timeout=5000.
- get_db() rolls back on exception before closing the session.
"""

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import get_settings

settings = get_settings()

_is_sqlite = settings.db_url.startswith("sqlite")

connect_args = {}
if _is_sqlite:
    # FastAPI runs sync endpoints in a threadpool, so connections may
    # be used on a different thread than they were created on.
    connect_args["check_same_thread"] = False
    # Timeout for acquiring a write lock, in seconds.
    connect_args["timeout"] = 30

engine = create_engine(
    settings.db_url,
    connect_args=connect_args,
    echo=settings.debug,
    future=True,
)


@event.listens_for(engine, "connect")
def _sqlite_pragmas(dbapi_conn, _record):
    """Enable FK enforcement, WAL, and busy timeout on every SQLite conn."""
    if not _is_sqlite:
        return
    cur = dbapi_conn.cursor()
    try:
        cur.execute("PRAGMA foreign_keys=ON")
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA synchronous=NORMAL")
        cur.execute("PRAGMA busy_timeout=5000")
    finally:
        cur.close()


SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""
    pass


def get_db():
    """
    FastAPI dependency. Yields a Session, rolls back on exception,
    and always closes.
    """
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
