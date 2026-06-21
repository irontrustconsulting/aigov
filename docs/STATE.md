# STATE.md — IronTrust AI Governance Platform

**Location:** `docs/STATE.md` — single source, mirrored to project knowledge. **The most volatile canonical — updated every sprint.**
**Purpose:** What is implemented and what must not be reinvented, at the level of *what exists · what shape · which gate*. It points outward for depth and never restates the detail.
**Lanes:** constraints → `INVARIANTS.md` (`INV-n`); schema (tables/enums/indexes) → `DATA-MODEL.md`; auth / identity / RLS / session mechanics → `ARCHITECTURE.md`; implementation shapes → `PATTERNS.md` (`PAT-n`); decisions/rationale → `DECISIONS.md` (`D-n`); conceptual model → `DOMAIN.md`.

**Current through:** Sprint 7b (export / audit pack). Sprints 1–7b built.

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
Product-category hierarchy, vendors/products by category, EU subcategory list — anonymous (back the public-ish wizard). `GET /v1/reference/products/{id}` (intake wizard detail). `GET /v1/reference/risks` (filter `layer`), `/v1/reference/controls` (filter `framework`) — member-level. Seeded: six controlled-vocab tables, control library (ISO 42001 / EU AI Act cross-map), risk library (OWASP LLM + NIST/ISO with risk→control links), EU taxonomy, product-category taxonomy, governance-role catalogue + conflict matrix, decision tree, AIIA/feeder section template.

### Platform (operator-facing)
Tenant provisioning (Cognito + DB, orphan-free — PAT-1); tenant listing; operator identity endpoints.

---

## 2. Audit actions in use

**Tenant plane** (`AuditEvent`, append-only, RLS, immutability trigger — INV-5):
`system.created`/`updated` · `classification.created`/`overridden`/`signed_off` · `governance_role.granted`/`revoked` · `member.created` · `assessment.created`/`deleted`/`feeder_created` · `assessment_item.created`/`amended`/`confirmed`/`deleted`/`treatment_set` · `control_link.created`/`deleted` · `evidence.created`/`deleted`/`access`/`linked`/`unlinked` · `lifecycle.advanced`/`held`/`halted_prohibited`/`authorised` · `vendor_approval.set`/`updated` · `product_approval.set`/`updated` · `assessment.submitted`/`review_recorded`/`reopened`/`needs_refresh` (6a) · `authorisation.granted` (6b) · `export.generated` (7b).

`action` is `varchar(120)` — a new action string needs no migration. `AuditEvent` stores `actor_user_id` (FK only); durable name/email is the deferred cross-cutting gap (D-25), with the ATO the lone exception. 7a coverage emits no audit (pure read). **Platform plane:** `PlatformAuditEvent` (operator-attributed).

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