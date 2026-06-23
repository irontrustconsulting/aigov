# UI-F5-EVIDENCE — Design Doc (FINAL, review r1 + source-verified r2)

**Status:** DESIGN, review round 1 dispositioned + §0 source-verified against live repo (round 2). A-1/A-2/A-6 resolved from code; V-7/V-8/V-1/V-2/V-3/V-4/V-10 closed; V-5/V-6/V-9 and upload-gate-enforcement remain execution-time confirms. Ready for handoff.
**Surface:** Evidence repository home (`apps/tenant/app/evidence`, **NEW**) + per-item evidence linking on the AIIA work surface (`apps/tenant/app/use-cases/[id]`, **ALTER**)
**Faces:** both. Adoption (system_owner / contributor: upload, link, manage) + assurance (reviewer / authoriser / auditor: browse, download, read linked manifest). admin → empty-state.
**Closes:** `DF3-1` / A2.
**Backend delta (confirmed):** one additive response-shape addition — a self-describing `evidence_links` manifest on the AIIA item read (V-7: absent today; `EvidenceLinkRead` is ids-only so a richer per-item shape is required). DF3-7 pattern: batch-loaded in `assemble_aiia_items`, no migration (data in `assessment_item_evidence`). No new route, table, enum, or migration.
**If-Match:** **none.** No evidence or evidence-link route accepts it (verified). `FE-6` dormant.
**Invalidation scope:** after link/unlink, refetch the **AIIA detail only**, never the lifecycle / whose-court vector (`DF5-10`, `D-29`).
**New convention (lands this sprint):** `FE-12` — file bytes stream through a dedicated BFF upload handler; the generic `[...path]` proxy is byte-unsafe for uploads (§5, verified). Appended to FRONTEND.
**Depends on:** F3 (`use-cases/[id]`, `assemble_aiia_items`), F0 (BFF proxy, `@irontrust/api-client`, `@irontrust/ui`).
**Source-of-truth caveat (D-21):** verified against `app/schemas/{evidence,assessment,export}.py`, `app/routers/v1/{evidence,assessments}.py`, `apps/tenant/app/api/proxy/[...path]/route.ts`, INVARIANTS/DATA-MODEL. The Sprint 4 *plan* (presigned-PUT, pending/active status) did not ship — live is single multipart `POST /v1/evidence`, no status enum.

---

## 1. Objective

Give evidence a home and make it linkable. Backend stores evidence (Sprint 4); F3 reads item evidence references as manifest text but cannot upload, browse, download, or link/unlink (`DF3-1`). This sprint wires the Sprint-4 capability into the tenant spine. Satisfies `EVD-1` (repository) and `EVD-2` (linking) — exact ids confirm at V-11 (`EVD-3` assignment / `EVD-4` freshness confirmed deferred). Out of scope: `EVD-3`, `EVD-4`, supersession/soft-void, AV scanning — post-MVP per STATE.

---

## 2. Resolved-decisions table (present vs ALTER)

| Object | Disposition | Note |
|---|---|---|
| `apps/tenant/app/evidence` | **NEW** | Repository home: list, upload, download, delete |
| `apps/tenant/app/use-cases/[id]` | **ALTER** | Per-item link/unlink + current-links manifest render |
| `packages/api-client` | **ALTER** | Evidence + evidence-link contracts; dedicated multipart upload helper (§5) |
| `packages/ui` | **ALTER** | Evidence table, upload control, file-row, link-picker, link-chip |
| `AssessmentItemRead` | **ALTER (additive, CONFIRMED)** | Add self-describing `evidence_links` manifest (V-7 absent; `EvidenceLinkRead` ids-only) |
| BFF upload path | **NEW (dedicated handler)** | Generic `[...path]` proxy is byte-unsafe for uploads (§5, V-8) |
| `FRONTEND.md` | **ALTER (append-only)** | Append `FE-12` |
| Backend routes / evidence + link schema | **PRESENT** | Shipped Sprint 4; consumed-only (modulo the item-read manifest delta) |

---

## 3. Surface decomposition & role branch

### 3a. Repository home — `apps/tenant/app/evidence` (NEW)

