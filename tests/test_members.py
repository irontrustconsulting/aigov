"""
Tests for the tenant-admin member creation sprint.

Coverage (mirrors §12 of the sprint):
  AC-1  Admin creates member -> 201; membership created, UserRole.MEMBER,
        zero governance roles; audit event staged.
  AC-2  Created member can immediately receive a governance role.
  AC-3  Non-admin -> 403.
  AC-4  Email already a member of this tenant (pre-check) -> 409.
  AC-5  Email already a Cognito user (UsernameExistsException) -> 409.
  AC-6  Cognito failure -> nothing persisted (no orphan app_user/membership).
  AC-7  Commit failure after Cognito -> delete_cognito_user called, error
        surfaced, no half-created member.
  AC-8  tenant_id written to membership matches ctx.tenant_id (RLS contract).
  AC-9  Member listing returns only caller's tenant members; status="pending"
        until Cognito confirmation, then "accepted".
  AC-10 tenant_id from context, not body; body cannot override scope.

Session strategy
----------------
provision_member opens its own SessionLocal(), separate from the request-scoped
db_session used by the router overrides. We patch
app.services.member_provisioning.SessionLocal -> _test_session_factory so its
commits land in the test DB and are cleaned up by the post-test TRUNCATE.
The member_client fixture adds this patch on top of the base client.

DB verification after provision_member commits uses a fresh session from
_test_session_factory (not db_session, which is a different session object
and may not reflect committed rows without expire_all).

Cognito is never called. create_cognito_user and delete_cognito_user are patched
per-test. get_cognito_user_status is patched where needed.
"""

from __future__ import annotations

import uuid
from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.context import TenantContext, get_tenant_context, get_tenant_db
from app.main import app
from app.models.base import UserRole
from app.models.governance import GovernanceRole, GovernanceRoleAssignment
from app.models.identity import Membership, Tenant, User
from app.models.lifecycle import AuditEvent

_FAKE_SUB = "fake-cognito-sub-member-001"
_MEMBER_EMAIL = "newmember@acme.test"
_MEMBER_NAME = "New Member"

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tenant(db_session: Session) -> Tenant:
    t = Tenant(id=uuid.uuid4(), name="Acme Corp", slug="acme")
    db_session.add(t)
    # Commit so provision_member's separate session can see this tenant via FK.
    db_session.commit()
    return t


@pytest.fixture
def tenant_b(db_session: Session) -> Tenant:
    t = Tenant(id=uuid.uuid4(), name="Rival Corp", slug="rival")
    db_session.add(t)
    db_session.commit()
    return t


def _make_member(
    db: Session, tenant: Tenant, role: UserRole = UserRole.MEMBER
) -> tuple[User, Membership]:
    u = User(
        id=uuid.uuid4(),
        cognito_sub=f"sub-{uuid.uuid4()}",
        email=f"{uuid.uuid4()}@test.local",
    )
    m = Membership(id=uuid.uuid4(), user_id=u.id, tenant_id=tenant.id, role=role)
    db.add_all([u, m])
    db.commit()
    return u, m


@pytest.fixture
def admin(db_session: Session, tenant: Tenant) -> tuple[User, Membership]:
    return _make_member(db_session, tenant, UserRole.ADMIN)


def _ctx_override(ctx: TenantContext):
    def _dep():
        return ctx
    return _dep


def _db_override(session: Session):
    def _dep() -> Generator[Session, None, None]:
        yield session
        session.flush()
    return _dep


@pytest.fixture
def member_client(client, _test_session_factory):
    """client with provision_member's SessionLocal patched to the test factory."""
    with patch(
        "app.services.member_provisioning.SessionLocal",
        _test_session_factory,
    ):
        yield client


def _admin_ctx(admin_tuple, tenant: Tenant) -> TenantContext:
    user, membership = admin_tuple
    return TenantContext(
        user_id=user.id,
        membership_id=membership.id,
        tenant_id=tenant.id,
        role="admin",
    )


def _member_ctx(member_tuple, tenant: Tenant) -> TenantContext:
    user, membership = member_tuple
    return TenantContext(
        user_id=user.id,
        membership_id=membership.id,
        tenant_id=tenant.id,
        role="member",
    )


# ---------------------------------------------------------------------------
# Helpers for verifying DB state after provision_member commits its own session
# ---------------------------------------------------------------------------

def _fresh_session(factory):
    """Return a plain (non-context-manager) session from the factory."""
    return factory()


