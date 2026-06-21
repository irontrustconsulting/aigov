# API-ROUTES.md — IronTrust AI Governance Platform · FastAPI Route Map

**Location:** `docs/API-ROUTES.md` — single source, mirrored to project knowledge. **Updated each sprint that adds, removes, or re-gates a route** — the route-surface counterpart to `DATA-MODEL.md` (schema) and `FRONTEND.md` (client↔API conventions).
**Purpose:** the canonical inventory of every FastAPI route — method, path, auth gate, request/response schema, file:line — so a sprint can verify the contract it's about to consume *from this file*, not by re-grepping `app/routers/` from scratch. It also names routes that sound plausible but **do not exist**, so a design doesn't quietly assume one.
**Scope (deliberate):** routes and gates, not field-by-field schema detail — schemas are named and pointed at `app/schemas/*.py`; full field shape lives there (D-21: the code is authoritative) or in `DATA-MODEL.md` for the underlying tables. Frontend-side mirrored types live in `packages/api-client/src/contracts/`.

**Authoritative inventory:** every router registered in `app/main.py`, read line-by-line against repo HEAD this sprint (`UI-F1-INTAKE`). **Still verify before relying on it** (`D-21`) — this file can drift the moment a route changes; if it disagrees with `app/routers/`, the code wins and this file is stale, not the other way round.

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
| `GET /reference/products/{product_id}` | `anon` | — | `ProductDetailOut` | — | Vendor + category tags + EU subcategories. |
| `GET /reference/operator-roles` | `member` | — | `VocabItemOut[]` | — | `UI-F1-INTAKE` WI-0; `active=true`, `sort_order`. |
| `GET /reference/hosting-models` | `member` | — | `VocabItemOut[]` | — | WI-0. |
| `GET /reference/usage-contexts` | `member` | — | `VocabItemOut[]` | — | WI-0. |
| `GET /reference/human-oversight-types` | `member` | — | `VocabItemOut[]` | — | WI-0. |
| `GET /reference/data-categories` | `member` | — | `DataCategoryOut[]` | — | WI-0; carries `is_special_category`. |
| `GET /reference/affected-parties` | `member` | — | `AffectedPartyOut[]` | — | WI-0; carries `is_vulnerable_group`. |
| `GET /reference/risks[?layer]` | `member` | — | `RiskRead[]` | — | AIIA item authoring. |
| `GET /reference/controls[?framework]` | `member` | — | `ControlRead[]` | — | AIIA item authoring; carries `frameworks[]` cross-map. |

The product/category/vendor/subcategory reads are intentionally `anon` — they back the pre-auth, sales-led catalogue drill-down (`UX.md` §4). The six `member`-gated vocab/risk/control reads are not — they're consumed mid-flow, after the caller is already a signed-in tenant member.

### Systems — `app/routers/v1/systems.py`

| Method · Path | Gate | Request | Response | If-Match | Notes |
|---|---|---|---|---|---|
| `POST /systems` | `gov:system_owner` | `SystemCreate` | `SystemDetail` (201) | — | `is_custom` ⊕ catalogue link is a 422 check constraint (`ck_system_custom_no_catalogue`), not app code. |
| `GET /systems` | `member` | — | `SystemRead[]` | — | RLS-scoped list. |
| `GET /systems/{system_id}` | `member` | — | `SystemDetail` | — | |
| `PATCH /systems/{system_id}` | `gov:system_owner` | `SystemUpdate` | `SystemDetail` | — | Link arrays (`data_category_ids`/`affected_party_ids`) replace, not merge. Relinking `catalogue_product_id` with use cases present → 409. |
| `GET /systems/{system_id}/prefill` | `member` | — | `PrefillResponse` | — | `200` with `facts: []` when no product (incl. `is_custom`) — never `404`. |

### Use cases & classification — gate 1 (the bridge) — `app/routers/v1/use_cases.py`

