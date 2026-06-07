"""
GET /platform/tenants — list all tenants (cross-tenant, operator-gated).
"""

from __future__ import annotations

import uuid

import pytest

from app.auth.operator_auth import verify_operator_token
from app.main import app
from app.models.identity import Tenant
from tests.conftest import token_override

URL = "/platform/tenants"


def test_list_empty(client, active_operator):
    """No tenants in DB -> 200 with empty list."""
    app.dependency_overrides[verify_operator_token] = token_override(active_operator.cognito_sub)
    try:
        r = client.get(URL)
    finally:
        app.dependency_overrides.pop(verify_operator_token, None)

    assert r.status_code == 200
    assert r.json() == []


def test_list_returns_tenants(client, active_operator, db_session):
    """Tenants inserted directly are returned, ordered by created_at."""
    db_session.add_all([
        Tenant(id=uuid.uuid4(), name="Alpha Corp", slug="alpha"),
        Tenant(id=uuid.uuid4(), name="Beta Inc", slug="beta"),
    ])
    db_session.commit()

    app.dependency_overrides[verify_operator_token] = token_override(active_operator.cognito_sub)
    try:
        r = client.get(URL)
    finally:
        app.dependency_overrides.pop(verify_operator_token, None)

    assert r.status_code == 200
    slugs = [t["slug"] for t in r.json()]
    assert "alpha" in slugs
    assert "beta" in slugs


def test_list_no_token(client):
    """No Authorization header -> 401."""
    r = client.get(URL)
    assert r.status_code == 401


def test_list_no_permission(client, db_session):
    """Active operator without tenant:provision -> 403."""
    sub = "list-no-perm-sub"
    from app.models.platform_rbac import Operator
    from app.models.base import OperatorStatus
    db_session.add(Operator(
        id=uuid.uuid4(), cognito_sub=sub, email="noperm3@irontrust.io",
        display_name="No Perm", status=OperatorStatus.ACTIVE,
    ))
    db_session.commit()

    app.dependency_overrides[verify_operator_token] = token_override(sub)
    try:
        r = client.get(URL)
    finally:
        app.dependency_overrides.pop(verify_operator_token, None)

    assert r.status_code == 403
