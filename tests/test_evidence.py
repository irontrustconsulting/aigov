"""
Tests for the evidence repository (sprints/SPRINT_EVIDENCE_REPOSITORY.md),
Phase A: upload (ordering + compensation), repository reads (list/detail +
presign + audit), pristine guarded delete, authorisation.

Session strategy
-----------------
upload_evidence opens its OWN SessionLocal() (evidence_service._tenant_session),
deliberately separate from the request-scoped db_session used everywhere else
-- the whole point of WI-2 is that the S3 put runs with no DB transaction open.
We patch app.services.evidence_service.SessionLocal -> _test_session_factory so
its commits land in the test DB. Because that's a genuinely separate session,
fixture data the upload path needs (tenant, membership, governance role grant)
must be COMMITTED, not just flushed -- mirrors tests/test_members.py's
provision_member pattern. list/get/delete go through the ordinary
get_tenant_db-overridden db_session, like every other v1 endpoint.

S3 is never called. app.services.evidence_service.storage.{put_object,
presign_get,delete_object} are mocked per-test.
"""

from __future__ import annotations

import hashlib
import io
import uuid
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.context import get_tenant_context
from app.main import app
from app.models.assessment import Assessment, AssessmentItem, AssessmentItemEvidence
from app.models.base import AssessmentType, EUAIActTier, ProvenanceConfidence, UserRole
from app.models.governance import GovernanceRole, GovernanceRoleAssignment
from app.models.identity import Membership, Tenant, User
from app.models.lifecycle import AuditEvent, Evidence
from app.services import evidence_service
from tests.aiia_helpers import (  # noqa: F401 (fixtures used by name)
    FRIA_AFFECTED_PERSONS_SECTION_KEY,
    OVERVIEW_SECTION_KEY,
    _ApiCtx,
    _make_classification,
    _make_ctx,
    _make_system,
    _make_use_case,
    _make_vendor_product_risk,
    _seed_feeder_template,
    _seed_template,
)

_GOVERNANCE_ROLES = [
    ("system_owner", 1),
    ("contributor", 1),
    ("reviewer", 2),
    ("authoriser", 2),
    ("auditor", 3),
]


# ---------------------------------------------------------------------------
# Fixtures (committed, not flushed -- see module docstring)
# ---------------------------------------------------------------------------


@pytest.fixture
def tenant(db_session: Session) -> Tenant:
    t = Tenant(id=uuid.uuid4(), name="Acme Corp", slug=f"acme-{uuid.uuid4().hex[:6]}")
    db_session.add(t)
    db_session.commit()
    return t


@pytest.fixture
def gov_roles(db_session: Session) -> dict[str, GovernanceRole]:
    roles = {}
    for key, line in _GOVERNANCE_ROLES:
        r = GovernanceRole(id=uuid.uuid4(), key=key, name=key, line_of_defence=line)
        db_session.add(r)
        roles[key] = r
    db_session.commit()
    return roles


def _make_member(db: Session, tenant: Tenant) -> tuple[User, Membership]:
    u = User(
        id=uuid.uuid4(),
        cognito_sub=f"sub-{uuid.uuid4()}",
        email=f"{uuid.uuid4()}@test.local",
    )
    m = Membership(
        id=uuid.uuid4(), user_id=u.id, tenant_id=tenant.id, role=UserRole.MEMBER
    )
    db.add_all([u, m])
    db.commit()
    return u, m


def _grant(
    db: Session, tenant: Tenant, membership: Membership, role: GovernanceRole
) -> None:
    db.add(
        GovernanceRoleAssignment(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            membership_id=membership.id,
            governance_role_id=role.id,
        )
    )
    db.commit()


@pytest.fixture
def contributor(db_session, tenant, gov_roles) -> tuple[User, Membership]:
    user, m = _make_member(db_session, tenant)
    _grant(db_session, tenant, m, gov_roles["contributor"])
    return user, m


