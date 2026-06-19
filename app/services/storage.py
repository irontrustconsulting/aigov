"""
Shared S3 helper for the evidence repository (sprints/SPRINT_EVIDENCE_REPOSITORY.md).

Two clients, not one:
* the INTERNAL client puts/deletes objects — the API talks to S3/MinIO over
  its internal network address.
* the PUBLIC client only ever signs presigned GET URLs — SigV4 signs the
  host, so a URL meant for a browser must be signed against the host the
  browser can actually reach (in dev-Compose, "minio:9000" vs
  "localhost:9000"; in prod both endpoints are the same AWS host).

Bytes never enter Postgres; the caller is responsible for hashing before
calling put_object — this module only moves bytes and signs URLs.
"""

from __future__ import annotations

from typing import IO

import boto3
from botocore.client import Config as BotoConfig

from app.config import settings

# Content types safe to render inline in a browser without risk of stored
# XSS (no text/html, no image/svg+xml — both can carry script). Anything
# else is neutralised to a download-only octet-stream on presigned GET.
_SAFE_CONTENT_TYPES = frozenset({
    "application/pdf",
    "image/png",
    "image/jpeg",
    "image/gif",
    "image/webp",
    "text/plain",
    "text/csv",
    "application/json",
    "application/zip",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
})


def _client(endpoint_url: str | None):
    addressing_style = "path" if settings.s3_use_path_style else "virtual"
    return boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        region_name=settings.s3_region,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        config=BotoConfig(
            s3={"addressing_style": addressing_style},
            signature_version="s3v4",
        ),
    )


def _internal_client():
    return _client(settings.s3_endpoint_url)


def _public_client():
    public = settings.s3_public_endpoint_url or settings.s3_endpoint_url
    return _client(public)


def put_object(
    bucket: str,
    key: str,
    fileobj: IO[bytes],
    *,
    sse_mode: str | None,
    sse_kms_key_id: str | None,
    original_filename: str,
) -> str | None:
    """Put a (seeked-to-0) file-like object. Returns the S3 VersionId, or
    None if the bucket isn't versioned. SSE is applied per settings, never
    left to the caller — no call path can store an object unencrypted."""
    extra: dict = {"Metadata": {"original-filename": original_filename}}
    if sse_mode:
        extra["ServerSideEncryption"] = sse_mode
        if sse_mode == "aws:kms" and sse_kms_key_id:
            extra["SSEKMSKeyId"] = sse_kms_key_id
    resp = _internal_client().put_object(Bucket=bucket, Key=key, Body=fileobj, **extra)
    return resp.get("VersionId")


def presign_get(
    bucket: str,
    key: str,
    version_id: str | None,
    *,
    ttl: int,
    filename: str,
    content_type: str | None,
) -> str:
    """Presigned GET, hardened: forces attachment download under the
    original filename and neutralises the content-type for anything not on
    the safe allow-list, closing the inline-render XSS path an
    un-allow-listed text/html or image/svg+xml object would otherwise open.
    Signed against the PUBLIC endpoint — the host the caller can reach."""
    safe_type = (
        content_type
        if content_type in _SAFE_CONTENT_TYPES
        else "application/octet-stream"
    )
    params = {
        "Bucket": bucket,
        "Key": key,
        "ResponseContentDisposition": f'attachment; filename="{filename}"',
        "ResponseContentType": safe_type,
    }
    if version_id:
        params["VersionId"] = version_id
    return _public_client().generate_presigned_url(
        "get_object", Params=params, ExpiresIn=ttl,
    )


def delete_object(bucket: str, key: str, version_id: str | None = None) -> None:
    """Delete by version when known, else by key (unversioned bucket)."""
    params: dict = {"Bucket": bucket, "Key": key}
    if version_id:
        params["VersionId"] = version_id
    _internal_client().delete_object(**params)