# ---------------------------------------------------------------------------
# AC-1: Success path
# ---------------------------------------------------------------------------

class TestCreateMemberSuccess:
    def test_admin_creates_member_returns_201(
        self, member_client, db_session, _test_session_factory, tenant, admin
    ):
        ctx = _admin_ctx(admin, tenant)
        app.dependency_overrides[get_tenant_context] = _ctx_override(ctx)
        app.dependency_overrides[get_tenant_db] = _db_override(db_session)

        with patch(
            "app.services.member_provisioning.create_cognito_user",
            return_value=_FAKE_SUB,
        ):
            try:
                r = member_client.post("/v1/members", json={
                    "email": _MEMBER_EMAIL,
                    "name": _MEMBER_NAME,
                })
            finally:
                app.dependency_overrides.pop(get_tenant_context, None)
                app.dependency_overrides.pop(get_tenant_db, None)

        assert r.status_code == 201
        body = r.json()
        assert "user_id" in body
        assert "membership_id" in body
        assert body["status"] == "pending"

        # Verify DB: membership exists, role=MEMBER, no governance roles
        verify = _fresh_session(_test_session_factory)
        try:
            membership_id = uuid.UUID(body["membership_id"])
            membership = verify.get(Membership, membership_id)
            assert membership is not None
            assert membership.role == UserRole.MEMBER
            assert membership.tenant_id == tenant.id  # AC-8 implicit check

            user_id = uuid.UUID(body["user_id"])
            user = verify.get(User, user_id)
            assert user is not None
            assert user.cognito_sub == _FAKE_SUB
            assert user.email == _MEMBER_EMAIL

            gov_assignments = list(verify.scalars(
                select(GovernanceRoleAssignment).where(
                    GovernanceRoleAssignment.membership_id == membership_id
                )
            ))
            assert gov_assignments == [], "New member must have zero governance roles"

            # AC-1: tenant-plane audit event
            audit = verify.scalar(
                select(AuditEvent).where(
                    AuditEvent.action == "member.created",
                    AuditEvent.tenant_id == tenant.id,
                )
            )
            assert audit is not None
            assert audit.entity_type == "membership"
            assert audit.entity_id == membership_id
        finally:
            verify.close()

    def test_ac8_tenant_id_in_membership_matches_context(
        self, member_client, db_session, _test_session_factory, tenant, admin
    ):
        """AC-8: tenant_id written to membership must equal the admin's tenant_id."""
        ctx = _admin_ctx(admin, tenant)
        app.dependency_overrides[get_tenant_context] = _ctx_override(ctx)
        app.dependency_overrides[get_tenant_db] = _db_override(db_session)

        with patch(
            "app.services.member_provisioning.create_cognito_user",
            return_value=_FAKE_SUB,
        ):
            try:
                r = member_client.post("/v1/members", json={
                    "email": _MEMBER_EMAIL,
                    "name": _MEMBER_NAME,
                })
            finally:
                app.dependency_overrides.pop(get_tenant_context, None)
                app.dependency_overrides.pop(get_tenant_db, None)

        assert r.status_code == 201
        verify = _fresh_session(_test_session_factory)
        try:
            membership = verify.get(Membership, uuid.UUID(r.json()["membership_id"]))
            assert membership.tenant_id == tenant.id
        finally:
            verify.close()


# ---------------------------------------------------------------------------
# AC-2: Governance role can be assigned immediately after member creation
# ---------------------------------------------------------------------------

class TestAC2GovernanceHandoff:
    def test_can_assign_governance_role_to_new_member(
        self, member_client, db_session, _test_session_factory, tenant, admin
    ):
        # Seed a governance role in the test DB.
        gov_role = GovernanceRole(
            id=uuid.uuid4(), key="reviewer", name="Reviewer", line_of_defence=2
        )
        db_session.add(gov_role)
        db_session.flush()

        ctx = _admin_ctx(admin, tenant)
        app.dependency_overrides[get_tenant_context] = _ctx_override(ctx)
        app.dependency_overrides[get_tenant_db] = _db_override(db_session)

        with patch(
            "app.services.member_provisioning.create_cognito_user",
            return_value=_FAKE_SUB,
        ):
            try:
                r = member_client.post("/v1/members", json={
                    "email": _MEMBER_EMAIL,
                    "name": _MEMBER_NAME,
                })
            finally:
                app.dependency_overrides.pop(get_tenant_context, None)
                app.dependency_overrides.pop(get_tenant_db, None)

        assert r.status_code == 201
        new_membership_id = r.json()["membership_id"]

        # Now assign a governance role via the existing endpoint.
        app.dependency_overrides[get_tenant_context] = _ctx_override(ctx)
        app.dependency_overrides[get_tenant_db] = _db_override(db_session)
        try:
            r2 = member_client.post("/v1/governance-roles/assignments", json={
                "membership_id": new_membership_id,
                "governance_role_id": str(gov_role.id),
            })
        finally:
            app.dependency_overrides.pop(get_tenant_context, None)
            app.dependency_overrides.pop(get_tenant_db, None)

        assert r2.status_code == 201