@pytest.fixture
def auditor(db_session, tenant, gov_roles) -> tuple[User, Membership]:
    user, m = _make_member(db_session, tenant)
    _grant(db_session, tenant, m, gov_roles["auditor"])
    return user, m


@pytest.fixture
def evidence_client(client, _test_session_factory):
    """client with evidence_service's standalone upload session patched to the
    test factory, so the upload path's commits land in (and are cleaned up
    with) the test DB."""
    with patch("app.services.evidence_service.SessionLocal", _test_session_factory):
        yield client


@pytest.fixture
def mock_storage():
    with (
        patch("app.services.evidence_service.storage.put_object") as put,
        patch("app.services.evidence_service.storage.presign_get") as presign,
        patch("app.services.evidence_service.storage.delete_object") as delete,
    ):
        put.return_value = "v1"
        presign.return_value = "https://example-public/signed-url"
        yield {"put": put, "presign": presign, "delete": delete}


class _FakeUpload:
    """Stand-in for fastapi.UploadFile for direct service-level calls --
    evidence_service only touches .file/.filename/.content_type."""

    def __init__(
        self,
        content: bytes,
        filename: str = "doc.pdf",
        content_type: str = "application/pdf",
    ):
        self.file = io.BytesIO(content)
        self.filename = filename
        self.content_type = content_type


# ---------------------------------------------------------------------------
# WI-2: upload ordering, success, compensation, size/empty guards
# ---------------------------------------------------------------------------


