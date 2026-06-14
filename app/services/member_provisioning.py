"""
app/services/member_provisioning.py

Tenant-admin creation of tenant members.

Runs entirely on the RLS app role (SessionLocal / irontrustai_app, NOBYPASSRLS).
The membership insert is RLS-checked (WITH CHECK tenant_id = current_tenant).
The only platform-plane resource touched is Cognito, with custom:tenant_id
pinned to the acting admin's tenant.

Choreography mirrors provision_tenant's ordering exactly, minus the tenant
insert and minus BYPASSRLS:

    1. Pre-check: membership already exists for this email in this tenant
       -> AlreadyProvisioned (driven from membership, not bare app_user).
    2. Cognito AdminCreateUser (shared helper), custom:tenant_id immutable.
       UsernameExistsException -> AlreadyProvisioned.
    3. INSERT app_user + flush; INSERT Membership(UserRole.MEMBER) under RLS.
    4. Stage tenant-plane AuditEvent; commit.
    5. Commit failure after Cognito -> best-effort delete Cognito user, re-raise.

Why this service owns its own session: the transaction must stay open across the
Cognito call so we can compensate on commit failure. A request-scoped session
that commits at request end cannot express that.
"""

from __future__ import annotations

import uuid

from botocore.exceptions import ClientError
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.base import UserRole
from app.models.identity import Membership, User
from app.models.lifecycle import AuditEvent
from app.services.cognito_helpers import create_cognito_user, delete_cognito_user
from app.services.provisioning import AlreadyProvisioned, ProvisioningError


def provision_member(
    *,
    tenant_id: uuid.UUID,
    email: str,
    name: str,
    actor_user_id: uuid.UUID,
    source: str = "api",
) -> tuple[uuid.UUID, uuid.UUID]:
    """Create a Cognito identity and tenant membership for a new member.

    Returns (user_id, membership_id). The membership has role=UserRole.MEMBER
    and zero governance roles.

    Raises:
        AlreadyProvisioned  -- email already a member of this tenant, or
                               already a Cognito user (UsernameExistsException).
        ProvisioningError   -- other Cognito failure.
    """
    session: Session = SessionLocal()
    try:
        # Pin RLS context for the duration of this transaction.
        session.begin()
        session.execute(
            text("SELECT set_config('app.current_tenant', :tid, true)"),
            {"tid": str(tenant_id)},
        )

        # 1. Pre-check: membership-driven (never a bare app_user query).
        existing = session.scalar(
            select(Membership)
            .join(User, User.id == Membership.user_id)
            .where(
                Membership.tenant_id == tenant_id,
                User.email == email,
            )
        )
        if existing is not None:
            raise AlreadyProvisioned(
                f"{email!r} is already a member of this tenant"
            )

        # 2. Cognito — external step. On failure, rollback: nothing persisted.
        try:
            sub = create_cognito_user(
                email=email,
                display_name=name,
                tenant_id=tenant_id,
            )
        except ClientError as e:
            session.rollback()
            code = e.response.get("Error", {}).get("Code")
            if code == "UsernameExistsException":
                raise AlreadyProvisioned(
                    f"Cognito already has a user for {email!r}"
                ) from e
            raise ProvisioningError("Cognito user creation failed") from e

        # 3. DB identity rows.
        user = User(cognito_sub=sub, email=email, display_name=name)
        session.add(user)
        session.flush()  # populate user.id for the membership FK

        membership = Membership(
            user_id=user.id,
            tenant_id=tenant_id,
            role=UserRole.MEMBER,
        )
        session.add(membership)
        session.flush()  # populate membership.id for the audit row

        # 4. Tenant-plane audit (staged; committed atomically below).
        session.add(AuditEvent(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            action="member.created",
            entity_type="membership",
            entity_id=membership.id,
            detail={"email": email, "name": name, "source": source},
        ))

        # 5. Commit. On failure: compensate Cognito, re-raise.
        try:
            session.commit()
        except Exception:
            session.rollback()
            delete_cognito_user(email)
            raise

        return user.id, membership.id
    finally:
        session.close()
