"""
Alembic environment configuration.

This file tells Alembic:
1. Which database to connect to (from our app's .env config)
2. Which models to inspect when autogenerating migrations
"""

from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

# Import our Base (the "parent" of all our ORM models)
from app.database import Base

# Import ALL models so Alembic can see every table definition.
# Without these imports, autogenerate won't detect your tables.
from app.models import (  # noqa: F401
    Customer,
    Product,
    Order,
    OrderItem,
    Payment,
    Invoice,
    AuditLog,
    Address,
)

# Import our settings to get the DB URL
from app.config import get_settings

settings = get_settings()

# Alembic Config object (access to values in alembic.ini)
config = context.config

# Override the empty sqlalchemy.url with our actual DB path
config.set_main_option("sqlalchemy.url", settings.db_url)

# Set up Python logging from the ini file
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# This is what Alembic inspects for autogenerate
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Generate SQL script without a live DB connection."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against the actual database."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()