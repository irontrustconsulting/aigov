"""fix_enum_label_case

Revision ID: 3a5b36bdd37a
Revises: 4cca0f3a200c
Create Date: 2026-06-20 11:45:29.500700

Pre-existing bug, unrelated to this sprint, discovered while live-smoke-
testing Sprint 5 (sprints/SPRINT_LIFECYCLE.md) against the real dev Postgres:
the test DB's schema is generated fresh from the ORM (Base.metadata.create_all,
self-consistent by construction), but every real migrated DB carries whatever
the hand-written DDL actually said -- and three enum types were created with
some or all labels in the wrong case. SQLAlchemy's Enum(SomePyEnum, ...)
binds by the Python member NAME by default (no values_callable anywhere in
this codebase, confirmed STATE.md inv 23), so a label that doesn't match the
uppercase member name makes that value un-writable in the real DB:

  - classification_status: ALL FOUR labels lowercase -- every
    snapshot_classification/compute_and_record_classification write fails
    (the column's Python-side default is ClassificationStatus.PENDING_REVIEW,
    which the ORM serializes as 'PENDING_REVIEW', a label the type doesn't
    have). This is the first write in use-case registration, so the bridge
    classification path is broken end-to-end against any real migrated DB.
  - eu_ai_act_tier: only REQUIRES_CONTEXT is lowercase ('requires_context'),
    its four siblings are correctly uppercase -- a use case the bridge can't
    resolve (no catalogue product / no primary mapping) fails to stamp
    eu_tier=REQUIRES_CONTEXT.
  - system_lifecycle_stage: ALL FOUR labels lowercase. Already flagged in
    STATE.md (added during this sprint's WI-9); included here as long as a
    fix migration is being written for the same class of bug. The field is
    not written by any code path today, so this one is precautionary.

ALTER TYPE ... RENAME VALUE is non-destructive: existing rows keep their
data, only the label text changes, so this needs no data migration/backfill.
"""
from collections.abc import Sequence

from alembic import op

revision: str = '3a5b36bdd37a'
down_revision: str | Sequence[str] | None = '4cca0f3a200c'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_RENAMES: dict[str, list[tuple[str, str]]] = {
    'classification_status': [
        ('pending_review', 'PENDING_REVIEW'),
        ('approved', 'APPROVED'),
        ('changes_requested', 'CHANGES_REQUESTED'),
        ('needs_refresh', 'NEEDS_REFRESH'),
    ],
    'eu_ai_act_tier': [
        ('requires_context', 'REQUIRES_CONTEXT'),
    ],
    'system_lifecycle_stage': [
        ('development', 'DEVELOPMENT'),
        ('pilot', 'PILOT'),
        ('production', 'PRODUCTION'),
        ('retired', 'RETIRED'),
    ],
}


def upgrade() -> None:
    for enum_name, renames in _RENAMES.items():
        for old, new in renames:
            op.execute(f"ALTER TYPE {enum_name} RENAME VALUE '{old}' TO '{new}'")


def downgrade() -> None:
    for enum_name, renames in _RENAMES.items():
        for old, new in renames:
            op.execute(f"ALTER TYPE {enum_name} RENAME VALUE '{new}' TO '{old}'")
