"""
The authorization layer that sits between a verified token and a tenant-scoped
database session.

Four composable dependencies, each with one definition:

  get_tenant_context         - verified token -> resolve & AUTHORISE against
                               the DB: the app_user must exist (by sub), the
                               claimed tenant must exist, and a membership must
                               link them. Returns a TenantContext (user,
                               membership_id, tenant_id, authoritative role).
                               This answers "who is this and may they act in
                               this tenant" — the question RLS cannot answer.

  get_tenant_db              - depends on the context; sets app.current_tenant
                               to the MEMBERSHIP-VERIFIED tenant and yields the
                               RLS-scoped session.

  require_role(*roles)       - Gates on membership.role (administrative axis):
                               "admin" or "member". Used for managing the
                               tenant itself (governance assignment, settings).

  require_governance_role(*) - Gates on governance_role_assignment (governance
                               axis): system_owner, contributor, reviewer,
                               authoriser, auditor. Reads from the DB assignment
                               table — never from token claims. Used for
                               workflow actions (create system, approve, etc.).

Failure modes are explicit:
  401  token missing/invalid (handled upstream in verify_cognito_token)
  403  authentic token, but user unknown / tenant unknown / not a member /
       wrong role  (authenticated but NOT authorised)
"""

from __future__ import annotations

import uuid
from collections.abc import Generator

from fastapi import Depends, HTTPException, status
from sqlalchemy import select, text
from sqlalchemy.orm import Session
from pydantic import BaseModel, ConfigDict

from app.db import ResolverSessionLocal, SessionLocal
from app.models import User, Tenant, Membership
from app.models.governance import GovernanceRole, GovernanceRoleAssignment
from app.auth.cognito import verify_cognito_token, CognitoClaims


class TenantContext(BaseModel):
    """The resolved, DB-authorised identity for a request."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    user_id: uuid.UUID
    membership_id: uuid.UUID   # the acting member's membership row id
    tenant_id: uuid.UUID
    role: str            # authoritative, read from the membership row
    email: str | None = None
    name: str | None = None


def get_tenant_context(
    claims: CognitoClaims = Depends(verify_cognito_token),
) -> TenantContext:
    """Resolve the verified claims against the database and AUTHORISE.

    Uses a short-lived admin session purely for these lookups (identity tables
    are not the user's tenant data; we are establishing *which* tenant before
    any tenant-scoped work happens). The resolved tenant then scopes the real
    request session in get_tenant_db.
    """
    # The tenant_id claim is authentic (token verified) but we treat the DB as
    # the source of truth for authorisation.
    try:
        claimed_tenant = uuid.UUID(claims.tenant_id)
    except (ValueError, TypeError):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Malformed tenant_id claim")

    with ResolverSessionLocal() as session:
        # 1. The user must already exist (created by onboarding, not lazily here).
        user = session.scalar(select(User).where(User.cognito_sub == claims.sub))
        if user is None:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                detail="User not provisioned",
            )

        # 2. The claimed tenant must exist.
        tenant = session.get(Tenant, claimed_tenant)
        if tenant is None:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                detail="Tenant not found",
            )

        # 3. A membership must link this user to this tenant — the authorisation
        #    check RLS cannot make. Role comes from HERE (authoritative), not
        #    from the token claim.
        membership = session.scalar(
            select(Membership).where(
                Membership.user_id == user.id,
                Membership.tenant_id == tenant.id,
            )
        )
        if membership is None:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                detail="User is not a member of this tenant",
            )

        return TenantContext(
            user_id=user.id,
            membership_id=membership.id,
            tenant_id=tenant.id,
            role=membership.role.value if hasattr(membership.role, "value") else str(membership.role),
            email=claims.email,
            name=claims.name,
        )


def get_tenant_db(
    ctx: TenantContext = Depends(get_tenant_context),
) -> Generator[Session, None, None]:
    """Yield a session scoped to the membership-verified tenant.

    SET LOCAL keeps app.current_tenant transaction-local, so it cannot leak
    across pooled connections. All queries in the handler run inside this
    transaction and are RLS-filtered to ctx.tenant_id.
    """
    db = SessionLocal()
    try:
        db.begin()
        db.execute(
            text("SELECT set_config('app.current_tenant', :tid, true)"),
            {"tid": str(ctx.tenant_id)},
        )
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def require_role(*allowed_roles: str):
    """Factory: returns a dependency that 403s unless the user's authoritative
    membership.role is in allowed_roles. Gates the administrative axis
    (admin / member). Defined once; parameterised at each endpoint.
    """
    def checker(ctx: TenantContext = Depends(get_tenant_context)) -> TenantContext:
        if ctx.role not in allowed_roles:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                detail=f"Requires membership role in {allowed_roles}; you are '{ctx.role}'",
            )
        return ctx
    return checker


def require_governance_role(*required_keys: str):
    """Factory: returns a dependency that 403s unless the member holds at
    least one of the named governance roles in governance_role_assignment.

    Gates the governance axis (system_owner, contributor, reviewer,
    authoriser, auditor). Reads from the DB assignment table on the
    RLS-scoped tenant session — never from token claims.

    FastAPI caches get_tenant_db within a request, so this dependency
    and the handler share the same session and the same RLS context.
    """
    def checker(
        ctx: TenantContext = Depends(get_tenant_context),
        db: Session = Depends(get_tenant_db),
    ) -> TenantContext:
        held_keys = set(db.scalars(
            select(GovernanceRole.key)
            .join(
                GovernanceRoleAssignment,
                GovernanceRole.id == GovernanceRoleAssignment.governance_role_id,
            )
            .where(GovernanceRoleAssignment.membership_id == ctx.membership_id)
        ))
        if not held_keys.intersection(required_keys):
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Requires governance role in {required_keys}; "
                    f"you hold {sorted(held_keys) or 'none'}"
                ),
            )
        return ctx
    return checker