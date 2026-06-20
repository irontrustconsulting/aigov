"""
Tests for system/portfolio rollup (sprints/SPRINT_LIFECYCLE.md WI-8).
"""

from __future__ import annotations

import uuid

from app.models.base import EUAIActTier, LifecycleState
from app.services.classification import ClassificationProposal, snapshot_classification
from app.services.lifecycle_service import portfolio_rollup, system_rollup
from tests.lifecycle_helpers import (  # noqa: F401
    _ApiCtx,
    _grant,
    _make_ctx,
    _make_system,
    _make_use_case,
    gov_roles,
    member,
    tenant,
)


def _bridge_proposal(tier: EUAIActTier) -> ClassificationProposal:
    return ClassificationProposal(
        tier=tier,
        subcategory_code="TEST-CODE",
        subcategory_name="Test",
        legal_ref=None,
        rationale="test rationale",
    )


class TestSystemRollup:
    def test_highest_tier_is_python_max_over_precedence(
        self,
        db_session,
        tenant,
        member,
    ):
        user, _ = member
        system = _make_system(db_session, tenant)
        uc_minimal = _make_use_case(db_session, tenant, system)
        snapshot_classification(
            uc_minimal,
            _bridge_proposal(EUAIActTier.MINIMAL),
            db_session,
            actor_user_id=user.id,
        )
        uc_high = _make_use_case(db_session, tenant, system)
        snapshot_classification(
            uc_high,
            _bridge_proposal(EUAIActTier.HIGH),
            db_session,
            actor_user_id=user.id,
        )

        rollup = system_rollup(db_session, tenant.id, system)
        assert rollup.use_case_count == 2
        assert rollup.highest_tier == EUAIActTier.HIGH

    def test_no_use_cases_highest_tier_none(self, db_session, tenant):
        system = _make_system(db_session, tenant)
        rollup = system_rollup(db_session, tenant.id, system)
        assert rollup.use_case_count == 0
        assert rollup.highest_tier is None
        assert rollup.use_cases == []

    def test_blocking_obligation_per_use_case(self, db_session, tenant, member):
        user, _ = member
        system = _make_system(db_session, tenant)
        use_case = _make_use_case(db_session, tenant, system)
        snapshot_classification(
            use_case,
            _bridge_proposal(EUAIActTier.HIGH),
            db_session,
            actor_user_id=user.id,
        )
        assert use_case.state == LifecycleState.UNDER_ASSESSMENT

        rollup = system_rollup(db_session, tenant.id, system)
        entry = rollup.use_cases[0]
        assert entry.use_case_id == use_case.id
        assert entry.state == LifecycleState.UNDER_ASSESSMENT
        assert entry.blocking is not None
        assert entry.blocking.reason_code == "no_aiia"


class TestPortfolioRollup:
    def test_portfolio_lists_only_systems_with_use_cases(
        self,
        db_session,
        tenant,
        member,
    ):
        user, _ = member
        system_with_use_case = _make_system(db_session, tenant)
        _make_use_case(db_session, tenant, system_with_use_case)
        _make_system(db_session, tenant)  # no use cases — excluded

        rollup = portfolio_rollup(db_session, tenant.id)
        assert len(rollup) == 1
        assert rollup[0].system_id == system_with_use_case.id

    def test_portfolio_endpoint_any_governance_role(
        self,
        client,
        db_session,
        tenant,
        member,
        gov_roles,
    ):
        user, m = member
        _grant(db_session, tenant, m, gov_roles["auditor"])  # read-only role
        system = _make_system(db_session, tenant)
        _make_use_case(db_session, tenant, system)

        ctx = _make_ctx(user, m, tenant)
        with _ApiCtx(ctx, db_session):
            r = client.get("/v1/portfolio")
        assert r.status_code == 200
        body = r.json()
        assert len(body) == 1
        assert body[0]["system_id"] == str(system.id)

    def test_rollup_endpoint_404_unknown_system(
        self,
        client,
        db_session,
        tenant,
        member,
        gov_roles,
    ):
        user, m = member
        _grant(db_session, tenant, m, gov_roles["auditor"])
        ctx = _make_ctx(user, m, tenant)
        with _ApiCtx(ctx, db_session):
            r = client.get(f"/v1/systems/{uuid.uuid4()}/rollup")
        assert r.status_code == 404
