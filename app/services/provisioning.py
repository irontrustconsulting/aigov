"""
app/services/provisioning.py

Platform-admin tenant provisioning (sales-led -- no self-service).

Stands up a brand-new tenant and its first owner. Invoked ONLY by the
authenticated platform-admin path; never by tenant request handling, never
self-service. Runs on ProvisionerSessionLocal -- the irontrustai_provisioner
role (BYPASSRLS, SELECT/INSERT on tenant/app_user/membership only).

Ordering (the no-two-phase-commit discipline we settled on):
    1. mint tenant_id in-process          (no DB round-trip needed for it)
    2. INSERT tenant, flush               (DB, still uncommitted)
    3. Cognito AdminCreateUser            (external; sends the invite email)
    4. INSERT app_user(sub) + membership  (DB, owner role)
    5. commit

  Cognito fails              -> rollback; nothing persisted (no orphan tenant).
  commit fails AFTER Cognito -> best-effort delete of the just-created Cognito
                                user (the one orphan this ordering can leave),
                                then re-raise.

Why this service owns its own Session rather than taking the request-scoped
one: the transaction choreography (hold the DB txn open across an external
Cognito call, compensate on commit failure) IS the algorithm. A generic
get_db dependency that commits at request end can't express that.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from botocore.exceptions import ClientError
from sqlalchemy import select

from app.db.session import ProvisionerSessionLocal
from app.models import Tenant, User, Membership, UserRole
from app.services.audit import record_platform_event
from app.services.cognito_helpers import create_cognito_user, delete_cognito_user

if TYPE_CHECKING:
    from app.auth.operator_authz import CurrentOperator


class ProvisioningError(Exception):
    """Base for provisioning failures."""


class AlreadyProvisioned(ProvisioningError):
    """A tenant with this slug, or a user with this email, already exists."""


def provision_tenant(
    *,
    org_name: str,
    slug: str,
    owner_email: str,
    owner_name: str,
    actor: "CurrentOperator | None" = None,
    source: str = "cli",
) -> tuple[uuid.UUID, uuid.UUID]:
    """Create a tenant and its first owner. Returns (tenant_id, owner_user_id).

    Idempotency: tenant.slug is unique and Cognito enforces one user per email,
    so a duplicate provision fails cleanly rather than double-creating. (Note
    app_user.email is indexed but NOT unique in the DB -- Cognito is the
    authority on user uniqueness. Add a unique constraint if you want the DB to
    enforce it too.)
    """
    session = ProvisionerSessionLocal()
    try:
        # --- idempotency pre-checks: fail fast, before any external call ---
        if session.execute(
            select(Tenant).where(Tenant.slug == slug)
        ).scalar_one_or_none():
            raise AlreadyProvisioned(f"tenant slug already exists: {slug!r}")
        if session.execute(
            select(User).where(User.email == owner_email)
        ).scalar_one_or_none():
            raise AlreadyProvisioned(f"a user already exists for: {owner_email!r}")

        # 1 + 2. Mint the id ourselves, create the tenant (uncommitted).
        # Minting in-process decouples the id from a DB round-trip, so we can
        # hand it to Cognito without depending on flush order for the value.
        tenant_id = uuid.uuid4()
        session.add(Tenant(id=tenant_id, name=org_name, slug=slug))
        session.flush()  # surface any tenant-level DB error now, before Cognito

        # 3. Cognito -- the external step. On failure, roll back: no orphan.
        try:
            sub = create_cognito_user(
                email=owner_email, display_name=owner_name, tenant_id=tenant_id
            )
        except ClientError as e:
            session.rollback()
            code = e.response.get("Error", {}).get("Code")
            if code == "UsernameExistsException":
                raise AlreadyProvisioned(
                    f"Cognito already has a user for {owner_email!r}"
                ) from e
            raise ProvisioningError("Cognito user creation failed") from e

        # 4. The DB identity rows, now that we have the sub.
        user = User(cognito_sub=sub, email=owner_email, display_name=owner_name)
        session.add(user)
        session.flush()  # populate user.id for the membership FK
        session.add(
            Membership(user_id=user.id, tenant_id=tenant_id, role=UserRole.ADMIN)
        )

        # 5. Stage audit row, then commit atomically.
        record_platform_event(
            session,
            actor=actor,
            action="PROVISION_TENANT",
            target_type="tenant",
            target_id=tenant_id,
            target_ref=slug,
            source=source,
            detail={"org_name": org_name, "owner_email": owner_email},
        )

        try:
            session.commit()
        except Exception:
            session.rollback()
            delete_cognito_user(owner_email)
            raise

        return tenant_id, user.id
    finally:
        session.close()