# ---------------------------------------------------------------------------
# AC-3: Non-admin -> 403
# ---------------------------------------------------------------------------

class TestAC3NonAdminForbidden:
    def test_member_cannot_create_member(
        self, member_client, db_session, tenant, admin
    ):
        plain_user, plain_membership = _make_member(db_session, tenant, UserRole.MEMBER)
        ctx = TenantContext(
            user_id=plain_user.id,
            membership_id=plain_membership.id,
            tenant_id=tenant.id,
            role="member",
        )
        app.dependency_overrides[get_tenant_context] = _ctx_override(ctx)
        app.dependency_overrides[get_tenant_db] = _db_override(db_session)
        try:
            r = member_client.post("/v1/members", json={
                "email": _MEMBER_EMAIL,
                "name": _MEMBER_NAME,
            })
        finally:
            app.dependency_overrides.pop(get_tenant_context, None)
            app.dependency_overrides.pop(get_tenant_db, None)

        assert r.status_code == 403


# ---------------------------------------------------------------------------
# AC-4: Email already a member of this tenant -> 409 (pre-check)
# ---------------------------------------------------------------------------

class TestAC4DuplicateMemberPrecheck:
    def test_existing_member_email_returns_409(
        self, member_client, db_session, _test_session_factory, tenant, admin
    ):
        # Seed an existing member with the target email.
        # Must commit so provision_member's pre-check session can see it.
        existing_user = User(
            id=uuid.uuid4(),
            cognito_sub="existing-sub",
            email=_MEMBER_EMAIL,
        )
        existing_membership = Membership(
            id=uuid.uuid4(),
            user_id=existing_user.id,
            tenant_id=tenant.id,
            role=UserRole.MEMBER,
        )
        db_session.add_all([existing_user, existing_membership])
        db_session.commit()

        ctx = _admin_ctx(admin, tenant)
        app.dependency_overrides[get_tenant_context] = _ctx_override(ctx)
        app.dependency_overrides[get_tenant_db] = _db_override(db_session)

        with patch(
            "app.services.member_provisioning.create_cognito_user",
            return_value=_FAKE_SUB,
        ) as mock_cognito:
            try:
                r = member_client.post("/v1/members", json={
                    "email": _MEMBER_EMAIL,
                    "name": _MEMBER_NAME,
                })
            finally:
                app.dependency_overrides.pop(get_tenant_context, None)
                app.dependency_overrides.pop(get_tenant_db, None)

        assert r.status_code == 409
        # Cognito must NOT have been called — pre-check fired first.
        mock_cognito.assert_not_called()


# ---------------------------------------------------------------------------
# AC-5: Email already in Cognito (UsernameExistsException) -> 409
# ---------------------------------------------------------------------------

class TestAC5CognitoUserExists:
    def test_cognito_username_exists_returns_409(
        self, member_client, db_session, _test_session_factory, tenant, admin
    ):
        ctx = _admin_ctx(admin, tenant)
        app.dependency_overrides[get_tenant_context] = _ctx_override(ctx)
        app.dependency_overrides[get_tenant_db] = _db_override(db_session)

        cognito_error = ClientError(
            {"Error": {"Code": "UsernameExistsException", "Message": "exists"}},
            "AdminCreateUser",
        )

        with patch(
            "app.services.member_provisioning.create_cognito_user",
            side_effect=cognito_error,
        ):
            try:
                r = member_client.post("/v1/members", json={
                    "email": _MEMBER_EMAIL,
                    "name": _MEMBER_NAME,
                })
            finally:
                app.dependency_overrides.pop(get_tenant_context, None)
                app.dependency_overrides.pop(get_tenant_db, None)

        assert r.status_code == 409

        # Verify no orphan rows were persisted.
        verify = _fresh_session(_test_session_factory)
        try:
            user = verify.scalar(select(User).where(User.email == _MEMBER_EMAIL))
            assert user is None, "No app_user row should be persisted"
        finally:
            verify.close()


