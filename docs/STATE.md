# STATE.md — IronTrust AI Governance Platform

**Location:** `docs/STATE.md` — single source, mirrored to project knowledge. **The most volatile canonical — updated every sprint.**
**Purpose:** What is implemented and what must not be reinvented, at the level of *what exists · what shape · which gate*. It points outward for depth and never restates the detail.
**Lanes:** constraints → `INVARIANTS.md` (`INV-n`); schema (tables/enums/indexes) → `DATA-MODEL.md`; auth / identity / RLS / session mechanics → `ARCHITECTURE.md`; implementation shapes → `PATTERNS.md` (`PAT-n`); decisions/rationale → `DECISIONS.md` (`D-n`); conceptual model → `DOMAIN.md`.

**Current through:** UI-F6-AUDITPACK (audit/coverage capstone — control-coverage view, export/audit pack, ATO document). Sprints 1–7b + UI-F1..F6 built (tenant UI plane complete).

---

## 1. Implemented capabilities

### System registration & intake
`POST /v1/systems` captures intake metadata: single-select vocab FKs (`operator_role_id`, `hosting_model_id`, `usage_context_id`, `human_oversight_type_id`, `catalogue_product_id`), `lifecycle_stage`, `is_custom`, multi-select `data_category_ids`/`affected_party_ids` (via `system_data_category`/`system_affected_party`), free-text `purpose` → `metadata_blob`. Vendor derived from product. `is_custom` + any catalogue FK → 422 (DB check `ck_system_custom_no_catalogue`). Vocab/link IDs must be `active=true` (422); `owner_user_id` must be a tenant member. `GET /v1/systems/{id}` → `SystemDetail` (resolved labels, `data_categories` with `is_special_category`, `affected_parties` with `is_vulnerable_group`, `use_case_count`, per-use-case states). `PATCH` updates a subset; link arrays replace; changing `catalogue_product_id` with use cases present → 409. Gates: `POST`/`PATCH` `system_owner`; `GET` any member. Audit `system.created`/`updated`.

### Catalogue prefill
`GET /v1/systems/{id}/prefill` → `catalogue_fact` rows (`key`, `value`, `source_url`, `source_label`, `last_checked_at`, `provenance`) — display-only confirm/amend panel. No product (incl. `is_custom`) → `200` empty, never `404`. No write-back.

### Classification — bridge (gate 1)
Auto-resolved on use-case creation via the reference bridge (`system → product → product_category → eu_ai_act_subcategory`). Unresolvable (no product / no primary mapping) → `REQUIRES_CONTEXT` → context gate. Snapshots versioned; overrides tracked (proposed/override tier, justification, actor) in `Classification` + `AuditEvent`. Resolution/persistence separated (INV-11; PAT-5).

### Classification — context-question gate (gate 2)
Versioned decision tree (`decision_tree`/`_question`/`_option`, global) seeded from YAML, content-hashed, fails loud on frozen-version mutation. `GET .../classification/context` (residual questions + snapshot); `POST .../context/preview` (pure read); `POST .../context` (submit → `PENDING_REVIEW` snapshot; does **not** stamp `eu_tier`; `system_owner`/`contributor`, override-to-different-tier needs `system_owner`); `POST .../classification/sign-off` (`reviewer`; `PENDING_REVIEW → APPROVED`, stamps `eu_tier` — D-9). Resolution deterministic, fail-closed (INV-12).

### AIIA core
`POST /v1/use-cases/{id}/assessments` creates the AIIA from the use case's **current** `Classification` snapshot; rejects `PROHIBITED`/`REQUIRES_CONTEXT`/no-snapshot (409). One current AIIA per use case (`uq_one_aiia_per_use_case`). Pre-fills in one transaction: tier-scoped section template (`CATALOGUE_CURATED` blanks); register facts snapshotted point-in-time (provenance handling per PAT-8 — note the register-fact tagging open item there); identity-only `AI_SUGGESTED` risk proposals via `propose_risk_set` (never scores). `GET .../sections`; `POST .../items {section_key}`; `PATCH .../items/{item_id}` (authoring fields; single conditional `UPDATE`, `lock_version`/`If-Match`, 412/409 — PAT-6); `POST .../items/{item_id}/confirm`; control-links. Pristine-delete only (INV-17, 36). Gates: create/delete `system_owner`; item/link writes `{system_owner, contributor}`; reads any governance role.

### AIIA feeders (FRIA / DPIA / MODEL_RISK)
`POST /v1/assessments/{aiia_id}/feeders {type}` — an `Assessment` row with `parent_aiia_id`; `type=AIIA` rejected (422); feeder-of-feeder rejected (422); one per type (`uq_feeder_type_per_aiia`). Scope copied from parent, never re-resolved (INV-15). Per-type register pre-fill. `propose_risk_set` is layer-aware (AIIA → governance-layer + `CatalogueProductRisk`; MODEL_RISK → OWASP technical; FRIA/DPIA → none). `GET /v1/assessments/{aiia_id}` assembles native + feeder-surfacing items at read time (`assemble_aiia_items`, INV-16; PAT-7). `GET .../feeder-recommendations` (required/recommended/N-A + basis). Feeder delete reuses the pristine path; parent delete cascades (`passive_deletes`, INV-47).

### Evidence repository
`POST /v1/evidence` (multipart) — server SHA256 over a two-pass spool, tenant-prefixed key, SSE; the S3 put holds no DB transaction (PAT-3, INV-18); commit failure compensates the S3 object. `GET /v1/evidence` (cursor-paginated, `link_count`); `GET /v1/evidence/{id}` (metadata + short-TTL presigned download, hardened — forced attachment, neutralised content-type, public endpoint; stages `evidence.access`; INV-22). `DELETE` is a single guarded statement (INV-19). Link/unlink evidence to items — disposition-gated (INV-20), idempotent unlink. Evidence → control is transitive via items only (INV-21). Gates: write/link `{system_owner, contributor}`; reads all five governance roles.

