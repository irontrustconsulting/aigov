# STATE.md — IronTrust AI Governance Platform

**Purpose:** A curated context artifact for design and review agents without direct repo access. It describes what is on the ground, what patterns exist, what must not be reinvented, and what is deliberately deferred. It is not a code inventory, not a changelog, and does not duplicate `CLAUDE.md`.

**Companion documents:**
- `CLAUDE.md` — durable engineering rules: stack, DB role model, session model, code conventions, schema-level invariants. Read for *how we build*.
- `docs/PRD.md` — product requirements. Read for *what to build and why*.
- `STATE.md` (this) — implementation state. Read for *what already exists and what must not be reinvented*.
- `sprints/*.md` — the active unit of work.

---

## How to use this file in prompts

| Task | Relevant sections |
|---|---|
| Designing a new feature / sprint | §3 (what exists) + §5 (deferred) — avoid building over existing work or into deferred scope |
| Writing a sprint spec | §4 (patterns) — reference the right seams; §2 (baseline) — anchor architectural decisions |
| Reviewing an implementation | §6 (invariants) as checklist; §4 (patterns) as the reference for correct shape |
| Generating an implementation plan | §2 (baseline) + §4 (patterns) for orientation; §5 to know where to stop |

Do not treat STATE.md as the sole source of truth for specific field names, function signatures, or SQL details. If a design depends on these, verify against the code.

---

## 1. Platform baseline

### Identity and membership

The core chain is:

```
Tenant ←── Membership(role: UserRole) ──→ User (app_user)
```

- **Tenant**: the organisational unit. Created only by `provision_tenant()` (operator CLI or `POST /platform/provision`). Never self-service; no public creation endpoint.
- **User** (`app_user`): a human identity. **Global, non-RLS.** Linked to Cognito via `cognito_sub`. Email is not DB-unique — Cognito is the uniqueness and invite authority. A user's access to any tenant is always mediated by a `Membership` row.
- **Membership**: the unit of authorisation. RLS-scoped to its tenant. `role` (`ADMIN` or `MEMBER`) is the administrative axis only — it confers no governance power.
- **`app_user` is not RLS-protected**: any read of users within a tenant context must join from `membership`, never query `app_user` directly. The app DB role can see all rows; only the membership join restricts scope to the caller's tenant.
- **One tenant per user**: Cognito `custom:tenant_id` is immutable. A user cannot belong to multiple tenants; multi-tenant identity is blocked by design.

### Auth and context (tenant side)

```
verify_cognito_token
  └── get_tenant_context  →  TenantContext (DB-authorised identity)
        └── get_tenant_db  →  RLS-scoped Session (app.current_tenant set per-transaction)
              ├── require_role("admin"|"member")      — administrative axis
              └── require_governance_role("key"...)   — governance axis (DB lookup)
```

`TenantContext` carries `user_id`, `membership_id`, `tenant_id`, `role` (authoritative from the membership row, not the token), `email`, `name`. It is the resolved, DB-verified identity for every tenant request.

The two gate dependencies guard different axes and must not be combined on the same endpoint. `require_role` is for administrative actions (member management, governance role assignment). `require_governance_role` is for workflow actions (system registration, classification, assessment authoring). `tenant_id` is always sourced from `ctx.tenant_id`, never from request body.

**Platform operators** use a wholly separate chain (`verify_operator_token` → `get_current_operator`) with permission-based authZ (`require_permission("key")`). Tenant and operator tokens cannot satisfy each other's verifiers.

### Multi-tenancy and RLS

Shared database with Postgres row-level security. RLS policies read `app.current_tenant` (set `SET LOCAL` per-transaction inside `get_tenant_db`) — transaction-local, cannot leak across pooled connections.

Global reference tables (catalogue, controls, risks, taxonomy, governance role catalogue and conflict matrix, decision tree, assessment section templates) have no `tenant_id` and no RLS. They are cross-tenant by design and readable from any session. Tenant data always carries `tenant_id`.

The app DB role (`irontrustai_app`, `NOBYPASSRLS`) has blanket DML on all `public` tables. Tenant isolation is enforced entirely by RLS, not by table grants. Privilege-elevated DB roles exist for provisioning and identity resolution; each is bound to exactly one engine/sessionmaker and may not be shared across purposes.

---

## 2. Governance role model

Two axes are strictly and permanently separated:

- **Administrative axis** (`UserRole` on `Membership`): account management only — managing members, assigning governance roles. Zero governance power.
- **Governance axis** (`governance_role_assignment`): five roles on three lines of defence.

| Role | Line | Composable with |
|---|---|---|
| `system_owner` | 1st | `contributor` only |
| `contributor` | 1st | `system_owner` only |
| `reviewer` | 2nd | — |
| `authoriser` | 2nd | — |
| `auditor` | 3rd | — |

Every cross-line pair conflicts. `system_owner + contributor` is the only composable pair. The conflict matrix is policy-as-data in the `governance_role_conflict` table (9 rows); `assert_governance_assignable()` is the **single locus** that enforces it — all new assignment paths must go through it. Self-assignment (admin granting to themselves) is blocked.

Governance roles are currently **tenant-wide**, not per-system. The per-system extension is designed as additive (a nullable `scope_id` on `governance_role_assignment`, `NULL` = tenant-wide, preserving every existing grant). Do not build it now; leave the seam.

---

## 3. Implemented capabilities

### AI system registration — full intake
- `POST /v1/systems` captures structured intake metadata: `catalogue_product_id` (links to the global catalogue), `operator_role_id`, `hosting_model_id`, `usage_context_id`, `human_oversight_type_id` (all single-select FKs into global vocab tables), `lifecycle_stage` (enum), `is_custom` (bool), multi-select `data_category_ids` and `affected_party_ids` (via link tables `system_data_category` / `system_affected_party`), and free-text `purpose` (written to `metadata_blob["purpose"]`).
- When `catalogue_product_id` is supplied, `catalogue_vendor_id` is derived from the product's vendor; any client-supplied vendor is overridden. Vendor-only (no product) is permitted.
- `is_custom = true` with any catalogue FK is rejected at the API layer (422) and blocked at the DB level (check constraint `ck_system_custom_no_catalogue`).
- All vocab FK and link IDs must reference `active = true` rows; inactive or missing IDs are rejected (422). `owner_user_id`, when supplied, must be a member of the tenant (service-layer check).
- `GET /v1/systems/{id}` returns full `SystemDetail`: resolved vocab labels, catalogue product/vendor names, `data_categories` with `is_special_category`, `affected_parties` with `is_vulnerable_group`, `use_case_count`, and per-use-case lifecycle states.
- `PATCH /v1/systems/{id}` updates any subset of metadata fields; link arrays replace the full set when supplied. Changing `catalogue_product_id` when use cases already exist is rejected (409). Vendor is re-derived when the product changes.
- `system.created` and `system.updated` audit events are committed atomically with the business rows. Reads emit no audit.
- Gate on `POST` and `PATCH`: `require_governance_role("system_owner")`. `GET` endpoints: any authenticated member.

