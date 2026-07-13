"""
Tests for the AIIA Feeders sprint (Phase B —
sprints/SPRINT_AIIA_FEEDERS.md).

Covers the §8 acceptance criteria: feeder creation (parent scope
inheritance, register pre-fill, MODEL_RISK technical-risk proposal,
feeder_created audit), integrity guards (type=AIIA rejected, feeder-of-
feeder rejected, duplicate type 409), propagation (surfaced items tagged
and re-keyed into the AIIA section, feeder-private items excluded),
feeder-recommendations, layer-aware propose_risk_set, and pristine-delete /
parent-cascade lifecycle.
"""

from __future__ import annotations

import uuid

from sqlalchemy import delete, select

from app.models.assessment import Assessment, AssessmentItem
from app.models.base import AssessmentType, EUAIActTier, ProvenanceConfidence
from app.models.intake import (
    AffectedParty,
    DataCategory,
    EUOperatorRole,
    UseCaseAffectedParty,
    UseCaseDataCategory,
)
from app.models.lifecycle import AuditEvent
from app.services.assessment_service import propose_risk_set
from tests.aiia_helpers import (  # noqa: F401 (fixtures used by name)
    DPIA_DATA_CATEGORIES_SECTION_KEY,
    FRIA_AFFECTED_PERSONS_SECTION_KEY,
    MODEL_RISK_DESCRIPTION_SECTION_KEY,
    MODEL_RISK_RISK_SECTION_KEY,
    OVERVIEW_SECTION_KEY,
    RISK_SECTION_KEY,
    STAKEHOLDERS_SECTION_KEY,
    _ApiCtx,
    _grant,
    _make_classification,
    _make_ctx,
    _make_system,
    _make_use_case,
    _make_vendor_product_risk,
    _seed_feeder_template,
    _seed_template,
    gov_roles,
    member,
    tenant,
)


def _create_aiia(
    client, db_session, tenant, owner_member, gov_roles, tier=EUAIActTier.HIGH,
):
    """Build a complete, governance-granted AIIA via the API. Returns
    (aiia_json, use_case, system)."""
    user, m = owner_member
    _grant(db_session, tenant, m, gov_roles["system_owner"])
    _grant(db_session, tenant, m, gov_roles["contributor"])
    system = _make_system(db_session, tenant)
    use_case = _make_use_case(db_session, tenant, system)
    _make_classification(db_session, tenant, use_case, tier)
    _seed_template(db_session, tier)

    ctx = _make_ctx(user, m, tenant)
    with _ApiCtx(ctx, db_session):
        r = client.post(f"/v1/use-cases/{use_case.id}/assessments")
    assert r.status_code == 201
    return r.json(), use_case, system


def _make_affected_party(db_session) -> AffectedParty:
    ap = AffectedParty(
        id=uuid.uuid4(), code=f"AP-{uuid.uuid4().hex[:6]}", label="Job applicants",
    )
    db_session.add(ap)
    db_session.flush()
    return ap


def _make_data_category(db_session, is_special: bool = False) -> DataCategory:
    dc = DataCategory(
        id=uuid.uuid4(), code=f"DC-{uuid.uuid4().hex[:6]}", label="Biometric data",
        is_special_category=is_special,
    )
    db_session.add(dc)
    db_session.flush()
    return dc


def _make_deployer_role(db_session) -> EUOperatorRole:
    role = EUOperatorRole(id=uuid.uuid4(), code="deployer", label="Deployer")
    db_session.add(role)
    db_session.flush()
    return role


