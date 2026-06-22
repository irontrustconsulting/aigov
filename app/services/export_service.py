"""Export / audit pack (sprints/SPRINT_AUDIT_PACK.md, Sprint 7b;
docs/AUDIT_PACK_DESIGN.md). Read-assembled over already-largely-immutable
data, plus one disclosure write (`export.generated`).

Session shape (D7 — the evidence_service precedent, STATE §4 third shape):
routes depend only on `get_tenant_context` (no `get_tenant_db`); the service
opens its own session, sets `REPEATABLE READ` via `execution_options` before
the first statement, then `SET LOCAL app.current_tenant`, runs the
governance-role gate as a plain call (not `Depends`, which would otherwise
pull in a request-scoped `get_tenant_db` session), assembles, computes a
canonical `content_hash`, stages `export.generated`, and owns the commit.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import and_, or_, select, text
from sqlalchemy.orm import Session

from app.auth.context import TenantContext, require_governance_role
from app.db.session import SessionLocal
from app.models.assessment import (
    Assessment,
    AssessmentItem,
    AssessmentItemControl,
    AssessmentItemEvidence,
    AssessmentSectionTemplate,
    Classification,
)
from app.models.base import AssessmentType, Framework
from app.models.domain import ProductApproval, System, UseCase, VendorApproval
from app.models.identity import Membership, User
from app.models.lifecycle import (
    AuditEvent,
    DeploymentAuthorisation,
    Evidence,
    LifecycleTransition,
)
from app.schemas.assessment import (
    AssessmentItemRead,
    AssessmentRead,
    ControlLinkRead,
    EvidenceLinkRead,
)
from app.schemas.coverage import CoverageMatrixRead
from app.schemas.export import (
    ActorRef,
    AssessmentExportRead,
    AtoDocumentRead,
    AuditTrailEntryRead,
    ClassificationHistoryEntryRead,
    EvidenceManifestEntryRead,
    ExportAssessmentItemRead,
    FeederExportRead,
    FrameworkExportRead,
    LifecycleTrailEntryRead,
    SystemExportRead,
    UseCaseExportRead,
    UseCaseExportSectionsRead,
)
from app.schemas.lifecycle import DeploymentAuthorisationRead
from app.schemas.system import SystemDetail
from app.services.coverage_service import compute_coverage
from app.services.system_service import get_system_detail

_ALL_GOVERNANCE_ROLES = (
    "system_owner",
    "contributor",
    "reviewer",
    "authoriser",
    "auditor",
)


@contextmanager
def _export_session(ctx: TenantContext) -> Generator[Session, None, None]:
    """A short, self-owned REPEATABLE READ transaction (D7) — deliberately
    not a FastAPI Depends(get_tenant_db), which runs READ COMMITTED and
    would hold a request-scoped session open for the whole request. The
    isolation level must be set before the first statement on the
    connection; `SET LOCAL app.current_tenant` is itself a statement, so
    execution_options runs first."""
    db = SessionLocal()
    try:
        db.begin()
        db.connection(execution_options={"isolation_level": "REPEATABLE READ"})
        db.execute(
            text("SELECT set_config('app.current_tenant', :tid, true)"),
            {"tid": str(ctx.tenant_id)},
        )
        require_governance_role(*_ALL_GOVERNANCE_ROLES)(ctx=ctx, db=db)
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Actor resolution — actor_user_id is nullable on both LifecycleTransition
# and AuditEvent, so this is a LEFT join (never drops the row), unlike the
# review-queue's inner-join precedent which relies on the column being
# always-populated under its query's precondition.
# ---------------------------------------------------------------------------


def _resolve_actors(
    db: Session, tenant_id: uuid.UUID, user_ids: set[uuid.UUID | None]
) -> dict[uuid.UUID, ActorRef]:
    ids = {uid for uid in user_ids if uid is not None}
    if not ids:
        return {}
    rows = db.execute(
        select(User.id, User.display_name, User.email)
        .join(Membership, Membership.user_id == User.id)
        .where(Membership.tenant_id == tenant_id, User.id.in_(ids))
    ).all()
    found = {
        row.id: ActorRef(user_id=row.id, name=row.display_name, email=row.email)
        for row in rows
    }
    # Anonymised/revoked actor: show the user-id, not nothing (§9 edge case).
    for uid in ids:
        found.setdefault(uid, ActorRef(user_id=uid, name=None, email=None))
    return found


def _actor_for(
    actors: dict[uuid.UUID, ActorRef], user_id: uuid.UUID | None
) -> ActorRef | None:
    return actors.get(user_id) if user_id is not None else None


def _resolve_signed_off_actors(
    db: Session, tenant_id: uuid.UUID, classification_ids: set[uuid.UUID]
) -> dict[uuid.UUID, ActorRef]:
    if not classification_ids:
        return {}
    rows = list(
        db.scalars(
            select(AuditEvent).where(
                AuditEvent.tenant_id == tenant_id,
                AuditEvent.action == "classification.signed_off",
                AuditEvent.entity_id.in_(classification_ids),
            )
        )
    )
    actors = _resolve_actors(db, tenant_id, {r.actor_user_id for r in rows})
    return {
        r.entity_id: _actor_for(actors, r.actor_user_id)
        for r in rows
        if r.entity_id is not None
    }


# ---------------------------------------------------------------------------
# Assessment record — native items only, feeders as complete sub-records
# with surfaces_into (D3). Never calls assemble_aiia_items.
# ---------------------------------------------------------------------------


def _batch_by_item(
    db: Session, model, item_ids: list[uuid.UUID]
) -> dict[uuid.UUID, list]:
    if not item_ids:
        return {}
    out: dict[uuid.UUID, list] = {}
    for row in db.scalars(select(model).where(model.item_id.in_(item_ids))):
        out.setdefault(row.item_id, []).append(row)
    return out


def _assessment_record(
    db: Session, tenant_id: uuid.UUID, aiia: Assessment
) -> tuple[AssessmentExportRead, list[uuid.UUID], list[uuid.UUID]]:
    native_items = list(
        db.scalars(
            select(AssessmentItem)
            .where(AssessmentItem.assessment_id == aiia.id)
            .order_by(AssessmentItem.created_at)
        )
    )
    feeders_orm = list(
        db.scalars(select(Assessment).where(Assessment.parent_aiia_id == aiia.id))
    )
    feeder_items_by_feeder: dict[uuid.UUID, list[AssessmentItem]] = {
        feeder.id: list(
            db.scalars(
                select(AssessmentItem)
                .where(AssessmentItem.assessment_id == feeder.id)
                .order_by(AssessmentItem.created_at)
            )
        )
        for feeder in feeders_orm
    }

    all_items = list(native_items)
    for items in feeder_items_by_feeder.values():
        all_items.extend(items)
    all_item_ids = [i.id for i in all_items]

    control_links_by_item = _batch_by_item(db, AssessmentItemControl, all_item_ids)
    evidence_links_by_item = _batch_by_item(db, AssessmentItemEvidence, all_item_ids)

    def _item_read(
        item: AssessmentItem, surfaces_into: str | None
    ) -> ExportAssessmentItemRead:
        # Exclude link fields from base — both are provided explicitly below.
        base = AssessmentItemRead.model_validate(item).model_dump(
            exclude={"control_links", "evidence_links"}
        )
        return ExportAssessmentItemRead(
            **base,
            surfaces_into=surfaces_into,
            control_links=[
                ControlLinkRead.model_validate(c)
                for c in control_links_by_item.get(item.id, [])
            ],
            evidence_links=[
                EvidenceLinkRead.model_validate(e)
                for e in evidence_links_by_item.get(item.id, [])
            ],
        )

    native_reads = [_item_read(i, None) for i in native_items]

    feeder_reads: list[FeederExportRead] = []
    all_assessment_ids = [aiia.id]
    for feeder in feeders_orm:
        all_assessment_ids.append(feeder.id)
        target_by_section_key = dict(
            db.execute(
                select(
                    AssessmentSectionTemplate.section_key,
                    AssessmentSectionTemplate.aiia_target_section_key,
                ).where(
                    AssessmentSectionTemplate.type == feeder.type,
                    AssessmentSectionTemplate.tier == feeder.tier_snapshot,
                )
            ).all()
        )
        feeder_reads.append(
            FeederExportRead(
                assessment_id=feeder.id,
                type=feeder.type,
                status=feeder.status,
                items=[
                    _item_read(item, target_by_section_key.get(item.section_key))
                    for item in feeder_items_by_feeder[feeder.id]
                ],
            )
        )

    record = AssessmentExportRead(
        aiia_id=aiia.id,
        status=aiia.status,
        native_items=native_reads,
        feeders=feeder_reads,
    )
    return record, all_item_ids, all_assessment_ids


# ---------------------------------------------------------------------------
# Evidence manifest (D2) — by reference only, deduped
# ---------------------------------------------------------------------------


def _evidence_manifest(
    db: Session, tenant_id: uuid.UUID, item_ids: list[uuid.UUID]
) -> tuple[list[EvidenceManifestEntryRead], list[uuid.UUID]]:
    if not item_ids:
        return [], []
    rows = db.execute(
        select(AssessmentItemEvidence.item_id, Evidence)
        .join(Evidence, Evidence.id == AssessmentItemEvidence.evidence_id)
        .where(
            AssessmentItemEvidence.item_id.in_(item_ids),
            AssessmentItemEvidence.tenant_id == tenant_id,
        )
    ).all()
    by_evidence: dict[uuid.UUID, dict] = {}
    for item_id, evidence in rows:
        entry = by_evidence.setdefault(
            evidence.id, {"evidence": evidence, "back_refs": []}
        )
        entry["back_refs"].append(item_id)
    entries = [
        EvidenceManifestEntryRead(
            id=e["evidence"].id,
            sha256=e["evidence"].sha256,
            title=e["evidence"].title,
            content_type=e["evidence"].content_type,
            size_bytes=e["evidence"].size_bytes,
            back_refs=e["back_refs"],
        )
        for e in by_evidence.values()
    ]
    return entries, list(by_evidence.keys())


# ---------------------------------------------------------------------------
# Lifecycle trail + ATO section
# ---------------------------------------------------------------------------


def _lifecycle_trail(
    db: Session, tenant_id: uuid.UUID, use_case_id: uuid.UUID
) -> list[LifecycleTrailEntryRead]:
    rows = list(
        db.scalars(
            select(LifecycleTransition)
            .where(
                LifecycleTransition.tenant_id == tenant_id,
                LifecycleTransition.use_case_id == use_case_id,
            )
            .order_by(LifecycleTransition.occurred_at)
        )
    )
    actors = _resolve_actors(db, tenant_id, {r.actor_user_id for r in rows})
    return [
        LifecycleTrailEntryRead(
            from_state=r.from_state,
            to_state=r.to_state,
            occurred_at=r.occurred_at,
            actor=_actor_for(actors, r.actor_user_id),
            reason=r.reason,
            triggered_by=r.triggered_by,
        )
        for r in rows
    ]


def _ato_section(
    db: Session, tenant_id: uuid.UUID, use_case: UseCase
) -> tuple[list[DeploymentAuthorisationRead], list[uuid.UUID]]:
    rows = list(
        db.scalars(
            select(DeploymentAuthorisation)
            .where(
                DeploymentAuthorisation.tenant_id == tenant_id,
                DeploymentAuthorisation.use_case_id == use_case.id,
            )
            .order_by(DeploymentAuthorisation.authorised_at)
        )
    )
    reads = [
        DeploymentAuthorisationRead(
            id=a.id,
            use_case_id=a.use_case_id,
            assessment_id=a.assessment_id,
            submission_round=a.submission_round,
            tier=a.tier,
            assessment_version=a.assessment_version,
            authorised_by_name=a.authorised_by_name,
            authorised_by_email=a.authorised_by_email,
            authorised_at=a.authorised_at,
            residual_risk_statement=a.residual_risk_statement,
            live_state=use_case.state.value,
        )
        for a in rows
    ]
    return reads, [a.id for a in rows]


# ---------------------------------------------------------------------------
# Audit-trail closure (D4, D11, D12, D14)
# ---------------------------------------------------------------------------


def _resolve_approval_ids(
    db: Session,
    tenant_id: uuid.UUID,
    *,
    vendor_id: uuid.UUID | None,
    product_id: uuid.UUID | None,
) -> list[uuid.UUID]:
    """Vendor/product clearance events key to the approval-row id, not the
    vendor/product id (D11) — scoped to the use case's system here, taking
    the ids straight off the already-assembled SystemDetail rather than a
    redundant System row lookup."""
    ids: list[uuid.UUID] = []
    if vendor_id is not None:
        ids.extend(
            db.scalars(
                select(VendorApproval.id).where(
                    VendorApproval.tenant_id == tenant_id,
                    VendorApproval.catalogue_vendor_id == vendor_id,
                )
            )
        )
    if product_id is not None:
        ids.extend(
            db.scalars(
                select(ProductApproval.id).where(
                    ProductApproval.tenant_id == tenant_id,
                    ProductApproval.catalogue_product_id == product_id,
                )
            )
        )
    return ids


def _audit_closure(
    db: Session,
    tenant_id: uuid.UUID,
    *,
    entity_ids: set[uuid.UUID],
    item_ids: set[uuid.UUID],
) -> list[AuditTrailEntryRead]:
    conditions = []
    if entity_ids:
        conditions.append(AuditEvent.entity_id.in_(entity_ids))
    if item_ids:
        conditions.append(
            and_(
                AuditEvent.entity_type.in_(
                    ("assessment_item_control", "assessment_item_evidence")
                ),
                AuditEvent.detail["item_id"]
                .as_string()
                .in_([str(i) for i in item_ids]),
            )
        )
    if not conditions:
        return []

    rows = list(
        db.scalars(
            select(AuditEvent)
            .where(AuditEvent.tenant_id == tenant_id, or_(*conditions))
            .order_by(AuditEvent.occurred_at)
        )
    )
    actors = _resolve_actors(db, tenant_id, {r.actor_user_id for r in rows})
    return [
        AuditTrailEntryRead(
            action=r.action,
            occurred_at=r.occurred_at,
            actor=_actor_for(actors, r.actor_user_id),
            entity_type=r.entity_type,
            entity_id=r.entity_id,
            detail=r.detail,
            # source_ip deliberately excluded (D12)
        )
        for r in rows
    ]


# ---------------------------------------------------------------------------
# Use-case record assembly (§4.2 items 1-7 — no audit trail, §4.4 closure
# is computed by the caller so a system export can run ONE combined query)
# ---------------------------------------------------------------------------


def _empty_coverage(
    scope: str, scope_id: uuid.UUID | None, framework: Framework | None
) -> CoverageMatrixRead:
    return CoverageMatrixRead(
        scope=scope,
        scope_id=scope_id,
        framework_filter=framework,
        include_unapproved=False,
        controls=[],
        frameworks=[],
        unaddressed_controls=[],
        not_an_obligation_set=True,
        generated_at=datetime.now(UTC),
    )


def _use_case_record(
    db: Session,
    tenant_id: uuid.UUID,
    use_case: UseCase,
    system_detail: SystemDetail,
    *,
    framework: Framework | None,
) -> tuple[UseCaseExportSectionsRead, set[uuid.UUID], set[uuid.UUID]]:
    """Assembles one use case's record body and returns the (entity_ids,
    item_ids) this record contributes to an audit closure — the caller
    decides whether to close per use case (standalone export) or union
    across many (system export)."""
    aiia = db.scalar(
        select(Assessment).where(
            Assessment.tenant_id == tenant_id,
            Assessment.use_case_id == use_case.id,
            Assessment.type == AssessmentType.AIIA,
        )
    )

    classifications = list(
        db.scalars(
            select(Classification)
            .where(
                Classification.tenant_id == tenant_id,
                Classification.use_case_id == use_case.id,
            )
            .order_by(Classification.version)
        )
    )
    signed_off_actors = _resolve_signed_off_actors(
        db, tenant_id, {c.id for c in classifications}
    )
    classification_history = [
        ClassificationHistoryEntryRead(
            tier=c.tier,
            proposed_tier=c.proposed_tier,
            overridden=c.overridden,
            rationale=c.rationale,
            basis_subcategory_code=c.basis_subcategory_code,
            basis_legal_ref=c.basis_legal_ref,
            status=c.status,
            version=c.version,
            signed_off_by=signed_off_actors.get(c.id),
        )
        for c in classifications
    ]

    if aiia is not None:
        assessment_record, item_ids, assessment_ids = _assessment_record(
            db, tenant_id, aiia
        )
        coverage = compute_coverage(
            db,
            tenant_id=tenant_id,
            scope="assessment",
            scope_id=aiia.id,
            framework=framework,
            require_evidence_for_satisfied=True,
        )
    else:
        assessment_record = AssessmentExportRead(
            aiia_id=None,
            status=None,
            native_items=[],
            feeders=[],
        )
        item_ids, assessment_ids = [], []
        coverage = _empty_coverage("assessment", None, framework)

    evidence_manifest, linked_evidence_ids = _evidence_manifest(db, tenant_id, item_ids)
    lifecycle_trail = _lifecycle_trail(db, tenant_id, use_case.id)
    atos, ato_ids = _ato_section(db, tenant_id, use_case)
    approval_ids = _resolve_approval_ids(
        db,
        tenant_id,
        vendor_id=system_detail.catalogue_vendor.id
        if system_detail.catalogue_vendor
        else None,
        product_id=system_detail.catalogue_product.id
        if system_detail.catalogue_product
        else None,
    )

    entity_ids = {
        use_case.id,
        *assessment_ids,
        *item_ids,
        *ato_ids,
        *linked_evidence_ids,
        *approval_ids,
    }
    entity_ids.update(c.id for c in classifications)

    sections = UseCaseExportSectionsRead(
        use_case_id=use_case.id,
        system=system_detail,
        classification_history=classification_history,
        assessment=assessment_record,
        evidence_manifest=evidence_manifest,
        coverage=coverage,
        lifecycle_trail=lifecycle_trail,
        atos=atos,
    )
    return sections, entity_ids, set(item_ids)


# ---------------------------------------------------------------------------
# content_hash (D1) — canonical JSON over the body sections only
# ---------------------------------------------------------------------------


def _strip_generated_at(value):
    """Nested CoverageMatrixRead sections each carry their own live
    `generated_at` (intentional on that response shape) — strip it
    recursively before hashing so the pack's content_hash reflects state,
    not wall-clock time, at every nesting level, not just the top one."""
    if isinstance(value, dict):
        return {
            k: _strip_generated_at(v) for k, v in value.items() if k != "generated_at"
        }
    if isinstance(value, list):
        return [_strip_generated_at(v) for v in value]
    return value


def _content_hash(body: dict) -> str:
    canonical = json.dumps(
        _strip_generated_at(body), sort_keys=True, separators=(",", ":"), default=str
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def _hashable_audit_trail(audit_trail: list[AuditTrailEntryRead]) -> list[dict]:
    """Excludes this record's own prior export.generated entries from the
    hash input — each export call stages one, which would otherwise show up
    in every subsequent export's closure (entity_id == use_case_id/system_id)
    and make content_hash drift on every view, even with no change to the
    governed record itself. Still included in the returned audit_trail."""
    return [
        e.model_dump(mode="json") for e in audit_trail if e.action != "export.generated"
    ]


def _stage_export_event(
    db: Session,
    ctx: TenantContext,
    *,
    entity_type: str,
    entity_id: uuid.UUID | None,
    scope: str,
    scope_id: uuid.UUID | None,
    framework_filter: Framework | None,
    content_hash: str,
) -> None:
    db.add(
        AuditEvent(
            id=uuid.uuid4(),
            tenant_id=ctx.tenant_id,
            actor_user_id=ctx.user_id,
            action="export.generated",
            entity_type=entity_type,
            entity_id=entity_id,
            detail={
                "scope": scope,
                "scope_id": str(scope_id) if scope_id else None,
                "framework_filter": framework_filter.value
                if framework_filter
                else None,
                "content_hash": content_hash,
            },
        )
    )


# ---------------------------------------------------------------------------
# Public entrypoints
# ---------------------------------------------------------------------------


def build_use_case_export(
    ctx: TenantContext, use_case_id: uuid.UUID, *, framework: Framework | None = None
) -> UseCaseExportRead:
    with _export_session(ctx) as db:
        use_case = db.scalar(
            select(UseCase).where(
                UseCase.id == use_case_id, UseCase.tenant_id == ctx.tenant_id
            )
        )
        if use_case is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Use case not found")

        system_detail = get_system_detail(use_case.system_id, db)
        sections, entity_ids, item_ids = _use_case_record(
            db, ctx.tenant_id, use_case, system_detail, framework=framework
        )
        audit_trail = _audit_closure(
            db, ctx.tenant_id, entity_ids=entity_ids, item_ids=item_ids
        )

        body = sections.model_dump(mode="json") | {
            "audit_trail": _hashable_audit_trail(audit_trail)
        }
        content_hash = _content_hash(body)

        _stage_export_event(
            db,
            ctx,
            entity_type="use_case",
            entity_id=use_case.id,
            scope="use_case",
            scope_id=use_case.id,
            framework_filter=framework,
            content_hash=content_hash,
        )

        return UseCaseExportRead(
            **sections.model_dump(),
            audit_trail=audit_trail,
            generated_at=datetime.now(UTC),
            content_hash=content_hash,
        )


def build_system_export(
    ctx: TenantContext, system_id: uuid.UUID, *, framework: Framework | None = None
) -> SystemExportRead:
    with _export_session(ctx) as db:
        system = db.scalar(
            select(System).where(
                System.id == system_id, System.tenant_id == ctx.tenant_id
            )
        )
        if system is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="System not found")

        system_detail = get_system_detail(system_id, db)
        use_cases = list(
            db.scalars(
                select(UseCase).where(
                    UseCase.system_id == system_id, UseCase.tenant_id == ctx.tenant_id
                )
            )
        )

        all_entity_ids: set[uuid.UUID] = {system.id}
        all_item_ids: set[uuid.UUID] = set()
        use_case_sections: list[UseCaseExportSectionsRead] = []
        for use_case in use_cases:
            sections, entity_ids, item_ids = _use_case_record(
                db, ctx.tenant_id, use_case, system_detail, framework=framework
            )
            use_case_sections.append(sections)
            all_entity_ids |= entity_ids
            all_item_ids |= item_ids

        system_coverage = compute_coverage(
            db,
            tenant_id=ctx.tenant_id,
            scope="system",
            scope_id=system_id,
            framework=framework,
            require_evidence_for_satisfied=True,
        )
        audit_trail = _audit_closure(
            db, ctx.tenant_id, entity_ids=all_entity_ids, item_ids=all_item_ids
        )

        body = {
            "system_id": str(system_id),
            "use_cases": [s.model_dump(mode="json") for s in use_case_sections],
            "system_coverage": system_coverage.model_dump(mode="json"),
            "audit_trail": _hashable_audit_trail(audit_trail),
        }
        content_hash = _content_hash(body)

        _stage_export_event(
            db,
            ctx,
            entity_type="system",
            entity_id=system_id,
            scope="system",
            scope_id=system_id,
            framework_filter=framework,
            content_hash=content_hash,
        )

        return SystemExportRead(
            system_id=system_id,
            system=system_detail,
            use_cases=use_case_sections,
            system_coverage=system_coverage,
            audit_trail=audit_trail,
            generated_at=datetime.now(UTC),
            content_hash=content_hash,
        )


def build_ato_document(
    ctx: TenantContext, use_case_id: uuid.UUID, *, round: int | None = None
) -> AtoDocumentRead:
    with _export_session(ctx) as db:
        use_case = db.scalar(
            select(UseCase).where(
                UseCase.id == use_case_id, UseCase.tenant_id == ctx.tenant_id
            )
        )
        if use_case is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Use case not found")

        query = select(DeploymentAuthorisation).where(
            DeploymentAuthorisation.tenant_id == ctx.tenant_id,
            DeploymentAuthorisation.use_case_id == use_case_id,
        )
        if round is not None:
            query = query.where(DeploymentAuthorisation.submission_round == round)
        # submission_round, not authorised_at, is the authoritative cycle key
        # (model docstring: authorisation_gate matches on it) — also avoids
        # an authorised_at tie when two ATOs are inserted in one transaction
        # (Postgres now() is constant for the transaction's duration).
        ato = db.scalar(
            query.order_by(DeploymentAuthorisation.submission_round.desc()).limit(1)
        )
        if ato is None:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND, detail="Use case has never been authorised"
            )

        ato_read = DeploymentAuthorisationRead(
            id=ato.id,
            use_case_id=ato.use_case_id,
            assessment_id=ato.assessment_id,
            submission_round=ato.submission_round,
            tier=ato.tier,
            assessment_version=ato.assessment_version,
            authorised_by_name=ato.authorised_by_name,
            authorised_by_email=ato.authorised_by_email,
            authorised_at=ato.authorised_at,
            residual_risk_statement=ato.residual_risk_statement,
            live_state=use_case.state.value,
        )

        current_assessment = db.get(Assessment, ato.assessment_id)
        current_assessment_summary = AssessmentRead.model_validate(current_assessment)

        current_classification = db.scalar(
            select(Classification)
            .where(
                Classification.tenant_id == ctx.tenant_id,
                Classification.use_case_id == use_case_id,
            )
            .order_by(Classification.version.desc())
            .limit(1)
        )
        current_classification_summary = None
        if current_classification is not None:
            signed_off = _resolve_signed_off_actors(
                db, ctx.tenant_id, {current_classification.id}
            )
            current_classification_summary = ClassificationHistoryEntryRead(
                tier=current_classification.tier,
                proposed_tier=current_classification.proposed_tier,
                overridden=current_classification.overridden,
                rationale=current_classification.rationale,
                basis_subcategory_code=current_classification.basis_subcategory_code,
                basis_legal_ref=current_classification.basis_legal_ref,
                status=current_classification.status,
                version=current_classification.version,
                signed_off_by=signed_off.get(current_classification.id),
            )

        # ATO document is read-grade, not export-grade (no export.generated
        # disclosure stage) — D6/inv 42 scope export.generated to the four
        # pack-assembly entrypoints; the underlying GET .../authorisation
        # precedent likewise stages nothing.
        return AtoDocumentRead(
            ato=ato_read,
            current_assessment_summary=current_assessment_summary,
            current_classification_summary=current_classification_summary,
        )


def build_framework_export(
    ctx: TenantContext, framework: Framework
) -> FrameworkExportRead:
    with _export_session(ctx) as db:
        coverage = compute_coverage(
            db,
            tenant_id=ctx.tenant_id,
            scope="tenant",
            scope_id=None,
            framework=framework,
            require_evidence_for_satisfied=True,
        )
        item_ids = {
            ref.item_id
            for control in coverage.controls
            for ref in control.breakdown.contributing_refs
        }
        substantiation_manifest, _ = _evidence_manifest(
            db, ctx.tenant_id, list(item_ids)
        )

        body = {
            "framework": framework.value,
            "coverage": coverage.model_dump(mode="json"),
            "substantiation_manifest": [
                e.model_dump(mode="json") for e in substantiation_manifest
            ],
        }
        content_hash = _content_hash(body)

        _stage_export_event(
            db,
            ctx,
            entity_type="framework",
            entity_id=None,
            scope="framework",
            scope_id=None,
            framework_filter=framework,
            content_hash=content_hash,
        )

        return FrameworkExportRead(
            framework=framework,
            coverage=coverage,
            substantiation_manifest=substantiation_manifest,
            generated_at=datetime.now(UTC),
            content_hash=content_hash,
        )