### Catalogue prefill
- `GET /v1/systems/{id}/prefill` returns all `catalogue_fact` rows for the system's linked product, each with `key`, `value` (jsonb passthrough), `source_url`, `source_label`, `last_checked_at`, and `provenance`. This is the display-only confirm/amend panel data.
- Systems without a linked product (including `is_custom = true`) return `200` with an empty facts list — never `404`.
- No write-back, no provenance transition. Catalogue facts are surfaced as-is; tenant confirmation/amendment is a future sprint.

### AI system classification — bridge auto-resolve (gate 1)
- EU AI Act classification is resolved automatically on use case creation by traversing the seeded reference bridge (`system → catalogue_product → product_category → eu_ai_act_subcategory`). When the bridge cannot resolve a tier — because the system has no catalogue product or no primary mapping — it returns `REQUIRES_CONTEXT`, which routes into the context-question gate below.
- Classification snapshots are versioned (`Classification.version`/`is_current`). Overrides are tracked with the proposed tier, override tier, justification, and actor in both the `Classification` row and an `AuditEvent`.

### EU AI Act classification — context-question gate (gate 2)
- For use cases the bridge cannot resolve (`REQUIRES_CONTEXT`), a versioned decision tree (`DecisionTree`/`DecisionTreeQuestion`/`DecisionTreeOption` — global, no RLS) drives a question-and-answer resolution, seeded from YAML (Art. 5 / Annex III / Art. 50; 17 questions, 34 options as of the current seed) via a version-aware loader that hashes content and fails loud on mutation of a frozen version.
- `GET /v1/use-cases/{id}/classification/context` — residual question set (unanswered questions) + the current snapshot. Open to all five governance roles.
- `POST .../classification/context/preview` — resolves supplied answers without persisting (pure read, `eu_tier` untouched). Open to all five governance roles.
- `POST .../classification/context` — submits answers, resolves, writes a **`PENDING_REVIEW`** `Classification` snapshot (does **not** stamp `use_case.eu_tier` yet). Gated to `system_owner`/`contributor`; overriding to a tier different from the computed one additionally requires `system_owner`.
- `POST .../classification/sign-off` — Reviewer-gated; flips the pending snapshot to **`APPROVED`** and stamps `use_case.eu_tier` — the act that makes a classification authoritative. Stages `classification.signed_off`.
- Resolution is deterministic and fail-closed: `resolve_context_classification()` applies a `PROHIBITED > HIGH > LIMITED > MINIMAL` precedence ladder; unanswered questions → `UNRESOLVED` (no write); `PROHIBITED` short-circuits to `PROHIBITED_HALT` immediately; `MINIMAL` is only ever an affirmative determination (all questions answered, nothing higher asserted) — never a fallback default.

### AI System Impact Assessment (AIIA) — core
- `POST /v1/use-cases/{id}/assessments` creates the AIIA. Reads only the use case's **current `Classification` snapshot** for the effective tier (never calls `resolve_classification()`/`snapshot_classification()`); rejects `PROHIBITED` and `REQUIRES_CONTEXT` (409), and a use case with no current snapshot at all (409). One current AIIA per use case (app-level pre-check + DB partial unique index `uq_one_aiia_per_use_case`).
- Creation pre-fills three ways in one transaction: (1) required sections from the tier-scoped `assessment_section_template` instantiated as blank `CATALOGUE_CURATED` items; (2) register facts (system name, use case purpose, resolved operator-role/hosting-model/usage-context/human-oversight-type labels) snapshotted as `USER_PROVIDED` items with `source_ref` pointing at the origin — point-in-time, since the register is mutable-in-place; (3) identity-only risk proposals (`AI_SUGGESTED`, never scores) via `propose_risk_set()`. An empty section template for a resolvable tier is a loud failure (500), not an empty shell.
- `GET /v1/assessments/{id}/sections` — the tier's required/recommended/N-A section template, joined against which sections already have items. `POST /v1/assessments/{id}/items {section_key}` instantiates a (typically recommended) section on demand.
- `PATCH .../items/{item_id}` amends authoring fields (`response`, `likelihood`, `severity`, `residual_likelihood`, `residual_severity`, `mitigation_plan`); `POST .../items/{item_id}/confirm` accepts a proposed risk as-is. Both are **single conditional `UPDATE`s** (never read-then-write) guarded by `lock_version`/`If-Match`: a lock mismatch is `412`, an invalid state transition is `409`. A still-`AI_SUGGESTED` item rejects an authoring-only PATCH (409 — confirm or amend first). A content-less PATCH is a silent no-op (no event, no provenance change).
- `POST/DELETE .../items/{item_id}/control-links` — link an item to a control with a `CoverageStatus`; duplicate link is 409.
- `DELETE /v1/assessments/{id}` is **pristine-only**: blocked (409) if any item has been confirmed/amended (vs. system-snapshotted facts, which don't count), any control link exists, or any feeder exists. A worked assessment must be voided instead (not yet built — see §5).
- Provenance (`AI_SUGGESTED`/`CATALOGUE_CURATED`/`USER_PROVIDED`/`USER_CONFIRMED`/`USER_AMENDED`) is always server-derived — no endpoint accepts it as input.
- Gate: create/delete `system_owner` only; item/link writes `{system_owner, contributor}`; reads any of the five governance roles. Reference reads (`GET /v1/reference/risks`, `/controls`, filterable by layer/framework) are member-level, unlike the anonymous wizard reference reads.

### AIIA Feeders (FRIA / DPIA / MODEL_RISK)
- `POST /v1/assessments/{aiia_id}/feeders {type}` creates a feeder — itself an `Assessment` row with `parent_aiia_id` set, reusing all AIIA item/control/provenance/concurrency/audit machinery unchanged. `type=AIIA` is rejected (422); a feeder cannot parent a feeder (422); at most one feeder per type per AIIA (`uq_feeder_type_per_aiia`, 409 on duplicate).
- Scope (`tier_snapshot`/`classification_version`) is **copied from the parent AIIA at creation and never re-resolved** — parent and feeder always agree on scope.
- Register pre-fill on creation: FRIA from `system_affected_party` → `affected_party` labels; DPIA from `system_data_category` → `data_category` labels; MODEL_RISK from system/product/hosting-model facts — all `USER_PROVIDED`, resolved-label snapshots, same as AIIA's own pre-fill. Empty junctions pre-fill nothing (valid; the section stays for manual authoring).
- `propose_risk_set()` is layer-aware by assessment type: AIIA gets governance-layer (NIST/ISO) library risks + `CatalogueProductRisk`; MODEL_RISK gets technical-layer (OWASP LLM Top 10) risks; FRIA/DPIA propose nothing (human-identified via their own sections).
- `GET /v1/assessments/{aiia_id}` assembles, read-time only, native AIIA items **plus** feeder items whose section maps (via `assessment_section_template.aiia_target_section_key`) into an AIIA section — surfaced items are tagged `source_assessment_id`/`source_type` and re-keyed to the AIIA's section, with provenance/`created_by`/control links travelling untouched. Nothing is copied or written back; editing/deleting a feeder item changes what's surfaced, no sync step. Feeder-private sections (no target) never surface in the AIIA — only in `GET /v1/assessments/{feeder_id}`.
- `GET /v1/assessments/{aiia_id}/feeder-recommendations` — strong default + shown reasoning per type (`required`/`recommended`/`not_applicable` + `basis` + `exists`): FRIA required at `HIGH` tier with a `deployer` operator role; DPIA required at `HIGH` tier with `is_special_category` data present, else recommended whenever any data category is present; MODEL_RISK always recommended.
- Feeder delete reuses the AIIA's pristine-delete path unchanged; parent-AIIA delete cascades to its feeders at the DB level (`parent_aiia_id ON DELETE CASCADE`, `passive_deletes=True` on the ORM relationship so the cascade isn't masked when the relationship is loaded in-session).