### Product lifecycle, gates & approvals
The use-case lifecycle is a determinate state machine (states → DOMAIN §6; enum → DATA-MODEL). `apply_transition` is the sole writer of `use_case.state` (INV-24). Six gate predicates (`lifecycle_gates.py`): vendor/product (tenant `VendorApproval`/`ProductApproval`, auto-pass when no catalogue link), classification readiness, assessment (structural readiness + `assessment_approved`), treatment, authorisation. `advance_use_case` auto-drives (step-0 PROHIBITED halt, INV-26; ceiling at `pending_authorisation`). `full_vector`/`re_evaluate` are the source of truth (INV-25, 35). `PUT /v1/vendors|products/{id}/approval` (`authoriser`) fans out per use case (mid-request commit + re-`set_config`, INV-27). `GET /v1/systems/{id}/rollup`, `/v1/portfolio`. Treatment fields written via `amend_item`, provenance-neutral.

### AIIA review & sign-off (Sprint 6a)
`Assessment` status `DRAFT → IN_REVIEW → APPROVED`, reopen `APPROVED → NEEDS_REFRESH`, bounce `IN_REVIEW → DRAFT`. `submission_round` cycle key. `AssessmentReview` domain row per decision (D-6). Service `assessment_review_service.py`: `submit_for_review` (`system_owner`), `record_review` (`reviewer`; `APPROVED` → same-transaction `advance_use_case`), `reopen` (`system_owner`), `list_review_queue`. Act-SoD via `assert_distinct_workflow_actor` (INV-28). Authoring status-lock (INV-31). Endpoints `submit`/`review`/`reopen`/`review-queue`.

### Deployment authorisation / ATO (Sprint 6b)
`DeploymentAuthorisation` — point-in-time ATO, text-stamped tier/identity/residual (D-13, D-14). `authorisation_gate` cycle-matches `submission_round` (INV-37). `authorise_use_case` (`authoriser`; recomputes `full_vector`; act-SoD; inserts ATO; `pending_authorisation → authorised` via the `authorise` event). `authorised` is entered **only** here (INV-35); prohibited is supreme even from `authorised` (INV-33). `POST /v1/use-cases/{id}/authorise`; `GET .../authorisation` (most recent + computed `live_state`, INV-32, 44).

### Control coverage view (Sprint 7a)
Read-only coverage engine (CTL-3), **zero migrations / no new schema**. `GET /v1/coverage` (tenant), `/v1/systems/{id}/coverage`, `/v1/assessments/{id}/coverage` (422 on a feeder id). `coverage_service` recomputes per request, never persists (INV-25). Qualifying-link filter: dispositioned items only, governing-AIIA `APPROVED` (INV-38). Per-control roll-up `SATISFIED`/`PARTIAL`/`OPEN`/`UNADDRESSED`, most-favourable-wins, with a `breakdown` (shown reasoning). Cross-framework satisfaction is structural, not inferred (INV-39, D-26). Interim denominator = controls-in-play + flagged `unaddressed_controls` (D-28); applicability denominator deferred (OPEN-3). `framework=`/`include_unapproved=` params; `require_evidence_for_satisfied` (default `false`; `true` in export — D-29). No audit (pure read). Response schemas only.

### Export / audit pack (Sprint 7b)
Structured-JSON export (EXP-1 data half; PDF deferred), **zero migrations / no new schema**, in `app/routers/v1/export.py`. `GET /v1/systems/{id}/export`, `/v1/use-cases/{id}/export`, `/v1/use-cases/{id}/authorisation/document` (EXP-1a; 404 if never authorised), `/v1/export?framework=`. `export_service`: `build_use_case_export`/`build_system_export`/`build_ato_document`/`build_framework_export`. Live assembly + canonical `content_hash` (INV-43, D-30); self-owned `REPEATABLE READ` session that owns the `export.generated` commit (PAT-10, D-35). Evidence by manifest, never bytes/URLs (INV-40, D-31). AIIA section = native items + `surfaces_into`, never `assemble_aiia_items` (INV-41, D-32). Audit-trail closure = entity-id OR `detail` back-ref, bounded residual (INV-45, D-33). ATO-basis honesty (INV-44, D-34). Export coverage calls pass `require_evidence_for_satisfied=true` (D-29). Gate: any-governance-role read (auditor). Stages `export.generated`.

### Member management
A tenant admin creates members (Cognito invite + `Membership(MEMBER, zero governance roles)` atomic with compensation — PAT-1). Listing is driven from `membership` joined to `app_user` with Cognito accept status; never bare `app_user` (INV-2).

### Governance role management
Full assign/revoke/list-by-tenant/list-by-member. SoD enforced at assignment via `assert_governance_assignable` (INV-7). Read-only catalogue endpoint returns the five roles + the full conflict matrix.

### Reference data (read-only, cross-tenant)
Product-category hierarchy, vendors/products by category, EU subcategory list — anonymous (back the public-ish wizard). `GET /v1/reference/products/{id}` (intake wizard detail). `GET /v1/reference/risks` (filter `layer`), `/v1/reference/controls` (filter `framework`) — member-level. `GET /v1/reference/{operator-roles,hosting-models,usage-contexts,human-oversight-types,data-categories,affected-parties}` (UI-F1-INTAKE WI-0; any tenant member; `active=true` rows, `sort_order`) — the six intake-vocab tables' list routes, backing the wizard's structured selects (`DF1-9`). Seeded: six controlled-vocab tables, control library (ISO 42001 / EU AI Act cross-map), risk library (OWASP LLM + NIST/ISO with risk→control links), EU taxonomy, product-category taxonomy, governance-role catalogue + conflict matrix, decision tree, AIIA/feeder section template.

