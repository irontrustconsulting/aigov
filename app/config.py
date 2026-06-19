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
    platform_ro_db_user: str                # env var PLATFORM_RO_DB_USER
    platform_ro_db_password: str            # env var PLATFORM_RO_DB_PASSWORD — secret, no default
    operator_provisioner_db_user: str       # env var OPERATOR_PROVISIONER_DB_USER
    operator_provisioner_db_password: str   # env var OPERATOR_PROVISIONER_DB_PASSWORD — secret, no default
    # Connection target (same host/port for both roles in dev).
    db_host: str = Field(default="localhost")
    db_port: int = Field(default=5432)

    # --- Object storage (evidence artifacts) ---
    # None => real AWS S3; set => S3-compatible endpoint (MinIO in dev)
    s3_endpoint_url: str | None = Field(default="http://localhost:9000")
    # Host that presigned URLs are signed against and that the browser
    # actually fetches. In dev-Compose the API reaches MinIO at "minio:9000"
    # but the browser can only reach "localhost:9000" — SigV4 signs the host,
    # so a URL signed against the internal name 404s from outside the
    # network. None => same as s3_endpoint_url (prod: both resolve to AWS).
    s3_public_endpoint_url: str | None = Field(default="http://localhost:9000")
    s3_region: str = Field(default="eu-west-2")
    # Static creds are a DEV convenience only. Leave unset in prod so boto3
    # resolves the instance/role chain (IRSA / ECS task role). Never ship long-lived keys.
    s3_access_key: str | None = Field(default="minioadmin")
    s3_secret_key: str | None = Field(default="minioadmin")
    s3_evidence_bucket: str = Field(default="aigov-evidence")
    # Path-style for MinIO; virtual-host for real S3.
    s3_use_path_style: bool = Field(default=True)
    # Encryption at rest. dev MinIO: off; prod: "aws:kms" for key-level auditability.
    s3_sse_mode: str | None = Field(default=None)         # "AES256" | "aws:kms" | None
    s3_sse_kms_key_id: str | None = Field(default=None)   # required iff sse_mode == "aws:kms"
    # Short-lived presigned GET for download.
    s3_presigned_get_ttl: int = Field(default=300)
    # Upload ceiling — must stay under the size_bytes INTEGER limit (~2.1 GB).
    evidence_max_upload_bytes: int = Field(default=100 * 1024 * 1024)  # 100 MiB

    # --- Cognito (auth) — fill when you wire auth; unused for now ---
    cognito_region: str | None = Field(default=None)
    cognito_user_pool_id: str | None = Field(default=None)
    cognito_app_client_id: str | None = Field(default=None)

    # --- Cognito: operator/platform pool (separate from the customer pool above) ---
    # Internal staff identities. authN only — no custom:tenant_id, no role attrs.
    cognito_operator_pool_issuer: str | None = Field(default=None)   # full iss URL — verifier uses this
    cognito_operator_app_client_id: str | None = Field(default=None) # checked as `aud`
    cognito_operator_user_pool_id: str | None = Field(default=None)  # bare pool id — for boto3 admin calls (create-operator)

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

    @property
    def operator_provisioner_database_url(self) -> URL:
        return URL.create(
            "postgresql+psycopg",
            username=self.operator_provisioner_db_user,
            password=self.operator_provisioner_db_password,
            host=self.db_host,
            port=self.db_port,
            database=self.postgres_db,
        )

    @property
    def platform_ro_database_url(self) -> URL:
        return URL.create(
            "postgresql+psycopg",
            username=self.platform_ro_db_user,
            password=self.platform_ro_db_password,
            host=self.db_host,
            port=self.db_port,
            database=self.postgres_db,
        )



@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()