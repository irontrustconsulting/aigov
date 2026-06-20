"""
Tests for vendor/product approval set/update + fan-out (sprints/
SPRINT_LIFECYCLE.md WI-7, §8 "approvals / fan-out" and "authz / tenancy").
"""

from __future__ import annotations

import uuid
from unittest.mock import patch

from sqlalchemy import select

from app.models.base import ApprovalStatus, EUAIActTier, LifecycleState
from app.models.domain import VendorApproval
from app.models.lifecycle import AuditEvent
from app.services.classification import ClassificationProposal, snapshot_classification
from app.services.lifecycle_service import (
    fan_out_product_approval,
    fan_out_vendor_approval,
    set_product_approval,
    set_vendor_approval,
)
from tests.lifecycle_helpers import (  # noqa: F401
    _ApiCtx,
    _grant,
    _make_ctx,
    _make_member,
    _make_product,
    _make_system,
    _make_use_case,
    _make_vendor,
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


class TestSetVendorApprovalFanOut:
    def test_set_approval_advances_waiting_use_case(
        self,
        client,
        db_session,
        _test_session_factory,
        tenant,
        member,
        gov_roles,
    ):
        user, m = member
        _grant(db_session, tenant, m, gov_roles["authoriser"])
        _grant(db_session, tenant, m, gov_roles["system_owner"])
        vendor = _make_vendor(db_session)
        product = _make_product(db_session, vendor)
        system = _make_system(db_session, tenant, product, vendor=vendor)
        use_case = _make_use_case(db_session, tenant, system)

        snapshot_classification(
            use_case,
            _bridge_proposal(EUAIActTier.HIGH),
            db_session,
            actor_user_id=user.id,
        )
        assert use_case.state == LifecycleState.VENDOR_CHECK  # parked, no approvals

        ctx = _make_ctx(user, m, tenant)
        with (
            patch("app.services.lifecycle_service.SessionLocal", _test_session_factory),
            _ApiCtx(ctx, db_session),
        ):
            r = client.put(
                f"/v1/vendors/{vendor.id}/approval",
                json={"status": "approved"},
            )
        assert r.status_code == 200

        db_session.refresh(use_case)
        # Vendor cleared, product still not — parked one gate further on.
        assert use_case.state == LifecycleState.PRODUCT_CHECK

        approval = db_session.scalar(
            select(VendorApproval).where(
                VendorApproval.catalogue_vendor_id == vendor.id
            )
        )
        assert approval.status == ApprovalStatus.APPROVED
        assert approval.decided_by_user_id == user.id

        audit = db_session.scalar(
            select(AuditEvent).where(AuditEvent.entity_id == approval.id)
        )
        assert audit.action == "vendor_approval.set"

    def test_revoke_regresses_advanced_use_case_to_held(
        self,
        db_session,
        _test_session_factory,
        tenant,
        member,
    ):
        user, _ = member
        vendor = _make_vendor(db_session)
        product = _make_product(db_session, vendor)
        system = _make_system(db_session, tenant, product, vendor=vendor)
        use_case = _make_use_case(db_session, tenant, system)

        # Classify FIRST, before any clearance exists, so use_case advances
        # entirely within db_session (no separate-session writes land on a
        # use case db_session still holds an in-memory reference to —
        # apply_transition's from-state guard would otherwise 409 against
        # the now-stale in-memory object, exactly like a real concurrent
        # writer would).
        snapshot_classification(
            use_case,
            _bridge_proposal(EUAIActTier.HIGH),
            db_session,
            actor_user_id=user.id,
        )
        assert use_case.state == LifecycleState.VENDOR_CHECK

        with patch(
            "app.services.lifecycle_service.SessionLocal",
            _test_session_factory,
        ):
            set_vendor_approval(
                db_session,
                tenant.id,
                vendor.id,
                approval_status=ApprovalStatus.APPROVED,
                valid_until=None,
                note=None,
                actor_user_id=user.id,
            )
            fan_out_vendor_approval(db_session, tenant.id, vendor.id, user.id)
            set_product_approval(
                db_session,
                tenant.id,
                product.id,
                approval_status=ApprovalStatus.APPROVED,
                valid_until=None,
                note=None,
                actor_user_id=user.id,
            )
            fan_out_product_approval(db_session, tenant.id, product.id, user.id)

        db_session.refresh(use_case)
        assert use_case.state == LifecycleState.UNDER_ASSESSMENT

        # Revoke the vendor clearance -> fan out -> the advanced use case
        # regresses to held.
        with patch(
            "app.services.lifecycle_service.SessionLocal",
            _test_session_factory,
        ):
            set_vendor_approval(
                db_session,
                tenant.id,
                vendor.id,
                approval_status=ApprovalStatus.REJECTED,
                valid_until=None,
                note="revoked",
                actor_user_id=user.id,
            )
            fan_out_vendor_approval(db_session, tenant.id, vendor.id, user.id)

        db_session.refresh(use_case)
        assert use_case.state == LifecycleState.HELD
        assert use_case.held_from_state == LifecycleState.UNDER_ASSESSMENT

    def test_fan_out_is_idempotent(
        self,
        db_session,
        _test_session_factory,
        tenant,
        member,
    ):
        user, _ = member
        vendor = _make_vendor(db_session)
        product = _make_product(db_session, vendor)
        system = _make_system(db_session, tenant, product, vendor=vendor)
        use_case = _make_use_case(db_session, tenant, system)
        snapshot_classification(
            use_case,
            _bridge_proposal(EUAIActTier.HIGH),
            db_session,
            actor_user_id=user.id,
        )

        with patch(
            "app.services.lifecycle_service.SessionLocal",
            _test_session_factory,
        ):
            set_vendor_approval(
                db_session,
                tenant.id,
                vendor.id,
                approval_status=ApprovalStatus.APPROVED,
                valid_until=None,
                note=None,
                actor_user_id=user.id,
            )
            fan_out_vendor_approval(db_session, tenant.id, vendor.id, user.id)

        db_session.refresh(use_case)
        state_after_first = use_case.state

        # Re-running the fan-out with nothing changed must be a no-op.
        with patch(
            "app.services.lifecycle_service.SessionLocal",
            _test_session_factory,
        ):
            fan_out_vendor_approval(db_session, tenant.id, vendor.id, user.id)

        db_session.refresh(use_case)
        assert use_case.state == state_after_first

    def test_update_existing_approval_stages_updated_action(
        self,
        db_session,
        _test_session_factory,
        tenant,
        member,
    ):
        user, _ = member
        vendor = _make_vendor(db_session)

        with patch(
            "app.services.lifecycle_service.SessionLocal",
            _test_session_factory,
        ):
            first = set_vendor_approval(
                db_session,
                tenant.id,
                vendor.id,
                approval_status=ApprovalStatus.UNDER_REVIEW,
                valid_until=None,
                note=None,
                actor_user_id=user.id,
            )
            second = set_vendor_approval(
                db_session,
                tenant.id,
                vendor.id,
                approval_status=ApprovalStatus.APPROVED,
                valid_until=None,
                note="cleared",
                actor_user_id=user.id,
            )
        assert first.id == second.id  # same row, updated in place

        actions = list(
            db_session.scalars(
                select(AuditEvent.action)
                .where(AuditEvent.entity_id == first.id)
                .order_by(AuditEvent.id)
            )
        )
        assert "vendor_approval.set" in actions
        assert "vendor_approval.updated" in actions


class TestAuthzAndTenancy:
    def test_non_authoriser_403(
        self,
        client,
        db_session,
        tenant,
        member,
    ):
        user, m = member  # plain MEMBER, no governance grant
        vendor = _make_vendor(db_session)

        ctx = _make_ctx(user, m, tenant)
        with _ApiCtx(ctx, db_session):
            r = client.put(
                f"/v1/vendors/{vendor.id}/approval",
                json={"status": "approved"},
            )
        assert r.status_code == 403

    def test_unknown_vendor_404(
        self,
        client,
        db_session,
        tenant,
        member,
        gov_roles,
    ):
        user, m = member
        _grant(db_session, tenant, m, gov_roles["authoriser"])
        ctx = _make_ctx(user, m, tenant)
        with _ApiCtx(ctx, db_session):
            r = client.put(
                f"/v1/vendors/{uuid.uuid4()}/approval",
                json={"status": "approved"},
            )
        assert r.status_code == 404

    def test_approvals_are_tenant_isolated(
        self,
        db_session,
        _test_session_factory,
        tenant,
        member,
    ):
        """tenant_id always comes from ctx, never the request body — two
        tenants approving the SAME vendor get independent rows; one cannot
        see or affect the other's clearance."""
        from app.models.identity import Tenant

        user, _ = member
        other_tenant = Tenant(id=uuid.uuid4(), name="Other Co", slug="other-co")
        db_session.add(other_tenant)
        db_session.flush()
        other_user, _ = _make_member(db_session, other_tenant)

        vendor = _make_vendor(db_session)  # global catalogue row, shared

        with patch(
            "app.services.lifecycle_service.SessionLocal",
            _test_session_factory,
        ):
            set_vendor_approval(
                db_session,
                tenant.id,
                vendor.id,
                approval_status=ApprovalStatus.APPROVED,
                valid_until=None,
                note=None,
                actor_user_id=user.id,
            )
            fan_out_vendor_approval(db_session, tenant.id, vendor.id, user.id)

        # The other tenant's clearance of the SAME vendor is independent —
        # still absent.
        other_approval = db_session.scalar(
            select(VendorApproval).where(
                VendorApproval.tenant_id == other_tenant.id,
                VendorApproval.catalogue_vendor_id == vendor.id,
            )
        )
        assert other_approval is None

        mine = db_session.scalar(
            select(VendorApproval).where(
                VendorApproval.tenant_id == tenant.id,
                VendorApproval.catalogue_vendor_id == vendor.id,
            )
        )
        assert mine is not None
        assert mine.status == ApprovalStatus.APPROVED
