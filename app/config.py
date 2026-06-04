"""
Application configuration, loaded from environment / .env.

One Settings object is the ONLY place environment differences live. "dev vs
prod" is purely which env values load — never a code change. Import the
singleton `settings` anywhere you need config.

Database URLs are COMPUTED from component fields (not stored as strings) so
that (a) each credential has one source of truth, and (b) special characters
in passwords are safely escaped by SQLAlchemy's URL.create().
"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- App ---
    app_env: str = Field(default="dev")          # dev | staging | prod
    debug: bool = Field(default=True)

    # --- Database components (read from .env; URLs are assembled below) ---
    # Admin / owner role: DDL power. Used ONLY by Alembic for migrations.
    postgres_user: str
    postgres_password: str
    postgres_db: str
    # Restricted runtime role: NOBYPASSRLS, DML only. Used by the running app.
    app_role: str
    app_runtime_password: str
    resolver_db_user: str = "irontrustai_resolver"
    resolver_db_password: str   # from .env, no default — it's a secret
    provisioner_db_user: str # from .env
    provisioner_db_password: str   # from .env, no default — it's a secret
    # Connection target (same host/port for both roles in dev).
    db_host: str = Field(default="localhost")
    db_port: int = Field(default=5432)

    # --- Object storage (S3 in prod, MinIO in dev) ---
    s3_endpoint_url: str | None = Field(default="http://localhost:9000")  # None => real AWS
    s3_region: str = Field(default="eu-west-1")
    s3_access_key: str = Field(default="minioadmin")
    s3_secret_key: str = Field(default="minioadmin")
    s3_evidence_bucket: str = Field(default="aigov-evidence")

    # --- Cognito (auth) — fill when you wire auth; unused for now ---
    cognito_region: str | None = Field(default=None)
    cognito_user_pool_id: str | None = Field(default=None)
    cognito_app_client_id: str | None = Field(default=None)

    # --- Computed connection URLs (assembled from components above) ---
    @property
    def database_url(self) -> URL:
        """Restricted runtime role — what the app connects as."""
        return URL.create(
            "postgresql+psycopg",
            username=self.app_role,
            password=self.app_runtime_password,
            host=self.db_host,
            port=self.db_port,
            database=self.postgres_db,
        )

    @property
    def migration_database_url(self) -> str:
        """Owner/admin role — what Alembic connects as for DDL."""
        return URL.create(
            "postgresql+psycopg",
            username=self.postgres_user,
            password=self.postgres_password,
            host=self.db_host,
            port=self.db_port,
            database=self.postgres_db,
        ).render_as_string(hide_password=False)
    
    @property
    def resolver_database_url(self) -> URL:
        return URL.create(
            "postgresql+psycopg",
            username=self.resolver_db_user,
            password=self.resolver_db_password,
            host=self.db_host,
            port=self.db_port,
            database=self.postgres_db,
        )
    @property
    def provisioner_database_url(self) -> URL:
        return URL.create(
            "postgresql+psycopg",
            username=self.provisioner_db_user,
            password=self.provisioner_db_password,
            host=self.db_host,
            port=self.db_port,
            database=self.postgres_db,
        )
    
    
       


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()