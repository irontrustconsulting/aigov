"""
Shared fixtures for the test suite.

DB strategy: a dedicated `irontrustai_test` Postgres database, created fresh
each test session via the admin credentials from settings. Tables are created
via Base.metadata.create_all (no migrations needed — no RLS, no triggers, no
grants to worry about in tests). All tables are truncated between tests so each
test starts with a clean slate.

Cognito is never called in tests. `verify_operator_token` is overridden per-test
via app.dependency_overrides. Service-level Cognito helpers (_create_cognito_owner,
_create_cognito_operator) are patched per-test where needed.

Session strategy: the `db_session` fixture opens a session on the test engine.
FastAPI dependencies (get_db, get_platform_ro_db, get_provisioner_db) are all
overridden to yield that same session so the test, the authZ seam, and the
router all share one view of the DB. Service-level sessionmakers
(ProvisionerSessionLocal, OperatorProvisionerSessionLocal) are patched to a
factory on the test engine so their commits land in the test DB and are cleaned
up by the post-test TRUNCATE.
"""

from __future__ import annotations

import uuid
from collections.abc import Generator
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import URL, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.auth.operator_auth import OperatorClaims, verify_operator_token
from app.auth.operator_authz import CurrentOperator
from app.config import settings
from app.db.session import get_db, get_platform_ro_db, get_provisioner_db
from app.main import app
from app.models import Base
from app.models.base import OperatorStatus
from app.models.platform_rbac import Operator, OperatorRole, Permission, Role, RolePermission

_TEST_DB = "irontrustai_test"


def _url(database: str) -> URL:
    return URL.create(
        "postgresql+psycopg",
        username=settings.postgres_user,
        password=settings.postgres_password,
        host=settings.db_host,
        port=settings.db_port,
        database=database,
    )


# ---------------------------------------------------------------------------
# Session-scoped: create the test database once, tear it down at the end.
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def test_engine():
    admin = create_engine(_url("postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f"DROP DATABASE IF EXISTS {_TEST_DB} WITH (FORCE)"))
        conn.execute(text(f"CREATE DATABASE {_TEST_DB}"))
    admin.dispose()

    engine = create_engine(_url(_TEST_DB))
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()

    admin = create_engine(_url("postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f"DROP DATABASE IF EXISTS {_TEST_DB} WITH (FORCE)"))
    admin.dispose()


@pytest.fixture(scope="session")
def _test_session_factory(test_engine):
    return sessionmaker(
        bind=test_engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )


# ---------------------------------------------------------------------------
# Function-scoped: clean slate per test.
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def clean_tables(test_engine):
    """Truncate every table after each test."""
    yield
    table_names = ", ".join(f'"{t.name}"' for t in Base.metadata.sorted_tables)
    with test_engine.connect() as conn:
        conn.execute(text(f"TRUNCATE {table_names} RESTART IDENTITY CASCADE"))
        conn.commit()


@pytest.fixture
def db_session(_test_session_factory) -> Generator[Session, None, None]:
    session = _test_session_factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db_session, _test_session_factory):
    """
    TestClient with:
    - All FastAPI DB dependencies pointing at db_session.
    - Service-level sessionmakers patched to _test_session_factory so their
      commits land in the test DB and are cleaned up by clean_tables.
    """
    def _db() -> Generator[Session, None, None]:
        yield db_session

    with (
        patch("app.services.provisioning.ProvisionerSessionLocal", _test_session_factory),
        patch("app.services.operator_provisioning.OperatorProvisionerSessionLocal", _test_session_factory),
    ):
        app.dependency_overrides[get_db] = _db
        app.dependency_overrides[get_platform_ro_db] = _db
        app.dependency_overrides[get_provisioner_db] = _db

        with TestClient(app, raise_server_exceptions=True) as c:
            yield c

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def token_override(sub: str, email: str = "op@irontrust.io", name: str = "Test Op"):
    """Returns a dependency override that yields controlled OperatorClaims."""
    claims = OperatorClaims(sub=sub, email=email, name=name)
    def _dep():
        return claims
    return _dep


@pytest.fixture
def active_operator(db_session) -> CurrentOperator:
    """Insert an active operator with tenant:provision into the test DB."""
    op_id = uuid.uuid4()
    perm_id = uuid.uuid4()
    role_id = uuid.uuid4()
    sub = "test-op-sub-001"
    email = "operator@irontrust.io"

    db_session.add_all([
        Permission(id=perm_id, key="tenant:provision"),
        Role(id=role_id, key="provisioner"),
        RolePermission(id=uuid.uuid4(), role_id=role_id, permission_id=perm_id),
        Operator(
            id=op_id, cognito_sub=sub, email=email,
            display_name="Test Op", status=OperatorStatus.ACTIVE,
        ),
        OperatorRole(id=uuid.uuid4(), operator_id=op_id, role_id=role_id, granted_by_id=None),
    ])
    db_session.commit()

    return CurrentOperator(
        id=op_id, cognito_sub=sub, email=email,
        display_name="Test Op", permissions=frozenset(["tenant:provision"]),
    )
