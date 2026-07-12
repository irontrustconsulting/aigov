"""
Tests for the clearance-queue read endpoint + service (UI-F10-CLEARANCE,
WI-1) — GET /v1/clearance-queue and clearance_queue().
"""

from __future__ import annotations

import uuid

import pytest

from app.models.base import ApprovalStatus, EUAIActTier, LifecycleState
from app.models.identity import Tenant
from app.services.classification import ClassificationProposal, snapshot_classification
from app.services.lifecycle_service import clearance_queue
from tests.lifecycle_helpers import (  # noqa: F401
    _ApiCtx,
    _grant,
    _make_ctx,
    _make_member,
    _make_product,
    _make_system,
    _make_use_case,
    _make_vendor,
    _make_vendor_approval,
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


class TestClearanceQueueService:
    def test_vendor_not_started_appears_with_awaiting_count(
        self, db_session, tenant, member,
    ):
        user, _ = member
        vendor = _make_vendor(db_session)
        system = _make_system(db_session, tenant, vendor=vendor)
        use_case = _make_use_case(db_session, tenant, system)
        snapshot_classification(
            use_case, _bridge_proposal(EUAIActTier.HIGH), db_session,
            actor_user_id=user.id,
        )
        assert use_case.state == LifecycleState.VENDOR_CHECK

        result = clearance_queue(db_session, tenant.id)
        assert len(result.vendors) == 1
        entry = result.vendors[0]
        assert entry.catalogue_vendor_id == vendor.id
        assert entry.status == ApprovalStatus.NOT_STARTED
        assert entry.awaiting_use_case_count == 1

    def test_affected_count_exceeds_awaiting_when_some_use_cases_have_moved_on(
        self, db_session, tenant, member,
    ):
        user, _ = member
        vendor = _make_vendor(db_session)
        system_awaiting = _make_system(db_session, tenant, vendor=vendor)
        system_halted = _make_system(db_session, tenant, vendor=vendor)

        uc_awaiting = _make_use_case(db_session, tenant, system_awaiting)
        snapshot_classification(
            uc_awaiting, _bridge_proposal(EUAIActTier.HIGH), db_session,
            actor_user_id=user.id,
        )
        assert uc_awaiting.state == LifecycleState.VENDOR_CHECK

        # A use case that resolves PROHIBITED halts immediately, off the
        # vendor_check gate entirely — still on a vendor-linked system, so it
        # counts toward the fan-out (affected) set but not the awaiting set.
        uc_halted = _make_use_case(db_session, tenant, system_halted)
        snapshot_classification(
            uc_halted, _bridge_proposal(EUAIActTier.PROHIBITED), db_session,
            actor_user_id=user.id,
        )
        assert uc_halted.state == LifecycleState.HALTED_PROHIBITED

        entry = clearance_queue(db_session, tenant.id).vendors[0]
        assert entry.awaiting_use_case_count == 1
        assert entry.affected_use_case_count == 2
        assert entry.affected_use_case_count > entry.awaiting_use_case_count
        assert entry.affected_system_count == 2

    def test_product_vendor_cleared_true_when_vendor_approved(
        self, db_session, tenant, member,
    ):
        user, _ = member
        vendor = _make_vendor(db_session)
        product = _make_product(db_session, vendor)
        system = _make_system(db_session, tenant, product, vendor=vendor)
        use_case = _make_use_case(db_session, tenant, system)
        _make_vendor_approval(db_session, tenant, vendor, status=ApprovalStatus.APPROVED)

        snapshot_classification(
            use_case, _bridge_proposal(EUAIActTier.HIGH), db_session,
            actor_user_id=user.id,
        )
        assert use_case.state == LifecycleState.PRODUCT_CHECK

        result = clearance_queue(db_session, tenant.id)
        vendor_entry = next(v for v in result.vendors if v.catalogue_vendor_id == vendor.id)
        assert vendor_entry.status == ApprovalStatus.APPROVED
        product_entry = next(
            p for p in vendor_entry.products if p.catalogue_product_id == product.id
        )
        assert product_entry.vendor_cleared is True
        assert product_entry.awaiting_use_case_count == 1

    def test_product_vendor_cleared_false_when_vendor_not_approved(
        self, db_session, tenant, member,
    ):
        user, _ = member
        vendor = _make_vendor(db_session)
        product = _make_product(db_session, vendor)
        system = _make_system(db_session, tenant, product, vendor=vendor)
        use_case = _make_use_case(db_session, tenant, system)

        snapshot_classification(
            use_case, _bridge_proposal(EUAIActTier.HIGH), db_session,
            actor_user_id=user.id,
        )
        assert use_case.state == LifecycleState.VENDOR_CHECK

        vendor_entry = clearance_queue(db_session, tenant.id).vendors[0]
        # Vendor itself not yet cleared -> its products are nested inert,
        # each carrying vendor_cleared=False regardless of their own status.
        product_entry = next(
            p for p in vendor_entry.products if p.catalogue_product_id == product.id
        )
        assert product_entry.vendor_cleared is False

    def test_clearance_queue_is_tenant_isolated(self, db_session, tenant, member):
        user, _ = member
        other_tenant = Tenant(id=uuid.uuid4(), name="Other Co", slug="other-co")
        db_session.add(other_tenant)
        db_session.flush()
        other_user, _ = _make_member(db_session, other_tenant)

        vendor = _make_vendor(db_session)
        other_system = _make_system(db_session, other_tenant, vendor=vendor)
        other_use_case = _make_use_case(db_session, other_tenant, other_system)
        snapshot_classification(
            other_use_case, _bridge_proposal(EUAIActTier.HIGH), db_session,
            actor_user_id=other_user.id,
        )
        assert other_use_case.state == LifecycleState.VENDOR_CHECK

        assert clearance_queue(db_session, tenant.id).vendors == []


class TestClearanceQueueEndpoint:
    @pytest.mark.parametrize(
        "role_key",
        ["system_owner", "contributor", "reviewer", "authoriser", "auditor"],
    )
    def test_each_governance_role_receives_200(
        self, client, db_session, tenant, member, gov_roles, role_key,
    ):
        user, m = member
        _grant(db_session, tenant, m, gov_roles[role_key])
        system = _make_system(db_session, tenant)
        _make_use_case(db_session, tenant, system)

        ctx = _make_ctx(user, m, tenant)
        with _ApiCtx(ctx, db_session):
            r = client.get("/v1/clearance-queue")
        assert r.status_code == 200

    def test_admin_zero_governance_roles_receives_403(
        self, client, db_session, tenant, member,
    ):
        user, m = member  # plain MEMBER, no governance grant
        ctx = _make_ctx(user, m, tenant)
        with _ApiCtx(ctx, db_session):
            r = client.get("/v1/clearance-queue")
        assert r.status_code == 403
