# Sprint Handoff — Evidence Repository (S3-backed upload, reuse across assessment items, immutable audit)

> This sprint builds the **central evidence repository** (EVD-1, EVD-2; AIIA-5): upload a file, store the bytes in S3, record a pointer row, and link that evidence to one or more assessment items, reusably. It ships in two phases — **Phase A** (upload + repository, no schema migration) and **Phase B** (item linking + propagation, one junction migration). EVD-3 (assignment/reminders), EVD-4 (freshness notifications), the export/audit pack (EXP-1), AV scanning, and Object Lock retention-application are **out of scope**. Both backing tables are reconciled against live DDL; the one open precondition is `AuditEvent` actor durability (§10).

---

## 1. Sprint title

**Evidence Repository: S3-backed upload with server-computed integrity hashing, a reusable tenant evidence store, disposition-gated linking to assessment items, hardened presigned download, and pristine guarded delete — additive on the existing assessment graph.**

---

## 2. Status going in / context

- The first-class `evidence` table (pointer + `sha256`) and the `assessment_item_evidence` M:N junction both **exist live**; this sprint builds everything below the model — S3 wiring, the write path, link/unlink, retrieval, delete — none of which exists yet.
- This is **Sprint 4**, the evidence/upload path the AIIA sprint deferred (`AIIA_DESIGN.md` §12). The AIIA item/control/feeder machinery it plugs into is already built.
- **First S3/boto3 wiring in the repository.** Greenfield on the storage side; dev runs MinIO, prod real S3, switched by endpoint config.
- **Two transactional shapes, and neither is the Cognito six-step pattern.** Upload makes a *slow* external call (S3 put up to the 100 MiB cap), so the put runs **outside** any DB transaction; the row+audit write is a short transaction after it, S3-compensated on commit failure. Link/unlink is pure DB on the tenant-plane atomic-audit rule. Do not conflate them.
- **Reuse is the product thesis (EVD-1):** one uploaded artifact (a DPA, model card, certification) satisfies many items across many assessments. The `Evidence` row is standalone; linking is a separate, additive act.
- **Separation of duties (4.9.1):** evidence provision is a 1st-line act — PRD §4.9.1 defines Contributor as "supplies requested evidence/facts." Writes are gated to `{system_owner, contributor}`; reads to all five governance roles (the auditor consumes evidence read-only).

---

## 3. Baseline & architectural context

### Existing components — reuse, do not rebuild

**`evidence` (tenant plane, RLS `tenant_isolation`) — reconciled against live `\d evidence`:** `id uuid PK`, `tenant_id uuid NOT NULL` (FK → `tenant` `ON DELETE CASCADE`), `title varchar(255) NOT NULL`, `s3_bucket varchar(255) NOT NULL`, `s3_key varchar(1024) NOT NULL`, `s3_version_id varchar(255) NULL`, `content_type varchar(120) NULL`, `size_bytes integer NULL`, `sha256 varchar(64) NULL` (non-unique `ix_evidence_sha256`), `uploaded_by_user_id uuid NULL` (FK → `app_user` `ON DELETE SET NULL`), `expires_at timestamptz NULL`, timestamps. RLS `USING (tenant_id = current_setting('app.current_tenant'))`. **No ALTER this sprint.**

**`assessment_item_evidence` (tenant plane, RLS `tenant_isolation`) — reconciled against live `\d`:** four columns only — `id uuid PK`, `item_id uuid NOT NULL` (FK → `assessment_item` `ON DELETE CASCADE`), `evidence_id uuid NOT NULL` (FK → `evidence` `ON DELETE CASCADE`), `tenant_id uuid NOT NULL` (FK → `tenant` `ON DELETE CASCADE`). Non-unique indexes on `item_id`, `evidence_id`, `tenant_id`. **No `created_by`/timestamps** (attribution lives in AuditEvents). **No `UNIQUE (item_id, evidence_id)`** — Phase B adds it.