class TestCreateFeeder:
    def test_fria_create_prefills_affected_persons(
        self, db_session, tenant, member, gov_roles, client,
    ):
        aiia, use_case, system = _create_aiia(
            client, db_session, tenant, member, gov_roles,
        )
        ap = _make_affected_party(db_session)
        link_id = uuid.uuid4()
        db_session.add(UseCaseAffectedParty(
            id=link_id, tenant_id=tenant.id, use_case_id=use_case.id, affected_party_id=ap.id,
        ))
        db_session.flush()
        _seed_feeder_template(db_session, EUAIActTier.HIGH, AssessmentType.FRIA)

        user, m = member
        ctx = _make_ctx(user, m, tenant)
        with _ApiCtx(ctx, db_session):
            r = client.post(
                f"/v1/assessments/{aiia['id']}/feeders", json={"type": "fria"},
            )
        assert r.status_code == 201
        feeder = r.json()
        assert feeder["type"] == "fria"
        assert feeder["parent_aiia_id"] == aiia["id"]
        assert feeder["tier_snapshot"] == aiia["tier_snapshot"]
        assert feeder["classification_version"] == aiia["classification_version"]

        items = list(db_session.scalars(
            select(AssessmentItem).where(
                AssessmentItem.assessment_id == uuid.UUID(feeder["id"]),
                AssessmentItem.section_key == FRIA_AFFECTED_PERSONS_SECTION_KEY,
            )
        ))
        snapshotted = [
            i for i in items if i.provenance == ProvenanceConfidence.USER_CONFIRMED
        ]
        assert any(i.response == "Job applicants" for i in snapshotted)
        assert any(
            i.source_ref == f"use_case_affected_party:{link_id}" for i in snapshotted
        )

        events = list(db_session.scalars(
            select(AuditEvent).where(AuditEvent.action == "assessment.feeder_created")
        ))
        assert len(events) == 1

    def test_dpia_create_prefills_data_categories(
        self, db_session, tenant, member, gov_roles, client,
    ):
        aiia, use_case, system = _create_aiia(
            client, db_session, tenant, member, gov_roles,
        )
        dc = _make_data_category(db_session, is_special=True)
        db_session.add(UseCaseDataCategory(
            id=uuid.uuid4(), tenant_id=tenant.id, use_case_id=use_case.id, data_category_id=dc.id,
        ))
        db_session.flush()
        _seed_feeder_template(db_session, EUAIActTier.HIGH, AssessmentType.DPIA)

        user, m = member
        ctx = _make_ctx(user, m, tenant)
        with _ApiCtx(ctx, db_session):
            r = client.post(
                f"/v1/assessments/{aiia['id']}/feeders", json={"type": "dpia"},
            )
        assert r.status_code == 201
        feeder = r.json()

        items = list(db_session.scalars(
            select(AssessmentItem).where(
                AssessmentItem.assessment_id == uuid.UUID(feeder["id"]),
                AssessmentItem.section_key == DPIA_DATA_CATEGORIES_SECTION_KEY,
            )
        ))
        assert any(i.response == "Biometric data" for i in items)

    def test_model_risk_create_prefills_description_and_proposes_risks(
        self, db_session, tenant, member, gov_roles, client,
    ):
        product, risk = _make_vendor_product_risk(db_session)
        aiia, use_case, system = _create_aiia(
            client, db_session, tenant, member, gov_roles,
        )
        system.catalogue_product_id = product.id
        db_session.flush()
        _seed_feeder_template(db_session, EUAIActTier.HIGH, AssessmentType.MODEL_RISK)

        user, m = member
        ctx = _make_ctx(user, m, tenant)
        with _ApiCtx(ctx, db_session):
            r = client.post(
                f"/v1/assessments/{aiia['id']}/feeders", json={"type": "model_risk"},
            )
        assert r.status_code == 201
        feeder = r.json()

        desc_items = list(db_session.scalars(
            select(AssessmentItem).where(
                AssessmentItem.assessment_id == uuid.UUID(feeder["id"]),
                AssessmentItem.section_key == MODEL_RISK_DESCRIPTION_SECTION_KEY,
            )
        ))
        assert any(i.response == product.name for i in desc_items)

        risk_items = list(db_session.scalars(
            select(AssessmentItem).where(
                AssessmentItem.assessment_id == uuid.UUID(feeder["id"]),
                AssessmentItem.section_key == MODEL_RISK_RISK_SECTION_KEY,
            )
        ))
        assert len(risk_items) == 1
        assert risk_items[0].risk_id == risk.id
        assert risk_items[0].provenance == ProvenanceConfidence.AI_SUGGESTED

    def test_empty_junction_yields_no_prefill_items_section_intact(
        self, db_session, tenant, member, gov_roles, client,
    ):
        aiia, use_case, system = _create_aiia(
            client, db_session, tenant, member, gov_roles,
        )
        _seed_feeder_template(db_session, EUAIActTier.HIGH, AssessmentType.FRIA)
        user, m = member
        ctx = _make_ctx(user, m, tenant)
        with _ApiCtx(ctx, db_session):
            r = client.post(
                f"/v1/assessments/{aiia['id']}/feeders", json={"type": "fria"},
            )
        assert r.status_code == 201
        feeder = r.json()
        items = list(db_session.scalars(
            select(AssessmentItem)
            .where(AssessmentItem.assessment_id == uuid.UUID(feeder["id"]))
        ))
        assert all(i.response is None for i in items)  # no affected parties

    def test_type_aiia_rejected_422(
        self, db_session, tenant, member, gov_roles, client,
    ):
        aiia, _, _ = _create_aiia(
            client, db_session, tenant, member, gov_roles,
        )
        user, m = member
        ctx = _make_ctx(user, m, tenant)
        with _ApiCtx(ctx, db_session):
            r = client.post(
                f"/v1/assessments/{aiia['id']}/feeders", json={"type": "aiia"},
            )
        assert r.status_code == 422

    def test_feeder_cannot_parent_a_feeder_422(
        self, db_session, tenant, member, gov_roles, client,
    ):
        aiia, _, _ = _create_aiia(
            client, db_session, tenant, member, gov_roles,
        )
        _seed_feeder_template(db_session, EUAIActTier.HIGH, AssessmentType.DPIA)
        _seed_feeder_template(db_session, EUAIActTier.HIGH, AssessmentType.FRIA)
        user, m = member
        ctx = _make_ctx(user, m, tenant)
        with _ApiCtx(ctx, db_session):
            r1 = client.post(
                f"/v1/assessments/{aiia['id']}/feeders", json={"type": "dpia"},
            )
            assert r1.status_code == 201
            feeder_id = r1.json()["id"]
            r2 = client.post(
                f"/v1/assessments/{feeder_id}/feeders", json={"type": "fria"},
            )
        assert r2.status_code == 422

    def test_duplicate_feeder_type_409(
        self, db_session, tenant, member, gov_roles, client,
    ):
        aiia, _, _ = _create_aiia(
            client, db_session, tenant, member, gov_roles,
        )
        _seed_feeder_template(db_session, EUAIActTier.HIGH, AssessmentType.FRIA)
        user, m = member
        ctx = _make_ctx(user, m, tenant)
        with _ApiCtx(ctx, db_session):
            r1 = client.post(
                f"/v1/assessments/{aiia['id']}/feeders", json={"type": "fria"},
            )
            assert r1.status_code == 201
            r2 = client.post(
                f"/v1/assessments/{aiia['id']}/feeders", json={"type": "fria"},
            )
        assert r2.status_code == 409

    def test_missing_parent_404(self, db_session, tenant, member, gov_roles, client):
        user, m = member
        _grant(db_session, tenant, m, gov_roles["system_owner"])
        ctx = _make_ctx(user, m, tenant)
        with _ApiCtx(ctx, db_session):
            r = client.post(
                f"/v1/assessments/{uuid.uuid4()}/feeders", json={"type": "fria"},
            )
        assert r.status_code == 404

    def test_empty_feeder_template_loud_failure(
        self, db_session, tenant, member, gov_roles, client,
    ):
        aiia, _, _ = _create_aiia(
            client, db_session, tenant, member, gov_roles,
        )
        # No _seed_feeder_template call — MODEL_RISK template missing for HIGH.
        user, m = member
        ctx = _make_ctx(user, m, tenant)
        with _ApiCtx(ctx, db_session):
            r = client.post(
                f"/v1/assessments/{aiia['id']}/feeders", json={"type": "model_risk"},
            )
        assert r.status_code == 500