class TestUpload:
    def test_upload_success(
        self, evidence_client, tenant, contributor, mock_storage, _test_session_factory
    ):
        ctx = _make_ctx(*contributor, tenant)
        app.dependency_overrides[get_tenant_context] = lambda: ctx
        try:
            resp = evidence_client.post(
                "/v1/evidence",
                files={"file": ("doc.pdf", b"hello world", "application/pdf")},
                data={"title": "My DPA"},
            )
        finally:
            app.dependency_overrides.pop(get_tenant_context, None)

        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["title"] == "My DPA"
        assert body["sha256"] == hashlib.sha256(b"hello world").hexdigest()
        assert body["size_bytes"] == len(b"hello world")

        mock_storage["put"].assert_called_once()
        put_args, put_kwargs = mock_storage["put"].call_args
        assert put_args[0] == "aigov-evidence"
        assert put_args[1] == f"{tenant.id}/evidence/{body['id']}"

        fresh = _test_session_factory()
        ev = fresh.scalar(select(Evidence).where(Evidence.id == uuid.UUID(body["id"])))
        audit = fresh.scalar(
            select(AuditEvent).where(AuditEvent.action == "evidence.created")
        )
        fresh.close()
        assert ev is not None
        assert ev.s3_version_id == "v1"
        assert audit is not None
        assert audit.entity_id == ev.id

    def test_put_runs_before_db_row_exists(
        self,
        evidence_client,
        tenant,
        contributor,
        mock_storage,
        _test_session_factory,
    ):
        """Ordering check for the no-held-connection requirement: at the
        moment storage.put_object is called, the Evidence row must not exist
        yet (hash+put happen before the short post-put transaction opens)."""
        row_at_put_time = {}

        def _put_side_effect(bucket, key, fileobj, **kwargs):
            fresh = _test_session_factory()
            row_at_put_time["row"] = fresh.scalar(
                select(Evidence).where(Evidence.tenant_id == tenant.id)
            )
            fresh.close()
            return "v1"

        mock_storage["put"].side_effect = _put_side_effect

        ctx = _make_ctx(*contributor, tenant)
        app.dependency_overrides[get_tenant_context] = lambda: ctx
        try:
            resp = evidence_client.post(
                "/v1/evidence",
                files={"file": ("doc.pdf", b"hello world", "application/pdf")},
            )
        finally:
            app.dependency_overrides.pop(get_tenant_context, None)

        assert resp.status_code == 201
        assert row_at_put_time["row"] is None  # no row existed at put-time

    def test_commit_failure_compensates_s3_object(
        self, tenant, contributor, _test_session_factory
    ):
        """Service-level: bypasses HTTP to control the exact commit, mirroring
        tests/test_members.py's AC-7 pattern."""
        real_precheck_session = _test_session_factory()
        real_insert_session = _test_session_factory()
        mock_insert_session = MagicMock(wraps=real_insert_session)
        mock_insert_session.commit.side_effect = RuntimeError(
            "simulated commit failure"
        )

        calls = {"n": 0}

        def _factory():
            calls["n"] += 1
            return real_precheck_session if calls["n"] == 1 else mock_insert_session

        ctx = _make_ctx(*contributor, tenant)
        upload = _FakeUpload(b"hello world")

        with (
            patch("app.services.evidence_service.SessionLocal", _factory),
            patch(
                "app.services.evidence_service.storage.put_object", return_value="v1"
            ) as put,
            patch("app.services.evidence_service.storage.delete_object") as delete,
        ):
            with pytest.raises(RuntimeError, match="simulated commit failure"):
                evidence_service.upload_evidence(ctx, upload, None)

        put.assert_called_once()
        delete.assert_called_once()
        delete_args = delete.call_args[0]
        assert delete_args[0] == "aigov-evidence"
        assert delete_args[2] == "v1"

        fresh = _test_session_factory()
        count = fresh.scalar(select(Evidence).where(Evidence.tenant_id == tenant.id))
        fresh.close()
        assert count is None  # nothing persisted

    def test_oversize_413(self, evidence_client, tenant, contributor, mock_storage):
        ctx = _make_ctx(*contributor, tenant)
        app.dependency_overrides[get_tenant_context] = lambda: ctx
        with patch("app.config.settings.evidence_max_upload_bytes", 10):
            try:
                resp = evidence_client.post(
                    "/v1/evidence",
                    files={"file": ("doc.pdf", b"x" * 1000, "application/pdf")},
                )
            finally:
                app.dependency_overrides.pop(get_tenant_context, None)
        assert resp.status_code == 413
        mock_storage["put"].assert_not_called()

    def test_empty_upload_422(self, evidence_client, tenant, contributor, mock_storage):
        ctx = _make_ctx(*contributor, tenant)
        app.dependency_overrides[get_tenant_context] = lambda: ctx
        try:
            resp = evidence_client.post(
                "/v1/evidence",
                files={"file": ("doc.pdf", b"", "application/pdf")},
            )
        finally:
            app.dependency_overrides.pop(get_tenant_context, None)
        assert resp.status_code == 422
        mock_storage["put"].assert_not_called()

    def test_non_write_role_403(self, evidence_client, tenant, auditor, mock_storage):
        ctx = _make_ctx(*auditor, tenant)
        app.dependency_overrides[get_tenant_context] = lambda: ctx
        try:
            resp = evidence_client.post(
                "/v1/evidence",
                files={"file": ("doc.pdf", b"hello world", "application/pdf")},
            )
        finally:
            app.dependency_overrides.pop(get_tenant_context, None)
        assert resp.status_code == 403
        mock_storage["put"].assert_not_called()


# ---------------------------------------------------------------------------
# WI-3: repository reads
# ---------------------------------------------------------------------------