**`assessment_item`:** carries `provenance ProvenanceConfidence` and the disposition model. Authoring-field writes on a still-`AI_SUGGESTED` item are blocked until confirm/amend (disposition-before-authoring). `CATALOGUE_CURATED` section-prompt items are exempt. This gate is extended to evidence-linking (§5).

**`assessment_item_control`:** the structural template for evidence link/unlink — a thin item↔X join, duplicate→409, no `lock_version`, attribution in AuditEvents. Mirror its endpoint shape; the one deliberate divergence is the disposition gate (§5).

**Read-time feeder assembly (`assemble_aiia_items`, `AIIA_DESIGN.md` §9.2):** `GET /assessments/{aiia_id}` assembles native ∪ surfaced feeder items, tagging `source_assessment_id` + `source_type`, carrying control links untouched. The single locus for cross-assessment surfacing; extended here to carry evidence links.

**Pristine-delete (`assessment_service.py`, `AIIA_DESIGN.md` §8.11):** an assessment/feeder hard-deletes only while pristine (no confirmed/amended items, no control links, no feeders). Extended here to also block on evidence links.

**Audit:** `AuditEvent` (tenant plane, append-only, RLS-scoped, DB immutability trigger). Action strings `entity.verb`.

**Governance (4.9.1):** `governance_role` catalogue + `require_governance_role(...)`; tenant-scoped (WKF-7). SoD enforced at assignment (WKF-5), never re-checked per action.

**Config:** `pydantic-settings` `Settings` singleton (`from app.config import settings`); component fields, computed URLs — never full URL strings in `.env`.

### Patterns to preserve

- **Tenant endpoint convention:** router under `app/routers/v1/`, registered in `app/main.py` under `/v1`; gate with `get_tenant_db` **plus one** role gate; `tenant_id = ctx.tenant_id`, never from body; schemas in `app/schemas/`.
- **Tenant-plane atomic audit:** the `AuditEvent` commits in the same transaction as its business rows, never separately.
- **Shared external helpers:** centralise the boto3 client in `app/services/storage.py`, mirroring `cognito_helpers.py`. Do not inline boto3 in handlers.
- **No new DB role.** All evidence work runs on `irontrustai_app` (`NOBYPASSRLS`) under RLS.
- **DB authority, fail-closed RLS:** an `evidence_id` or `item_id` supplied in a request is only usable if RLS-visible to the caller; cross-tenant references resolve to nothing.

---

## 4. Goal / contract

The feature must:

1. **Upload** a file: stream it to S3 under a tenant-prefixed key, compute its `sha256` server-side, and record a pointer row — **without holding a DB transaction across the put**.
2. Expose a **reusable repository**: list evidence (paginated, with link-count) and retrieve one item's metadata plus a **hardened presigned download URL**.
3. **Link / unlink** existing evidence to assessment items, **disposition-gated**, with reuse across items and assessments.
4. **Delete** an evidence row only while **pristine** (zero links), via a single guarded statement that cannot race through the junction CASCADE.
5. **Audit** every create/link/unlink/delete and every download-URL issuance.

**Storage contract:**

```
storage.put_object(bucket, key, fileobj, *, sse, metadata) -> version_id   # SSE by policy; sets original-filename metadata
storage.presign_get(bucket, key, version_id, *, ttl, filename, safe_content_type) -> url   # attachment-forced
storage.delete_object(bucket, key, version_id | None)   # by version when set, else by key
```

Bytes never enter Postgres; `sha256` never comes from the client. The row is the system of record for the pointer; the bytes are immutable post-upload (re-evidencing is a new row, not a mutation).

---

## 5. Domain model / rules