Read: `GET /v1/evidence?limit&cursor` (`gov:ALL`, cursor `next_cursor`, carries `link_count`). Rows render `title`, `content_type`, `size_bytes`, `sha256` (integrity, truncated with copy), `created_at`, `link_count`. Evidence carries **no provenance** (`D-19`) — no badge, `FE-5` does not apply (`DF5-1`). **Uploader display omitted in MVP** (`DF5-11`, A-6): `EvidenceRead.uploaded_by_user_id` is a bare UUID, no durable name; naming would need an additive `uploaded_by_name` via an `INV-34` read-time join (D-25-safe, DF4-6 precedent), deferred to hold the single-additive-delta budget.

Acts:
- **Upload** (`gov:write` = system_owner / contributor): `POST /v1/evidence` multipart `{file, title?}` → `EvidenceRead`. Via the dedicated BFF upload handler (§5). On success, invalidate the list.
- **Download** (`gov:ALL`): `GET /v1/evidence/{id}` → `EvidenceDetailRead` (`download_url`: short-TTL presigned S3 URL, hardened — `INV-22`). Browser navigates to that URL; **never inline-renders bytes** (`INV-22`). Fetched **only on explicit download intent** — the detail read stages `evidence.access` (`DF5-3`).
- **Delete** (`gov:write`): `DELETE /v1/evidence/{id}` (204). Pristine guard (`INV-19`): a linked row cannot be deleted. Control **disabled-with-reason when `link_count > 0`** (`FE-8`, `DF5-6`); the server rejection code (V-5, open) is authoritative over advisory `link_count`.

Role branch: system_owner / contributor → full. reviewer / authoriser / auditor → read-only (browse, download; no upload/delete — `FE-8` absent). admin (zero gov roles) → empty-state, **no `gov:ALL` call** (`DF5-7`; verified: admin gets 403 on every gov route).

### 3b. Per-item linking — `apps/tenant/app/use-cases/[id]` (ALTER)

On each AIIA item (`assemble_aiia_items` read):
- **Render current links** — self-describing manifest per item from the new `evidence_links` field (`evidence_id, title, sha256, content_type, size_bytes`; **no `download_url`**, so rendering triggers no `evidence.access`). Renders from the item read alone — no repository load, no per-id detail fetch.
- **Link** (`gov:write`): `POST /v1/assessments/{aid}/items/{iid}/evidence-links` `{evidence_id}` → `EvidenceLinkRead`. Picker reads `GET /v1/evidence` (on intent, A-3). **Disposition-gated** (`INV-20`): a still-`AI_SUGGESTED` item rejects the link — control **present-but-disabled-with-reason** (`FE-8`, `DF5-5`). Control-link stays free (`INV-20` asymmetry) — do not mirror.
- **Unlink** (`gov:write`): `DELETE /v1/assessments/{aid}/items/{iid}/evidence-links/{evidence_id}` (204, idempotent). **Path param is `evidence_id`** — link table keyed `UNIQUE(item_id, evidence_id)` (verified); never a link-row id (`DF5-9`).
- After link/unlink: invalidate-and-refetch the **AIIA detail only** (`staleTime: 0`, `FE-7`); **not** the lifecycle / whose-court vector — evidence is not a gate input (`D-29`: interactive coverage runs `require_evidence_for_satisfied=false`; the assessment gate is structural-readiness + `assessment_approved`) (`DF5-10`).

Role branch: system_owner / contributor → link/unlink (disposition-gated). reviewer / authoriser / auditor → read-only manifest per item (assurance face; no controls — `FE-8`, A-5). admin → empty-state (existing F3).

---

## 4. Routes consumed (all verified)

| Method · Path | Gate | If-Match | Use |
|---|---|---|---|
| `GET /v1/me` | member | — | role branch + admin empty-state (`DF5-7`) |
| `GET /v1/evidence?limit&cursor` | gov:ALL | — | repository list (`link_count`, `next_cursor`) + link picker |
| `POST /v1/evidence` | gov:write (in-service) | — | upload (multipart, dedicated handler §5) |
| `GET /v1/evidence/{id}` | gov:ALL | — | presigned download (on intent — stages `evidence.access`) |
| `DELETE /v1/evidence/{id}` | gov:write | — | pristine delete (INV-19) |
| `POST /v1/assessments/{aid}/items/{iid}/evidence-links` | gov:write | — | link (disposition-gated, INV-20) |
| `DELETE /v1/assessments/{aid}/items/{iid}/evidence-links/{evidence_id}` | gov:write | — | unlink (idempotent; by evidence_id) |
| `GET /v1/assessments/{id}` | gov:ALL | — | AIIA detail + new per-item `evidence_links` manifest (WI-F) |
| `GET /v1/use-cases/{id}` · `.../assessments` · `GET /v1/systems/{id}/rollup` | member / gov:ALL | — | F3 context, unchanged |

