"""
app/services/evidence_service.py

Evidence repository (sprints/SPRINT_EVIDENCE_REPOSITORY.md): upload, list,
retrieve, delete. Owns its own session for upload — see _tenant_session below
for why.

Two transactional shapes, kept apart (sprint §2):
* upload_evidence: the S3 put runs with NO db session open at all (not
  before, not held idle) — the put is bracketed by two short, independent
  transactions (a write-role pre-check, then the row+audit insert). This is
  the OPPOSITE of provision_member's Cognito choreography (one transaction
  held open across the external call) — here the external call must never
  see an open transaction, so a request-scoped Depends(get_tenant_db) (held
  for the whole request) cannot be used for this route at all.
* list_evidence / get_evidence / delete_evidence: ordinary tenant reads/
  writes on the request-scoped session, same as every other v1 endpoint.
"""

from __future__ import annotations

import base64
import hashlib
import uuid
from collections.abc import Generator
from contextlib import contextmanager
from datetime import datetime
from tempfile import SpooledTemporaryFile

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import delete, exists, func, select, text
from sqlalchemy.orm import Session

from app.auth.context import TenantContext, require_governance_role
from app.config import settings
from app.db.session import SessionLocal
from app.models.assessment import AssessmentItemEvidence
from app.models.lifecycle import AuditEvent, Evidence
from app.services import storage

_WRITE_ROLES = ("system_owner", "contributor")
_ALL_GOVERNANCE_ROLES = (
    "system_owner", "contributor", "reviewer", "authoriser", "auditor",
)

_CHUNK_BYTES = 1024 * 1024          # 1 MiB streaming read for the hash pass
_SPOOL_MAX_MEMORY_BYTES = 8 * 1024 * 1024  # spool to disk past 8 MiB


@contextmanager
def _tenant_session(ctx: TenantContext) -> Generator[Session, None, None]:
    """A short, standalone tenant-scoped transaction — deliberately NOT a
    FastAPI Depends(get_tenant_db). That dependency stays open for the whole
    request; this one opens, does its work, and closes on its own, so it can
    be used twice with the slow S3 put running in between, holding nothing."""
    db = SessionLocal()
    try:
        db.begin()
        db.execute(
            text("SELECT set_config('app.current_tenant', :tid, true)"),
            {"tid": str(ctx.tenant_id)},
        )
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _hash_and_spool(upload: UploadFile) -> tuple[int, str, SpooledTemporaryFile]:
    """Two-pass prep: hash the upload into a local spool, no DB involved.
    Streamed in chunks so the size cap (413) is enforced before the whole
    body is buffered."""
    spooled = SpooledTemporaryFile(max_size=_SPOOL_MAX_MEMORY_BYTES)
    hasher = hashlib.sha256()
    size = 0
    while chunk := upload.file.read(_CHUNK_BYTES):
        size += len(chunk)
        if size > settings.evidence_max_upload_bytes:
            raise HTTPException(
                status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="Evidence exceeds the upload size cap",
            )
        hasher.update(chunk)
        spooled.write(chunk)
    if size == 0:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Empty upload")
    return size, hasher.hexdigest(), spooled


def upload_evidence(
    ctx: TenantContext, upload: UploadFile, title: str | None,
) -> Evidence:
    with _tenant_session(ctx) as db:
        require_governance_role(*_WRITE_ROLES)(ctx=ctx, db=db)

    size, sha256, spooled = _hash_and_spool(upload)
    evidence_id = uuid.uuid4()
    bucket = settings.s3_evidence_bucket
    key = f"{ctx.tenant_id}/evidence/{evidence_id}"

    spooled.seek(0)
    version_id = storage.put_object(
        bucket, key, spooled,
        sse_mode=settings.s3_sse_mode, sse_kms_key_id=settings.s3_sse_kms_key_id,
        original_filename=upload.filename or str(evidence_id),
    )

    try:
        with _tenant_session(ctx) as db:
            ev = Evidence(
                id=evidence_id, tenant_id=ctx.tenant_id,
                title=title or upload.filename or str(evidence_id),
                s3_bucket=bucket, s3_key=key, s3_version_id=version_id,
                content_type=upload.content_type, size_bytes=size, sha256=sha256,
                uploaded_by_user_id=ctx.user_id,
            )
            db.add(ev)
            db.flush()
            db.add(AuditEvent(
                id=uuid.uuid4(), tenant_id=ctx.tenant_id, actor_user_id=ctx.user_id,
                action="evidence.created", entity_type="evidence",
                entity_id=evidence_id,
                detail={
                    "sha256": sha256, "size_bytes": size,
                    "content_type": upload.content_type,
                },
            ))
    except Exception:
        storage.delete_object(bucket, key, version_id)
        raise
    return ev


