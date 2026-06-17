# AI System Impact Assessment (AIIA) — Backend Design Proposal (v2)

**Feature:** AIIA core (create, populate, structure), ISO/IEC 42005-aligned, EU AI Act tier-scoped
**Scope:** Additive feature on the existing multi-tenant governance platform — not a greenfield redesign
**Status:** v2.7 — all design decisions resolved (risk identity-only, feeder-private+export, join-table RLS parity, reference-FK hardening) and the schema migration drafted (`aiia_core_migration.py`). Model matched end-to-end against the live database; no open dependencies
**Out of scope this sprint:** evidence file upload (Sprint 4), status transitions / review / sign-off (Sprint 6), AI-assisted text drafting (post-MVP), AIIA versioning / refresh-on-material-change cycle (post-MVP — seams in place), the lifecycle orchestrator

**Decisions:** all resolved (§13); schema migration drafted (`aiia_core_migration.py`).

---

## 1. Overview

This sprint builds the full backend for creating, populating, and structuring an AIIA — one per use case — with FRIA, DPIA-style, and model/system-risk analyses as first-class feeder sections that push data into the AIIA rather than living as separate documents. The AIIA is scoped by the use case's EU AI Act tier so the assessment is proportionate and defensible.

The design leans on existing foundations: the tenant-endpoint contract, the tenant-plane atomic-audit rule, the §1.5 provenance model, read-only classification, and the seeded reference libraries. **The AIIA service makes no external-system calls** — it is pure DB plus read-only reference composition, so it follows the tenant-plane rule (stage the `AuditEvent` in the session, commit atomically with the business rows) and explicitly not the six-step Cognito ordering.

Work splits into **Phase A** (create and populate an AIIA — a demoable vertical slice) and **Phase B** (feeders and propagation). Concurrency protection and the delete/remediation path are pulled into Phase A as audit-integrity concerns (see §10).

### 1.1 Resolved design decisions

| Decision | Resolution |
| --- | --- |
| Feeder propagation | Reference, not copy — AIIA assembles feeder items at read time |
| Inherited register/classification facts | **Snapshot** into the AIIA at creation (point-in-time), tagged `USER_PROVIDED`; register is mutable-in-place so snapshot is the only point-in-time option. Snapshot **resolved labels** for FK dimensions, not just ids |
| Section template source | Seeded reference data, keyed by `(type, tier, section_key)` |
| Feeder cardinality | `UNIQUE (parent_aiia_id, type)`; MODEL_RISK is the only one that relaxes later |
| Feeder-private sections | `aiia_target_section_key = NULL` → surfaces in no AIIA section; export includes each feeder's own view |
| Feeder scoping | **Feeder inherits parent AIIA's `tier_snapshot` / `classification_version`** — never re-resolves |
| Risk proposal | **Identity only, not scores** — scores are human authoring fields |
| Provenance enum | `{AI_SUGGESTED, CATALOGUE_CURATED, USER_PROVIDED, USER_CONFIRMED, USER_AMENDED}` |
| Override metric | Measured over `AI_SUGGESTED`-origin (proposed-risk) items only |
| Confirm vs amend | Explicit confirm; server-derived provenance; disposition-before-authoring on proposed risks |
| Concurrency | Optimistic (`lock_version` / `If-Match`, 412) + conditional from-state update — **in Phase A** |
| Remediation | Hard delete only while pristine; worked-state void deferred to Sprint 6 |
| Governance role scope | Tenant-scoped (WKF-7); SoD enforced at assignment, not in these endpoints |
| Residual risk | Per-item `residual_likelihood` / `residual_severity`, nullable until a mitigation exists |
| AIIA versioning posture | **Version-ready now, versioning behaviour post-MVP** — `version` (run version) + `is_current` mirror `Classification`; one *current* AIIA per use case |
| One AIIA per use case | `uq_one_aiia_per_use_case` exists as `WHERE type = 'AIIA'`; evolves to `WHERE type = 'AIIA' AND is_current` |
| Join-table tenancy | **`tenant_id` + RLS added** to `assessment_item_control` / `assessment_item_evidence` (parity); item-first access as defense-in-depth |
| Reference-data FK hardening | `risk_id` (`SET NULL → RESTRICT`), `control_id` (`CASCADE → RESTRICT`) — library deletion can't orphan/strip assessment records |
| Tier source | AIIA reads the **current `Classification` snapshot** (override-aware effective `tier` + `version`); never calls `resolve_classification()` or `snapshot_classification()` |

---

## 2. Reused components (existing foundations)

