"""
Database wiring: engine, session factory, and the request-scoped session
dependency used by FastAPI route handlers.

Sync SQLAlchemy 2.0 for now (simplest to reason about). The async seam for the
lifecycle worker comes later and doesn't require async here — keep this sync.
"""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings

engine = create_engine(
    settings.database_url,
    echo=settings.debug,          # log SQL in dev; quiet in prod
    pool_pre_ping=True,           # transparently recover dropped connections
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)

# Resolver engine — used ONLY by identity resolution (get_tenant_context).
# Bound to irontrustai_resolver: BYPASSRLS, read-only on identity tables.
resolver_engine = create_engine(
    settings.resolver_database_url,
    echo=settings.debug,
    pool_pre_ping=True,
)

ResolverSessionLocal = sessionmaker(
    bind=resolver_engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)

# Provisioner engine: used ONLY by the platform-admin provisioning path to
# stand up a new tenant + its first owner. Mirrors the resolver — a separate,
# least-privilege connection for exactly one job.
provisioner_engine = create_engine(
    settings.provisioner_database_url,
    echo=settings.debug,
    pool_pre_ping=True,            # match whatever kwargs your resolver_engine uses
)
ProvisionerSessionLocal = sessionmaker(
    bind=provisioner_engine,
    autoflush=False,              # we control flush ourselves (flush tenant → Cognito → insert user)
    expire_on_commit=False,       # keep the created objects usable after commit (for the response)
)

# Operator-provisioner engine — used ONLY by the create-operator CLI command.
# Bound to irontrustai_operator_provisioner: SELECT,INSERT on operator/operator_role;
# SELECT on role. NOBYPASSRLS (those tables carry no RLS).
operator_provisioner_engine = create_engine(
    settings.operator_provisioner_database_url,
    echo=settings.debug,
    pool_pre_ping=True,
)

OperatorProvisionerSessionLocal = sessionmaker(
    bind=operator_provisioner_engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)

# Platform read-only engine — used ONLY by the operator authZ seam.
# Bound to irontrustai_platform_ro: BYPASSRLS, SELECT on RBAC tables only.
platform_ro_engine = create_engine(
    settings.platform_ro_database_url,
    echo=settings.debug,
    pool_pre_ping=True,
)

PlatformROSessionLocal = sessionmaker(
    bind=platform_ro_engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)


def get_provisioner_db() -> Generator[Session, None, None]:
    db = ProvisionerSessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_platform_ro_db() -> Generator[Session, None, None]:
    db = PlatformROSessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency. Yields a session, always closes it.

    Usage:
        @router.get("/things")
        def list_things(db: Session = Depends(get_db)):
            ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()