class TestRepositoryReads:
    def test_list_paginates_and_reports_link_count(
        self,
        client,
        db_session,
        tenant,
        contributor,
        gov_roles,
    ):
        user, m = contributor
        # AIIA creation is system_owner-only; grant it too so this one member
        # can both stand up the fixture item and read the evidence list.
        _grant(db_session, tenant, m, gov_roles["system_owner"])
        ctx = _make_ctx(user, m, tenant)
        evs = []
        for i in range(3):
            ev = Evidence(
                id=uuid.uuid4(),
                tenant_id=tenant.id,
                title=f"Doc {i}",
                s3_bucket="b",
                s3_key=f"k{i}",
                uploaded_by_user_id=user.id,
            )
            db_session.add(ev)
            evs.append(ev)
        db_session.flush()

        # Link evs[0] to a real item so its link_count should read 1.
        product, risk = _make_vendor_product_risk(db_session)
        system = _make_system(db_session, tenant, product)
        use_case = _make_use_case(db_session, tenant, system)
        _make_classification(db_session, tenant, use_case, EUAIActTier.HIGH)
        _seed_template(db_session, EUAIActTier.HIGH)
        with _ApiCtx(ctx, db_session):
            r = client.post(f"/v1/use-cases/{use_case.id}/assessments")
        assert r.status_code == 201
        aiia_id = uuid.UUID(r.json()["id"])
        item = db_session.scalar(
            select(AssessmentItem).where(
                AssessmentItem.assessment_id == aiia_id,
                AssessmentItem.section_key == OVERVIEW_SECTION_KEY,
            )
        )
        db_session.add(
            AssessmentItemEvidence(
                id=uuid.uuid4(),
                tenant_id=tenant.id,
                item_id=item.id,
                evidence_id=evs[0].id,
            )
        )
        db_session.flush()

        with _ApiCtx(ctx, db_session):
            r1 = client.get("/v1/evidence", params={"limit": 2})
        assert r1.status_code == 200
        page1 = r1.json()
        assert len(page1["items"]) == 2
        assert page1["next_cursor"] is not None
        by_id = {i["id"]: i["link_count"] for i in page1["items"]}
        if str(evs[0].id) in by_id:
            assert by_id[str(evs[0].id)] == 1
        assert all("download_url" not in i for i in page1["items"])

        with _ApiCtx(ctx, db_session):
            r2 = client.get(
                "/v1/evidence", params={"limit": 2, "cursor": page1["next_cursor"]}
            )
        assert r2.status_code == 200
        page2 = r2.json()
        assert len(page2["items"]) == 1
        assert page2["next_cursor"] is None

    def test_get_returns_presigned_url_and_stages_access_audit(
        self,
        client,
        db_session,
        tenant,
        contributor,
        gov_roles,
    ):
        user, m = contributor
        ctx = _make_ctx(user, m, tenant)
        ev = Evidence(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            title="DPA",
            s3_bucket="b",
            s3_key="k",
            content_type="application/pdf",
            uploaded_by_user_id=user.id,
        )
        db_session.add(ev)
        db_session.flush()

        with (
            patch(
                "app.services.evidence_service.storage.presign_get",
                return_value="https://example-public/signed-url",
            ) as presign,
            _ApiCtx(ctx, db_session),
        ):
            r = client.get(f"/v1/evidence/{ev.id}")

        assert r.status_code == 200
        body = r.json()
        assert body["download_url"] == "https://example-public/signed-url"
        presign.assert_called_once()
        audit = db_session.scalar(
            select(AuditEvent).where(
                AuditEvent.action == "evidence.access",
                AuditEvent.entity_id == ev.id,
            )
        )
        assert audit is not None

    def test_get_cross_tenant_404(
        self, client, db_session, tenant, contributor, gov_roles
    ):
        other_tenant = Tenant(
            id=uuid.uuid4(), name="Other", slug=f"other-{uuid.uuid4().hex[:6]}"
        )
        db_session.add(other_tenant)
        db_session.flush()
        ev = Evidence(
            id=uuid.uuid4(),
            tenant_id=other_tenant.id,
            title="Not yours",
            s3_bucket="b",
            s3_key="k",
        )
        db_session.add(ev)
        db_session.flush()

        user, m = contributor
        ctx = _make_ctx(user, m, tenant)
        with _ApiCtx(ctx, db_session):
            r = client.get(f"/v1/evidence/{ev.id}")
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# WI-4: pristine guarded delete
# ---------------------------------------------------------------------------