# ---------------------------------------------------------------------------
# AC-6: Cognito failure -> nothing persisted
# ---------------------------------------------------------------------------

class TestAC6CognitoFailNothingPersisted:
    def test_generic_cognito_error_nothing_persisted(
        self, member_client, db_session, _test_session_factory, tenant, admin
    ):
        ctx = _admin_ctx(admin, tenant)
        app.dependency_overrides[get_tenant_context] = _ctx_override(ctx)
        app.dependency_overrides[get_tenant_db] = _db_override(db_session)

        cognito_error = ClientError(
            {"Error": {"Code": "InternalErrorException", "Message": "boom"}},
            "AdminCreateUser",
        )

        with patch(
            "app.services.member_provisioning.create_cognito_user",
            side_effect=cognito_error,
        ):
            try:
                r = member_client.post("/v1/members", json={
                    "email": _MEMBER_EMAIL,
                    "name": _MEMBER_NAME,
                })
            finally:
                app.dependency_overrides.pop(get_tenant_context, None)
                app.dependency_overrides.pop(get_tenant_db, None)

        assert r.status_code == 500

        verify = _fresh_session(_test_session_factory)
        try:
            user = verify.scalar(select(User).where(User.email == _MEMBER_EMAIL))
            assert user is None, "Cognito failure must leave no orphan app_user"
            memberships = list(verify.scalars(
                select(Membership).where(Membership.tenant_id == tenant.id)
            ))
            # Only pre-existing memberships (the admin's) should exist.
            assert len(memberships) == 1
        finally:
            verify.close()


# ---------------------------------------------------------------------------
# AC-7: Commit failure after Cognito -> delete_cognito_user called, error
#        surfaced, no half-created member.
# ---------------------------------------------------------------------------

class TestAC7CommitFailure:
    def test_commit_failure_triggers_cognito_compensation(
        self, _test_session_factory, tenant
    ):
        """Service-level unit test. Bypasses HTTP to control the exact commit.

        Strategy: patch SessionLocal to return a session whose commit method
        raises, while all other methods (begin, execute, add, flush) delegate
        to the real session. This lets provision_member reach the commit step
        before failing.

        The `tenant` fixture already commits the tenant row, so provision_member's
        session can satisfy the FK when inserting the membership.
        """
        real_session = _test_session_factory()
        mock_session = MagicMock(wraps=real_session)
        mock_session.commit.side_effect = RuntimeError("simulated commit failure")

        def _failing_factory():
            return mock_session

        from app.services.member_provisioning import provision_member
        from app.services.provisioning import AlreadyProvisioned, ProvisioningError

        with (
            patch("app.services.member_provisioning.SessionLocal", _failing_factory),
            patch(
                "app.services.member_provisioning.create_cognito_user",
                return_value=_FAKE_SUB,
            ),
            patch(
                "app.services.member_provisioning.delete_cognito_user"
            ) as mock_delete,
        ):
            with pytest.raises(RuntimeError, match="simulated commit failure"):
                provision_member(
                    tenant_id=tenant.id,
                    email=_MEMBER_EMAIL,
                    name=_MEMBER_NAME,
                    actor_user_id=uuid.uuid4(),
                    source="test",
                )

        mock_delete.assert_called_once_with(_MEMBER_EMAIL)
        real_session.close()


# ---------------------------------------------------------------------------
# AC-9: Member listing — membership-driven, status derived from Cognito
# ---------------------------------------------------------------------------