### Platform (operator-facing)
Tenant provisioning (Cognito + DB, orphan-free — PAT-1); tenant listing; durable operator identity endpoint (`GET /platform/me`, authenticated-operator-only, `D-39` — `GET /platform/whoami` struck `UI-F7-PROVISION`). Operator creation via HTTP (`POST /platform/operators`, `UI-F8-OPERATOR-RBAC`); operator + role listing; `platform_admin` role + `operator:create` permission seeded; operators surface in operator console.

### UI foundation (`UI-F0-FOUNDATION`)
Two Next.js App Router BFF apps, `apps/tenant` (port 3000) and `apps/operator` (port 3001), pnpm/Turborepo monorepo. Each app's own Next server runs the Cognito authorization-code + PKCE flow against that plane's pool, holds the ID/refresh token server-side in a session store keyed by an opaque session id (MVP: in-memory, dev-only — `lib/auth/in-memory-session-store.ts`), and forwards the bearer ID token to the API via a per-app BFF proxy (`app/api/proxy/[...path]/route.ts`); the browser never holds a token (`INV-50`). CSRF guard (`Sec-Fetch-Site`/`Origin`) on state-changing BFF routes. Shared packages: `@irontrust/tokens` (one primitive token layer as Tailwind v4 `@theme` custom properties, two skins via `[data-theme]`); `@irontrust/ui` (Radix+Tailwind primitives, the FE-4 structured-input set, the FE-5 prefill-with-basis control, the FE-8 SoD-visible `SodAction` wrapper, 412/409 banners, a scaffold whose-court indicator); `@irontrust/api-client` (typed BFF-only fetch wrapper, `If-Match`/412→`StaleLockError`/409→`BadFromStateError` mapping, runtime+compile-time guard against client-supplied `tenant_id`/`provenance`, the mandatory `useLiveState` hook for lifecycle/gate-vector/coverage/authorisation reads). `packages/eslint-plugin-irontrust` enforces the package boundary, the no-literal-token-value rule, and the no-raw-live-state-query rule. Smoke surfaces only (`/dashboard` per app, calling `GET /v1/whoami` / `GET /platform/me` and, on the tenant side, `GET /v1/me` for a role-aware affordance render) — not a feature surface; the intake wizard is next. Added `GET /v1/me` (W-BE): the caller's own membership + administrative role + governance roles, self-scoped only (no path param), filling the gap left by `governance-roles/assignments/member/{membership_id}` (which takes a foreign id with no self-check).

**Post-sprint infrastructure corrections (2026-06-24):** Both apps' root `app/page.tsx` was a bare stub; now server-redirects to `/dashboard`. Auth callback (`app/api/auth/callback/route.ts`) redirected to app origin root after login; now redirects directly to `/dashboard`. Session store (`lib/auth/in-memory-session-store.ts`) was module-scoped; pinned to `globalThis` in both apps so Next.js HMR module re-instantiation in dev no longer wipes live sessions. Operator console layout now auto-redirects to `/api/auth/login` when `GET /platform/me` errors (session expired/wiped), rather than silently collapsing to an empty nav. Provisioning form mutation now handles 401 (redirect to login) and unexpected 5xx (visible error message) — previously failed silently.

Both Cognito pools' OAuth/PKCE/hosted-UI-domain config is applied (`infra/cognito_tenant.tf`, `infra/cognito_operator.tf`) against the real, pre-existing tenant pool (`eu-west-2_yW42jUA1i`, imported into Terraform state for the first time this sprint — it predates IaC management) and the existing operator pool — both updated in place, same pool/client ids, zero data loss. A `terraform apply` run without the prior `terraform import` step briefly created a duplicate empty tenant pool; caught via `terraform plan`/AWS describe before any further drift, the duplicate was destroyed and the real pool imported and updated cleanly. `terraform plan` shows no drift as of this sprint's close.

