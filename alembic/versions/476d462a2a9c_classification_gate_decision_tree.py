"""classification_gate_decision_tree

Adds the decision-tree reference tables used by the Classification Gate sprint
(WI-1) and the classification.status column (additive schema delta, §10).

New global reference tables (no tenant_id, no RLS):
  decision_tree, decision_tree_question, decision_tree_option

New Postgres enum: classification_status
Additive column:   classification.status (PENDING_REVIEW default)

Revision ID: 476d462a2a9c
Revises: ff6654ebd569
Create Date: 2026-06-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "476d462a2a9c"
down_revision: str | Sequence[str] | None = "ff6654ebd569"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. New classification_status enum type
    # ------------------------------------------------------------------
    op.execute(sa.text(
        "CREATE TYPE classification_status AS ENUM "
        "('pending_review', 'approved', 'changes_requested', 'needs_refresh')"
    ))

    # ------------------------------------------------------------------
    # 2 – 4. Decision-tree reference tables (raw DDL to avoid SQLAlchemy
    #         re-creating the existing eu_ai_act_tier enum type).
    # ------------------------------------------------------------------
    op.execute(sa.text("""
        CREATE TABLE decision_tree (
            id          UUID PRIMARY KEY,
            version     VARCHAR(50)  NOT NULL,
            name        VARCHAR(255) NOT NULL,
            content_hash VARCHAR(64) NOT NULL,
            created_at  TIMESTAMPTZ  NOT NULL DEFAULT now(),
            updated_at  TIMESTAMPTZ  NOT NULL DEFAULT now(),
            CONSTRAINT  uq_decision_tree_version UNIQUE (version)
        )
    """))
    op.execute(sa.text(
        "CREATE INDEX ix_decision_tree_version ON decision_tree (version)"
    ))

    op.execute(sa.text("""
        CREATE TABLE decision_tree_question (
            id            UUID PRIMARY KEY,
            tree_id       UUID         NOT NULL
                              REFERENCES decision_tree(id) ON DELETE CASCADE,
            question_code VARCHAR(80)  NOT NULL,
            text          TEXT         NOT NULL,
            probes_rung   eu_ai_act_tier,
            legal_ref     VARCHAR(120),
            sort_order    INTEGER      NOT NULL DEFAULT 0,
            CONSTRAINT uq_dtq_tree_code UNIQUE (tree_id, question_code)
        )
    """))
    op.execute(sa.text(
        "CREATE INDEX ix_decision_tree_question_tree_id "
        "ON decision_tree_question (tree_id)"
    ))

    op.execute(sa.text("""
        CREATE TABLE decision_tree_option (
            id                      UUID PRIMARY KEY,
            question_id             UUID        NOT NULL
                                        REFERENCES decision_tree_question(id)
                                        ON DELETE CASCADE,
            option_code             VARCHAR(80) NOT NULL,
            label                   VARCHAR(255) NOT NULL,
            asserts_rung            eu_ai_act_tier,
            asserts_subcategory_code VARCHAR(80),
            CONSTRAINT uq_dto_question_code UNIQUE (question_id, option_code)
        )
    """))
    op.execute(sa.text(
        "CREATE INDEX ix_decision_tree_option_question_id "
        "ON decision_tree_option (question_id)"
    ))

    # ------------------------------------------------------------------
    # 5. classification.status column (additive, backfill then constrain)
    # ------------------------------------------------------------------
    op.execute(sa.text(
        "ALTER TABLE classification "
        "ADD COLUMN status classification_status NOT NULL DEFAULT 'pending_review'"
    ))
    # Remove the server default after backfill; the Python model default
    # handles new rows and we don't want a silent DB-level fallback.
    op.execute(sa.text(
        "ALTER TABLE classification ALTER COLUMN status DROP DEFAULT"
    ))

    # ------------------------------------------------------------------
    # 6. Grants for the app role (SELECT only — curated reference data)
    # ------------------------------------------------------------------
    op.execute(sa.text("GRANT SELECT ON decision_tree TO irontrustai_app"))
    op.execute(sa.text("GRANT SELECT ON decision_tree_question TO irontrustai_app"))
    op.execute(sa.text("GRANT SELECT ON decision_tree_option TO irontrustai_app"))


def downgrade() -> None:
    op.execute(sa.text("ALTER TABLE classification DROP COLUMN status"))
    op.execute(sa.text("DROP TYPE IF EXISTS classification_status"))
    op.execute(sa.text("DROP TABLE IF EXISTS decision_tree_option"))
    op.execute(sa.text("DROP TABLE IF EXISTS decision_tree_question"))
    op.execute(sa.text("DROP TABLE IF EXISTS decision_tree"))
