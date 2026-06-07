"""
POST /platform/provision — end-to-end tests through the HTTP layer.

Cognito's AdminCreateUser is patched in every test; the rest of the stack
(authZ, DB writes, audit) runs against the real test database.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.auth.operator_auth import verify_operator_token
from app.main import app
from tests.conftest import token_override

URL = "/platform/provision"

_VALID_BODY = {
    "org_name": "Acme Corp",
    "slug": "acme",
    "owner_email": "owner@acme.com",
    "owner_name": "Jane Doe",
}

_FAKE_SUB = "cognito-fake-sub-tenant-001"


@pytest.fixture
def mock_cognito_owner():
    with patch(
        "app.services.provisioning._create_cognito_owner",
        return_value=_FAKE_SUB,
    ) as m:
        yield m


def test_provision_success(client, active_operator, mock_cognito_owner):
    """Valid request by permitted operator -> 201 with tenant_id and owner_id."""
    app.dependency_overrides[verify_operator_token] = token_override(active_operator.cognito_sub)
    try:
        r = client.post(URL, json=_VALID_BODY)
    finally:
        app.dependency_overrides.pop(verify_operator_token, None)

    assert r.status_code == 201
    body = r.json()
    assert "tenant_id" in body
    assert "owner_id" in body
    mock_cognito_owner.assert_called_once()


def test_provision_duplicate_slug(client, active_operator, mock_cognito_owner):
    """Second provision with the same slug -> 409."""
    app.dependency_overrides[verify_operator_token] = token_override(active_operator.cognito_sub)
    try:
        r1 = client.post(URL, json=_VALID_BODY)
        assert r1.status_code == 201

        # Different owner email to avoid that pre-check, same slug
        body2 = {**_VALID_BODY, "owner_email": "other@acme.com"}
        r2 = client.post(URL, json=body2)
    finally:
        app.dependency_overrides.pop(verify_operator_token, None)

    assert r2.status_code == 409


def test_provision_no_permission(client, db_session):
    """Active operator without tenant:provision -> 403."""
    import uuid
    from app.models.platform_rbac import Operator
    from app.models.base import OperatorStatus

    sub = "no-perm-op-sub"
    db_session.add(Operator(
        id=uuid.uuid4(), cognito_sub=sub, email="noperm2@irontrust.io",
        display_name="No Perm", status=OperatorStatus.ACTIVE,
    ))
    db_session.commit()

    app.dependency_overrides[verify_operator_token] = token_override(sub)
    try:
        r = client.post(URL, json=_VALID_BODY)
    finally:
        app.dependency_overrides.pop(verify_operator_token, None)

    assert r.status_code == 403


def test_provision_no_token(client):
    """No Authorization header -> 401."""
    r = client.post(URL, json=_VALID_BODY)
    assert r.status_code == 401
