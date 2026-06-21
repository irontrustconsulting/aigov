"""Tests for the control coverage view (sprints/SPRINT_APPLICABILITY.md,
Sprint 7a). Covers the handoff's §10 list 1-8 directly, plus the *intent* of
the "live RLS/enum DB" items 9-14 against the standard no-RLS test harness:
this repo's test DB has no RLS active (tests/conftest.py — create_all, no
migrations), so cross-tenant/governing-status correctness is verified via
coverage_service's own explicit tenant_id filtering, exactly like every
other tenant-scoped service in this suite (see test_lifecycle_rollup.py).
"""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.models.assessment import AssessmentItemEvidence
from app.models.base import (
    AssessmentStatus,
    AssessmentType,
    CoverageStatus,
    EUAIActTier,
    Framework,
)
from app.models.identity import Tenant
from app.models.knowledge import ControlFrameworkMap
from app.models.lifecycle import Evidence
from app.services.coverage_service import compute_coverage
from tests.lifecycle_helpers import (  # noqa: F401
    _ApiCtx,
    _grant,
    _make_aiia,
    _make_control,
    _make_control_link,
    _make_feeder,
    _make_item,
    _make_member,
    _make_system,
    _make_use_case,
    gov_roles,
    member,
    tenant,
)


def _make_fw_map(
    db: Session, control, framework: Framework, clause_ref: str
) -> ControlFrameworkMap:
    m = ControlFrameworkMap(
        id=uuid.uuid4(),
        control_id=control.id,
        framework=framework,
        clause_ref=clause_ref,
    )
    db.add(m)
    db.flush()
    return m


def _approve(db: Session, assessment) -> None:
    assessment.status = AssessmentStatus.APPROVED
    db.flush()


def _make_evidence(db: Session, tenant: Tenant) -> Evidence:
    e = Evidence(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        title="Test evidence",
        s3_bucket="test-bucket",
        s3_key=f"test/{uuid.uuid4()}",
    )
    db.add(e)
    db.flush()
    return e


def _make_evidence_link(
    db: Session, tenant: Tenant, item, evidence
) -> AssessmentItemEvidence:
    link = AssessmentItemEvidence(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        item_id=item.id,
        evidence_id=evidence.id,
    )
    db.add(link)
    db.flush()
    return link


class TestRollupLadder:
    def test_satisfied_wins_over_partial_and_open(
        self, db_session: Session, tenant: Tenant
    ):
        system = _make_system(db_session, tenant)
        use_case = _make_use_case(db_session, tenant, system)
        aiia = _make_aiia(db_session, tenant, use_case, tier_snapshot=EUAIActTier.HIGH)
        _approve(db_session, aiia)
        control = _make_control(db_session)

        for cov in (
            CoverageStatus.OPEN,
            CoverageStatus.PARTIAL,
            CoverageStatus.SATISFIED,
        ):
            item = _make_item(db_session, tenant, aiia)
            _make_control_link(db_session, tenant, item, control, coverage=cov)

        result = compute_coverage(
            db_session,
            tenant_id=tenant.id,
            scope="tenant",
            scope_id=None,
        )
        assert len(result.controls) == 1
        assert result.controls[0].verdict == "SATISFIED"
        assert result.controls[0].breakdown.satisfied == 1
        assert result.controls[0].breakdown.partial == 1
        assert result.controls[0].breakdown.open == 1
        assert len(result.controls[0].breakdown.contributing_refs) == 3


class TestProvenanceFilter:
    def test_ai_suggested_item_excluded(self, db_session: Session, tenant: Tenant):
        from app.models.base import ProvenanceConfidence

        system = _make_system(db_session, tenant)
        use_case = _make_use_case(db_session, tenant, system)
        aiia = _make_aiia(db_session, tenant, use_case, tier_snapshot=EUAIActTier.HIGH)
        _approve(db_session, aiia)
        control = _make_control(db_session)
        item = _make_item(
            db_session, tenant, aiia, provenance=ProvenanceConfidence.AI_SUGGESTED
        )
        _make_control_link(
            db_session, tenant, item, control, coverage=CoverageStatus.SATISFIED
        )

        result = compute_coverage(
            db_session,
            tenant_id=tenant.id,
            scope="tenant",
            scope_id=None,
        )
        assert result.controls == []
        unaddressed_ids = {c.control_id for c in result.unaddressed_controls}
        assert control.id in unaddressed_ids


