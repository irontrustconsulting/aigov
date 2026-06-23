"""
Behaviour contract for POST /platform/operators.

Gate: require_permission("operator:create") — only platform_admin holds it.
Service: provision_operator wraps Cognito + DB; Cognito is patched here.
"""

from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest
from sqlalchemy import select

from app.auth.operator_auth import verify_operator_token
from app.auth.operator_authz import CurrentOperator
from app.main import app
from app.models.base import OperatorStatus
from app.models.platform_audit import PlatformAuditEvent
from app.models.platform_rbac import Operator, OperatorRole, Permission, Role, RolePermission
from tests.conftest import token_override

CREATE = "/platform/operators"

_FAKE_COGNITO_SUB = "cognito-sub-new-op"


@pytest.fixture
def seeded_roles(db_session):
    """Seed both roles and all permissions; return (admin_role_id, provisioner_role_id)."""
    perm_provision_id = uuid.uuid4()
    perm_create_id = uuid.uuid4()
    role_admin_id = uuid.uuid4()
    role_provisioner_id = uuid.uuid4()

    db_session.add_all([
        Permission(id=perm_provision_id, key="tenant:provision"),
        Permission(id=perm_create_id, key="operator:create"),
        Role(id=role_admin_id, key="platform_admin"),
        Role(id=role_provisioner_id, key="provisioner"),
        RolePermission(id=uuid.uuid4(), role_id=role_admin_id, permission_id=perm_provision_id),
        RolePermission(id=uuid.uuid4(), role_id=role_admin_id, permission_id=perm_create_id),
        RolePermission(id=uuid.uuid4(), role_id=role_provisioner_id, permission_id=perm_provision_id),
    ])
    db_session.commit()
    return role_admin_id, role_provisioner_id


@pytest.fixture
def platform_admin_op(db_session, seeded_roles):
    """Insert an active platform_admin operator."""
    role_admin_id, _ = seeded_roles
    op_id = uuid.uuid4()
    sub = "platform-admin-sub-f8"
    email = "admin@irontrust.io"

    db_session.add_all([
        Operator(
            id=op_id, cognito_sub=sub, email=email,
            display_name="Platform Admin", status=OperatorStatus.ACTIVE,
        ),
        OperatorRole(id=uuid.uuid4(), operator_id=op_id, role_id=role_admin_id, granted_by_id=None),
    ])
    db_session.commit()

    return CurrentOperator(
        id=op_id, cognito_sub=sub, email=email,
        display_name="Platform Admin",
        permissions=frozenset(["tenant:provision", "operator:create"]),
    )


@pytest.fixture
def provisioner_only_op(db_session, seeded_roles):
    """Insert an active provisioner-only operator (no operator:create)."""
    _, role_provisioner_id = seeded_roles
    op_id = uuid.uuid4()
    sub = "provisioner-sub-f8"
    email = "prov@irontrust.io"

    db_session.add_all([
        Operator(
            id=op_id, cognito_sub=sub, email=email,
            display_name="Provisioner", status=OperatorStatus.ACTIVE,
        ),
        OperatorRole(id=uuid.uuid4(), operator_id=op_id, role_id=role_provisioner_id, granted_by_id=None),
    ])
    db_session.commit()

    return CurrentOperator(
        id=op_id, cognito_sub=sub, email=email,
        display_name="Provisioner",
        permissions=frozenset(["tenant:provision"]),
    )


def _do_create(client, sub, body):
    app.dependency_overrides[verify_operator_token] = token_override(sub)
    try:
        return client.post(CREATE, json=body)
    finally:
        app.dependency_overrides.pop(verify_operator_token, None)


def test_platform_admin_creates_provisioner(client, platform_admin_op):
    """platform_admin → 201; cognito_sub and operator_id in response; invite sent."""
    with patch(
        "app.services.operator_provisioning._create_cognito_operator",
        return_value=_FAKE_COGNITO_SUB,
    ) as mock_cognito:
        r = _do_create(client, platform_admin_op.cognito_sub, {
            "email": "new-prov@irontrust.io",
            "display_name": "New Provisioner",
            "role_key": "provisioner",
        })

    assert r.status_code == 201
    body = r.json()
    assert "operator_id" in body
    assert body["cognito_sub"] == _FAKE_COGNITO_SUB
    mock_cognito.assert_called_once_with(
        email="new-prov@irontrust.io", display_name="New Provisioner"
    )


def test_duplicate_email_returns_409(client, platform_admin_op, db_session):
    """Operator with same email already in DB → 409."""
    db_session.add(Operator(
        id=uuid.uuid4(), cognito_sub="existing-sub", email="dup@irontrust.io",
        display_name="Existing", status=OperatorStatus.ACTIVE,
    ))
    db_session.commit()

    with patch("app.services.operator_provisioning._create_cognito_operator"):
        r = _do_create(client, platform_admin_op.cognito_sub, {
            "email": "dup@irontrust.io",
            "display_name": "Dup",
            "role_key": "provisioner",
        })

    assert r.status_code == 409


def test_unknown_role_returns_422(client, platform_admin_op):
    """Non-existent role_key → 422."""
    with patch("app.services.operator_provisioning._create_cognito_operator"):
        r = _do_create(client, platform_admin_op.cognito_sub, {
            "email": "ghost@irontrust.io",
            "display_name": "Ghost",
            "role_key": "does_not_exist",
        })

    assert r.status_code == 422


def test_provisioner_only_cannot_create(client, provisioner_only_op):
    """Caller without operator:create → 403."""
    r = _do_create(client, provisioner_only_op.cognito_sub, {
        "email": "new@irontrust.io",
        "display_name": "New",
        "role_key": "provisioner",
    })
    assert r.status_code == 403
    assert "permission" in r.json()["detail"].lower()


def test_audit_event_attributes_calling_operator(client, platform_admin_op, db_session):
    """Successful create → PlatformAuditEvent with actor = calling operator."""
    with patch(
        "app.services.operator_provisioning._create_cognito_operator",
        return_value=_FAKE_COGNITO_SUB,
    ):
        r = _do_create(client, platform_admin_op.cognito_sub, {
            "email": "audited@irontrust.io",
            "display_name": "Audited Op",
            "role_key": "provisioner",
        })

    assert r.status_code == 201

    db_session.expire_all()
    event = db_session.scalars(
        select(PlatformAuditEvent).where(PlatformAuditEvent.action == "CREATE_OPERATOR")
    ).one()
    assert event.actor_sub == platform_admin_op.cognito_sub
    assert event.actor_email == platform_admin_op.email
    assert event.source == "http"
    assert event.target_ref == "audited@irontrust.io"
