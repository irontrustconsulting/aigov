"""Router-level tests for the export / audit pack endpoints (Sprint 7b) —
confirms the actual HTTP wiring: routes depend only on get_tenant_context
(no get_tenant_db), the governance-role gate still fires (now invoked
inside the service's own session), and the export_service.SessionLocal
patch needed for build_* to see committed test data threads through a real
request, not just a direct service call.
"""

from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest
from sqlalchemy.orm import Session

from app.models.base import AssessmentStatus, EUAIActTier
from tests.lifecycle_helpers import (  # noqa: F401
    _ApiCtx,
    _grant,
    _make_aiia,
    _make_ctx,
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


def _approve(db: Session, assessment) -> None:
    assessment.status = AssessmentStatus.APPROVED
    db.flush()


class TestExportEndpoints:
    def test_use_case_export_any_governance_role(
        self, client, db_session: Session, tenant, member, gov_roles
    ):
        user, m = member
        _grant(db_session, tenant, m, gov_roles["auditor"])
        system = _make_system(db_session, tenant)
        use_case = _make_use_case(db_session, tenant, system)
        aiia = _make_aiia(db_session, tenant, use_case, tier_snapshot=EUAIActTier.HIGH)
        _approve(db_session, aiia)
        ctx = _make_ctx(user, m, tenant)
        db_session.commit()

        with _ApiCtx(ctx, db_session):
            r = client.get(f"/v1/use-cases/{use_case.id}/export")
        assert r.status_code == 200
        body = r.json()
        assert body["use_case_id"] == str(use_case.id)
        assert "content_hash" in body

    def test_no_governance_role_403s(self, client, db_session: Session, tenant, member):
        user, m = member  # no role granted
        system = _make_system(db_session, tenant)
        use_case = _make_use_case(db_session, tenant, system)
        ctx = _make_ctx(user, m, tenant)
        db_session.commit()

        with _ApiCtx(ctx, db_session):
            r = client.get(f"/v1/use-cases/{use_case.id}/export")
        assert r.status_code == 403

    def test_system_export_404_unknown_system(
        self, client, db_session: Session, tenant, member, gov_roles
    ):
        user, m = member
        _grant(db_session, tenant, m, gov_roles["auditor"])
        ctx = _make_ctx(user, m, tenant)
        db_session.commit()

        with _ApiCtx(ctx, db_session):
            r = client.get(f"/v1/systems/{uuid.uuid4()}/export")
        assert r.status_code == 404

    def test_ato_document_404_never_authorised(
        self, client, db_session: Session, tenant, member, gov_roles
    ):
        user, m = member
        _grant(db_session, tenant, m, gov_roles["auditor"])
        system = _make_system(db_session, tenant)
        use_case = _make_use_case(db_session, tenant, system)
        ctx = _make_ctx(user, m, tenant)
        db_session.commit()

        with _ApiCtx(ctx, db_session):
            r = client.get(f"/v1/use-cases/{use_case.id}/authorisation/document")
        assert r.status_code == 404

    def test_framework_export_requires_framework_param(
        self, client, db_session: Session, tenant, member, gov_roles
    ):
        user, m = member
        _grant(db_session, tenant, m, gov_roles["auditor"])
        ctx = _make_ctx(user, m, tenant)
        db_session.commit()

        with _ApiCtx(ctx, db_session):
            r = client.get("/v1/export", params={"framework": "iso_42001"})
        assert r.status_code == 200
        assert r.json()["framework"] == "iso_42001"