class TestUnaddressed:
    def test_zero_link_control_is_unaddressed_only(
        self, db_session: Session, tenant: Tenant
    ):
        _make_control(db_session)  # no links at all

        result = compute_coverage(
            db_session,
            tenant_id=tenant.id,
            scope="tenant",
            scope_id=None,
        )
        assert result.controls == []
        assert len(result.unaddressed_controls) == 1
        assert result.not_an_obligation_set is True


class TestFrameworkProjection:
    def test_multi_homed_control_same_verdict_each_framework_and_filter_narrows(
        self, db_session: Session, tenant: Tenant
    ):
        system = _make_system(db_session, tenant)
        use_case = _make_use_case(db_session, tenant, system)
        aiia = _make_aiia(db_session, tenant, use_case, tier_snapshot=EUAIActTier.HIGH)
        _approve(db_session, aiia)
        control = _make_control(db_session)
        _make_fw_map(db_session, control, Framework.ISO_42001, "A.6.2.1")
        _make_fw_map(db_session, control, Framework.EU_AI_ACT, "Art. 9")
        item = _make_item(db_session, tenant, aiia)
        _make_control_link(
            db_session, tenant, item, control, coverage=CoverageStatus.SATISFIED
        )

        full = compute_coverage(
            db_session, tenant_id=tenant.id, scope="tenant", scope_id=None
        )
        assert len(full.controls) == 1
        fws = {m.framework for m in full.controls[0].framework_mappings}
        assert fws == {Framework.ISO_42001, Framework.EU_AI_ACT}
        assert full.controls[0].verdict == "SATISFIED"

        narrowed = compute_coverage(
            db_session,
            tenant_id=tenant.id,
            scope="tenant",
            scope_id=None,
            framework=Framework.ISO_42001,
        )
        assert len(narrowed.controls) == 1
        assert [m.clause_ref for m in narrowed.controls[0].framework_mappings] == [
            "A.6.2.1"
        ]
        assert narrowed.controls[0].verdict == "SATISFIED"

    def test_one_control_multiple_clauses_in_one_framework_all_listed(
        self, db_session: Session, tenant: Tenant
    ):
        system = _make_system(db_session, tenant)
        use_case = _make_use_case(db_session, tenant, system)
        aiia = _make_aiia(db_session, tenant, use_case, tier_snapshot=EUAIActTier.HIGH)
        _approve(db_session, aiia)
        control = _make_control(db_session)
        _make_fw_map(db_session, control, Framework.ISO_42001, "A.6.2.1")
        _make_fw_map(db_session, control, Framework.ISO_42001, "A.6.2.2")
        item = _make_item(db_session, tenant, aiia)
        _make_control_link(
            db_session, tenant, item, control, coverage=CoverageStatus.OPEN
        )

        result = compute_coverage(
            db_session, tenant_id=tenant.id, scope="tenant", scope_id=None
        )
        clause_refs = {m.clause_ref for m in result.controls[0].framework_mappings}
        assert clause_refs == {"A.6.2.1", "A.6.2.2"}

    def test_clause_backed_by_two_controls_rolls_up(
        self, db_session: Session, tenant: Tenant
    ):
        system = _make_system(db_session, tenant)
        use_case = _make_use_case(db_session, tenant, system)
        aiia = _make_aiia(db_session, tenant, use_case, tier_snapshot=EUAIActTier.HIGH)
        _approve(db_session, aiia)

        control_a = _make_control(db_session)
        control_b = _make_control(db_session)
        _make_fw_map(db_session, control_a, Framework.ISO_42001, "A.6.2.1")
        _make_fw_map(db_session, control_b, Framework.ISO_42001, "A.6.2.1")

        item_a = _make_item(db_session, tenant, aiia)
        _make_control_link(
            db_session, tenant, item_a, control_a, coverage=CoverageStatus.OPEN
        )
        item_b = _make_item(db_session, tenant, aiia)
        _make_control_link(
            db_session, tenant, item_b, control_b, coverage=CoverageStatus.SATISFIED
        )

        result = compute_coverage(
            db_session, tenant_id=tenant.id, scope="tenant", scope_id=None
        )
        assert len(result.frameworks) == 1
        clause = result.frameworks[0]
        assert clause.framework == Framework.ISO_42001
        assert clause.clause_ref == "A.6.2.1"
        assert clause.verdict == "SATISFIED"
        assert {control_a.id, control_b.id} == set(clause.control_ids)


