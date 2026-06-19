# Evidence Repository — Backend Design Proposal (v2)

**Feature:** Central evidence repository (EVD-1, EVD-2; AIIA-5) — file upload, S3-backed store, reuse across assessment items, immutable audit
**Scope:** Additive feature on the existing multi-tenant governance platform — not a greenfield redesign. This is **Sprint 4**, the evidence/upload path the AIIA design (`AIIA_DESIGN.md` §12) deferred.
**Status:** v2.1 — second review round incorporated (15 findings, Appendix B); both evidence tables now reconciled against live DDL. Headline changes vs v1: upload restructured so **no DB transaction is held across the S3 put** (#1); evidence delete is a **single guarded statement**, not check-then-delete (#2); download forces `Content-Disposition: attachment` + safe content-type (#4); evidence-linking now **requires disposition** (#8). The `\d assessment_item_evidence` precondition (#3) is **discharged** — `UNIQUE (item_id, evidence_id)` confirmed absent (Phase B adds it; same migration drops the now-redundant single-column `item_id` index), `tenant_id` + RLS confirmed present. The one remaining hard precondition is `AuditEvent` actor durability (#7).
**Out of scope this sprint:** evidence assignment with due dates/reminders (EVD-3, post-MVP); freshness/expiry notifications (EVD-4 — `expires_at` seam present, unused); export/audit pack (EXP-1 — consumes evidence; the presigned-download primitive is the seam); AV/malware scanning (the proxy upload path is the marked interception seam, §12); content-addressed storage / hard sha256 dedup; evidence supersession / versioning chains; soft-void of worked evidence (pristine hard-delete only); Object Lock **retention-application** logic; per-tenant CMK / crypto-shred / per-tenant residency (§12, deliberate MVP tradeoff)

**Decisions:** all resolved (§1.1, §13, Appendix B). Phase A migration: **none** (table reconciled against live DDL). Phase B migration: `evidence_link_migration.py` — adds `UNIQUE (item_id, evidence_id)` (verify absent via `\d assessment_item_evidence` first).

---

## 1. Overview

This sprint builds the full backend for the evidence repository: upload a file, store the bytes in S3, record a pointer row in Postgres, and link that evidence to one or more assessment items. Evidence is **reusable** — one uploaded artifact (a DPA, a model card, a security certification) satisfies many items across many assessments without re-uploading. This is what turns an assessment from a self-declaration into an audit-ready record.

The design leans on existing foundations: the first-class `evidence` table (pointer + `sha256`, live), the `assessment_item_evidence` junction (`tenant_id` + RLS already added by the AIIA migration), the `assessment_item_control` link/unlink endpoints as a structural template, the tenant-plane atomic-audit rule, and the read-time feeder assembly.

**Two transactional shapes, and neither is the Cognito six-step pattern (revised in v2).** The upload path makes an external call (S3), but — unlike `provision_tenant`, whose Cognito calls are sub-second — an S3 put of up to the 100 MiB cap is a multi-second byte push. So the upload does **not** hold a DB transaction across the put: it hashes and puts to S3 with no connection held, then opens a short transaction for the row + audit and commits, compensating the S3 object on commit failure (§4.3). The link/unlink path is pure DB and follows the tenant-plane rule (stage the `AuditEvent`, commit atomically with the rows). The two shapes must not be conflated.

Work splits into **Phase A** (upload + repository — a demoable vertical slice: put evidence in, get it back) and **Phase B** (item linking + propagation). All link writes — including initial-link-on-upload — live in Phase B, behind the uniqueness guard and the link endpoints (#5). The only genuinely new infrastructure (boto3, MinIO-in-dev, presigned URLs, the streaming hash, the compensation path) lives in Phase A.

### 1.1 Resolved design decisions

| Decision | Resolution |
| --- | --- |
| Upload transport | **Proxied through the API**, but the put runs **outside any DB transaction** — UUID generated app-side, hash + S3 put first, then a short row+audit transaction (#1). Atomic; S3-compensated on commit failure. Presigned-PUT + S3-enforced checksum is the documented **scale seam**, not MVP |
| Download transport | **Presigned GET**, short TTL, authorised by the RLS read of the `Evidence` row — bytes never touch the API on the read path. Forced `Content-Disposition: attachment` + safe content-type (#4); presigned against a **public** endpoint distinct from the internal put endpoint (#6) |
| `sha256` semantics | **Integrity + lookup, not uniqueness** — schema-confirmed (nullable, non-unique `ix_evidence_sha256`). Soft dedup *detection* only; no constraint to fight |
| Evidence-row hard delete | **Single guarded statement** — `DELETE … WHERE NOT EXISTS (link)`, zero rows → 409 (#2). Load-bearing at the app layer because the junction FK is `ON DELETE CASCADE` (the DB will not block it); the guard must be atomic, not check-then-delete |
| Uploader durability | `uploaded_by_user_id` is `ON DELETE SET NULL`; the actor of record is the `evidence.created` AuditEvent — **conditional on AuditEvent snapshotting durable actor identity** (name/email at write), not a membership-resolvable FK (#7, verify) |
| Provenance | Evidence sits **outside** the §1.5 provenance machine — a user-uploaded artifact, not item content with a system default. No `ProvenanceConfidence` tag; the `evidence.*` audit trail is its defensibility record |
| Evidence → control | **Transitive via items only** — no direct evidence↔control table. Framework satisfaction derives from the control-library cross-map (`AIIA_DESIGN.md` §8.12) |
| Disposition gate on linking | **Requires disposition (revised in v2).** Reject an evidence-link on a still-`AI_SUGGESTED` item (409, "confirm or amend first"); section-prompt (`CATALOGUE_CURATED`) items exempt, as in the authoring gate. Evidence is substantiation — heavier than a control link — so it belongs behind the disposition gate even though control-links do not (#8) |
| Original filename | **Stashed in S3 object metadata** on the put (`x-amz-meta-original-filename`); no PG column. Drives the `Content-Disposition` download name (#4, #10) |
| Encryption at rest | **SSE applied by the storage layer on every put, by policy** — never per-caller. SSE-KMS in prod (one CMK; per-tenant keys / crypto-shred deferred — §12) |
| Bucket immutability | **Object Lock enabled at bucket creation** (Terraform; versioning auto-on), **no blanket default retention**. Selective WORM applied at the authorisation gate — lifecycle work, not this sprint |
| Credentials | Static keys are a **dev-only** convenience; prod leaves them unset → boto3 instance/role chain |
| Junction uniqueness | Phase B **adds `UNIQUE (item_id, evidence_id)`** — **confirmed absent** via live `\d` (#3). Same migration **drops the now-redundant `ix_assessment_item_evidence_item_id`** (the composite unique covers `item_id` as leftmost prefix); the `evidence_id` index stays (load-bearing for the delete guard + link-count) |
| Pristine-delete predicate | **Extended to count evidence links** — edits the shared AIIA/feeder delete path (`assessment_service.py`), so **not purely additive**: re-run the AIIA/feeder delete tests (#9) |
| Feeder propagation | Evidence links **travel with surfaced feeder items** in the read-time assembly (parity with control links; `AIIA_DESIGN.md` §9.2) — borrowed at read time, never copied |
| Download access auditing | **Audited** — minting a presigned GET is a chain-of-custody event for evidence, not a plain read; write `evidence.access` on issuance (#11) |

---

## 2. Reused components (existing foundations)

- **First-class `evidence` table (live).** Pointer (`s3_bucket` / `s3_key` / `s3_version_id`) + `sha256` + the `expires_at` seam. Reconciled column-for-column against the live `\d evidence` output (§3); no ALTER this sprint. Invariant 6 (bytes in S3, pointer in PG) is already the contract.
- **`assessment_item_evidence` junction (live).** Item↔evidence M:N, `tenant_id` + RLS added by the AIIA migration. The reuse mechanism: one `Evidence` row referenced by many join rows across many items/assessments. *(Junction-internal constraint set unverified — §3, #3.)*
- **Control-link endpoint shape (`assessment_item_control`).** The structural template for evidence link/unlink — same item↔X join, duplicate→409, no `lock_version`, attribution in AuditEvents (no `created_by`/timestamps on the join). The one deliberate divergence: evidence-linking is disposition-gated, control-linking is not (§9.1, #8).
- **Tenant-endpoint contract.** Router in `app/routers/v1/`, registered under `/v1`; `get_tenant_db` plus exactly one of `require_role` / `require_governance_role`; `tenant_id` from `ctx.tenant_id`; schemas in `app/schemas/`.
- **Tenant audit plane.** Link/unlink stage an `AuditEvent` committed atomically with the rows; the immutability trigger and RLS cover the junction. The durable-actor property is depended upon (#7).
- **Compensation discipline (STATE §4).** Reused in spirit, not verbatim: the upload compensates the S3 object on commit failure, but the external put runs *before* the transaction, not inside it (§4.3, #1). The proxy upload path is also the marked **AV-scan interception seam** (§12, #12).
- **Read-time feeder assembly (`AIIA_DESIGN.md` §9.2).** `GET /assessments/{aiia_id}` assembles native ∪ surfaced feeder items, tagging `source_assessment_id` + `type`. Extended here to carry evidence links on surfaced items.
- **Governance role model (PRD §4.9).** Tenant-scoped; SoD is a conflict matrix at assignment. These endpoints consume roles for gating and carry no SoD logic. PRD §4.9.1 defines Contributor as "supplies requested evidence/facts" — evidence writes map to `{system_owner, contributor}`.

---

## 3. Data model

No new model. The `evidence` table and the `assessment_item_evidence` junction both exist; Phase A touches neither, Phase B adds one constraint to the junction.

**DDL verification status (revised in v2, #3).** Distinguish what the live `\d evidence` output pins from what is inferred:
- **Verified from `\d evidence`:** the full `evidence` column set (→ "no Phase A migration" stands); the RLS `tenant_isolation` policy; the `tenant` FK (`CASCADE`) and `uploaded_by_user_id` FK (`SET NULL`); and — from the reverse-FK listing — that `assessment_item_evidence.evidence_id` is `ON DELETE CASCADE` (→ inv 4's premise holds; it is not `RESTRICT`).
- **Verified from `\d assessment_item_evidence` (round 3):** four columns only (`id`, `item_id`, `evidence_id`, `tenant_id` — no `created_by`/timestamps, confirming attribution-in-audit); `tenant_id` + RLS present; all three FKs `ON DELETE CASCADE`; and **no `UNIQUE (item_id, evidence_id)`** — only non-unique single-column indexes on `item_id` / `evidence_id` / `tenant_id`. The Phase B migration adds the composite unique. **Index hygiene:** once that unique lands, `ix_assessment_item_evidence_item_id` is redundant (the composite serves `item_id` as leftmost prefix) and is dropped in the same migration; `ix_assessment_item_evidence_evidence_id` stays — the reverse lookup `WHERE evidence_id = :id` backs both the §8.4 delete guard and the §6 link-count, and the composite cannot serve an `evidence_id`-leading query.
- **One remaining hard precondition:** `AuditEvent` actor durability (#7) — unaddressed by either `\d`, a different table.

**`evidence`** *(table exists — reconciled against live `\d evidence`; **no ALTER this sprint**)*
- `id` (uuid PK — **generated app-side via `uuid_pk()` before the S3 put**, §4.3), `tenant_id` (uuid, FK → `tenant` `ON DELETE CASCADE`, indexed) — present
- `title` (varchar 255, NOT NULL) — the human label. No `original_filename` column; default `title` to the uploaded filename when none supplied, and **stash the raw filename in S3 object metadata** (#10).
- `s3_bucket` (NOT NULL), `s3_key` (varchar 1024, NOT NULL) — present
- `s3_version_id` (varchar 255, **nullable**) — captured from the put when versioning is on. Compensation deletes by *version* when set, by *key* when null (§8.6).
- `content_type` (varchar 120, nullable) — recorded from the multipart part; **not** hard-allow-listed, which is exactly why the download path must neutralise inline rendering (§5, #4).
- `size_bytes` (**integer**, nullable) — implicit **~2.1 GB ceiling**; the upload cap sits well under it. Exceeding it is a `bigint` migration.
- `sha256` (varchar 64, nullable, non-unique `ix_evidence_sha256`) — **integrity + lookup, not uniqueness**. Server-computed (§4.3).
- `uploaded_by_user_id` (uuid, nullable, FK → `app_user` `ON DELETE SET NULL`) — evidence outlives its uploader; the durable actor lives in the AuditEvent **iff** that event snapshots identity (§8.10, #7).
- `expires_at` (timestamptz, nullable) — the **EVD-4 seam**; unused this sprint.
- `created_at`, `updated_at` — present.
- **RLS:** `tenant_isolation` `USING (tenant_id = current_setting('app.current_tenant'))`. USING-only is sufficient — Postgres applies the same predicate as `WITH CHECK` on INSERT.

**`assessment_item_evidence`** (item ↔ evidence M:N junction — exists)
- `id`, `item_id` (FK → `assessment_item`, `ON DELETE CASCADE`), `evidence_id` (FK → **`evidence`**, `ON DELETE CASCADE` — verified, §3) — present
- `tenant_id` + RLS — **present (verified, round 3)**. Four columns total; no `created_by`/timestamps, so attribution stays in the `evidence.linked`/`evidence.unlinked` AuditEvents.
- No `created_by` / timestamps on the join — attribution stays in the `evidence.linked` / `evidence.unlinked` AuditEvents, parity with the control-link join.
- **ALTER (Phase B): add `UNIQUE (item_id, evidence_id)`** (confirmed absent, round 3) — the §11 duplicate→409 depends on it. Same migration **drops `ix_assessment_item_evidence_item_id`** as redundant under the new composite; keeps `ix_assessment_item_evidence_evidence_id`.

**Reconciliation note — the `uri` stub is superseded.** `AIIA_DESIGN.md` §12 anticipated a `label`/`uri` link with a render-time sanitisation concern. The implemented model is pointer-based, so there is no stored URL — but the XSS surface did not vanish, it **moved to the file body** and is closed on the download path instead (forced attachment + safe content-type, §5, #4), not by the absence of a `uri` column.

---

## 4. Storage layer & the upload path

The spine of this feature. The bytes never enter Postgres; the integrity hash never comes from the client; and (v2) the multi-second S3 put never sits inside a DB transaction.

### 4.1 Configuration (`app/config.py`) — first S3/boto3 wiring in the project

```python
# --- Object storage (evidence artifacts) ---
# INTERNAL endpoint — API → S3/MinIO for puts. None => real AWS S3.
s3_endpoint_url: str | None = Field(default="http://minio:9000")
# PUBLIC endpoint — used ONLY to mint presigned URLs the browser will fetch.
# SigV4 signs the host, so this must match what the browser hits (#6).
# None => fall back to s3_endpoint_url (correct in prod, where both are the AWS endpoint).
s3_public_endpoint_url: str | None = Field(default="http://localhost:9000")
s3_region: str = Field(default="eu-west-1")
# Static creds are a DEV convenience only. Leave unset in prod so boto3
# resolves the instance/role chain (IRSA / ECS task role). Never ship long-lived keys.
s3_access_key: str | None = Field(default="minioadmin")
s3_secret_key: str | None = Field(default="minioadmin")
s3_evidence_bucket: str = Field(default="aigov-evidence")
# Path-style for MinIO; virtual-host for real S3.
s3_use_path_style: bool = Field(default=True)
# Encryption at rest. dev MinIO: off; prod: "aws:kms" for key-level auditability.
s3_sse_mode: str | None = Field(default=None)         # "AES256" | "aws:kms" | None
s3_sse_kms_key_id: str | None = Field(default=None)   # required iff sse_mode == "aws:kms"
# Short-lived presigned GET for download.
s3_presigned_get_ttl: int = Field(default=300)
# Upload ceiling — must stay under the size_bytes INTEGER limit (~2.1 GB).
evidence_max_upload_bytes: int = Field(default=100 * 1024 * 1024)  # 100 MiB
```

The split endpoint (#6) is the dev-critical addition: in Docker Compose the API reaches MinIO at `minio:9000` while the browser reaches it at `localhost:9000`; a URL presigned against the internal host fails SigV4 validation when the browser fetches it, and the host cannot be rewritten without breaking the signature. Two boto3 clients — one bound to the internal endpoint for puts, one to the public endpoint for `generate_presigned_url`. In prod both resolve to the AWS endpoint, so the public field is `None`.

### 4.2 Storage helper (`app/services/storage.py`)

Centralised boto3 wiring, mirroring `cognito_helpers.py`: internal + presign client factories; `put_object(...)` that applies SSE by policy, sets `x-amz-meta-original-filename`, and returns the `VersionId`; `generate_presigned_get(...)` at the configured TTL with `ResponseContentDisposition=attachment; filename="…"` and a neutralised `ResponseContentType` for non-safe types (§5); tenant-prefixed key layout `{tenant_id}/evidence/{evidence_id}`.

### 4.3 Evidence service (`app/services/evidence_service.py`) — upload ordering (revised in v2, #1)

S3 is external **and slow**, so the put runs *before* the DB transaction, and the connection is held only for the row write:

```
1. Generate evidence UUID app-side (uuid_pk()); derive S3 key {tenant_id}/evidence/{uuid}
2. Hash pass over the spooled upload — NO DB, NO transaction
3. S3 put_object (SSE by policy, original-filename metadata) → VersionId   [still no DB connection held]
4. Open a SHORT tenant transaction: INSERT evidence row (pre-generated id, sha256, version_id)
                                     + stage evidence.created AuditEvent  → commit
5. Commit failure → best-effort delete the S3 object/version; re-raise
```

The connection is held only across step 4 (one INSERT + one audit insert + commit), never across the hash or the put. This trades a slightly wider orphan window — a crash between steps 3 and 4 leaves an S3 object with no row — for not serialising multi-second uploads onto the connection pool. Orphans (here and on compensation failure) are reconciliation-sweep territory (deferred); the objects are UUID-keyed and referenced by nothing.

The link/unlink path is the *other* shape (no external call): pre-check, stage the join + `AuditEvent`, `flush`, let `get_tenant_db` commit atomically.

**`sha256` is server-computed.** Note (#15): this is **not** stream-through hashing. Starlette's `UploadFile` spools to a local `SpooledTemporaryFile`, and boto3's `upload_fileobj` may read it non-sequentially for multipart, which would corrupt a read-through digest — so the bytes are spooled to local disk and read in **two sequential passes** (hash, then `seek(0)`, then put). The local spool is a minor disk-pressure surface under concurrent uploads (bounded by the upload cap × concurrency); worth a tmpfs/size note in deploy config, not a design blocker. "Buffer nothing into the DB" is the accurate invariant, not "stream it."

---

## 5. Transport — proxied upload, hardened presigned download

**Upload: proxied through the API for MVP**, with the put outside any transaction (§4.3, #1). The driver is defensibility — the `sha256` is integrity evidence that the stored artifact is the one assessed, and a server-owned hash is the only kind that stands. Single-phase, atomic at the DB.

**Scale seam (documented, not built):** presigned **PUT** with `ChecksumAlgorithm=SHA256` *enforced* by S3 — S3 rejects any object whose bytes don't match the declared checksum, so the stored hash stays trustworthy even though the API never sees the bytes. Two-phase, dependent on S3/MinIO checksum parity; an extension, not a rewrite.

**Download: presigned GET, hardened (revised in v2, #4, #6).** Server authorises via the RLS read of the `Evidence` row — readable → short-TTL presigned URL; RLS-hidden → nothing. Three required properties:
- **`ResponseContentDisposition: attachment; filename="<original>"`** — forces download rather than inline render, closing the stored-XSS path that an un-allow-listed `text/html` / `image/svg+xml` artifact would otherwise open in the bucket origin, and giving the file a real name instead of a UUID blob.
- **Neutralised `ResponseContentType`** for non-safe types (serve `application/octet-stream`) as defence in depth behind the attachment header.
- **Presigned against `s3_public_endpoint_url`** so the signed host matches what the browser fetches (#6).
- *Hardening tier (not MVP): a dedicated cookieless download origin for evidence bytes.*

**Issuing a presigned GET is audited** (`evidence.access`, #11) — for evidence, minting a time-boxed direct-to-bytes URL is a chain-of-custody event, closer to EVD-2's "export" than to a plain read. Lightweight: actor + evidence id + timestamp.

---

## 6. API endpoints

| Method + path | Purpose | Gate |
| --- | --- | --- |
| `POST /v1/evidence` (multipart) | Upload → S3 → `Evidence` row. **No initial link** (linking is Phase B, #5) | `{system_owner, contributor}` |
| `GET /v1/evidence` | Central repository listing — **paginated**, with per-item **link-count / usage** (#14) | any governance role |
| `GET /v1/evidence/{id}` | Metadata + short-TTL presigned **GET** URL (attachment, safe type); writes `evidence.access` (#11) | any governance role |
| `DELETE /v1/evidence/{id}` | Pristine-only hard delete via the single guarded statement (#2) | `{system_owner, contributor}` |
| `POST /v1/assessments/{aid}/items/{item_id}/evidence-links {evidence_id}` | Link existing evidence; disposition-gated (#8); duplicate → 409 | `{system_owner, contributor}` |
| `DELETE .../items/{item_id}/evidence-links/{evidence_id}` | Unlink (idempotent; no-op writes no audit, #15) | `{system_owner, contributor}` |

Item reads surface evidence links alongside control links — in the item read and, for feeder items, in the read-time assembly (§9). Reads use any of the five governance roles; writes `{system_owner, contributor}`.

---

## 7. Tenancy, RLS & isolation

Entirely tenant-plane, on `irontrustai_app` / `get_tenant_db`, `NOBYPASSRLS`, **no new DB role**, no plane crossing. Both `evidence` and `assessment_item_evidence` are RLS-scoped, so a tenant resolves only its own evidence rows — and therefore only its own S3 keys. Tenant-prefixed keys add a second fence: a guessed key yields nothing without an RLS-readable row to mint a presigned URL from.

`tenant_id` is always `ctx.tenant_id`, never a body field. The `evidence_id` in a link request is **RLS-validated** — you can only link evidence you can read; a cross-tenant `evidence_id` is invisible and the join insert finds nothing to reference (fail-closed). S3-side, the storage layer applies SSE on every put by policy.

---

## 8. Constraints & invariants

1. **Bytes in S3 only.** Postgres holds the pointer + `sha256` (inv. 6). **Buffer nothing into the DB**; bytes spool to local disk and are read in two passes (§4.3, #15) — not stream-through hashing.
2. **`sha256` is server-computed, never client-set.** The hash is integrity evidence.
3. **Evidence bytes are immutable post-upload.** Re-evidencing is a new row with a new hash — which keeps `expires_at` / supersession a clean post-MVP seam.
4. **Evidence-row delete is a single guarded statement.** `DELETE FROM evidence WHERE id = :id AND NOT EXISTS (SELECT 1 FROM assessment_item_evidence WHERE evidence_id = :id)`; zero rows → 409. **Not check-then-delete** — the junction's `ON DELETE CASCADE` means a concurrent link insert would otherwise be silently stripped (STATE inv 14; #2). Load-bearing because the DB permits what the app must restrict (inverse of the reference-FK `RESTRICT` pattern).
5. **Assessment/item pristine-delete predicate extended to count evidence links** — an item with an evidence link is "worked." This edits the **shared** AIIA/feeder delete path (`assessment_service.py`), so it is not purely additive: re-run the AIIA/feeder pristine-delete tests (#9). Preserve that path's existing atomicity.
6. **Upload put runs outside the transaction; compensation by version-or-key.** Connection held only for the row+audit write (#1). On commit failure, delete by version when `s3_version_id` is set, by key when null (#6 prior).
7. **Audit atomicity.** Link/unlink stage the `AuditEvent` in the same transaction. Upload stages `evidence.created` inside the short row transaction (step 4). A **no-op unlink writes no AuditEvent** (parity with no-op PATCH; #15). Never commit audit separately.
8. **`tenant_id` from context, never body** (inv. 3). The `evidence_id` in a link request is RLS-validated.
9. **SSE by policy.** Encryption at rest is a property of the storage layer, on every put; not an option an individual call can omit.
10. **Evidence is outside the §1.5 provenance machine; uploader durability depends on the audit model.** No `ProvenanceConfidence` tag. The "evidence outlives its uploader" claim holds **only if** `AuditEvent` snapshots durable actor identity (name/email at write), not just a membership-resolvable `user_id` FK — otherwise a departed employee's upload becomes unattributable (#7). Verify; if absent, it is an audit-model gap beyond this sprint that this claim depends on.
11. **Evidence → control is transitive via items only.** No direct evidence↔control table; framework satisfaction derives from the control-library cross-map.
12. **Evidence-linking is disposition-gated (revised in v2).** Reject a link on a still-`AI_SUGGESTED` item (409); `CATALOGUE_CURATED` section-prompt items exempt, as in the authoring gate. Deliberately asymmetric with control-links: evidence is substantiation, and re-pointing proof under a later amendment is worse than re-pointing a mapping (#8).
13. **Duplicate link integrity.** `UNIQUE (item_id, evidence_id)` is a Phase B ALTER (verify absent, #3); DB-level, catch the violation → 409.
14. **Feeder propagation is reference, not copy.** Surfaced feeder items carry their evidence links untouched into the AIIA read; never written back. The read-time assembly is the single locus (inv. 16).
15. **No new DB role.** Tenant work runs on `irontrustai_app` (`NOBYPASSRLS`).
16. **Object Lock capability ≠ retention application.** The bucket carries Object Lock from creation; applying retention at the authorisation gate is lifecycle work, not this sprint — otherwise WORM collides with pristine-delete.

---

## 9. Linking & propagation

### 9.1 Link / unlink
Evidence-link is the control-link shape — a thin join, `POST` to create (duplicate → 409 via `UNIQUE (item_id, evidence_id)`, Phase B), `DELETE` to remove (idempotent; a no-op removal writes no audit, #15). No `lock_version` / `If-Match` — a join insert/delete is not a provenance transition.

**Disposition gate (revised in v2, #8).** An evidence-link is **rejected (409) on a still-`AI_SUGGESTED` item** — "confirm or amend the proposed risk first" — and allowed on every dispositioned or non-proposal item (`USER_PROVIDED`, `CATALOGUE_CURATED`, `USER_CONFIRMED`, `USER_AMENDED`), exactly mirroring disposition-before-authoring (STATE inv 13). This is a conscious asymmetry with control-links, which carry no such gate: evidence is the defensibility artifact, and attaching a certification to a proposed risk that is later amended into a *different* risk silently re-points the substantiation. The right consistency axis is disposition-before-substantive-work, not the join's mechanics.

### 9.2 Propagation (reference, not copy)
Evidence links ride the existing read-time assembly. `GET /assessments/{aiia_id}` assembles native ∪ surfaced feeder items, each tagged `source_assessment_id` + `type`; this sprint ensures a surfaced feeder item carries its evidence links untouched, as it carries control links. Nothing is copied or written back. The §8.5 predicate extension means a feeder item with an evidence link blocks the feeder's pristine-delete — and, per #9, that extension touches shared AIIA/feeder code, so the existing delete tests must be re-run, not just the new evidence ones.

---

## 10. Sequencing

**Phase A — storage foundation + repository (demoable).** No schema migration (the `evidence` table is reconciled against live DDL, §3). Config fields incl. the split public/internal endpoint; `storage.py` (internal + presign clients, SSE-by-policy put with original-filename metadata, hardened presigned GET); `POST /v1/evidence` (UUID app-side → hash → put → short row+audit transaction, §4.3) **with no linking**; paginated `GET /v1/evidence` with link-count; `GET /v1/evidence/{id}` (presigned download + `evidence.access`); the single-guarded pristine evidence-row delete; `evidence.created` / `evidence.deleted` / `evidence.access` audit.

**Phase B — linking + propagation.** Junction reconciled (round 3): `tenant_id` + RLS present, `UNIQUE (item_id, evidence_id)` absent — precondition discharged. `evidence_link_migration.py` adds the composite unique **and drops the now-redundant `ix_assessment_item_evidence_item_id`**. Then: item evidence-link / unlink endpoints (disposition-gated, #8); the read-time-assembly extension; the pristine-delete predicate extension (shared-code — re-run AIIA/feeder delete tests, #9); item-read surfacing; `evidence.linked` / `evidence.unlinked` audit.

**Bucket provisioning (Terraform `infra/`, not Alembic).** Prod bucket created with Object Lock enabled (versioning auto-on), no default retention, governance mode. Dev MinIO: versioning on, Object Lock unnecessary. Alongside Phase A.

**Seams preserved now:** `expires_at` (EVD-4); presigned-PUT + checksum (upload scale path); Object Lock retention application (authorisation/lifecycle); the proxy upload path as the **AV-scan interception seam** (#12); export-pack consumption of the presigned-download primitive (EXP-1).

---

## 11. Edge & failure cases

- S3 put succeeds, then process dies before the row commits → orphaned object (wider window than v1 by design, #1); reconciliation-sweep territory (deferred). Commit *failure* → step-5 compensation deletes by version-or-key.
- Row staged, but this can't happen before the put now — the put precedes the transaction (§4.3).
- Duplicate bytes (same `sha256`) → soft detection via `ix_evidence_sha256`; default allows the row. No hard constraint.
- Duplicate link (same evidence on same item) → 409 via `UNIQUE (item_id, evidence_id)` (Phase B).
- Cross-tenant link attempt → fail-closed: `evidence_id` / `item_id` not RLS-visible.
- Link to a still-`AI_SUGGESTED` item → **409** (disposition required, §9.1, #8). Link to a dispositioned / section-prompt item → allowed.
- Concurrent delete vs link → the guarded `DELETE … WHERE NOT EXISTS` loses to a committed link (zero rows → 409), never strips it (#2).
- Oversized file → 413 against `evidence_max_upload_bytes`, enforced during the hash pass (not from a spoofable `Content-Length`). Empty / zero-byte → 422.
- `text/html` / `image/svg+xml` upload → stored fine; download forces `attachment` + neutral type, so it cannot render inline (#4).
- MinIO presigned URL → minted against `s3_public_endpoint_url`; fetching the internal-host variant would fail SigV4 (#6).
- Presigned URL expiry / clock skew → short TTL; `sha256` lets the client verify integrity.
- Bucket versioning disabled → `s3_version_id` null; compensation deletes by key (§8.6).
- Uploader later deleted → row survives (`SET NULL`); attribution comes from the `evidence.created` AuditEvent **iff** it snapshots identity (#7).
- No-op unlink (link absent) → 200/204, **no AuditEvent** (#15).

---

## 12. Intentionally deferred (post-MVP / later sprints)

- **Evidence assignment with due dates / reminders (EVD-3)** — post-MVP; no model touched.
- **Freshness / expiry notifications (EVD-4)** — `expires_at` present and unused; no scheduler.
- **Presigned direct-to-S3 upload** — the scale seam (§5); deferred because proxying lets the server own the hash.
- **AV / malware scanning** — deferred, but the **proxy upload path is the named interception seam** (#12): with presigned-direct *download*, scan-on-access is awkward, so scanning hooks at ingest, where bytes already flow through the API.
- **Content-addressed storage / hard `sha256` dedup** — beyond optional soft detection.
- **Evidence supersession / versioning chains, soft-void of worked evidence** — MVP is pristine hard-delete only; bytes immutable post-upload.
- **Object Lock retention-application logic** — capability provisioned at bucket creation; applying locks at the authorisation gate is lifecycle work.
- **Per-tenant CMK / crypto-shred / per-tenant residency (#13).** One shared CMK → no per-tenant key isolation and no crypto-shred on offboarding; a global `eu-west-1` satisfies "EU residency" but not the PRD §6 per-tenant residency *option*. Acceptable for an EU-only ICP at MVP — recorded as a deliberate, compliance-visible tradeoff, not an oversight.

### Next consumer (not post-MVP)
- **Export / audit pack (EXP-1, a Must)** — consumes evidence via the presigned-download primitive this sprint builds; the feeder-private export requirement (`AIIA_DESIGN.md` §9.2) reserves the seam. Its own sprint, the immediate downstream consumer.

---

## 13. Decisions resolved + migration

All previously-open decisions resolved (fixed in the design, not deferred):

1. **Upload ordering → put-before-transaction** (#1); connection never held across the S3 put.
2. **Evidence delete → single guarded statement** (#2), atomic against the junction CASCADE.
3. **`sha256` → integrity + lookup, not uniqueness** — schema-confirmed.
4. **Download → hardened presigned GET** (attachment + safe type + public-endpoint presign; #4, #6), audited on issuance (#11).
5. **Disposition gate on linking → required** (#8), deliberately asymmetric with control-links.
6. **Evidence → control → transitive via items only.**
7. **Uploader durability → conditional on AuditEvent actor snapshotting** (#7, verify).

**Migration set:**
- **Phase A: none.** The `evidence` table is reconciled against live DDL.
- **Phase B: `evidence_link_migration.py`** — add `UNIQUE (item_id, evidence_id)` to `assessment_item_evidence` (confirmed absent, round 3) **and drop the redundant `ix_assessment_item_evidence_item_id`** (keep `ix_…_evidence_id`). Set `down_revision` to your current head.

**Verify before build (hard preconditions):**
- ~~`\d assessment_item_evidence`~~ — **discharged (round 3):** `tenant_id`+RLS present, `UNIQUE (item_id, evidence_id)` absent.
- `AuditEvent` actor durability — does it snapshot name/email at write, or store a resolvable FK only (#7)? **The one open precondition.**

**Not an Alembic migration:** bucket provisioning (Object Lock at creation, versioning, no default retention) is Terraform `infra/`. AWS provider semantics for `object_lock_enabled` (create-time / ForceNew in many versions) re-checked when the bucket Terraform is written.

---

## Appendix A — Review disposition (round 1)

| # | Sev | Finding | Disposition |
| --- | --- | --- | --- |
| 1 | Blocking | Evidence table column set unknown | Resolved: matched against live DDL; no Phase A migration (§3) |
| 2 | Blocking | `sha256` uniqueness/dedup semantics | Resolved: integrity + lookup, non-unique index (§3, §8.2) |
| 3 | Blocking | Junction FK CASCADE — DB won't block deleting linked evidence | Resolved: app-level pristine gate load-bearing (§8.4) — *and made atomic in round 2, #2* |
| 4 | Should | Upload transport unresolved | Resolved: proxied; presigned-PUT+checksum the scale seam (§5) — *ordering corrected in round 2, #1* |
| 5 | Should | Hash corruption under boto3 multipart | Resolved: dedicated hash pass, `seek(0)` (§4.3) |
| 6 | Should | Compensation undefined for null `s3_version_id` | Resolved: delete by key when null (§8.6) |
| 7 | Should | S3 config not production-grade | Resolved: role-chain creds, SSE by policy, path-style, TTL/cap (§4.1) |
| 8 | Should | Bucket immutability posture | Resolved: Terraform at creation, no blanket retention, governance mode (§7, §10) |
| 9 | Should | Junction lacks `UNIQUE (item_id, evidence_id)` | Resolved: Phase B migration adds it (§3, §8.13) — *verify gate added round 2, #3* |
| 10 | Minor | Disposition gate on linking | *Reversed in round 2 (#8): now required, not "no gate"* |
| 11 | Minor | Evidence → control directness | Resolved: transitive via items (§8.11) |
| 12 | Minor | `uri` stored-link vector | *Re-opened round 2 (#4): vector moved to file body, closed on download path* |
| 13 | Minor | Original filename not retained | *Revised round 2 (#10): stashed in S3 object metadata* |
| 14 | Minor | `size_bytes` INTEGER caps at ~2.1 GB | Noted; `bigint` migration if exceeded (§3) |
| 15 | Minor | Evidence outside §1.5 provenance machine | Intentional (§8.10) — *durability caveat added round 2, #7* |

## Appendix B — Review disposition (round 2)

| # | Sev | Finding | Disposition |
| --- | --- | --- | --- |
| 1 | Blocking | DB transaction held across the S3 put → pool exhaustion | **Accepted.** Put-before-transaction; UUID app-side; connection held only for row+audit (§1, §4.3, §8.6) |
| 2 | Blocking | Pristine-delete is check-then-delete → races through CASCADE | **Accepted.** Single guarded `DELETE … WHERE NOT EXISTS`, 0 rows → 409 (§8.4, §11) |
| 3 | Blocking | "Resolved" claims rest on unverified DDL | **Accepted, narrowed → now discharged (round 3).** `\d evidence` pinned the column set + CASCADE FK; `\d assessment_item_evidence` confirmed `tenant_id`+RLS present and `UNIQUE` absent. Only #7 (audit actor durability) remains open (§3, §13) |
| 4 | Should | Presigned GET needs `Content-Disposition: attachment` + safe type — XSS moved, not removed | **Accepted (own miss).** Forced attachment + neutral content-type + filename; cookieless origin as hardening (§5) |
| 5 | Should | Linking-on-upload contradicts the Phase A/B split | **Accepted.** All linking → Phase B; `POST /v1/evidence` takes no link (§6, §10) |
| 6 | Should | MinIO presigned URLs break across the Compose host boundary | **Accepted.** Split `s3_public_endpoint_url` for presign vs internal put (§4.1) |
| 7 | Should | "Outlives uploader" needs AuditEvent to denormalize actor identity | **Accepted.** Reframed as conditional; verify gate — cross-cutting audit-model property (§8.10, §13) |
| 8 | Minor | Disposition-before-evidencing asymmetry vs inv 13 | **Accepted, reversing v1.** Evidence-linking now disposition-gated; deliberate asymmetry with control-links (§1.1, §9.1, §8.12) |
| 9 | Minor | Phase B edits shared AIIA delete logic — not purely additive | **Accepted.** Flagged shared-code; re-run AIIA/feeder delete tests (§8.5, §9.2, §10) |
| 10 | Minor | Original filename discarded | **Accepted.** Stash in S3 object metadata; drives download filename (§3, §4.2) |
| 11 | Minor | Audit presigned-download issuance? | **Accepted (yes).** `evidence.access` on URL issuance — custody event (§5, §6) |
| 12 | Minor | Name the proxy upload path as the AV-scan seam | **Accepted.** Marked (§2, §12) |
| 13 | Minor | Single CMK + single region/bucket vs PRD §6 | **Accepted as recorded tradeoff** (§12) |
| 14 | Minor | `GET /v1/evidence` needs pagination + link-count | **Accepted** (§6) |
| 15 | Minor | No-op unlink should not audit; "stream it" imprecise | **Accepted.** No-op unlink → no audit; corrected to spool-then-two-passes + disk-pressure note (§4.3, §8.1, §8.7) |
# Evidence Repository — Backend Design Proposal (v1)

**Feature:** Central evidence repository (EVD-1, EVD-2; AIIA-5) — file upload, S3-backed store, reuse across assessment items, immutable audit
**Scope:** Additive feature on the existing multi-tenant governance platform — not a greenfield redesign. This is **Sprint 4**, the evidence/upload path the AIIA design (`AIIA_DESIGN.md` §12) deferred.
**Status:** v1.0 — all design decisions resolved (§1.1, §13). The first-class `evidence` table reconciled end-to-end against live DDL; **Phase A needs no schema migration**, Phase B adds one junction constraint (`evidence_link_migration.py`). Both previously-open questions (disposition gate on linking; evidence→control directness) dispositioned (Appendix A).
**Out of scope this sprint:** evidence assignment with due dates/reminders (EVD-3, post-MVP); freshness/expiry notifications (EVD-4 — `expires_at` seam present, unused); export/audit pack (EXP-1 — consumes evidence; the presigned-download primitive is the seam); AV/malware scanning; content-addressed storage / hard sha256 dedup; evidence supersession / versioning chains; soft-void of worked evidence (pristine hard-delete only); Object Lock **retention-application** logic (the bucket carries the capability — applying locks at the authorisation gate is lifecycle work)

**Decisions:** all resolved (§1.1, §13). Phase A migration: **none** (table build-ready). Phase B migration: `evidence_link_migration.py` — adds `UNIQUE (item_id, evidence_id)` to the junction.

---

## 1. Overview

This sprint builds the full backend for the evidence repository: upload a file, store the bytes in S3, record a pointer row in Postgres, and link that evidence to one or more assessment items. Evidence is **reusable** — one uploaded artifact (a DPA, a model card, a security certification) satisfies many items across many assessments without re-uploading. This is what turns an assessment from a self-declaration into an audit-ready record.

The design leans on existing foundations: the first-class `evidence` table (pointer + `sha256`, live), the `assessment_item_evidence` junction (`tenant_id` + RLS already added by the AIIA migration), the `assessment_item_control` link/unlink endpoints as a structural template, the tenant-plane atomic-audit rule, and the read-time feeder assembly. **Unlike the AIIA service, the evidence upload path *does* make an external-system call (S3)** — so it follows the six-step external-call ordering (the Cognito choreography of `provision_tenant` / `provision_member`), while the link/unlink path is pure DB and follows the tenant-plane rule (stage the `AuditEvent`, commit atomically with the rows). One feature, two transactional shapes; they must not be conflated.

Work splits into **Phase A** (upload + repository — a demoable vertical slice: put evidence in, get it back) and **Phase B** (item linking + propagation). The only genuinely new infrastructure (boto3, MinIO-in-dev, presigned URLs, the streaming hash, the compensation path) lives in Phase A; Phase B is a near-clone of the control-link path plus two assessment-graph edits.

### 1.1 Resolved design decisions

| Decision | Resolution |
| --- | --- |
| Upload transport | **Proxied through the API** — server receives bytes, computes `sha256` server-side, puts to S3 via the six-step choreography. Atomic; no orphan/confirm window. Presigned-PUT + S3-enforced checksum is the documented **scale seam**, not MVP |
| Download transport | **Presigned GET**, short TTL, authorised by the RLS read of the `Evidence` row — bytes never touch the API on the read path |
| `sha256` semantics | **Integrity + lookup, not uniqueness** — schema-confirmed (nullable, non-unique `ix_evidence_sha256`). Soft dedup *detection* only ("link the existing one?"); no constraint to fight |
| Evidence-row hard delete | **Pristine-only** (zero links). **Load-bearing at the app layer** because the junction FK is `ON DELETE CASCADE` — the DB will *not* block it (inverse of the reference-FK `RESTRICT` pattern) |
| Uploader durability | `uploaded_by_user_id` is `ON DELETE SET NULL` — evidence outlives its uploader; the actor of record is the `evidence.created` AuditEvent, resolved via the membership join, never bare `app_user` |
| Provenance | Evidence sits **outside** the §1.5 provenance machine — a user-uploaded artifact, not item content with a system default. No `ProvenanceConfidence` tag; the `evidence.*` audit trail is its defensibility record |
| Evidence → control | **Transitive via items only** — no direct evidence↔control table. Framework satisfaction derives from the control-library cross-map (`AIIA_DESIGN.md` §8.12); one evidence on one item reaches every control that item links across both frameworks |
| Disposition gate on linking | **Mirror control-links — no disposition gate.** Control-linking imposes none today; evidence-linking is the same item↔X shape. (Confirm — Appendix A #10) |
| Title vs filename | `title` defaults to the uploaded filename when none supplied; **no separate `original_filename`** retained (no such column, no metadata JSONB). A reusable repository is better served by a human title |
| Encryption at rest | **SSE applied by the storage layer on every put, by policy** — never per-caller. SSE-KMS in prod (one CMK) for CloudTrail key-access logging |
| Bucket immutability | **Object Lock enabled at bucket creation** (Terraform; versioning auto-on), **no blanket default retention**. Selective WORM (retention/legal-hold) applied at the authorisation gate — lifecycle work, not this sprint |
| Credentials | Static keys are a **dev-only** convenience; prod leaves them unset → boto3 instance/role chain (IRSA / task role) |
| Junction uniqueness | Phase B **adds `UNIQUE (item_id, evidence_id)`** — absent today (the AIIA migration added it for the *control* join only); the §11 duplicate→409 depends on it |
| Pristine-delete predicate | **Extended to count evidence links** — an item carrying evidence is "worked"; mirrors `AIIA_DESIGN.md` §8.11 for items/AIIAs/feeders |
| Feeder propagation | Evidence links **travel with surfaced feeder items** in the read-time assembly (parity with control links; `AIIA_DESIGN.md` §9.2) — borrowed at read time, never copied |

---

## 2. Reused components (existing foundations)

- **First-class `evidence` table (live).** Pointer (`s3_bucket` / `s3_key` / `s3_version_id`) + `sha256` + the `expires_at` seam. Reconciled column-for-column against live DDL (§3); no ALTER this sprint. Invariant 6 (bytes in S3, pointer in PG) is already the contract.
- **`assessment_item_evidence` junction (live).** Item↔evidence M:N, `tenant_id` + RLS added by the AIIA migration. The reuse mechanism: one `Evidence` row referenced by many join rows across many items/assessments.
- **Control-link endpoint shape (`assessment_item_control`).** The structural template for evidence link/unlink — same item↔X join, duplicate→409, no provenance transition, no `lock_version`, attribution in AuditEvents (no `created_by`/timestamps on the join).
- **External-call choreography (STATE §4 / `provision_tenant`).** The upload path's six-step ordering: pre-check → stage+flush → external put → write-back → stage audit → commit-or-compensate. Reused verbatim in shape.
- **Tenant-endpoint contract.** Router in `app/routers/v1/`, registered under `/v1`; `get_tenant_db` plus exactly one of `require_role` / `require_governance_role`; `tenant_id` from `ctx.tenant_id`; schemas in `app/schemas/`.
- **Tenant audit plane.** Link/unlink stage an `AuditEvent` committed atomically with the rows; the immutability trigger and RLS cover the junction.
- **Read-time feeder assembly (`AIIA_DESIGN.md` §9.2).** `GET /assessments/{aiia_id}` assembles native ∪ surfaced feeder items, tagging `source_assessment_id` + `type`. Extended here to carry evidence links on surfaced items.
- **Governance role model (PRD §4.9).** Tenant-scoped; SoD is a conflict matrix at assignment. These endpoints consume roles for gating and carry no SoD logic. PRD §4.9.1 defines Contributor as "supplies requested evidence/facts" — evidence writes map to `{system_owner, contributor}`.

---

## 3. Data model

No new model. The `evidence` table and the `assessment_item_evidence` junction both exist; Phase A touches neither, Phase B adds one constraint to the junction.

**`evidence`** *(table exists — reconciled against live DDL; **no ALTER this sprint**)*
- `id` (uuid PK), `tenant_id` (uuid, FK → `tenant` `ON DELETE CASCADE`, indexed) — present
- `title` (varchar 255, NOT NULL) — the human label. **No `original_filename` column** and no metadata JSONB; default `title` to the uploaded filename when the client supplies none.
- `s3_bucket` (NOT NULL), `s3_key` (varchar 1024, NOT NULL) — present
- `s3_version_id` (varchar 255, **nullable**) — captured from the put when bucket versioning is on. **Nullable by design** → the compensation path must delete by *key* when null, by *version* when set (§8.6).
- `content_type` (varchar 120, nullable) — recorded from the multipart part; not hard-allow-listed (evidence is heterogeneous).
- `size_bytes` (**integer**, nullable) — implicit **~2.1 GB ceiling**; the upload cap sits well under it (§4.1). Exceeding it is a `bigint` migration.
- `sha256` (varchar 64, nullable, non-unique `ix_evidence_sha256`) — **integrity + lookup, not uniqueness**. Server-computed (§4.3). The index backs optional dedup *detection*, not enforcement.
- `uploaded_by_user_id` (uuid, nullable, FK → `app_user` `ON DELETE SET NULL`) — **evidence outlives its uploader**; the durable actor is the `evidence.created` AuditEvent.
- `expires_at` (timestamptz, nullable) — the **EVD-4 seam**; unused this sprint.
- `created_at`, `updated_at` — present.
- **RLS:** `tenant_isolation` `USING (tenant_id = current_setting('app.current_tenant'))`. USING-only is sufficient — Postgres applies the same predicate as `WITH CHECK` on INSERT, so new rows are tenant-validated.

**`assessment_item_evidence`** (item ↔ evidence M:N junction — exists)
- `id`, `item_id` (FK → `assessment_item`, `ON DELETE CASCADE`), `evidence_id` (FK → **`evidence`**, `ON DELETE CASCADE`) — present
- `tenant_id` + RLS — present (added by the AIIA migration, parity decision).
- No `created_by` / timestamps on the join — attribution stays in the `evidence.linked` / `evidence.unlinked` AuditEvents, parity with the control-link join.
- **ALTER (Phase B): add `UNIQUE (item_id, evidence_id)`** — **absent today.** The AIIA migration added the analogous `UNIQUE (item_id, control_id)` to the *control* join but not to this one; the §11 duplicate→409 depends on it. *(Confirm against live `\d assessment_item_evidence` before drafting the migration.)*

**Reconciliation note — the `uri` stub is superseded.** `AIIA_DESIGN.md` §12 anticipated an evidence stub with a `label`/`uri` link and flagged "sanitise `assessment_item_evidence.uri` at render, validate scheme on input." The implemented model is **pointer-based** (`title` + S3 pointer + `sha256`), so that concern is **moot**: no user-controlled URL is ever stored or rendered. The only URL in the system is a server-minted, short-TTL presigned GET (§5) — which removes the stored-link / injection vector entirely rather than mitigating it.

---

## 4. Storage layer & the upload choreography

The spine of this feature. The bytes never enter Postgres; the integrity hash never comes from the client.

### 4.1 Configuration (`app/config.py`) — first S3/boto3 wiring in the project

```python
# --- Object storage (evidence artifacts) ---
# None => real AWS S3; set => S3-compatible endpoint (MinIO in dev)
s3_endpoint_url: str | None = Field(default="http://localhost:9000")
s3_region: str = Field(default="eu-west-1")
# Static creds are a DEV convenience only. Leave unset in prod so boto3
# resolves the instance/role chain (IRSA / ECS task role). Never ship long-lived keys.
s3_access_key: str | None = Field(default="minioadmin")
s3_secret_key: str | None = Field(default="minioadmin")
s3_evidence_bucket: str = Field(default="aigov-evidence")
# Path-style for MinIO; virtual-host for real S3.
s3_use_path_style: bool = Field(default=True)
# Encryption at rest. dev MinIO: off; prod: "aws:kms" for key-level auditability.
s3_sse_mode: str | None = Field(default=None)         # "AES256" | "aws:kms" | None
s3_sse_kms_key_id: str | None = Field(default=None)   # required iff sse_mode == "aws:kms"
# Short-lived presigned GET for download.
s3_presigned_get_ttl: int = Field(default=300)
# Upload ceiling — must stay under the size_bytes INTEGER limit (~2.1 GB).
evidence_max_upload_bytes: int = Field(default=100 * 1024 * 1024)  # 100 MiB
```

Beyond the bare skeleton: credentials nullable (role-chain in prod); explicit path-style (the dev/prod divergence that breaks on first prod deploy); SSE as a storage-layer property; presigned TTL and upload cap as config (the cap enforced *during* streaming, not from a spoofable `Content-Length`). Region is a residency choice (GDPR / EU AI Act), not just latency.

### 4.2 Storage helper (`app/services/storage.py`)

Centralised boto3 wiring, mirroring `cognito_helpers.py`: a client factory selecting endpoint + addressing style from config; `put_object(...)` that applies SSE by policy and returns the `VersionId`; `generate_presigned_get(...)` at the configured TTL; tenant-prefixed key layout `{tenant_id}/evidence/{evidence_id}` (defence-in-depth on top of RLS).

### 4.3 Evidence service (`app/services/evidence_service.py`) — upload choreography

S3 is an external system, so the upload owns its session and follows the six-step ordering:

```
1. Pre-check in DB   (tenant valid; if linking on upload, item exists & is RLS-visible)
2. Stage Evidence row + flush  (uncommitted) — obtain id, derive S3 key
3. S3 put_object  → failure → rollback; nothing persisted
4. Write s3_version_id (+ sha256) from the put result back onto the row
5. Stage AuditEvent  (evidence.created)
6. Commit  → on failure, best-effort delete the S3 object/version; re-raise
```

The link/unlink path is the *other* shape (no external call): pre-check, stage the join + `AuditEvent`, `flush`, let `get_tenant_db` commit atomically. It must never reach for the choreography above.

**`sha256` is computed server-side** — never client-asserted, mirroring the server-derived-provenance posture (`AIIA_DESIGN.md` §4). **Gotcha:** Starlette's `UploadFile` is a seekable `SpooledTemporaryFile`, and boto3's `upload_fileobj` may read it non-sequentially for multipart, which would corrupt a read-through digest. Hash in a **dedicated pass**, `seek(0)`, then upload — two sequential passes over a small spooled file, unambiguously correct.

---

## 5. Transport — proxied upload, presigned download

**Upload: proxied through the API for MVP.** The driver is defensibility — the `sha256` is integrity evidence that the stored artifact is the one assessed, and a server-owned hash is the only kind that stands. The single-phase flow is atomic: no orphan window, no confirm endpoint, no reaper for abandoned presigned uploads. Evidence here is human-paced, modest governance documents; occupying a sync worker for an upload is a non-issue at this volume.

**Scale seam (documented, not built):** presigned **PUT** with `ChecksumAlgorithm=SHA256` *enforced* by S3 — S3 rejects any object whose bytes don't match the client-declared checksum, so the stored hash stays trustworthy even though the API never sees the bytes; read it back via HeadObject and persist. Defensible *and* scalable, but two-phase and dependent on S3/MinIO checksum parity (a dev/prod divergence risk). The later move is an extension, not a rewrite.

**Download: presigned GET, always.** Server authorises via the RLS read of the `Evidence` row — readable row → short-TTL presigned URL; RLS-hidden row → nothing — and bytes never touch the API on the read path. Asymmetric but correct: proxy the write to own the hash, presign the read to offload the bytes.

---

## 6. API endpoints

| Method + path | Purpose | Gate |
| --- | --- | --- |
| `POST /v1/evidence` (multipart) | Upload → S3 → `Evidence` row; optional initial item link(s) | `{system_owner, contributor}` |
| `GET /v1/evidence` | Central repository listing — browse to reuse rather than re-upload | any governance role |
| `GET /v1/evidence/{id}` | Metadata + short-TTL presigned **GET** URL | any governance role |
| `DELETE /v1/evidence/{id}` | Pristine-only hard delete (zero links) | `{system_owner, contributor}` |
| `POST /v1/assessments/{aid}/items/{item_id}/evidence-links {evidence_id}` | Link existing evidence; duplicate → 409 | `{system_owner, contributor}` |
| `DELETE .../items/{item_id}/evidence-links/{evidence_id}` | Unlink (idempotent delete-if-exists) | `{system_owner, contributor}` |

Item reads surface evidence links alongside control links — in the item read and, for feeder items, in the read-time assembly (§9). Reference/read gates follow the AIIA pattern: any of the five governance roles for reads, `{system_owner, contributor}` for writes.

---

## 7. Tenancy, RLS & isolation

Entirely tenant-plane, on `irontrustai_app` / `get_tenant_db`, `NOBYPASSRLS`, **no new DB role**, no plane crossing. Both `evidence` and `assessment_item_evidence` are RLS-scoped, so a tenant resolves only its own evidence rows — and therefore only its own S3 keys. Tenant-prefixed keys (`{tenant_id}/evidence/{id}`) add a second fence: even a guessed key yields nothing without an RLS-readable row to mint a presigned URL from.

`tenant_id` is always `ctx.tenant_id`, never a body field. The `evidence_id` in a link request is **RLS-validated** — you can only link evidence you can read; a cross-tenant `evidence_id` is simply invisible and the join insert finds nothing to reference (fail-closed). S3-side, the storage layer applies SSE on every put by policy, so no code path can store an evidence object unencrypted.

---

## 8. Constraints & invariants

1. **Bytes in S3 only.** Postgres holds the pointer (`s3_bucket` / `s3_key` / `s3_version_id`) + `sha256` (inv. 6). Never buffer the whole file to the DB; stream it.
2. **`sha256` is server-computed, never client-set.** The hash is integrity evidence; a client hash would defeat it. Mirrors the server-derived-provenance posture.
3. **Evidence bytes are immutable post-upload.** Re-evidencing is a *new* row with a *new* hash, not a mutation — which is what keeps `expires_at` / supersession a clean post-MVP seam.
4. **Pristine-delete only (evidence row), and it is load-bearing at the app layer.** Hard `DELETE` of an `Evidence` row is permitted only with zero `assessment_item_evidence` links. The junction FK is `ON DELETE CASCADE`, so the **DB will not block** a delete of linked evidence — it silently strips the joins off their items, mutating a possibly-approved assessment without passing the assessment's own delete guards. This is the inverse of the reference-FK `RESTRICT` pattern: there the DB enforces and the app may relax; **here the DB permits and the app must restrict.**
5. **Assessment/item pristine-delete predicate extended.** An item carrying an evidence link is "worked" — the §8.11 (`AIIA_DESIGN.md`) pristine predicate (no confirms/amends, no control links, no feeders) gains **no evidence links**, for items, AIIAs, and feeders.
6. **Upload choreography + null-version compensation.** The six-step external-call ordering; on commit failure, best-effort delete — by *version* when `s3_version_id` is set, by *key* when null. Get this wrong and a commit failure on a non-versioned bucket orphans an object the cleanup misses.
7. **Audit atomicity.** Link/unlink stage the `AuditEvent` in the same transaction and commit atomically. Upload stages at step 5, commits at step 6. Never commit audit separately.
8. **`tenant_id` from context, never body** (inv. 3). The `evidence_id` in a link request is RLS-validated.
9. **SSE by policy.** Encryption at rest is a property of the storage layer, applied on every put; not an option an individual call can omit.
10. **Evidence is outside the §1.5 provenance machine.** No `ProvenanceConfidence` tag — it is a user-origin artifact, not item content with a system default. The `evidence.*` audit trail is its defensibility record.
11. **Evidence → control is transitive via items only.** No direct evidence↔control table. Framework satisfaction (ISO 42001 *and* EU AI Act) derives from the control-library cross-map (`AIIA_DESIGN.md` §8.12).
12. **Duplicate link integrity.** `UNIQUE (item_id, evidence_id)` is a **Phase B ALTER** (absent today); without it duplicate links are possible. DB-level; catch the violation → 409.
13. **Feeder propagation is reference, not copy.** When a feeder item surfaces into the AIIA read, its evidence links surface with it, tagged with the source — never written into the AIIA. The read-time assembly is the single locus (`AIIA_DESIGN.md` §9.2, inv. 16).
14. **No new DB role.** Tenant work runs on `irontrustai_app` (`NOBYPASSRLS`); the set is fixed.
15. **Object Lock capability ≠ retention application.** The bucket is provisioned with Object Lock enabled at creation (§7 infra), but **no blanket default retention**; applying retention/legal-hold at the authorisation gate is lifecycle work, not this sprint — otherwise WORM would collide with pristine-delete (the app role neither holds nor should hold `s3:BypassGovernanceRetention`).

---

## 9. Linking & propagation

### 9.1 Link / unlink
Evidence-link is the control-link shape: a thin join, `POST` to create (duplicate → 409 via `UNIQUE (item_id, evidence_id)`, Phase B), `DELETE` to remove (idempotent delete-if-exists). No `lock_version` / `If-Match` — a join insert/delete is not a provenance transition on the item, so the optimistic-concurrency machinery doesn't apply (parity with control-links). Attribution lives in `evidence.linked` / `evidence.unlinked` AuditEvents, not on the join.

**Disposition gate.** Mirror control-links: **no** disposition gate — an evidence link may attach to an item regardless of its provenance state. Control-linking imposes none today, and consistency favours the same shape. (Evidencing a still-`AI_SUGGESTED` risk is conceptually odd; flagged for confirm, Appendix A #10 — but it is not a present gate.)

### 9.2 Propagation (reference, not copy)
Evidence links ride the existing read-time assembly. `GET /assessments/{aiia_id}` already assembles native ∪ surfaced feeder items, each tagged `source_assessment_id` + `type`; this sprint ensures a surfaced feeder item carries its evidence links **untouched**, exactly as it carries control links. Nothing is copied or written back; editing/unlinking on the feeder changes what surfaces, no sync step. The pristine-delete extension (§8.5) means a feeder item with an evidence link blocks the feeder's pristine-delete — the propagation seam showing up in the delete path.

---

## 10. Sequencing

**Phase A — storage foundation + repository (demoable).** No schema migration (the `evidence` table is build-ready). Config fields; `storage.py` (client factory, SSE-by-policy put, presigned GET, tenant-prefixed keys); `POST /v1/evidence` (upload → streaming hash → put → row, six-step choreography, null-version compensation); `GET /v1/evidence`; `GET /v1/evidence/{id}` (presigned download); pristine evidence-row delete; `evidence.created` / `evidence.deleted` audit. This is the only phase with new infrastructure.

**Phase B — linking + propagation.** `evidence_link_migration.py` (add `UNIQUE (item_id, evidence_id)` to the junction — confirm absent against live `\d`). Then: item evidence-link / unlink endpoints; the read-time-assembly extension to carry evidence links on surfaced feeder items; the pristine-delete predicate extension (items / AIIAs / feeders); item-read surfacing; `evidence.linked` / `evidence.unlinked` audit. Pure DB; mirrors the control-link path.

**Bucket provisioning (Terraform `infra/`, not Alembic).** Create the prod evidence bucket with Object Lock enabled at creation (versioning auto-on), no default retention, governance mode. Dev MinIO: versioning on (to exercise `s3_version_id`), Object Lock unnecessary. Do this alongside Phase A.

**Seams preserved now:** `expires_at` (EVD-4 freshness, post-MVP); presigned-PUT + checksum (upload scale path); Object Lock retention application (lifecycle/authorisation work); the export pack's consumption of the presigned-download primitive (EXP-1).

---

## 11. Edge & failure cases

- S3 put succeeds, commit fails → orphaned object; compensation (step 6) deletes it (by version or key). Compensation itself failing → log for a reconciliation sweep (sweep deferred).
- Row staged, S3 put fails → rollback; nothing persisted (step 3). Clean.
- Duplicate bytes (same `sha256`) → soft detection via `ix_evidence_sha256`; default allows the row. Optional "link the existing one?" — no hard constraint.
- Duplicate link (same evidence on same item) → 409, via `UNIQUE (item_id, evidence_id)` (Phase B).
- Cross-tenant link attempt → fail-closed: `evidence_id` / `item_id` not RLS-visible; the join insert references nothing.
- Link to a still-`AI_SUGGESTED`, undispositioned item → **allowed** (mirror control-links; §9.1).
- Oversized file → 413 against `evidence_max_upload_bytes`, enforced during streaming. Empty / zero-byte → 422.
- Pristine-delete of evidence with live links → 409. Pristine-delete of an assessment/item/feeder whose item carries evidence → 409 (extended predicate, §8.5).
- Presigned URL expiry / clock skew → short TTL; the `sha256` lets the client verify integrity on download.
- Bucket versioning disabled → `s3_version_id` null; treat as a startup/infra precondition, and ensure compensation deletes by key (§8.6).
- `uploaded_by_user_id` user later deleted → row survives with null uploader; reads tolerate null and resolve the actor from the `evidence.created` AuditEvent.

---

## 12. Intentionally deferred (post-MVP / later sprints)

- **Evidence assignment with due dates / reminders (EVD-3)** — post-MVP; no model touched.
- **Freshness / expiry notifications (EVD-4)** — `expires_at` present and unused; no scheduler, no notification logic.
- **Presigned direct-to-S3 upload** — the scale seam (§5); deferred because proxying is what lets the server own the hash.
- **AV / malware scanning** — no infrastructure; out of scope.
- **Content-addressed storage / hard `sha256` dedup** — beyond optional soft detection.
- **Evidence supersession / versioning chains, soft-void of worked evidence** — MVP is pristine hard-delete only; bytes are immutable post-upload.
- **Object Lock retention-application logic** — capability provisioned at bucket creation; applying locks at the authorisation gate is lifecycle work.

### Next consumer (not post-MVP)
- **Export / audit pack (EXP-1, a Must)** — consumes evidence via the presigned-download primitive this sprint builds; the feeder-private export requirement (`AIIA_DESIGN.md` §9.2) already reserves the seam. Its own sprint, but the immediate downstream consumer — not a deferral.

---

## 13. Decisions resolved + migration

All previously-open decisions are now resolved (fixed in the design, not deferred):

1. **Schema reconciliation → complete.** The `evidence` table matched column-for-column against live DDL; **Phase A needs no migration**.
2. **`sha256` → integrity + lookup, not uniqueness** — schema-confirmed (nullable, non-unique index). Soft dedup detection only.
3. **Evidence-row delete → pristine-only, app-enforced** — load-bearing because the junction FK is `ON DELETE CASCADE` (the DB won't block it).
4. **Upload transport → proxied** (server-owned hash); presigned-PUT + S3 checksum is the documented scale seam.
5. **Download → presigned GET**, RLS-authorised.
6. **Disposition gate on linking → none** (mirror control-links); confirm (Appendix A #10).
7. **Evidence → control → transitive via items only** — resolved from the AIIA cross-map model; no direct table.

**Migration set:**
- **Phase A: none.** The `evidence` table is build-ready.
- **Phase B: `evidence_link_migration.py`** — add `UNIQUE (item_id, evidence_id)` to `assessment_item_evidence`. *(Confirm absent against live `\d assessment_item_evidence` — the AIIA migration added the unique only to the control join.)* Set `down_revision` to your current head.

**Not an Alembic migration:** bucket provisioning (Object Lock at creation, versioning, no default retention) is Terraform `infra/`. AWS provider semantics for `object_lock_enabled` (create-time / ForceNew in many versions) should be re-checked at the point the bucket Terraform is written.

---

## Appendix A — Review disposition

| # | Sev | Finding | Disposition |
| --- | --- | --- | --- |
| 1 | Blocking | Evidence table column set unknown — design can't assume fields | Resolved: matched against live DDL (`title`, pointer, `content_type`, `size_bytes`, `sha256`, `uploaded_by_user_id`, `expires_at`); no Phase A migration (§3) |
| 2 | Blocking | `sha256` uniqueness/dedup semantics undecided | Resolved: nullable + non-unique index = integrity + lookup; soft detection, no enforcement (§3, §8.2) |
| 3 | Blocking | Junction FK is `ON DELETE CASCADE` — DB won't block deleting linked evidence | Resolved: app-level pristine gate is load-bearing; inverse of the `RESTRICT` pattern (§8.4) |
| 4 | Should | Upload transport (proxied vs presigned) unresolved | Resolved: proxied for server-owned hash; presigned-PUT+checksum is the scale seam (§5) |
| 5 | Should | Hash computation under boto3 multipart could corrupt the digest | Resolved: dedicated hashing pass, `seek(0)`, then upload (§4.3) |
| 6 | Should | Compensation undefined when `s3_version_id` is null | Resolved: delete by key when null, by version when set (§8.6) |
| 7 | Should | S3 config not production-grade (static keys, no SSE, no path-style) | Resolved: nullable creds → role chain; SSE by policy; explicit path-style; TTL/cap as config (§4.1) |
| 8 | Should | Bucket immutability (versioning + Object Lock) posture | Resolved: Terraform at bucket creation, no blanket retention, governance mode, selective WORM at authorisation (§7, §10) |
| 9 | Should | Junction lacks `UNIQUE (item_id, evidence_id)` (AIIA migration added it for control only) | Resolved: Phase B `evidence_link_migration.py` adds it; duplicate→409 depends on it (§3, §8.12) — confirm against live `\d` |
| 10 | Minor | Disposition gate on evidence-linking | Decided: mirror control-links, no gate (§9.1) — **confirm** |
| 11 | Minor | Evidence → control directness | Resolved from the AIIA cross-map model: transitive via items; no direct table (§8.11) |
| 12 | Minor | `assessment_item_evidence.uri` stored-link vector (AIIA §12) | Moot: pointer model + presigned GET stores no user URL; the vector is removed, not mitigated (§3) |
| 13 | Minor | Original filename not retained | Accepted: `title` defaults to filename; a column add if traceability later demands it (§3) |
| 14 | Minor | `size_bytes` INTEGER caps uploads at ~2.1 GB | Noted: cap set well under; `bigint` migration if ever exceeded (§3, §4.1) |
| 15 | Minor | Evidence sits outside the §1.5 provenance machine | Intentional: user artifact, not a system-asserted default; audit trail is the record (§8.10) |