def _encode_cursor(created_at: datetime, evidence_id: uuid.UUID) -> str:
    raw = f"{created_at.isoformat()}|{evidence_id}"
    return base64.urlsafe_b64encode(raw.encode()).decode()


def _decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    raw = base64.urlsafe_b64decode(cursor.encode()).decode()
    ts, eid = raw.split("|", 1)
    return datetime.fromisoformat(ts), uuid.UUID(eid)


def list_evidence(
    ctx: TenantContext, db: Session, *, cursor: str | None, limit: int,
) -> tuple[list[tuple[Evidence, int]], str | None]:
    link_count = (
        select(func.count(AssessmentItemEvidence.id))
        .where(AssessmentItemEvidence.evidence_id == Evidence.id)
        .correlate(Evidence)
        .scalar_subquery()
    )
    stmt = (
        select(Evidence, link_count.label("link_count"))
        .where(Evidence.tenant_id == ctx.tenant_id)
        .order_by(Evidence.created_at, Evidence.id)
        .limit(limit + 1)
    )
    if cursor:
        try:
            after_ts, after_id = _decode_cursor(cursor)
        except Exception as exc:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, detail="Invalid cursor",
            ) from exc
        stmt = stmt.where(
            (Evidence.created_at > after_ts)
            | ((Evidence.created_at == after_ts) & (Evidence.id > after_id))
        )

    rows = db.execute(stmt).all()
    has_next = len(rows) > limit
    rows = rows[:limit]

    next_cursor = None
    if has_next and rows:
        last_evidence, _ = rows[-1]
        next_cursor = _encode_cursor(last_evidence.created_at, last_evidence.id)

    return rows, next_cursor


def get_evidence(
    ctx: TenantContext, db: Session, evidence_id: uuid.UUID,
) -> tuple[Evidence, str]:
    ev = db.scalar(
        select(Evidence).where(
            Evidence.id == evidence_id, Evidence.tenant_id == ctx.tenant_id,
        )
    )
    if ev is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Evidence not found")

    url = storage.presign_get(
        ev.s3_bucket, ev.s3_key, ev.s3_version_id,
        ttl=settings.s3_presigned_get_ttl, filename=ev.title,
        content_type=ev.content_type,
    )
    db.add(AuditEvent(
        id=uuid.uuid4(), tenant_id=ctx.tenant_id, actor_user_id=ctx.user_id,
        action="evidence.access", entity_type="evidence", entity_id=evidence_id,
        detail={},
    ))
    db.flush()
    return ev, url


def delete_evidence(ctx: TenantContext, db: Session, evidence_id: uuid.UUID) -> None:
    """Single guarded statement — never check-then-delete. The junction's
    ON DELETE CASCADE means a concurrent link insert between a SELECT count
    and a DELETE would be silently stripped; NOT EXISTS in the same
    statement closes that race."""
    stmt = delete(Evidence).where(
        Evidence.id == evidence_id,
        Evidence.tenant_id == ctx.tenant_id,
        ~exists().where(AssessmentItemEvidence.evidence_id == evidence_id),
    )
    result = db.execute(stmt)
    if result.rowcount == 0:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="Evidence is linked to one or more assessment items, or not found",
        )
    db.add(AuditEvent(
        id=uuid.uuid4(), tenant_id=ctx.tenant_id, actor_user_id=ctx.user_id,
        action="evidence.deleted", entity_type="evidence", entity_id=evidence_id,
        detail={},
    ))
    db.flush()