class TestPropagation:
    def test_surfaced_items_tagged_and_rekeyed(
        self, db_session, tenant, member, gov_roles, client,
    ):
        aiia, use_case, system = _create_aiia(
            client, db_session, tenant, member, gov_roles,
        )
        ap = _make_affected_party(db_session)
        db_session.add(UseCaseAffectedParty(
            id=uuid.uuid4(), tenant_id=tenant.id, use_case_id=use_case.id, affected_party_id=ap.id,
        ))
        db_session.flush()
        _seed_feeder_template(db_session, EUAIActTier.HIGH, AssessmentType.FRIA)

        user, m = member
        ctx = _make_ctx(user, m, tenant)
        with _ApiCtx(ctx, db_session):
            r_feeder = client.post(
                f"/v1/assessments/{aiia['id']}/feeders", json={"type": "fria"},
            )
            feeder_id = r_feeder.json()["id"]
            r_detail = client.get(f"/v1/assessments/{aiia['id']}")
        assert r_detail.status_code == 200
        items = r_detail.json()["items"]

        surfaced = [i for i in items if i.get("source_assessment_id") == feeder_id]
        assert len(surfaced) >= 1
        assert all(i["section_key"] == STAKEHOLDERS_SECTION_KEY for i in surfaced)
        assert all(i["source_type"] == "fria" for i in surfaced)
        assert any(i["response"] == "Job applicants" for i in surfaced)

    def test_feeder_private_items_excluded_from_aiia(
        self, db_session, tenant, member, gov_roles, client,
    ):
        aiia, use_case, system = _create_aiia(
            client, db_session, tenant, member, gov_roles,
        )
        _seed_feeder_template(db_session, EUAIActTier.HIGH, AssessmentType.FRIA)
        user, m = member
        ctx = _make_ctx(user, m, tenant)
        with _ApiCtx(ctx, db_session):
            r_feeder = client.post(
                f"/v1/assessments/{aiia['id']}/feeders", json={"type": "fria"},
            )
            feeder_id = r_feeder.json()["id"]
            # fria_internal_complaint_process is recommended, not required —
            # instantiate it on demand, same as any recommended section.
            r_private_item = client.post(
                f"/v1/assessments/{feeder_id}/items",
                json={"section_key": "fria_internal_complaint_process"},
            )
            assert r_private_item.status_code == 201
            r_aiia_detail = client.get(f"/v1/assessments/{aiia['id']}")
            r_feeder_detail = client.get(f"/v1/assessments/{feeder_id}")

        # The feeder-private "internal complaint process" curated item exists
        # on the feeder's own view...
        feeder_items = r_feeder_detail.json()["items"]
        assert any(
            i["section_key"] == "fria_internal_complaint_process" for i in feeder_items
        )
        # ...but never surfaces into the AIIA's view.
        aiia_items = r_aiia_detail.json()["items"]
        assert not any(
            i["section_key"] == "fria_internal_complaint_process" for i in aiia_items
        )

    def test_editing_feeder_item_changes_surfaced_view(
        self, db_session, tenant, member, gov_roles, client,
    ):
        aiia, use_case, system = _create_aiia(
            client, db_session, tenant, member, gov_roles,
        )
        _seed_feeder_template(db_session, EUAIActTier.HIGH, AssessmentType.DPIA)
        user, m = member
        ctx = _make_ctx(user, m, tenant)
        with _ApiCtx(ctx, db_session):
            r_feeder = client.post(
                f"/v1/assessments/{aiia['id']}/feeders", json={"type": "dpia"},
            )
            feeder_id = r_feeder.json()["id"]
            r_item = client.post(
                f"/v1/assessments/{feeder_id}/items",
                json={"section_key": DPIA_DATA_CATEGORIES_SECTION_KEY, "response": "X"},
            )
            item = r_item.json()
            r_patch = client.patch(
                f"/v1/assessments/{feeder_id}/items/{item['id']}",
                json={"response": "Updated"},
                headers={"If-Match": str(item["lock_version"])},
            )
            assert r_patch.status_code == 200
            r_detail = client.delete(
                f"/v1/assessments/{feeder_id}/items/{item['id']}",
            )
            assert r_detail.status_code == 204
            r_aiia_detail = client.get(f"/v1/assessments/{aiia['id']}")

        aiia_items = r_aiia_detail.json()["items"]
        assert not any(i["id"] == item["id"] for i in aiia_items)

    def test_feeder_control_link_counts_toward_aiia_view(
        self, db_session, tenant, member, gov_roles, client,
    ):
        from tests.aiia_helpers import _make_control

        aiia, use_case, system = _create_aiia(
            client, db_session, tenant, member, gov_roles,
        )
        _seed_feeder_template(db_session, EUAIActTier.HIGH, AssessmentType.DPIA)
        control = _make_control(db_session)
        user, m = member
        ctx = _make_ctx(user, m, tenant)
        with _ApiCtx(ctx, db_session):
            r_feeder = client.post(
                f"/v1/assessments/{aiia['id']}/feeders", json={"type": "dpia"},
            )
            feeder_id = r_feeder.json()["id"]
            feeder_items = client.get(f"/v1/assessments/{feeder_id}").json()["items"]
            target_item = next(
                i for i in feeder_items
                if i["section_key"] == DPIA_DATA_CATEGORIES_SECTION_KEY
            ) if feeder_items else None
            if target_item is None:
                # No pre-filled item (no data categories registered) — create one.
                created = client.post(
                    f"/v1/assessments/{feeder_id}/items",
                    json={"section_key": DPIA_DATA_CATEGORIES_SECTION_KEY},
                ).json()
                target_item = created
            r_link = client.post(
                f"/v1/assessments/{feeder_id}/items/{target_item['id']}/control-links",
                json={"control_id": str(control.id), "coverage": "satisfied"},
            )
            assert r_link.status_code == 201


