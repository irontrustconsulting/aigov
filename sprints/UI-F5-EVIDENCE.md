# UI-F5-EVIDENCE — Sprint Handoff (execution-only)

**For:** Claude Code (VS Code, plan mode). Execution-only; rationale in `UI-F5-EVIDENCE-design-final.md`.
**Surface:** `apps/tenant/app/evidence` (NEW) + `apps/tenant/app/use-cases/[id]` (ALTER).
**Closes:** `DF3-1` / A2.
**Backend delta:** one additive field — a self-describing `evidence_links` manifest on the AIIA item read (WI-F). No migration, route, table, or enum.
**If-Match:** none on any evidence/evidence-link call. Do not send it.
**Pre-resolved at §0 r2 (do not re-litigate):** A-1 dedicated upload handler (generic proxy byte-unsafe); A-2 additive manifest; A-6 omit uploader in MVP. Open confirms remain: V-5, V-6, V-9, in-service upload gate, EVD-1/2 ids.

---

## §0 — Pre-flight (close the open confirms before the dependent WI; D-21)

| V | Item | Result / action | Blocks |
|---|---|---|---|
| V-1 | `EvidenceRead` shape | **Closed:** id,title,content_type,size_bytes,sha256,`uploaded_by_user_id`,created_at,updated_at; no status enum | WI-A, WI-D |
| V-2 | `EvidenceListResponse` | **Closed:** `EvidenceListItem`+`link_count`; cursor `next_cursor` | WI-A, WI-D |
| V-3 | `EvidenceDetailRead` | **Closed:** `download_url`; `GET /{id}` stages `evidence.access` | WI-A, WI-D |
| V-4 | link schemas | **Closed:** create `{evidence_id}`; read `{id,item_id,evidence_id}` ids-only | WI-A, WI-E, WI-F |
| V-5 | `DELETE /evidence/{id}` code when `link_count>0` | **Confirm** in `evidence_service.delete_evidence`: 409\|404\|422 | WI-D |
| V-6 | `POST .../evidence-links` code on AI_SUGGESTED | **Confirm** in `assessment_service.create_evidence_link`: 409\|422 | WI-E |
| V-7 | `AssessmentItemRead` evidence | **Closed:** absent → WI-F needed | WI-E, WI-F |
| V-8 | BFF `[...path]` | **Closed:** `request.text()` corrupts binary → dedicated handler (WI-C) | WI-C |
| V-9 | `POST /evidence` size/type cap | **Confirm** API/config; BFF sets a ceiling regardless | WI-C, WI-D |
| V-10 | gates | **Closed:** upload in-service; reads gov:ALL; delete/link/unlink gov:write; admin 403 | WI-D, WI-E |
| V-11 | `EVD-1/2` ids | **Confirm** against REQUIREMENTS (EVD-3/4 deferred already confirmed) | WI-G |
| — | upload gate | **Confirm** `evidence_service.upload_evidence` actually calls `require_governance_role` (security) | WI-D |

---

## Work items (dependency-ordered)

### WI-A · `@irontrust/api-client` — evidence contracts + upload helper
- Contract types: `EvidenceRead` (id, title, content_type, size_bytes, sha256, uploaded_by_user_id, created_at, updated_at), `EvidenceListItem` (+`link_count`), `EvidenceListResponse` ({items, next_cursor}), `EvidenceDetailRead` (+`download_url`), `EvidenceLinkCreate` ({evidence_id}), `EvidenceLinkRead` ({id, item_id, evidence_id}).
- Calls (BFF-routed): `listEvidence({limit,cursor})`, `getEvidenceDetail(id)`, `deleteEvidence(id)`, `linkEvidence(aid,iid,{evidence_id})`, `unlinkEvidence(aid,iid,evidence_id)`, `uploadEvidence(file, title?)` (multipart, via the WI-C dedicated handler). **No `If-Match` on any.** Never set `tenant_id`/`provenance`.
- **Done-check:** unit test asserts no `If-Match` on these calls; `unlinkEvidence` targets `.../evidence-links/{evidence_id}`; `uploadEvidence` sends `multipart/form-data`.

### WI-C · Dedicated BFF upload handler (blocks WI-D upload; A-1 / V-8)
- New handler (e.g. `apps/tenant/app/api/evidence-upload/route.ts`) forwarding **raw bytes** to `POST /v1/evidence`: pipe `request.body` (ReadableStream) or pass `request.arrayBuffer()`/`Blob`. **Never `request.text()`** — it UTF-8-corrupts binary. Preserve the inbound `multipart/form-data` `Content-Type` + boundary. **Do not route uploads through `app/api/proxy/[...path]`.**
- Reuse session lookup + bearer-forward + CSRF origin/`Sec-Fetch-Site` check (`NFR-1`). Impose a body-size ceiling (V-9); map over-limit to a clear too-large error, not a bare 413.
- **Done-check:** integration test uploads a **binary** file (e.g. a small PDF/PNG) browser→BFF→API→S3 and reads it back via the list with a byte-exact `sha256`; the same file through `[...path]` is shown to corrupt (regression guard); a cross-origin upload is rejected (CSRF).