- **Bytes in S3 only.** Postgres holds the pointer (`s3_bucket`/`s3_key`/`s3_version_id`) + `sha256`. Buffer nothing into the DB. The upload spools to a local `SpooledTemporaryFile` and is read in **two sequential passes** (hash, then `seek(0)`, then put) — not stream-through, because boto3 multipart may read the seekable spool non-sequentially and corrupt a read-through digest.
- **`sha256` is integrity + lookup, not uniqueness** (schema-confirmed: nullable, non-unique index). Server-computed. Optional soft dedup *detection* via the index; no constraint, no enforcement.
- **Tenant-prefixed keys:** `{tenant_id}/evidence/{evidence_id}` — defence in depth on top of RLS.
- **SSE by policy:** the storage layer applies server-side encryption on every put; no call path can store an object unencrypted.
- **Evidence sits outside the §1.5 provenance machine.** It is a user-origin artifact, not a system-asserted default — no `ProvenanceConfidence` tag. Its defensibility record is the `evidence.*` audit trail.
- **Evidence → control is transitive via items only.** No direct evidence↔control link. Framework satisfaction derives from the control-library cross-map: one evidence on one item reaches every control that item links across both frameworks.
- **Disposition gate on linking (deliberate asymmetry with control-links):** reject an evidence-link on a still-`AI_SUGGESTED` item (409, "confirm or amend the proposed risk first"); allow on every dispositioned or non-proposal item (`USER_PROVIDED`, `CATALOGUE_CURATED`, `USER_CONFIRMED`, `USER_AMENDED`). Evidence is substantiation — re-pointing proof under a later amendment is worse than re-pointing a mapping, so it belongs behind the same gate as authoring (inv 13), even though control-links carry no such gate.
- **Pristine delete is a single guarded statement,** not check-then-delete: the junction's `ON DELETE CASCADE` means a concurrent link insert between a `SELECT count` and a `DELETE` would be silently stripped. Delete is guarded by `NOT EXISTS`; zero rows → 409.
- **Pristine-delete of an assessment/item/feeder also blocks on evidence links** — an item carrying evidence is "worked." This extends shared code (§6 WI-8).
- **Feeder propagation is reference, not copy:** surfaced feeder items carry their evidence links untouched into the AIIA read; never written back.
- **Uploader durability:** `uploaded_by_user_id` is `SET NULL` — evidence outlives its uploader; the durable actor is the `evidence.created` AuditEvent (conditional on the audit model snapshotting identity — §10).
- **Download is a custody event:** issuing a presigned GET is audited (`evidence.access`), closer to EVD-2's "export" than a plain read.

---

## 6. Work items

> Phase A = WI-1 → WI-5 (shippable/demoable: upload + repository + delete; no migration). Phase B = WI-6 → WI-9 (linking + propagation). WI-0 is Terraform/infra, parallel.

**WI-0 — Bucket provisioning (Terraform `infra/`, parallel).**
Prod evidence bucket created **with Object Lock enabled at creation** (versioning auto-on), **no blanket default retention**, governance mode. Dev MinIO: create the bucket with **versioning enabled** (so `s3_version_id` is exercised); Object Lock unnecessary. Not an Alembic migration. (Retention/legal-hold application is deferred to lifecycle work — §9.)

**WI-1 — S3 config + dual-client storage helper.**
Add the `s3_*` settings (§11) to `app/config.py`, including a **separate internal vs public endpoint** (SigV4 signs the host: the API puts via the internal endpoint; presigned URLs the browser fetches must be signed against the public endpoint). `app/services/storage.py`: an internal client (puts) and a presign client (GET URLs); `put_object` applies SSE by policy and sets `x-amz-meta-original-filename`, returns `VersionId`; `presign_get` forces `ResponseContentDisposition: attachment; filename="…"` and neutralises `ResponseContentType` for non-safe types; `delete_object` by version-or-key. Static creds dev-only; prod leaves them unset (boto3 role chain).

**WI-2 — Upload service + ordering (`app/services/evidence_service.py`).**
`POST /v1/evidence` (multipart). Order: generate `evidence_id` app-side (`uuid_pk()`); reject oversize/empty (413/422); hash pass (no DB); `storage.put_object` (no connection held); then a **short** tenant transaction inserting the `evidence` row (pre-generated id, `sha256`, `version_id`, `content_type`, `size_bytes`, `uploaded_by_user_id = ctx.user_id`, `title` defaulting to the original filename) and staging `evidence.created`; commit; on commit failure compensate the S3 object (by version-or-key). **No linking on upload** (Phase B). See §11.

