"""
Shared Cognito helpers used by both the platform provisioning path
(provision_tenant) and the tenant-scoped member creation path (provision_member).

Design notes
------------
* create_cognito_user: generic enough for both owner and member creation.
  `custom:tenant_id` is always pinned by the caller — never from user input.
* delete_cognito_user: best-effort compensation. Never raises: a leftover
  Cognito user is picked up by the reconciler rather than masking the
  original error.
"""

from __future__ import annotations

import uuid

import boto3
from botocore.exceptions import ClientError

from app.config import settings


def _cognito():
    return boto3.client("cognito-idp", region_name=settings.cognito_region)


def create_cognito_user(
    *,
    email: str,
    display_name: str,
    tenant_id: uuid.UUID,
) -> str:
    """Create a user in the tenant Cognito pool and return their `sub`.

    AdminCreateUser sends an invitation email with a temporary password;
    the user sets their real password on first login.

    Pool prerequisites (configure once):
    * `custom:tenant_id` must be IMMUTABLE — authz trusts this claim.
    * Pool must use email as the username/alias.

    Raises ClientError on all Cognito failures, including
    UsernameExistsException — callers map that to AlreadyProvisioned.
    """
    client = _cognito()
    resp = client.admin_create_user(
        UserPoolId=settings.cognito_user_pool_id,
        Username=email,
        UserAttributes=[
            {"Name": "email", "Value": email},
            # Vouched by the creating party (operator for owner, admin for member).
            # Receiving the invite email proves address control.
            {"Name": "email_verified", "Value": "true"},
            {"Name": "name", "Value": display_name},
            {"Name": "custom:tenant_id", "Value": str(tenant_id)},
        ],
        DesiredDeliveryMediums=["EMAIL"],
    )
    return next(
        a["Value"] for a in resp["User"]["Attributes"] if a["Name"] == "sub"
    )


def delete_cognito_user(email: str) -> None:
    """Best-effort compensating delete. Never raises."""
    try:
        _cognito().admin_delete_user(
            UserPoolId=settings.cognito_user_pool_id, Username=email
        )
    except Exception:
        pass  # TODO: log for the reconciler to pick up


def get_cognito_user_status(email: str) -> str | None:
    """Return the Cognito UserStatus string for a user, or None if not found.

    Used to derive the accept status in member listings:
      FORCE_CHANGE_PASSWORD -> "pending"
      CONFIRMED             -> "accepted"
    """
    try:
        resp = _cognito().admin_get_user(
            UserPoolId=settings.cognito_user_pool_id, Username=email
        )
        return resp.get("UserStatus")
    except ClientError as e:
        if e.response.get("Error", {}).get("Code") == "UserNotFoundException":
            return None
        raise
