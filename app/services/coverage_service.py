"""Control coverage view (sprints/SPRINT_APPLICABILITY.md, Sprint 7a;
docs/APPLICABILITY_DESIGN.md). Pure read: recomputed per request off current
`assessment_item_control` links, never persisted (D1) — no flush, no
AuditEvent.

Qualifying-link filter (D3/D4): a link counts iff its item's provenance is
not AI_SUGGESTED, and the item's *governing AIIA* status is in the allowed
set. The governing AIIA is the item's own assessment when that assessment is
itself type=AIIA, else the assessment at `parent_aiia_id` — never a feeder's
own perpetual-DRAFT status (inv 31).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Literal

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, aliased

from app.models.assessment import (
    Assessment,
    AssessmentItem,
    AssessmentItemControl,
    AssessmentItemEvidence,
)
from app.models.base import (
    AssessmentStatus,
    AssessmentType,
    CoverageStatus,
    Framework,
    ProvenanceConfidence,
)
from app.models.domain import System, UseCase
from app.models.knowledge import Control, ControlFrameworkMap
from app.schemas.coverage import (
    ContributingRefRead,
    ControlCoverageRead,
    CoverageBreakdownRead,
    CoverageMatrixRead,
    FrameworkClauseCoverageRead,
    FrameworkMappingRead,
    UnaddressedControlRead,
)

Scope = Literal["tenant", "system", "assessment"]

_DEFAULT_ALLOWED_STATUSES = {AssessmentStatus.APPROVED}
_UNAPPROVED_ALLOWED_STATUSES = {
    AssessmentStatus.APPROVED,
    AssessmentStatus.DRAFT,
    AssessmentStatus.NEEDS_REFRESH,
}


def compute_coverage(
    db: Session,
    *,
    tenant_id: uuid.UUID,
    scope: Scope,
    scope_id: uuid.UUID | None,
    framework: Framework | None = None,
    include_unapproved: bool = False,
    require_evidence_for_satisfied: bool = False,
) -> CoverageMatrixRead:
    scope_clause = _resolve_scope_clause(
        db, tenant_id=tenant_id, scope=scope, scope_id=scope_id
    )

    qualifying = _fetch_qualifying_links(
        db,
        tenant_id=tenant_id,
        scope_clause=scope_clause,
        include_unapproved=include_unapproved,
    )
    _apply_evidence_substantiation(
        db, qualifying, require_evidence_for_satisfied=require_evidence_for_satisfied
    )

    by_control: dict[uuid.UUID, list[dict]] = {}
    for link in qualifying:
        by_control.setdefault(link["control_id"], []).append(link)
    in_play_control_ids = set(by_control)

    controls_by_id = _load_controls(db, in_play_control_ids)
    fw_maps_by_control = _load_framework_maps(db, in_play_control_ids)

    control_reads: list[ControlCoverageRead] = []
    for control_id, links in by_control.items():
        control = controls_by_id.get(control_id)
        if control is None:
            continue
        mappings = fw_maps_by_control.get(control_id, [])
        if framework is not None:
            mappings = [m for m in mappings if m.framework == framework]
            if not mappings:
                continue
        control_reads.append(
            ControlCoverageRead(
                control_id=control.id,
                code=control.code,
                title=control.title,
                verdict=_rollup_verdict(link["effective_coverage"] for link in links),
                breakdown=_build_breakdown(links),
                framework_mappings=[
                    FrameworkMappingRead(framework=m.framework, clause_ref=m.clause_ref)
                    for m in mappings
                ],
            )
        )

    return CoverageMatrixRead(
        scope=scope,
        scope_id=scope_id,
        framework_filter=framework,
        include_unapproved=include_unapproved,
        controls=control_reads,
        frameworks=_build_clause_axis(control_reads),
        unaddressed_controls=_build_unaddressed(
            db, in_play_control_ids=in_play_control_ids, framework=framework
        ),
        not_an_obligation_set=True,
        generated_at=datetime.now(UTC),
    )


# ---------------------------------------------------------------------------
# Scope -> contributing item set (§4.1)
# ---------------------------------------------------------------------------


def _resolve_scope_clause(db: Session, *, tenant_id: uuid.UUID, scope: Scope, scope_id):
    if scope == "tenant":
        return Assessment.tenant_id == tenant_id

    if scope == "system":
        if scope_id is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="scope_id required")
        exists = db.scalar(
            select(System.id).where(
                System.id == scope_id, System.tenant_id == tenant_id
            )
        )
        if exists is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="System not found")
        # AIIAs and feeders alike carry use_case_id directly, so no
        # parent_aiia_id climb is needed to resolve system scope.
        use_case_ids = select(UseCase.id).where(
            UseCase.system_id == scope_id, UseCase.tenant_id == tenant_id
        )
        return Assessment.use_case_id.in_(use_case_ids)

    if scope == "assessment":
        if scope_id is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="scope_id required")
        aiia = db.scalar(
            select(Assessment).where(
                Assessment.id == scope_id, Assessment.tenant_id == tenant_id
            )
        )
        if aiia is None:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND, detail="Assessment not found"
            )
        if aiia.type != AssessmentType.AIIA:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="scope_id must be an AIIA assessment, not a feeder",
            )
        return (Assessment.id == scope_id) | (Assessment.parent_aiia_id == scope_id)

    raise ValueError(f"unknown scope {scope!r}")


# ---------------------------------------------------------------------------
# Qualifying-link filter (§4.2)
# ---------------------------------------------------------------------------


def _fetch_qualifying_links(
    db: Session, *, tenant_id: uuid.UUID, scope_clause, include_unapproved: bool
) -> list[dict]:
    governing = aliased(Assessment)
    query = (
        select(
            AssessmentItemControl.item_id,
            AssessmentItemControl.control_id,
            AssessmentItemControl.coverage,
            Assessment.id.label("assessment_id"),
            Assessment.parent_aiia_id,
            Assessment.status.label("own_status"),
            governing.status.label("parent_status"),
        )
        .join(AssessmentItem, AssessmentItemControl.item_id == AssessmentItem.id)
        .join(Assessment, AssessmentItem.assessment_id == Assessment.id)
        .outerjoin(governing, Assessment.parent_aiia_id == governing.id)
        .where(
            AssessmentItemControl.tenant_id == tenant_id,
            AssessmentItem.provenance != ProvenanceConfidence.AI_SUGGESTED,
            scope_clause,
        )
    )
    allowed = (
        _UNAPPROVED_ALLOWED_STATUSES
        if include_unapproved
        else _DEFAULT_ALLOWED_STATUSES
    )

    qualifying = []
    for row in db.execute(query).all():
        governing_status = (
            row.parent_status if row.parent_aiia_id is not None else row.own_status
        )
        if governing_status not in allowed:
            continue
        qualifying.append(
            {
                "item_id": row.item_id,
                "assessment_id": row.assessment_id,
                "control_id": row.control_id,
                "coverage": row.coverage,
                "governing_status": governing_status,
            }
        )
    return qualifying


# ---------------------------------------------------------------------------
# Evidence-backed substantiation (7b D13) — opt-in, default leaves 7a
# untouched
# ---------------------------------------------------------------------------


def _apply_evidence_substantiation(
    db: Session, qualifying: list[dict], *, require_evidence_for_satisfied: bool
) -> None:
    """Sets `effective_coverage` (drives the ladder/verdict) and `downgraded`
    (drives the breakdown split) on every link in place. A SATISFIED link
    without a linked evidence row downgrades to effective PARTIAL — never
    drops — and is counted separately as `downgraded_unsubstantiated`, not
    folded into `partial` (D13)."""
    if not require_evidence_for_satisfied:
        for link in qualifying:
            link["effective_coverage"] = link["coverage"]
            link["downgraded"] = False
        return

    satisfied_item_ids = {
        link["item_id"]
        for link in qualifying
        if link["coverage"] == CoverageStatus.SATISFIED
    }
    items_with_evidence = (
        set(
            db.scalars(
                select(AssessmentItemEvidence.item_id)
                .where(AssessmentItemEvidence.item_id.in_(satisfied_item_ids))
                .distinct()
            )
        )
        if satisfied_item_ids
        else set()
    )
    for link in qualifying:
        if (
            link["coverage"] == CoverageStatus.SATISFIED
            and link["item_id"] not in items_with_evidence
        ):
            link["effective_coverage"] = CoverageStatus.PARTIAL
            link["downgraded"] = True
        else:
            link["effective_coverage"] = link["coverage"]
            link["downgraded"] = False


# ---------------------------------------------------------------------------
# Per-control roll-up (§4.3) + framework projection (§4.4)
# ---------------------------------------------------------------------------


def _rollup_verdict(coverages) -> str:
    coverages = list(coverages)
    if CoverageStatus.SATISFIED in coverages:
        return "SATISFIED"
    if CoverageStatus.PARTIAL in coverages:
        return "PARTIAL"
    return "OPEN"


def _build_breakdown(links: list[dict]) -> CoverageBreakdownRead:
    return CoverageBreakdownRead(
        satisfied=sum(
            1
            for link in links
            if link["coverage"] == CoverageStatus.SATISFIED and not link["downgraded"]
        ),
        partial=sum(1 for link in links if link["coverage"] == CoverageStatus.PARTIAL),
        open=sum(1 for link in links if link["coverage"] == CoverageStatus.OPEN),
        downgraded_unsubstantiated=sum(1 for link in links if link["downgraded"]),
        contributing_refs=[
            ContributingRefRead(
                item_id=link["item_id"],
                assessment_id=link["assessment_id"],
                governing_status=link["governing_status"],
            )
            for link in links
        ],
    )


def _load_controls(
    db: Session, control_ids: set[uuid.UUID]
) -> dict[uuid.UUID, Control]:
    if not control_ids:
        return {}
    controls = db.scalars(select(Control).where(Control.id.in_(control_ids)))
    return {c.id: c for c in controls}


def _load_framework_maps(
    db: Session, control_ids: set[uuid.UUID]
) -> dict[uuid.UUID, list[ControlFrameworkMap]]:
    if not control_ids:
        return {}
    by_control: dict[uuid.UUID, list[ControlFrameworkMap]] = {}
    for m in db.scalars(
        select(ControlFrameworkMap).where(
            ControlFrameworkMap.control_id.in_(control_ids)
        )
    ):
        by_control.setdefault(m.control_id, []).append(m)
    return by_control


def _build_clause_axis(
    control_reads: list[ControlCoverageRead],
) -> list[FrameworkClauseCoverageRead]:
    by_clause: dict[tuple[Framework, str], dict] = {}
    for cr in control_reads:
        for m in cr.framework_mappings:
            entry = by_clause.setdefault(
                (m.framework, m.clause_ref),
                {
                    "control_ids": [],
                    "verdicts": [],
                },
            )
            entry["control_ids"].append(cr.control_id)
            entry["verdicts"].append(cr.verdict)

    results = []
    for (fw, clause_ref), entry in by_clause.items():
        verdicts = entry["verdicts"]
        if "SATISFIED" in verdicts:
            verdict = "SATISFIED"
        elif "PARTIAL" in verdicts:
            verdict = "PARTIAL"
        else:
            verdict = "OPEN"
        results.append(
            FrameworkClauseCoverageRead(
                framework=fw,
                clause_ref=clause_ref,
                verdict=verdict,
                control_ids=entry["control_ids"],
            )
        )
    return results


# ---------------------------------------------------------------------------
# Interim denominator (§4.5/D8)
# ---------------------------------------------------------------------------


def _build_unaddressed(
    db: Session, *, in_play_control_ids: set[uuid.UUID], framework: Framework | None
) -> list[UnaddressedControlRead]:
    query = select(Control)
    if in_play_control_ids:
        query = query.where(Control.id.notin_(in_play_control_ids))
    if framework is not None:
        query = (
            query.join(
                ControlFrameworkMap, ControlFrameworkMap.control_id == Control.id
            )
            .where(ControlFrameworkMap.framework == framework)
            .distinct()
        )

    controls = list(db.scalars(query))
    if not controls:
        return []
    fw_maps_by_control = _load_framework_maps(db, {c.id for c in controls})
    return [
        UnaddressedControlRead(
            control_id=c.id,
            code=c.code,
            title=c.title,
            framework_mappings=[
                FrameworkMappingRead(framework=m.framework, clause_ref=m.clause_ref)
                for m in fw_maps_by_control.get(c.id, [])
            ],
        )
        for c in controls
    ]