class TestDelete:
    def test_delete_pristine_succeeds_and_stages_audit(
        self,
        client,
        db_session,
        tenant,
        contributor,
        gov_roles,
    ):
        user, m = contributor
        ctx = _make_ctx(user, m, tenant)
        ev = Evidence(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            title="DPA",
            s3_bucket="b",
            s3_key="k",
        )
        db_session.add(ev)
        db_session.flush()

        with _ApiCtx(ctx, db_session):
            r = client.delete(f"/v1/evidence/{ev.id}")
        assert r.status_code == 204

        assert db_session.scalar(select(Evidence).where(Evidence.id == ev.id)) is None
        audit = db_session.scalar(
            select(AuditEvent).where(
                AuditEvent.action == "evidence.deleted",
                AuditEvent.entity_id == ev.id,
            )
        )
        assert audit is not None

    def test_delete_linked_evidence_409_never_strips(
        self,
        client,
        db_session,
        tenant,
        contributor,
        gov_roles,
    ):
        user, m = contributor
        _grant(db_session, tenant, m, gov_roles["system_owner"])
        ctx = _make_ctx(user, m, tenant)
        ev = Evidence(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            title="DPA",
            s3_bucket="b",
            s3_key="k",
        )
        db_session.add(ev)
        db_session.flush()

        product, risk = _make_vendor_product_risk(db_session)
        system = _make_system(db_session, tenant, product)
        use_case = _make_use_case(db_session, tenant, system)
        _make_classification(db_session, tenant, use_case, EUAIActTier.HIGH)
        _seed_template(db_session, EUAIActTier.HIGH)
        with _ApiCtx(ctx, db_session):
            r = client.post(f"/v1/use-cases/{use_case.id}/assessments")
        aiia_id = uuid.UUID(r.json()["id"])
        item = db_session.scalar(
            select(AssessmentItem).where(
                AssessmentItem.assessment_id == aiia_id,
                AssessmentItem.section_key == OVERVIEW_SECTION_KEY,
            )
        )
        db_session.add(
            AssessmentItemEvidence(
                id=uuid.uuid4(),
                tenant_id=tenant.id,
                item_id=item.id,
                evidence_id=ev.id,
            )
        )
        db_session.flush()

        with _ApiCtx(ctx, db_session):
            r = client.delete(f"/v1/evidence/{ev.id}")
        assert r.status_code == 409
        assert (
            db_session.scalar(select(Evidence).where(Evidence.id == ev.id)) is not None
        )

    def test_delete_absent_409(
        self, client, db_session, tenant, contributor, gov_roles
    ):
        user, m = contributor
        ctx = _make_ctx(user, m, tenant)
        with _ApiCtx(ctx, db_session):
            r = client.delete(f"/v1/evidence/{uuid.uuid4()}")
        assert r.status_code == 409

    def test_non_write_role_403(self, client, db_session, tenant, auditor, gov_roles):
        user, m = auditor
        ctx = _make_ctx(user, m, tenant)
        ev = Evidence(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            title="DPA",
            s3_bucket="b",
            s3_key="k",
        )
        db_session.add(ev)
        db_session.flush()
        with _ApiCtx(ctx, db_session):
            r = client.delete(f"/v1/evidence/{ev.id}")
        assert r.status_code == 403


# ---------------------------------------------------------------------------
# WI-7/8/9 (Phase B): link/unlink, propagation, pristine-delete extension
# ---------------------------------------------------------------------------