### WI-B · `@irontrust/ui` — evidence primitives
- `EvidenceTable` (title, content_type, size_bytes, sha256-with-copy, created_at, link_count, row actions; no uploader column — DF5-11).
- `EvidenceUploadControl` (file input + optional title; pending/disabled; too-large + error surfaces).
- `EvidenceLinkPicker` (paginated over `listEvidence`, client-side filter over the loaded page — A-3).
- `EvidenceManifestChip` (per-item: title/sha256/filename from the WI-F manifest; unlink action).
- Reuse the `FE-8` disabled-with-reason wrapper for delete (`link_count>0`) and link (AI_SUGGESTED).
- **Done-check:** axe + keyboard pass (WCAG 2.1 AA, `FE-3`/`FE-4`); no literal colour/spacing values (lint).

### WI-D · `apps/tenant/app/evidence` (NEW) — repository home
- Role branch off `GET /v1/me` (`DF5-7`): admin → empty-state, **no `gov:ALL` evidence call**. system_owner/contributor → list+upload+download+delete. reviewer/authoriser/auditor → list+download only (upload/delete absent, `FE-8`).
- Download: `getEvidenceDetail` **only on explicit download click** (`DF5-3`), then navigate the browser to `download_url` (attachment; never inline).
- Delete: disabled-with-reason on `link_count>0` (`DF5-6`); surface the V-5 server reason.
- **Done-check (`evidence-home.spec`):** admin empty-state issues no evidence request; reviewer sees no upload/delete; upload appears with sha256; download triggers one `getEvidenceDetail` + browser navigation, no eager per-row detail; delete blocked on linked (V-5 code → reason), succeeds unlinked.

### WI-E · `apps/tenant/app/use-cases/[id]` (ALTER) — per-item linking
- Render the per-item evidence manifest from the WI-F `evidence_links` field (renders from the item read alone; no repository load; no `evidence.access`).
- system_owner/contributor: **Link** via `EvidenceLinkPicker` → `linkEvidence`; disposition-gated (`INV-20`/`DF5-5`) present-but-disabled-with-reason on AI_SUGGESTED; surface the V-6 code. **Unlink** via `unlinkEvidence(...{evidence_id})`, idempotent.
- reviewer/authoriser/auditor: read-only manifest, no controls (`FE-8`, A-5). admin: empty-state (existing F3).
- After link/unlink: invalidate-and-refetch the **AIIA-detail key only** (`FE-7`); **not** the lifecycle/whose-court key (`DF5-10`/`D-29`).
- **Done-check (`use-case-evidence.spec`):** link disabled-with-reason on AI_SUGGESTED, enabled post confirm/amend; link/unlink round-trips and re-renders the manifest; unlink idempotent and targets `{evidence_id}`; query-cache assertion confirms link/unlink invalidates the AIIA-detail key and **not** the lifecycle key; reviewer/auditor render the manifest with no controls.

### WI-F · Backend additive `evidence_links` manifest on the item read
- Add `evidence_links: list[ItemEvidenceRead] = []` to `AssessmentItemRead` in `app/schemas/assessment.py`, where `ItemEvidenceRead = {evidence_id, title, sha256, content_type, size_bytes}` (**no `download_url`, no bytes**). Batch-load in `assemble_aiia_items` (join `assessment_item_evidence` → `evidence`), mirroring `_batch_control_links` (DF3-7). No migration. Existing callers unbroken.
- **Done-check:** `GET /v1/assessments/{id}` returns `items[].evidence_links` with title/sha256 populated; no `download_url` present; existing AIIA-detail tests pass; batch-loaded (no per-item query).

### WI-G · Canonical update (volatile tier + the one FRONTEND append)
- **STATE.md:** `UI-F5-EVIDENCE` shipped (`apps/tenant/app/evidence` NEW; `use-cases/[id]` ALTER; dedicated upload handler); move "Evidence linking / repository surface (A2)" and `DF3-1` out of the deferred register (closed); note `FE-6`-dormant / no-If-Match.
- **DATA-MODEL.md:** note `evidence_links` (`ItemEvidenceRead`) on the AIIA item read shape (no table/enum change).
- **DECISIONS.md:** append `DF5-1..DF5-11`. Do not renumber existing ids.
- **FRONTEND.md:** append `FE-12` (uploads via a dedicated BFF handler forwarding raw bytes — never `request.text()`; preserve multipart content-type/boundary; CSRF/`NFR-1`; browser→BFF→API; download via presigned URL to S3, never inline) with cites `INV-50`, `INV-18`, `FE-2`, `NFR-1`, `INV-22`; add the FE-n index row. **Only** stable-tier touch.
- **INVARIANTS.md:** no new `INV` expected; if V-5/V-6 service inspection surfaces a structural constraint worth promoting, raise before appending; never renumber.
- **API-ROUTES.md:** `UI-F5-EVIDENCE` consumption note (consumed-only + the WI-F item-read field). No route added/removed/re-gated.
- **Done-check:** `INDEX.md` ceilings updated (`DF5-1..11`, `FE-12`); no stable-tier file but `FRONTEND.md` modified; no live `INV-n`/`D-n` renumbered.

---

## Appendix A — Decisions
A-1 dedicated upload handler (RESOLVED) · A-2 additive manifest (RESOLVED) · A-3 picker paginated-only · A-4 direct presigned download · A-5 assurance read-only manifest · A-6 omit uploader in MVP (RESOLVED).

## Appendix B — Source-verification register
Closed r2: V-1, V-2, V-3, V-4, V-7, V-8, V-10. Execution confirms: V-5, V-6, V-9, in-service upload gate, V-11 (EVD-1/2 ids). Client surfaces whatever code the server returns for V-5/V-6. `SPRINTS.md` superseded by live code on any disagreement.