**Gate footgun (verified, carry to handoff):** `POST /v1/evidence` depends only on `get_tenant_context` — **no route-level governance gate**; the `gov:write` check is inside `evidence_service.upload_evidence` (the route passes no `db`). Gate the upload control client-side (`FE-8`); a non-gov caller gets a **service-level 403**. (Service body not in the provided slice — confirm the in-service `require_governance_role` is actually present at execution; security-relevant.)

---

## 5. The hard part — file bytes through the BFF (`FE-12`, A-1 RESOLVED, V-8 CLOSED)

The F0 proxy (`apps/tenant/app/api/proxy/[...path]/route.ts`) forwards bodies with `body: hasBody ? await request.text() : undefined`. `request.text()` **UTF-8-decodes and buffers the whole body**, which corrupts binary file bytes and the multipart boundary. **The generic proxy therefore cannot carry an evidence upload** — option (a) "reuse `[...path]`" is ruled out by code.

**Resolution (A-1):** a **dedicated tenant BFF upload route handler** (e.g. `apps/tenant/app/api/evidence-upload/route.ts` or a multipart branch keyed off `content-type`) that forwards the **raw bytes** to `POST /v1/evidence` — pipe `request.body` (ReadableStream) or pass `request.arrayBuffer()`/`Blob`, never `request.text()` — preserving the inbound `multipart/form-data` `Content-Type` and boundary. It reuses the existing session lookup + bearer-forward and the CSRF origin / `Sec-Fetch-Site` check (`NFR-1`).

**`FE-12` (the rule, regardless of file path):** file uploads route through a dedicated BFF handler that forwards raw bytes (never `request.text()`), preserves the multipart content-type/boundary, holds no bytes at rest beyond transit, applies the CSRF check, and is browser→BFF→API only. **Asymmetry:** *upload* browser→BFF→API→S3; *download* browser→BFF(`GET detail`)→presigned URL→browser→S3 directly (S3 ≠ API, so the hardened short-TTL public-endpoint URL does not breach `INV-50`). Body-size: the router sets no cap (V-9, open); the BFF imposes a ceiling and surfaces a clear too-large error, not a bare 413.

---

## 6. Invariants & conventions the surface must honour

1. `INV-50` / `D-37` / `FE-2` — no token in browser; upload via dedicated BFF handler, reads via BFF.
2. `INV-22` — download hardened, never inline; follow the presigned `download_url`, render no bytes. *(Not `FE-5` — N1.)*
3. `INV-19` — pristine delete; delete disabled-with-reason on `link_count > 0` (`DF5-6`).
4. `INV-20` / `D-20` — evidence-link disposition-gated; control-link not; do not mirror (`DF5-5`).
5. `D-19` — evidence outside the provenance machine, no badge (`DF5-1`). *(`INV-21` is only the no-direct-table half — N2.)*
6. `INV-6` — pointer-only; show `sha256` as the integrity signal, never reconstruct bytes.
7. `FE-7` / `D-29` — invalidate AIIA detail only after link/unlink; not the lifecycle vector (`DF5-10`).
8. `FE-6` — dormant: no `If-Match` on any evidence route (verified) (`DF5-4`).
9. `FE-8` / `UX-5` — upload/delete/link/unlink absent for read-only roles; disposition/`link_count` blocks disabled-with-reason.
10. `FE-9` — TanStack through the BFF; mutations via BFF; never client `tenant_id` (`INV-3`) / `provenance` (`INV-13`).
11. `INV-40` (spirit) — the per-item `evidence_links` manifest carries no bytes and no presigned URL; retrieval stays on `GET /v1/evidence/{id}`.
12. `UX-3` / `UX-6` — owner's vocabulary ("documents / files"); attach a file, the system handles hash/storage/manifest.

---

## 7. Sprint-local decisions (`DF5-n`)

