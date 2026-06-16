"""
Alembic async migration environment.

Configured to work with SQLAlchemy's asyncio extensions (asyncpg driver).
Imports all ORM models via app.db.base to ensure target_metadata
sees every table for autogeneration.

Reference: Alembic Cookbook — Using Asyncio with Alembic
"""

import asyncio
import os
import sys
from logging.config import fileConfig

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.core.config import settings

# Import Base with all models registered
from app.db.base import Base  # noqa: F401

# Alembic Config object (provides access to .ini values)
config = context.config

# Override sqlalchemy.url with the app's DATABASE_URL
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

# Standard Python logging from alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Target metadata for autogeneration
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode.

    Generates SQL scripts without connecting to the database.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:  # type: ignore[no-untyped-def]
    """Execute migrations within a synchronous connection context."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """
    Run migrations in 'online' mode using async engine.

    Creates an AsyncEngine and runs migrations through
    connection.run_sync() bridge.
    """
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode (async wrapper)."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