class TestAC9MemberListing:
    def test_lists_only_caller_tenant_members(
        self, member_client, db_session, tenant, tenant_b, admin
    ):
        # Two members in tenant A, one member in tenant B.
        user_a1, m_a1 = _make_member(db_session, tenant)
        _user_a2, _m_a2 = _make_member(db_session, tenant)
        _user_b, _m_b = _make_member(db_session, tenant_b)

        ctx = _admin_ctx(admin, tenant)
        app.dependency_overrides[get_tenant_context] = _ctx_override(ctx)
        app.dependency_overrides[get_tenant_db] = _db_override(db_session)

        # Cognito returns FORCE_CHANGE_PASSWORD -> "pending" for all.
        with patch(
            "app.routers.v1.members.get_cognito_user_status",
            return_value="FORCE_CHANGE_PASSWORD",
        ):
            try:
                r = member_client.get("/v1/members")
            finally:
                app.dependency_overrides.pop(get_tenant_context, None)
                app.dependency_overrides.pop(get_tenant_db, None)

        assert r.status_code == 200
        body = r.json()
        # Expect admin + 2 members = 3 rows, all in tenant A.
        assert len(body["items"]) == 3
        tenant_ids_in_response = {
            item["membership_id"]
            for item in body["items"]
        }
        # None should be from tenant_b.
        tenant_b_membership_id = str(_m_b.id)
        assert tenant_b_membership_id not in tenant_ids_in_response

    def test_status_pending_for_force_change_password(
        self, member_client, db_session, tenant, admin
    ):
        _make_member(db_session, tenant)  # one additional member

        ctx = _admin_ctx(admin, tenant)
        app.dependency_overrides[get_tenant_context] = _ctx_override(ctx)
        app.dependency_overrides[get_tenant_db] = _db_override(db_session)

        with patch(
            "app.routers.v1.members.get_cognito_user_status",
            return_value="FORCE_CHANGE_PASSWORD",
        ):
            try:
                r = member_client.get("/v1/members")
            finally:
                app.dependency_overrides.pop(get_tenant_context, None)
                app.dependency_overrides.pop(get_tenant_db, None)

        assert r.status_code == 200
        for item in r.json()["items"]:
            assert item["status"] == "pending"

    def test_status_accepted_for_confirmed_user(
        self, member_client, db_session, tenant, admin
    ):
        _make_member(db_session, tenant)

        ctx = _admin_ctx(admin, tenant)
        app.dependency_overrides[get_tenant_context] = _ctx_override(ctx)
        app.dependency_overrides[get_tenant_db] = _db_override(db_session)

        with patch(
            "app.routers.v1.members.get_cognito_user_status",
            return_value="CONFIRMED",
        ):
            try:
                r = member_client.get("/v1/members")
            finally:
                app.dependency_overrides.pop(get_tenant_context, None)
                app.dependency_overrides.pop(get_tenant_db, None)

        assert r.status_code == 200
        for item in r.json()["items"]:
            assert item["status"] == "accepted"

    def test_non_admin_cannot_list_members(
        self, member_client, db_session, tenant, admin
    ):
        plain_user, plain_membership = _make_member(db_session, tenant, UserRole.MEMBER)
        ctx = TenantContext(
            user_id=plain_user.id,
            membership_id=plain_membership.id,
            tenant_id=tenant.id,
            role="member",
        )
        app.dependency_overrides[get_tenant_context] = _ctx_override(ctx)
        app.dependency_overrides[get_tenant_db] = _db_override(db_session)
        try:
            r = member_client.get("/v1/members")
        finally:
            app.dependency_overrides.pop(get_tenant_context, None)
            app.dependency_overrides.pop(get_tenant_db, None)

        assert r.status_code == 403


# ---------------------------------------------------------------------------
# AC-10: tenant_id always from context, never the body
# ---------------------------------------------------------------------------

class TestAC10TenantIdFromContext:
    def test_body_cannot_override_tenant(
        self, member_client, db_session, _test_session_factory, tenant, tenant_b, admin
    ):
        """Endpoint has no tenant_id field in the body; anything extra is ignored."""
        ctx = _admin_ctx(admin, tenant)
        app.dependency_overrides[get_tenant_context] = _ctx_override(ctx)
        app.dependency_overrides[get_tenant_db] = _db_override(db_session)

        with patch(
            "app.services.member_provisioning.create_cognito_user",
            return_value=_FAKE_SUB,
        ):
            try:
                # Pass a body that includes a different tenant_id — it should be silently ignored.
                r = member_client.post("/v1/members", json={
                    "email": _MEMBER_EMAIL,
                    "name": _MEMBER_NAME,
                    "tenant_id": str(tenant_b.id),  # extra field, not on MemberCreate
                })
            finally:
                app.dependency_overrides.pop(get_tenant_context, None)
                app.dependency_overrides.pop(get_tenant_db, None)

        assert r.status_code == 201

        verify = _fresh_session(_test_session_factory)
        try:
            membership = verify.get(Membership, uuid.UUID(r.json()["membership_id"]))
            assert membership.tenant_id == tenant.id, (
                "Membership must be in admin's tenant, not the body-supplied tenant_id"
            )
            assert membership.tenant_id != tenant_b.id
        finally:
            verify.close()
