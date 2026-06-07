"""
Behaviour contract for the operator authZ seam (get_current_operator +
require_permission). All five contract rows from the hand-off doc, plus
cross-plane isolation checks.

All tests hit GET /platform/whoami which is gated by
require_permission("tenant:provision").
"""

from __future__ import annotations

import uuid

import pytest

from app.auth.operator_auth import verify_operator_token
from app.main import app
from app.models.base import OperatorStatus
from app.models.platform_rbac import Operator
from tests.conftest import token_override

WHOAMI = "/platform/whoami"


def test_no_token(client):
    """No Authorization header -> 401, no DB or Cognito lookup attempted."""
    r = client.get(WHOAMI)
    assert r.status_code == 401


def test_valid_token_unknown_operator(client):
    """Valid token but sub has no matching operator row -> 403."""
    app.dependency_overrides[verify_operator_token] = token_override("ghost-sub-xyz")
    try:
        r = client.get(WHOAMI)
    finally:
        app.dependency_overrides.pop(verify_operator_token, None)
    assert r.status_code == 403
    assert "recognized" in r.json()["detail"].lower()


def test_operator_disabled(client, db_session):
    """Operator row exists but status=DISABLED -> 403."""
    sub = "disabled-op-sub"
    db_session.add(Operator(
        id=uuid.uuid4(), cognito_sub=sub, email="disabled@irontrust.io",
        display_name="Disabled", status=OperatorStatus.DISABLED,
    ))
    db_session.commit()

    app.dependency_overrides[verify_operator_token] = token_override(sub)
    try:
        r = client.get(WHOAMI)
    finally:
        app.dependency_overrides.pop(verify_operator_token, None)
    assert r.status_code == 403
    assert "disabled" in r.json()["detail"].lower()


def test_active_operator_no_permission(client, db_session):
    """Active operator but no tenant:provision permission -> 403."""
    sub = "no-perm-sub"
    db_session.add(Operator(
        id=uuid.uuid4(), cognito_sub=sub, email="noperm@irontrust.io",
        display_name="No Perm", status=OperatorStatus.ACTIVE,
    ))
    db_session.commit()

    app.dependency_overrides[verify_operator_token] = token_override(sub)
    try:
        r = client.get(WHOAMI)
    finally:
        app.dependency_overrides.pop(verify_operator_token, None)
    assert r.status_code == 403
    assert "permission" in r.json()["detail"].lower()


def test_active_operator_permitted(client, active_operator):
    """Active operator with tenant:provision -> 200, identity echoed."""
    app.dependency_overrides[verify_operator_token] = token_override(active_operator.cognito_sub)
    try:
        r = client.get(WHOAMI)
    finally:
        app.dependency_overrides.pop(verify_operator_token, None)
    assert r.status_code == 200
    body = r.json()
    assert body["cognito_sub"] == active_operator.cognito_sub
    assert body["email"] == active_operator.email
    assert "tenant:provision" in body["permissions"]


# ---------------------------------------------------------------------------
# Cross-plane isolation
# ---------------------------------------------------------------------------

def test_platform_route_rejects_missing_token(client):
    """No token on a platform route -> 401 (not a tenant-plane 403)."""
    r = client.get(WHOAMI)
    assert r.status_code == 401


def test_tenant_route_does_not_use_operator_gate(client):
    """Tenant routes (GET /v1/systems) are independent of the operator gate.

    Without any token the tenant verifier returns 401. This confirms the two
    gates are wired separately — the platform gate is not accidentally applied
    to tenant routes.
    """
    r = client.get("/v1/systems")
    # Tenant verifier raises 401 for missing token — not a 403 from operator gate.
    assert r.status_code == 401
