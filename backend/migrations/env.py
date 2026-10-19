"""Alembic environment: migrate the database named by DATABASE_URL_UNPOOLED / DATABASE_URL (or local SQLite)."""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

from app.config import env_settings
from app.storage.db import DEFAULT_SQLITE, describe_url, normalize_url
from app.storage.schema import metadata

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)  # keep the app's redacting logger


def database_url() -> str:
    override = context.get_x_argument(as_dictionary=True).get("url")
    if override:
        return normalize_url(override)
    s = env_settings()
    raw = s.database_url_unpooled or s.database_url
    if raw:
        return normalize_url(raw)
    DEFAULT_SQLITE.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{DEFAULT_SQLITE.as_posix()}"


def run_migrations_offline() -> None:
    url = database_url()
    context.configure(url=url, target_metadata=metadata, literal_binds=True, render_as_batch=url.startswith("sqlite"))
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    url = database_url()
    print(f"Migrating {describe_url(url)} database")
    engine = create_engine(url, poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=metadata, render_as_batch=url.startswith("sqlite"))
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
