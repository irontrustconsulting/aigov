"""
Audit row tests — every privileged action writes an append-only
PlatformAuditEvent with the correct fields.

Service functions are called directly against the test DB for CLI-path tests;
HTTP-path tests go through the TestClient.
"""

from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest
from sqlalchemy import select

from app.auth.operator_auth import verify_operator_token
from app.auth.operator_authz import CurrentOperator
from app.main import app
from app.models.platform_audit import PlatformAuditEvent
from app.models.base import OperatorStatus
from app.models.platform_rbac import Role
from app.services.provisioning import provision_tenant
from app.services.operator_provisioning import provision_operator
from tests.conftest import token_override

_FAKE_TENANT_SUB = "fake-cognito-sub-tenant"
_FAKE_OP_SUB = "fake-cognito-sub-op"


# ---------------------------------------------------------------------------
# HTTP path
# ---------------------------------------------------------------------------

def test_http_provision_writes_audit(client, active_operator, db_session):
    """POST /platform/provision -> one PlatformAuditEvent with correct fields."""
    with patch("app.services.provisioning.create_cognito_user", return_value=_FAKE_TENANT_SUB):
        app.dependency_overrides[verify_operator_token] = token_override(active_operator.cognito_sub)
        try:
            r = client.post("/platform/provision", json={
                "org_name": "Audit Corp",
                "slug": "audit-corp",
                "owner_email": "owner@audit.com",
                "owner_name": "Audit Owner",
            })
        finally:
            app.dependency_overrides.pop(verify_operator_token, None)

    assert r.status_code == 201

    # Read audit row — use a fresh query on db_session (READ COMMITTED sees the
    # committed row from the patched ProvisionerSessionLocal)
    db_session.expire_all()
    rows = db_session.scalars(select(PlatformAuditEvent)).all()
    assert len(rows) == 1
    row = rows[0]
    assert row.action == "PROVISION_TENANT"
    assert row.source == "http"
    assert row.actor_sub == active_operator.cognito_sub
    assert row.actor_email == active_operator.email
    assert row.target_ref == "audit-corp"
    assert row.detail["org_name"] == "Audit Corp"


# ---------------------------------------------------------------------------
# CLI path — call service directly, using the test DB via the patched factory
# ---------------------------------------------------------------------------

def test_cli_provision_with_actor(db_session, _test_session_factory):
    """provision_tenant with actor= writes audit row with actor fields set."""
    actor = CurrentOperator(
        id=uuid.uuid4(),
        cognito_sub="cli-actor-sub",
        email="cli-actor@irontrust.io",
        display_name="CLI Actor",
        permissions=frozenset(["tenant:provision"]),
    )
    with (
        patch("app.services.provisioning.ProvisionerSessionLocal", _test_session_factory),
        patch("app.services.provisioning.create_cognito_user", return_value="fake-sub-cli"),
    ):
        provision_tenant(
            org_name="CLI Org",
            slug="cli-org",
            owner_email="owner@cliorg.com",
            owner_name="CLI Owner",
            actor=actor,
            source="cli",
        )

    db_session.expire_all()
    row = db_session.scalars(select(PlatformAuditEvent)).one()
    assert row.action == "PROVISION_TENANT"
    assert row.source == "cli"
    assert row.actor_sub == "cli-actor-sub"
    assert row.actor_email == "cli-actor@irontrust.io"


def test_cli_provision_genesis_actor_null(db_session, _test_session_factory):
    """provision_tenant with actor=None (genesis) -> audit row has null actor fields."""
    with (
        patch("app.services.provisioning.ProvisionerSessionLocal", _test_session_factory),
        patch("app.services.provisioning.create_cognito_user", return_value="fake-sub-genesis"),
    ):
        provision_tenant(
            org_name="Genesis Org",
            slug="genesis-org",
            owner_email="owner@genesis.com",
            owner_name="Genesis Owner",
            actor=None,
            source="cli",
        )

    db_session.expire_all()
    row = db_session.scalars(select(PlatformAuditEvent)).one()
    assert row.actor_sub is None
    assert row.actor_email is None
    assert row.source == "cli"


def test_cli_create_operator_writes_audit(db_session, _test_session_factory):
    """provision_operator writes a CREATE_OPERATOR audit row."""
    # Seed the provisioner role that provision_operator looks up
    role_id = uuid.uuid4()
    from app.models.platform_rbac import Role
    session = _test_session_factory()
    session.add(Role(id=role_id, key="provisioner"))
    session.commit()
    session.close()

    actor = CurrentOperator(
        id=uuid.uuid4(),
        cognito_sub="granting-op-sub",
        email="grantor@irontrust.io",
        display_name="Grantor",
        permissions=frozenset(["tenant:provision"]),
    )
    with (
        patch("app.services.operator_provisioning.OperatorProvisionerSessionLocal", _test_session_factory),
        patch("app.services.operator_provisioning._create_cognito_operator", return_value="new-op-cognito-sub"),
    ):
        provision_operator(
            email="newop@irontrust.io",
            display_name="New Op",
            role_key="provisioner",
            actor=actor,
            source="cli",
        )

    db_session.expire_all()
    row = db_session.scalars(select(PlatformAuditEvent)).one()
    assert row.action == "CREATE_OPERATOR"
    assert row.source == "cli"
    assert row.actor_sub == "granting-op-sub"
    assert row.target_ref == "newop@irontrust.io"
    assert row.detail["role"] == "provisioner"


def test_audit_actor_matches_operator(client, active_operator, db_session):
    """actor_sub in the audit row matches the verified operator's cognito_sub."""
    with patch("app.services.provisioning.create_cognito_user", return_value=_FAKE_TENANT_SUB):
        app.dependency_overrides[verify_operator_token] = token_override(
            active_operator.cognito_sub, email=active_operator.email
        )
        try:
            client.post("/platform/provision", json={
                "org_name": "Match Corp",
                "slug": "match-corp",
                "owner_email": "owner@match.com",
                "owner_name": "Match Owner",
            })
        finally:
            app.dependency_overrides.pop(verify_operator_token, None)

    db_session.expire_all()
    row = db_session.scalars(select(PlatformAuditEvent)).one()
    assert row.actor_sub == active_operator.cognito_sub