- **DF5-1** — Evidence renders as a plain artifact, no provenance badge; `FE-5` n/a (`D-19`).
- **DF5-2** — Upload via a dedicated BFF handler forwarding raw bytes (`FE-12`); the generic proxy is byte-unsafe (V-8).
- **DF5-3** — `GET /v1/evidence/{id}` fetched only on explicit download intent (stages `evidence.access`); the per-item manifest carries no `download_url`, so it triggers none.
- **DF5-4** — No `If-Match` on any evidence route; `FE-6` dormant.
- **DF5-5** — Link control disposition-gated (`INV-20`): present-but-disabled on AI_SUGGESTED; control-link asymmetry preserved.
- **DF5-6** — Delete disabled-with-reason on `link_count > 0` (`INV-19`); server code authoritative.
- **DF5-7** — admin → empty-state, no `gov:ALL` evidence call (`DF2-5`; verified admin-403).
- **DF5-8** — Additive `evidence_links` on `AssessmentItemRead` is a **self-describing manifest** (`evidence_id, title, sha256, content_type, size_bytes`; no `download_url`), batch-loaded in `assemble_aiia_items` — not an ids-only `EvidenceLinkRead` mirror, so the surface needs no repository load and triggers no per-id `evidence.access`.
- **DF5-9** — Unlink by `evidence_id` (table `UNIQUE(item_id, evidence_id)`), never a link-row id.
- **DF5-10** — Link/unlink invalidates AIIA detail only, never the lifecycle vector (`D-29`).
- **DF5-11** — Uploader display omitted in MVP (`uploaded_by_user_id` is a bare UUID); naming deferred to an additive `uploaded_by_name` INV-34 join (D-25-safe).

---

## 8. Design-level work-item decomposition (rationale-bearing; handoff is separate)

- **WI-A** — `@irontrust/api-client`: evidence + evidence-link contracts; dedicated multipart upload helper; no `If-Match`.
- **WI-B** — `@irontrust/ui`: evidence table, upload control, file-row, link-picker (paginated, A-3), link-chip + unlink, `FE-8` disabled-with-reason reuse.
- **WI-C** — Dedicated BFF upload handler (raw-byte forward; CSRF; size ceiling); `FE-12`. **Do not route upload through `[...path]`.**
- **WI-D** — `apps/tenant/app/evidence` (NEW): list + upload + download + delete; 5-way role branch + admin empty-state.
- **WI-E** — `apps/tenant/app/use-cases/[id]` (ALTER): per-item manifest + link/unlink (disposition-gated); assurance read-only manifest.
- **WI-F** — Backend additive `evidence_links` self-describing manifest on the item read (DF5-8), batch-loaded.
- **WI-G** — Canonical update (STATE; DATA-MODEL for the item-read shape; append `DF5-1..11` + `FE-12`; close `DF3-1`/A2).

Done-checks tie to: upload round-trips a **binary** file end-to-end with a matching `sha256` (proves the dedicated handler preserves bytes; a `request.text()` path would fail this); download follows the hardened presigned URL (attachment, no inline) with a single detail fetch and no eager per-row prefetch; delete blocked on linked / succeeds on unlinked; link rejected on AI_SUGGESTED, accepted post-confirm; unlink idempotent by evidence_id; link/unlink invalidates the AIIA-detail key but **not** the lifecycle key; reviewer/auditor see the read-only manifest with no controls; admin empty-state issues no evidence call; no `If-Match` on any evidence call.

---

## §0 — Pre-flight verify register (source-verified r2)

