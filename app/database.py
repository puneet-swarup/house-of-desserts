"""
Database engine and session management.

Python/SQLAlchemy concepts:
- Engine: The connection factory. Creates and manages database connections.
- Session: A "unit of work." You do all your DB operations through a session,
  then commit (save) or rollback (discard). Think of it like a transaction.
- Base: The declarative base class. All your ORM models inherit from this.
  It's like a "parent class" that gives models their table-mapping magic.
- get_db(): A FastAPI "dependency." Routes that need a DB session declare
  `db: Session = Depends(get_db)` and FastAPI handles the lifecycle.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import get_settings

settings = get_settings()

# For SQLite, we need check_same_thread=False because FastAPI uses
# a threadpool for sync endpoints. This is safe for our single-user app.
connect_args = {}
if settings.db_url.startswith("sqlite"):
    connect_args["check_same_thread"] = False

# The Engine — one per application. It manages a pool of DB connections.
engine = create_engine(
    settings.db_url,
    connect_args=connect_args,
    echo=settings.debug,  # Print SQL queries to console in debug mode
)

# SessionLocal — a factory that creates new Session objects.
# Each request gets its own session (created by get_db below).
SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,  # We control when to commit
    autoflush=False,   # We control when to flush
    expire_on_commit=False,  # Objects remain accessible after commit
)


class Base(DeclarativeBase):
    """
    Base class for all ORM models.

    Python concept: In SQLAlchemy 2.0, you use DeclarativeBase instead of
    the old `declarative_base()` function. All your models will do:
        class Customer(Base):
            __tablename__ = "customers"
            ...
    This registers them with Base.metadata, which Alembic uses for migrations.
    """
    pass


def get_db():
    """
    FastAPI dependency that provides a database session per request.

    Python concept: This is a "generator" (note the `yield`).
    FastAPI calls this before the route, gives the session to the route,
    and after the route finishes, the code after `yield` runs (cleanup).

    Usage in a route:
        @router.get("/customers")
        def list_customers(db: Session = Depends(get_db)):
            return db.query(Customer).all()
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()   