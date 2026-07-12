# API-ROUTES.md — IronTrust AI Governance Platform · FastAPI Route Map

**Location:** `docs/API-ROUTES.md` — single source, mirrored to project knowledge. **Updated each sprint that adds, removes, or re-gates a route** — the route-surface counterpart to `DATA-MODEL.md` (schema) and `FRONTEND.md` (client↔API conventions).
**Purpose:** the canonical inventory of every FastAPI route — method, path, auth gate, request/response schema, file:line — so a sprint can verify the contract it's about to consume *from this file*, not by re-grepping `app/routers/` from scratch. It also names routes that sound plausible but **do not exist**, so a design doesn't quietly assume one.
**Scope (deliberate):** routes and gates, not field-by-field schema detail — schemas are named and pointed at `app/schemas/*.py`; full field shape lives there (D-21: the code is authoritative) or in `DATA-MODEL.md` for the underlying tables. Frontend-side mirrored types live in `packages/api-client/src/contracts/`.

**Authoritative inventory:** every router registered in `app/main.py`, read line-by-line against repo HEAD through `UI-F4-ASSURE`. **Still verify before relying on it** (`D-21`) — this file can drift the moment a route changes; if it disagrees with `app/routers/`, the code wins and this file is stale, not the other way round.

---

## 1. Gate shorthand

| Shorthand | Dependency | Meaning |
|---|---|---|
| `anon` | none (or plain `get_db`) | No auth at all — global reference reads only. |
| `member` | `get_tenant_context` / `get_tenant_db` | Any authenticated tenant member (administrative role `admin` or `member`); no governance-role check. |
| `admin` | `require_role("admin")` | Tenant admin only (administrative axis). |
| `gov:ALL` | `require_governance_role("system_owner","contributor","reviewer","authoriser","auditor")` | Any of the five governance roles — the standard read gate for governed resources. |
| `gov:write` | `require_governance_role("system_owner","contributor")` | First-line write gate (capture/provision acts). |
| `gov:<role>` | `require_governance_role("<role>")` | A single named governance role. |
| `operator:<perm>` | `require_permission("<perm>")` (platform plane) | Operator-console auth — a platform permission, never a tenant governance role. |
| `op-auth` | `get_current_operator` (platform plane) | Authenticated operator only — identity verified from DB, no permission assertion. Any valid active operator gets 200 regardless of permissions held. |

`member`/`admin`/`gov:*` all run on the RLS-scoped session from `get_tenant_db` (tenant isolation is structural, not a per-route concern to re-verify — `INV-4`). Routes with no DB session at all (the export router) gate inside their own self-owned session — noted per-route below.

