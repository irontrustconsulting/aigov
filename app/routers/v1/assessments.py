"""
AIIA core endpoints (v1, tenant plane) — sprints/SPRINT_AIIA.md, Phase A.

Mixed path roots (/use-cases/... and /assessments/...), so this router
carries no shared prefix; each route declares its full path and the whole
router is registered under /v1 in app.main.

Gating (design doc §6): assessment reads -> any of the five governance
roles; assessment/item writes -> {system_owner, contributor}; AIIA
create/delete -> system_owner only. Admin (administrative axis) is never a
governance role and gets 403 on every route here, reads included.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.context import TenantContext, get_tenant_db, require_governance_role
from app.models.assessment import Assessment, AssessmentItem, AssessmentReview
from app.models.identity import User
from app.schemas.assessment import (
    AssessmentDetail,
    AssessmentItemAmend,
    AssessmentItemCreate,
    AssessmentItemRead,
    AssessmentRead,
    AssessmentReviewCreate,
    AssessmentReviewRead,
    ControlLinkCreate,
    ControlLinkRead,
    EvidenceLinkCreate,
    EvidenceLinkRead,
    FeederCreate,
    FeederRecommendationRead,
    ReviewQueueEntryRead,
    SectionRead,
)
from app.services import assessment_review_service as review_svc
from app.services import assessment_service as svc

router = APIRouter(tags=["assessments"])

_ALL_GOVERNANCE_ROLES = (
    "system_owner", "contributor", "reviewer", "authoriser", "auditor",
)
_WRITE_ROLES = ("system_owner", "contributor")


def _parse_if_match(if_match: str) -> int:
    try:
        return int(if_match)
    except ValueError as exc:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="If-Match must be an integer lock_version",
        ) from exc


# ---------------------------------------------------------------------------
# AIIA create / list / detail / delete
# ---------------------------------------------------------------------------

@router.post(
    "/use-cases/{use_case_id}/assessments",
    response_model=AssessmentRead,
    status_code=status.HTTP_201_CREATED,
)
def create_aiia(
    use_case_id: uuid.UUID,
    ctx: TenantContext = Depends(require_governance_role("system_owner")),
    db: Session = Depends(get_tenant_db),
) -> Assessment:
    return svc.create_aiia(use_case_id, ctx, db)


@router.get(
    "/use-cases/{use_case_id}/assessments",
    response_model=list[AssessmentRead],
)
def list_use_case_assessments(
    use_case_id: uuid.UUID,
    ctx: TenantContext = Depends(require_governance_role(*_ALL_GOVERNANCE_ROLES)),
    db: Session = Depends(get_tenant_db),
) -> list[Assessment]:
    return list(
        db.scalars(
            select(Assessment).where(
                Assessment.use_case_id == use_case_id,
                Assessment.tenant_id == ctx.tenant_id,
            ).order_by(Assessment.created_at)
        )
    )


@router.get("/assessments/{assessment_id}", response_model=AssessmentDetail)
def get_assessment(
    assessment_id: uuid.UUID,
    ctx: TenantContext = Depends(require_governance_role(*_ALL_GOVERNANCE_ROLES)),
    db: Session = Depends(get_tenant_db),
) -> AssessmentDetail:
    assessment = svc.load_assessment(assessment_id, ctx, db)
    reviews = _load_reviews(assessment_id, db)
    return AssessmentDetail(
        **AssessmentRead.model_validate(assessment).model_dump(),
        items=svc.assemble_aiia_items(assessment, db),
        reviews=reviews,
    )


def _load_reviews(
    assessment_id: uuid.UUID, db: Session
) -> list[AssessmentReviewRead]:
    """Load AssessmentReview rows for the review-history display (WI-9b).
    reviewer_display_name resolved via User join (INV-34); rows are ordered
    chronologically so the latest request-changes comment is at the end."""
    rows = db.execute(
        select(
            AssessmentReview.id,
            AssessmentReview.assessment_id,
            AssessmentReview.decision,
            AssessmentReview.note,
            AssessmentReview.submission_round,
            AssessmentReview.created_at,
            User.display_name,
        )
        .join(User, User.id == AssessmentReview.reviewer_user_id)
        .where(AssessmentReview.assessment_id == assessment_id)
        .order_by(AssessmentReview.created_at)
    ).all()
    return [
        AssessmentReviewRead(
            id=row.id,
            assessment_id=row.assessment_id,
            reviewer_display_name=row.display_name,
            decision=row.decision,
            note=row.note,
            submission_round=row.submission_round,
            created_at=row.created_at,
        )
        for row in rows
    ]


@router.delete("/assessments/{assessment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_assessment(
    assessment_id: uuid.UUID,
    ctx: TenantContext = Depends(require_governance_role("system_owner")),
    db: Session = Depends(get_tenant_db),
) -> None:
    # Reused as-is for feeders too (sprints/SPRINT_AIIA_FEEDERS.md §3) — kept
    # at the stricter Phase-A AIIA-delete gate (system_owner only) rather
    # than widening to {system_owner, contributor} for feeders specifically,
    # since this single route can't distinguish AIIA-vs-feeder before
    # loading the row, and a role dependency is the wrong layer to special-
    # case that (CLAUDE.md: role checks are dependencies, not inlined).
    svc.delete_assessment(assessment_id, ctx, db)


# ---------------------------------------------------------------------------
# Review & sign-off (Sprint 6a — sprints/SPRINT_AUTHORIZATION_6A.md)
# ---------------------------------------------------------------------------

@router.post("/assessments/{assessment_id}/submit", response_model=AssessmentRead)
def submit_for_review(
    assessment_id: uuid.UUID,
    if_match: str = Header(..., alias="If-Match"),
    ctx: TenantContext = Depends(require_governance_role("system_owner")),
    db: Session = Depends(get_tenant_db),
) -> Assessment:
    return review_svc.submit_for_review(
        assessment_id, _parse_if_match(if_match), ctx, db,
    )


@router.post("/assessments/{assessment_id}/review", response_model=AssessmentRead)
def record_review(
    assessment_id: uuid.UUID,
    payload: AssessmentReviewCreate,
    if_match: str = Header(..., alias="If-Match"),
    ctx: TenantContext = Depends(require_governance_role("reviewer")),
    db: Session = Depends(get_tenant_db),
) -> Assessment:
    return review_svc.record_review(
        assessment_id,
        payload.decision,
        payload.note,
        _parse_if_match(if_match),
        ctx,
        db,
    )


@router.post("/assessments/{assessment_id}/reopen", response_model=AssessmentRead)
def reopen_assessment(
    assessment_id: uuid.UUID,
    if_match: str = Header(..., alias="If-Match"),
    ctx: TenantContext = Depends(require_governance_role("system_owner")),
    db: Session = Depends(get_tenant_db),
) -> Assessment:
    return review_svc.reopen(assessment_id, _parse_if_match(if_match), ctx, db)


@router.get("/assessments/review-queue", response_model=list[ReviewQueueEntryRead])
def get_review_queue(
    ctx: TenantContext = Depends(require_governance_role("reviewer")),
    db: Session = Depends(get_tenant_db),
) -> list[ReviewQueueEntryRead]:
    return review_svc.list_review_queue(ctx, db)


# ---------------------------------------------------------------------------
# Feeders (Phase B — sprints/SPRINT_AIIA_FEEDERS.md)
# ---------------------------------------------------------------------------

@router.post(
    "/assessments/{aiia_id}/feeders",
    response_model=AssessmentRead,
    status_code=status.HTTP_201_CREATED,
)
def create_feeder(
    aiia_id: uuid.UUID,
    payload: FeederCreate,
    ctx: TenantContext = Depends(require_governance_role(*_WRITE_ROLES)),
    db: Session = Depends(get_tenant_db),
) -> Assessment:
    return svc.create_feeder(aiia_id, payload.type, ctx, db)


@router.get(
    "/assessments/{aiia_id}/feeder-recommendations",
    response_model=list[FeederRecommendationRead],
)
def get_feeder_recommendations(
    aiia_id: uuid.UUID,
    ctx: TenantContext = Depends(require_governance_role(*_ALL_GOVERNANCE_ROLES)),
    db: Session = Depends(get_tenant_db),
) -> list[FeederRecommendationRead]:
    return svc.get_feeder_recommendations(aiia_id, ctx, db)


# ---------------------------------------------------------------------------
# Sections
# ---------------------------------------------------------------------------

@router.get("/assessments/{assessment_id}/sections", response_model=list[SectionRead])
def get_sections(
    assessment_id: uuid.UUID,
    ctx: TenantContext = Depends(require_governance_role(*_ALL_GOVERNANCE_ROLES)),
    db: Session = Depends(get_tenant_db),
) -> list[dict]:
    return svc.list_sections(assessment_id, ctx, db)


# ---------------------------------------------------------------------------
# Items
# ---------------------------------------------------------------------------

@router.post(
    "/assessments/{assessment_id}/items",
    response_model=AssessmentItemRead,
    status_code=status.HTTP_201_CREATED,
)
def create_item(
    assessment_id: uuid.UUID,
    payload: AssessmentItemCreate,
    ctx: TenantContext = Depends(require_governance_role(*_WRITE_ROLES)),
    db: Session = Depends(get_tenant_db),
) -> AssessmentItem:
    return svc.create_item_from_section(
        assessment_id, payload.section_key, payload.response, ctx, db,
    )


@router.patch(
    "/assessments/{assessment_id}/items/{item_id}",
    response_model=AssessmentItemRead,
)
def amend_item(
    assessment_id: uuid.UUID,
    item_id: uuid.UUID,
    payload: AssessmentItemAmend,
    if_match: str = Header(..., alias="If-Match"),
    ctx: TenantContext = Depends(require_governance_role(*_WRITE_ROLES)),
    db: Session = Depends(get_tenant_db),
) -> AssessmentItem:
    del assessment_id  # item_id is globally unique and tenant-scoped; path nesting only
    return svc.amend_item(item_id, payload, _parse_if_match(if_match), ctx, db)


@router.post(
    "/assessments/{assessment_id}/items/{item_id}/confirm",
    response_model=AssessmentItemRead,
)
def confirm_item(
    assessment_id: uuid.UUID,
    item_id: uuid.UUID,
    if_match: str = Header(..., alias="If-Match"),
    ctx: TenantContext = Depends(require_governance_role(*_WRITE_ROLES)),
    db: Session = Depends(get_tenant_db),
) -> AssessmentItem:
    del assessment_id
    return svc.confirm_item(item_id, _parse_if_match(if_match), ctx, db)


@router.delete(
    "/assessments/{assessment_id}/items/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_item(
    assessment_id: uuid.UUID,
    item_id: uuid.UUID,
    ctx: TenantContext = Depends(require_governance_role(*_WRITE_ROLES)),
    db: Session = Depends(get_tenant_db),
) -> None:
    del assessment_id
    svc.delete_item(item_id, ctx, db)


# ---------------------------------------------------------------------------
# Control links
# ---------------------------------------------------------------------------

@router.post(
    "/assessments/{assessment_id}/items/{item_id}/control-links",
    response_model=ControlLinkRead,
    status_code=status.HTTP_201_CREATED,
)
def create_control_link(
    assessment_id: uuid.UUID,
    item_id: uuid.UUID,
    payload: ControlLinkCreate,
    ctx: TenantContext = Depends(require_governance_role(*_WRITE_ROLES)),
    db: Session = Depends(get_tenant_db),
):
    del assessment_id
    return svc.create_control_link(
        item_id, payload.control_id, payload.coverage, ctx, db,
    )


@router.delete(
    "/assessments/{assessment_id}/items/{item_id}/control-links/{link_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_control_link(
    assessment_id: uuid.UUID,
    item_id: uuid.UUID,
    link_id: uuid.UUID,
    ctx: TenantContext = Depends(require_governance_role(*_WRITE_ROLES)),
    db: Session = Depends(get_tenant_db),
) -> None:
    del assessment_id, item_id
    svc.delete_control_link(link_id, ctx, db)


# ---------------------------------------------------------------------------
# Evidence links
# ---------------------------------------------------------------------------

@router.post(
    "/assessments/{assessment_id}/items/{item_id}/evidence-links",
    response_model=EvidenceLinkRead,
    status_code=status.HTTP_201_CREATED,
)
def create_evidence_link(
    assessment_id: uuid.UUID,
    item_id: uuid.UUID,
    payload: EvidenceLinkCreate,
    ctx: TenantContext = Depends(require_governance_role(*_WRITE_ROLES)),
    db: Session = Depends(get_tenant_db),
):
    del assessment_id
    return svc.create_evidence_link(item_id, payload.evidence_id, ctx, db)


@router.delete(
    "/assessments/{assessment_id}/items/{item_id}/evidence-links/{evidence_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_evidence_link(
    assessment_id: uuid.UUID,
    item_id: uuid.UUID,
    evidence_id: uuid.UUID,
    ctx: TenantContext = Depends(require_governance_role(*_WRITE_ROLES)),
    db: Session = Depends(get_tenant_db),
) -> None:
    del assessment_id
    svc.delete_evidence_link(item_id, evidence_id, ctx, db)