class TestAssessmentScope:
    def test_feeder_id_rejected_with_422(self, db_session: Session, tenant: Tenant):
        system = _make_system(db_session, tenant)
        use_case = _make_use_case(db_session, tenant, system)
        aiia = _make_aiia(db_session, tenant, use_case, tier_snapshot=EUAIActTier.HIGH)
        feeder = _make_feeder(db_session, tenant, aiia, AssessmentType.FRIA)

        from fastapi import HTTPException

        try:
            compute_coverage(
                db_session,
                tenant_id=tenant.id,
                scope="assessment",
                scope_id=feeder.id,
            )
            raise AssertionError("expected HTTPException")
        except HTTPException as exc:
            assert exc.status_code == 422

    def test_assessment_scope_includes_feeder_items(
        self, db_session: Session, tenant: Tenant
    ):
        system = _make_system(db_session, tenant)
        use_case = _make_use_case(db_session, tenant, system)
        aiia = _make_aiia(db_session, tenant, use_case, tier_snapshot=EUAIActTier.HIGH)
        _approve(db_session, aiia)
        feeder = _make_feeder(db_session, tenant, aiia, AssessmentType.FRIA)
        control = _make_control(db_session)
        feeder_item = _make_item(db_session, tenant, feeder)
        _make_control_link(
            db_session, tenant, feeder_item, control, coverage=CoverageStatus.SATISFIED
        )

        result = compute_coverage(
            db_session,
            tenant_id=tenant.id,
            scope="assessment",
            scope_id=aiia.id,
        )
        assert len(result.controls) == 1
        assert result.controls[0].verdict == "SATISFIED"


class TestGoverningAiiaStatus:
    """The load-bearing case (D4): a feeder's own status stays DRAFT for the
    AIIA's whole review lifecycle, so qualification must climb to the
    parent AIIA's status, never read the feeder's own status."""

    def test_feeder_item_qualifies_under_approved_aiia_despite_feeder_draft(
        self, db_session: Session, tenant: Tenant
    ):
        system = _make_system(db_session, tenant)
        use_case = _make_use_case(db_session, tenant, system)
        aiia = _make_aiia(db_session, tenant, use_case, tier_snapshot=EUAIActTier.HIGH)
        _approve(db_session, aiia)
        feeder = _make_feeder(db_session, tenant, aiia, AssessmentType.FRIA)
        assert feeder.status == AssessmentStatus.DRAFT
        control = _make_control(db_session)
        item = _make_item(db_session, tenant, feeder)
        _make_control_link(
            db_session, tenant, item, control, coverage=CoverageStatus.SATISFIED
        )

        result = compute_coverage(
            db_session, tenant_id=tenant.id, scope="tenant", scope_id=None
        )
        assert len(result.controls) == 1
        ref = result.controls[0].breakdown.contributing_refs[0]
        assert ref.governing_status == AssessmentStatus.APPROVED

    def test_feeder_item_excluded_under_draft_aiia_default_admitted_with_flag(
        self, db_session: Session, tenant: Tenant
    ):
        system = _make_system(db_session, tenant)
        use_case = _make_use_case(db_session, tenant, system)
        aiia = _make_aiia(db_session, tenant, use_case, tier_snapshot=EUAIActTier.HIGH)
        # aiia.status stays DRAFT (factory default)
        feeder = _make_feeder(db_session, tenant, aiia, AssessmentType.FRIA)
        control = _make_control(db_session)
        item = _make_item(db_session, tenant, feeder)
        _make_control_link(
            db_session, tenant, item, control, coverage=CoverageStatus.SATISFIED
        )

        default = compute_coverage(
            db_session,
            tenant_id=tenant.id,
            scope="tenant",
            scope_id=None,
        )
        assert default.controls == []

        admitted = compute_coverage(
            db_session,
            tenant_id=tenant.id,
            scope="tenant",
            scope_id=None,
            include_unapproved=True,
        )
        assert len(admitted.controls) == 1
        ref = admitted.controls[0].breakdown.contributing_refs[0]
        assert ref.governing_status == AssessmentStatus.DRAFT

    def test_needs_refresh_excluded_default_distinct_from_draft_under_unapproved(
        self, db_session: Session, tenant: Tenant
    ):
        system = _make_system(db_session, tenant)
        use_case = _make_use_case(db_session, tenant, system)
        aiia = _make_aiia(db_session, tenant, use_case, tier_snapshot=EUAIActTier.HIGH)
        aiia.status = AssessmentStatus.NEEDS_REFRESH
        db_session.flush()
        control = _make_control(db_session)
        item = _make_item(db_session, tenant, aiia)
        _make_control_link(
            db_session, tenant, item, control, coverage=CoverageStatus.SATISFIED
        )

        default = compute_coverage(
            db_session,
            tenant_id=tenant.id,
            scope="tenant",
            scope_id=None,
        )
        assert default.controls == []

        admitted = compute_coverage(
            db_session,
            tenant_id=tenant.id,
            scope="tenant",
            scope_id=None,
            include_unapproved=True,
        )
        assert len(admitted.controls) == 1
        ref = admitted.controls[0].breakdown.contributing_refs[0]
        assert ref.governing_status == AssessmentStatus.NEEDS_REFRESH