**If-Match column:** `—` means the route never accepts it; a route that does is named explicitly (the F1 footgun: assuming a route takes `If-Match` when it doesn't, or vice versa — `FE-6`/`PAT-6`).

---

## 2. Tenant plane — `/v1`

### Reference data — `app/routers/v1/reference.py`

| Method · Path | Gate | Request | Response | If-Match | Notes |
|---|---|---|---|---|---|
| `GET /reference/product-categories[?parent_id]` | `anon` | — | `ProductCategoryRead[]` | — | Wizard drill-down; no `parent_id` → top-level. |
| `GET /reference/product-categories/{category_id}/vendors` | `anon` | — | `VendorRead[]` | — | Distinct vendors with ≥1 product in the category. |
| `GET /reference/product-categories/{category_id}/products[?vendor_id]` | `anon` | — | `ProductRead[]` | — | Optional vendor narrow. |
| `GET /reference/eu-ai-act/subcategories` | `anon` | — | `EUAIActSubcategoryRead[]` | — | Each row carries its `tier`. |
| `GET /reference/products/{product_id}` | `anon` | — | `ProductDetailOut` | — | Vendor + category tags + EU subcategories. `ProductDetailOut.logo_url: string \| null` and `ProductDetailOut.vendor.logo_url: string \| null` included (additive, UI-C2). |
| `GET /reference/operator-roles` | `member` | — | `VocabItemOut[]` | — | `UI-F1-INTAKE` WI-0; `active=true`, `sort_order`. |
| `GET /reference/hosting-models` | `member` | — | `VocabItemOut[]` | — | WI-0. |
| `GET /reference/usage-contexts` | `member` | — | `VocabItemOut[]` | — | WI-0. |
| `GET /reference/human-oversight-types` | `member` | — | `VocabItemOut[]` | — | WI-0. |
| `GET /reference/data-categories` | `member` | — | `DataCategoryOut[]` | — | WI-0; carries `is_special_category`. |
| `GET /reference/affected-parties` | `member` | — | `AffectedPartyOut[]` | — | WI-0; carries `is_vulnerable_group`. |
| `GET /reference/risks[?layer]` | `member` | — | `RiskRead[]` | — | AIIA item authoring. |
| `GET /reference/controls[?framework]` | `member` | — | `ControlRead[]` | — | AIIA item authoring; carries `frameworks[]` cross-map. |

The product/category/vendor/subcategory reads are intentionally `anon` — they back the pre-auth, sales-led catalogue drill-down (`UX.md` §4). The six `member`-gated vocab/risk/control reads are not — they're consumed mid-flow, after the caller is already a signed-in tenant member.

### Registrations — `app/routers/v1/registrations.py` (DM-S2)

| Method · Path | Gate | Request | Response | If-Match | Notes |
|---|---|---|---|---|---|
| `POST /registrations` | `gov:system_owner` | `RegistrationCreate` | `RegistrationRead` (201) | — | Atomic: system + first use case + classification snapshot in one transaction. `RegistrationCreate` system-stable fields: `name`, `is_custom`, `catalogue_product_id`, `operator_role_id`, `hosting_model_id`, `lifecycle_stage`, `owner_user_id`, `purpose`. Use-case fields: `title`, `intended_use_category_id` (FK `product_category`, nullable — replaces `use_case_purpose` dropped DM-S4b), `context_blob`, `usage_context_id`, `human_oversight_type_id`, `data_category_ids`, `affected_party_ids`. **DM-S3:** optional `draft_id: uuid | null` — when present, the matching `draft_registration` row is deleted atomically (SV-3/D-66). **DM-S4b:** classification branches on `ClassificationDisposition` (D-71, D-73, INV-82): `REQUIRES_CONTEXT` → gate-2 seam snapshot (`off_label=True` when product present but no declared category — D-72); `AUTHORITATIVE` → `APPROVED` + stamps `eu_tier`; `DOWN_SELECTION` → `PENDING_REVIEW`, `eu_tier` NOT stamped. **CAT-4 (INV-83, D-74, D-75):** optional `confirmed_fields: list[str]` — signals which seeded fields the user confirmed/amended. Entries: bare API snake_case key for intake fields (e.g. `"operator_role_id"`), `"fact:<key>"` for confirmed catalogue facts, `"fact_amended:<key>"` for amended catalogue facts. For catalogue-linked non-custom systems: derived defaults (`operator_role_id`, `lifecycle_stage`) that still hold their seed value MUST appear in `confirmed_fields`; omitting them raises HTTP 422 `{"undispositioned_fields": [...]}`. Writes `prefill_disposition` rows + `system.field_confirmed` / `system.field_amended` audit events inside the same transaction. Response `RegistrationRead = { system: SystemDetail, use_case: UseCaseRead, classification: ClassificationRead }`. `SystemDetail` carries `field_provenance: dict[str, str] | null` (projection from `prefill_disposition` rows). INV-78: the only route that constructs a System. D-65. |

### Draft registrations — `app/routers/v1/draft_registrations.py` (DM-S3)

One active draft per user per tenant (INV-79). RLS scopes to tenant; application layer additionally filters `owner_user_id == ctx.user_id` (DF-D3-4). `draft_blob` stores pre-boundary wizard fields + clamped step cursor (DF-D3-1..3). No `If-Match` — last-write-wins (DF-D3-6).

| Method · Path | Gate | Request | Response | If-Match | Notes |
|---|---|---|---|---|---|
| `POST /draft-registrations` | `gov:system_owner` | — | `DraftRegistrationRead` (200) | — | SELECT-first get-or-create (DF-D3-5). Returns existing row if one already exists; creates with empty `draft_blob` otherwise. Always 200. |
| `GET /draft-registrations/active` | `gov:system_owner` | — | `DraftRegistrationRead` (200) or 204 | — | Returns caller's active draft or 204 (no body) if none exists. |
| `PATCH /draft-registrations/{id}` | `gov:system_owner` | `DraftRegistrationPatch` | `DraftRegistrationRead` (200) | — | Replaces `draft_blob` wholesale (last-write-wins). 404 if id not found or belongs to a different user. |
| `DELETE /draft-registrations/{id}` | `gov:system_owner` | — | 204 | — | Owner-filtered discard. 404 if not found or different owner. Called via `onStartOver` in `ResumePrompt` (FE-28). |

### Catalogue prefill — `app/routers/v1/catalogue.py` (DM-S2)

| Method · Path | Gate | Request | Response | If-Match | Notes |
|---|---|---|---|---|---|
| `GET /catalogue/products/{product_id}/prefill` | `member` | — | `PrefillResponse` | — | By-product prefill before system exists (DF-D2-2). `facts: []` when product has no facts. Shared resolver with `GET /systems/{id}/prefill`. No audit. |
| `GET /catalogue/products/{product_id}/categories` | `member` | — | `ProductCategoryRead[]` | — | **DM-S4b.** Returns the `ProductCategoryMembership` rows for this product joined to `ProductCategory`; empty list if none. Used by the wizard use-case step to build the intended-use category selector (FE-31, D-71). No audit. |

### Systems — `app/routers/v1/systems.py`

| Method · Path | Gate | Request | Response | If-Match | Notes |
|---|---|---|---|---|---|
| ~~`POST /systems`~~ | — | — | — | — | **Removed in DM-S2 (INV-78).** System construction is now only via `POST /registrations`. Returns 404/405. |
| `GET /systems` | `member` | — | `SystemRead[]` | — | RLS-scoped list. |
| `GET /systems/{system_id}` | `member` | — | `SystemDetail` | — | |
| `PATCH /systems/{system_id}` | `gov:system_owner` | `SystemUpdate` | `SystemDetail` | — | Relinking `catalogue_product_id` with use cases present → 409. **CAT-4 (D-75):** when a provenance-bearing field (`operator_role_id`, `hosting_model_id`, `lifecycle_stage`, `purpose`, `name`) changes value, upserts the corresponding `prefill_disposition` row to `USER_AMENDED` and stages a `system.field_amended` audit event inside the same transaction. |
| `GET /systems/{system_id}/prefill` | `member` | — | `PrefillResponse` | — | `200` with `facts: []` when no product (incl. `is_custom`) — never `404`. Delegates to `get_prefill_by_product` shared resolver (DM-S2). |

### Use cases & classification — gate 1 (the bridge) — `app/routers/v1/use_cases.py`

| Method · Path | Gate | Request | Response | If-Match | Notes |
|---|---|---|---|---|---|
| `POST /use-cases` | `gov:system_owner` | `UseCaseCreate` | `UseCaseWithClassification` (201) | — | Auto-derives + snapshots the classification in the same call (the bridge: `system → product → product_category → eu_ai_act_subcategory`). **DM-S1:** `UseCaseCreate` gains `usage_context_id`, `human_oversight_type_id`, `data_category_ids`, `affected_party_ids`; `UseCaseRead` returns resolved `usage_context`, `human_oversight_type`, `data_categories`, `affected_parties`. |
| `GET /use-cases` | `member` | — | `UseCaseRead[]` | — | |
| `GET /use-cases/{use_case_id}` | `member` | — | `UseCaseWithClassification` | — | 404 if no current classification snapshot exists. `UseCaseRead` includes the four resolved context fields (DM-S1). |
| `POST /use-cases/{use_case_id}/classify/override` | `gov:system_owner` | `OverrideRequest` | `UseCaseWithClassification` | — | 422 on unknown `subcategory_code` or `tier` ≠ `subcategory.tier`. New current snapshot; prior preserved `is_current=False`. |

`ClassificationRead` (the gate-1 projection, embedded in both responses above) carries `requires_context` and `status` (DM-S4b, WI-6b). `status` is needed by the wizard to branch `DOWN_SELECTION` → whose-court without a separate lifecycle call (D-73). **Note:** `ClassificationRead` does NOT include `created_at`/`updated_at`; pass a `ClassificationStatusRead` to components that need those fields.

### Classification context gate — gate 2 — `app/routers/v1/classification_context.py`

All paths nest under `/use-cases/{use_case_id}/classification/...`.

| Method · Path | Gate | Request | Response | If-Match | Notes |
|---|---|---|---|---|---|
| `GET .../classification/context` | `gov:ALL` | — | `ClassificationContextRead` | — | Pure read; residual = full tree when no answers yet. |
| `POST .../classification/context/preview` | `gov:ALL` | `PreviewRequest` | `ContextOutcomeRead` | — | Pure resolve, no write — `kind` is `UNRESOLVED`\|`RESOLVED`\|`PROHIBITED_HALT`. |
| `POST .../classification/context` | `gov:write` | `ComputeRequest` | `ComputeResultRead` (201) | — | Writes a `PENDING_REVIEW` snapshot; does **not** stamp `eu_tier`. `override_tier` set → an inline 403 unless the caller separately holds `system_owner` (contributor can compute, never override — checked ad hoc in this handler, not via the role dependency). `UNRESOLVED` outcome → `200`-shaped result with no snapshot written. |
| `POST .../classification/sign-off` | `gov:reviewer` | — | `SignOffRead` | — | `PENDING_REVIEW → APPROVED`; the only place that stamps `use_case.eu_tier` on the context path (`D-9`). **Not consumed by `UI-F1-INTAKE`** — out of that sprint's scope. |

`ClassificationStatusRead` (the gate-2 projection, in `ClassificationContextRead`/`ComputeResultRead`) carries `status`, never `requires_context`.

### Lifecycle, approvals, rollup — `app/routers/v1/lifecycle.py`

Three routers share this file: `router` (`/use-cases/...`), `approvals_router` (no shared prefix), `rollup_router` (`/systems/...`).

| Method · Path | Gate | Request | Response | If-Match | Notes |
|---|---|---|---|---|---|
| `GET /use-cases/{use_case_id}/lifecycle` | `gov:ALL` | — | `UseCaseLifecycleRead` | — | Recomputes the full gate vector live, never persists. `blocking` = first non-`advance` `GateResultRead`, or `null`. |
| `POST /use-cases/{use_case_id}/lifecycle/re-evaluate` | `gov:system_owner` | — | `UseCaseLifecycleRead` | — | The manual lever (design doc §1.1) — recomputes and moves to the correct resting gate; not an "advance" call, a re-settle call. |
| `POST /use-cases/{use_case_id}/authorise` | `gov:authoriser` | `AuthoriseRequest` | `DeploymentAuthorisationRead` (200) | — | The only route that enters `authorised` (`D-12`). Act-SoD checked inside the service. |
| `GET /use-cases/{use_case_id}/authorisation` | `gov:ALL` | — | `DeploymentAuthorisationRead` | — | Most recent ATO + computed `live_state`; 404 if never authorised. |
| `PUT /vendors/{vendor_id}/approval` | `gov:authoriser` | `VendorApprovalCreate` | `VendorApprovalRead` | — | Set/update only — no delete; fans out to every affected use case same-request. |
| `PUT /products/{product_id}/approval` | `gov:authoriser` | `ProductApprovalCreate` | `ProductApprovalRead` | — | Same shape as vendor approval. |
| `GET /systems/{system_id}/rollup` | `gov:ALL` | — | `SystemRollupRead` | — | Use cases + states + highest tier + per-use-case `blocking`, recomputed live. |
| `GET /portfolio` | `gov:ALL` | — | `SystemRollupRead[]` | — | Tenant-wide, one entry per system with ≥1 use case. |
| `GET /clearance-queue` | `gov:ALL` | — | `ClearanceQueueRead` | — | UI-F10-CLEARANCE. Vendor-grouped clearance status, recomputed live; `awaiting_use_case_count`/`affected_use_case_count`/`affected_system_count` reuse the same `System.catalogue_vendor_id`/`catalogue_product_id` join `fan_out_vendor_approval`/`fan_out_product_approval` use. Read is `gov:ALL`; the set-clearance act stays on the existing `PUT /vendors\|products/{id}/approval` rows above, `gov:authoriser`. |

**`POST /use-cases/{id}/advance` does not exist** — see §4.

### Governance role management — `app/routers/v1/governance_roles.py`

| Method · Path | Gate | Request | Response | If-Match | Notes |
|---|---|---|---|---|---|
| `GET /governance-roles/catalogue` | `member` | — | `GovernanceCatalogueRead` | — | The five roles + the full SoD conflict matrix. |
| `GET /governance-roles/assignments` | `member` | — | `GovernanceRoleAssignmentRead[]` | — | Tenant-wide. |
| `GET /governance-roles/assignments/member/{membership_id}` | `member` | — | `GovernanceRoleAssignmentRead[]` | — | Takes a **foreign** `membership_id`, no self-check — not a self-read route (`GET /v1/me` exists for that). |
| `POST /governance-roles/assignments` | `admin` | `GovernanceRoleAssignmentCreate` | `GovernanceRoleAssignmentRead` (201) | — | `assert_governance_assignable` blocks SoD conflicts + self-assignment. |
| `DELETE /governance-roles/assignments/{assignment_id}` | `admin` | — | — (204) | — | |

### Members — `app/routers/v1/members.py`

| Method · Path | Gate | Request | Response | If-Match | Notes |
|---|---|---|---|---|---|
| `POST /members` | `admin` | `MemberCreate` | `MemberCreated` (201) | — | Cognito invite + `Membership` atomic with compensation (`PAT-1`); 409 if already provisioned. |
| `GET /members[?status][&limit][&cursor]` | `admin` | — | `MemberListResponse` | — | Keyset-paginated; `membership` joined to `app_user`, accept status derived from Cognito — never a bare `app_user` read (`INV-2`). |

### Me — `app/routers/v1/me.py`

| Method · Path | Gate | Request | Response | If-Match | Notes |
|---|---|---|---|---|---|
| `GET /me` | `member` | — | `MeRead` | — | Self-scoped only, no path param. Roles read from `governance_role_assignment`, never a token claim (`D-24`). |

### Evidence repository — `app/routers/v1/evidence.py`

| Method · Path | Gate | Request | Response | If-Match | Notes |
|---|---|---|---|---|---|
| `POST /evidence` | `gov:write` (enforced *inside* `evidence_service.upload_evidence`, not as a route dependency — the route only depends on `get_tenant_context`, no `get_tenant_db`, `PAT-3`) | multipart: `file`, `title?` | `EvidenceRead` (201) | — | Two-pass spool + server SHA256; S3 put holds no DB transaction. **Gate footgun:** reading the route signature alone looks like `member`-only — the role check is a manual `require_governance_role(...)(ctx=ctx, db=db)` call inside the service, since the route has no `db` dependency to hang a gate on. |
| `GET /evidence[?limit][&cursor]` | `gov:ALL` | — | `EvidenceListResponse` | — | Cursor-paginated, carries `link_count`. |
| `GET /evidence/{evidence_id}` | `gov:ALL` | — | `EvidenceDetailRead` | — | Short-TTL presigned download URL; hardened (forced attachment, neutralised content-type — `INV-22`). |
| `DELETE /evidence/{evidence_id}` | `gov:write` | — | — (204) | — | Single guarded statement (`INV-19`). |

### Assessments — AIIA core, review/sign-off, feeders, sections, items, links — `app/routers/v1/assessments.py`

No shared path prefix — routes split across `/use-cases/{id}/assessments` and `/assessments/...`.

| Method · Path | Gate | Request | Response | If-Match | Notes |
|---|---|---|---|---|---|
| `POST /use-cases/{use_case_id}/assessments` | `gov:system_owner` | — | `AssessmentRead` (201) | — | Creates the AIIA from the use case's current classification; 409 on `PROHIBITED`/`REQUIRES_CONTEXT`/no-snapshot, or if one already exists (`uq_one_aiia_per_use_case`). |
| `GET /use-cases/{use_case_id}/assessments` | `gov:ALL` | — | `AssessmentRead[]` | — | |
| `GET /assessments/{assessment_id}` | `gov:ALL` | — | `AssessmentDetail` | — | `items` assembled at read time (`assemble_aiia_items`, `INV-16`); each item includes `control_links: ControlLinkRead[]` (batch-loaded, `DF3-7`) and `evidence_links: ItemEvidenceRead[]` (batch-loaded, `DF5-8`, UI-F5-EVIDENCE). No `download_url` in manifest — download is on-intent via `GET /evidence/{id}` (DF5-3). |
| `DELETE /assessments/{assessment_id}` | `gov:system_owner` | — | — (204) | — | Pristine-delete only (`INV-17, 36`); same route/gate for an AIIA or a feeder. |
| `POST /assessments/{assessment_id}/submit` | `gov:system_owner` | — | `AssessmentRead` | **yes** (`lock_version`) | `DRAFT → IN_REVIEW`. |
| `POST /assessments/{assessment_id}/review` | `gov:reviewer` | `AssessmentReviewCreate` | `AssessmentRead` | **yes** | `IN_REVIEW → APPROVED`\|`DRAFT` (bounce); `APPROVED` same-transaction-advances the use case. Act-SoD vs. submitter. |
| `POST /assessments/{assessment_id}/reopen` | `gov:system_owner` | — | `AssessmentRead` | **yes** | `APPROVED → NEEDS_REFRESH`. |
| `GET /assessments/review-queue` | `gov:reviewer` | — | `ReviewQueueEntryRead[]` | — | |
| `POST /assessments/{aiia_id}/feeders` | `gov:write` | `FeederCreate` | `AssessmentRead` (201) | — | 422 if `type=AIIA`, feeder-of-feeder, or duplicate type (`uq_feeder_type_per_aiia`). |
| `GET /assessments/{aiia_id}/feeder-recommendations` | `gov:ALL` | — | `FeederRecommendationRead[]` | — | Required/recommended/N-A + basis. |
| `GET /assessments/{assessment_id}/sections` | `gov:ALL` | — | `SectionRead[]` | — | |
| `POST /assessments/{assessment_id}/items` | `gov:write` | `AssessmentItemCreate` | `AssessmentItemRead` (201) | — | |
| `PATCH /assessments/{assessment_id}/items/{item_id}` | `gov:write` | `AssessmentItemAmend` | `AssessmentItemRead` | **yes** | Single conditional `UPDATE`; 412 stale lock, 409 bad-from-state (`PAT-6`). |
| `POST /assessments/{assessment_id}/items/{item_id}/confirm` | `gov:write` | — | `AssessmentItemRead` | **yes** | |
| `DELETE /assessments/{assessment_id}/items/{item_id}` | `gov:write` | — | — (204) | — | |
| `POST /assessments/{assessment_id}/items/{item_id}/control-links` | `gov:write` | `ControlLinkCreate` | `ControlLinkRead` (201) | — | |
| `DELETE /assessments/{assessment_id}/items/{item_id}/control-links/{link_id}` | `gov:write` | — | — (204) | — | |
| `POST /assessments/{assessment_id}/items/{item_id}/evidence-links` | `gov:write` | `EvidenceLinkCreate` | `EvidenceLinkRead` (201) | — | Disposition-gated — still-`AI_SUGGESTED` item rejected (`INV-20`). |
| `DELETE /assessments/{assessment_id}/items/{item_id}/evidence-links/{evidence_id}` | `gov:write` | — | — (204) | — | Idempotent unlink. |

`admin` (administrative role, zero governance roles) gets 403 on every route in this file, reads included — there is no admin carve-out.

### Coverage — `app/routers/v1/coverage.py`

Read-only, zero migrations, recomputed per request (never persisted — `INV-25`).

| Method · Path | Gate | Request | Response | If-Match | Notes |
|---|---|---|---|---|---|
| `GET /coverage[?framework][&include_unapproved]` | `gov:ALL` | — | `CoverageMatrixRead` | — | Tenant-wide. |
| `GET /systems/{system_id}/coverage[?framework][&include_unapproved]` | `gov:ALL` | — | `CoverageMatrixRead` | — | |
| `GET /assessments/{assessment_id}/coverage[?framework][&include_unapproved]` | `gov:ALL` | — | `CoverageMatrixRead` | — | 422 if `assessment_id` is a feeder, not an AIIA. |

### Export / audit pack — `app/routers/v1/export.py`

No `get_tenant_db` on any route — each opens its own `REPEATABLE READ` session and runs the governance-role gate (`gov:ALL`, any-governance-role read — the auditor's route) inside it (`export_service._export_session`, `PAT-10`/`D-35`), the same shape evidence upload uses.

| Method · Path | Gate | Request | Response | If-Match | Notes |
|---|---|---|---|---|---|
| `GET /systems/{system_id}/export[?framework]` | `gov:ALL` (in-session) | — | `SystemExportRead` | — | |
| `GET /use-cases/{use_case_id}/export[?framework]` | `gov:ALL` (in-session) | — | `UseCaseExportRead` | — | |
| `GET /use-cases/{use_case_id}/authorisation/document[?round]` | `gov:ALL` (in-session) | — | `AtoDocumentRead` | — | 404 if never authorised. ATO row is authoritative; referenced assessment/classification shown as current state, labelled "may have drifted" (`D-34`) — never reconstructed to the authorisation moment. |
| `GET /export?framework=` | `gov:ALL` (in-session) | — | `FrameworkExportRead` | — | |

Evidence appears by manifest (id/sha256/filename/back-refs) only — never bytes or a presigned URL (`INV-40`).

### Root / unversioned — `app/main.py`

| Method · Path | Gate | Request | Response | If-Match | Notes |
|---|---|---|---|---|---|
| `GET /v1/whoami` | token-verified, no tenant resolution | — | `{sub, email, name, tenant_id, role}` (raw `dict`) | — | Smoke route — echoes the verified Cognito claims, does not hit the DB. |
| `GET /health` | `anon` | — | `{status, env}` | — | Liveness. |
| `GET /health/db` | `anon` | — | `{status, db}` | — | Readiness — `SELECT 1`. |

---

## 3. Platform plane — `/platform`

Separate auth context entirely (`operator_authz`, not `app.auth.context`) — `CurrentOperator` + `require_permission(...)`, never a tenant `TenantContext`/governance role (`INV-1`, `D-24`).

### `app/routers/platform/tenants.py`

| Method · Path | Gate | Request | Response | If-Match | Notes |
|---|---|---|---|---|---|
| `POST /platform/provision` | `tenant:provision` | `ProvisionRequest` | `ProvisionResponse` (201) | — | The **only** tenant-creation path (`D-23`); 409 if already provisioned. |
| `GET /platform/tenants` | `tenant:provision` | — | `TenantListItem[]` | — | Cross-tenant read — operator plane only, never reachable from the tenant plane. |

### `app/routers/platform/me.py`

| Method · Path | Gate | Request | Response | If-Match | Notes |
|---|---|---|---|---|---|
| `GET /platform/me` | `op-auth` | — | `{id, email, display_name, permissions}` (raw `dict`) | — | Durable operator identity contract (`D-39`); the operator-plane analogue of `GET /v1/me`. Permission keys in `permissions` are byte-exact (e.g. `'tenant:provision'`). |

`GET /platform/whoami` was struck this sprint (`UI-F7-PROVISION`, A1/N4); route returns 404.

### `app/routers/platform/operators.py`

All three routes share gate `operator:create` (`require_permission("operator:create")`). Note: the gate column uses the bare permission key — the `operator:<perm>` shorthand would double-prefix (`operator:operator:create`) for permissions whose key already begins with `operator:` (`D-40`).

| Method · Path | Gate | Request | Response | If-Match | Notes |
|---|---|---|---|---|---|
| `POST /platform/operators` | `operator:create` | `OperatorCreate` | `OperatorCreated` (201) | — | Wraps `provision_operator`; 409 duplicate email; 422 unknown `role_key`; 500 Cognito failure. `PlatformAuditEvent` `CREATE_OPERATOR` attributed to calling operator. |
| `GET /platform/operators` | `operator:create` | — | `OperatorListItem[]` | — | Lists all operators with their roles. |
| `GET /platform/roles` | `operator:create` | — | `RoleListItem[]` | — | Lists assignable roles (for the create-operator form select). |

---

## 4. Confirmed absent — do not assume these exist

Routes that sound plausible given the domain model, but do not exist at repo HEAD as of this sprint (`UI-F1-INTAKE` §0 pre-flight). If a future design wants one of these, that's a new route to build, not a gap in this map.

- **`POST /v1/use-cases/{id}/advance`** — no generic "advance" verb. The lifecycle auto-advances on every classification/assessment/treatment write; the only *explicit* state-advancing acts are `POST .../authorise` (→ `authorised`) and `POST .../lifecycle/re-evaluate` (re-settle, not force-advance).
- **`GET /v1/systems/{id}/approval-status`** — no dedicated approval-status field/route, still absent as of `UI-F10-CLEARANCE`. Vendor/product clearance is read via `GET /v1/use-cases/{id}/lifecycle`'s `blocking` vector (`responsible_party == "authoriser"`), `GET /v1/systems/{id}/rollup`'s per-use-case `blocking`, or the dedicated vendor-grouped `GET /v1/clearance-queue` (`UI-F10-CLEARANCE`).
- **`POST /v1/tenants`** — intentionally removed (`D-23`). Provisioning is operator-only, `POST /platform/provision`.
- **A vocab-list route for `SystemLifecycleStage`** — it's a 4-value fixed enum (`development`/`pilot`/`production`/`retired`), not a vocab table; there is nothing to list. Render it as a static client-side option set, but confirm casing against `pg_enum` first (`D-21` — wire values are the enum's lowercase `.value`, not the uppercase DB label name; see `DATA-MODEL.md` enum-label note).
- **A member-list route usable for `SystemCreate.owner_user_id`** — `GET /v1/members` exists but is `admin`-gated, not `gov:*`; there is no member-level "pick a tenant member" read. `owner_user_id` is optional and FK-validated on write only.

---

## 5. `If-Match` / optimistic concurrency — which routes actually take it

Only five routes accept `If-Match` (`PAT-6`, `INV-14`) — all five are AIIA item/assessment-status mutations in `assessments.py`:

`POST /assessments/{id}/submit` · `POST /assessments/{id}/review` · `POST /assessments/{id}/reopen` · `PATCH /assessments/{id}/items/{item_id}` · `POST /assessments/{id}/items/{item_id}/confirm`

Every other mutation in this map — including every `UI-F1-INTAKE`-consumed route — never sends or checks it. A client building a generic "send `If-Match` whenever we have a `lock_version`" helper must special-case these five, not default to always-on.

---

## 6. Sprint consumption notes

**`UI-F3-ASSESS`** — no route delta; consumed-only. No routes added, removed, or re-gated. Routes consumed by this sprint:

- `GET /me` — pre-flight role branch (DF2-5: admin → no gov:ALL call)
- `GET /use-cases/{id}` — identity + system_id for header
- `GET /systems/{id}/rollup` — system name (not in `UseCaseWithClassification`)
- `GET /use-cases/{id}/lifecycle` — whose-court + re-evaluate trigger
- `POST /use-cases/{id}/lifecycle/re-evaluate` — system_owner lever
- `GET /use-cases/{id}/assessments` — find current AIIA
- `POST /use-cases/{id}/assessments` — bootstrap
- `GET /assessments/{id}` — assembled detail (`staleTime: 0`, FE-7)
- `GET /assessments/{id}/sections` — section template
- `GET /assessments/{id}/feeder-recommendations` — feeder recs panel (read-only; A7 provisional)
- `GET /reference/risks` — risk picker
- `GET /reference/controls` — control picker
- `POST /assessments/{id}/items` — item create
- `PATCH /assessments/{id}/items/{item_id}` — amend (If-Match live — first surface to send it, inverts `DF1-5`)
- `POST /assessments/{id}/items/{item_id}/confirm` — confirm AI_SUGGESTED (If-Match)
- `DELETE /assessments/{id}/items/{item_id}` — item delete
- `POST /assessments/{id}/items/{item_id}/control-links` — link control (free on any item, INV-20)
- `DELETE /assessments/{id}/items/{item_id}/control-links/{link_id}` — unlink
- `POST /assessments/{id}/submit` — submit (If-Match on assessment.lock_version)

**Additive backend schema delta (`DF3-7`):** `AssessmentItemRead` now includes `control_links: list[ControlLinkRead]` (batch-loaded in `assemble_aiia_items`). This is a response-shape addition to `GET /assessments/{id}` — the route, gate, and path are unchanged; only the shape of items in `AssessmentDetail.items` grew. No migration required (data already existed in `assessment_item_control`). The `§2` assessments table row is still current — the gate and method are unchanged; the schema note for `GET /assessments/{id}` now reflects `AssessmentDetail` includes `items[].control_links`.

Evidence linking (`POST .../evidence-links`) and coverage (`GET /assessments/{id}/coverage`) are available in the route map but **not consumed** by this sprint (A2/A3 deferred — `DF3-1`, `DF3-2`).

**`UI-F4-ASSURE`** — no route delta; consumed-only. No routes added, removed, or re-gated. Routes consumed by this sprint:

- `GET /me` — pre-flight role branch (5-way extension: reviewer/authoriser/auditor split from assurance catch-all)
- `GET /use-cases/{id}` — classification status for sign-off disambiguation (DF4-2)
- `GET /use-cases/{id}/lifecycle` — whose-court + lifecycle state for act routing
- `GET /use-cases/{id}/assessments` — find current AIIA
- `GET /assessments/{id}` — assembled detail + review history (WI-9b additive field; see below)
- `GET /assessments/{id}/sections` — section template (reviewer/authoriser read)
- `GET /assessments/{id}/feeder-recommendations` — feeder recs panel (read)
- `GET /assessments/review-queue` — reviewer queue (`gov:reviewer`; issued only when caller is reviewer)
- `GET /systems/{id}/rollup` — system name for header
- `POST /assessments/{id}/review` — AIIA review decision (If-Match; `gov:reviewer`)
- `POST /assessments/{id}/reopen` — APPROVED → NEEDS_REFRESH (If-Match; `gov:system_owner`)
- `POST /use-cases/{id}/classification/sign-off` — reviewer sign-off (no If-Match; `gov:reviewer`)
- `POST /use-cases/{id}/authorise` — deployment authorisation (no If-Match; `gov:authoriser`)
- `GET /use-cases/{id}/authorisation` — ATO read + live_state (`staleTime: 0`; `gov:ALL`; 404 if never authorised)

**Additive backend schema delta (`DF4-6`):** `AssessmentDetail` now includes `reviews: list[AssessmentReviewRead]` (batch-loaded in `GET /assessments/{id}` handler via INV-34 membership join). `AssessmentReviewRead` carries `reviewer_display_name` (not a durable stamp — D-25; resolved at read time). No migration required (data already existed in `assessment_review`). Gate and path of `GET /assessments/{id}` unchanged; only the response shape grew.

**`UI-F5-EVIDENCE`** — no route delta; consumed-only. No routes added, removed, or re-gated. Routes consumed by this sprint:

- `GET /me` — pre-flight role branch (admin → no evidence request issued, DF5-7)
- `GET /evidence?limit=50` — evidence repository list (`gov:ALL`)
- `GET /evidence/{evidence_id}` — on-intent download (presigned URL + `evidence.access` audit; `gov:ALL`; `staleTime: 0`; fired only on user click, DF5-3)
- `POST /evidence` — evidence upload (`gov:write`; via dedicated BFF handler — NOT the generic proxy, FE-12)
- `DELETE /evidence/{evidence_id}` — evidence delete (`gov:write`)
- `GET /assessments/{id}` — assembled detail (now includes `items[].evidence_links`, DF5-8; gate and path unchanged)
- `POST /assessments/{id}/items/{item_id}/evidence-links` — link evidence (`gov:write`; disposition-gated — AI_SUGGESTED rejects, INV-20; no `If-Match`, DF5-4)
- `DELETE /assessments/{id}/items/{item_id}/evidence-links/{evidence_id}` — unlink (path param is `evidence_id`, not link-row id, DF5-9; no `If-Match`, DF5-4)

**Additive backend schema delta (DF5-8):** `AssessmentItemRead` now includes `evidence_links: list[ItemEvidenceRead]` (batch-loaded in `assemble_aiia_items` via `_batch_evidence_links` — JOIN `assessment_item_evidence → evidence`). `ItemEvidenceRead` carries `evidence_id`, `title`, `sha256`, `content_type`, `size_bytes` — no `download_url` (DF5-3). No migration required. Same additive pattern as DF3-7/DF4-6; existing callers unbroken.

**`UI-F7-PROVISION`** — **durable route delta +1** (`whoami` struck → `/platform/me` added; raw-route replace, no net route count change). Backend item only; frontend surface consumes existing `POST /platform/provision` + `GET /platform/tenants` (gates unchanged). Routes consumed:

- `GET /platform/me` — operator identity + permission set at surface root (`op-auth`; `D-39`); no `GET /platform/tenants` or form issued when `tenant:provision ∉ permissions` (`DF7-1`)
- `GET /platform/tenants` — tenant list, read-only (`operator:tenant:provision`)
- `POST /platform/provision` — provision a new tenant (`operator:tenant:provision`; 409 collision keys: `slug` and `owner_email` independently)

**`UI-F8-OPERATOR-RBAC`** — **durable route delta +3** (`POST /platform/operators`, `GET /platform/operators`, `GET /platform/roles`; all gated `operator:create`). Backend + frontend; schema delta 0 DDL (seed-only migration `c8f3a2e91bd5`). Routes consumed:

- `GET /platform/me` — operator identity + permission set at surface root (`op-auth`); `operator:create ∈ permissions` gates list + form (`DF7-1` pattern)
- `GET /platform/operators` — operator list (`operator:create`; enabled only when permission held)
- `GET /platform/roles` — assignable roles for form select (`operator:create`; enabled only when permission held)
- `POST /platform/operators` — create new operator with role (`operator:create`; 409 duplicate email; 422 unknown role; 500 Cognito failure)

**`UI-F6-AUDITPACK`** — **no route delta; consumed-only**. No routes added, removed, or re-gated. Routes consumed by this sprint:

- `GET /me` — pre-flight role branch (admin → no coverage/export call issued, DF2-5)
- `GET /coverage[?framework][&include_unapproved]` — tenant-wide coverage matrix (`gov:ALL`; eager, `staleTime: 0`)
- `GET /systems/{id}/coverage[?framework][&include_unapproved]` — system-scoped coverage (`gov:ALL`; eager)
- `GET /assessments/{id}/coverage[?framework][&include_unapproved]` — use-case/assessment-scoped coverage (`gov:ALL`; eager; only when governing AIIA is `APPROVED` — INV-38/DF3-2)
- `GET /systems/{id}/export[?framework]` — system audit pack (`gov:ALL` in-session; deliberate-only — INV-53; stages `export.generated`)
- `GET /use-cases/{id}/export[?framework]` — use-case audit pack (`gov:ALL` in-session; deliberate-only — INV-53)
- `GET /use-cases/{id}/authorisation/document[?round]` — ATO document (`gov:ALL` in-session; deliberate-only — INV-53; 404 if never authorised; no round-enumeration call — DF6-10)
- `GET /export?framework=` — framework audit pack (`gov:ALL` in-session; deliberate-only — INV-53)
- `GET /evidence/{id}` — on-intent manifest download (presigned URL + `evidence.access` audit; same DF5-3 pattern as F5)

**Zero backend/schema delta:** all routes built at Sprint 7a/7b; response shapes (`CoverageMatrixRead`, `UseCaseExportRead`, `SystemExportRead`, `FrameworkExportRead`, `AtoDocumentRead`) mirrored into `packages/api-client/src/contracts/coverage.ts` and `export.ts` — no server change.

**`UI-F10-CLEARANCE`** — **1 NEW route** (`GET /clearance-queue`, `gov:ALL`; additive schema, no table/enum/migration). Backend + frontend. Routes consumed:

- `GET /me` — pre-flight role branch; zero governance roles (admin) → no `GET /clearance-queue` call issued (DF-CLR-17)
- `GET /clearance-queue` — vendor-grouped clearance status (`gov:ALL`; live state, `staleTime: 0`); read for every governance role, set-clearance action rendered only for `authoriser`
- `PUT /vendors/{vendor_id}/approval` — unchanged, now also consumed from the new `apps/tenant/app/clearances` surface (`gov:authoriser`)
- `PUT /products/{product_id}/approval` — unchanged, same surface (`gov:authoriser`)
- `GET /portfolio` — unchanged; dashboard your-court/posture re-treatment reads already-loaded data, no new call (DF6-9)
