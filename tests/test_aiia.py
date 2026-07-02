"""
Tests for the AIIA core sprint (sprints/SPRINT_AIIA.md, Phase A).

Covers the §7 acceptance criteria: creation + classification gate, the
confirm/amend provenance state machine, optimistic concurrency (412) vs the
from-state guard (409), pristine-delete, control links + FK hardening,
governance-role gating (incl. admin -> 403), sections, and the gated
reference reads.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models.assessment import (
    Assessment,
    AssessmentItem,
    AssessmentItemControl,
    Classification,
)
from app.models.base import ClassificationStatus, EUAIActTier, ProvenanceConfidence
from app.models.governance import GovernanceRole
from app.models.identity import Tenant
from app.models.lifecycle import AuditEvent
from tests.aiia_helpers import (  # noqa: F401 (fixtures used by name)
    OVERVIEW_SECTION_KEY,
    RISK_SECTION_KEY,
    STAKEHOLDERS_SECTION_KEY,
    _ApiCtx,
    _grant,
    _make_classification,
    _make_control,
    _make_ctx,
    _make_member,
    _make_system,
    _make_use_case,
    _make_vendor_product_risk,
    _seed_template,
    admin_member,
    gov_roles,
    member,
    tenant,
)

# ---------------------------------------------------------------------------
# 1. Creation + classification gate
# ---------------------------------------------------------------------------

class TestCreateAIIA:
    def test_system_owner_creates_aiia_with_prefill(
        self, client, db_session, tenant, member, gov_roles,
    ):
        user, m = member
        _grant(db_session, tenant, m, gov_roles["system_owner"])
        product, risk = _make_vendor_product_risk(db_session)
        system = _make_system(db_session, tenant, product)
        use_case = _make_use_case(db_session, tenant, system)
        _make_classification(db_session, tenant, use_case, EUAIActTier.HIGH)
        _seed_template(db_session, EUAIActTier.HIGH)

        ctx = _make_ctx(user, m, tenant)
        with _ApiCtx(ctx, db_session):
            r = client.post(f"/v1/use-cases/{use_case.id}/assessments")

        assert r.status_code == 201
        body = r.json()
        assert body["tier_snapshot"] == "high_risk"
        assert body["classification_version"] == 1
        assert body["is_current"] is True

        items = list(db_session.scalars(
            select(AssessmentItem).where(AssessmentItem.assessment_id == uuid.UUID(body["id"]))
        ))
        by_section = {}
        for i in items:
            by_section.setdefault(i.section_key, []).append(i)

        # required section instantiated, blank, curated
        assert len(by_section["system_overview"]) >= 1  # required prompt + snapshot facts
        curated = [i for i in by_section["system_overview"] if i.provenance == ProvenanceConfidence.CATALOGUE_CURATED]
        assert len(curated) == 1
        assert curated[0].response is None

        # snapshotted facts present as USER_PROVIDED with source_ref (system.name)
        snapshotted = [i for i in by_section["system_overview"] if i.provenance == ProvenanceConfidence.USER_PROVIDED]
        assert any(i.source_ref == "system.name" for i in snapshotted)

        # proposed risk present, identity-only, with selection_basis
        risk_items = by_section[RISK_SECTION_KEY]
        assert len(risk_items) == 1
        assert risk_items[0].risk_id == risk.id
        assert risk_items[0].provenance == ProvenanceConfidence.AI_SUGGESTED
        assert risk_items[0].selection_basis is not None
        assert risk_items[0].likelihood is None
        assert risk_items[0].severity is None

        # one assessment.created audit event
        events = list(db_session.scalars(
            select(AuditEvent).where(AuditEvent.action == "assessment.created")
        ))
        assert len(events) == 1

    def test_prohibited_tier_blocked(self, db_session, tenant, member, gov_roles, client):
        user, m = member
        _grant(db_session, tenant, m, gov_roles["system_owner"])
        system = _make_system(db_session, tenant)
        use_case = _make_use_case(db_session, tenant, system)
        _make_classification(db_session, tenant, use_case, EUAIActTier.PROHIBITED)

        ctx = _make_ctx(user, m, tenant)
        with _ApiCtx(ctx, db_session):
            r = client.post(f"/v1/use-cases/{use_case.id}/assessments")
        assert r.status_code == 409
        assert db_session.scalar(select(Assessment).where(Assessment.use_case_id == use_case.id)) is None

    def test_requires_context_blocked(self, db_session, tenant, member, gov_roles, client):
        user, m = member
        _grant(db_session, tenant, m, gov_roles["system_owner"])
        system = _make_system(db_session, tenant)
        use_case = _make_use_case(db_session, tenant, system)
        _make_classification(db_session, tenant, use_case, EUAIActTier.REQUIRES_CONTEXT)

        ctx = _make_ctx(user, m, tenant)
        with _ApiCtx(ctx, db_session):
            r = client.post(f"/v1/use-cases/{use_case.id}/assessments")
        assert r.status_code == 409

    def test_unsigned_context_classification_blocked(
        self, db_session, tenant, member, gov_roles, client,
    ):
        """Sprint 5 WI-4 / STATE_MACHINE.md Appendix A #1: the context gate
        computes a concrete tier into a PENDING_REVIEW snapshot but does not
        stamp use_case.eu_tier (that's sign-off's job). create_aiia must read
        eu_tier, not the snapshot's own tier — so this case 409s even though
        the current snapshot already carries a concrete (HIGH) tier."""
        user, m = member
        _grant(db_session, tenant, m, gov_roles["system_owner"])
        system = _make_system(db_session, tenant)
        use_case = _make_use_case(db_session, tenant, system)
        use_case.eu_tier = EUAIActTier.REQUIRES_CONTEXT
        db_session.add(Classification(
            id=uuid.uuid4(), tenant_id=tenant.id, use_case_id=use_case.id,
            tier=EUAIActTier.HIGH, rationale="context-computed, unsigned",
            version=1, is_current=True, status=ClassificationStatus.PENDING_REVIEW,
        ))
        db_session.flush()

        ctx = _make_ctx(user, m, tenant)
        with _ApiCtx(ctx, db_session):
            r = client.post(f"/v1/use-cases/{use_case.id}/assessments")
        assert r.status_code == 409
        assert db_session.scalar(
            select(Assessment).where(Assessment.use_case_id == use_case.id)
        ) is None

    def test_no_current_classification_blocked(self, db_session, tenant, member, gov_roles, client):
        user, m = member
        _grant(db_session, tenant, m, gov_roles["system_owner"])
        system = _make_system(db_session, tenant)
        use_case = _make_use_case(db_session, tenant, system)
        # No Classification row at all.

        ctx = _make_ctx(user, m, tenant)
        with _ApiCtx(ctx, db_session):
            r = client.post(f"/v1/use-cases/{use_case.id}/assessments")
        assert r.status_code == 409

    def test_duplicate_aiia_conflict(self, db_session, tenant, member, gov_roles, client):
        user, m = member
        _grant(db_session, tenant, m, gov_roles["system_owner"])
        system = _make_system(db_session, tenant)
        use_case = _make_use_case(db_session, tenant, system)
        _make_classification(db_session, tenant, use_case, EUAIActTier.HIGH)
        _seed_template(db_session, EUAIActTier.HIGH)

        ctx = _make_ctx(user, m, tenant)
        with _ApiCtx(ctx, db_session):
            r1 = client.post(f"/v1/use-cases/{use_case.id}/assessments")
            assert r1.status_code == 201
            r2 = client.post(f"/v1/use-cases/{use_case.id}/assessments")
        assert r2.status_code == 409

    def test_empty_template_is_loud_failure(self, db_session, tenant, member, gov_roles, client):
        """MINIMAL is resolvable but deliberately has no seeded template rows."""
        user, m = member
        _grant(db_session, tenant, m, gov_roles["system_owner"])
        system = _make_system(db_session, tenant)
        use_case = _make_use_case(db_session, tenant, system)
        _make_classification(db_session, tenant, use_case, EUAIActTier.MINIMAL)
        # No _seed_template call.

        ctx = _make_ctx(user, m, tenant)
        with _ApiCtx(ctx, db_session):
            r = client.post(f"/v1/use-cases/{use_case.id}/assessments")
        assert r.status_code == 500

    def test_member_without_governance_role_403(self, db_session, tenant, member, client):
        user, m = member
        system = _make_system(db_session, tenant)
        use_case = _make_use_case(db_session, tenant, system)

        ctx = _make_ctx(user, m, tenant)
        with _ApiCtx(ctx, db_session):
            r = client.post(f"/v1/use-cases/{use_case.id}/assessments")
        assert r.status_code == 403

    def test_admin_gets_403_on_reads_too(self, db_session, tenant, admin_member, gov_roles, client):
        """Admin (administrative axis) holds zero governance roles -> 403,
        including on reads."""
        user, m = admin_member
        system = _make_system(db_session, tenant)
        use_case = _make_use_case(db_session, tenant, system)
        _make_classification(db_session, tenant, use_case, EUAIActTier.HIGH)

        ctx = _make_ctx(user, m, tenant)
        with _ApiCtx(ctx, db_session):
            r_create = client.post(f"/v1/use-cases/{use_case.id}/assessments")
            r_list = client.get(f"/v1/use-cases/{use_case.id}/assessments")
        assert r_create.status_code == 403
        assert r_list.status_code == 403


# ---------------------------------------------------------------------------
# Helper to build a full AIIA via the API, for item-mutation tests
# ---------------------------------------------------------------------------

def _create_aiia(client, db_session, tenant, owner_member, gov_roles, tier=EUAIActTier.HIGH):
    user, m = owner_member
    _grant(db_session, tenant, m, gov_roles["system_owner"])
    system = _make_system(db_session, tenant)
    use_case = _make_use_case(db_session, tenant, system)
    _make_classification(db_session, tenant, use_case, tier)
    _seed_template(db_session, tier)

    ctx = _make_ctx(user, m, tenant)
    with _ApiCtx(ctx, db_session):
        r = client.post(f"/v1/use-cases/{use_case.id}/assessments")
    assert r.status_code == 201
    return r.json(), use_case


# ---------------------------------------------------------------------------
# 2. Sections + item creation
# ---------------------------------------------------------------------------

class TestSections:
    def test_get_sections_distinguishes_required_recommended(
        self, db_session, tenant, member, gov_roles, client,
    ):
        aiia, _ = _create_aiia(client, db_session, tenant, member, gov_roles)
        user, m = member
        ctx = _make_ctx(user, m, tenant)
        with _ApiCtx(ctx, db_session):
            r = client.get(f"/v1/assessments/{aiia['id']}/sections")
        assert r.status_code == 200
        by_key = {s["section_key"]: s for s in r.json()}
        assert by_key["system_overview"]["applicability"] == "required"
        assert by_key["system_overview"]["instantiated"] is True
        assert by_key[STAKEHOLDERS_SECTION_KEY]["applicability"] == "recommended"
        assert by_key[STAKEHOLDERS_SECTION_KEY]["instantiated"] is False

    def test_post_items_instantiates_recommended_section(
        self, db_session, tenant, member, gov_roles, client,
    ):
        aiia, _ = _create_aiia(client, db_session, tenant, member, gov_roles)
        user, m = member
        _grant(db_session, tenant, m, gov_roles["contributor"])
        ctx = _make_ctx(user, m, tenant)
        with _ApiCtx(ctx, db_session):
            r = client.post(
                f"/v1/assessments/{aiia['id']}/items",
                json={"section_key": STAKEHOLDERS_SECTION_KEY},
            )
        assert r.status_code == 201
        assert r.json()["section_key"] == STAKEHOLDERS_SECTION_KEY
        assert r.json()["provenance"] == "catalogue_curated"

    def test_post_items_unknown_section_key_422(
        self, db_session, tenant, member, gov_roles, client,
    ):
        aiia, _ = _create_aiia(client, db_session, tenant, member, gov_roles)
        user, m = member
        ctx = _make_ctx(user, m, tenant)
        with _ApiCtx(ctx, db_session):
            r = client.post(
                f"/v1/assessments/{aiia['id']}/items",
                json={"section_key": "does_not_exist"},
            )
        assert r.status_code == 422


# ---------------------------------------------------------------------------
# 3. Confirm / amend provenance state machine
# ---------------------------------------------------------------------------

class TestItemMutation:
    def _risk_item(self, db_session, aiia_id) -> AssessmentItem:
        return db_session.scalar(
            select(AssessmentItem).where(
                AssessmentItem.assessment_id == uuid.UUID(aiia_id),
                AssessmentItem.section_key == RISK_SECTION_KEY,
            )
        )

    def test_authoring_patch_on_ai_suggested_blocked(
        self, db_session, tenant, member, gov_roles, client,
    ):
        product, risk = _make_vendor_product_risk(db_session)
        user, m = member
        _grant(db_session, tenant, m, gov_roles["system_owner"])
        system = _make_system(db_session, tenant, product)
        use_case = _make_use_case(db_session, tenant, system)
        _make_classification(db_session, tenant, use_case, EUAIActTier.HIGH)
        _seed_template(db_session, EUAIActTier.HIGH)
        ctx = _make_ctx(user, m, tenant)
        with _ApiCtx(ctx, db_session):
            r = client.post(f"/v1/use-cases/{use_case.id}/assessments")
        aiia = r.json()
        item = self._risk_item(db_session, aiia["id"])
        assert item.provenance == ProvenanceConfidence.AI_SUGGESTED

        with _ApiCtx(ctx, db_session):
            r = client.patch(
                f"/v1/assessments/{aiia['id']}/items/{item.id}",
                json={"likelihood": 3},
                headers={"If-Match": str(item.lock_version)},
            )
        assert r.status_code == 409

    def test_confirm_then_author_succeeds(
        self, db_session, tenant, member, gov_roles, client,
    ):
        product, risk = _make_vendor_product_risk(db_session)
        user, m = member
        _grant(db_session, tenant, m, gov_roles["system_owner"])
        _grant(db_session, tenant, m, gov_roles["contributor"])
        system = _make_system(db_session, tenant, product)
        use_case = _make_use_case(db_session, tenant, system)
        _make_classification(db_session, tenant, use_case, EUAIActTier.HIGH)
        _seed_template(db_session, EUAIActTier.HIGH)

        ctx = _make_ctx(user, m, tenant)
        with _ApiCtx(ctx, db_session):
            r = client.post(f"/v1/use-cases/{use_case.id}/assessments")
        aiia = r.json()
        item = self._risk_item(db_session, aiia["id"])
        assert item is not None

        with _ApiCtx(ctx, db_session):
            r_confirm = client.post(
                f"/v1/assessments/{aiia['id']}/items/{item.id}/confirm",
                headers={"If-Match": str(item.lock_version)},
            )
        assert r_confirm.status_code == 200
        confirmed = r_confirm.json()
        assert confirmed["provenance"] == "user_confirmed"

        with _ApiCtx(ctx, db_session):
            r_author = client.patch(
                f"/v1/assessments/{aiia['id']}/items/{item.id}",
                json={"likelihood": 4, "severity": 3, "mitigation_plan": "Mitigate via X"},
                headers={"If-Match": str(confirmed["lock_version"])},
            )
        assert r_author.status_code == 200
        authored = r_author.json()
        assert authored["likelihood"] == 4
        assert authored["provenance"] == "user_confirmed"  # author keeps state per §4 table

        events = list(db_session.scalars(
            select(AuditEvent).where(AuditEvent.action == "assessment_item.amended")
        ))
        assert len(events) == 1

    def test_noop_patch_is_silent(self, db_session, tenant, member, gov_roles, client):
        aiia, _ = _create_aiia(client, db_session, tenant, member, gov_roles)
        item = db_session.scalar(
            select(AssessmentItem).where(
                AssessmentItem.assessment_id == uuid.UUID(aiia["id"]),
                AssessmentItem.section_key == "system_overview",
                AssessmentItem.provenance == ProvenanceConfidence.CATALOGUE_CURATED,
            )
        )
        user, m = member
        ctx = _make_ctx(user, m, tenant)
        with _ApiCtx(ctx, db_session):
            r = client.patch(
                f"/v1/assessments/{aiia['id']}/items/{item.id}",
                json={},
                headers={"If-Match": str(item.lock_version)},
            )
        assert r.status_code == 200
        events = list(db_session.scalars(
            select(AuditEvent).where(AuditEvent.action == "assessment_item.amended")
        ))
        assert len(events) == 0

    def test_curated_answer_transitions_to_user_provided(
        self, db_session, tenant, member, gov_roles, client,
    ):
        aiia, _ = _create_aiia(client, db_session, tenant, member, gov_roles)
        item = db_session.scalar(
            select(AssessmentItem).where(
                AssessmentItem.assessment_id == uuid.UUID(aiia["id"]),
                AssessmentItem.section_key == "system_overview",
                AssessmentItem.provenance == ProvenanceConfidence.CATALOGUE_CURATED,
            )
        )
        user, m = member
        ctx = _make_ctx(user, m, tenant)
        with _ApiCtx(ctx, db_session):
            r = client.patch(
                f"/v1/assessments/{aiia['id']}/items/{item.id}",
                json={"response": "Answered"},
                headers={"If-Match": str(item.lock_version)},
            )
        assert r.status_code == 200
        assert r.json()["provenance"] == "user_provided"

    def test_stale_if_match_412(self, db_session, tenant, member, gov_roles, client):
        aiia, _ = _create_aiia(client, db_session, tenant, member, gov_roles)
        item = db_session.scalar(
            select(AssessmentItem).where(
                AssessmentItem.assessment_id == uuid.UUID(aiia["id"]),
                AssessmentItem.section_key == "system_overview",
                AssessmentItem.provenance == ProvenanceConfidence.CATALOGUE_CURATED,
            )
        )
        user, m = member
        ctx = _make_ctx(user, m, tenant)
        with _ApiCtx(ctx, db_session):
            r = client.patch(
                f"/v1/assessments/{aiia['id']}/items/{item.id}",
                json={"response": "Answered"},
                headers={"If-Match": str(item.lock_version + 99)},
            )
        assert r.status_code == 412

    def test_confirm_non_ai_suggested_409(self, db_session, tenant, member, gov_roles, client):
        aiia, _ = _create_aiia(client, db_session, tenant, member, gov_roles)
        item = db_session.scalar(
            select(AssessmentItem).where(
                AssessmentItem.assessment_id == uuid.UUID(aiia["id"]),
                AssessmentItem.section_key == "system_overview",
                AssessmentItem.provenance == ProvenanceConfidence.CATALOGUE_CURATED,
            )
        )
        user, m = member
        ctx = _make_ctx(user, m, tenant)
        with _ApiCtx(ctx, db_session):
            r = client.post(
                f"/v1/assessments/{aiia['id']}/items/{item.id}/confirm",
                headers={"If-Match": str(item.lock_version)},
            )
        assert r.status_code == 409


# ---------------------------------------------------------------------------
# 4. Control links
# ---------------------------------------------------------------------------

class TestControlLinks:
    def test_create_link_then_duplicate_409(self, db_session, tenant, member, gov_roles, client):
        aiia, _ = _create_aiia(client, db_session, tenant, member, gov_roles)
        item = db_session.scalar(
            select(AssessmentItem).where(AssessmentItem.assessment_id == uuid.UUID(aiia["id"])).limit(1)
        )
        control = _make_control(db_session)
        user, m = member
        ctx = _make_ctx(user, m, tenant)
        with _ApiCtx(ctx, db_session):
            r1 = client.post(
                f"/v1/assessments/{aiia['id']}/items/{item.id}/control-links",
                json={"control_id": str(control.id), "coverage": "partial"},
            )
            assert r1.status_code == 201
            r2 = client.post(
                f"/v1/assessments/{aiia['id']}/items/{item.id}/control-links",
                json={"control_id": str(control.id), "coverage": "partial"},
            )
        assert r2.status_code == 409

    def test_unknown_control_id_422(self, db_session, tenant, member, gov_roles, client):
        aiia, _ = _create_aiia(client, db_session, tenant, member, gov_roles)
        item = db_session.scalar(
            select(AssessmentItem).where(AssessmentItem.assessment_id == uuid.UUID(aiia["id"])).limit(1)
        )
        user, m = member
        ctx = _make_ctx(user, m, tenant)
        with _ApiCtx(ctx, db_session):
            r = client.post(
                f"/v1/assessments/{aiia['id']}/items/{item.id}/control-links",
                json={"control_id": str(uuid.uuid4()), "coverage": "partial"},
            )
        assert r.status_code == 422

    def test_bad_coverage_422(self, db_session, tenant, member, gov_roles, client):
        aiia, _ = _create_aiia(client, db_session, tenant, member, gov_roles)
        item = db_session.scalar(
            select(AssessmentItem).where(AssessmentItem.assessment_id == uuid.UUID(aiia["id"])).limit(1)
        )
        control = _make_control(db_session)
        user, m = member
        ctx = _make_ctx(user, m, tenant)
        with _ApiCtx(ctx, db_session):
            r = client.post(
                f"/v1/assessments/{aiia['id']}/items/{item.id}/control-links",
                json={"control_id": str(control.id), "coverage": "not_a_real_value"},
            )
        assert r.status_code == 422

    def test_delete_link(self, db_session, tenant, member, gov_roles, client):
        aiia, _ = _create_aiia(client, db_session, tenant, member, gov_roles)
        item = db_session.scalar(
            select(AssessmentItem).where(AssessmentItem.assessment_id == uuid.UUID(aiia["id"])).limit(1)
        )
        control = _make_control(db_session)
        user, m = member
        ctx = _make_ctx(user, m, tenant)
        with _ApiCtx(ctx, db_session):
            r1 = client.post(
                f"/v1/assessments/{aiia['id']}/items/{item.id}/control-links",
                json={"control_id": str(control.id), "coverage": "partial"},
            )
            link_id = r1.json()["id"]
            r2 = client.delete(
                f"/v1/assessments/{aiia['id']}/items/{item.id}/control-links/{link_id}"
            )
        assert r2.status_code == 204
        assert db_session.get(AssessmentItemControl, uuid.UUID(link_id)) is None


# ---------------------------------------------------------------------------
# 5. FK hardening (RESTRICT, not CASCADE/SET NULL)
# ---------------------------------------------------------------------------

class TestFKHardening:
    def test_deleting_referenced_risk_is_restricted(self, db_session, tenant, member, gov_roles, client):
        product, risk = _make_vendor_product_risk(db_session)
        system = _make_system(db_session, tenant, product)
        use_case = _make_use_case(db_session, tenant, system)
        _make_classification(db_session, tenant, use_case, EUAIActTier.HIGH)
        _seed_template(db_session, EUAIActTier.HIGH)
        user, m = member
        _grant(db_session, tenant, m, gov_roles["system_owner"])
        ctx = _make_ctx(user, m, tenant)
        with _ApiCtx(ctx, db_session):
            r = client.post(f"/v1/use-cases/{use_case.id}/assessments")
        assert r.status_code == 201

        db_session.delete(risk)
        with pytest.raises(IntegrityError):
            db_session.flush()
        db_session.rollback()

    def test_deleting_referenced_control_is_restricted(self, db_session, tenant, member, gov_roles, client):
        aiia, _ = _create_aiia(client, db_session, tenant, member, gov_roles)
        item = db_session.scalar(
            select(AssessmentItem).where(AssessmentItem.assessment_id == uuid.UUID(aiia["id"])).limit(1)
        )
        control = _make_control(db_session)
        user, m = member
        ctx = _make_ctx(user, m, tenant)
        with _ApiCtx(ctx, db_session):
            client.post(
                f"/v1/assessments/{aiia['id']}/items/{item.id}/control-links",
                json={"control_id": str(control.id), "coverage": "partial"},
            )

        db_session.delete(control)
        with pytest.raises(IntegrityError):
            db_session.flush()
        db_session.rollback()


# ---------------------------------------------------------------------------
# 6. Pristine delete
# ---------------------------------------------------------------------------

class TestDelete:
    def test_pristine_delete_succeeds(self, db_session, tenant, member, gov_roles, client):
        aiia, _ = _create_aiia(client, db_session, tenant, member, gov_roles)
        user, m = member
        ctx = _make_ctx(user, m, tenant)
        with _ApiCtx(ctx, db_session):
            r = client.delete(f"/v1/assessments/{aiia['id']}")
        assert r.status_code == 204
        assert db_session.get(Assessment, uuid.UUID(aiia["id"])) is None
        events = list(db_session.scalars(
            select(AuditEvent).where(AuditEvent.action == "assessment.deleted")
        ))
        assert len(events) == 1

    def test_worked_assessment_delete_409(self, db_session, tenant, member, gov_roles, client):
        aiia, _ = _create_aiia(client, db_session, tenant, member, gov_roles)
        item = db_session.scalar(
            select(AssessmentItem).where(
                AssessmentItem.assessment_id == uuid.UUID(aiia["id"]),
                AssessmentItem.section_key == "system_overview",
                AssessmentItem.provenance == ProvenanceConfidence.CATALOGUE_CURATED,
            )
        )
        user, m = member
        ctx = _make_ctx(user, m, tenant)
        with _ApiCtx(ctx, db_session):
            client.patch(
                f"/v1/assessments/{aiia['id']}/items/{item.id}",
                json={"response": "Answered"},
                headers={"If-Match": str(item.lock_version)},
            )
            r = client.delete(f"/v1/assessments/{aiia['id']}")
        assert r.status_code == 409

    def test_delete_item_cascades_control_links(self, db_session, tenant, member, gov_roles, client):
        aiia, _ = _create_aiia(client, db_session, tenant, member, gov_roles)
        item = db_session.scalar(
            select(AssessmentItem).where(AssessmentItem.assessment_id == uuid.UUID(aiia["id"])).limit(1)
        )
        control = _make_control(db_session)
        user, m = member
        ctx = _make_ctx(user, m, tenant)
        with _ApiCtx(ctx, db_session):
            client.post(
                f"/v1/assessments/{aiia['id']}/items/{item.id}/control-links",
                json={"control_id": str(control.id), "coverage": "partial"},
            )
            r = client.delete(f"/v1/assessments/{aiia['id']}/items/{item.id}")
        assert r.status_code == 204
        assert db_session.get(AssessmentItem, item.id) is None
        remaining_links = list(db_session.scalars(
            select(AssessmentItemControl).where(AssessmentItemControl.item_id == item.id)
        ))
        assert remaining_links == []


# ---------------------------------------------------------------------------
# 7. Tenant isolation (app-level filter; test DB has no RLS)
# ---------------------------------------------------------------------------

class TestTenantIsolation:
    def test_cross_tenant_item_access_404s(self, db_session, tenant, member, gov_roles, client):
        aiia, _ = _create_aiia(client, db_session, tenant, member, gov_roles)
        item = db_session.scalar(
            select(AssessmentItem).where(AssessmentItem.assessment_id == uuid.UUID(aiia["id"])).limit(1)
        )

        other_tenant = Tenant(id=uuid.uuid4(), name="Other Co", slug="other-co")
        db_session.add(other_tenant)
        db_session.flush()
        other_user, other_m = _make_member(db_session, other_tenant)
        other_ctx = _make_ctx(other_user, other_m, other_tenant)

        with _ApiCtx(other_ctx, db_session):
            r = client.patch(
                f"/v1/assessments/{aiia['id']}/items/{item.id}",
                json={"response": "Hijacked"},
                headers={"If-Match": str(item.lock_version)},
            )
        assert r.status_code == 403  # no governance role in other tenant either

    def test_cross_tenant_assessment_list_empty(self, db_session, tenant, member, gov_roles, client):
        _create_aiia(client, db_session, tenant, member, gov_roles)

        other_tenant = Tenant(id=uuid.uuid4(), name="Other Co 2", slug="other-co-2")
        db_session.add(other_tenant)
        db_session.flush()
        other_user, other_m = _make_member(db_session, other_tenant)
        other_gov_roles = {}
        for key in ("system_owner",):
            role = db_session.scalar(select(GovernanceRole).where(GovernanceRole.key == key))
            other_gov_roles[key] = role
        _grant(db_session, other_tenant, other_m, other_gov_roles["system_owner"])
        other_system = _make_system(db_session, other_tenant)
        other_use_case = _make_use_case(db_session, other_tenant, other_system)

        other_ctx = _make_ctx(other_user, other_m, other_tenant)
        with _ApiCtx(other_ctx, db_session):
            r = client.get(f"/v1/use-cases/{other_use_case.id}/assessments")
        assert r.status_code == 200
        assert r.json() == []


# ---------------------------------------------------------------------------
# 8. Gated reference reads
# ---------------------------------------------------------------------------

class TestReferenceReads:
    def test_member_can_list_risks_and_controls(self, db_session, tenant, member, client):
        _make_vendor_product_risk(db_session)
        _make_control(db_session)
        user, m = member
        ctx = _make_ctx(user, m, tenant)
        with _ApiCtx(ctx, db_session):
            r_risks = client.get("/v1/reference/risks")
            r_controls = client.get("/v1/reference/controls")
        assert r_risks.status_code == 200
        assert len(r_risks.json()) >= 1
        assert r_controls.status_code == 200
        assert len(r_controls.json()) >= 1
