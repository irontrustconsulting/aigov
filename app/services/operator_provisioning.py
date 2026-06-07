"""
app/services/operator_provisioning.py

Platform-operator provisioning (credential-gated CLI — not self-service).

Creates an operator identity: a Cognito user in the operator pool plus the
matching `operator` row and its initial role grant. This is the genesis
bootstrap path; no prior operator is required (granted_by_id is NULL).

Ordering (mirrors the tenant provisioner's discipline):
    1. Idempotency pre-check: fail fast if operator email already exists.
    2. INSERT operator row, flush (DB, uncommitted).
    3. Cognito AdminCreateUser (external; sends invite email).
    4. INSERT operator_role row.
    5. commit.

  Cognito fails              -> rollback; no orphan DB row.
  commit fails AFTER Cognito -> best-effort AdminDeleteUser to compensate,
                                then re-raise.

DB connection: irontrustai_operator_provisioner (SELECT,INSERT on operator/
operator_role; SELECT on role). Never the app or platform_ro connections.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import boto3
from botocore.exceptions import ClientError
from sqlalchemy import select

from app.config import settings
from app.db.session import OperatorProvisionerSessionLocal
from app.models.platform_rbac import Operator, OperatorRole, Role
from app.models.base import OperatorStatus
from app.services.audit import record_platform_event

if TYPE_CHECKING:
    from app.auth.operator_authz import CurrentOperator


class OperatorProvisioningError(Exception):
    """Base for operator provisioning failures."""


class OperatorAlreadyExists(OperatorProvisioningError):
    """An operator with this email already exists."""


class RoleNotFound(OperatorProvisioningError):
    """The requested role key does not exist in the DB."""


def _cognito_operator():
    return boto3.client(
        "cognito-idp",
        region_name=settings.cognito_region or "eu-west-2",
    )


def _create_cognito_operator(*, email: str, display_name: str) -> str:
    """Create the operator in Cognito's operator pool; return their `sub`."""
    client = _cognito_operator()
    resp = client.admin_create_user(
        UserPoolId=settings.cognito_operator_user_pool_id,
        Username=email,
        UserAttributes=[
            {"Name": "email", "Value": email},
            {"Name": "email_verified", "Value": "true"},
            {"Name": "name", "Value": display_name},
        ],
        DesiredDeliveryMediums=["EMAIL"],
    )
    return next(
        a["Value"] for a in resp["User"]["Attributes"] if a["Name"] == "sub"
    )


def _delete_cognito_operator(email: str) -> None:
    """Best-effort compensating delete. Never raises."""
    try:
        _cognito_operator().admin_delete_user(
            UserPoolId=settings.cognito_operator_user_pool_id,
            Username=email,
        )
    except Exception:
        pass  # leave for manual reconciliation; don't mask the original error


def provision_operator(
    *,
    email: str,
    display_name: str,
    role_key: str = "provisioner",
    actor: "CurrentOperator | None" = None,
    source: str = "cli",
) -> tuple[uuid.UUID, str]:
    """Create an operator and assign their initial role.

    Returns (operator_id, cognito_sub).

    Idempotency: operator.email check + Cognito's own UsernameExistsException
    both surface cleanly as OperatorAlreadyExists.
    """
    session = OperatorProvisionerSessionLocal()
    try:
        # --- pre-check: fail before touching Cognito ---
        existing = session.execute(
            select(Operator).where(Operator.email == email)
        ).scalar_one_or_none()
        if existing is not None:
            raise OperatorAlreadyExists(f"operator already exists: {email!r}")

        role = session.execute(
            select(Role).where(Role.key == role_key)
        ).scalar_one_or_none()
        if role is None:
            raise RoleNotFound(f"role not found: {role_key!r}")

        # --- 2. Insert operator row (uncommitted) ---
        operator_id = uuid.uuid4()
        operator = Operator(
            id=operator_id,
            cognito_sub="__pending__",   # placeholder until Cognito returns sub
            email=email,
            display_name=display_name,
            status=OperatorStatus.ACTIVE,
        )
        session.add(operator)
        session.flush()

        # --- 3. Cognito ---
        try:
            sub = _create_cognito_operator(email=email, display_name=display_name)
        except ClientError as e:
            session.rollback()
            code = e.response.get("Error", {}).get("Code")
            if code == "UsernameExistsException":
                raise OperatorAlreadyExists(
                    f"Cognito already has a user for {email!r}"
                ) from e
            raise OperatorProvisioningError("Cognito user creation failed") from e

        # --- 4. Update sub now that we have it, then add role grant ---
        operator.cognito_sub = sub
        session.add(OperatorRole(
            operator_id=operator_id,
            role_id=role.id,
            granted_by_id=None,   # genesis bootstrap — no prior operator
        ))

        # --- 5. Stage audit row, then commit atomically ---
        record_platform_event(
            session,
            actor=actor,
            action="CREATE_OPERATOR",
            target_type="operator",
            target_id=operator_id,
            target_ref=email,
            source=source,
            detail={"display_name": display_name, "role": role_key},
        )

        try:
            session.commit()
        except Exception:
            session.rollback()
            _delete_cognito_operator(email)
            raise

        return operator_id, sub
    finally:
        session.close()
