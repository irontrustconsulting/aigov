"""Tests for the export / audit pack (sprints/SPRINT_AUDIT_PACK.md, Sprint
7b). build_* functions open their OWN SessionLocal() (export_service.
_export_session) — same shape as evidence_service's upload path (see
tests/test_evidence.py's module docstring) — so we patch
app.services.export_service.SessionLocal to the test session factory and
COMMIT (not just flush) all fixture data before invoking them: a second,
genuinely separate session can only see committed rows.
"""

from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.assessment import AssessmentItemEvidence
from app.models.base import (
    AssessmentStatus,
    AssessmentType,
    CoverageStatus,
    EUAIActTier,
)
from app.models.lifecycle import Evidence
from app.services import assessment_service
from app.services.export_service import (
    build_ato_document,
    build_system_export,
    build_use_case_export,
)
from tests.aiia_helpers import (
    FRIA_AFFECTED_PERSONS_SECTION_KEY,
    STAKEHOLDERS_SECTION_KEY,
    _seed_feeder_template,
    _seed_template,
)
from tests.lifecycle_helpers import (  # noqa: F401
    _grant,
    _make_aiia,
    _make_ato,
    _make_control,
    _make_control_link,
    _make_ctx,
    _make_feeder,
    _make_item,
    _make_member,
    _make_system,
    _make_use_case,
    gov_roles,
    member,
    tenant,
)


@pytest.fixture(autouse=True)
def _patch_export_session(_test_session_factory):
    with patch("app.services.export_service.SessionLocal", _test_session_factory):
        yield


def _make_evidence(db: Session, tenant) -> Evidence:
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


def _approve(db: Session, assessment) -> None:
    assessment.status = AssessmentStatus.APPROVED
    db.flush()


class TestAssessmentRecord:
    def test_native_items_only_plus_feeder_surfaces_into(
        self, db_session: Session, tenant, member, gov_roles
    ):
        user, m = member
        _grant(db_session, tenant, m, gov_roles["auditor"])
        _seed_template(db_session, EUAIActTier.HIGH)
        _seed_feeder_template(db_session, EUAIActTier.HIGH, AssessmentType.FRIA)

        system = _make_system(db_session, tenant)
        use_case = _make_use_case(db_session, tenant, system)
        aiia = _make_aiia(db_session, tenant, use_case, tier_snapshot=EUAIActTier.HIGH)
        _approve(db_session, aiia)
        native_item = _make_item(
            db_session, tenant, aiia, section_key="risk_identification"
        )

        feeder = _make_feeder(db_session, tenant, aiia, AssessmentType.FRIA)
        surfaced_item = _make_item(
            db_session, tenant, feeder, section_key=FRIA_AFFECTED_PERSONS_SECTION_KEY
        )
        private_item = _make_item(
            db_session, tenant, feeder, section_key="fria_internal_complaint_process"
        )

        ctx = _make_ctx(user, m, tenant)
        db_session.commit()

        result = build_use_case_export(ctx, use_case.id)

        native_ids = {i.id for i in result.assessment.native_items}
        assert native_ids == {native_item.id}
        assert result.assessment.native_items[0].surfaces_into is None

        assert len(result.assessment.feeders) == 1
        feeder_read = result.assessment.feeders[0]
        assert feeder_read.assessment_id == feeder.id
        by_id = {i.id: i for i in feeder_read.items}
        assert by_id[surfaced_item.id].surfaces_into == STAKEHOLDERS_SECTION_KEY
        assert by_id[private_item.id].surfaces_into is None
        # No re-surfacing/dup into the AIIA's own native item list (inv 16/41).
        assert surfaced_item.id not in native_ids


