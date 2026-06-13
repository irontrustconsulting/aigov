"""
EU AI Act classification service.

Two concerns, strictly separated:

  resolve_classification  — reads global reference data only, writes nothing.
                            Returns a ClassificationProposal describing the
                            proposed tier and its basis.

  snapshot_classification — writes the tenant-scoped Classification row,
                            unsets the prior current snapshot, updates the
                            use case's eu_tier, and stages an AuditEvent.
                            The caller owns the transaction.

Resolution algorithm
--------------------
1. The use case's system must have a catalogue_product_id.
   No product → REQUIRES_CONTEXT.
2. Traverse: product → product_category_membership → product_category_eu_mapping
   (is_primary=True) → eu_ai_act_subcategory.
3. No primary mappings across any of the product's categories → REQUIRES_CONTEXT.
4. One or more primary mappings → pick the one with the highest tier.
   Tier order (highest first): PROHIBITED > HIGH > LIMITED > MINIMAL.

REQUIRES_CONTEXT is an explicit terminal state, not an error. It is the seam
where the future context-question wizard will attach.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models.assessment import Classification
from app.models.base import EUAIActTier
from app.models.domain import System, UseCase
from app.models.lifecycle import AuditEvent
from app.models.taxonomy import (
    EUAIActSubcategory,
    ProductCategoryEUMapping,
    ProductCategoryMembership,
)

# Ordered from highest to lowest — used when multiple primary mappings resolve.
_TIER_ORDER: list[EUAIActTier] = [
    EUAIActTier.PROHIBITED,
    EUAIActTier.HIGH,
    EUAIActTier.LIMITED,
    EUAIActTier.MINIMAL,
]


@dataclass
class ClassificationProposal:
    """Result of resolve_classification. Immutable; writes nothing."""
    tier: EUAIActTier
    subcategory_code: str | None
    subcategory_name: str | None
    legal_ref: str | None
    rationale: str

    @property
    def requires_context(self) -> bool:
        return self.tier == EUAIActTier.REQUIRES_CONTEXT


def resolve_classification(system_id: uuid.UUID, db: Session) -> ClassificationProposal:
    """Derive the proposed EU AI Act tier for a use case by traversing the
    seeded reference bridge. Pure read; does not write to the DB.

    The db session may be the RLS-scoped tenant session (the system row is
    tenant-scoped) or a reference session — the reference tables are global.
    The global tables (product_category_membership, product_category_eu_mapping,
    eu_ai_act_subcategory) carry no RLS and are readable from either session.
    """
    system = db.get(System, system_id)
    if system is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="System not found")

    if system.catalogue_product_id is None:
        return ClassificationProposal(
            tier=EUAIActTier.REQUIRES_CONTEXT,
            subcategory_code=None,
            subcategory_name=None,
            legal_ref=None,
            rationale=(
                "System has no catalogue product link. "
                "Context questions are required to determine the applicable tier."
            ),
        )

    # Fetch all PRIMARY mappings across the product's categories in one query.
    rows = db.execute(
        select(
            EUAIActSubcategory.code,
            EUAIActSubcategory.name,
            EUAIActSubcategory.tier,
            EUAIActSubcategory.legal_ref,
        )
        .join(
            ProductCategoryEUMapping,
            ProductCategoryEUMapping.eu_ai_act_subcategory_id == EUAIActSubcategory.id,
        )
        .join(
            ProductCategoryMembership,
            ProductCategoryMembership.product_category_id
            == ProductCategoryEUMapping.product_category_id,
        )
        .where(
            ProductCategoryMembership.catalogue_product_id
            == system.catalogue_product_id,
            ProductCategoryEUMapping.is_primary.is_(True),
        )
    ).all()

    if not rows:
        return ClassificationProposal(
            tier=EUAIActTier.REQUIRES_CONTEXT,
            subcategory_code=None,
            subcategory_name=None,
            legal_ref=None,
            rationale=(
                "None of the product's categories has a primary EU AI Act mapping. "
                "Context questions are required to determine the applicable tier."
            ),
        )

    # Pick the highest-tier row. Rows not in _TIER_ORDER (shouldn't happen
    # with clean seed data, but be safe) sort below MINIMAL.
    def _tier_rank(row) -> int:
        try:
            return _TIER_ORDER.index(EUAIActTier(row.tier))
        except ValueError:
            return len(_TIER_ORDER)

    best = min(rows, key=_tier_rank)
    tier = EUAIActTier(best.tier)

    # Build a human-readable rationale.
    all_codes = ", ".join(r.code for r in rows)
    rationale = (
        f"Derived from product category primary mappings: [{all_codes}]. "
        f"Governing subcategory: {best.code} ({best.legal_ref or 'no legal ref'}) — "
        f"highest applicable tier."
    )
    if len(rows) == 1:
        rationale = (
            f"Derived from product category primary mapping: {best.code} "
            f"({best.legal_ref or 'no legal ref'})."
        )

    return ClassificationProposal(
        tier=tier,
        subcategory_code=best.code,
        subcategory_name=best.name,
        legal_ref=best.legal_ref,
        rationale=rationale,
    )


def snapshot_classification(
    use_case: UseCase,
    proposal: ClassificationProposal,
    db: Session,
    *,
    actor_user_id: uuid.UUID,
    overridden: bool = False,
    proposed_tier: EUAIActTier | None = None,
    justification: str | None = None,
) -> Classification:
    """Persist a Classification snapshot. Unsets any prior is_current row first.

    Respects uq_current_classification: at most one is_current=True row per
    use_case. Always inserts a new row — never mutates an existing one.

    Updates use_case.eu_tier and use_case.eu_ai_act_subcategory_id to keep
    the use case's own current tier in sync with the latest snapshot.
    """
    # Unset prior current snapshot (if any).
    db.execute(
        update(Classification)
        .where(
            Classification.use_case_id == use_case.id,
            Classification.is_current.is_(True),
        )
        .values(is_current=False)
    )

    # Determine version number.
    prior_version = db.scalar(
        select(Classification.version)
        .where(Classification.use_case_id == use_case.id)
        .order_by(Classification.version.desc())
        .limit(1)
    )
    version = (prior_version or 0) + 1

    rationale = proposal.rationale
    if overridden and justification:
        rationale = f"{rationale}\n\nOverride justification: {justification}"
    elif overridden:
        rationale = f"{rationale}\n\nTier overridden by user."

    classification = Classification(
        id=uuid.uuid4(),
        tenant_id=use_case.tenant_id,
        use_case_id=use_case.id,
        tier=proposal.tier,
        rationale=rationale,
        answers_blob={},
        version=version,
        is_current=True,
        overridden=overridden,
        proposed_tier=proposed_tier,
        basis_subcategory_code=proposal.subcategory_code,
        basis_legal_ref=proposal.legal_ref,
    )
    db.add(classification)

    # Keep the use case's denormalised tier current.
    use_case.eu_tier = proposal.tier
    db.add(use_case)

    db.flush()

    detail: dict = {
        "tier": proposal.tier.value,
        "basis_subcategory_code": proposal.subcategory_code,
        "basis_legal_ref": proposal.legal_ref,
        "version": version,
    }
    if overridden:
        detail["proposed_tier"] = proposed_tier.value if proposed_tier else None
        detail["justification"] = justification

    db.add(AuditEvent(
        id=uuid.uuid4(),
        tenant_id=use_case.tenant_id,
        actor_user_id=actor_user_id,
        action="classification.overridden" if overridden else "classification.created",
        entity_type="classification",
        entity_id=classification.id,
        detail=detail,
    ))

    return classification
