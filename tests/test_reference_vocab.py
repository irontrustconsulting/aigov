"""
Tests for the UI-F1-INTAKE WI-0 backend addition: list routes for the six
intake-vocab tables (app/models/intake.py) that previously had no GET route
— only FK-validation against them on SystemCreate/SystemUpdate. These back
the wizard's WI-5 structured selects.

Covers: each route returns only active=true rows, ordered by sort_order,
gated to any tenant member (mirrors list_risks/list_controls).
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.orm import Session

from app.models.identity import Tenant
from app.models.intake import (
    AffectedParty,
    DataCategory,
    EUOperatorRole,
    HostingModel,
    HumanOversightType,
    UsageContext,
)
from tests.aiia_helpers import _ApiCtx, _make_ctx, member, tenant  # noqa: F401


def _add(db: Session, cls, *, code: str, label: str, sort_order: int, active: bool, **extra):
    row = cls(id=uuid.uuid4(), code=code, label=label, sort_order=sort_order, active=active, **extra)
    db.add(row)
    return row


class TestVocabListRoutes:
    @pytest.mark.parametrize(
        "path,model,extra",
        [
            ("/v1/reference/operator-roles", EUOperatorRole, {}),
            ("/v1/reference/hosting-models", HostingModel, {}),
            ("/v1/reference/usage-contexts", UsageContext, {}),
            ("/v1/reference/human-oversight-types", HumanOversightType, {}),
            ("/v1/reference/data-categories", DataCategory, {"is_special_category": True}),
            ("/v1/reference/affected-parties", AffectedParty, {"is_vulnerable_group": True}),
        ],
    )
    def test_lists_only_active_rows_in_sort_order(
        self, db_session, tenant, member, client, path, model, extra,
    ):
        _add(db_session, model, code="z-row", label="Z Row", sort_order=1, active=True, **extra)
        _add(db_session, model, code="a-row", label="A Row", sort_order=0, active=True, **extra)
        _add(db_session, model, code="inactive-row", label="Inactive", sort_order=-1, active=False, **extra)
        db_session.flush()

        user, m = member
        ctx = _make_ctx(user, m, tenant)
        with _ApiCtx(ctx, db_session):
            r = client.get(path)

        assert r.status_code == 200
        body = r.json()
        assert [row["code"] for row in body] == ["a-row", "z-row"]
        for row in body:
            assert "id" in row and "code" in row and "label" in row

    def test_requires_tenant_membership(self, db_session, client, path="/v1/reference/operator-roles"):
        r = client.get(path)
        assert r.status_code in (401, 403)

    def test_data_categories_carry_special_flag(self, db_session, tenant, member, client):
        _add(db_session, DataCategory, code="health", label="Health data",
             sort_order=0, active=True, is_special_category=True)
        db_session.flush()
        user, m = member
        ctx = _make_ctx(user, m, tenant)
        with _ApiCtx(ctx, db_session):
            r = client.get("/v1/reference/data-categories")
        assert r.status_code == 200
        assert r.json()[0]["is_special_category"] is True

    def test_affected_parties_carry_vulnerable_flag(self, db_session, tenant, member, client):
        _add(db_session, AffectedParty, code="minors", label="Minors",
             sort_order=0, active=True, is_vulnerable_group=True)
        db_session.flush()
        user, m = member
        ctx = _make_ctx(user, m, tenant)
        with _ApiCtx(ctx, db_session):
            r = client.get("/v1/reference/affected-parties")
        assert r.status_code == 200
        assert r.json()[0]["is_vulnerable_group"] is True