class TestEvidenceManifest:
    def test_deduped_by_reference_no_bytes_no_urls(
        self, db_session: Session, tenant, member, gov_roles
    ):
        user, m = member
        _grant(db_session, tenant, m, gov_roles["auditor"])
        system = _make_system(db_session, tenant)
        use_case = _make_use_case(db_session, tenant, system)
        aiia = _make_aiia(db_session, tenant, use_case, tier_snapshot=EUAIActTier.HIGH)
        _approve(db_session, aiia)
        item1 = _make_item(db_session, tenant, aiia)
        item2 = _make_item(db_session, tenant, aiia)
        evidence = _make_evidence(db_session, tenant)
        for item in (item1, item2):
            db_session.add(
                AssessmentItemEvidence(
                    id=uuid.uuid4(),
                    tenant_id=tenant.id,
                    item_id=item.id,
                    evidence_id=evidence.id,
                )
            )
        db_session.flush()

        ctx = _make_ctx(user, m, tenant)
        db_session.commit()

        result = build_use_case_export(ctx, use_case.id)
        assert len(result.evidence_manifest) == 1
        entry = result.evidence_manifest[0]
        assert entry.id == evidence.id
        assert set(entry.back_refs) == {item1.id, item2.id}
        assert not hasattr(entry, "download_url")
        assert not hasattr(entry, "presigned_url")


class TestAtoDocument:
    def test_never_authorised_404s(
        self, db_session: Session, tenant, member, gov_roles
    ):
        user, m = member
        _grant(db_session, tenant, m, gov_roles["auditor"])
        system = _make_system(db_session, tenant)
        use_case = _make_use_case(db_session, tenant, system)
        ctx = _make_ctx(user, m, tenant)
        db_session.commit()

        with pytest.raises(HTTPException) as exc_info:
            build_ato_document(ctx, use_case.id)
        assert exc_info.value.status_code == 404

    def test_most_recent_default_and_round_selects_cycle(
        self, db_session: Session, tenant, member, gov_roles
    ):
        user, m = member
        _grant(db_session, tenant, m, gov_roles["auditor"])
        system = _make_system(db_session, tenant)
        use_case = _make_use_case(db_session, tenant, system)
        aiia = _make_aiia(db_session, tenant, use_case, tier_snapshot=EUAIActTier.HIGH)
        _approve(db_session, aiia)
        ato1 = _make_ato(db_session, tenant, use_case, aiia, user, submission_round=1)
        ato2 = _make_ato(db_session, tenant, use_case, aiia, user, submission_round=2)
        ctx = _make_ctx(user, m, tenant)
        db_session.commit()

        latest = build_ato_document(ctx, use_case.id)
        assert latest.ato.id == ato2.id
        assert latest.basis_is_current_state_not_authorisation_snapshot is True

        round1 = build_ato_document(ctx, use_case.id, round=1)
        assert round1.ato.id == ato1.id


class TestEmptyCases:
    def test_use_case_with_no_assessment_returns_empty_sections(
        self, db_session: Session, tenant, member, gov_roles
    ):
        user, m = member
        _grant(db_session, tenant, m, gov_roles["auditor"])
        system = _make_system(db_session, tenant)
        use_case = _make_use_case(db_session, tenant, system)
        ctx = _make_ctx(user, m, tenant)
        db_session.commit()

        result = build_use_case_export(ctx, use_case.id)
        assert result.assessment.aiia_id is None
        assert result.assessment.native_items == []
        assert result.coverage.controls == []
        assert result.atos == []

    def test_empty_system_returns_with_empties(
        self, db_session: Session, tenant, member, gov_roles
    ):
        user, m = member
        _grant(db_session, tenant, m, gov_roles["auditor"])
        system = _make_system(db_session, tenant)
        ctx = _make_ctx(user, m, tenant)
        db_session.commit()

        result = build_system_export(ctx, system.id)
        assert result.use_cases == []
        assert result.system_coverage.controls == []


