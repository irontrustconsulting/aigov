"""
Behaviour contract for GET /platform/operators and GET /platform/roles.

Both routes share the operator:create gate (DF7-1 shared gate).
"""

from __future__ import annotations

import uuid

import pytest

from app.auth.operator_auth import verify_operator_token
from app.auth.operator_authz import CurrentOperator
from app.main import app
from app.models.base import OperatorStatus
from app.models.platform_rbac import Operator, OperatorRole, Permission, Role, RolePermission
from tests.conftest import token_override

OPERATORS = "/platform/operators"
ROLES = "/platform/roles"


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
    sub = "platform-admin-list-sub"
    email = "admin-list@irontrust.io"

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
    sub = "provisioner-list-sub"
    email = "prov-list@irontrust.io"

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


def test_platform_admin_lists_operators(client, platform_admin_op):
    """platform_admin → 200; calling operator visible with their role."""
    app.dependency_overrides[verify_operator_token] = token_override(platform_admin_op.cognito_sub)
    try:
        r = client.get(OPERATORS)
    finally:
        app.dependency_overrides.pop(verify_operator_token, None)

    assert r.status_code == 200
    items = r.json()
    assert isinstance(items, list)
    match = next((o for o in items if o["email"] == platform_admin_op.email), None)
    assert match is not None, "calling operator not in list"
    assert "platform_admin" in match["roles"]


def test_provisioner_only_cannot_list_operators(client, provisioner_only_op):
    """Caller without operator:create → 403 on GET /platform/operators."""
    app.dependency_overrides[verify_operator_token] = token_override(provisioner_only_op.cognito_sub)
    try:
        r = client.get(OPERATORS)
    finally:
        app.dependency_overrides.pop(verify_operator_token, None)

    assert r.status_code == 403


def test_platform_admin_lists_roles(client, platform_admin_op):
    """platform_admin → 200; both platform_admin and provisioner in roles list."""
    app.dependency_overrides[verify_operator_token] = token_override(platform_admin_op.cognito_sub)
    try:
        r = client.get(ROLES)
    finally:
        app.dependency_overrides.pop(verify_operator_token, None)

    assert r.status_code == 200
    keys = {item["key"] for item in r.json()}
    assert "provisioner" in keys
    assert "platform_admin" in keys


def test_provisioner_only_cannot_list_roles(client, provisioner_only_op):
    """Caller without operator:create → 403 on GET /platform/roles."""
    app.dependency_overrides[verify_operator_token] = token_override(provisioner_only_op.cognito_sub)
    try:
        r = client.get(ROLES)
    finally:
        app.dependency_overrides.pop(verify_operator_token, None)

    assert r.status_code == 403
