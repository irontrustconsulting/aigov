# Sprint Handoff — Phase B: Feeders (FRIA / DPIA / MODEL_RISK)

> Additive on Phase A (AIIA Core). A feeder **is** an `assessment` row; Phase B reuses all Phase-A item/control/evidence/provenance/concurrency/audit machinery and adds only feeder creation, scoping, per-feeder section taxonomies, register pre-fill, distributed risk identification, and read-time propagation. Self-contained for a coding agent.

---

## 1. Sprint title

**Phase B — Feeders: create FRIA / DPIA / MODEL_RISK assessments that inherit AIIA scope, pre-fill from the register, identify domain risks, and feed into the parent AIIA by reference.**

---

## 2. Status going in / context

- **Phase A (AIIA Core) is the baseline and must be merged first.** Phase B does not stand alone.
- **A feeder is an `assessment` row** with `type ∈ {FRIA, DPIA, MODEL_RISK}` and `parent_aiia_id` set. All item CRUD, confirm/amend, control links, provenance, `lock_version` concurrency, pristine-delete, RLS, and tenant-plane audit from Phase A operate on a feeder unchanged.
- **No external-system calls.** Tenant-plane atomic-audit only.
- **Design decisions resolved:** distributed-by-domain risk identification; opinionated feeder recommendation; MODEL_RISK pre-filled (not blank); 1:1 feeder→AIIA section mapping; reference (not copy) propagation.
- **One reference-schema dependency** for the DPIA-required trigger only (`data_category` personal-data flag — §10).

---

## 3. Baseline & architectural context

Builds directly on Phase A. Reused **unchanged**:
- `assessment` (polymorphic; `type`, `parent_aiia_id`, `tier_snapshot`, `classification_version`, `version`, `is_current`, `lock_version`, `status`, `created_by`), `assessment_item`, `assessment_item_control`, `assessment_item_evidence`, `assessment_section_template`.
- Item endpoints `/v1/assessments/{id}/items…` operate on a feeder id with no change.
- Provenance enum + state machine + override metric; conditional-update concurrency; tenant-plane atomic audit; RLS on all tenant + join tables; governance-role gating (`{system_owner, contributor}` writes).
- `propose_risk_set(...)` from Phase A — **generalised to be type/layer-aware** here (§5.5).

Register sources (existing, mutable-in-place):
- `system_affected_party` (M:N junction `system` ↔ `affected_party`) → FRIA pre-fill.
- `system_data_category` (M:N junction `system` ↔ `data_category`) → DPIA pre-fill.
- `system` fields (`catalogue_product_id`, modality tags, `hosting_model_id`, structured dims) → MODEL_RISK pre-fill.

---

## 4. Goal / contract

A tenant can attach FRIA, DPIA, and/or MODEL_RISK feeders to an AIIA; each inherits the AIIA's scope, pre-fills from the register, identifies risks in its standards-domain, and surfaces into the parent AIIA by reference. The platform asserts **which feeders the use case needs**.

New / changed endpoints (all tenant endpoints; gates as shown):

| Endpoint | Purpose | Gate |
| --- | --- | --- |
| `POST /v1/assessments/{id}/feeders` | create feeder (`{type}`); `{id}` must be an AIIA | governance: `system_owner`/`contributor` |
| `DELETE /v1/assessments/{feeder_id}` | delete feeder (pristine only) | governance: `system_owner`/`contributor` |
| `GET /v1/assessments/{aiia_id}` | **extended**: AIIA detail now assembles surfaced feeder items per section (§5.6) | governance: any |
| `GET /v1/assessments/{aiia_id}/feeder-recommendations` | required/recommended/N-A per feeder type, with basis (§5.3) | governance: any |

