"""
AssessmentService — AIIA core (sprints/SPRINT_AIIA.md, Phase A).

Tenant-plane pattern throughout: no external call, so every mutation stages
its AuditEvent and db.flush()s in the caller's transaction (get_tenant_db
commits at request end). tenant_id is always taken from ctx.tenant_id, never
trusted from a loaded row's FK alone — every query re-filters on it
(belt-and-suspenders, matching use_cases.py: RLS enforces it in prod, the
explicit filter enforces it in the no-RLS test DB).

Provenance is server-derived everywhere here — no function in this module
accepts a provenance value as input.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from fastapi import HTTPException, status
from sqlalchemy import and_, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.context import TenantContext
from app.models.assessment import (
    Assessment,
    AssessmentItem,
    AssessmentItemControl,
    AssessmentSectionTemplate,
    Classification,
)
from app.models.base import (
    AssessmentType,
    CoverageStatus,
    EUAIActTier,
    ProvenanceConfidence,
    RiskLayer,
    SectionApplicability,
)
from app.models.domain import CatalogueProduct, CatalogueProductRisk, System, UseCase
from app.models.intake import (
    AffectedParty,
    DataCategory,
    EUOperatorRole,
    HostingModel,
    HumanOversightType,
    SystemAffectedParty,
    SystemDataCategory,
    UsageContext,
)
from app.models.knowledge import Control, Risk
from app.models.lifecycle import AuditEvent
from app.schemas.assessment import (
    AssessmentItemAmend,
    AssessmentItemRead,
    FeederRecommendationRead,
)

# Section keys items attach to (must match the seeded template's
# section_key — see data/seed/aiia_section_template.yaml). The risk
# sections get no curated framing item of their own (see
# _instantiate_required_sections) — they're populated entirely by
# AI_SUGGESTED proposed risk items.
RISK_SECTION_KEY = "risk_identification"                        # AIIA
MODEL_RISK_RISK_SECTION_KEY = "model_risk_identified_risks"      # MODEL_RISK feeder
OVERVIEW_SECTION_KEY = "system_overview"                         # AIIA
FRIA_AFFECTED_PERSONS_SECTION_KEY = "fria_affected_persons"
DPIA_DATA_CATEGORIES_SECTION_KEY = "dpia_data_categories"
MODEL_RISK_DESCRIPTION_SECTION_KEY = "model_risk_model_description"

_RISK_SECTION_BY_TYPE: dict[AssessmentType, str] = {
    AssessmentType.AIIA: RISK_SECTION_KEY,
    AssessmentType.MODEL_RISK: MODEL_RISK_RISK_SECTION_KEY,
}

# At most one feeder of each type per AIIA (design doc §5.2).
FEEDER_TYPES = (AssessmentType.FRIA, AssessmentType.DPIA, AssessmentType.MODEL_RISK)

# Authoring fields a PATCH may touch. Disposition-before-authoring blocks
# these on a still-AI_SUGGESTED item (design doc §4).
_AUTHORING_FIELDS = (
    "response", "likelihood", "severity",
    "residual_likelihood", "residual_severity", "mitigation_plan",
)


@dataclass
class ProposedRisk:
    """Identity + shown reasoning only — never scores (design doc §4)."""
    risk_id: uuid.UUID
    selection_basis: str


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _load_use_case(use_case_id: uuid.UUID, ctx: TenantContext, db: Session) -> UseCase:
    use_case = db.scalar(
        select(UseCase).where(
            UseCase.id == use_case_id, UseCase.tenant_id == ctx.tenant_id,
        )
    )
    if use_case is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Use case not found")
    return use_case


def _load_current_classification(
    use_case_id: uuid.UUID, db: Session,
) -> Classification | None:
    return db.scalar(
        select(Classification).where(
            Classification.use_case_id == use_case_id,
            Classification.is_current.is_(True),
        )
    )


def load_assessment(
    assessment_id: uuid.UUID, ctx: TenantContext, db: Session,
) -> Assessment:
    assessment = db.scalar(
        select(Assessment).where(
            Assessment.id == assessment_id, Assessment.tenant_id == ctx.tenant_id,
        )
    )
    if assessment is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Assessment not found")
    return assessment


def _load_item(item_id: uuid.UUID, ctx: TenantContext, db: Session) -> AssessmentItem:
    item = db.scalar(
        select(AssessmentItem).where(
            AssessmentItem.id == item_id, AssessmentItem.tenant_id == ctx.tenant_id,
        )
    )
    if item is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail="Assessment item not found",
        )
    return item


def _resolve_label(db: Session, model, id_: uuid.UUID | None) -> str | None:
    if id_ is None:
        return None
    row = db.get(model, id_)
    return row.label if row is not None else None


def _stage_audit(
    db: Session, *, tenant_id: uuid.UUID, actor_user_id: uuid.UUID,
    action: str, entity_type: str, entity_id: uuid.UUID, detail: dict,
) -> None:
    db.add(AuditEvent(
        id=uuid.uuid4(), tenant_id=tenant_id, actor_user_id=actor_user_id,
        action=action, entity_type=entity_type, entity_id=entity_id, detail=detail,
    ))


def _add_snapshot_item(
    db: Session, ctx: TenantContext, assessment: Assessment, *,
    section_key: str, prompt: str, response: str, source_ref: str,
) -> None:
    """USER_PROVIDED, point-in-time snapshot of a register fact — the
    resolved label is frozen, never the bare FK id (design doc §5/§5.4)."""
    db.add(AssessmentItem(
        id=uuid.uuid4(), tenant_id=ctx.tenant_id, assessment_id=assessment.id,
        section_key=section_key, prompt=prompt, response=response,
        provenance=ProvenanceConfidence.USER_PROVIDED, source_ref=source_ref,
    ))


def _instantiate_required_sections(
    db: Session, ctx: TenantContext, assessment: Assessment,
    template_rows: list[AssessmentSectionTemplate], *, skip_section_key: str | None,
) -> int:
    """CATALOGUE_CURATED, blank response, one per required template row.
    skip_section_key excludes the type's risk section — that one is
    populated entirely by AI_SUGGESTED proposed risk items instead."""
    count = 0
    for tmpl in template_rows:
        if tmpl.applicability != SectionApplicability.REQUIRED:
            continue
        if tmpl.section_key == skip_section_key:
            continue
        db.add(AssessmentItem(
            id=uuid.uuid4(), tenant_id=ctx.tenant_id, assessment_id=assessment.id,
            section_key=tmpl.section_key, prompt=tmpl.prompt,
            provenance=ProvenanceConfidence.CATALOGUE_CURATED,
        ))
        count += 1
    return count


def _add_proposed_risk_items(
    db: Session, ctx: TenantContext, assessment: Assessment,
    proposed: list[ProposedRisk], section_key: str,
) -> None:
    for p in proposed:
        db.add(AssessmentItem(
            id=uuid.uuid4(), tenant_id=ctx.tenant_id, assessment_id=assessment.id,
            section_key=section_key, risk_id=p.risk_id,
            provenance=ProvenanceConfidence.AI_SUGGESTED,
            selection_basis=p.selection_basis,
        ))


# ---------------------------------------------------------------------------
# Risk proposal (pure read composition)
# ---------------------------------------------------------------------------

def propose_risk_set(
    assessment_type: AssessmentType,
    tier: EUAIActTier,
    modality_tags: list[str],
    catalogue_product_id: uuid.UUID | None,
    db: Session,
) -> list[ProposedRisk]:
    """Identity + selection_basis only — never scores. Layer-aware by
    assessment type (Phase B design doc §5.5):
      AIIA        -> governance-layer (NIST/ISO) library risks + CatalogueProductRisk
      MODEL_RISK  -> technical-layer (OWASP LLM Top 10) library risks
      FRIA / DPIA -> none — rights/data-subject risks are human-identified
                     via the feeder's own sections, not auto-proposed.
    Best-effort: no catalogue product or no CatalogueProductRisk rows ->
    that source contributes nothing, not an error (design doc §11).
    modality_tags is an accepted forward-looking seam (no modality data
    model exists yet) — unused this sprint.
    """
    del modality_tags  # forward-looking seam, unused this sprint

    proposed: list[ProposedRisk] = []
    seen_risk_ids: set[uuid.UUID] = set()

    if assessment_type == AssessmentType.AIIA:
        for risk_id in db.scalars(
            select(Risk.id).where(Risk.layer == RiskLayer.GOVERNANCE_RIGHTS)
        ):
            seen_risk_ids.add(risk_id)
            proposed.append(ProposedRisk(
                risk_id=risk_id,
                selection_basis=f"Governance-layer risk (NIST/ISO), tier {tier.value}",
            ))
        if catalogue_product_id is not None:
            for row in db.scalars(
                select(CatalogueProductRisk).where(
                    CatalogueProductRisk.product_id == catalogue_product_id,
                )
            ):
                if row.risk_id in seen_risk_ids:
                    continue
                seen_risk_ids.add(row.risk_id)
                basis = f"CatalogueProductRisk, product {catalogue_product_id}"
                proposed.append(
                    ProposedRisk(risk_id=row.risk_id, selection_basis=basis)
                )

    elif assessment_type == AssessmentType.MODEL_RISK:
        for risk_id in db.scalars(
            select(Risk.id).where(Risk.layer == RiskLayer.TECHNICAL_SECURITY)
        ):
            proposed.append(ProposedRisk(
                risk_id=risk_id,
                selection_basis="Technical-layer risk (OWASP LLM Top 10)",
            ))

    # FRIA / DPIA: no auto-proposal — fall through with an empty list.
    return proposed


# ---------------------------------------------------------------------------
# AIIA creation (Phase A's demoable vertical slice)
# ---------------------------------------------------------------------------

def create_aiia(use_case_id: uuid.UUID, ctx: TenantContext, db: Session) -> Assessment:
    use_case = _load_use_case(use_case_id, ctx, db)
    system = db.get(System, use_case.system_id)

    classification = _load_current_classification(use_case_id, db)
    if classification is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="Use case has no current classification snapshot",
        )
    if classification.tier == EUAIActTier.PROHIBITED:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="Use case is classified PROHIBITED; no assessment may be created",
        )
    if classification.tier == EUAIActTier.REQUIRES_CONTEXT:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="Use case requires classification context before scoping an AIIA",
        )

    tier_snapshot = classification.tier
    classification_version = classification.version

    # App-level pre-check, belt-and-suspenders with the DB-level partial
    # unique index (uq_one_aiia_per_use_case — hand-written in the
    # migration, so it doesn't exist in a Base.metadata.create_all test DB).
    # The IntegrityError catch below still covers a genuine creation race.
    existing_current = db.scalar(
        select(Assessment.id).where(
            Assessment.use_case_id == use_case_id,
            Assessment.type == AssessmentType.AIIA,
            Assessment.is_current.is_(True),
        ).limit(1)
    )
    if existing_current is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="A current AIIA already exists for this use case",
        )

    template_rows = list(db.scalars(
        select(AssessmentSectionTemplate).where(
            AssessmentSectionTemplate.type == AssessmentType.AIIA,
            AssessmentSectionTemplate.tier == tier_snapshot,
        ).order_by(AssessmentSectionTemplate.sort_order)
    ))
    if not template_rows:
        # Seeding bug, not a client error — fail loudly rather than create
        # an empty shell (design doc §5/§8.12).
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"No section template seeded for (AIIA, {tier_snapshot.value})",
        )

    assessment = Assessment(
        id=uuid.uuid4(),
        tenant_id=ctx.tenant_id,
        use_case_id=use_case_id,
        type=AssessmentType.AIIA,
        tier_snapshot=tier_snapshot,
        classification_version=classification_version,
        created_by=ctx.user_id,
    )
    db.add(assessment)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="A current AIIA already exists for this use case",
        ) from exc

    # --- Pre-fill 1: required sections, CATALOGUE_CURATED, blank response ---
    # The risk section is populated entirely by proposed risk items (Pre-fill
    # 3) — it gets no curated framing item of its own, or every AIIA would
    # carry a permanently-blank "answer this" item sitting next to its risks.
    required_count = _instantiate_required_sections(
        db, ctx, assessment, template_rows, skip_section_key=RISK_SECTION_KEY,
    )

    # --- Pre-fill 2: snapshot inherited register facts (USER_PROVIDED) ------
    snapshot_count = 0
    if system is not None:
        snapshot_facts: list[tuple[str, str, str]] = [
            (f"System name: {system.name}", system.name, "system.name"),
        ]
        if use_case.purpose:
            snapshot_facts.append((
                f"Use case purpose: {use_case.purpose}",
                use_case.purpose, "use_case.purpose",
            ))
        _fk_dimensions = (
            ("Operator role", EUOperatorRole,
             system.operator_role_id, "system.operator_role_id"),
            ("Hosting model", HostingModel,
             system.hosting_model_id, "system.hosting_model_id"),
            ("Usage context", UsageContext,
             system.usage_context_id, "system.usage_context_id"),
            ("Human oversight type", HumanOversightType,
             system.human_oversight_type_id, "system.human_oversight_type_id"),
        )
        for label_prefix, model, fk_id, ref in _fk_dimensions:
            label = _resolve_label(db, model, fk_id)
            if label is not None:
                snapshot_facts.append(
                    (f"{label_prefix}: {label}", label, f"{ref}:{fk_id}")
                )

        for prompt, response, source_ref in snapshot_facts:
            _add_snapshot_item(
                db, ctx, assessment, section_key=OVERVIEW_SECTION_KEY,
                prompt=prompt, response=response, source_ref=source_ref,
            )
            snapshot_count += 1

    # --- Pre-fill 3: identity-only proposed risks (AI_SUGGESTED) ------------
    proposed = propose_risk_set(
        AssessmentType.AIIA, tier_snapshot, [],
        system.catalogue_product_id if system else None,
        db,
    )
    _add_proposed_risk_items(db, ctx, assessment, proposed, RISK_SECTION_KEY)

    _stage_audit(
        db, tenant_id=ctx.tenant_id, actor_user_id=ctx.user_id,
        action="assessment.created", entity_type="assessment", entity_id=assessment.id,
        detail={
            "tier_snapshot": tier_snapshot.value,
            "classification_version": classification_version,
            "required_sections": required_count,
            "snapshotted_facts": snapshot_count,
            "proposed_risk_ids": [str(p.risk_id) for p in proposed],
        },
    )
    db.flush()
    return assessment


# ---------------------------------------------------------------------------
# Feeder creation (Phase B — sprints/SPRINT_AIIA_FEEDERS.md)
# ---------------------------------------------------------------------------

def create_feeder(
    parent_aiia_id: uuid.UUID, feeder_type: AssessmentType,
    ctx: TenantContext, db: Session,
) -> Assessment:
    """A feeder is an `assessment` row — reuses every Phase-A item/control/
    provenance/concurrency/audit mechanism unchanged. Scope (tier_snapshot,
    classification_version) is copied from the parent AIIA, never
    re-resolved (design doc §5.2)."""
    if feeder_type not in FEEDER_TYPES:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"type={feeder_type.value} cannot be created as a feeder",
        )

    parent = load_assessment(parent_aiia_id, ctx, db)
    if parent.type != AssessmentType.AIIA:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="A feeder cannot parent another feeder",
        )

    # App-level pre-check, belt-and-suspenders with the DB-level
    # uq_feeder_type_per_aiia constraint (a plain, non-partial unique
    # constraint, so it does exist in a Base.metadata.create_all test DB —
    # unlike uq_one_aiia_per_use_case). The IntegrityError catch below still
    # covers a genuine creation race.
    existing = db.scalar(
        select(Assessment.id).where(
            Assessment.parent_aiia_id == parent.id,
            Assessment.type == feeder_type,
        ).limit(1)
    )
    if existing is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail=f"A {feeder_type.value} feeder already exists for this AIIA",
        )

    template_rows = list(db.scalars(
        select(AssessmentSectionTemplate).where(
            AssessmentSectionTemplate.type == feeder_type,
            AssessmentSectionTemplate.tier == parent.tier_snapshot,
        ).order_by(AssessmentSectionTemplate.sort_order)
    ))
    if not template_rows:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                f"No section template seeded for "
                f"({feeder_type.value}, {parent.tier_snapshot.value})"
            ),
        )

    feeder = Assessment(
        id=uuid.uuid4(),
        tenant_id=ctx.tenant_id,
        use_case_id=parent.use_case_id,
        type=feeder_type,
        parent_aiia_id=parent.id,
        tier_snapshot=parent.tier_snapshot,
        classification_version=parent.classification_version,
        created_by=ctx.user_id,
    )
    db.add(feeder)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail=f"A {feeder_type.value} feeder already exists for this AIIA",
        ) from exc

    risk_section_key = _RISK_SECTION_BY_TYPE.get(feeder_type)
    required_count = _instantiate_required_sections(
        db, ctx, feeder, template_rows, skip_section_key=risk_section_key,
    )

    use_case = db.get(UseCase, parent.use_case_id)
    system = db.get(System, use_case.system_id) if use_case else None
    snapshot_count = 0
    proposed: list[ProposedRisk] = []

    if system is not None and feeder_type == AssessmentType.FRIA:
        for link in db.scalars(
            select(SystemAffectedParty)
            .where(SystemAffectedParty.system_id == system.id)
        ):
            label = _resolve_label(db, AffectedParty, link.affected_party_id)
            if label is None:
                continue
            _add_snapshot_item(
                db, ctx, feeder, section_key=FRIA_AFFECTED_PERSONS_SECTION_KEY,
                prompt=f"Affected party: {label}", response=label,
                source_ref=f"system_affected_party:{link.affected_party_id}",
            )
            snapshot_count += 1

    elif system is not None and feeder_type == AssessmentType.DPIA:
        for link in db.scalars(
            select(SystemDataCategory).where(SystemDataCategory.system_id == system.id)
        ):
            label = _resolve_label(db, DataCategory, link.data_category_id)
            if label is None:
                continue
            _add_snapshot_item(
                db, ctx, feeder, section_key=DPIA_DATA_CATEGORIES_SECTION_KEY,
                prompt=f"Data category: {label}", response=label,
                source_ref=f"system_data_category:{link.data_category_id}",
            )
            snapshot_count += 1

    elif system is not None and feeder_type == AssessmentType.MODEL_RISK:
        model_facts: list[tuple[str, str, str]] = []
        if system.catalogue_product_id is not None:
            product = db.get(CatalogueProduct, system.catalogue_product_id)
            if product is not None:
                model_facts.append((
                    "Catalogue product", product.name,
                    f"system.catalogue_product_id:{product.id}",
                ))
        hosting_label = _resolve_label(db, HostingModel, system.hosting_model_id)
        if hosting_label is not None:
            model_facts.append((
                "Hosting model", hosting_label,
                f"system.hosting_model_id:{system.hosting_model_id}",
            ))
        for label_prefix, value, source_ref in model_facts:
            _add_snapshot_item(
                db, ctx, feeder, section_key=MODEL_RISK_DESCRIPTION_SECTION_KEY,
                prompt=f"{label_prefix}: {value}", response=value,
                source_ref=source_ref,
            )
            snapshot_count += 1

        proposed = propose_risk_set(
            AssessmentType.MODEL_RISK, parent.tier_snapshot, [],
            system.catalogue_product_id, db,
        )
        _add_proposed_risk_items(db, ctx, feeder, proposed, MODEL_RISK_RISK_SECTION_KEY)

    _stage_audit(
        db, tenant_id=ctx.tenant_id, actor_user_id=ctx.user_id,
        action="assessment.feeder_created", entity_type="assessment",
        entity_id=feeder.id,
        detail={
            "parent_aiia_id": str(parent.id),
            "type": feeder_type.value,
            "required_sections": required_count,
            "snapshotted_facts": snapshot_count,
            "proposed_risk_ids": [str(p.risk_id) for p in proposed],
        },
    )
    db.flush()
    return feeder


# ---------------------------------------------------------------------------
# AIIA detail propagation (Phase B — read-time reference, never copy)
# ---------------------------------------------------------------------------

def assemble_aiia_items(aiia: Assessment, db: Session) -> list[AssessmentItemRead]:
    """Native items pass through unchanged. Feeder items whose
    (feeder.type, feeder.tier_snapshot, item.section_key) resolves via
    aiia_target_section_key are surfaced too, re-keyed to the AIIA section
    they map into and tagged with source_assessment_id/source_type
    (design doc §5.6). Feeder-private items (NULL target) are excluded —
    they surface only in that feeder's own GET /assessments/{feeder_id}.
    Read-time only: nothing here is written back; provenance, created_by,
    and control links all travel with the item by id, untouched."""
    native_items = list(db.scalars(
        select(AssessmentItem).where(AssessmentItem.assessment_id == aiia.id)
        .order_by(AssessmentItem.created_at)
    ))
    result = [AssessmentItemRead.model_validate(i) for i in native_items]

    if aiia.type != AssessmentType.AIIA:
        return result  # feeders surface nothing of their own — own view only

    feeders = list(db.scalars(
        select(Assessment).where(Assessment.parent_aiia_id == aiia.id)
    ))
    for feeder in feeders:
        target_by_section_key = dict(db.execute(
            select(
                AssessmentSectionTemplate.section_key,
                AssessmentSectionTemplate.aiia_target_section_key,
            ).where(
                AssessmentSectionTemplate.type == feeder.type,
                AssessmentSectionTemplate.tier == feeder.tier_snapshot,
                AssessmentSectionTemplate.aiia_target_section_key.is_not(None),
            )
        ).all())
        if not target_by_section_key:
            continue

        feeder_items = list(db.scalars(
            select(AssessmentItem).where(
                AssessmentItem.assessment_id == feeder.id,
                AssessmentItem.section_key.in_(target_by_section_key.keys()),
            )
        ))
        for item in feeder_items:
            data = AssessmentItemRead.model_validate(item).model_dump()
            data["section_key"] = target_by_section_key[item.section_key]
            data["source_assessment_id"] = feeder.id
            data["source_type"] = feeder.type
            result.append(AssessmentItemRead(**data))

    return result


# ---------------------------------------------------------------------------
# Feeder recommendations (design doc §5.3) — strong default + shown
# reasoning; the user confirms by creating, the platform never auto-creates.
# ---------------------------------------------------------------------------

def get_feeder_recommendations(
    aiia_id: uuid.UUID, ctx: TenantContext, db: Session,
) -> list[FeederRecommendationRead]:
    aiia = load_assessment(aiia_id, ctx, db)
    if aiia.type != AssessmentType.AIIA:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Feeder recommendations apply to an AIIA, not a feeder",
        )

    use_case = db.get(UseCase, aiia.use_case_id)
    system = db.get(System, use_case.system_id) if use_case else None
    is_high = aiia.tier_snapshot == EUAIActTier.HIGH

    existing_types = set(db.scalars(
        select(Assessment.type).where(Assessment.parent_aiia_id == aiia.id)
    ))

    is_deployer = False
    if system is not None and system.operator_role_id is not None:
        role = db.get(EUOperatorRole, system.operator_role_id)
        is_deployer = role is not None and role.code == "deployer"

    if is_high and is_deployer:
        fria_app = SectionApplicability.REQUIRED
        fria_basis = "EU AI Act Art. 27 — high-risk system with deployer obligations"
    elif is_high:
        fria_app = SectionApplicability.RECOMMENDED
        fria_basis = "EU AI Act Art. 27 — high-risk system"
    else:
        fria_app = SectionApplicability.NOT_APPLICABLE
        fria_basis = "EU AI Act Art. 27 — not triggered at this tier"

    has_data_category = False
    has_special_category = False
    if system is not None:
        categories = list(db.scalars(
            select(DataCategory)
            .join(
                SystemDataCategory,
                SystemDataCategory.data_category_id == DataCategory.id,
            )
            .where(SystemDataCategory.system_id == system.id)
        ))
        has_data_category = len(categories) > 0
        has_special_category = any(c.is_special_category for c in categories)

    if is_high and has_special_category:
        dpia_app = SectionApplicability.REQUIRED
        dpia_basis = "GDPR Art. 35 — special-category data + high-risk processing"
    elif has_data_category:
        dpia_app = SectionApplicability.RECOMMENDED
        dpia_basis = "GDPR Art. 35 — personal data present"
    else:
        dpia_app = SectionApplicability.NOT_APPLICABLE
        dpia_basis = "GDPR Art. 35 — no personal data registered"

    return [
        FeederRecommendationRead(
            type=AssessmentType.FRIA, applicability=fria_app, basis=fria_basis,
            exists=AssessmentType.FRIA in existing_types,
        ),
        FeederRecommendationRead(
            type=AssessmentType.DPIA, applicability=dpia_app, basis=dpia_basis,
            exists=AssessmentType.DPIA in existing_types,
        ),
        FeederRecommendationRead(
            type=AssessmentType.MODEL_RISK,
            applicability=SectionApplicability.RECOMMENDED,
            basis="NIST AI RMF / ISO 42001 — applies to any deployed model",
            exists=AssessmentType.MODEL_RISK in existing_types,
        ),
    ]


# ---------------------------------------------------------------------------
# Sections
# ---------------------------------------------------------------------------

def list_sections(
    assessment_id: uuid.UUID, ctx: TenantContext, db: Session,
) -> list[dict]:
    assessment = load_assessment(assessment_id, ctx, db)
    template_rows = list(db.scalars(
        select(AssessmentSectionTemplate).where(
            AssessmentSectionTemplate.type == assessment.type,
            AssessmentSectionTemplate.tier == assessment.tier_snapshot,
        ).order_by(AssessmentSectionTemplate.sort_order)
    ))
    existing_items = list(db.scalars(
        select(AssessmentItem).where(AssessmentItem.assessment_id == assessment.id)
    ))
    first_item_by_section: dict[str, uuid.UUID] = {}
    for item in existing_items:
        if item.section_key and item.section_key not in first_item_by_section:
            first_item_by_section[item.section_key] = item.id

    return [
        {
            "section_key": tmpl.section_key,
            "title": tmpl.title,
            "applicability": tmpl.applicability,
            "prompt": tmpl.prompt,
            "iso_42005_clause": tmpl.iso_42005_clause,
            "instantiated": tmpl.section_key in first_item_by_section,
            "item_id": first_item_by_section.get(tmpl.section_key),
        }
        for tmpl in template_rows
    ]


def create_item_from_section(
    assessment_id: uuid.UUID, section_key: str, response: str | None,
    ctx: TenantContext, db: Session,
) -> AssessmentItem:
    assessment = load_assessment(assessment_id, ctx, db)
    tmpl = db.scalar(
        select(AssessmentSectionTemplate).where(
            AssessmentSectionTemplate.type == assessment.type,
            AssessmentSectionTemplate.tier == assessment.tier_snapshot,
            AssessmentSectionTemplate.section_key == section_key,
        )
    )
    if tmpl is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unknown section_key {section_key!r} for this assessment's tier",
        )

    item = AssessmentItem(
        id=uuid.uuid4(), tenant_id=ctx.tenant_id, assessment_id=assessment.id,
        section_key=section_key, prompt=tmpl.prompt, response=response,
        provenance=(
            ProvenanceConfidence.USER_PROVIDED if response is not None
            else ProvenanceConfidence.CATALOGUE_CURATED
        ),
        created_by=ctx.user_id,
    )
    db.add(item)
    _stage_audit(
        db, tenant_id=ctx.tenant_id, actor_user_id=ctx.user_id,
        action="assessment_item.created", entity_type="assessment_item",
        entity_id=item.id, detail={"section_key": section_key},
    )
    db.flush()
    return item


# ---------------------------------------------------------------------------
# Item mutation: amend, confirm, delete
# ---------------------------------------------------------------------------

def amend_item(
    item_id: uuid.UUID, patch: AssessmentItemAmend, expected_lock_version: int,
    ctx: TenantContext, db: Session,
) -> AssessmentItem:
    item = _load_item(item_id, ctx, db)

    changes: dict[str, tuple[object, object]] = {}
    for field in _AUTHORING_FIELDS:
        new_value = getattr(patch, field)
        if new_value is None:
            continue
        old_value = getattr(item, field)
        if new_value != old_value:
            changes[field] = (old_value, new_value)

    if not changes:
        return item  # content-less PATCH: no-op, no event, no provenance change

    if item.provenance == ProvenanceConfidence.AI_SUGGESTED:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="Confirm or amend the proposed risk before authoring this item",
        )

    new_provenance = (
        ProvenanceConfidence.USER_PROVIDED
        if item.provenance == ProvenanceConfidence.CATALOGUE_CURATED
        else item.provenance
    )

    values = {field: new for field, (_old, new) in changes.items()}
    values["provenance"] = new_provenance
    values["lock_version"] = AssessmentItem.lock_version + 1

    result = db.execute(
        update(AssessmentItem)
        .where(
            AssessmentItem.id == item_id,
            AssessmentItem.tenant_id == ctx.tenant_id,
            AssessmentItem.lock_version == expected_lock_version,
        )
        .values(**values)
    )
    if result.rowcount == 0:
        raise HTTPException(
            status.HTTP_412_PRECONDITION_FAILED,
            detail="Stale If-Match: item was modified by another request",
        )

    field_detail = {
        field: {"before": old, "after": new}
        for field, (old, new) in changes.items()
    }
    field_detail["provenance"] = {
        "before": item.provenance.value, "after": new_provenance.value,
    }
    _stage_audit(
        db, tenant_id=ctx.tenant_id, actor_user_id=ctx.user_id,
        action="assessment_item.amended", entity_type="assessment_item",
        entity_id=item_id, detail=field_detail,
    )
    db.flush()
    db.refresh(item)
    return item


def confirm_item(
    item_id: uuid.UUID, expected_lock_version: int, ctx: TenantContext, db: Session,
) -> AssessmentItem:
    item = _load_item(item_id, ctx, db)

    result = db.execute(
        update(AssessmentItem)
        .where(
            AssessmentItem.id == item_id,
            AssessmentItem.tenant_id == ctx.tenant_id,
            AssessmentItem.provenance == ProvenanceConfidence.AI_SUGGESTED,
            AssessmentItem.lock_version == expected_lock_version,
        )
        .values(
            provenance=ProvenanceConfidence.USER_CONFIRMED,
            lock_version=AssessmentItem.lock_version + 1,
        )
    )
    if result.rowcount == 0:
        # Loser of a confirm/amend race, or a non-AI_SUGGESTED item: 409
        # either way (design doc: "Concurrent confirm/amend race -> 409").
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="Item is not confirmable, or was modified concurrently",
        )

    _stage_audit(
        db, tenant_id=ctx.tenant_id, actor_user_id=ctx.user_id,
        action="assessment_item.confirmed", entity_type="assessment_item",
        entity_id=item_id,
        detail={"risk_id": str(item.risk_id) if item.risk_id else None},
    )
    db.flush()
    db.refresh(item)
    return item


def delete_item(item_id: uuid.UUID, ctx: TenantContext, db: Session) -> None:
    item = _load_item(item_id, ctx, db)
    control_link_ids = [
        str(link_id) for link_id in db.scalars(
            select(AssessmentItemControl.id)
            .where(AssessmentItemControl.item_id == item.id)
        )
    ]
    db.delete(item)
    _stage_audit(
        db, tenant_id=ctx.tenant_id, actor_user_id=ctx.user_id,
        action="assessment_item.deleted", entity_type="assessment_item",
        entity_id=item_id, detail={"cascaded_control_link_ids": control_link_ids},
    )
    db.flush()


# ---------------------------------------------------------------------------
# Assessment delete (pristine only)
# ---------------------------------------------------------------------------

def _is_pristine(assessment: Assessment, db: Session) -> bool:
    # "Worked" = a human acted on the item: confirmed/amended a proposed
    # risk, or answered a curated section prompt. System-snapshotted
    # register facts are also USER_PROVIDED but carry a source_ref and are
    # present from the moment of creation — they must not block the
    # create/delete/re-create path, so they're excluded here.
    worked_item = db.scalar(
        select(AssessmentItem.id).where(
            AssessmentItem.assessment_id == assessment.id,
            or_(
                AssessmentItem.provenance.in_([
                    ProvenanceConfidence.USER_CONFIRMED,
                    ProvenanceConfidence.USER_AMENDED,
                ]),
                and_(
                    AssessmentItem.provenance == ProvenanceConfidence.USER_PROVIDED,
                    AssessmentItem.source_ref.is_(None),
                ),
            ),
        ).limit(1)
    )
    if worked_item is not None:
        return False
    link = db.scalar(
        select(AssessmentItemControl.id)
        .join(AssessmentItem, AssessmentItem.id == AssessmentItemControl.item_id)
        .where(AssessmentItem.assessment_id == assessment.id)
        .limit(1)
    )
    if link is not None:
        return False
    feeder = db.scalar(
        select(Assessment.id).where(Assessment.parent_aiia_id == assessment.id).limit(1)
    )
    return feeder is None


def delete_assessment(
    assessment_id: uuid.UUID, ctx: TenantContext, db: Session,
) -> None:
    assessment = load_assessment(assessment_id, ctx, db)
    if not _is_pristine(assessment, db):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="Assessment has worked content; use void (deferred), not delete",
        )
    db.delete(assessment)
    _stage_audit(
        db, tenant_id=ctx.tenant_id, actor_user_id=ctx.user_id,
        action="assessment.deleted", entity_type="assessment", entity_id=assessment_id,
        detail={},
    )
    db.flush()


# ---------------------------------------------------------------------------
# Control links
# ---------------------------------------------------------------------------

def create_control_link(
    item_id: uuid.UUID, control_id: uuid.UUID, coverage: CoverageStatus,
    ctx: TenantContext, db: Session,
) -> AssessmentItemControl:
    item = _load_item(item_id, ctx, db)
    control = db.get(Control, control_id)
    if control is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"control_id {control_id} not found",
        )

    link = AssessmentItemControl(
        id=uuid.uuid4(), tenant_id=ctx.tenant_id, item_id=item.id,
        control_id=control_id, coverage=coverage,
    )
    db.add(link)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="This control is already linked to this item",
        ) from exc

    _stage_audit(
        db, tenant_id=ctx.tenant_id, actor_user_id=ctx.user_id,
        action="control_link.created", entity_type="assessment_item_control",
        entity_id=link.id,
        detail={
            "item_id": str(item_id), "control_id": str(control_id),
            "coverage": coverage.value,
        },
    )
    db.flush()
    return link


def delete_control_link(link_id: uuid.UUID, ctx: TenantContext, db: Session) -> None:
    link = db.scalar(
        select(AssessmentItemControl).where(
            AssessmentItemControl.id == link_id,
            AssessmentItemControl.tenant_id == ctx.tenant_id,
        )
    )
    if link is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Control link not found")

    db.delete(link)
    _stage_audit(
        db, tenant_id=ctx.tenant_id, actor_user_id=ctx.user_id,
        action="control_link.deleted", entity_type="assessment_item_control",
        entity_id=link_id,
        detail={"item_id": str(link.item_id), "control_id": str(link.control_id)},
    )
    db.flush()