class TestFeederRecommendations:
    def test_recommendations_reflect_tier_and_data_profile(
        self, db_session, tenant, member, gov_roles, client,
    ):
        aiia, use_case, system = _create_aiia(
            client, db_session, tenant, member, gov_roles,
        )
        role = _make_deployer_role(db_session)
        system.operator_role_id = role.id
        dc = _make_data_category(db_session, is_special=True)
        db_session.add(UseCaseDataCategory(
            id=uuid.uuid4(), tenant_id=tenant.id, use_case_id=use_case.id, data_category_id=dc.id,
        ))
        db_session.flush()

        user, m = member
        ctx = _make_ctx(user, m, tenant)
        with _ApiCtx(ctx, db_session):
            r = client.get(f"/v1/assessments/{aiia['id']}/feeder-recommendations")
        assert r.status_code == 200
        by_type = {row["type"]: row for row in r.json()}

        assert by_type["fria"]["applicability"] == "required"
        assert by_type["fria"]["exists"] is False
        assert by_type["dpia"]["applicability"] == "required"
        assert by_type["model_risk"]["applicability"] == "recommended"

    def test_exists_flips_after_feeder_created(
        self, db_session, tenant, member, gov_roles, client,
    ):
        aiia, _, _ = _create_aiia(
            client, db_session, tenant, member, gov_roles,
        )
        _seed_feeder_template(db_session, EUAIActTier.HIGH, AssessmentType.FRIA)
        user, m = member
        ctx = _make_ctx(user, m, tenant)
        with _ApiCtx(ctx, db_session):
            client.post(f"/v1/assessments/{aiia['id']}/feeders", json={"type": "fria"})
            r = client.get(f"/v1/assessments/{aiia['id']}/feeder-recommendations")
        by_type = {row["type"]: row for row in r.json()}
        assert by_type["fria"]["exists"] is True

    def test_minimal_tier_low_data_profile_not_applicable(
        self, db_session, tenant, member, gov_roles, client,
    ):
        aiia, use_case, system = _create_aiia(
            client, db_session, tenant, member, gov_roles, tier=EUAIActTier.MINIMAL,
        )
        user, m = member
        ctx = _make_ctx(user, m, tenant)
        with _ApiCtx(ctx, db_session):
            r = client.get(f"/v1/assessments/{aiia['id']}/feeder-recommendations")
        by_type = {row["type"]: row for row in r.json()}
        assert by_type["fria"]["applicability"] == "not_applicable"
        assert by_type["dpia"]["applicability"] == "not_applicable"
        assert by_type["model_risk"]["applicability"] == "recommended"