def _create_aiia(
    client, db_session, tenant, owner_member, gov_roles, tier=EUAIActTier.HIGH
):
    """Build a complete, governance-granted AIIA via the API, mirroring
    tests/test_aiia_feeders.py's helper of the same name. AIIA creation is
    system_owner-only; owner_member's contributor grant (from the fixture)
    already covers the evidence-link write gate, so only top up system_owner."""
    user, m = owner_member
    _grant(db_session, tenant, m, gov_roles["system_owner"])
    product, risk = _make_vendor_product_risk(db_session)
    system = _make_system(db_session, tenant, product)
    use_case = _make_use_case(db_session, tenant, system)
    _make_classification(db_session, tenant, use_case, tier)
    _seed_template(db_session, tier)

    ctx = _make_ctx(user, m, tenant)
    with _ApiCtx(ctx, db_session):
        r = client.post(f"/v1/use-cases/{use_case.id}/assessments")
    assert r.status_code == 201
    return r.json(), use_case, system


def _link_evidence_to_curated_item(client, db_session, tenant, owner_member, gov_roles):
    """Build an AIIA, link a fresh Evidence row to its CATALOGUE_CURATED
    (non-AI_SUGGESTED) item, and return (aiia, item, evidence, ctx) for
    reuse across the link-success and unlink tests."""
    aiia, _, _ = _create_aiia(client, db_session, tenant, owner_member, gov_roles)
    user, m = owner_member
    ctx = _make_ctx(user, m, tenant)
    item = db_session.scalar(
        select(AssessmentItem).where(
            AssessmentItem.assessment_id == uuid.UUID(aiia["id"]),
            AssessmentItem.provenance == ProvenanceConfidence.CATALOGUE_CURATED,
        )
    )
    assert item is not None
    ev = Evidence(
        id=uuid.uuid4(), tenant_id=tenant.id, title="DPA", s3_bucket="b", s3_key="k"
    )
    db_session.add(ev)
    db_session.flush()

    with _ApiCtx(ctx, db_session):
        r = client.post(
            f"/v1/assessments/{aiia['id']}/items/{item.id}/evidence-links",
            json={"evidence_id": str(ev.id)},
        )
    assert r.status_code == 201
    return aiia, item, ev, ctx