| Method · Path | Gate | Request | Response | If-Match | Notes |
|---|---|---|---|---|---|
| `POST /use-cases` | `gov:system_owner` | `UseCaseCreate` | `UseCaseWithClassification` (201) | — | Auto-derives + snapshots the classification in the same call (the bridge: `system → product → product_category → eu_ai_act_subcategory`). |
| `GET /use-cases` | `member` | — | `UseCaseRead[]` | — | |
| `GET /use-cases/{use_case_id}` | `member` | — | `UseCaseWithClassification` | — | 404 if no current classification snapshot exists. |
| `POST /use-cases/{use_case_id}/classify/override` | `gov:system_owner` | `OverrideRequest` | `UseCaseWithClassification` | — | 422 on unknown `subcategory_code` or `tier` ≠ `subcategory.tier`. New current snapshot; prior preserved `is_current=False`. |

`ClassificationRead` (the gate-1 projection, embedded in both responses above) carries `requires_context`, never `status`.

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
| `GET /assessments/{assessment_id}` | `gov:ALL` | — | `AssessmentDetail` | — | `items` assembled at read time (`assemble_aiia_items`, `INV-16`). |
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
| `POST /platform/provision` | `operator:tenant:provision` | `ProvisionRequest` | `ProvisionResponse` (201) | — | The **only** tenant-creation path (`D-23`); 409 if already provisioned. |
| `GET /platform/tenants` | `operator:tenant:provision` | — | `TenantListItem[]` | — | Cross-tenant read — operator plane only, never reachable from the tenant plane. |

### `app/routers/platform/whoami.py`

| Method · Path | Gate | Request | Response | If-Match | Notes |
|---|---|---|---|---|---|
| `GET /platform/whoami` | `operator:tenant:provision` | — | `{id, cognito_sub, email, display_name, permissions}` (raw `dict`) | — | Verification aid, marked `TODO: remove after acceptance testing` in source — still live as of this sprint. |

---

## 4. Confirmed absent — do not assume these exist

Routes that sound plausible given the domain model, but do not exist at repo HEAD as of this sprint (`UI-F1-INTAKE` §0 pre-flight). If a future design wants one of these, that's a new route to build, not a gap in this map.

- **`POST /v1/use-cases/{id}/advance`** — no generic "advance" verb. The lifecycle auto-advances on every classification/assessment/treatment write; the only *explicit* state-advancing acts are `POST .../authorise` (→ `authorised`) and `POST .../lifecycle/re-evaluate` (re-settle, not force-advance).
- **`GET /v1/systems/{id}/approval-status`** — no dedicated approval-status field/route. Vendor/product clearance is read via `GET /v1/use-cases/{id}/lifecycle`'s `blocking` vector (`responsible_party == "authoriser"`) or `GET /v1/systems/{id}/rollup`'s per-use-case `blocking`.
- **`POST /v1/tenants`** — intentionally removed (`D-23`). Provisioning is operator-only, `POST /platform/provision`.
- **A vocab-list route for `SystemLifecycleStage`** — it's a 4-value fixed enum (`development`/`pilot`/`production`/`retired`), not a vocab table; there is nothing to list. Render it as a static client-side option set, but confirm casing against `pg_enum` first (`D-21` — wire values are the enum's lowercase `.value`, not the uppercase DB label name; see `DATA-MODEL.md` enum-label note).
- **A member-list route usable for `SystemCreate.owner_user_id`** — `GET /v1/members` exists but is `admin`-gated, not `gov:*`; there is no member-level "pick a tenant member" read. `owner_user_id` is optional and FK-validated on write only.

---

## 5. `If-Match` / optimistic concurrency — which routes actually take it

Only five routes accept `If-Match` (`PAT-6`, `INV-14`) — all five are AIIA item/assessment-status mutations in `assessments.py`:

`POST /assessments/{id}/submit` · `POST /assessments/{id}/review` · `POST /assessments/{id}/reopen` · `PATCH /assessments/{id}/items/{item_id}` · `POST /assessments/{id}/items/{item_id}/confirm`

Every other mutation in this map — including every `UI-F1-INTAKE`-consumed route — never sends or checks it. A client building a generic "send `If-Match` whenever we have a `lock_version`" helper must special-case these five, not default to always-on.