- **Classification, read-only.** AIIA creation reads the use case's **current `Classification` snapshot** (`is_current=True`) — an ordinary RLS-scoped tenant read — for the override-aware effective `tier`, the `version` (→ `classification_version`), and the `rationale` / `basis_subcategory_code` / `basis_legal_ref` used in pre-fill. It calls **neither `resolve_classification()`** (which returns the bridge-derived *proposal*, is keyed by `system_id`, and is not override-aware) **nor `snapshot_classification()`**. The AIIA is a pure consumer of the classification *outcome*, not the classification machinery — so overrides flow through automatically (the snapshot's `tier` already reflects them) and the scoping is traceable to the exact decision via `classification_version`.
- **Reference data (cross-tenant, read-only).** Risk Library (OWASP LLM Top 10 + NIST/ISO governance layer, with risk-to-control links), control library (ISO 42001 / EU AI Act cross-map), EU AI Act taxonomy, `CatalogueProductRisk`. No tenant scoping, no RLS.
- **Provenance model and §1.5.** Reused and extended by one value (§4).
- **Tenant-endpoint contract.** Router in `app/routers/v1/`, registered under `/v1`; `get_tenant_db` plus exactly one of `require_role` / `require_governance_role`; `tenant_id` from `ctx.tenant_id`; schemas in `app/schemas/`.
- **Tenant audit plane.** All mutations stage an `AuditEvent` committed atomically with the rows; immutability trigger and RLS cover the new tables.
- **Governance role model (PRD §4.9).** Tenant-scoped; SoD is a conflict matrix at assignment (WKF-5/6). These endpoints consume roles for gating and carry no SoD logic of their own.

---

## 3. Data model

A **single polymorphic `Assessment` table** with a `type` discriminator — feeders share the AIIA's item/control/evidence structure.

