"""Alembic environment configuration for clawtion.

Reads the database URL from the CLAWTION_DB_URL environment variable,
defaulting to the local development PostgreSQL instance.
Uses an asynchronous engine for migration execution.
"""

import asyncio
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

from clawtion.core.db.models import Base

# Alembic Config object
config = context.config

# Set the database URL from environment variable with default fallback
db_url = os.environ.get(
    "CLAWTION_DB_URL",
    "postgresql+asyncpg://clawtion:clawtion@localhost:5432/clawtion",
)
config.set_main_option("sqlalchemy.url", db_url)

# Set up Python logging from the ini file
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# MetaData for autogenerate support
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    Configures the context with just a URL and not an Engine,
    emitting SQL as a script instead of executing it directly.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    """Execute migrations against the given connection."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations using an asynchronous engine."""
    url = config.get_main_option("sqlalchemy.url")
    connectable = create_async_engine(url)

    try:
        async with connectable.connect() as connection:
            await connection.run_sync(do_run_migrations)
    finally:
        await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode using an async engine."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