class TestTenantIsolation:
    def test_cross_tenant_links_never_counted(
        self, db_session: Session, tenant: Tenant
    ):
        other = Tenant(id=uuid.uuid4(), name="Other Co", slug="other-co")
        db_session.add(other)
        db_session.flush()

        system = _make_system(db_session, other)
        use_case = _make_use_case(db_session, other, system)
        aiia = _make_aiia(db_session, other, use_case, tier_snapshot=EUAIActTier.HIGH)
        _approve(db_session, aiia)
        control = _make_control(db_session)
        item = _make_item(db_session, other, aiia)
        _make_control_link(
            db_session, other, item, control, coverage=CoverageStatus.SATISFIED
        )

        result = compute_coverage(
            db_session,
            tenant_id=tenant.id,
            scope="tenant",
            scope_id=None,
        )
        # Control is global reference data (no tenant_id), so it's visible —
        # but the other tenant's SATISFIED link must not count toward it:
        # it shows up unaddressed for `tenant`, never in the primary matrix.
        assert result.controls == []
        unaddressed_ids = {c.control_id for c in result.unaddressed_controls}
        assert control.id in unaddressed_ids


class TestSystemScope:
    def test_system_scope_spans_multiple_use_cases_via_feeder_use_case_id(
        self, db_session: Session, tenant: Tenant
    ):
        system = _make_system(db_session, tenant)
        uc1 = _make_use_case(db_session, tenant, system)
        uc2 = _make_use_case(db_session, tenant, system)
        aiia1 = _make_aiia(db_session, tenant, uc1, tier_snapshot=EUAIActTier.HIGH)
        _approve(db_session, aiia1)
        aiia2 = _make_aiia(db_session, tenant, uc2, tier_snapshot=EUAIActTier.HIGH)
        _approve(db_session, aiia2)
        feeder2 = _make_feeder(db_session, tenant, aiia2, AssessmentType.FRIA)

        control = _make_control(db_session)
        item1 = _make_item(db_session, tenant, aiia1)
        _make_control_link(
            db_session, tenant, item1, control, coverage=CoverageStatus.OPEN
        )
        item2 = _make_item(db_session, tenant, feeder2)
        _make_control_link(
            db_session, tenant, item2, control, coverage=CoverageStatus.SATISFIED
        )

        result = compute_coverage(
            db_session,
            tenant_id=tenant.id,
            scope="system",
            scope_id=system.id,
        )
        assert len(result.controls) == 1
        assert result.controls[0].verdict == "SATISFIED"
        assert len(result.controls[0].breakdown.contributing_refs) == 2

    def test_unknown_system_404s(self, db_session: Session, tenant: Tenant):
        from fastapi import HTTPException

        try:
            compute_coverage(
                db_session,
                tenant_id=tenant.id,
                scope="system",
                scope_id=uuid.uuid4(),
            )
            raise AssertionError("expected HTTPException")
        except HTTPException as exc:
            assert exc.status_code == 404

    def test_system_with_no_assessments_returns_empty_matrix(
        self, db_session: Session, tenant: Tenant
    ):
        system = _make_system(db_session, tenant)
        result = compute_coverage(
            db_session,
            tenant_id=tenant.id,
            scope="system",
            scope_id=system.id,
        )
        assert result.controls == []


