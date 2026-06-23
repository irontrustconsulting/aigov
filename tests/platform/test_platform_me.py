"""
Behaviour contract for GET /platform/me — the durable operator identity endpoint.

D-39: authenticated-operator-only (no permission assertion); returns
{id, email, display_name, permissions}; permissions sourced from the DB
operator→role→permission chain, never from token claims.
"""

from __future__ import annotations

import uuid

import pytest

from app.auth.operator_auth import verify_operator_token
from app.main import app
from app.models.base import OperatorStatus
from app.models.platform_rbac import Operator
from tests.conftest import token_override

ME = "/platform/me"


def test_no_token(client):
    r = client.get(ME)
    assert r.status_code == 401


def test_unknown_operator(client):
    """Valid token but sub has no operator row -> 403."""
    app.dependency_overrides[verify_operator_token] = token_override("ghost-sub-xyz")
    try:
        r = client.get(ME)
    finally:
        app.dependency_overrides.pop(verify_operator_token, None)
    assert r.status_code == 403


def test_disabled_operator(client, db_session):
    """Operator row exists but status=DISABLED -> 403."""
    sub = "disabled-op-sub-me"
    db_session.add(Operator(
        id=uuid.uuid4(), cognito_sub=sub, email="disabled-me@irontrust.io",
        display_name="Disabled", status=OperatorStatus.DISABLED,
    ))
    db_session.commit()

    app.dependency_overrides[verify_operator_token] = token_override(sub)
    try:
        r = client.get(ME)
    finally:
        app.dependency_overrides.pop(verify_operator_token, None)
    assert r.status_code == 403


def test_operator_with_permission(client, active_operator):
    """Active operator with tenant:provision -> 200, permission in set."""
    app.dependency_overrides[verify_operator_token] = token_override(active_operator.cognito_sub)
    try:
        r = client.get(ME)
    finally:
        app.dependency_overrides.pop(verify_operator_token, None)

    assert r.status_code == 200
    body = r.json()
    assert body["email"] == active_operator.email
    assert "cognito_sub" not in body
    assert "tenant:provision" in body["permissions"]


def test_operator_without_permission(client, db_session):
    """Active operator with NO permissions -> 200 (not 403); permissions empty."""
    sub = "no-perm-sub-me"
    db_session.add(Operator(
        id=uuid.uuid4(), cognito_sub=sub, email="noperm-me@irontrust.io",
        display_name="No Perm", status=OperatorStatus.ACTIVE,
    ))
    db_session.commit()

    app.dependency_overrides[verify_operator_token] = token_override(sub)
    try:
        r = client.get(ME)
    finally:
        app.dependency_overrides.pop(verify_operator_token, None)

    assert r.status_code == 200
    body = r.json()
    assert "tenant:provision" not in body["permissions"]


def test_whoami_gone(client):
    """GET /platform/whoami must return 404 after removal."""
    r = client.get("/platform/whoami")
    assert r.status_code == 404


def test_permissions_from_db_not_claims(client, db_session):
    """Permissions come from the DB chain; the token itself carries no permission data."""
    sub = "claims-test-sub-me"
    db_session.add(Operator(
        id=uuid.uuid4(), cognito_sub=sub, email="claims-test-me@irontrust.io",
        display_name="Claims Test", status=OperatorStatus.ACTIVE,
    ))
    db_session.commit()

    # Token has no permission fields — if permissions were claims-sourced they'd
    # be absent; DB-sourced they're empty (no roles assigned).
    app.dependency_overrides[verify_operator_token] = token_override(sub)
    try:
        r = client.get(ME)
    finally:
        app.dependency_overrides.pop(verify_operator_token, None)

    assert r.status_code == 200
    assert r.json()["permissions"] == []