**WI-3 — Repository read endpoints.**
`GET /v1/evidence` — paginated listing (cursor + limit), each row carrying a `link_count` (`COUNT(assessment_item_evidence WHERE evidence_id = e.id)`, served by `ix_…_evidence_id`); no presigned URLs in the list. `GET /v1/evidence/{id}` — metadata + a short-TTL presigned download URL (attachment-forced, safe type), and stages `evidence.access` in a transaction (a custody-audited GET). Reads gated to all five governance roles.

**WI-4 — Pristine evidence-row delete.**
`DELETE /v1/evidence/{id}` — a single guarded statement: `DELETE FROM evidence WHERE id = :id AND NOT EXISTS (SELECT 1 FROM assessment_item_evidence WHERE evidence_id = :id)`. Zero rows → 409 (linked or absent). On one row → stage `evidence.deleted`, commit atomically. **Does not delete the S3 object in-band** for MVP (orphaned bytes are reconciliation-sweep territory, deferred); if deleting the object, do so only after the row delete commits, never before. Gated `{system_owner, contributor}`.

**WI-5 — Phase A audit strings.**
New `entity.verb` actions: `evidence.created`, `evidence.deleted`, `evidence.access`. Staged atomically with their transactions.

**WI-6 — Junction migration (`evidence_link_migration.py`, DDL only — Phase B).**
Add `UNIQUE (item_id, evidence_id)` to `assessment_item_evidence`; **drop the now-redundant `ix_assessment_item_evidence_item_id`** (the composite serves `item_id` as leftmost prefix). **Keep `ix_assessment_item_evidence_evidence_id`** (backs the WI-4 delete guard and the WI-3 link-count; the composite cannot serve an `evidence_id`-leading query). Set `down_revision` to current head.

**WI-7 — Link / unlink endpoints + audit (Phase B).**
`POST /v1/assessments/{aid}/items/{item_id}/evidence-links {evidence_id}` — disposition-gated (409 on `AI_SUGGESTED` item), duplicate → 409 (the new unique), `evidence_id`/`item_id` RLS-validated, stages `evidence.linked`. `DELETE …/evidence-links/{evidence_id}` — idempotent; a no-op removal (link absent) writes **no** AuditEvent (parity with no-op PATCH); a real removal stages `evidence.unlinked`. No `lock_version`. See §11.

**WI-8 — Pristine-delete predicate extension (shared `assessment_service.py` — Phase B).**
Extend the assessment/item/feeder pristine predicate to also block when any item carries an evidence link. **This edits shared AIIA/feeder delete code — not purely additive.** Re-run the existing AIIA/feeder pristine-delete tests; preserve that path's atomicity.

**WI-9 — Read-time assembly extension (`assemble_aiia_items` — Phase B).**
Surface a feeder item's evidence links into the AIIA read alongside its control links, tagged with the source, untouched — never copied or written back. The single locus for this surfacing.

---

## 7. Constraints / non-negotiables