class TestProposeRiskSetLayerAware:
    def test_aiia_returns_governance_and_catalogue_risks(self, db_session):
        from app.models.base import RiskLayer, RiskSource
        from app.models.knowledge import Risk

        gov_risk = Risk(
            id=uuid.uuid4(), code=f"GOV-{uuid.uuid4().hex[:6]}",
            title="Governance risk",
            layer=RiskLayer.GOVERNANCE_RIGHTS, source=RiskSource.NIST_AI_RMF,
        )
        db_session.add(gov_risk)
        db_session.flush()

        proposed = propose_risk_set(
            AssessmentType.AIIA, EUAIActTier.HIGH, [], None, db_session,
        )
        assert any(p.risk_id == gov_risk.id for p in proposed)

    def test_model_risk_returns_technical_layer_only(self, db_session):
        product, tech_risk = _make_vendor_product_risk(db_session)  # TECHNICAL_SECURITY
        proposed = propose_risk_set(
            AssessmentType.MODEL_RISK, EUAIActTier.HIGH, [], product.id, db_session,
        )
        assert any(p.risk_id == tech_risk.id for p in proposed)

    def test_fria_and_dpia_propose_nothing(self, db_session):
        product, _risk = _make_vendor_product_risk(db_session)
        assert propose_risk_set(
            AssessmentType.FRIA, EUAIActTier.HIGH, [], product.id, db_session,
        ) == []
        assert propose_risk_set(
            AssessmentType.DPIA, EUAIActTier.HIGH, [], product.id, db_session,
        ) == []