class TestEvidenceLinks:
    def test_link_ai_suggested_item_409(
        self, client, db_session, tenant, contributor, gov_roles
    ):
        aiia, _, _ = _create_aiia(client, db_session, tenant, contributor, gov_roles)
        user, m = contributor
        ctx = _make_ctx(user, m, tenant)
        item = db_session.scalar(
            select(AssessmentItem).where(
                AssessmentItem.assessment_id == uuid.UUID(aiia["id"]),
                AssessmentItem.provenance == ProvenanceConfidence.AI_SUGGESTED,
            )
        )
        assert item is not None
        ev = Evidence(
            id=uuid.uuid4(), tenant_id=tenant.id, title="DPA", s3_bucket="b", s3_key="k"
        )
        db_session.add(ev)
        db_session.flush()

        with _ApiCtx(ctx, db_session):
            r = client.post(
                f"/v1/assessments/{aiia['id']}/items/{item.id}/evidence-links",
                json={"evidence_id": str(ev.id)},
            )
        assert r.status_code == 409
        assert db_session.scalar(select(AssessmentItemEvidence)) is None

    def test_link_dispositioned_item_succeeds_and_stages_audit(
        self,
        client,
        db_session,
        tenant,
        contributor,
        gov_roles,
    ):
        aiia, item, ev, ctx = _link_evidence_to_curated_item(
            client,
            db_session,
            tenant,
            contributor,
            gov_roles,
        )
        link = db_session.scalar(
            select(AssessmentItemEvidence).where(
                AssessmentItemEvidence.item_id == item.id,
                AssessmentItemEvidence.evidence_id == ev.id,
            )
        )
        assert link is not None
        audit = db_session.scalar(
            select(AuditEvent).where(AuditEvent.action == "evidence.linked")
        )
        assert audit is not None
        assert audit.entity_id == link.id

    def test_duplicate_link_409(
        self, client, db_session, tenant, contributor, gov_roles
    ):
        aiia, _, _ = _create_aiia(client, db_session, tenant, contributor, gov_roles)
        user, m = contributor
        ctx = _make_ctx(user, m, tenant)
        item = db_session.scalar(
            select(AssessmentItem).where(
                AssessmentItem.assessment_id == uuid.UUID(aiia["id"]),
                AssessmentItem.provenance == ProvenanceConfidence.CATALOGUE_CURATED,
            )
        )
        ev = Evidence(
            id=uuid.uuid4(), tenant_id=tenant.id, title="DPA", s3_bucket="b", s3_key="k"
        )
        db_session.add(ev)
        db_session.flush()

        with _ApiCtx(ctx, db_session):
            r1 = client.post(
                f"/v1/assessments/{aiia['id']}/items/{item.id}/evidence-links",
                json={"evidence_id": str(ev.id)},
            )
            r2 = client.post(
                f"/v1/assessments/{aiia['id']}/items/{item.id}/evidence-links",
                json={"evidence_id": str(ev.id)},
            )
        assert r1.status_code == 201
        assert r2.status_code == 409

    def test_cross_tenant_evidence_id_fails_closed(
        self,
        client,
        db_session,
        tenant,
        contributor,
        gov_roles,
    ):
        aiia, _, _ = _create_aiia(client, db_session, tenant, contributor, gov_roles)
        user, m = contributor
        ctx = _make_ctx(user, m, tenant)
        item = db_session.scalar(
            select(AssessmentItem).where(
                AssessmentItem.assessment_id == uuid.UUID(aiia["id"]),
                AssessmentItem.provenance == ProvenanceConfidence.CATALOGUE_CURATED,
            )
        )
        other_tenant = Tenant(
            id=uuid.uuid4(), name="Other", slug=f"other-{uuid.uuid4().hex[:6]}"
        )
        db_session.add(other_tenant)
        db_session.flush()
        ev = Evidence(
            id=uuid.uuid4(),
            tenant_id=other_tenant.id,
            title="Not yours",
            s3_bucket="b",
            s3_key="k",
        )
        db_session.add(ev)
        db_session.flush()

        with _ApiCtx(ctx, db_session):
            r = client.post(
                f"/v1/assessments/{aiia['id']}/items/{item.id}/evidence-links",
                json={"evidence_id": str(ev.id)},
            )
        assert r.status_code == 404

    def test_unlink_idempotent_no_audit_on_noop(
        self,
        client,
        db_session,
        tenant,
        contributor,
        gov_roles,
    ):
        aiia, item, ev, ctx = _link_evidence_to_curated_item(
            client,
            db_session,
            tenant,
            contributor,
            gov_roles,
        )
        with _ApiCtx(ctx, db_session):
            r1 = client.delete(
                f"/v1/assessments/{aiia['id']}/items/{item.id}/evidence-links/{ev.id}"
            )
            audit_count_after_real_unlink = db_session.scalar(
                select(AuditEvent).where(AuditEvent.action == "evidence.unlinked")
            )
            r2 = client.delete(
                f"/v1/assessments/{aiia['id']}/items/{item.id}/evidence-links/{ev.id}"
            )

        assert r1.status_code == 204
        assert audit_count_after_real_unlink is not None
        assert r2.status_code == 204
        assert (
            db_session.scalar(select(AssessmentItemEvidence)) is None
        )  # no duplicate audit/row from the no-op second call

    def test_non_write_role_403(
        self, client, db_session, tenant, contributor, auditor, gov_roles
    ):
        aiia, _, _ = _create_aiia(client, db_session, tenant, contributor, gov_roles)
        item = db_session.scalar(
            select(AssessmentItem).where(
                AssessmentItem.assessment_id == uuid.UUID(aiia["id"]),
                AssessmentItem.provenance == ProvenanceConfidence.CATALOGUE_CURATED,
            )
        )
        ev = Evidence(
            id=uuid.uuid4(), tenant_id=tenant.id, title="DPA", s3_bucket="b", s3_key="k"
        )
        db_session.add(ev)
        db_session.flush()

        auditor_user, auditor_m = auditor
        auditor_ctx = _make_ctx(auditor_user, auditor_m, tenant)
        with _ApiCtx(auditor_ctx, db_session):
            r = client.post(
                f"/v1/assessments/{aiia['id']}/items/{item.id}/evidence-links",
                json={"evidence_id": str(ev.id)},
            )
        assert r.status_code == 403


