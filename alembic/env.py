"""
Alembic migration environment.

Wired to the app: it pulls the database URL from your Settings (not from
alembic.ini) and points `target_metadata` at Base.metadata, so
`alembic revision --autogenerate` sees every model you've imported.

NOTE: autogenerate will NOT produce the partial unique indexes, RLS policies,
or the audit-immutability trigger (they aren't expressible as ORM model
attributes). Add those by hand in the generated migration — the SQL is in
DATA_MODEL_NOTES.md.
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# Import settings and the models' metadata.
from app.config import settings
from app.models import Base  # noqa: F401  (imports all models -> populates metadata)

config = context.config

# Inject the DB URL from our Settings rather than hardcoding in alembic.ini.
config.set_main_option("sqlalchemy.url", settings.migration_database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

def include_object(object, name, type_, reflected, compare_to):
    # Skip objects we manage by hand in raw SQL (partial indexes, etc.)
    # so autogenerate doesn't try to drop/recreate them.
    if type_ == "index" and name in {
        "uq_one_aiia_per_use_case",
        "uq_current_classification",
        "uq_one_primary_eu_mapping",
    }:
        return False
    return True


def run_migrations_offline() -> None:
    """Run migrations without a live DB connection (emits SQL)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        include_object=include_object
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against a live DB connection."""
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
            include_object=include_object
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()