Reused as-is: `GET /assessments/{feeder_id}` (feeder's own items only), `GET /assessments/{feeder_id}/sections` (feeder tier template), `GET /use-cases/{id}/assessments` (lists feeders), all `/items…` and `/control-links…` endpoints on a feeder id.

New audit action: `assessment.feeder_created`. (Feeder item/link mutations reuse the Phase-A action strings.)

---

## 5. Domain model / rules

### 5.1 Feeder taxonomy & AIIA targets
Each feeder type has a standards-grounded section set in `assessment_section_template` keyed `(type, tier, section_key)`; each row's `aiia_target_section_key` is the AIIA section it surfaces into, or `NULL` (feeder-private). Structure (exact rows = WI-1 seed):

| Type | Standard | Sections (representative) | AIIA target / private |
| --- | --- | --- | --- |
| FRIA | EU AI Act Art 27 | deployment desc; affected persons/groups; rights at risk; likelihood/severity to rights; oversight; mitigation; complaint/redress | harm-identification + oversight; redress → private |
| DPIA | GDPR Art 35 | processing desc; necessity & proportionality; lawful basis; data categories & subjects; risks to data subjects; mitigations; DPO consultation | data-protection section; DPO consult → private |
| MODEL_RISK | OWASP LLM 2025 + NIST/ISO | model desc; data/training provenance; performance & robustness; security/adversarial; bias & fairness; drift & monitoring; dependencies | technical-risk section; ops/monitoring → private |

### 5.2 Cardinality & scoping
`UNIQUE (parent_aiia_id, type)` — at most one of each type per AIIA. A feeder **copies its parent AIIA's `tier_snapshot` / `classification_version` at creation and never re-resolves** (parent and feeder stay scope-identical, including an inherited stale-but-coherent snapshot). `version = 1`, `is_current = true`. MODEL_RISK is the only type that relaxes to 1..N later (multi-component models) — out of scope now.

### 5.3 Feeder recommendation (opinionated default)
`GET /assessments/{aiia_id}/feeder-recommendations` returns, per feeder type, `applicability` + `basis` + `exists`:

| Type | required | recommended | basis |
| --- | --- | --- | --- |
| FRIA | tier = HIGH and deployer obligations apply | tier = HIGH | EU AI Act Art 27 |
| DPIA | personal/special-category data present (via `data_category` flag — §10) and high-risk processing | any data category present | GDPR Art 35 |
| MODEL_RISK | — | always | NIST AI RMF / ISO 42001 |

Strong default + shown reasoning + overridable: the user confirms by creating; declining is an override (audited skip-justification is Sprint 6, not Phase B).

### 5.4 Register pre-fill (snapshot, `USER_PROVIDED`)
On feeder creation, resolve junction → reference entity, snapshot the **resolved label** (+ `source_ref` = reference id), one item per linked entity:
- **FRIA** ← `system_affected_party` → `affected_party` label, items under "affected persons/groups."
- **DPIA** ← `system_data_category` → `data_category` label, items under "data categories & subjects."
- **MODEL_RISK** ← `system` fields (resolved `catalogue_product` model identity, modality, `hosting_model` label) → items under "model description."

Point-in-time (register is mutable-in-place); snapshot the label, never the bare FK id. Empty junction → no pre-filled items (valid; section remains for human authoring).

### 5.5 Distributed risk identification
Each feeder identifies risks in its domain; risks consolidate into the AIIA via propagation (§5.6). `propose_risk_set(assessment_type, tier, modality_tags, catalogue_product_id)` is **layer-aware**, mapping the two-layer Risk Library by type:

| Assessment | Auto-proposed risk set (`AI_SUGGESTED`, identity-only) |
| --- | --- |
| AIIA | governance layer (NIST/ISO) + `CatalogueProductRisk` |
| MODEL_RISK | technical layer (OWASP LLM Top 10) |
| FRIA | none auto-proposed — rights risks are human-identified via the FRIA sections |
| DPIA | none auto-proposed — data-subject risks are human-identified via the DPIA sections |

> **Phase-A coordination:** if Phase A shipped `propose_risk_set` as all-layers, narrow the AIIA call to the governance layer + product (technical/OWASP moves to MODEL_RISK). The function gains an `assessment_type` parameter; AIIA passes `AIIA`. Same provenance, disposition-before-authoring, and override-metric rules apply to feeder proposed risks.

### 5.6 Propagation — read-time reference (never copy)
`GET /assessments/{aiia_id}` assembles per AIIA section `:S`:
```
native:  assessment_item WHERE assessment_id = :aiia AND section_key = :S
feeder:  assessment_item j  (its assessment.parent_aiia_id = :aiia)
         JOIN assessment_section_template t
           ON t.type = feeder.type
          AND t.tier = feeder.tier_snapshot
          AND t.section_key = j.section_key
         WHERE t.aiia_target_section_key = :S
```
Surfaced items are tagged `source_assessment_id` + `type`; their `provenance`, `created_by`, scores, and **control links travel untouched** (a control linked on a feeder item counts toward AIIA coverage). Feeder-private sections (`aiia_target_section_key = NULL`) surface only in `GET /assessments/{feeder_id}`. Single source of truth: editing/deleting a feeder item changes/removes it everywhere it surfaces, no sync. Mapping is **1:1** (one feeder section → one AIIA section). Duplicate risks across sources surface both, tagged by source — no dedup (MVP).

### 5.7 Integrity & deletion
Parent must be `type = AIIA`, same tenant + use case; a feeder cannot parent a feeder; `type = AIIA` at the feeder endpoint → 422; `UNIQUE (parent_aiia_id, type)`. Feeder deletion is **pristine-only** (no confirms/amends, no control links); cascade removes its items (and their surfacing). Parent-AIIA deletion cascades to feeders (`parent_aiia_id ON DELETE CASCADE`).

---

## 6. Work items

- **WI-B1 — Feeder section-template seed (data migration).** Rows for FRIA / DPIA / MODEL_RISK per `(type, tier)`: `section_key`, `applicability`, `prompt`, `iso_42005_clause` (or Art 27 / Art 35 ref), `aiia_target_section_key` (NULL = private). Content task; gates pre-fill and propagation. Validate every non-null target resolves to a real AIIA section key.
- **WI-B2 — `create_feeder(parent_aiia_id, type, ctx)`** in `AssessmentService`: integrity checks (§5.7); copy parent scope (§5.2); register pre-fill (§5.4); layer-aware risk proposal for MODEL_RISK (§5.5); one `assessment.feeder_created` audit; tenant-plane atomic commit. No external call.
- **WI-B3 — Feeder pristine-delete** (reuse the Phase-A pristine guard on a feeder id).
- **WI-B4 — Propagation assembly** in `GET /assessments/{aiia_id}` detail (§5.6); surfaced-item tagging in the read schema.
- **WI-B5 — `propose_risk_set` made layer/type-aware** (§5.5) + the Phase-A AIIA call-site adjustment.
- **WI-B6 — Feeder recommendation** read (§5.3) + DPIA-trigger predicate against the `data_category` flag.
- **WI-B7 — Schemas:** `FeederCreate {type}`, feeder-recommendation read, extended AIIA detail (surfaced feeder items with source tags). No new item-level schemas.

---

## 7. Constraints / non-negotiables

1. **A feeder is an `assessment`** — reuse Phase-A item/control/evidence/provenance/concurrency/audit; add no parallel machinery.
2. **Scope is inherited, never re-resolved** — copy parent `tier_snapshot` / `classification_version`.
3. **Parent integrity** — parent is `type = AIIA`, same tenant + use case; no feeder-of-feeder; `type = AIIA` rejected (422); `UNIQUE (parent_aiia_id, type)`.
4. **Propagation is read-time reference only** — no copy, no sync, no write-back into the AIIA; surfaced items keep their own provenance/`created_by`.
5. **Risk proposal is layer-aware** — MODEL_RISK = technical/OWASP; AIIA = governance + product; FRIA/DPIA = human-identified (no auto-proposal).
6. **Pre-fill snapshots resolved labels**, `USER_PROVIDED`, `source_ref` to origin; point-in-time.
7. **Pristine-delete only;** parent deletion cascades to feeders.
8. **All Phase-A invariants apply** (provenance server-derived, disposition-before-authoring, conditional-update concurrency, audit atomicity, RLS, `tenant_id` from `ctx`).
9. **1:1 feeder→AIIA section mapping** via `aiia_target_section_key`.

---

## 8. Acceptance criteria

- `POST /feeders {type}` on an AIIA → feeder created with parent scope inherited, register pre-fill present (`USER_PROVIDED`, labels + `source_ref`), MODEL_RISK technical risks proposed (`AI_SUGGESTED`), one `assessment.feeder_created` event.
- `type = AIIA` → 422; non-AIIA / missing parent → 404/409; second feeder of an existing type → 409; feeder parenting a feeder → 422.
- Feeder `tier_snapshot` / `classification_version` equal the parent's exactly.
- FRIA pre-fills one item per `system_affected_party`; DPIA one per `system_data_category`; MODEL_RISK from system/model facts; empty junction → no items, section intact.
- `GET /assessments/{aiia_id}` surfaces feeder items under mapped sections, tagged `source_assessment_id` + `type`, with feeder provenance/`created_by` intact and feeder control links counting toward AIIA coverage; feeder-private items appear only in `GET /assessments/{feeder_id}`.
- Editing a feeder item changes the surfaced view; deleting it removes it from the AIIA view (no sync step).
- `feeder-recommendations` returns correct required/recommended/N-A + basis per type for the use case's tier and data profile; `exists` reflects created feeders.
- `propose_risk_set(AIIA, …)` returns governance + product only; `propose_risk_set(MODEL_RISK, …)` returns OWASP technical; FRIA/DPIA return none.
- Pristine feeder delete cascades its items; worked feeder delete → 409; parent-AIIA delete cascades to feeders.
- RLS: cross-tenant feeder / feeder-item / link → 404.

---

## 9. Out of scope

- Feeder versioning/refresh (rides the post-MVP AIIA versioning cycle — feeders version with their parent).
- Multi-component MODEL_RISK (1..N).
- Cross-feeder risk dedup/merge.
- N:M feeder→AIIA section mapping.
- Audited feeder-skip justification (Sprint 6 sign-off).
- Evidence on feeder items (Sprint 4; works for free once the upload path lands).
- The `evidence` first-class table.
- FRIA/DPIA library-proposed risk layers (only if/when the Risk Library is extended with rights/data layers).

---

## 10. Dependencies / decision notes

**Resolved:** distributed-by-domain risk identification; feeder recommendation triggers; MODEL_RISK pre-filled (not blank); 1:1 section mapping; reference propagation; pre-fill resolves junction → reference entity and snapshots the label.

**Phase-A coordination:** `propose_risk_set` becomes `assessment_type`-aware and the AIIA call narrows to governance + product (WI-B5).

**Reference-schema dependency (DPIA-required trigger only):** `data_category` must carry a personal/special-category flag to drive the "personal data present" predicate (§5.3). If absent: either add the classification, or soften the DPIA-required trigger to "recommended when any data category is present." Confirm with `\d data_category`. FRIA needs only the `affected_party` label (no attribute dependency); its trigger is tier-driven.

**External:** none.

---

## 11. Implementation contract

- **Placement:** feeder creation/delete in `app/services/assessment.py` (extend, do not fork); the feeder endpoints in the existing `assessments` router; schemas in `app/schemas/`; the feeder section-template seed as an Alembic data migration.
- **Reuse, don't fork:** feeder items flow through the Phase-A `/items…` and `/control-links…` endpoints and service methods; do not duplicate them for feeders.
- **Tenancy / audit / concurrency:** identical to Phase A — `tenant_id` from `ctx`, `AuditEvent` staged in-session and committed atomically, conditional-update concurrency, RLS.
- **Pre-fill:** resolve junction → reference entity in the same transaction as feeder creation; snapshot labels; never copy bare FK ids; `provenance = USER_PROVIDED`, `source_ref` set.
- **Propagation:** read-time only, in the AIIA detail assembler; never materialise feeder items into the AIIA. Surfaced-item source tags are computed in the read, not stored.
- **Naming:** mirror the live schema (`type`, `parent_aiia_id`, `assessment_section_template.aiia_target_section_key`, `system_affected_party`/`affected_party`, `system_data_category`/`data_category`).

---

## 12. Execution protocol

1. **WI-B5** — make `propose_risk_set` layer/type-aware; adjust the Phase-A AIIA call site (coordinating change; land first so risk behaviour is coherent).
2. **WI-B1** — seed feeder section templates; validate target-key resolution.
3. **WI-B2 + WI-B3** — `create_feeder` (integrity → scope inherit → pre-fill → MODEL_RISK proposal → audit → atomic commit) and pristine-delete.
4. **WI-B7** — schemas, including the extended AIIA detail.
5. **WI-B4** — propagation assembly in the AIIA detail read.
6. **WI-B6** — feeder recommendation read (after confirming the `data_category` flag).
7. Validate each step against §8 before proceeding; do not materialise propagation or fork item machinery.

---

## 13. Validation protocol

- **Unit:** `propose_risk_set` per type (AIIA → governance+product, MODEL_RISK → OWASP, FRIA/DPIA → empty); feeder integrity guards (type=AIIA, feeder-of-feeder, duplicate type); pre-fill label-resolution + snapshot (incl. empty junction); recommendation predicate per tier/data profile.
- **Integration:** feeder create → correct pre-fill + scope inheritance + audit; the full §8 error matrix; feeder item CRUD/confirm/amend/link reuse Phase-A behaviour unchanged on a feeder id.
- **Propagation:** surfaced items appear under mapped sections with source tags and intact provenance; feeder control links count toward AIIA coverage; feeder-private items excluded from AIIA, present in feeder view; edit/delete of a feeder item reflects in the AIIA view with no sync step; 1:1 mapping honoured; orphan target key surfaces nowhere and is caught by seed validation.
- **Tenancy / RLS:** cross-tenant feeder, feeder item, and feeder control/evidence link → 404; direct join-row access under a foreign tenant returns nothing.
- **Lifecycle:** pristine feeder delete cascades items; worked feeder delete → 409; parent-AIIA delete cascades to feeders; surfaced feeder items disappear from the AIIA when the feeder is deleted.
- **Phase B exit:** from an AIIA, a user is shown which feeders are required/recommended; can create FRIA/DPIA/MODEL_RISK; sees each pre-filled from the register and (MODEL_RISK) with proposed technical risks; assesses feeder items through the same item machinery; and sees those facts and risks consolidated into the AIIA by reference with correct source attribution and coverage — entirely through the API, with a clean audit trail.

---

## 14. Addendum — reconciliation against the shipped Phase A code

This sprint was drafted against the Phase A *design*. Phase A has since been implemented (`app/services/assessment_service.py`, `app/routers/v1/assessments.py`, `data/seed/aiia_section_template.yaml`). Five points in the sections above don't match what's actually on the ground — corrected here so WI-B work doesn't get implemented against a stale assumption.

1. **§11 names the wrong service file.** It says `app/services/assessment.py`; the real file from Phase A is **`app/services/assessment_service.py`**. Extend that file — do not create `assessment.py`.

2. **`propose_risk_set` is not "all-layers" today — it's catalogue-product-only.** The Phase-A implementation queries `CatalogueProductRisk` only; it never queries the `Risk` library by `RiskLayer` at all (`tier`/`modality_tags` are accepted-but-currently-unused parameters, explicitly marked as a forward-looking seam in the code). This means **§10's framing ("if Phase A shipped all-layers... narrow the AIIA call") does not apply** — WI-B5 is not a narrowing, it is *adding* two new layer-based queries that don't exist yet:
   - `AIIA` → `RiskLayer.GOVERNANCE_RIGHTS` risks (dedup by `risk_id` against the existing catalogue-product risks) **+** the existing catalogue-product query (unchanged).
   - `MODEL_RISK` → `RiskLayer.TECHNICAL_SECURITY` risks (OWASP LLM Top 10).
   - `FRIA` / `DPIA` → `[]` (unchanged from "no auto-proposal").
   - New signature: `propose_risk_set(assessment_type, tier, modality_tags, catalogue_product_id, db)`. Update `create_aiia`'s call site to pass `AssessmentType.AIIA` explicitly.
   - `selection_basis` needs a layer-aware string per source (e.g. `"Governance-layer risk (NIST/ISO) for tier {tier}"` vs the existing `"CatalogueProductRisk for product {id}"`).

3. **The §10 reference-schema dependency is already resolved — no new migration needed.** Confirmed against `05ff13cdcdc3_system_intake_vocab_tables.py`: `data_category.is_special_category` exists (special-category rows seeded), and `eu_operator_role.code = 'deployer'` exists (provider/deployer/importer/distributor all seeded). The FRIA/DPIA-required predicates in §5.3 can be written directly against these columns.

4. **Phase A's existing feeder seed rows in `data/seed/aiia_section_template.yaml` are a placeholder, not WI-B1's real content.** They were seeded "ahead" per the Phase A design doc's sequencing note, with a deliberately small representative set. Concrete gaps against §5.1/§5.4 to close in WI-B1:
   - No FRIA section keyed for "affected persons/groups" as a **pre-fill target** — the existing `fria_vulnerable_groups` is a discussion prompt, not an entity-list section. Add `fria_affected_persons` (required, `aiia_target_section_key: stakeholders_affected_parties`) as the §5.4 FRIA pre-fill target.
   - No MODEL_RISK "model description" section to pre-fill from system/model facts. Add `model_risk_model_description` (required, `aiia_target_section_key: technical_robustness`) as the §5.4 MODEL_RISK pre-fill target.
   - MODEL_RISK rows are seeded **only at `high_risk`**. §5.3 says MODEL_RISK is "always" recommended regardless of tier — as seeded today, creating a MODEL_RISK feeder under a LIMITED/MINIMAL AIIA would hit the empty-template loud-failure guard (the same one that fires for an unseeded AIIA tier). Add MODEL_RISK rows at `limited_risk` and `minimal_risk`.
   - DPIA's required/recommended trigger (§5.3) is data-driven, not tier-driven, but DPIA is currently seeded only at `high_risk`/`limited_risk`. Add DPIA rows at `minimal_risk`.
   - `dpia_data_categories` (existing) is reusable as-is as the §5.4 DPIA pre-fill target — no change needed there.

5. **`UNIQUE(parent_aiia_id, type)` does not exist yet** — it needs a new migration in WI-B work (additive, non-partial — should autogenerate cleanly, unlike the hand-managed partial indexes). `assessment.parent_aiia_id` is already `ON DELETE CASCADE` from Phase A, so "parent-AIIA delete cascades to feeders" (§5.7, §8) already holds at the DB level with no further work.

**Adjusted sequencing** (supersedes §12 step ordering where it conflicts):

1. WI-B5 — make `propose_risk_set` type-aware per point 2 above; update the `create_aiia` call site.
2. New migration — `UNIQUE(parent_aiia_id, type)` on `assessment`.
3. WI-B1 — expand `data/seed/aiia_section_template.yaml` per point 4 above; re-run `python -m scripts.seed.seed_aiia_section_template` (idempotent); add a validation pass (loader-time or a one-off script) that every non-null `aiia_target_section_key` resolves to a real `(AIIA, tier, section_key)` row — an orphaned target key must fail loudly, the same philosophy as the empty-template guard.
4. WI-B2 + WI-B3 — `create_feeder` / feeder delete in `assessment_service.py`, reusing the resolved-label snapshot helper already written for `create_aiia`'s Pre-fill 2, and reusing `_is_pristine`/`delete_assessment` as-is (confirm during implementation that the pristine check is correctly generic over any `Assessment` row, not AIIA-specific).
5. WI-B7 — schemas (`FeederCreate`, `FeederRecommendationRead`, extended `AssessmentDetail`/`AssessmentItemRead` with `source_assessment_id`/`source_type`).
6. WI-B4 — propagation assembly in the `GET /assessments/{aiia_id}` detail read.
7. WI-B6 — feeder-recommendations endpoint, now unblocked by point 3.
8. New endpoints wire into the **existing** `app/routers/v1/assessments.py` — no new router file.
9. Tests in a new `tests/test_aiia_feeders.py`; promote the fixture helpers shared with `tests/test_aiia.py` (`tenant`, `member`, `gov_roles`, `_make_system`, `_make_use_case`, `_ctx_override`/`_ApiCtx`) into one shared location rather than copy-pasting a second time, now that two files need them.