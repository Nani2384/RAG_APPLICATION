import asyncio
from logging.config import fileConfig
from sqlalchemy import pool
from alembic import context

# 1. Import Settings and Database Base metadata
from app.core.config import settings
from app.models.domain import Base

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# 2. Overwrite SQLAlchemy URL config option dynamically
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 3. Map target metadata for autogenerate support
target_metadata = Base.metadata

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = settings.DATABASE_URL
    # Alembic offline needs synchronous scheme representation
    if "+asyncpg" in url:
        url = url.replace("+asyncpg", "")
        
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()

def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()

async def run_migrations_online_async() -> None:
    """Run migrations asynchronously in 'online' mode using SQLAlchemy AsyncEngine."""
    from sqlalchemy.ext.asyncio import create_async_engine
    
    connectable = create_async_engine(
        settings.DATABASE_URL,
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()

def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    asyncio.run(run_migrations_online_async())

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
