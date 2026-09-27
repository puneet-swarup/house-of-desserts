"""
Alembic environment.

Reads DB_URL from app.config.Settings so there's a single source of
truth for the database location. SQLite needs `render_as_batch=True`
to support ALTER (SQLite doesn't support ALTER COLUMN natively;
alembic rewrites the table behind the scenes).
"""

from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

# Importing the models package registers every table with Base.metadata,
# which is what autogenerate compares against the live DB.
from app import models  # noqa: F401
from app.config import get_settings
from app.database import Base

config = context.config

# Single source of truth for the DB URL
settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.db_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Emit SQL to stdout without connecting to a DB."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations using a live connection."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