**`Assessment`** *(table exists — annotations mark what's present vs what to ALTER)*
- `id`, `tenant_id`, `use_case_id` — present
- `type` — `assessment_type` enum (`AIIA | FRIA | DPIA | MODEL_RISK`). **The column is `type`, not `kind`** — adopt `type` throughout.
- `parent_aiia_id` — nullable self-FK (`ON DELETE CASCADE`); present. Deleting an AIIA cascades to its feeders at the DB level (the pristine-delete guard, §8.11, sits as policy on top).
- `status` — `assessment_status` enum; present (a real enum). Transitions still Sprint 6.
- `version` — integer, present. **The run version**, confirmed (mirrors `Classification.version`); `lock_version` (below) carries optimistic concurrency separately.
- `residual_risk_summary` — text, present. The assessment-level residual the authoriser accepts (Sprint 6); aggregates per-item residuals.
- `approved_by_user_id`, `approved_at` — present. Sprint 6 sign-off columns already exist.
- `created_at`, `updated_at` — present.
- **ALTERs the design needs (currently absent):**
  - `tier_snapshot` (`eu_ai_act_tier`) — the tier the assessment was scoped from. Without it the assessment can't record what it was assessed against (point-in-time + drift). **Load-bearing.**
  - `classification_version` (integer) — the drift key linking to the `Classification` version scoped from. **Load-bearing.**
  - `is_current` (boolean, default true) — required for version-readiness and to current-scope the unique index (§8.1).
  - `lock_version` (integer) — optimistic-concurrency token (§8.6), distinct from the run `version`.
  - `created_by` (uuid) — **add.** Explicit initiator attribution on the row (also recorded in the `assessment.created` AuditEvent, but denormalised here for direct queryability). Action-time SoD still keys off item authorship, not this.
- **Feeder note:** a feeder copies its parent's `tier_snapshot` / `classification_version` at creation (§9.1).

**`AssessmentItem`** *(table exists — annotations mark present vs ALTER)*
- `id`, `tenant_id`, `assessment_id` — present (FK → assessment, `ON DELETE CASCADE`)
- `risk_id` — present; nullable FK → `risk` library. **ALTER: `ON DELETE SET NULL → RESTRICT`** — SET NULL would orphan a still-`AI_SUGGESTED` item's only substance; RESTRICT blocks deleting a referenced library risk (deprecate via soft-flag instead). See §11.
- `prompt`, `response` — present (text, nullable)
- `likelihood`, `severity` — present, **integer** (this is the score scale). **Authoring fields — not proposed by the system** (§4).
- `mitigation_plan` — present (text)
- `provenance` — present (`provenance_confidence` enum); **server-derived only** (§4). *Enum extension: add `USER_PROVIDED` if the current type is the original four (`ALTER TYPE … ADD VALUE`).*
- `ai_suggested_text` — present, text. The post-MVP AI-drafting seam (AI-drafted response text); **null/unused this sprint** — consistent with `AI_SUGGESTED` meaning deterministic identity-only here.
- `created_at`, `updated_at` — present.
- **ALTERs the design needs (currently absent):**
  - `section_key` — **load-bearing.** The table is currently a flat item list; the whole tier-scoped section model (`GET /sections`, the template join, required/recommended instantiation, and feeder propagation via `section_key` → `aiia_target_section_key`) keys on this. Highest-priority add.
  - `residual_likelihood`, `residual_severity` (integer) — per-item residual; **nullable until a mitigation exists** (do not default to zero or to inherent).
  - `created_by` (uuid) — the action-time SoD seam (authoriser ∉ item authors, §8.12/§8.16). Creation only; amends are already in the audit events.
  - `selection_basis` (text) — for proposed-risk items, why the risk was proposed for this use case (shown reasoning; §4, review #10).
  - `source_ref` — origin pointer for snapshotted register facts (§5).
  - `lock_version` (integer) — optimistic-concurrency token (§8.6).

**`assessment_item_control`** (control-link join — exists)
- `id`, `item_id` (FK → assessment_item, `ON DELETE CASCADE`), `control_id` (FK → `control`)
- `coverage` — `coverage_status` enum (`open | partial | satisfied` *— confirm values*). **Column is `coverage`, not `coverage_status`.**
- **ALTER: add `tenant_id` + RLS** (parity decision — §13). Backfilled from the parent item; `ON DELETE CASCADE` to tenant; same `tenant_isolation` policy as `assessment_item`. Attribution stays in the `control_link.*` AuditEvents (no `created_by`/timestamps on the join).
- **ALTER: add `UNIQUE (item_id, control_id)`** — absent today, so duplicate links are possible; the §11 duplicate→409 depends on it. The link stores `control_id` + `coverage` only — framework satisfaction (ISO 42001 *and* EU AI Act) derives from the control library's cross-map.
- **ALTER: `control_id` FK `ON DELETE CASCADE → RESTRICT`** — CASCADE would silently delete coverage records when a library control is removed (loss of audit evidence); RESTRICT blocks deletion while referenced (§11).

**`assessment_item_evidence`** (item ↔ evidence M:N junction — exists)
- `id`, `item_id` (FK → assessment_item, `ON DELETE CASCADE`), `evidence_id` (FK → **`evidence`**, `ON DELETE CASCADE`)
- Evidence is a **first-class `evidence` table**, not a stub on the link — one evidence artifact can satisfy many items, and `label`/`uri`/file-backing live on `evidence` (upload/write path is Sprint 4; junction unused until then).
- **ALTER: add `tenant_id` + RLS** (parity decision — §13), backfilled from the parent item. *(Confirm `\d evidence` when Sprint 4 lands.)*

**`assessment_section_template`** (new — created by the migration; seeded reference data, global, no RLS) — unique `(type, tier, section_key)`:
- `applicability` — `section_applicability` enum (`required | recommended | not_applicable`) — new enum created by the migration
- `prompt` — default section prompt text
- `iso_42005_clause` — standard basis (shown reasoning)
- `aiia_target_section_key` — feeder rows only: the AIIA section under which this feeder section surfaces (`NULL` = feeder-private; §9.2)
- Row content (sections per tier, clauses, feeder→AIIA targets) is a **separate data-seeding migration**, not the schema migration.

---

## 4. Provenance, the confirm/amend model, and the override metric

`provenance` describes the origin/disposition of an item's substantive content. It is the spine of defensibility and the source of the override-rate signal, so its semantics are tight.

**Enum (five values):**

| Value | Meaning |
| --- | --- |
| `AI_SUGGESTED` | System-proposed risk, undispositioned. *Deterministic catalogue/library proposal — not LLM (text drafting is deferred).* |
| `CATALOGUE_CURATED` | Curated reference content (a section prompt), not yet answered/edited |
| `USER_PROVIDED` | User-origin content with no system default behind it — a section answer, a from-scratch item, or a snapshotted register fact |
| `USER_CONFIRMED` | User accepted a system-proposed default (a proposed risk) as-is |
| `USER_AMENDED` | User changed a system-proposed default (the proposed risk, or a curated prompt) |

**Invariant — provenance is server-derived, never client-set.** It must not appear in any request body. The tag is a consequence of which act was recorded, not a state the client claims; otherwise explicit confirmation is theatre.

**Proposed substance vs authoring fields.** For a proposed-risk item, the proposed substance is `risk_id` + its generated framing. Everything else — `response`, `likelihood`, `severity`, `mitigation_plan`, `residual_*` — is the user's to author. **The system does not propose scores** (deployment-context judgements it can't make at proposal time); proposing them would anchor the user and assert a default §1.5 can't defend.

**Disposition-before-authoring (proposed-risk items only).** A proposed risk must be confirmed or amended before authoring fields can be written to it. An authoring-only PATCH on a still-`AI_SUGGESTED` item is rejected (409 — "confirm or amend the proposed risk first"). This preserves explicit-confirm and lands every proposed item in a clean accepted/overridden/rejected state. Section-prompt items are not subject to this — you answer them, you don't confirm a question.

**Two separated, separately-audited acts:**
- **PATCH amends only.** A real content change → `assessment_item.amended` with field-level before/after. A content-less PATCH is a no-op (no event, no provenance change).
- **Confirm confirms only.** `POST …/items/{item_id}/confirm` → `USER_CONFIRMED` + `assessment_item.confirmed`. Valid only from `AI_SUGGESTED` (proposed risks).

**State machine:**

| From | confirm | amend (proposed substance) | author (response/scores/mitigation) |
| --- | --- | --- | --- |
| `AI_SUGGESTED` (proposed risk) | → `USER_CONFIRMED` | → `USER_AMENDED` | blocked until dispositioned |
| `CATALOGUE_CURATED` (section prompt) | n/a (409) | edit prompt → `USER_AMENDED` | answer → `USER_PROVIDED` |
| `USER_PROVIDED` | n/a (409) | stays `USER_PROVIDED` | stays `USER_PROVIDED` |
| `USER_CONFIRMED` | 409 | → `USER_AMENDED` | stays `USER_CONFIRMED` |
| `USER_AMENDED` | 409 | stays `USER_AMENDED` | stays `USER_AMENDED` |

**Concurrency on the transition (§8.6/§8.7).** Confirm and amend execute as conditional updates (`… WHERE provenance IN (valid_from_states) AND lock_version = :expected`) — 0 rows → 409/412. Never read-then-write, or the from-state guard is only advisory under race and the diff is computed against a stale read.

**Override metric (§7.1).** Computed over `AI_SUGGESTED`-origin items only: `(amended + deleted proposed risks) / (proposed risks)`. `USER_PROVIDED` and `CATALOGUE_CURATED` items never count — they had no proposed default to override. This is what makes the headline discovery signal mean what the PRD intends.

**Shown reasoning for risk selection (§1.5).** Each proposed risk carries `selection_basis` ("proposed because modality=image + tier=high"; "CatalogueProductRisk for product X") on the item, so the basis is interrogable in the UI, not just the risk's own source attribution.

---

## 5. Services

**`AssessmentService.create_aiia(...)`** — one tenant transaction, tenant-plane pattern (no external call):
1. Pre-check: use case in `ctx.tenant_id`; **read the current `Classification` snapshot** for the effective `tier` + `version` + `rationale`/basis; reject `PROHIBITED` (hard stop) and `REQUIRES_CONTEXT` (no tier → no template); if no current snapshot exists at all, block (same family as `REQUIRES_CONTEXT` — shouldn't occur given auto-resolve on use-case creation, but guard); rely on the partial unique index for duplicate-AIIA. Capture `tier_snapshot = Classification.tier` and `classification_version = Classification.version`.
2. **Assert the section template for `(AIIA, tier)` is non-empty** — an empty set is a seeding bug; fail loudly, do not create an empty shell.
3. Pre-fill, three distinct mechanisms:
   - *Sections*: instantiate items for **required** sections from the template (`CATALOGUE_CURATED`, response blank). Recommended sections are surfaced via `GET /sections` and instantiated on demand (§6).
   - *Inherited facts*: **snapshot** into the AIIA as `USER_PROVIDED` items with `source_ref` to the register — `system.name`, `use_case.purpose`, intake deployment context (`use_case.context_blob` + the system's structured dimensions `operator_role_id` / `hosting_model_id` / `usage_context_id` / `human_oversight_type_id`, plus `system.metadata_blob`). The register is mutable-in-place (no history), so snapshot is the only point-in-time option. For the structured FK dimensions, snapshot the **resolved label** (the operator-role/hosting-model/etc. name), not just the FK id — the referenced reference rows can be renamed/re-seeded and each FK is `ON DELETE SET NULL`, so freezing the label is what preserves the record; keep the id in `source_ref`.
   - *Risks*: `propose_risk_set(...)` → `AI_SUGGESTED` items, identity only, each with `selection_basis`.
4. Stage **one** `assessment.created` `AuditEvent` summarising the pre-fill (template version, proposed risk ids, counts). Per-item events begin when humans act.
5. Commit atomically.

**`propose_risk_set(tier, modality_tags, catalogue_product_id)`** — pure read composition over the Risk Library + `CatalogueProductRisk`, returning candidate risk *identities* + selection basis. Deterministic, isolated for testing.

**Feeder propagation (Phase B)** — reference model; AIIA assembles feeder items at read time (§9.2).

**Reference read services** for `/reference/risks` and `/reference/controls` — thin filtered projections.

---

## 6. API surface

All new endpoints are tenant endpoints. Assessment reads require a governance role; writes require a first-line authoring role; reference reads (global data) use member-level `require_role`. Mutating endpoints honour `If-Match` (§8.6).

| Endpoint | Purpose | Gate |
| --- | --- | --- |
| `POST /v1/use-cases/{id}/assessments` | create AIIA (initiation) | governance: **system_owner** |
| `DELETE /v1/assessments/{id}` | delete AIIA — **pristine only** (§8.11) | governance: **system_owner** |
| `GET /v1/use-cases/{id}/assessments` | list AIIA + feeders | governance: any of five |
| `GET /v1/assessments/{id}` | full detail (items, control links, evidence stubs, surfaced feeder items) | governance: any of five |
| `POST /v1/assessments/{id}/feeders` | create FRIA / DPIA / MODEL_RISK feeder (rejects `type=AIIA`, 422) | governance: **system_owner, contributor** |
| `DELETE /v1/assessments/{feeder_id}` | delete feeder — pristine only | governance: **system_owner, contributor** |
| `GET /v1/assessments/{id}/sections` | tier-based section template (required + recommended + N/A) | governance: any of five |
| `POST /v1/assessments/{id}/items` | create item (template `section_key` → instantiates that section's curated prompt) | governance: **system_owner, contributor** |
| `PATCH /v1/assessments/{id}/items/{item_id}` | amend item | governance: **system_owner, contributor** |
| `POST /v1/assessments/{id}/items/{item_id}/confirm` | confirm proposed risk as-is | governance: **system_owner, contributor** |
| `DELETE /v1/assessments/{id}/items/{item_id}` | delete item (audited cascade of control links) | governance: **system_owner, contributor** |
| `POST /v1/assessments/{id}/items/{item_id}/control-links` | link control | governance: **system_owner, contributor** |
| `DELETE /v1/assessments/{id}/items/{item_id}/control-links/{link_id}` | unlink control | governance: **system_owner, contributor** |
| `GET /v1/reference/risks` | reference risks (filter: layer, framework, tier) | **require_role** (member) |
| `GET /v1/reference/controls` | reference controls (filter: framework) | **require_role** (member) |

**Role notes.** Write set is `{system_owner, contributor}` only — reviewer/authoriser are second line and must not author what they later review; auditor is read-only. AIIA initiation and AIIA delete are reserved to `system_owner`. Roles are tenant-scoped (WKF-7), so the gate checks the caller's tenant role directly. **Admin is not a governance role and gets 403 on every assessment endpoint, reads included** — make the 403 name the missing role. Write the gate as "holds role X at a scope covering this object" so the later object-scoped extension is additive.

**Audit action strings (`entity.verb`).** `assessment.created`, `assessment.deleted`, `assessment.feeder_created`, `assessment_item.created`, `assessment_item.amended`, `assessment_item.confirmed`, `assessment_item.deleted`, `control_link.created`, `control_link.deleted`.

---

## 7. Architecture fit

Creation runs in one tenant transaction (§5), tenant-plane atomic-audit — no external call, no compensation, no separate audit commit.

**The classification gate stays a node, not a flow.** On `REQUIRES_CONTEXT` (read from the current snapshot) the endpoint refuses with a typed reason; it does not prompt for missing context — that routing is the (out-of-scope) orchestrator's job. The feature consumes the classification *outcome* (the persisted snapshot); it does not invoke `resolve_classification()`. (`resolve_classification()` re-enters only at the post-MVP refresh cycle, to re-derive the proposal and compare it against the snapshot for reference drift.)

**Tenant isolation.** `assessment` and `assessment_item` carry `tenant_id` and are RLS-enrolled; the immutability trigger covers audit rows; reference tables (`assessment_section_template`, control/risk libraries, taxonomy) are global, not RLS-scoped. The join tables `assessment_item_control` and `assessment_item_evidence` ship without `tenant_id`/RLS today; the migration **adds `tenant_id` + RLS to both** (parity decision, §13) so isolation is enforced directly rather than only transitively — uniform RLS across all tenant tables. Item-first access (§8.17) remains the norm as defense-in-depth, but is no longer the *sole* line of isolation.

**Completeness is a future orchestrator read.** What makes §4.1's assessment gate "met" (required sections present + item coverage) is a read this feature ultimately exposes. Build it alongside status in Sprint 6, but keep the logic in a service the orchestrator can call, not in an HTTP handler.

---

## 8. Constraints & invariants

1. **One *current* AIIA per use case.** The index already exists as `uq_one_aiia_per_use_case = UNIQUE (use_case_id) WHERE type = 'AIIA'` — correct for MVP, but it forbids a second AIIA regardless of version, so versioning isn't yet functional. Version-ready form (after adding `is_current`): `UNIQUE (use_case_id) WHERE type = 'AIIA' AND is_current`. This mirrors `uq_current_classification` (`WHERE is_current = true`) and lets the post-MVP refresh cycle insert new `version`s and flip `is_current` without a constraint migration. DB-level; catch the unique violation → 409.
2. **PROHIBITED → no assessment.** Hard stop at creation, typed reason.
3. **REQUIRES_CONTEXT → blocked.** No tier → no template; refuse with a reason pointing to classification.
4. **Tier snapshot at creation.** Persist `tier_snapshot` (= the effective `Classification.tier`) + `classification_version` (= `Classification.version`). Both are derivable from the current snapshot; `tier_snapshot` is a denormalisation kept for read convenience. Expose snapshot-vs-current in reads so drift is visible before the refresh cycle exists.
5. **Feeder inherits parent scope.** A feeder copies its parent AIIA's `tier_snapshot` / `classification_version` and never re-resolves — otherwise parent and child disagree on scope and the feeder surfaces mismatched sections.
6. **Optimistic concurrency (Phase A).** Mutations honour `If-Match` on `lock_version`; mismatch → 412. Protects the `amended` before/after diff — a corrupted diff makes the audit record itself wrong. (`lock_version` is the edit-level concurrency token, distinct from the run-level `version`.)
7. **Atomic from-state guard.** Provenance transitions are conditional updates (`… WHERE provenance IN (valid_from_states)`), not read-then-write; 0 rows → 409.
8. **Provenance is server-derived (§4).** Override metric reads `AI_SUGGESTED`-origin items only.
9. **Residual nullable until mitigation.** `residual > inherent` is a soft advisory flag, not a hard block (a mitigation introducing a new failure mode is real and audit-worthy).
10. **Audit atomicity.** Every mutation stages its `AuditEvent` in the same transaction; never commit audit separately.
11. **Pristine-delete only.** Hard `DELETE` of an assessment is permitted only while pristine (no confirms/amends, no control links, no feeders) — the create/delete/re-create path. A worked assessment is **voided**, not deleted (deleting real content + an immutable "created then deleted" trail reads like spoliation); void needs minimal status work → Sprint 6.
12. **Cross-map derivation.** The control link stores `control_id` + `coverage` only; framework satisfaction derives from the library cross-map. **`UNIQUE (item_id, control_id)` is an ALTER to add** (absent today; without it duplicate links are possible).
13. **Feeder integrity.** `parent_aiia_id` references an `AIIA`-type assessment in the same tenant and use case; a feeder cannot parent a feeder; `type=AIIA` rejected at the feeder endpoint (422); `UNIQUE (parent_aiia_id, type)`.
14. **Classification read/write separation preserved** — this feature reads only the persisted current snapshot and calls neither `resolve_classification()` nor `snapshot_classification()`.
15. **SoD lives at assignment, not here** — endpoints gate by role and trust the conflict matrix.
16. **Action-time SoD seam (forward-looking).** In the tenant-scoped MVP the assignment matrix already guarantees authoriser≠author. The `created_by`-everywhere seam only bites under the future object-scoped roles (owner on system X, authoriser on Y) — keep it, but it is not a present gate.
17. **Item-first access to join tables (defense-in-depth).** With `tenant_id` + RLS now on `assessment_item_control` / `assessment_item_evidence` (§7), isolation is enforced directly; item-first access remains the norm and a tested invariant as a second line, not the only one.

---

## 9. Feeder cardinality & propagation

### 9.1 Cardinality & scoping
Feeders hang off the AIIA; the AIIA is one-per-use-case → cardinality is per use case. FRIA 0..1, DPIA 0..1, MODEL_RISK 0..1 for MVP (a use case binds to one product = one model context). **Constraint:** `UNIQUE (parent_aiia_id, type)`. **Relaxation seam:** when the catalogue models multi-component products, MODEL_RISK becomes 1..N — scope the constraint to `{FRIA, DPIA}` and give MODEL_RISK a component reference. Only MODEL_RISK ever relaxes, and only when the catalogue model changes.

Feeders **inherit the parent's `tier_snapshot` / `classification_version`** at creation (§8.5).

**Feeder pre-fill from the register (Phase B).** Feeders should not start blank — the register already holds the structured inputs each one needs: `system_affected_party` is core FRIA input (rights-bearing parties), and `system_data_category` is core DPIA input (data processed). On feeder creation, pre-fill the FRIA's affected parties and the DPIA's data categories straight from these tables — the "facts entered once, not re-keyed" principle applied to feeders. Both are mutable-in-place children, so if these pre-filled facts are part of the frozen feeder record, snapshot them with the same resolved-label logic as §5.

### 9.2 Propagation (reference, not copy)
Feeders never copy into the AIIA. `GET /assessments/{aiia_id}` assembles, per AIIA section, native items ∪ surfaced feeder items, each surfaced item tagged with `source_assessment_id` + `type`. The mapping rides on the seeded template: each feeder section row carries an optional `aiia_target_section_key`. Provenance and `created_by` are untouched — the AIIA borrows the view, not the row; single source of truth, no sync, no conflict class.

`GET /assessments/{feeder_id}` returns only that feeder's own items. **Feeder-private sections** (`aiia_target_section_key = NULL`) surface in no AIIA section by design — so the **export/audit pack must include each feeder's full own view**, or a nowhere-mapped FRIA finding would be invisible to an auditor reading only the AIIA. *(Confirm preference vs a catch-all AIIA section — §13.)*

---

## 10. Sequencing

**Phase A — AIIA core (demoable).** Step 0: the schema migration (`aiia_core_migration.py`) — the `assessment` / `assessment_item` ALTERs, enum extensions, join-table `tenant_id`+RLS, FK hardening, and `assessment_section_template` create. Then the section-template **data-seeding** migration (sections per tier + ISO/IEC 42005 clauses + feeder→AIIA targets). Then: AIIA creation with snapshot pre-fill + identity-only risk proposal; item CRUD; explicit confirm with disposition-before-authoring; control links; pristine delete; **optimistic concurrency + atomic from-state guard**; `GET /sections`; `GET /assessments/{id}`; reference reads. Residual and `selection_basis` live here.

**Phase B — feeders + propagation.** Feeder creation (inheriting parent scope), register pre-fill (affected parties → FRIA, data categories → DPIA), the `aiia_target_section_key` mapping, and read-time assembly.

**Seams preserved now:** `status` (Sprint 6 lifecycle + worked-state void), `created_by` (Sprint 6 action-time SoD), `assessment_item_evidence` stub (Sprint 4), `tier_snapshot`/`classification_version` + `version`/`is_current` + current-scoped constraint (post-MVP AIIA versioning / refresh).

---

## 11. Edge & failure cases

- Use case not in tenant → 404. Tier `PROHIBITED` → 409/422, no row. Tier `REQUIRES_CONTEXT` → 409. No current `Classification` snapshot at all → 409 (block; guard against the data-integrity gap). Duplicate AIIA (race) → 409. Empty template for a resolvable tier → loud failure (seeding bug), not an empty shell.
- No `CatalogueProductRisk` / no catalogue product → creation succeeds with a tier/modality-only (possibly empty) proposed set. Pre-fill is best-effort.
- `risk_id`/`control_id` not in library → 422. Duplicate control link → 409 (once `UNIQUE (item_id, control_id)` is added — §8.12). Bad `coverage` → 422.
- Deleting a referenced library **risk** or **control** → blocked by `RESTRICT` (FK hardening, §3) rather than silently nulling `risk_id` / cascading away coverage records; deprecate library entries via soft-flag instead.
- Authoring-only PATCH on undispositioned `AI_SUGGESTED` item → 409 (confirm/amend first). Confirm on a non-`AI_SUGGESTED` item → 409. No-op PATCH → no-op.
- `If-Match` mismatch on any mutation → 412 (stale read; protects the diff). Concurrent confirm/amend → conditional update, loser gets 409.
- Delete a worked assessment → 409 (use void, deferred). Delete a pristine assessment → cascade + `assessment.deleted`. Delete an item with control links → audited cascade.
- `residual > inherent` → soft advisory flag.
- Feeder before any AIIA → 404/409. `type=AIIA` at feeder endpoint → 422. Feeder parenting a feeder → 422. Second feeder of an existing type → 409.
- Post-creation reclassification → `tier_snapshot` stale vs current; both surfaced in reads.

---

## 12. Intentionally deferred (post-MVP / later sprints)

- **Evidence file upload** (Sprint 4) — stub modelled; sanitise `assessment_item_evidence.uri` at render, validate scheme on input.
- **Status transitions / review / sign-off, incl. worked-state void** (Sprint 6) — `status` + `created_by` positioned now.
- **AI-assisted text drafting and AI-suggested scoring** (post-MVP) — so `AI_SUGGESTED` here is deterministic, identity-only.
- **AIIA versioning + refresh-on-material-change cycle** (post-MVP — seams in place: `version`/`is_current`, current-scoped constraint, `tier_snapshot`/`classification_version`). An AIIA is re-runnable; each run is an immutable version that re-snapshots then-current facts (so `created_at` becomes the version stamp). **Drift detection** = AIIA's captured `classification_version` ≠ the use case's current Classification version, with a tier change. **Trigger decomposition:** only a change to `system.catalogue_product_id` (or the reference mappings) moves the tier under current `resolve_classification` logic → *tier-driven refresh* (re-scope sections, re-propose risks); edits to `purpose` / `context_blob` / affected parties / data categories are material to *content* but not tier → softer *content-refresh flag*. **Policy:** flag-and-warn (`needs_refresh`) for most drift, force on a tier *increase*, hard-stop on anything → `PROHIBITED` (the existing AIIA must not be signable). The trigger lives at the classification layer (when `snapshot_classification` runs and the tier changes), not inside the AIIA.
- **AIIA-level residual *heat view*** (AIIA-8, a Could) — the `assessment.residual_risk_summary` column already exists, so capturing the summary is available (naturally populated at Sprint 6 sign-off, from per-item residuals); only the heat-view *visualisation* is the deferred Could.
- **Object-scoped (per-system) governance roles** — additive; gate written not to preclude it.
- **Bulk "confirm all proposed"** — keep per-item confirmed events if added.

### Next slice (not post-MVP)
- **System-level rollup (AIIA-1b, a Must)** — reads completed use-case AIIAs; depends on this sprint's output. Scheduled as the immediate next slice, not a post-MVP deferral.

---

## 13. Decisions resolved + migration

All previously-open design decisions are now resolved (design phase — fixed in the model rather than deferred):

1. **Risk proposal granularity → identity-only.** Scores are authoring fields, not proposed substance; AI-suggested scoring is post-MVP (§4).
2. **Feeder-private sections + export → confirmed.** `aiia_target_section_key = NULL` marks feeder-private; those items surface in no AIIA section, and the export pack includes each feeder's own full view (§9.2).
3. **Join-table tenancy → RLS parity.** `tenant_id` + RLS added to `assessment_item_control` / `assessment_item_evidence` (§7); item-first access stays as defense-in-depth (§8.17).
4. **Reference-data FK hardening.** `assessment_item.risk_id` (`SET NULL → RESTRICT`) and `assessment_item_control.control_id` (`CASCADE → RESTRICT`) so deleting a library risk/control can't orphan or silently strip an assessment record; library entries deprecate via soft-flag (§3, §11).

**Schema reconciliation — complete (all six tables read).** `classification` fully satisfies §2/§5. The full ALTER/CREATE set is captured in the migration `aiia_core_migration.py`:
- `assessment`: adopt `type` (not `kind`); add `tier_snapshot`, `classification_version` (backfilled + NOT NULL), `is_current`, `lock_version`, `created_by`; evolve `uq_one_aiia_per_use_case` (partial unique *index*) to `WHERE type = 'AIIA' AND is_current`.
- `assessment_item`: add `section_key` (load-bearing), `residual_likelihood`/`residual_severity`, `selection_basis`, `source_ref`, `created_by`, `lock_version`; index `section_key`.
- enums: `provenance_confidence += USER_PROVIDED`; new `section_applicability`.
- `assessment_item_control`: add `UNIQUE (item_id, control_id)`, `tenant_id` + RLS; harden `control_id` FK.
- `assessment_item_evidence`: add `tenant_id` + RLS.
- harden `assessment_item.risk_id` FK.
- create `assessment_section_template` (global reference; row-seeding is a separate data migration).
- Existing seams already present: `status` enum, `residual_risk_summary`, `approved_by_user_id`/`approved_at`, cascade FKs.

**Migration notes:** `ALTER TYPE … ADD VALUE` is in-transaction-safe on PG12+ since the value isn't used in the same migration (split it out for PG<12); the `tier_snapshot`/`classification_version` backfill + NOT NULL assumes every use case has a current classification (true under auto-resolve) and will fail loudly otherwise. Set `down_revision` to your current head.

*Not in this sprint: the `evidence` first-class table (exists; its columns belong to the Sprint 4 evidence/upload path), and the `assessment_section_template` row content (a separate data-seeding migration).*

---

## Appendix A — Review disposition

| # | Sev | Finding | Disposition |
| --- | --- | --- | --- |
| 1 | Blocking | Per-item provenance can't measure override rate | Resolved: scores not proposed; override scoped to `AI_SUGGESTED`-origin items; disposition-before-authoring (§4) |
| 2 | Blocking | Does proposal include scores? | Decided: identity only; scores are authoring fields (§4, §5) |
| 3 | Blocking | No enum value for inherited facts | Added `USER_PROVIDED`; inherited facts snapshotted with `source_ref` (§3, §4) |
| 4 | Should | No delete / remediation path | Pristine-delete added; worked-state void → Sprint 6 (§6, §8.11) |
| 5 | Should | Feeder tier not bound to parent | Feeder inherits parent scope (§8.5, §9.1) |
| 6 | Should | Concurrency corrupts audit diff | Optimistic concurrency into Phase A (§8.6, §10) |
| 7 | Should | Transition needs atomic guard | Conditional from-state update (§8.7) |
| 8 | Should | AIIA-1b filed as deferred | Moved to "next slice" (§12) |
| 9 | Minor | Recommended sections unreachable | Surfaced via `GET /sections`; instantiated via `POST /items` (§6) |
| 10 | Minor | Thin shown-reasoning for risks | `selection_basis` on proposed items (§3, §4) |
| 11 | Minor | §2/§13 contradiction on classification | Resolved from source: `resolve_classification()` is proposal-only; AIIA reads the current `Classification` snapshot for the effective tier (§2, §5, §7) |
| 12 | Minor | Empty template → silent empty AIIA | Non-empty assertion; loud failure (§5, §8) |
| 13 | Minor | Feeder-private sections surface nowhere | Intentional; export includes feeder view (§9.2) — confirm |
| 14 | Minor | `type=AIIA` at feeder endpoint | Explicit 422 (§6, §8.13) |
| 15 | Minor | `assessment_item_evidence.uri` stored-link vector | Scheme validation on input; sanitise at export (§3, §12) |
| 16 | Minor | Action-time SoD reads as present gap | Relabelled forward-looking (§8.16) |