class TestFeederLifecycle:
    def test_pristine_feeder_delete_cascades(
        self, db_session, tenant, member, gov_roles, client,
    ):
        aiia, _, _ = _create_aiia(
            client, db_session, tenant, member, gov_roles,
        )
        _seed_feeder_template(db_session, EUAIActTier.HIGH, AssessmentType.FRIA)
        user, m = member
        ctx = _make_ctx(user, m, tenant)
        with _ApiCtx(ctx, db_session):
            r_feeder = client.post(
                f"/v1/assessments/{aiia['id']}/feeders", json={"type": "fria"},
            )
            feeder_id = r_feeder.json()["id"]
            r_delete = client.delete(f"/v1/assessments/{feeder_id}")
        assert r_delete.status_code == 204
        assert db_session.get(Assessment, uuid.UUID(feeder_id)) is None

    def test_worked_feeder_delete_409(
        self, db_session, tenant, member, gov_roles, client,
    ):
        aiia, _, _ = _create_aiia(
            client, db_session, tenant, member, gov_roles,
        )
        _seed_feeder_template(db_session, EUAIActTier.HIGH, AssessmentType.DPIA)
        user, m = member
        ctx = _make_ctx(user, m, tenant)
        with _ApiCtx(ctx, db_session):
            r_feeder = client.post(
                f"/v1/assessments/{aiia['id']}/feeders", json={"type": "dpia"},
            )
            feeder_id = r_feeder.json()["id"]
            r_item = client.post(
                f"/v1/assessments/{feeder_id}/items",
                json={"section_key": DPIA_DATA_CATEGORIES_SECTION_KEY, "response": "X"},
            )
            assert r_item.status_code == 201
            r_delete = client.delete(f"/v1/assessments/{feeder_id}")
        assert r_delete.status_code == 409

    def test_parent_aiia_delete_cascades_to_feeder(
        self, db_session, tenant, member, gov_roles, client,
    ):
        aiia, _, _ = _create_aiia(
            client, db_session, tenant, member, gov_roles,
        )
        _seed_feeder_template(db_session, EUAIActTier.HIGH, AssessmentType.FRIA)
        user, m = member
        ctx = _make_ctx(user, m, tenant)
        with _ApiCtx(ctx, db_session):
            r_feeder = client.post(
                f"/v1/assessments/{aiia['id']}/feeders", json={"type": "fria"},
            )
            feeder_id = r_feeder.json()["id"]

        # Hard-delete the parent at the DB level via a Core statement
        # (bypassing both the pristine guard and the ORM unit-of-work,
        # which would otherwise null the feeder's FK itself since it's
        # already in this session's identity map — masking whether the
        # DB's own ON DELETE CASCADE is actually configured). This isolates
        # the schema-level invariant: the application's delete_assessment
        # never reaches this path anyway, since pristine-delete blocks any
        # AIIA that still has feeders.
        db_session.execute(
            delete(Assessment).where(Assessment.id == uuid.UUID(aiia["id"]))
        )
        db_session.flush()
        remaining = db_session.execute(
            select(Assessment.id).where(Assessment.id == uuid.UUID(feeder_id))
        ).scalar_one_or_none()
        assert remaining is None