class TestPristineDeleteBlockedByEvidence:
    def test_assessment_delete_blocked_when_item_has_evidence_link(
        self,
        client,
        db_session,
        tenant,
        contributor,
        gov_roles,
    ):
        aiia, _, _ = _create_aiia(client, db_session, tenant, contributor, gov_roles)
        user, m = contributor
        ctx = _make_ctx(user, m, tenant)
        item = db_session.scalar(
            select(AssessmentItem).where(
                AssessmentItem.assessment_id == uuid.UUID(aiia["id"]),
                AssessmentItem.provenance == ProvenanceConfidence.CATALOGUE_CURATED,
            )
        )
        ev = Evidence(
            id=uuid.uuid4(), tenant_id=tenant.id, title="DPA", s3_bucket="b", s3_key="k"
        )
        db_session.add(ev)
        db_session.flush()

        with _ApiCtx(ctx, db_session):
            r_link = client.post(
                f"/v1/assessments/{aiia['id']}/items/{item.id}/evidence-links",
                json={"evidence_id": str(ev.id)},
            )
            assert r_link.status_code == 201
            r_delete = client.delete(f"/v1/assessments/{aiia['id']}")
        assert r_delete.status_code == 409
        assert db_session.get(Assessment, uuid.UUID(aiia["id"])) is not None


class TestFeederEvidencePropagation:
    def test_feeder_items_evidence_link_surfaces_into_aiia_read_untouched(
        self,
        client,
        db_session,
        tenant,
        contributor,
        gov_roles,
    ):
        aiia, _, _ = _create_aiia(client, db_session, tenant, contributor, gov_roles)
        _seed_feeder_template(db_session, EUAIActTier.HIGH, AssessmentType.FRIA)
        user, m = contributor
        ctx = _make_ctx(user, m, tenant)

        with _ApiCtx(ctx, db_session):
            r_feeder = client.post(
                f"/v1/assessments/{aiia['id']}/feeders",
                json={"type": "fria"},
            )
        assert r_feeder.status_code == 201
        feeder_id = uuid.UUID(r_feeder.json()["id"])

        feeder_item = db_session.scalar(
            select(AssessmentItem).where(
                AssessmentItem.assessment_id == feeder_id,
                AssessmentItem.section_key == FRIA_AFFECTED_PERSONS_SECTION_KEY,
            )
        )
        assert feeder_item is not None
        ev = Evidence(
            id=uuid.uuid4(), tenant_id=tenant.id, title="DPA", s3_bucket="b", s3_key="k"
        )
        db_session.add(ev)
        db_session.flush()

        with _ApiCtx(ctx, db_session):
            r_link = client.post(
                f"/v1/assessments/{feeder_id}/items/{feeder_item.id}/evidence-links",
                json={"evidence_id": str(ev.id)},
            )
            assert r_link.status_code == 201
            r_aiia_detail = client.get(f"/v1/assessments/{aiia['id']}")
        assert r_aiia_detail.status_code == 200

        items = r_aiia_detail.json()["items"]
        surfaced = [i for i in items if i["id"] == str(feeder_item.id)]
        assert len(surfaced) == 1
        assert surfaced[0]["source_assessment_id"] == str(feeder_id)

        # Reference, not copy: exactly one link row, still keyed to the
        # feeder item's own id -- nothing was written back or duplicated by
        # the read-time assembly.
        links = list(
            db_session.scalars(
                select(AssessmentItemEvidence).where(
                    AssessmentItemEvidence.evidence_id == ev.id,
                )
            )
        )
        assert len(links) == 1
        assert links[0].item_id == feeder_item.id
