"""
DEV-ONLY: seed extra memberships under an existing tenant for testing SoD.

Creates 3 extra User + Membership rows (member_b, member_c, member_d) in the
named tenant so that the governance role assignment tests have ≥2 distinct
members to work with. Uses the provisioner session (BYPASSRLS) so it can write
identity rows directly.

Does NOT create Cognito users — these members only need to EXIST in the DB for
assignment-time SoD tests; they don't need to log in during this sprint.

Usage (dev only):
    python -m scripts.seed.seed_dev_members --tenant-slug <slug>

Idempotent: runs again if members already exist without creating duplicates.
"""

from __future__ import annotations

import uuid
import sys

from sqlalchemy import select

from app.db.session import ProvisionerSessionLocal
from app.models import User, Membership
from app.models.base import UserRole


_DEV_MEMBERS = [
    {
        "cognito_sub": "dev-member-b-sub",
        "email": "member-b@dev.local",
        "display_name": "Dev Member B",
        "role": UserRole.MEMBER,
    },
    {
        "cognito_sub": "dev-member-c-sub",
        "email": "member-c@dev.local",
        "display_name": "Dev Member C",
        "role": UserRole.MEMBER,
    },
    {
        "cognito_sub": "dev-member-d-sub",
        "email": "member-d@dev.local",
        "display_name": "Dev Member D",
        "role": UserRole.MEMBER,
    },
]


def main(tenant_slug: str) -> None:
    from app.models import Tenant

    with ProvisionerSessionLocal() as session:
        tenant = session.scalar(select(Tenant).where(Tenant.slug == tenant_slug))
        if tenant is None:
            print(f"Tenant '{tenant_slug}' not found. Run provision_tenant first.")
            sys.exit(1)

        for spec in _DEV_MEMBERS:
            user = session.scalar(select(User).where(User.cognito_sub == spec["cognito_sub"]))
            if user is None:
                user = User(
                    id=uuid.uuid4(),
                    cognito_sub=spec["cognito_sub"],
                    email=spec["email"],
                    display_name=spec["display_name"],
                )
                session.add(user)
                session.flush()

            membership = session.scalar(
                select(Membership).where(
                    Membership.user_id == user.id,
                    Membership.tenant_id == tenant.id,
                )
            )
            if membership is None:
                membership = Membership(
                    id=uuid.uuid4(),
                    user_id=user.id,
                    tenant_id=tenant.id,
                    role=spec["role"],
                )
                session.add(membership)

        session.commit()
        print(f"Dev members seeded under tenant '{tenant_slug}'.")
        for spec in _DEV_MEMBERS:
            u = session.scalar(select(User).where(User.cognito_sub == spec["cognito_sub"]))
            m = session.scalar(select(Membership).where(
                Membership.user_id == u.id, Membership.tenant_id == tenant.id
            ))
            print(f"  {spec['email']}  user_id={u.id}  membership_id={m.id}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Seed dev memberships for SoD testing")
    parser.add_argument("--tenant-slug", required=True, help="Slug of an existing provisioned tenant")
    args = parser.parse_args()
    main(args.tenant_slug)