class TestContentHash:
    def test_stable_across_identical_state_changes_after_mutation(
        self, db_session: Session, tenant, member, gov_roles
    ):
        user, m = member
        _grant(db_session, tenant, m, gov_roles["auditor"])
        system = _make_system(db_session, tenant)
        use_case = _make_use_case(db_session, tenant, system)
        aiia = _make_aiia(db_session, tenant, use_case, tier_snapshot=EUAIActTier.HIGH)
        _approve(db_session, aiia)
        item = _make_item(db_session, tenant, aiia)
        control = _make_control(db_session)
        _make_control_link(
            db_session, tenant, item, control, coverage=CoverageStatus.OPEN
        )
        ctx = _make_ctx(user, m, tenant)
        db_session.commit()

        first = build_use_case_export(ctx, use_case.id)
        second = build_use_case_export(ctx, use_case.id)
        assert first.content_hash == second.content_hash

        other_control = _make_control(db_session)
        _make_control_link(
            db_session, tenant, item, other_control, coverage=CoverageStatus.SATISFIED
        )
        db_session.commit()

        third = build_use_case_export(ctx, use_case.id)
        assert third.content_hash != first.content_hash


class TestAuditClosure:
    def test_removal_pair_survives_link_hard_delete(
        self, db_session: Session, tenant, member, gov_roles
    ):
        """D14 — link rows hard-delete; the closure must still show both
        the .created and .deleted events of a removed link, via
        detail.item_id, since the link-row id no longer exists to close
        against."""
        user, m = member
        _grant(db_session, tenant, m, gov_roles["auditor"])
        system = _make_system(db_session, tenant)
        use_case = _make_use_case(db_session, tenant, system)
        aiia = _make_aiia(db_session, tenant, use_case, tier_snapshot=EUAIActTier.HIGH)
        item = _make_item(
            db_session, tenant, aiia
        )  # AIIA still DRAFT: authoring unlocked
        control = _make_control(db_session)
        evidence = _make_evidence(db_session, tenant)
        ctx = _make_ctx(user, m, tenant)

        link = assessment_service.create_control_link(
            item.id, control.id, CoverageStatus.SATISFIED, ctx, db_session
        )
        assessment_service.delete_control_link(link.id, ctx, db_session)
        assessment_service.create_evidence_link(item.id, evidence.id, ctx, db_session)
        assessment_service.delete_evidence_link(item.id, evidence.id, ctx, db_session)

        _approve(db_session, aiia)
        db_session.commit()

        result = build_use_case_export(ctx, use_case.id)
        actions = [e.action for e in result.audit_trail]
        assert actions.count("control_link.created") == 1
        assert actions.count("control_link.deleted") == 1
        assert actions.count("evidence.linked") == 1
        assert actions.count("evidence.unlinked") == 1


class TestSystemExport:
    def test_unknown_system_404s(self, db_session: Session, tenant, member, gov_roles):
        user, m = member
        _grant(db_session, tenant, m, gov_roles["auditor"])
        ctx = _make_ctx(user, m, tenant)
        db_session.commit()

        with pytest.raises(HTTPException) as exc_info:
            build_system_export(ctx, uuid.uuid4())
        assert exc_info.value.status_code == 404

    def test_system_export_combines_multiple_use_cases(
        self, db_session: Session, tenant, member, gov_roles
    ):
        user, m = member
        _grant(db_session, tenant, m, gov_roles["auditor"])
        system = _make_system(db_session, tenant)
        uc1 = _make_use_case(db_session, tenant, system)
        uc2 = _make_use_case(db_session, tenant, system)
        aiia1 = _make_aiia(db_session, tenant, uc1, tier_snapshot=EUAIActTier.HIGH)
        _approve(db_session, aiia1)
        aiia2 = _make_aiia(db_session, tenant, uc2, tier_snapshot=EUAIActTier.HIGH)
        _approve(db_session, aiia2)
        ctx = _make_ctx(user, m, tenant)
        db_session.commit()

        result = build_system_export(ctx, system.id)
        assert {s.use_case_id for s in result.use_cases} == {uc1.id, uc2.id}


class TestGovernanceGate:
    def test_no_governance_role_403s(self, db_session: Session, tenant, member):
        user, m = member  # no role granted
        system = _make_system(db_session, tenant)
        use_case = _make_use_case(db_session, tenant, system)
        ctx = _make_ctx(user, m, tenant)
        db_session.commit()

        with pytest.raises(HTTPException) as exc_info:
            build_use_case_export(ctx, use_case.id)
        assert exc_info.value.status_code == 403