- **Bytes in S3 only.** Pointer + `sha256` in PG; buffer nothing into the DB.
- **No DB transaction across the S3 put.** UUID app-side; hash + put first; short row+audit transaction after; S3-compensated on commit failure. The Cognito DB-first ordering does **not** apply.
- **`sha256` server-computed, never client-set.** Two-pass hash over the local spool; never tee through boto3's multipart reader.
- **Single guarded delete.** `DELETE … WHERE NOT EXISTS (link)`; never check-then-delete (the junction CASCADE makes the race destructive). Zero rows → 409.
- **Disposition gate on linking.** Reject on `AI_SUGGESTED`; allow otherwise. Deliberately asymmetric with control-links.
- **SSE by policy** on every put; not a per-caller option.
- **Tenant-prefixed keys**; `tenant_id = ctx.tenant_id`, never body; `evidence_id`/`item_id` RLS-validated, fail-closed.
- **Hardened presigned download:** forced `Content-Disposition: attachment` + safe content-type, signed against the **public** endpoint. Closes the file-body XSS path that an un-allow-listed `text/html`/`image/svg+xml` would otherwise open inline in the bucket origin.
- **Atomic tenant-plane audit:** each write commits its `AuditEvent` in the same transaction; no-op unlink writes none.
- **No new DB role.** `irontrustai_app`, `NOBYPASSRLS`, under RLS.
- **Evidence → control is transitive via items.** No direct evidence↔control table.
- **Feeder propagation is reference, not copy.** Single locus `assemble_aiia_items`.
- **Pristine-delete edits shared code (WI-8).** Re-run AIIA/feeder delete tests; do not regress them.
- **Bytes immutable post-upload.** Re-evidencing is a new row with a new hash.

---

## 8. Acceptance criteria

- [ ] Upload streams to S3 under `{tenant_id}/evidence/{id}`, computes `sha256` server-side, and writes the pointer row; **no DB connection is held across the put** (verifiable by the ordering and by a held-connection test under concurrency).
- [ ] An injected commit failure after the put compensates the S3 object (by version-or-key) and persists no row.
- [ ] Oversize (> cap, enforced during the hash pass) → 413; empty/zero-byte → 422.
- [ ] `GET /v1/evidence` paginates and returns a correct `link_count` per row; no presigned URLs in the list.
- [ ] `GET /v1/evidence/{id}` returns metadata + a presigned URL that forces download (attachment) with the original filename and a neutralised content-type for non-safe types; the URL is signed against the public endpoint; the call stages `evidence.access`.
- [ ] `DELETE /v1/evidence/{id}` deletes only while pristine via the single guarded statement; a concurrent link insert causes the delete to affect zero rows → 409, never a strip.
- [ ] **(Phase B)** The junction migration adds `UNIQUE (item_id, evidence_id)`, drops `ix_…_item_id`, keeps `ix_…_evidence_id`.
- [ ] **(Phase B)** Linking to an `AI_SUGGESTED` item → 409; to a dispositioned/section-prompt item → success; duplicate link → 409; cross-tenant `evidence_id`/`item_id` → fail-closed (404/empty).
- [ ] **(Phase B)** Unlink is idempotent; a no-op removal writes no AuditEvent; a real removal stages `evidence.unlinked`.
- [ ] **(Phase B)** A feeder item's evidence links surface into the AIIA read (`assemble_aiia_items`) untouched, tagged with the source; nothing is copied or written back.
- [ ] **(Phase B)** Pristine-delete of an assessment/item/feeder blocks (409) when an item carries an evidence link; existing AIIA/feeder pristine-delete tests re-run green.
- [ ] Every create/link/unlink/delete/access commits its `AuditEvent` atomically with its rows; an injected failure rolls back both.
- [ ] **Authorisation:** writes (upload/delete/link/unlink) → 403 for any non-`{system_owner, contributor}`; reads (list/detail) → 200 for all five governance roles.
- [ ] No evidence path runs on a `BYPASSRLS` role; all reads/writes are RLS-scoped.

---

## 9. Out of scope

- **Evidence assignment with due dates / reminders (EVD-3)** — post-MVP; no model touched.
- **Freshness / expiry notifications (EVD-4)** — `expires_at` present and unused; no scheduler.
- **Export / audit pack (EXP-1)** — the immediate downstream consumer of the presigned-download primitive, but its own sprint; build none of it here.
- **Presigned direct-to-S3 *upload*** — the scale seam; deferred so the server owns the hash.
- **AV / malware scanning** — deferred; the proxy upload path is the marked future interception seam.
- **Content-addressed storage / hard `sha256` dedup** — beyond optional soft detection.
- **Evidence supersession / versioning chains; soft-void of worked evidence** — pristine hard-delete only; bytes immutable.
- **Object Lock retention-application** — the bucket carries the capability (WI-0); applying retention/legal-hold at the authorisation gate is lifecycle work.
- **Per-tenant CMK / crypto-shred / per-tenant residency** — one shared CMK and a single region for MVP; a recorded, compliance-visible tradeoff.
- **In-band S3 object deletion on row delete** — orphaned bytes are reconciliation-sweep territory (deferred).

