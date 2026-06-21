"""Router-level tests for the control coverage endpoints (Sprint 7a) — the
any-governance-role read gate, and the 404/422 scope-resolution status codes
surfacing correctly through HTTP."""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.models.base import (
    AssessmentStatus,
    AssessmentType,
    CoverageStatus,
    EUAIActTier,
)
from app.models.identity import Tenant
from tests.lifecycle_helpers import (  # noqa: F401
    _ApiCtx,
    _grant,
    _make_aiia,
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


class TestCoverageEndpoints:
    def test_tenant_coverage_any_governance_role(
        self, client, db_session: Session, tenant: Tenant, member, gov_roles
    ):
        user, m = member
        _grant(db_session, tenant, m, gov_roles["auditor"])
        system = _make_system(db_session, tenant)
        use_case = _make_use_case(db_session, tenant, system)
        aiia = _make_aiia(db_session, tenant, use_case, tier_snapshot=EUAIActTier.HIGH)
        aiia.status = AssessmentStatus.APPROVED
        db_session.flush()
        control = _make_control(db_session)
        item = _make_item(db_session, tenant, aiia)
        _make_control_link(
            db_session, tenant, item, control, coverage=CoverageStatus.SATISFIED
        )

        ctx = _make_ctx(user, m, tenant)
        with _ApiCtx(ctx, db_session):
            r = client.get("/v1/coverage")
        assert r.status_code == 200
        body = r.json()
        assert body["scope"] == "tenant"
        assert len(body["controls"]) == 1
        assert body["controls"][0]["verdict"] == "SATISFIED"

    def test_no_governance_role_403s(
        self, client, db_session: Session, tenant: Tenant, member
    ):
        user, m = member  # no governance role granted
        ctx = _make_ctx(user, m, tenant)
        with _ApiCtx(ctx, db_session):
            r = client.get("/v1/coverage")
        assert r.status_code == 403

    def test_system_coverage_404_unknown_system(
        self, client, db_session: Session, tenant: Tenant, member, gov_roles
    ):
        user, m = member
        _grant(db_session, tenant, m, gov_roles["auditor"])
        ctx = _make_ctx(user, m, tenant)
        with _ApiCtx(ctx, db_session):
            r = client.get(f"/v1/systems/{uuid.uuid4()}/coverage")
        assert r.status_code == 404

    def test_assessment_coverage_422_on_feeder_id(
        self, client, db_session: Session, tenant: Tenant, member, gov_roles
    ):
        user, m = member
        _grant(db_session, tenant, m, gov_roles["auditor"])
        system = _make_system(db_session, tenant)
        use_case = _make_use_case(db_session, tenant, system)
        aiia = _make_aiia(db_session, tenant, use_case, tier_snapshot=EUAIActTier.HIGH)
        feeder = _make_feeder(db_session, tenant, aiia, AssessmentType.FRIA)

        ctx = _make_ctx(user, m, tenant)
        with _ApiCtx(ctx, db_session):
            r = client.get(f"/v1/assessments/{feeder.id}/coverage")
        assert r.status_code == 422
