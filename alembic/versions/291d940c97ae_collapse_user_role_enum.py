"""collapse_user_role_enum

Collapse membership.role from {ADMIN, REVIEWER, CONTRIBUTOR, AUDITOR_READONLY}
to {ADMIN, MEMBER}.

Data migration: CONTRIBUTOR, AUDITOR_READONLY, REVIEWER → MEMBER.
No governance roles are granted by this migration — remapping the
administrative column value is all it does. Users who need governance
capability must be granted the matching governance role explicitly via the
assignment endpoint.

DOWNGRADE NOTE: this is a LOSSY downgrade by design. The four-value enum is
restored, but rows remapped to MEMBER cannot be split back — they will all
land as CONTRIBUTOR. Do not rely on downgrade for data recovery; it exists
only for schema rollback in a fresh environment.

Revision ID: 291d940c97ae
Revises: 8b7d2f48a456
Create Date: 2026-06-13 13:30:07.214085
"""
from collections.abc import Sequence

from alembic import op


revision: str = '291d940c97ae'
down_revision: str | Sequence[str] | None = '8b7d2f48a456'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Postgres cannot drop enum values in place — create a new type,
    # migrate the column, then swap names.
    op.execute("CREATE TYPE user_role_v2 AS ENUM ('ADMIN', 'MEMBER')")

    op.execute("""
        ALTER TABLE membership
        ALTER COLUMN role TYPE user_role_v2
        USING CASE role::text
            WHEN 'ADMIN'            THEN 'ADMIN'::user_role_v2
            WHEN 'CONTRIBUTOR'      THEN 'MEMBER'::user_role_v2
            WHEN 'AUDITOR_READONLY' THEN 'MEMBER'::user_role_v2
            WHEN 'REVIEWER'         THEN 'MEMBER'::user_role_v2
            ELSE                         'MEMBER'::user_role_v2
        END
    """)

    op.execute("DROP TYPE user_role")
    op.execute("ALTER TYPE user_role_v2 RENAME TO user_role")


def downgrade() -> None:
    # Lossy: MEMBER rows all land as CONTRIBUTOR — original AUDITOR_READONLY
    # and REVIEWER values cannot be recovered. See module docstring.
    op.execute(
        "CREATE TYPE user_role_old AS ENUM "
        "('ADMIN', 'REVIEWER', 'CONTRIBUTOR', 'AUDITOR_READONLY')"
    )

    op.execute("""
        ALTER TABLE membership
        ALTER COLUMN role TYPE user_role_old
        USING CASE role::text
            WHEN 'ADMIN' THEN 'ADMIN'::user_role_old
            ELSE              'CONTRIBUTOR'::user_role_old
        END
    """)

    op.execute("DROP TYPE user_role")
    op.execute("ALTER TYPE user_role_old RENAME TO user_role")