| V | Item | Result |
|---|---|---|
| V-1 | `evidence` / `EvidenceRead` shape; status enum; uploader FK | **Closed.** id, title, content_type, size_bytes, sha256, `uploaded_by_user_id` (bare UUID), created_at, updated_at. No status field/enum. |
| V-2 | `EvidenceListResponse` | **Closed.** `EvidenceListItem`=`EvidenceRead`+`link_count`; `{items, next_cursor}`. |
| V-3 | `EvidenceDetailRead` | **Closed.** adds `download_url`; `GET /{id}` stages `evidence.access` (STATE). |
| V-4 | `EvidenceLinkCreate`/`EvidenceLinkRead` | **Closed.** create `{evidence_id}`; read `{id,item_id,evidence_id}` (ids only → DF5-8 manifest). |
| V-5 | `DELETE /evidence/{id}` code when linked | **Open.** Service body not in slice; confirm 409/404/422 at execution. |
| V-6 | `POST .../evidence-links` code on AI_SUGGESTED | **Open.** Service body not in slice; confirm 409/422 at execution. |
| V-7 | `AssessmentItemRead` evidence exposure | **Closed.** has `control_links`, **no `evidence_links`** → WI-F. |
| V-8 | BFF `[...path]` body handling | **Closed.** `await request.text()` buffers + corrupts binary → dedicated handler mandatory (§5). |
| V-9 | `POST /evidence` size/content-type cap | **Open.** No router-level cap; API/config not in slice; BFF imposes the ceiling. |
| V-10 | Gates | **Closed.** upload in-service (footgun), reads gov:ALL, delete/link/unlink gov:write, admin 403. |
| V-11 | `EVD-1/2` ids | **Partial.** EVD-3/4 deferred confirmed; EVD-1/2 mapping inferred (REQUIREMENTS not in slice). |
| upload gate | in-service `require_governance_role` present? | **Open.** Asserted by canon; service body not in slice; confirm (security-relevant). |

---

## Appendix A — Open decisions (resolved at r2 where marked)

- **A-1 · BFF upload path — RESOLVED.** Dedicated streaming handler; generic `[...path]` is byte-unsafe (`request.text()`). Codifies `FE-12`.
- **A-2 · Per-item current-links read — RESOLVED.** Additive self-describing `evidence_links` manifest on `AssessmentItemRead` (V-7 absent; ids-only `EvidenceLinkRead` insufficient). DF5-8.
- **A-3 · Link-picker search.** MVP paginated-only (`limit`/`cursor`; no `?q=`), client-side filter over the loaded page; backend `?q=` a follow-on nudge.
- **A-4 · Download mechanism.** Direct browser navigation to the presigned `download_url` (S3 ≠ API; `INV-50` not engaged).
- **A-5 · Assurance-face per-item evidence.** Include the read-only manifest for reviewer/authoriser/auditor; controls absent (`FE-8`).
- **A-6 · Uploader attribution — RESOLVED.** Omit in MVP (`uploaded_by_user_id` is a bare UUID; naming needs an additive `uploaded_by_name` INV-34 join, D-25-safe, deferred).

---

## Appendix B — Source-verification register

Verified r2 against `app/schemas/{evidence,assessment,export}.py`, `app/routers/v1/{evidence,assessments,export}.py`, `apps/tenant/app/api/proxy/[...path]/route.ts`, INVARIANTS, DATA-MODEL. **Remaining execution-time confirms:** V-5, V-6, V-9, the in-service upload gate, and V-11's EVD-1/2 ids (REQUIREMENTS not in the provided slice). The client handles V-5/V-6 by surfacing whatever rejection code the server returns. The Sprint 4 plan is superseded by live code wherever they disagree.

---

## Appendix C — Disposition log

**Review round 1 (design review):**

| Finding | Disposition | Resolution |
|---|---|---|
| N1 · FE-5 miscited | Accepted | INV-22 alone (§3a, §6.2) |
| N2 · D-19/INV-21 over-pair | Accepted | D-19 for provenance, INV-21 for no-direct-table (§6.5) |
| N3 · invalidation scope | Accepted | DF5-10, verified against D-29; pinned in done-check |
| S1 · A-6 source | Accepted | V-1 extended; resolved r2 (bare-UUID FK) |
| S2 · EVD ids | Accepted | V-11 (partial r2) |
| S3 · V-8 live-only | Accepted | Closed r2 by repo inspection |

**Source-verification round 2 (live repo):**

| Item | Outcome |
|---|---|
| V-8 | Generic proxy `request.text()` corrupts binary → A-1 resolved to a dedicated handler; FE-12 gains the byte-safety clause; surface table + WI-C updated. |
| V-7 | `evidence_links` absent from `AssessmentItemRead` → WI-F confirmed. |
| V-4 → DF5-8 | `EvidenceLinkRead` ids-only → WI-F made a self-describing manifest (no repository load, no `evidence.access` spam). |
| A-6 / V-1 | `uploaded_by_user_id` is a bare UUID → DF5-11 omits uploader display in MVP. |
| V-1/2/3/10 | Closed as documented. V-5/V-6/V-9 + upload-gate remain execution confirms. |