### Evidence repository
- `POST /v1/evidence` (multipart) uploads a file: server-computed `sha256` over a two-pass local spool (hash, then `seek(0)`, then S3 `put_object` — never a tee through boto3's multipart reader), tenant-prefixed key `{tenant_id}/evidence/{id}`, SSE applied by policy. The S3 put runs with **no DB transaction or connection held** — `upload_evidence` opens its own short, standalone session (`evidence_service.SessionLocal`, not `Depends(get_tenant_db)`) before the put (governance-role pre-check) and another after it (row + `evidence.created` audit insert); a commit failure on the second compensates the S3 object (delete by version-or-key) before re-raising.
- `GET /v1/evidence` — cursor-paginated repository listing, each row carrying `link_count` (correlated subquery against `assessment_item_evidence`); no presigned URLs in the list. `GET /v1/evidence/{id}` — metadata plus a short-TTL presigned download URL, hardened: forced `Content-Disposition: attachment`, content-type neutralised to `application/octet-stream` for anything off a small safe allow-list (closes the inline-render XSS path an unlisted `text/html`/`image/svg+xml` would otherwise open), signed against a **public** S3 endpoint distinct from the internal one the put uses (`s3_public_endpoint_url`). Issuing the URL stages `evidence.access` — a download is a custody event, not a silent read.
- `DELETE /v1/evidence/{id}` is a **single guarded statement** (`DELETE ... WHERE id = :id AND NOT EXISTS (SELECT 1 FROM assessment_item_evidence WHERE evidence_id = :id)`), not check-then-delete — the junction's `ON DELETE CASCADE` means a concurrent link insert between a separate `SELECT count` and a `DELETE` would be silently stripped. Zero rows affected is `409`, whether the row is linked or simply doesn't exist (the single statement can't distinguish, by design).
- `POST/DELETE /v1/assessments/{aid}/items/{item_id}/evidence-links` link/unlink existing evidence to an item, reusably across items and assessments. **Disposition-gated**, deliberately asymmetric with control-links: linking onto a still-`AI_SUGGESTED` item is `409` (confirm or amend first); every other provenance (`CATALOGUE_CURATED`, `USER_PROVIDED`, `USER_CONFIRMED`, `USER_AMENDED`) is allowed. Duplicate link is `409` (`UNIQUE(item_id, evidence_id)`); a cross-tenant `evidence_id` fails closed (`404`). Unlink is **idempotent**: a no-op removal (link already absent) returns `204` and writes no `AuditEvent`; a real removal stages `evidence.unlinked`.
- Evidence → control is **transitive via items only** — there is no direct evidence↔control table. Evidence sits outside the §1.5 provenance machine (no `ProvenanceConfidence` tag): it's a user-origin artifact, not a system-asserted default.
- The AIIA/feeder **pristine-delete predicate** (`_is_pristine` in `assessment_service.py`) is extended to also block when any item carries an evidence link, same shape as the existing control-link guard. `assemble_aiia_items` needed no change for feeder propagation — evidence links travel with the item by id, exactly like control links, since neither is embedded in the `AssessmentItemRead` schema; both are queried separately by `item_id`, which never changes when a feeder item surfaces into the AIIA read.
- No new DB role: all evidence work runs on `irontrustai_app` (`NOBYPASSRLS`), under RLS, same as every other tenant table.
- Gate: upload/delete/link/unlink → `{system_owner, contributor}` (evidence provision is a 1st-line act); list/detail reads → all five governance roles (the auditor consumes evidence read-only).

### Product lifecycle, gates & approvals
- The use-case lifecycle (`requested → vendor_check → product_check → intake → under_assessment → treatment_pending → pending_authorisation → authorised`, plus terminal `halted_prohibited` and regression `held`; `deployed`/`retired` still reserved, unwired) is now a determinate, fully-driven state machine — Sprint 4's model-only seam (`LifecycleState`, `LifecycleTransition`) is wired end to end. `apply_transition()` (`app/services/lifecycle_service.py`) is the **sole** writer of `use_case.state`: a single conditional `UPDATE … WHERE state=:from` (zero rows → `409`), enum bound through the typed column (by *member name* — confirmed off the live DDL, never `.value`), stages `LifecycleTransition` + `AuditEvent` atomically.
- Six gate predicates (`app/services/lifecycle_gates.py`) are pure reads returning `GateResult{verdict, reason_code, reason, responsible_party}`: `vendor_gate`/`product_gate` (tenant-scoped `VendorApproval`/`ProductApproval`, auto-pass when the system has no catalogue link), `classification_readiness` (prohibition off the current snapshot's `tier`, assessable-readiness off `use_case.eu_tier` — the single readiness definition, also consumed by `create_aiia`), `assessment_gate` = `structural_assessment_readiness()` (current AIIA exists, required feeders present, no still-`AI_SUGGESTED` items) **AND** `assessment_approved()` (current AIIA's `status == APPROVED` — Sprint 6a; a human-act term, never auto-satisfied), `treatment_gate` (every dispositioned risk item carries a substantiated `treatment_decision`), `authorisation_gate` (Sprint 6b — see its own subsection below).
- `advance_use_case()` is the auto-advance driver, wired into the same transaction as every classification write (`snapshot_classification`, `compute_and_record_classification`, `sign_off_classification`) and item disposition/treatment writes (`confirm_item`, the treatment branch of `amend_item`): step 0 checks the current classification snapshot for `PROHIBITED` (forces `halted_prohibited` from any non-terminal state, including the context path where `eu_tier` is never stamped `PROHIBITED`, and including `authorised` — Sprint 6b, inv 33), then advances one gate at a time until the first park, the `pending_authorisation` ceiling, or a halt. `_GATE_FNS`/`_ADVANCE_TABLE` deliberately have no entry past `pending_authorisation` — `authorisation_gate` is evaluated only by `full_vector()` (below), never by this walk, so a cycle-matching ATO can never auto-advance a use case into `authorised` (inv 35; see the Sprint 6b subsection for why this split exists).
- `full_vector()` recomputes every gate in canonical order (never cached) — Sprint 6b appends `authorisation_gate` as an explicit 6th entry after the 5-state loop, not through `_GATE_FNS` (see above). `re_evaluate()` (the manual lever, `POST /v1/use-cases/{id}/lifecycle/re-evaluate`, `system_owner`-gated) moves a use case to the full vector's target — advancing, un-holding (restoring to the **earliest** still-unsatisfied gate, not a forward jump from `held_from_state`, and never to `authorised` — `_target_from_vector` cannot produce it), or regressing an already-advanced use case to `held` when an upstream approval has since lapsed (no scheduler — caught lazily on the next consequential read/write). An `authorised` use case is special-cased explicitly (Sprint 6b): a no-op if the full 6-entry vector still all-advances, otherwise one direct regression to `held` — the generic rank-comparison branch cannot handle it (`authorised` outranks every vector-targetable state, so it would regress unconditionally without the special case). `GET /v1/use-cases/{id}/lifecycle` recomputes and shows the vector; it never persists.
- `PUT /v1/vendors/{id}/approval` / `PUT /v1/products/{id}/approval` (`authoriser`-gated) set/update the tenant's clearance (no delete — withdrawal is a status change) and fan out to every affected use case as **one idempotent transaction per use case** — each opens its own short-lived session against the RLS-bound `irontrustai_app` role and must `set_config('app.current_tenant', …)` itself (no FastAPI dependency chain there). The approval write commits explicitly, *before* the fan-out runs, so the fan-out's independent sessions read a durable row rather than racing the request's own end-of-handler commit.
- `GET /v1/systems/{id}/rollup` / `GET /v1/portfolio` (any governance role) — use cases + states + highest tier present + outstanding obligations per system; highest tier is a Python `max` over a precedence ladder, never SQL on the enum.
- Treatment fields (`treatment_decision` — `MITIGATE`/`ACCEPT`, `TRANSFER`/`AVOID` reserved; `treatment_rationale`) are written through `amend_item`, **provenance-neutral** — the write never enters the `CATALOGUE_CURATED → USER_PROVIDED` branch authoring-field changes do, so it cannot pollute the override-rate metric. Still disposition-gated (`409` on a still-`AI_SUGGESTED` item).
- No new DB role; all four touched tables (`use_case`, `vendor_approval`, `product_approval`, `assessment_item`) already carried RLS from earlier sprints, so the migrations were column-only.

### AIIA review & sign-off (Sprint 6a)
- `Assessment` status lifecycle, driven: `DRAFT → IN_REVIEW → APPROVED`, re-open `APPROVED → NEEDS_REFRESH`, bounce `IN_REVIEW → DRAFT` (changes requested). `Assessment.submission_round` (int, default 0) increments on every submit — the cycle key `authorisation_gate` (Sprint 6b, below) matches against; `Assessment.submitted_by_user_id`/`submitted_at` stamp the submitter.
- `AssessmentReview` (`app/models/assessment.py`) — tenant-scoped, RLS, one row per review decision: `reviewer_user_id`, `decision` (`ReviewDecision`: `APPROVED`/`CHANGES_REQUESTED`, uppercase Postgres labels confirmed off live DDL), `note` (DB `CHECK` requires non-null when `CHANGES_REQUESTED`), `submission_round`. Plain `Base`, not `TimestampMixin` — rows are never mutated after insert, only `created_at` is meaningful (mirrors `AuditEvent`'s append-only shape, though this table has no DB-level immutability trigger).
- `app/services/assessment_review_service.py` — tenant-plane, no external call, same shape as `assessment_service.py` (stage rows + `AuditEvent`, single `db.flush()`, no mid-request commit): `submit_for_review` (`system_owner`; pre-check `structural_assessment_readiness()` AND `treatment_gate()`, both must advance or `409`; `{DRAFT,NEEDS_REFRESH} → IN_REVIEW`), `record_review` (`reviewer`; act-SoD via `assert_distinct_workflow_actor`; `APPROVED` → `APPROVED` + same-transaction `advance_use_case()`; `CHANGES_REQUESTED` → `DRAFT`, no advance), `reopen` (`system_owner`; `APPROVED → NEEDS_REFRESH`, no advance/regression call — caught lazily by the next `re_evaluate`/consequential write), `list_review_queue` (`reviewer`; `status=IN_REVIEW AND submitted_by != caller`, AIIAs only).
- Every status write is a single conditional `UPDATE … WHERE id=:id AND tenant_id=:tid AND lock_version=:expected AND status IN (:from...)`; a zero-row update is disambiguated by re-reading the row — changed `lock_version` is `412`, unchanged `lock_version` with a status outside the allowed set is `409`.
- Act-level SoD (`assert_distinct_workflow_actor`, `app/services/governance.py`, alongside `assert_governance_assignable`) is a **second, distinct SoD locus** keyed on `user_id` (not `membership_id`): `reviewer ≠ submitted_by`. See revised invariant 7.
- Authoring lock (`_assert_authoring_unlocked`, `assessment_service.py`): every item-mutation entry point (`amend_item`, `confirm_item`, `create_item_from_section`, `create_control_link`, `create_evidence_link`) `409`s while the **AIIA** (resolved via `parent_aiia_id` for a feeder item, so the lock reaches feeder items too) is `IN_REVIEW`/`APPROVED`. A feeder's own `status` column stays `DRAFT` throughout 6a — only the AIIA enters the review workflow.
- Pristine-delete (`_is_pristine`) is now status-and-history-aware: not pristine if `status != DRAFT`, or if any `AssessmentReview` row references the assessment — on top of the existing item/control-link/evidence-link/feeder checks.
- Endpoints (`app/routers/v1/assessments.py`): `POST /v1/assessments/{id}/submit` (`system_owner`, `If-Match`), `POST /v1/assessments/{id}/review {decision, note}` (`reviewer`, `If-Match`), `POST /v1/assessments/{id}/reopen` (`system_owner`, `If-Match`), `GET /v1/assessments/review-queue` (`reviewer`) — submitter identity resolved by joining `Membership → User`, never bare `app_user` (inv 2, extended by inv 34).
- Audit actions: `assessment.submitted`, `assessment.review_recorded`, `assessment.reopened`, `assessment.needs_refresh`.

### Deployment authorisation / ATO (Sprint 6b)
- `DeploymentAuthorisation` (`app/models/lifecycle.py`) — tenant-scoped, RLS, the ATO: `use_case_id`, `assessment_id` (FK→`assessment`, `RESTRICT`), `submission_round` (the cycle key — D11), `tier` (text-stamped, **not** the `EUAIActTier` enum FK, deliberately decoupled from the live type), `assessment_version`, `authorised_by_user_id` (FK, `RESTRICT`) plus `authorised_by_name`/`authorised_by_email` (text, stamped — D13 durable attribution), `authorised_at`, `residual_risk_statement` (not null). Plain `Base`, point-in-time and never mutated — re-authorisation always writes a **new** row; multiple rows may exist per use case (one per authorised cycle).
- `authorisation_gate` (`app/services/lifecycle_gates.py`) = `assessment_approved()` **AND** a `DeploymentAuthorisation` row whose `submission_round` equals the current AIIA's `submission_round` — existence alone is **not** sufficient (inv 37); a stale ATO from a prior cycle parks the gate.
- `app/services/authorisation_service.py` — `authorise_use_case` (`authoriser`-gated; tenant-plane, no external call, one transaction): recomputes `full_vector()`, rejects `409` unless `use_case.state == pending_authorisation` and every gate below authorisation currently advances; act-SoD via `assert_distinct_workflow_actor` (`authoriser ∉ {approved_by_user_id, submitted_by_user_id}` off the current AIIA, reusing 6a's predicate unchanged); inserts the ATO (identity resolved via `Membership → User`, never bare `app_user`); `apply_transition(pending_authorisation → authorised)` via a new `"authorise"` event (inv 24) — emits `lifecycle.authorised` automatically; the ATO write is separately staged as `authorisation.granted`.
- **`authorised` is entered only by `authorise_use_case`** (inv 35) — `advance_use_case`'s gate-driving dict (`_GATE_FNS`/`_ADVANCE_TABLE`) has no entry past `pending_authorisation`, so a cycle-matching ATO existing is never sufficient on its own to cross into `authorised`; only the explicit human act does. `re_evaluate` mirrors this: it may hold an `authorised` use case in place (no-op, vector still all-advances) or regress it to `held` (something lapsed), but its `HELD`-restore branch can only ever target a vector-guarded state, never `authorised` — so a regressed-then-upstream-restored use case lands at `pending_authorisation` and waits for the authoriser to re-confirm, even when the existing ATO still cycle-matches.
- **Prohibited is supreme even from `authorised`** (inv 33): `apply_transition`'s `"halt"` legality check is state-agnostic (`from_state not in _TERMINAL_STATES`), so `(authorised, halt, halted_prohibited)` was already legal with no code change — `advance_use_case`'s step-0 PROHIBITED check runs regardless of starting state. Defensive: no reclassification path can run post-authorisation yet (§5), but the rule holds the moment one does.
- Pristine-delete (`_is_pristine`) also blocks when any `DeploymentAuthorisation` row references the assessment, independent of (but redundant with, in practice) the 6a `AssessmentReview` check — an assessment can only reach `assessment_approved()` (required for authorisation) by first acquiring a review row.
- Endpoints (`app/routers/v1/lifecycle.py`, same router as `/lifecycle`/`/lifecycle/re-evaluate`): `POST /v1/use-cases/{id}/authorise {residual_risk_statement}` (`authoriser`) → the ATO; `GET /v1/use-cases/{id}/authorisation` (any governance role) → the most recent ATO **plus a computed `live_state`** (inv 32, NB4) read fresh off `use_case.state` — an ATO's existence is never read as "currently authorised"; `404` if the use case has never been authorised.
- Audit actions: `authorisation.granted`, `lifecycle.authorised`.
- `deployed`/`retired` remain reserved and unwired (§5) — out of this sprint's scope by design (PRD §3.2).

### Member management
- A tenant admin creates members via a single endpoint: Cognito invite + `Membership(UserRole.MEMBER, zero governance roles)` created atomically in a service-owned transaction with Cognito compensation on failure.
- Member listing is driven from `membership` (RLS-scoped), joined to `app_user`, with Cognito-derived accept status (`pending` / `accepted`). Never queried bare from `app_user`.

### Governance role management
- Full assignment lifecycle: assign, revoke, list by tenant, list by member. SoD enforced at assignment via `assert_governance_assignable()`.
- Read-only catalogue endpoint returns all five roles and the full conflict matrix.

### Reference data (read-only, cross-tenant)
- Product category hierarchy, vendors and products by category, EU AI Act subcategory list. All global; no tenant scoping; anonymous (`get_db`, no auth) since they back the public-ish wizard flow.
- `GET /v1/reference/products/{id}` returns product detail for the intake wizard: vendor, product category tags, and mapped EU AI Act subcategories.
- `GET /v1/reference/risks` (filter: `layer`) and `GET /v1/reference/controls` (filter: `framework`) — **member-level auth required** (`get_tenant_db` + `require_role`), unlike the wizard reads above; these back AIIA item authoring.
- Six controlled-vocabulary tables seeded by migration (all global, no RLS): `eu_operator_role` (EU AI Act Art. 3 postures: provider, deployer, importer, distributor), `hosting_model`, `usage_context`, `human_oversight_type` (EU AI Act Art. 14), `data_category` (GDPR/EU AI Act special categories flagged via `is_special_category`), `affected_party` (EU AI Act Art. 27 vulnerable groups flagged via `is_vulnerable_group`). Named `eu_operator_role` to avoid collision with the platform RBAC `operator_role` join table.
- Also seeded: control library (ISO 42001 / EU AI Act with cross-map), risk library (OWASP LLM Top 10 technical layer + NIST/ISO governance layer with risk-to-control links), EU AI Act taxonomy (categories, subcategories, tiers, legal refs), product category taxonomy, governance role catalogue, decision tree (context-question gate), and the AIIA/feeder section template (`data/seed/aiia_section_template.yaml`).

### Platform (operator-facing)
- Tenant provisioning: creates tenant + owner in Cognito and DB, orphan-free.
- Tenant listing and operator identity endpoints.

### Audit trail
- **Tenant plane** (`AuditEvent`): append-only, RLS-scoped. Postgres trigger enforces immutability at the DB level. Action strings in use: `system.created`/`updated`, `classification.created`/`overridden`/`signed_off`, `governance_role.granted`/`revoked`, `member.created`, `assessment.created`/`deleted`/`feeder_created`, `assessment_item.created`/`amended`/`confirmed`/`deleted`/`treatment_set`, `control_link.created`/`deleted`, `evidence.created`/`deleted`/`access`/`linked`/`unlinked`, `lifecycle.advanced`/`held`/`halted_prohibited`/`authorised`, `vendor_approval.set`/`updated`, `product_approval.set`/`updated`, `assessment.submitted`/`review_recorded`/`reopened`/`needs_refresh` (Sprint 6a), `authorisation.granted` (Sprint 6b).
- **`AuditEvent` stores only `actor_user_id`** (FK → `app_user`, `ondelete=RESTRICT`) — no actor name/email snapshot at write time. A deleted user is blocked by the FK, but an *anonymized* user (fields wiped, row kept) makes old audit rows unattributable. Flagged during the evidence sprint as a pre-existing cross-cutting gap; not fixed (beyond one sprint's scope) — see §5.
- **Platform plane** (`PlatformAuditEvent`): operator-attributed. Used by tenant provisioning.

---

## 4. Established patterns

### Adding a tenant endpoint
1. Router in `app/routers/v1/`; registered in `app/main.py` under `/v1`.
2. Gate with `get_tenant_db` plus either `require_role(...)` or `require_governance_role(...)` — not both.
3. `tenant_id` is always `ctx.tenant_id`, never a request body field.
4. API schemas live in `app/schemas/`, separate from ORM models.

### Services that call external systems (Cognito or otherwise)
Such a service owns its own DB session and must follow this ordering:
```
1. Pre-check in DB  (fail fast before any external call)
2. Optional DB inserts + flush  (uncommitted)
3. External call  → failure → rollback; nothing persisted
4. DB inserts that depend on the external result
5. Stage AuditEvent
6. Commit  → failure → best-effort compensate external; re-raise
```
This pattern is implemented in `provision_tenant` and `provision_member`. Shared Cognito helpers (`create_cognito_user`, `delete_cognito_user`, `get_cognito_user_status`) live in `app/services/cognito_helpers.py`. Reuse them; do not duplicate.

### Tenant-plane services with no external call
Simpler than the above: pre-check in DB, stage the business-row writes and the `AuditEvent` in the same session, `db.flush()`. No ordering choreography needed — `get_tenant_db` commits the whole request atomically. This is the pattern for `assessment_service.py` (AIIA/feeder creation and mutation) and the context-classification service — neither calls out to Cognito or any other external system.

### A third shape: an external call that must NOT hold a transaction open
Cognito's choreography (above) deliberately holds one transaction open across the external call so it can compensate on commit failure. `evidence_service.upload_evidence` is the opposite: S3 puts can run up to the upload size cap, so no DB connection may be held idle for that long. The route doesn't depend on `get_tenant_db` at all (that dependency, once injected, holds a connection for the whole request) — it depends only on `get_tenant_context` (no session) and the service opens two independent short sessions of its own (`SessionLocal`, not `Depends`): one before the put (role pre-check), one after (row + audit insert), with the put itself running in between holding neither. Use this shape for any future upload/slow-external-call path; do not bolt it onto the Cognito ordering above.

### Auditing
- **Tenant plane**: add an `AuditEvent` to the session and commit it atomically with the business rows. Never commit audit separately.
- **Platform plane**: use `record_platform_event()` from `app/services/audit.py`.
- Action strings follow an `entity.verb` convention — see §3's Audit trail subsection for the current set in use.

### Classification read / write separation
`resolve_classification()` (bridge) and `resolve_context_classification()` (decision tree) are pure reads, safe to call multiple times. `snapshot_classification()` and `compute_and_record_classification()` write; the caller owns the transaction. `sign_off_classification()` is the only thing that stamps `use_case.eu_tier` for the context-gate path. Always keep resolution and persistence separate — and never re-enter either resolver from AIIA/feeder code, which reads only the persisted current snapshot.

### Optimistic concurrency (`lock_version` / `If-Match`)
Introduced for AIIA items: every mutating endpoint that changes a provenance-bearing row takes an `If-Match` header carrying the expected `lock_version`, and the mutation is a single conditional `UPDATE ... WHERE id = :id AND lock_version = :expected [AND <from-state guard>]`. Zero rows updated because of a stale lock is `412`; zero rows updated because the row wasn't in a valid from-state is `409` — these are deliberately distinguishable. Never read-then-write for a provenance transition; the from-state check must live in the `UPDATE`'s `WHERE` clause, not in application code after a separate `SELECT`.

### Read-time reference propagation (not copy)
Feeders surface into their parent AIIA by assembling a view at read time (`assemble_aiia_items`) — never by writing a copy into the AIIA or syncing on edit. If a future feature needs one entity's content to appear inside another's read response, prefer this shape (join at read time, tag the source) over duplicating rows.

### Provenance (§1.5 pattern)
Every system-proposed or system-derived value carries a `ProvenanceConfidence` tag: `AI_SUGGESTED`, `CATALOGUE_CURATED`, `USER_PROVIDED`, `USER_CONFIRMED`, or `USER_AMENDED`. `USER_PROVIDED` means user-origin content with no system default behind it (a from-scratch answer, or a snapshotted register fact) — distinct from `USER_CONFIRMED`/`USER_AMENDED`, which mean a system default was accepted or changed. Provenance is always server-derived, never accepted as request input. On `AssessmentItem`, a still-`AI_SUGGESTED` item must be confirmed or amended before its authoring fields can be written (disposition-before-authoring) — section-prompt items (`CATALOGUE_CURATED`) are exempt, since answering them isn't "overriding a default."

### Live-smoke-test RLS-sensitive code against the real dev DB before trusting it
The test suite's DB (`irontrustai_test`) is built via `Base.metadata.create_all()` — no RLS, no triggers, no grants, and its enum types are generated fresh from the ORM declaration so they're always self-consistent by construction. None of that is true of a real migrated database, where enum labels and RLS policies come from hand-written migration history that can drift from the ORM's assumptions. A green test suite proves business logic; it proves **nothing** about RLS-scoped queries, `SET LOCAL`/`app.current_tenant` handling, or enum label case against the real schema. Before trusting new code that touches any of those (a new fan-out/background-session pattern, a new enum, a new RLS-scoped query path), run it once against the actual dev Postgres (`docker compose up -d`, `alembic upgrade head`) using the real `SessionLocal`/role, not just the test harness. This is how Sprint 5 caught both the `classification_status`/`eu_ai_act_tier` label bug (inv 23) and the mid-request-commit-resets-`SET LOCAL` bug (inv 27) — the 295-test suite was green the entire time either bug was live.

---

## 5. Deferred / not yet implemented

The following have model definitions or designed seams but no service or router code (or are explicitly out of this MVP's sequencing).

| Area | What exists | What's missing |
|---|---|---|
| **AIIA versioning / refresh-on-material-change** | `Assessment.version`/`is_current`, `tier_snapshot`/`classification_version` drift-detection fields | The re-run cycle itself: detecting a material change, re-snapshotting, flagging `needs_refresh` |
| **Worked-state void** | Review/sign-off built (Sprint 6a, §3); pristine-delete is status-and-history-aware | Pristine-delete is still the only removal path — a worked (reviewed/approved) assessment has no void/withdraw path at all today |
| **`deployed`/`retired` transitions** | Authorisation/ATO built through `authorised` (Sprint 6b, §3); `LifecycleState.DEPLOYED`/`RETIRED` members exist | No transition into either — `authorised` is the lifecycle's ceiling by design (PRD §3.2) |
| **Evidence assignment / reminders (EVD-3), freshness notifications (EVD-4)** | Repository + linking built; `Evidence.expires_at` column present, unused | Due-date assignment, scheduler, expiry/freshness notifications |
| **Evidence AV/malware scanning** | Proxied upload path (server-mediated, not presigned-PUT) | No interception; the proxy path is the marked future seam |
| **Evidence supersession / versioning chains, soft-void** | `s3_version_id` captured per upload | Bytes are immutable post-upload by design (re-evidencing is a new row); no chain/version-replace UX, no soft-void — pristine hard-delete is the only removal path |
| **Evidence Object Lock retention-application, per-tenant CMK** | Prod bucket created with Object Lock capability + governance mode (Terraform, WI-0) | Applying retention/legal-hold at the authorisation gate; one shared CMK + single region is the recorded MVP tradeoff, not yet revisited |
| **`AuditEvent` actor durability** | `actor_user_id` FK only (`ondelete=RESTRICT`); `DeploymentAuthorisation` is the one explicit exception — it stamps `authorised_by_name`/`email` as text at write time (Sprint 6b, D13), since the ATO is export-grade and must stay attributable even after a user is anonymized | `AuditEvent` itself, plus `AssessmentReview`/`submitted_by`/`approved_by`, still have no durable name/email snapshot — accepted gap (Sprint 6a design doc §11), deferred to this cross-cutting fix, not solved piecemeal — cross-cutting, beyond any one sprint |
| **Export / audit pack (EXP-1)** | Evidence presigned-download primitive exists (the eventual export consumer) | Not started; the feeder design reserves the seam (feeder-private sections must appear in an export even though they don't surface in the AIIA read) |
| **Member deactivation / resend invite** | — | Deferred follow-on; not designed yet |
| **AI-assisted drafting** | `ai_suggested_text` field on `AssessmentItem` | No generation or suggestion flows; all current `AI_SUGGESTED` proposals are deterministic catalogue/library lookups, not LLM-generated |
| **Per-object governance roles** | Nullable `scope_id` seam described | Not built; do not add it yet |
| **Multi-component MODEL_RISK (1..N per AIIA)** | `uq_feeder_type_per_aiia` scoped to allow this relaxation later | Only matters once the catalogue models multi-component products; MODEL_RISK is 0..1 today like FRIA/DPIA |
| **Cross-feeder risk dedup** | — | A risk proposed by both the AIIA and a feeder (or two feeders) surfaces twice, untouched; no merge logic exists or is planned for MVP |
| **`system.lifecycle_stage` enum binding bug** | Column + Postgres `system_lifecycle_stage` type both exist (migration `05ff13cdcdc3`) | The DB type was created with **lowercase** labels (`'development'`, …), but the ORM column has no `values_callable` — same as every other enum here, it writes by **member name** (`'DEVELOPMENT'`, uppercase). Setting `system.lifecycle_stage` and flushing will raise `invalid input value for enum system_lifecycle_stage`. Discovered while confirming invariant 23 against live DDL (Sprint 5 WI-9); the field is apparently never written today so it hasn't surfaced. Fix is a migration recreating the type with uppercase labels — out of this sprint's scope, flagging so the next touch doesn't assume it works |

---

## 6. Invariants future work must not break

1. **Plane separation.** Tenant and operator tokens must never satisfy each other's verifiers. Never share auth dependencies across planes.
2. **`app_user` reads are membership-driven.** Any user listing in a tenant context joins from `membership`; `app_user` is never queried bare.
3. **`tenant_id` from context, never body.** On every tenant-mutating endpoint, `tenant_id` is `ctx.tenant_id`.
4. **No `BYPASSRLS` for tenant-scoped work.** Tenant services run on the `irontrustai_app` role (`NOBYPASSRLS`).
5. **`AuditEvent` is append-only.** No UPDATE or DELETE at the application layer. The Postgres trigger is the backstop.
6. **Evidence bytes live in S3.** Postgres holds only the pointer (`s3_bucket`, `s3_key`, `s3_version_id`) and `sha256`. Never store file bytes in the DB.
7. **SoD checks go through exactly two sanctioned loci — never a third, inline check.** (Revised, Sprint 6a.) *Assignment-time* SoD — may this membership hold this governance role, given what it already holds? — goes through `assert_governance_assignable()` only. *Act-time* SoD — did one person perform two distinct workflow roles on the same object (e.g. review their own submission)? — goes through `assert_distinct_workflow_actor()` only, keyed on `user_id`, not `membership_id`. No inline conflict logic in handlers or services, for either kind.
8. **Operator permissions reach operators only through roles.** No direct operator → permission grants.
9. **Cognito is the uniqueness authority for email.** `app_user.email` is not DB-unique by design. Do not add a unique constraint without understanding what Cognito's uniqueness enforcement implies.
10. **Classification tier is never asserted from catalogue facts alone.** Tier comes from deployment context (bridge or context-question gate), never the catalogue directly. The catalogue informs; it never decides.
11. **Classification resolution and persistence stay separate**, on both gates. `resolve_classification()`/`resolve_context_classification()` never write; `snapshot_classification()`/`compute_and_record_classification()`/`sign_off_classification()` own the transaction. AIIA/feeder creation reads only the current persisted snapshot and never re-enters either resolver.
12. **Context-gate resolution is fail-closed.** Unanswered questions → `UNRESOLVED`, no snapshot. `MINIMAL` is only ever reached affirmatively (everything answered, nothing higher asserted) — never a default or fallback.
13. **AIIA/feeder provenance is always server-derived.** No request schema accepts a `provenance` field. A still-`AI_SUGGESTED` item blocks authoring-field writes until confirmed or amended.
14. **Provenance transitions are single conditional `UPDATE`s.** Never read-then-write; the from-state guard lives in the `WHERE` clause so a stale read can't corrupt the audit diff. `412` (lock mismatch) and `409` (bad from-state) are deliberately distinguishable.
15. **A feeder's scope is copied from its parent AIIA at creation and never re-resolved.** Parent and feeder must always agree on `tier_snapshot`/`classification_version`.
16. **Feeder propagation into the AIIA is read-time reference only.** Never copy a feeder item into the AIIA, never write back. `assemble_aiia_items` is the single locus for this assembly.
17. **Pristine-delete only, for both AIIA and feeders.** A hard `DELETE` is permitted only with no confirmed/amended items, no control links, no evidence links, and (for an AIIA) no feeders. A worked assessment must be voided instead — not yet built (§5).
18. **No DB transaction or connection held across a slow external call that doesn't need one.** Evidence upload's S3 put runs with nothing open; the upload route does not depend on `get_tenant_db`. Contrast with Cognito provisioning (invariant: a transaction *is* held there, deliberately, to compensate on failure) — know which shape a new external-call path needs before writing it.
19. **Evidence pristine-delete is a single guarded statement, never check-then-delete.** The `assessment_item_evidence` junction's `ON DELETE CASCADE` makes a separate `SELECT count` then `DELETE` racy (a concurrent link insert between the two would be silently stripped); the `NOT EXISTS` guard must live in the same statement as the `DELETE`.
20. **Evidence-linking is disposition-gated; control-linking is not.** A still-`AI_SUGGESTED` item rejects an evidence link (substantiation belongs behind the same gate as authoring) but accepts a control link freely — a deliberate, documented asymmetry. Do not "fix" one to match the other without re-reading why.
21. **Evidence → control is transitive via items only.** Never add a direct evidence↔control table; framework satisfaction derives from the control-library cross-map via whichever item the evidence is linked to.
22. **Presigned evidence downloads are always hardened.** Forced `Content-Disposition: attachment`, content-type neutralised off a safe allow-list, signed against the public (not internal) S3 endpoint. Never serve evidence inline.
23. **Every by-name enum is stored by Postgres enum **member name**, not `.value`.** Confirmed directly off the DDL: `lifecycle_state`'s labels are `'REQUESTED'`, `'VENDOR_CHECK'`, … (uppercase), even though the Python `.value`s are lowercase. A raw `.value` bind in a hand-written `WHERE`/`UPDATE` will silently match zero rows. Always bind through the typed SQLAlchemy column (the ORM does this correctly); never construct a raw string comparison from `.value`. **Don't assume an enum type matches this convention without checking `pg_enum` directly** — `classification_status` (all four labels lowercase) and `eu_ai_act_tier.REQUIRES_CONTEXT` (lowercase, its four siblings uppercase) were found genuinely broken this way against the real migrated dev DB in Sprint 5 (the no-RLS test DB, which generates its schema fresh from the ORM, can never catch this class of bug — only checking the real DDL can); fixed via `alembic/versions/3a5b36bdd37a_fix_enum_label_case.py` (`ALTER TYPE … RENAME VALUE`, non-destructive). `system_lifecycle_stage` was fixed in the same migration as a precaution (unused by any code path today).
24. **`apply_transition` is the sole writer of `use_case.state`.** No other code path may construct an `UPDATE … SET state = …` against `use_case`, directly or via the ORM instance attribute outside this function.
25. **The full gate vector is source of truth; persisted `use_case.state` is a cursor.** No gating decision (advance, regress, an authorisation attempt) may read persisted `state` alone — recompute via `full_vector`/`re_evaluate` at every consequential read or write. A status `GET` shows the computed verdict and never persists it.
26. **Prohibited is terminal, supreme, and read off the current classification snapshot's `tier`, never `eu_tier`.** Fires from any non-terminal state, including `held` — `eu_tier` is never stamped `PROHIBITED` on the context-question path, so reading it instead would silently let a prohibited practice sit un-halted.
27. **A mid-request `db.commit()` resets `SET LOCAL`-scoped settings, including `app.current_tenant`.** `get_tenant_db` sets it once per request because it never commits until the request ends; `set_vendor_approval`/`set_product_approval` (Sprint 5) deliberately commit mid-request (so the approval fan-out's independent sessions read a durable row) and must immediately re-`set_config` afterward (`_set_tenant_context` in `lifecycle_service.py`), or every subsequent RLS-scoped query on that same session for the rest of the request silently returns zero rows. The no-RLS test DB cannot catch this class of bug at all — caught only by live-smoke-testing against the real RLS-enabled dev Postgres. Any future code that commits mid-request on an RLS-bound session must do the same.

Sprints 6a (review & sign-off) and 6b (deployment authorisation / ATO) add
invariants 28–37. Numbering follows the design doc (`docs/AUTORIZATION.md` §8).

28. **Act-level SoD is distinct from assignment SoD and lives only in `assert_distinct_workflow_actor()`** (sanctioned by revised inv 7): `reviewer ≠ submitted_by` (6a); `authoriser ∉ {approved_by, submitted_by}` (6b).
29. **Residual-risk acceptance is the authoriser's act.** `residual_risk_statement` is authored on the ATO by the authoriser at `authorise_use_case` time — never derived from or assignable to the reviewer's AIIA approval.
30. **Reviewer/authoriser gates are human-act gates, never auto-advanced.** `assessment_approved()` is satisfied only by `record_review(APPROVED)`; `authorisation_gate`'s human-act term is satisfied only by `authorise_use_case`. `advance_use_case`/`re_evaluate` never derive either.
31. **AIIA authoring is status-locked.** Item and feeder-item writes are rejected (`409`) while the parent AIIA is `IN_REVIEW` or `APPROVED`; a feeder item's lock is resolved through its parent via `parent_aiia_id`, since the feeder's own `status` never moves.
32. **The ATO is a point-in-time fact; deployment authority is the live vector.** A `DeploymentAuthorisation` row is never mutated; re-authorisation always writes a new row. Consumers read the computed `live_state` (`GET .../authorisation`), never infer "currently authorised" from a row's mere existence.
33. **`authorised` is not a safe harbour from prohibition.** `apply_transition`'s `"halt"` legality is state-agnostic (`from_state not in _TERMINAL_STATES`) and `advance_use_case`'s step-0 PROHIBITED check runs regardless of starting state — reclassification to `PROHIBITED` forces `halted_prohibited` directly from `authorised`, with no special-casing required.
34. **Actor-identity reads join via `membership`, never bare `app_user`** (inv 2, applied to the review queue, review history, and the ATO's authoriser identity).
35. **`authorised` is entered only by `authorise_use_case`.** `advance_use_case`'s gate-driving structures (`_GATE_FNS`/`_ADVANCE_TABLE`) have no entry past `pending_authorisation`, so a cycle-matching ATO is never sufficient on its own to cross into `authorised`. `re_evaluate` may hold an already-`authorised` use case in place (no-op, full vector still all-advances) or regress it to `held`, but its restore branch can only target a vector-guarded state — never `authorised` — so a regressed-then-restored use case always lands at `pending_authorisation` and waits for re-confirmation.
36. **Pristine-delete is status-and-history-aware.** Hard `DELETE` is blocked unless `status == DRAFT` **and** no `AssessmentReview`/`DeploymentAuthorisation` row references the assessment — on top of invariant 17's existing conditions.
37. **`authorisation_gate` matches by cycle.** It passes only when a `DeploymentAuthorisation`'s `submission_round` equals the assessment's current `submission_round` — existence alone is insufficient; a re-submitted cycle orphans the prior ATO.
