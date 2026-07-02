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

Resolution algorithm (DM-S4b, INV-82, D-71)
--------------------------------------------
When use_case.product_category_id is set (declared intended-use category):
  1. Find the declared category's primary EU AI Act mapping → governing tier.
     No primary mapping for the declared category → REQUIRES_CONTEXT.
  2. Also compute the product-wide-highest tier (retained query).
  3. disposition = AUTHORITATIVE if governing tier == product-wide-highest.
     disposition = DOWN_SELECTION  if governing tier  < product-wide-highest.

When use_case.product_category_id is null (no declaration; POST /use-cases
and legacy paths):
  - Product-wide-highest path unchanged; disposition = AUTHORITATIVE.
  - No product or no primary mappings → REQUIRES_CONTEXT.

REQUIRES_CONTEXT is an explicit terminal state, not an error. It is the seam
where the context-question wizard attaches.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models.assessment import Classification
from app.models.base import ClassificationDisposition, ClassificationStatus, EUAIActTier
from app.models.domain import System, UseCase
from app.models.lifecycle import AuditEvent
from app.models.taxonomy import (
    EUAIActSubcategory,
    ProductCategoryEUMapping,
    ProductCategoryMembership,
)
from app.services.lifecycle_service import advance_use_case

# Ordered from highest to lowest — used when multiple primary mappings resolve.
_TIER_ORDER: list[EUAIActTier] = [
    EUAIActTier.PROHIBITED,
    EUAIActTier.HIGH,
    EUAIActTier.LIMITED,
    EUAIActTier.MINIMAL,
]


def _tier_rank(tier: EUAIActTier) -> int:
    try:
        return _TIER_ORDER.index(tier)
    except ValueError:
        return len(_TIER_ORDER)


def _primary_mappings_for_product(product_id: uuid.UUID, db: Session):
    """Return all primary EU AI Act subcategory rows for a product."""
    return db.execute(
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
            ProductCategoryMembership.catalogue_product_id == product_id,
            ProductCategoryEUMapping.is_primary.is_(True),
        )
    ).all()


def _primary_mappings_for_category(product_id: uuid.UUID, category_id: uuid.UUID, db: Session):
    """Return primary EU AI Act subcategory rows for one specific product category."""
    return db.execute(
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
            ProductCategoryMembership.catalogue_product_id == product_id,
            ProductCategoryMembership.product_category_id == category_id,
            ProductCategoryEUMapping.is_primary.is_(True),
        )
    ).all()


@dataclass
class ClassificationProposal:
    """Result of resolve_classification. Immutable; writes nothing."""
    tier: EUAIActTier
    subcategory_code: str | None
    subcategory_name: str | None
    legal_ref: str | None
    rationale: str
    disposition: ClassificationDisposition = field(default=ClassificationDisposition.AUTHORITATIVE)

    @property
    def requires_context(self) -> bool:
        return self.tier == EUAIActTier.REQUIRES_CONTEXT


def resolve_classification(
    system_id: uuid.UUID,
    use_case_id: uuid.UUID | None,
    db: Session,
) -> ClassificationProposal:
    """Derive the proposed EU AI Act tier for a use case.

    Pure read; does not write to the DB. Declared-category-aware (D-71,
    INV-82): when use_case.product_category_id is set, the governing
    subcategory comes from that category's primary mapping. The null path
    falls through to the product-wide-highest algorithm (backward-compatible
    with POST /use-cases and legacy rows).

    use_case_id may be None (legacy / direct-service callers) — in that case
    the null declaration path is taken (product-wide-highest, AUTHORITATIVE).
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

    declared_category_id: uuid.UUID | None = None
    if use_case_id is not None:
        use_case = db.get(UseCase, use_case_id)
        if use_case is not None:
            declared_category_id = use_case.product_category_id

    if declared_category_id is not None:
        # Declared path: governing = declared category's primary mapping.
        declared_rows = _primary_mappings_for_category(
            system.catalogue_product_id, declared_category_id, db
        )
        if not declared_rows:
            return ClassificationProposal(
                tier=EUAIActTier.REQUIRES_CONTEXT,
                subcategory_code=None,
                subcategory_name=None,
                legal_ref=None,
                rationale=(
                    "The declared intended-use category has no primary EU AI Act mapping. "
                    "Context questions are required to determine the applicable tier."
                ),
            )

        governing = min(declared_rows, key=lambda r: _tier_rank(EUAIActTier(r.tier)))
        governing_tier = EUAIActTier(governing.tier)

        # Also compute product-wide-highest to determine disposition.
        all_rows = _primary_mappings_for_product(system.catalogue_product_id, db)
        product_best = min(all_rows, key=lambda r: _tier_rank(EUAIActTier(r.tier)))
        product_highest = EUAIActTier(product_best.tier)

        disposition = (
            ClassificationDisposition.AUTHORITATIVE
            if _tier_rank(governing_tier) <= _tier_rank(product_highest)
            else ClassificationDisposition.DOWN_SELECTION
        )

        rationale = (
            f"Governing subcategory derived from declared intended-use category: "
            f"{governing.code} ({governing.legal_ref or 'no legal ref'}). "
            f"Disposition: {disposition.value}."
        )
        return ClassificationProposal(
            tier=governing_tier,
            subcategory_code=governing.code,
            subcategory_name=governing.name,
            legal_ref=governing.legal_ref,
            rationale=rationale,
            disposition=disposition,
        )

    # Null path: product-wide-highest (backward-compatible with POST /use-cases).
    rows = _primary_mappings_for_product(system.catalogue_product_id, db)

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

    best = min(rows, key=lambda r: _tier_rank(EUAIActTier(r.tier)))
    tier = EUAIActTier(best.tier)

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
        disposition=ClassificationDisposition.AUTHORITATIVE,
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
    status: ClassificationStatus = ClassificationStatus.PENDING_REVIEW,
    stamp_eu_tier: bool = True,
    off_label: bool = False,
) -> Classification:
    """Persist a Classification snapshot. Unsets any prior is_current row first.

    Respects uq_current_classification: at most one is_current=True row per
    use_case. Always inserts a new row — never mutates an existing one.

    When stamp_eu_tier=True (default), updates use_case.eu_tier and
    use_case.eu_ai_act_subcategory_id. When False (DOWN_SELECTION path),
    eu_tier is left unstamped until reviewer sign-off (D-73).
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
        status=status,
        off_label=off_label,
    )
    db.add(classification)

    if stamp_eu_tier:
        use_case.eu_tier = proposal.tier
        db.add(use_case)

    db.flush()

    detail: dict = {
        "tier": proposal.tier.value,
        "basis_subcategory_code": proposal.subcategory_code,
        "basis_legal_ref": proposal.legal_ref,
        "version": version,
        "disposition": proposal.disposition.value,
        "off_label": off_label,
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

    # Sprint 5 WI-5: drives intake + the prohibited halt off this snapshot
    # becoming current. In-session, pre-commit — atomic with this write
    # (design doc §4.3, STATE_MACHINE.md inv 4).
    advance_use_case(db, use_case, actor_user_id)

    return classification