### Intake / registration wizard (`UI-F1-INTAKE`)
`apps/tenant/app/systems/new` — the first tenant feature surface (adoption face, `UX.md` §5), pure wire-up over landed S1/S2/S5 routes plus the F0 shared packages, with one additive backend addition (`DF1-9`: the six intake-vocab list routes). A single-page wizard (`page.tsx`) driven by a reducer (`wizard-state.ts`) over the steps: drill-down (category → vendor → product, or "not in catalogue / in-house" exit) → structured capture (`POST /v1/systems`) → catalogue-fact prefill confirm (display-only, `DF1-4`/`DF1-8`) → use-case create (`POST /v1/use-cases`), branching on the create response in this precedence order: `requires_context` → the context-question gate sub-surface (preview-before-commit, the UNRESOLVED loop, `POST .../context`) → resolved tier + the gate-1 override ladder (`POST .../classify/override`, structurally tier/subcategory-matched) → whose-court (`GET .../lifecycle`, reading `blocking.responsible_party`/`reason` for real semantics — replaces the F0 generic pill). Role-aware at the page root via `GET /v1/me` (`D-24`): system_owner gets the full spine; a bare contributor/member gets a "needs a system owner" empty-state (capture is system_owner-only); reviewer/authoriser/auditor get an assurance-read message — this surface has no capture controls for them. `override_tier`/`classify/override` controls are `SodAction`-barred (absent, not disabled) for non-system_owner, backed server-side by `require_governance_role("system_owner")` (verified: a forced contributor call now asserted 403 in `tests/test_use_case_classification.py::test_override_by_non_system_owner_gets_403`, closing a gap the existing suite hadn't covered). Confirmed absent at this sprint's pre-flight and still absent: `POST .../advance` and `GET /systems/{id}/approval-status` — vendor/product clearance is surfaced via the lifecycle `blocking` vector instead (`C-3`). Reviewer sign-off (`DF1-3`) and `If-Match`/`FE-6` (`DF1-5`, asserted dormant by test) are out of scope for F1.

### Use-case work surface / AIIA authoring (`UI-F3-ASSESS`)

`apps/tenant/app/use-cases/[id]` — the third tenant feature surface. Pure wire-up over existing assessment routes; no new backend routes, tables, or enums. One additive backend schema delta: `control_links: list[ControlLinkRead] = []` added to `AssessmentItemRead` (and batch-loaded in `assemble_aiia_items` via `_batch_control_links` — one query, no N+1) so the GET /assessments/{id} response includes linked controls on page load. `app/schemas/assessment.py` and `app/services/assessment_service.py` only; no migration.

Route `use-cases/[id]`. `GET /v1/me` fetches first; four-way role branch: **admin** (zero governance roles) → admin/empty-state, no `gov:ALL` call; **reviewer/authoriser/auditor** → assembled AIIA read-only, no author controls; **contributor** → item-author + control-link only, bootstrap/submit/re-evaluate absent (FE-8 structural); **system_owner** → full author mode.

Consumed routes: `GET /v1/me` · `GET /v1/use-cases/{id}` · `GET /v1/use-cases/{id}/assessments` · `GET /v1/use-cases/{id}/lifecycle` · `GET /v1/systems/{id}/rollup` · `GET /v1/assessments/{id}` · `GET /v1/assessments/{id}/sections` · `GET /v1/assessments/{id}/feeder-recommendations` · `GET /v1/reference/risks` · `GET /v1/reference/controls` · `POST /v1/use-cases/{id}/assessments` (bootstrap, `gov:system_owner`) · `POST /v1/assessments/{id}/items` · `PATCH /v1/assessments/{id}/items/{item_id}` (If-Match) · `POST /v1/assessments/{id}/items/{item_id}/confirm` (If-Match) · `DELETE /v1/assessments/{id}/items/{item_id}` · `POST /v1/assessments/{id}/items/{item_id}/control-links` · `DELETE .../control-links/{link_id}` · `POST /v1/assessments/{id}/submit` (If-Match) · `POST /v1/use-cases/{id}/lifecycle/re-evaluate`.

**FE-6 live**: `If-Match` sent on PATCH items, confirm items, and submit — inverting DF1-5 dormancy. 412 (StaleLockBanner) ≠ 409 (BadFromStateBanner) in every caller. `staleTime: 0` on `useAssessmentDetail` (FE-7). Feeder-surfaced items (`source_assessment_id !== null`) rendered read-only (INV-16/PAT-7). Four `AssessmentStatus` values all rendered: DRAFT/NEEDS_REFRESH (author-open), IN_REVIEW/APPROVED (locked, write controls `SodAction blockedReason`). V-4 forward-link void closed: `system-detail-client.tsx` now links each use case to `/use-cases/{id}`.

**V-8 outcome (recorded at §0):** required feeders DO gate `structural_assessment_readiness` (`"required_feeder_missing"` park) — A7's provisional defer is a confirmed scope hole for feeder-gated tiers. Noted in DF3-6.

### Assurance / act-SoD surface (`UI-F4-ASSURE`)

`apps/tenant/app/use-cases/[id]` (ALTER) + `apps/tenant/app/review-queue` (NEW). Frontend wire-up; zero new routes, tables, or enums. One additive backend schema delta: `reviews: list[AssessmentReviewRead] = []` added to `AssessmentDetail` (WI-9b — elected at §0 V-2; `reviewer_display_name` from INV-34 membership join; D-25-guarded — no durable name/email stamp on `AssessmentReview` model). `app/schemas/assessment.py` and `app/routers/v1/assessments.py` only; no migration.

**Role branch extension (WI-8):** `resolveRoleBranch` extended from 4-way (`assurance` catch-all) to 5-way — `reviewer | authoriser | auditor` each get their own act surface. Auditor: assembled AIIA + ATO read-only only; no court row; no act controls; issues no `gov:reviewer` call.

**Review queue (WI-1):** `apps/tenant/app/review-queue` — `GET /assessments/review-queue` (`gov:reviewer`) issued only when caller is a reviewer; non-reviewer/admin renders empty-state with no queue call. Each row links to `/use-cases/{use_case_id}` (Topology B, DF4-1).

**AIIA review panel (WI-2):** reviewer branch, AIIA `IN_REVIEW` → `POST /assessments/{id}/review` + `If-Match`; `decision = "approved" | "changes_requested"`; `note` required (server 422) when `changes_requested`. 412 (`StaleLockBanner`) ≠ 409 (`BadFromStateBanner`). Approved → same-txn `advance_use_case`; `changes_requested` → bounce to `DRAFT`. act-SoD (`assert_distinct_workflow_actor`) enforced at server (INV-28).

**Classification sign-off panel (WI-3):** reviewer branch, classification `status = "pending_review"` → `POST /use-cases/{id}/classification/sign-off` (no `If-Match`). 409/403 only; no 412 path. Disambiguation: AIIA `IN_REVIEW` → review panel; classification `PENDING_REVIEW` → sign-off panel; both map to `"reviewer"` court; surface disambiguates by object state, not court vocabulary (DF4-2).

**Authorise panel (WI-4):** authoriser branch, lifecycle state `pending_authorisation` → `POST /use-cases/{id}/authorise` (body: `{residual_risk_statement}`; no `If-Match`). 409/403 only. `residual_risk_statement` required client-side. act-SoD at server (INV-28; authoriser ∉ {reviewer, submitter}).

**ATO terminal (WI-5):** any gov role, lifecycle state `authorised` → `GET /use-cases/{id}/authorisation` (`staleTime: 0`, INV-32). 404 → renders nothing. Drift caveat when `live_state ≠ "authorised"` (DF4-4 / INV-44 precedent). `authorised_by_name` from INV-34 join (already on the response shape at `DeploymentAuthorisationRead`).

**Reopen control (WI-6):** system_owner branch, AIIA `status = "approved"` → `POST /assessments/{id}/reopen` + `If-Match`; `APPROVED → NEEDS_REFRESH`; authoring fields unlock on refetch. 412/409 distinct. Completes the rework loop (DF4-5).

**Review history (WI-7):** sourced from `AssessmentDetail.reviews` (WI-9b). Visible to system_owner, reviewer, authoriser. Each row: `reviewer_display_name` (INV-34 join), `decision`, `submission_round`, `created_at`, `note`.

**§0 V-1 resolution:** `list_review_queue` pre-filters `submitted_by_user_id != ctx.user_id` at the query level. WI-9a NOT elected — queue pre-filter covers the common SoD case; across-reassignment edge degrades to act-time 403 (DF4-3).

**If-Match callers in this sprint:** `POST /assessments/{id}/review` + `POST /assessments/{id}/reopen`. No `If-Match` on sign-off or authorise (no 412 path on those routes). `FE-6` live callers: F3's submit/amend/confirm + F4's review/reopen.

Consumed routes (no route delta): `GET /v1/me` · `GET /v1/use-cases/{id}` · `GET /v1/use-cases/{id}/assessments` · `GET /v1/use-cases/{id}/lifecycle` · `GET /v1/systems/{id}/rollup` · `GET /v1/assessments/{id}` · `GET /v1/assessments/{id}/sections` · `GET /v1/assessments/{id}/feeder-recommendations` · `GET /assessments/review-queue` · `POST /assessments/{id}/review` (If-Match) · `POST /assessments/{id}/reopen` (If-Match) · `POST /use-cases/{id}/classification/sign-off` · `POST /use-cases/{id}/authorise` · `GET /use-cases/{id}/authorisation`.

### Evidence repository surface (`UI-F5-EVIDENCE`)

`apps/tenant/app/evidence` (NEW) + `apps/tenant/app/use-cases/[id]` (ALTER). Wires the already-built evidence backend (Sprint 4) into the tenant UI, closing `DF3-1`. One additive backend schema delta: `evidence_links: list[ItemEvidenceRead]` added to `AssessmentItemRead` (batch-loaded in `assemble_aiia_items` via `_batch_evidence_links` — one JOIN query, no N+1). No new routes, tables, or enums.

**Role branch:** `GET /v1/me` pre-fetched; admin (zero gov roles) → empty-state, no evidence request issued (DF5-7); all five governance roles → evidence list + download; `system_owner`/`contributor` → additionally upload + delete. Download is on-intent: `GET /evidence/{id}` (presigned URL + audit `evidence.access`) fired only on explicit user click, never pre-fetched per row (DF5-3).

**Evidence repository home** (`apps/tenant/app/evidence/page.tsx`): `EvidenceTable` (all gov roles), `EvidenceUploadControl` (write roles), on-intent download via `useEvidenceDetail(id, enabled)` + `window.location.href` navigation. Delete disabled-with-reason when `link_count > 0` (INV-19, DF5-6).

**Per-item manifest** (`apps/tenant/app/use-cases/[id]/_regions/evidence-manifest.tsx`): reads `item.evidence_links` (the batch-loaded manifest — no download_url, DF5-8). Link is disposition-gated: `AI_SUGGESTED` items show the button disabled-with-reason (INV-20, DF5-5). Unlink targets `evidence_id`, not a link-row id (DF5-9). Feeder-surfaced items: `canWrite=false` → read-only. Invalidates AIIA-detail only after link/unlink; lifecycle key NOT invalidated (DF5-10, D-29).

**FE-12 (new):** binary file uploads must route through a dedicated BFF handler (`apps/tenant/app/api/evidence-upload/route.ts`) that reads the body as `arrayBuffer()`, never `request.text()`. The generic proxy's `request.text()` UTF-8-decodes binary bytes, corrupting the file and producing a mismatched SHA-256. The dedicated handler preserves the `Content-Type` header including the `boundary=` parameter.

**Backend shape:** `_batch_evidence_links(db, item_ids)` JOINs `assessment_item_evidence → evidence` to materialise `ItemEvidenceRead` objects (carrying `title`/`sha256`/`content_type`/`size_bytes` from the `evidence` table, not `assessment_item_evidence`). A `@field_validator("evidence_links", mode="before")` guard in `AssessmentItemRead` short-circuits Pydantic's ORM `from_attributes` path (which would read the incomplete ORM relationship, lacking `evidence` columns) and returns `[]`; `assemble_aiia_items` then overwrites the field with the batch-loaded result.

Consumed routes (no route delta): `GET /v1/me` · `GET /v1/evidence?limit=50` · `GET /v1/evidence/{id}` · `POST /v1/evidence` (via dedicated BFF handler, FE-12) · `DELETE /v1/evidence/{id}` · `POST /v1/assessments/{id}/items/{item_id}/evidence-links` · `DELETE /v1/assessments/{id}/items/{item_id}/evidence-links/{evidence_id}` · `GET /v1/assessments/{id}` (extended — now includes `items[].evidence_links`).

### Audit / coverage capstone (`UI-F6-AUDITPACK`)

`apps/tenant/app/audit` (NEW) + `apps/tenant/app/systems/[id]` (ALTER) + `apps/tenant/app/use-cases/[id]` (ALTER) + `apps/tenant/app/dashboard` (ALTER, link only). Pure frontend wire-up over the already-built Sprint 7a/7b coverage and export backend. **Zero backend/schema delta** — every route was `gov:ALL` at the sprint's §0 pre-flight. Closes EXP-1's render half (interim: in-DOM sectioned view + browser print; templated PDF remains deferred as EXP-3).

**`/audit` programme home (`apps/tenant/app/audit`):** `GET /v1/me` first (DF2-5 role branch): admin (zero governance roles) → empty-state, no coverage/export call issued. Gov-role callers: `useTenantCoverage` eager (`staleTime: 0`, FE-7/NB5); `include_unapproved` toggle default off — when on, wraps the not-yet-audit-grade matrix in `AuditGradeDivider` (INV-52/DF6-8); framework picker + "Generate framework audit pack" button → one deliberate `useFrameworkExport` fetch (INV-53) → `AuditPackView` rendered inline; pack index links to per-system/per-use-case surfaces.

**System panels (`systems/[id]` ALTER):** system-coverage panel (`useSystemCoverage`, eager, `staleTime: 0`, `CoverageMatrix` with `NotAnObligationSetBanner` when `not_an_obligation_set`); system-export action (`useSystemExport`, deliberate-only — `enabled: false`, `staleTime: Infinity`, `refetchOnWindowFocus: false`). Both gated to governance-role callers (admin → omitted, no call issued).

**Use-case panels (`use-cases/[id]` ALTER):** three sub-panels via `apps/tenant/app/use-cases/[id]/_regions/audit-panels.tsx`:
1. **Coverage** — `useUseCaseCoverage` (`GET /assessments/{id}/coverage`); renders only when the governing AIIA is `APPROVED` (INV-38/DF3-2); else "coverage available after approval" empty-state (no fetch issued when not approved).
2. **Use-case export** — `useUseCaseExport`, deliberate-only; "Generate use-case audit pack" button → `AuditPackView`.
3. **ATO document** — `useAtoDocument`, deliberate-only; defaults to latest round; honours `?round=N` deep-link (DF6-10); no round-enumeration call. 404 → "never authorised" empty-state. Renders `AtoDocumentView` with always-shown drift caveat (DF6-5/INV-44).

**Dashboard ALTER (link only):** PortfolioHub `postureSection` gains `<Link href="/audit">View control coverage and audit packs →</Link>`; no coverage truth rendered (DF6-9).

**`@irontrust/ui` additions:** `CoverageMatrix` (verdict chips SATISFIED/PARTIAL/OPEN/UNADDRESSED; `downgraded_unsubstantiated` distinct from `partial`, never merged — INV-51; `verdict` treated as plain `str`, no enum bind); `NotAnObligationSetBanner` (prominent caveat + gaps list; no compliance-% headline — INV-52); `AuditGradeDivider` (hard visual boundary, `role="region"`, required between interactive-posture and audit-grade views — INV-51/52); `AuditPackView` (sectioned for `UseCaseExportRead`/`SystemExportRead`/`FrameworkExportRead`; trail actors: `name ?? email ?? user_id ?? "(system)"` per §4.5; footer `content_hash` + `generated_at`); `EvidenceManifestTable` (download via callback → `GET /v1/evidence/{id}`; no URL in props/DOM — INV-40); `AtoDocumentView` (drift caveat always rendered first — DF6-5; `authorised_by_name`/`_email` from durable stamp, no hedge — §4.4).

**`@irontrust/api-client` additions:** `CoverageMatrixRead` + related coverage types (`packages/api-client/src/contracts/coverage.ts`); `AtoDocumentRead`, `AssessmentExportRead`, `UseCaseExportRead`, `SystemExportRead`, `FrameworkExportRead`, `ActorRef`, `EvidenceManifestEntryRead`, `ClassificationHistoryEntryRead` (`packages/api-client/src/contracts/export.ts`).

**`apps/tenant/lib/audit` hooks:** `useTenantCoverage`/`useSystemCoverage`/`useUseCaseCoverage` (eager, `staleTime: 0`); `useSystemExport`/`useUseCaseExport`/`useFrameworkExport`/`useAtoDocument` (deliberate-only, `enabled: boolean`, `staleTime: Infinity`, `refetchOnWindowFocus: false`, `refetchOnMount: false` — INV-53).

**Two-event audit model (NB2):** `export.generated` per deliberate pack/ATO-document generation (INV-42); `evidence.access` per manifest download on-intent (INV-22, same pattern as F5/DF5-3). Coverage reads are audit-free (INV-25).

Consumed routes (no route delta): `GET /v1/me` · `GET /v1/coverage` · `GET /v1/systems/{id}/coverage` · `GET /v1/assessments/{id}/coverage` · `GET /v1/systems/{id}/export` · `GET /v1/use-cases/{id}/export` · `GET /v1/use-cases/{id}/authorisation/document` · `GET /v1/export?framework=` · `GET /v1/evidence/{id}`.

### Operator RBAC management console (`UI-F8-OPERATOR-RBAC`)

`apps/operator/app/(console)/operators` (NEW) + `apps/operator/app/(console)/layout.tsx` (ALTER — RBAC Management nav entry lit). Brings operator creation into `INV-49` compliance. `INV-49`/`D-36` remain live (the convention continues to judge all future operator surfaces); only the creation-via-UI gap is resolved.

**Backend — seed (migration `c8f3a2e91bd5`, 0 DDL):** new permission `operator:create` + new role `platform_admin` (full platform administration: both `tenant:provision` and `operator:create`) seeded as migration-embedded deployment data, following `cef7211ddfe4` precedent (`DF8-1`). `provisioner` role unchanged (`{tenant:provision}` only).

**Backend — routes (`app/routers/platform/operators.py`):**
- `POST /platform/operators` — wraps `provision_operator(actor=caller, source="http")`; gate `operator:create`; 409 duplicate email; 422 unknown `role_key`; 500 Cognito failure; `PlatformAuditEvent` `CREATE_OPERATOR` attributes calling operator.
- `GET /platform/operators` — operator list with roles; gate `operator:create` (`DF8-2` shared gate).
- `GET /platform/roles` — role list for form select; gate `operator:create` (`DF8-2`).

`provision_operator` corrected: `granted_by_id` now set to `actor.id` when actor is not None (was hardcoded `None`; genesis-only `NULL` is preserved for `actor=None` path).

**Frontend — operators surface:** Root branch gates on `operator:create ∈ permissions` (from `GET /platform/me`):
- **With permission:** issues `GET /platform/operators` + `GET /platform/roles` (both `enabled: true`), renders operator list + create form. Form captures `email`, `display_name`, `role_key` (select, default `provisioner`). 201 → "Invite sent" + invalidates `["platform-operators"]`. 409 → email field error. 422 → role-select field error. 403 → refetches `["platform-me"]`.
- **Without permission:** renders nothing; **zero** calls to `GET /platform/operators` or `GET /platform/roles` (`DF7-1` pattern).

**Frontend — nav:** "RBAC Management" entry moved from visible-disabled UNBUILT array to `RequirePermission` gate on `operator:create` (`FE-13`), linking to `/operators` — absent (not greyed) when permission not held (`DF7-2`).

Tested: `tests/platform/test_operators_create.py` (5 assertions: 201 + invite; 409; 422; 403; audit attribution); `tests/platform/test_operators_list.py` (4 assertions: list 200 + role; list 403; roles 200; roles 403); `apps/operator/app/(console)/operators/__tests__/operators.test.tsx` (5 assertions: zero-call guard; list+form; 201+invalidate; 409; 422). `test_audit.py::test_cli_create_operator_writes_audit` corrected to seed actor's operator row (FK requirement of corrected `granted_by_id`).

**Deferred (`DF8-3`):** operator status toggle (ACTIVE↔DISABLED); role re-grant / revoke.

---

### Operator provisioning console (`UI-F7-PROVISION`)

`apps/operator/app/(console)/provisioning` (NEW) + `apps/operator/app/(console)/layout.tsx` (NEW nav shell) + `GET /platform/me` backend (NEW, durable D-39). Brings provisioning into `INV-49` compliance — the live gap (provisioning operable only via CLI/raw HTTP) is removed. `INV-49`/`D-36` remain live (the convention continues to judge all future operator surfaces); only the provisioning gap is resolved.

**Backend:** `GET /platform/me` (`app/routers/platform/me.py`), gated `get_current_operator` (bare, no permission assertion — any valid active operator gets 200). Response `{id, email, display_name, permissions}` (drops `cognito_sub`). `GET /platform/whoami` struck; 404 on access. Tested in `tests/platform/test_platform_me.py` (7 assertions: no-token 401; unknown/disabled operator 403; permitted/unpermitted operator each 200; whoami gone 404; permissions from DB chain not claims).

**Frontend — nav shell:** `apps/operator/app/(console)/layout.tsx` reads `GET /platform/me` once at shell root (query key `["platform-me"]`). Provisioning nav entry present iff `'tenant:provision' ∈ permissions` (`FE-13`, `RequirePermission` primitive at `apps/operator/components/require-permission.tsx`); absent otherwise. Three unbuilt surfaces (RBAC Management, Catalogue Curation, Curation Inbox) render visible-disabled "not yet available" to all operators — roadmap signalling only, distinct from permission-absent (N2/`DF7-2`).

**Frontend — provisioning surface:** Root branch gates on `'tenant:provision' ∈ permissions`:
- **With permission:** issues `GET /platform/tenants` (query key `["platform-tenants"]`), renders tenant list + provision form. List columns: `id`, `name`, `slug`, `created_at` (from `TenantListItem`). Form captures `ProvisionRequest` (`org_name`, `slug`, `owner_email`, `owner_name`) with client-side validation mirroring server constraints. 201 → renders `{tenant_id, owner_id}` + invalidates `["platform-tenants"]`. 409 → flags `slug` field on slug collision, `owner_email` field on email collision (two independent collision checks). 403 → refetches `GET /platform/me`, re-branches.
- **Without permission:** empty state; **no** `GET /platform/tenants` issued; no form. This is the B1 regression guard (`DF7-1`).

**FE-13 primitive** (`RequirePermission`): renders children only when the named permission is held; absent (not disabled) when not held. Operator-plane analogue of `FE-8` (`SodAction`); grounded on `INV-8`/`D-24`. Presentational only; backend `require_permission` remains authz authority.

Tested: `tests/platform/test_platform_me.py` (backend); `apps/operator/app/(console)/provisioning/__tests__/page.test.tsx` (6 frontend assertions covering B1 guard, list+form render, 201 path, 409 slug/email conflicts, 403 refetch).

---

### Portfolio landing & system drill-in (`UI-F2-PORTFOLIO`)
`apps/tenant/app/dashboard` (the F0 authenticated-landing route, promoted from the W7a/b smoke surface to the real portfolio home) plus `apps/tenant/app/systems/[id]` (drill-in) — the second tenant feature surface, pure wire-up over `GET /v1/portfolio`, `GET /v1/systems`, `GET /v1/systems/{id}/rollup`, `GET /v1/use-cases/{id}/lifecycle`, `GET /v1/me`; read-only (`re-evaluate` deferred, `A1`); zero backend/schema delta. `GET /v1/me` is fetched first and branches proactively (`DF2-5`): an admin-only caller (zero governance roles) renders an admin/empty state and the `gov:ALL`-gated `GET /portfolio` is never issued. Otherwise the portfolio hub (`PortfolioHub`) renders a "your court" section and a "portfolio posture" section for every governance-role caller — 1st-line roles (`system_owner`/`contributor`) lead with your-court, 2nd/3rd-line lead with posture — plus the per-system use-case list; `GET /v1/systems` entries absent from the portfolio result (no use case yet) render as a separate, non-interactive "register a use case" nudge card (`A2`), excluded from court computation. A `system_owner`-gated "Register a system →" link was added to the Systems section of the portfolio hub (`apps/tenant/app/dashboard/page.tsx`) during genesis testing (2026-06-24) — absent when caller holds no `system_owner` role.

Whose-court derivation (`apps/tenant/lib/portfolio/court.ts`, `FE-11`/`D-38`) corrects the design doc's B1 hypothesis: live verification of `app/services/lifecycle_gates.py`'s `classification_readiness` showed the gate already disambiguates a `REQUIRES_CONTEXT` use case correctly (`"reviewer"` while the classification snapshot is `PENDING_REVIEW`, `"user"` once it isn't) — there is no `requires_context` field on `SystemRollupRead`/`UseCaseRollupEntry` and no client pre-branch is applied; court is read directly from `blocking.responsible_party`, always. `responsible_party` (`"user"|"reviewer"|"authoriser"|"vendor"|"system"`) is mapped to governance roles (`"user"`→`system_owner`, `"reviewer"`/`"authoriser"` 1:1, `"vendor"`/`"system"`→ no role, never anyone's court); `contributor` is never emitted by any gate, so a `contributor` court row never appears. The promoted `@irontrust/ui` `WhoseCourtIndicator` (`partyLabel`, `isYourCourt`) is the presentational highlight (`FE-8`) — backend remains the authz authority.

The system drill-in renders each use case's blocking reason/court as informational text only, with no forward-link control: `apps/tenant/app/systems/new`'s wizard step is plain in-memory `useReducer` state, never synced to the URL, so there is no per-use-case resumable destination to link to (a gap, not silently dropped — see the deferred register below).

---

## 2. Audit actions in use

**Tenant plane** (`AuditEvent`, append-only, RLS, immutability trigger — INV-5):
`system.created`/`updated` · `classification.created`/`overridden`/`signed_off` · `governance_role.granted`/`revoked` · `member.created` · `assessment.created`/`deleted`/`feeder_created` · `assessment_item.created`/`amended`/`confirmed`/`deleted`/`treatment_set` · `control_link.created`/`deleted` · `evidence.created`/`deleted`/`access`/`linked`/`unlinked` · `lifecycle.advanced`/`held`/`halted_prohibited`/`authorised` · `vendor_approval.set`/`updated` · `product_approval.set`/`updated` · `assessment.submitted`/`review_recorded`/`reopened`/`needs_refresh` (6a) · `authorisation.granted` (6b) · `export.generated` (7b).

`action` is `varchar(120)` — a new action string needs no migration. `AuditEvent` stores `actor_user_id` (FK only); durable name/email is the deferred cross-cutting gap (D-25), with the ATO the lone exception. 7a coverage emits no audit (pure read). **Platform plane:** `PlatformAuditEvent` (operator-attributed). Actions: `PROVISION_TENANT` (source `http`/`cli`); `CREATE_OPERATOR` (source `http` from `POST /platform/operators` — `UI-F8`; source `cli` from `create-operator` CLI).

---

## 3. Deferred / not yet implemented

| Area | What exists | What's missing |
|---|---|---|
| **Applicability layer** (OPEN-3) | Coverage view built (7a); interim flagged-unaddressed denominator | The applicable/excluded partition — EU-derived per-use-case obligation set + ISO tenant SoA (CLS-6) |
| **Export PDF render** | EXP-1 JSON built (7b) | PDF rendering (EXP-1's render half — frontend/later) |
| **Auditor-scoped access (EXP-2)** | Any-governance-role read today | Thin membership addition for read-only auditor scoping |
| **Branded export (EXP-3)** | — | Templated/branded output |
| **Persisted / async export** | Live computation + `content_hash` (D-30) | Frozen artifacts + history; async/streamed export for outsized packs |
| **AIIA versioning / refresh** (OPEN-2) | `version`/`is_current`, `tier_snapshot`/`classification_version` fields | The re-run cycle: detect material change → re-snapshot → flag `needs_refresh` |
| **Worked-state void** (OPEN-1) | Review/sign-off (6a); pristine-delete is status-and-history-aware (INV-36) | A void/withdraw path — pristine hard-delete is still the only removal |
| **`deployed`/`retired` transitions** | Enum members exist | No transition; `authorised` is the lifecycle ceiling by design |
| **Evidence assignment / freshness (EVD-3/4)** | Repository + linking; `expires_at` column present, unused | Due-date assignment, scheduler, expiry/freshness notifications |
| **Evidence AV/malware scanning** | Proxied upload path (the marked seam) | No interception |
| **Evidence supersession / soft-void** | `s3_version_id` per upload | Version-replace UX, soft-void — pristine hard-delete only |
| **Evidence Object Lock / per-tenant CMK** | Bucket Object-Lock capability (Terraform) | Retention/legal-hold application; one shared CMK + single region is the recorded MVP tradeoff |
| **`AuditEvent` actor durability** (D-25) | ATO text-stamps name/email (the exception) | Durable name/email on `AuditEvent` + `AssessmentReview`/`submitted_by`/`approved_by` — one cross-cutting fix, not piecemeal |
| **Member deactivation / resend invite** | — | Not designed |
| **AI-assisted drafting** | `ai_suggested_text` field | No generation flows; all `AI_SUGGESTED` proposals are deterministic catalogue/library lookups |
| **Per-object governance roles** (D-22) | Nullable `scope_id` seam described | Not built; do not add yet |
| **Multi-component MODEL_RISK** | `uq_feeder_type_per_aiia` scoped to allow it | 0..1 per AIIA today, like FRIA/DPIA |
| **Cross-feeder risk dedup** | — | A risk proposed by AIIA and a feeder surfaces twice, untouched; no merge planned for MVP |
| **`re-evaluate` on the portfolio hub** | Shipped in `UI-F3-ASSESS` (`apps/tenant/app/use-cases/[id]`, `system_owner`-only) | Intentionally absent from the portfolio hub (hub is read-only, `A1`) |
| **Per-use-case resumable URL** | `apps/tenant/app/use-cases/[id]` shipped in `UI-F3-ASSESS`; `system-detail-client.tsx` now links each use case forward (`V-4` void closed) | F1's wizard step-progress is still in-memory `useReducer` state — the intake wizard itself has no resumable URL |
| **Coverage panel (A3)** | Coverage backend built (7a) | Deferred — headline counts only meaningful on an `APPROVED` governing AIIA (INV-38); DRAFT reads mislead |
| **Feeder authoring (A7, provisional)** | Feeder recommendations read-only panel; no feeder create/author UI | PROVISIONAL: deferred (DF3-6 — confirmed scope hole for feeder-gated tiers) |
| **`AuditEvent` actor durability** (D-25) | ATO text-stamps name/email (exception); `AssessmentReviewRead.reviewer_display_name` from INV-34 join at read time (WI-9b) | One deferred cross-cutting fix for durable name/email on `AuditEvent` + `AssessmentReview`/`submitted_by`/`approved_by` |