class TestEvidenceSubstantiation:
    """D13 (7b) — require_evidence_for_satisfied=True downgrades an
    unevidenced SATISFIED link to effective PARTIAL, counted separately as
    downgraded_unsubstantiated, never folded into partial and never
    dropping to UNADDRESSED."""

    def test_default_false_leaves_7a_behaviour_untouched(
        self, db_session: Session, tenant: Tenant
    ):
        system = _make_system(db_session, tenant)
        use_case = _make_use_case(db_session, tenant, system)
        aiia = _make_aiia(db_session, tenant, use_case, tier_snapshot=EUAIActTier.HIGH)
        _approve(db_session, aiia)
        control = _make_control(db_session)
        item = _make_item(db_session, tenant, aiia)
        _make_control_link(
            db_session, tenant, item, control, coverage=CoverageStatus.SATISFIED
        )

        result = compute_coverage(
            db_session, tenant_id=tenant.id, scope="tenant", scope_id=None
        )
        assert result.controls[0].verdict == "SATISFIED"
        assert result.controls[0].breakdown.satisfied == 1
        assert result.controls[0].breakdown.downgraded_unsubstantiated == 0

    def test_satisfied_with_evidence_stays_satisfied(
        self, db_session: Session, tenant: Tenant
    ):
        system = _make_system(db_session, tenant)
        use_case = _make_use_case(db_session, tenant, system)
        aiia = _make_aiia(db_session, tenant, use_case, tier_snapshot=EUAIActTier.HIGH)
        _approve(db_session, aiia)
        control = _make_control(db_session)
        item = _make_item(db_session, tenant, aiia)
        _make_control_link(
            db_session, tenant, item, control, coverage=CoverageStatus.SATISFIED
        )
        evidence = _make_evidence(db_session, tenant)
        _make_evidence_link(db_session, tenant, item, evidence)

        result = compute_coverage(
            db_session,
            tenant_id=tenant.id,
            scope="tenant",
            scope_id=None,
            require_evidence_for_satisfied=True,
        )
        assert result.controls[0].verdict == "SATISFIED"
        assert result.controls[0].breakdown.satisfied == 1
        assert result.controls[0].breakdown.downgraded_unsubstantiated == 0

    def test_satisfied_without_evidence_downgrades_distinct_from_partial(
        self, db_session: Session, tenant: Tenant
    ):
        system = _make_system(db_session, tenant)
        use_case = _make_use_case(db_session, tenant, system)
        aiia = _make_aiia(db_session, tenant, use_case, tier_snapshot=EUAIActTier.HIGH)
        _approve(db_session, aiia)
        control = _make_control(db_session)
        item = _make_item(db_session, tenant, aiia)
        _make_control_link(
            db_session, tenant, item, control, coverage=CoverageStatus.SATISFIED
        )

        result = compute_coverage(
            db_session,
            tenant_id=tenant.id,
            scope="tenant",
            scope_id=None,
            require_evidence_for_satisfied=True,
        )
        breakdown = result.controls[0].breakdown
        assert breakdown.satisfied == 0
        assert breakdown.partial == 0
        assert breakdown.downgraded_unsubstantiated == 1

    def test_downgrade_of_only_link_yields_partial_not_unaddressed(
        self, db_session: Session, tenant: Tenant
    ):
        system = _make_system(db_session, tenant)
        use_case = _make_use_case(db_session, tenant, system)
        aiia = _make_aiia(db_session, tenant, use_case, tier_snapshot=EUAIActTier.HIGH)
        _approve(db_session, aiia)
        control = _make_control(db_session)
        item = _make_item(db_session, tenant, aiia)
        _make_control_link(
            db_session, tenant, item, control, coverage=CoverageStatus.SATISFIED
        )

        result = compute_coverage(
            db_session,
            tenant_id=tenant.id,
            scope="tenant",
            scope_id=None,
            require_evidence_for_satisfied=True,
        )
        assert len(result.controls) == 1
        assert result.controls[0].verdict == "PARTIAL"