---

## 10. Dependencies / decision notes

**Verify before build (the one open precondition):**
- **`AuditEvent` actor durability (#7).** The "evidence outlives its uploader" guarantee assumes `AuditEvent` snapshots durable actor identity (name/email at write time), not just a membership-resolvable `user_id` FK — otherwise a departed employee's upload becomes unattributable. Inspect the `AuditEvent` model. If it stores an FK only, that is a cross-cutting audit-model gap beyond this sprint that this durability claim depends on; surface it rather than working around it.

**Reconciled against live DDL (do not re-verify):**
- `evidence` column set, RLS, and FKs — pinned (`\d evidence`). → Phase A needs **no migration**.
- `assessment_item_evidence` — four columns, `tenant_id` + RLS present, all FKs CASCADE, **no `UNIQUE (item_id, evidence_id)`** (`\d assessment_item_evidence`). → the WI-6 migration.

**Additive schema deltas this sprint:**
- Phase A: **none.**
- Phase B (`evidence_link_migration.py`): add `UNIQUE (item_id, evidence_id)`; drop `ix_…_item_id`; keep `ix_…_evidence_id`.
- New action strings: `evidence.created`, `evidence.deleted`, `evidence.access` (Phase A); `evidence.linked`, `evidence.unlinked` (Phase B). All new.

**Integration seams:**
- `assemble_aiia_items` (WI-9) and the `assessment_service.py` pristine predicate (WI-8) are shared AIIA code — extend in place, re-run their tests.
- `require_governance_role(...)` must accept role sets: `{system_owner, contributor}` for writes; all five for reads. Confirm the signature.
- The storage helper's dual client (internal put vs public presign) is the MinIO-across-Compose fix; in prod both resolve to the AWS endpoint.

**Locked decisions (do not relitigate):**
- Proxied upload, **put-before-transaction**; presigned-PUT + checksum is the deferred scale seam.
- Hardened presigned **download** (attachment + safe type + public-endpoint signing), audited on issuance.
- **Disposition-gated** linking; transitive evidence→control; evidence outside the §1.5 provenance machine.
- **Single guarded** pristine delete; pristine predicate extended to evidence links.
- SSE by policy; tenant-prefixed keys; one shared CMK for MVP.
- Object Lock capability at bucket creation; retention application deferred.

**Optional hardenings:** a dedicated cookieless download origin for evidence bytes; `bigint` `size_bytes` if the upload cap is ever raised past the `integer` ceiling (~2.1 GB).

---

## 11. Implementation contract

### Storage helper (WI-1)

```
storage.put_object(bucket, key, fileobj, *, sse_mode, sse_kms_key_id, original_filename)
    -> version_id            # SSE applied by policy; sets x-amz-meta-original-filename
storage.presign_get(bucket, key, version_id, *, ttl, filename, content_type)
    -> url                   # ResponseContentDisposition='attachment; filename="..."'
                             # ResponseContentType neutralised for non-safe types
                             # signed against the PUBLIC endpoint client
storage.delete_object(bucket, key, version_id | None)   # by version when set, else by key
```

### Upload (WI-2) — external put BEFORE the DB transaction

```
1. Pre-check: ctx.tenant_id present. Reject size > cap (413) / 0 bytes (422).
2. evidence_id = uuid_pk(); key = f"{ctx.tenant_id}/evidence/{evidence_id}"
3. sha256 = hash_pass(spooled_upload)            # NO DB, NO transaction
4. version_id = storage.put_object(bucket, key, spooled_upload,
                    sse_mode=..., original_filename=upload.filename)   # no connection held
5. OPEN short tenant transaction:
     INSERT evidence(id=evidence_id, tenant_id=ctx.tenant_id,
                     title=title or upload.filename, s3_bucket=bucket, s3_key=key,
                     s3_version_id=version_id, content_type=upload.content_type,
                     size_bytes=size, sha256=sha256, uploaded_by_user_id=ctx.user_id)
     stage AuditEvent(evidence.created)
   COMMIT
6. COMMIT failure -> storage.delete_object(bucket, key, version_id); re-raise   # compensate
```

### Pristine delete (WI-4) — single guarded statement

```
DELETE FROM evidence
 WHERE id = :id
   AND NOT EXISTS (SELECT 1 FROM assessment_item_evidence WHERE evidence_id = :id);
-- RLS scopes to ctx.tenant_id automatically
-- 0 rows -> 409 (linked or absent); 1 row -> stage AuditEvent(evidence.deleted); COMMIT
```

### Link / unlink (WI-7) — transactions, gated `{system_owner, contributor}`

```
LINK:
1. Load item (RLS). item.provenance == AI_SUGGESTED -> 409 (disposition required).
2. INSERT assessment_item_evidence(item_id, evidence_id, tenant_id=ctx.tenant_id)
     # UNIQUE(item_id, evidence_id) violation -> 409
     # evidence_id / item_id not RLS-visible -> fail closed (404)
3. stage AuditEvent(evidence.linked); COMMIT atomically

UNLINK (idempotent):
1. DELETE assessment_item_evidence WHERE item_id=:i AND evidence_id=:e   # RLS
2. 0 rows -> return 204, NO AuditEvent (no-op)
3. 1 row  -> stage AuditEvent(evidence.unlinked); COMMIT
```

### Configuration (`app/config.py`, WI-1)

```python
s3_endpoint_url: str | None        = "http://minio:9000"      # internal put; None => real AWS
s3_public_endpoint_url: str | None = "http://localhost:9000"  # presign host; None => same as internal (prod)
s3_region: str                     = "eu-west-1"
s3_access_key: str | None          = "minioadmin"   # dev only; unset in prod -> role chain
s3_secret_key: str | None          = "minioadmin"
s3_evidence_bucket: str            = "aigov-evidence"
s3_use_path_style: bool            = True            # MinIO path-style; virtual-host for real S3
s3_sse_mode: str | None            = None            # "AES256" | "aws:kms" | None; prod "aws:kms"
s3_sse_kms_key_id: str | None      = None            # required iff sse_mode == "aws:kms"
s3_presigned_get_ttl: int          = 300
evidence_max_upload_bytes: int     = 100 * 1024 * 1024   # under the size_bytes INTEGER ceiling
```

### API (under `/v1`; `tenant_id = ctx.tenant_id`; schemas in `app/schemas/`)

| Endpoint | Method | Purpose | Phase | Gate |
|---|---|---|---|---|
| `/v1/evidence` | POST (multipart) | Upload → S3 → row (no linking) | A | `{system_owner, contributor}` |
| `/v1/evidence` | GET | Paginated repository + `link_count` | A | all five roles |
| `/v1/evidence/{id}` | GET | Metadata + presigned download (audited) | A | all five roles |
| `/v1/evidence/{id}` | DELETE | Pristine guarded delete | A | `{system_owner, contributor}` |
| `/v1/assessments/{aid}/items/{item_id}/evidence-links` | POST | Link (disposition-gated) | B | `{system_owner, contributor}` |
| `/v1/assessments/{aid}/items/{item_id}/evidence-links/{evidence_id}` | DELETE | Unlink (idempotent) | B | `{system_owner, contributor}` |

### Audit action strings

`evidence.created`, `evidence.deleted`, `evidence.access` (Phase A); `evidence.linked`, `evidence.unlinked` (Phase B). All new, `entity.verb`, committed atomically (no-op unlink excepted).

---

## 12. Execution protocol

1. **Read before writing.** Study `provision_member`/`provision_tenant` for the transaction/audit idiom — **then invert it**: the S3 put runs *before* the transaction, not inside it. Study an `assessment_item_control` link endpoint (the link template), `assemble_aiia_items` (the surfacing locus), the `assessment_service.py` pristine-delete path, an existing `app/routers/v1/` router, and `app/config.py`. Match the conventions.
2. **Additive only.** Phase A touches no existing table. Phase B adds one junction migration and extends two shared functions (`assemble_aiia_items`, the pristine predicate) — extend in place, do not fork.
3. **Two transactional shapes, kept apart.** Upload = external-put-then-short-transaction with S3 compensation; link/unlink/delete = pure-DB atomic audit. The link path must never reach for the upload choreography.
4. **Sequence:** WI-1 → WI-2 → WI-3 → WI-4 → WI-5 (Phase A, shippable); then WI-6 → WI-7 → WI-8 → WI-9 (Phase B). WI-0 (Terraform) in parallel.
5. **One gate per route. SoD is not re-checked** — trust assignment-time enforcement.
6. **Honour the non-negotiables everywhere:** never hold a connection across the put; never check-then-delete; never link an `AI_SUGGESTED` item; never store an object unencrypted; never sign a presigned URL against the internal endpoint; never serve evidence inline (always attachment + safe type).
7. **Keep the hash pass pure of DB.** No connection open during hashing or the put.
8. **Verify `AuditEvent` actor durability (§10) before depending on it.** Invent no columns or signatures; confirm against the codebase where a fact is unverified.

---

## 13. Validation protocol

**Unit (storage helper, pure):** SSE params applied on every put; `presign_get` emits `ResponseContentDisposition=attachment` + neutralised content-type + the public-endpoint host; key layout `{tenant_id}/evidence/{id}`; `delete_object` targets a version when supplied, a key when null; two-pass hash equals the known `sha256` of a fixture, including a file large enough to trigger multipart.

**Integration (upload, WI-2):** a successful upload yields one S3 object + one row + one `evidence.created`, atomic, with the connection never held across the put (assert via a concurrency/held-connection probe); injected commit failure leaves no row and no S3 object (compensation fired); oversize → 413 during the hash pass; zero-byte → 422; `s3_version_id` populated when the bucket is versioned, null-safe when not.

**Integration (repository, WI-3):** listing paginates and reports correct `link_count`; detail returns a working attachment-forced presigned URL and stages `evidence.access`; an `image/svg+xml` artifact cannot render inline through the issued URL.

**Integration (delete, WI-4):** pristine delete removes the row and stages `evidence.deleted`; a concurrent committed link makes the guarded delete affect zero rows → 409 (never a strip); deleting absent/other-tenant id → 404/409.

**Integration (link/unlink, WI-7 — Phase B):** link to `AI_SUGGESTED` → 409; to a dispositioned/`CATALOGUE_CURATED` item → success + `evidence.linked`; duplicate → 409 (the new unique); cross-tenant `evidence_id` → fail-closed; unlink no-op → 204, no audit; real unlink → `evidence.unlinked`.

**Integration (propagation + shared delete, WI-8/WI-9 — Phase B):** a feeder item's evidence links surface into the AIIA read tagged with the source, untouched; an item with an evidence link blocks pristine-delete of its assessment/feeder (409); the **existing AIIA/feeder pristine-delete suite re-runs green**.

**Authorisation:** upload/delete/link/unlink → 403 for any non-`{system_owner, contributor}`; list/detail → 200 for all five governance roles; no path runs on a `BYPASSRLS` role.

**Migration (WI-6):** post-migration `\d assessment_item_evidence` shows `UNIQUE (item_id, evidence_id)`, no `ix_…_item_id`, and a retained `ix_…_evidence_id`; downgrade restores the prior state.

**End-to-end:** upload → appears in the repository with `link_count = 0` → link to an item → appears on the item read and (via a feeder) on the AIIA read → pristine-delete of the assessment blocked → unlink → evidence-row delete succeeds → every step carries its audit event.