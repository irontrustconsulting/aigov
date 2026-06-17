# Sprint Handoff — Classification Gate (EU AI Act intake / prohibited-practice hard stop)

> This sprint builds the classification **gate (gate 2) as a headless node**, and **includes the minimal Reviewer sign-off action** (the 2nd-line act that makes a classification authoritative). The review *infrastructure* — queue, comment threads, notifications, the full draft→in-review→approved→needs-refresh richness — is the shared workflow track and is **out of scope**. The cross-gate state machine and gates 1/3/4/5 are out of scope.

---

## 1. Sprint title

**Classification Gate: deterministic EU AI Act tier resolution, prohibited-practice hard stop, and Reviewer sign-off — as a headless, orchestrator-callable node.**

---

## 2. Status going in / context

- A use case is classified at **gate 2** of the gated lifecycle (4.1.1) — the *intake / prohibited-practice hard stop*. Gate 1 (vendor & product clearance) precedes it; the assessment gate (gate 3) follows.
- The existing engine resolves a tier by traversing the catalogue bridge (`system → catalogue_product → product_category → eu_ai_act_subcategory`). When it cannot, `resolve_classification()` returns `REQUIRES_CONTEXT` — a **return-only sentinel**, not a stored value.
- This sprint builds the classification gate's logic as a **node** the (out-of-scope) orchestrator drives. It does not build the orchestrator, the other gates, or the review workflow infrastructure.
- **Interaction model (4.1.3):** capture-once, orchestrate-in-background. The node is **not** a front-loaded user wizard. Classification resolves automatically from already-known context where possible; missing inputs are requested **just-in-time and targeted** — but the *triggering and routing* of those requests is the orchestrator's job. The node provides the *capabilities* (resolve, compute-residual, accept-answers, sign-off), not the user flow.
- **Separation of duties (4.9.1):** provision and judgement are different acts held by different roles. The 1st line (owner/contributor) *provides and confirms facts*; the 2nd-line **Reviewer reviews and signs off the classification**. That sign-off is the authoritative ratification.

---

## 3. Baseline & architectural context

### Existing components — reuse, do not rebuild

**`classification` (tenant plane, RLS `tenant_isolation`):** `id`, `tenant_id`, `use_case_id`, `tier eu_ai_act_tier NOT NULL`, `proposed_tier eu_ai_act_tier NULL`, `overridden boolean NOT NULL`, `rationale text NOT NULL`, `answers_blob jsonb NOT NULL`, `version integer NOT NULL`, `is_current boolean NOT NULL`, `basis_subcategory_code varchar(80) NULL`, `basis_legal_ref varchar(120) NULL`, timestamps. Partial unique index `uq_current_classification (use_case_id) WHERE is_current = true` — the concurrency guard. FKs cascade from `tenant`, `use_case`.

**`eu_ai_act_tier` enum** (shared across `eu_ai_act_subcategory.tier`, `classification.tier`, `use_case.eu_tier`): `PROHIBITED`, `HIGH`, `LIMITED`, `MINIMAL`, `UNCLASSIFIED`.

**Taxonomy & bridge (global reference, no `tenant_id`, no RLS, YAML-seeded):** `EUAIActCategory`; `EUAIActSubcategory` (`code` unique, `tier NOT NULL`, `legal_ref`) — carries the tier; `ProductCategory` (hierarchical); `ProductCategoryMembership` (M:N); `ProductCategoryEUMapping` — the bridge (M:N, `is_primary`, one primary per product category via partial unique index).

**Engine:** `resolve_classification()` — pure read, returns proposed tier or `REQUIRES_CONTEXT`, safe to call repeatedly. `snapshot_classification()` — writes; caller owns the transaction.

**Audit:** `AuditEvent` (tenant plane, append-only, RLS-scoped, DB immutability trigger). Action strings `entity.verb`.

**Governance (4.9.1):** `governance_role` catalogue + `require_governance_role(...)`; tenant-scoped assignment (WKF-7). Three lines of defence: 1st `system_owner` / `contributor` (own/provide, co-holdable); 2nd `reviewer` (reviews & signs off classification/FRIA/AIIA; recommends) / `authoriser` (accepts residual risk; separated from reviewer); 3rd `auditor` (read-only). SoD enforced as a conflict matrix **at assignment time** (WKF-5); cross-line pairs conflict; only `system_owner + contributor` compose.

**Provenance §1.5:** answers carry `ProvenanceConfidence` — `AI_SUGGESTED`, `CATALOGUE_CURATED`, `USER_CONFIRMED`, `USER_AMENDED`. The tier is the deterministic function of the answers; provenance tags the answers, not the tier.

### Patterns to preserve

- **Tenant endpoint convention:** router under `app/routers/v1/`, registered in `app/main.py` under `/v1`; gate with `get_tenant_db` **plus one** role gate; `tenant_id = ctx.tenant_id`; schemas in `app/schemas/`.
- **Classification read/write separation:** resolution is pure; the snapshot write is caller-owned.
- **Tenant-plane auditing:** the `AuditEvent` commits atomically with the business rows, never separately.
- **No external call** in this feature → the Cognito-style external-call ordering does **not** apply.
- **SoD is enforced at role assignment, not per action.** The node gates by role and trusts the conflict matrix; it does not re-check conflicts.

---

## 4. Goal / contract

For a use case at gate 2, the node must:

1. **Resolve** the EU AI Act tier deterministically from already-known answers (catalogue prefill + supplied answers), landing on a specific `EUAIActSubcategory` where the answers identify one.
2. **Compute the residual** — the targeted questions still required to resolve — when known context is insufficient (so the orchestrator can request them just-in-time).
3. Produce a **three-way outcome**: `UNRESOLVED` (gate not met), `RESOLVED` (proceedable: `HIGH`/`LIMITED`/`MINIMAL`), or **`PROHIBITED_HALT`** (the strong, defensible hard stop).
4. **Record** the computed classification in `PENDING_REVIEW` status (provision attributed to 1st line).
5. **Sign off** — a 2nd-line **Reviewer** approves the pending classification, at which point it becomes authoritative: status → `APPROVED`, and `use_case.eu_tier` is stamped.

**Service contract:**

```
resolve_context_classification(answers, tree_version)
    -> Outcome{ kind: UNRESOLVED | RESOLVED | PROHIBITED_HALT,
               tier, subcategory_code | None, rationale, missing: [...] }
```
Pure, deterministic, reproducible. No writes.

The `APPROVED` classification is the **AIIA's input contract** (front-loader). Persist everything the AIIA will front-load (tier, subcategory basis, legal ref, answers, rationale). The AIIA's *logic* is deferred; its *input data* is captured here.

---

## 5. Domain model / rules

- **Precedence ladder (not a free tree):** `PROHIBITED > HIGH > LIMITED > MINIMAL`. Resolution selects the highest-precedence asserted rung **regardless of question order**. Contradictory assertions resolve to the higher rung by rule — not an error.
- **Prohibited-practice hard stop (gate 2's signature):** resolution to `PROHIBITED` produces the distinct `PROHIBITED_HALT` outcome, surfaced with its reasoning. The node *determines and surfaces* it; the orchestrator *enforces* "do not advance to assessment" (out of scope, and moot now — no assessment gate exists yet). `use_case.eu_tier = PROHIBITED` (on sign-off) is the durable hard-stop marker. Overriding a prohibited result is permitted only via the deliberate, audited override path (`system_owner` proposes, Reviewer signs off) — never a silent bypass.
- **`MINIMAL` is an affirmative determination only** (ladder positively concludes "not prohibited/high/limited", all gating questions answered). Never a fallback.
- **Fail closed:** incomplete/ambiguous answers → `UNRESOLVED`, **no snapshot**, `use_case.eu_tier` stays `UNCLASSIFIED`. Never default to `MINIMAL`. "All gating questions answered but no terminal reached" is a seed/logic **defect** → fail loud, persist nothing.
- **`UNCLASSIFIED`** is the persisted "not yet / could not classify" state; `REQUIRES_CONTEXT` (the resolver's return sentinel) corresponds to it. **`classification.tier` holds real tiers only** — never `UNCLASSIFIED`.
- **Subcategory landing:** where answers identify a subcategory, populate `basis_subcategory_code` + `basis_legal_ref` from `EUAIActSubcategory`; otherwise tier-only with basis null.
- **Provision vs judgement (SoD):** the 1st line provides/confirms facts and *proposes* overrides; the 2nd-line Reviewer *signs off*. The owner never unilaterally finalises a tier; the Reviewer can request changes but does not author the tier.
- **Catalogue confirmation = a diff (WI-9):** `ProductCategoryEUMapping` defines the candidate subcategory set per product category (primary + siblings). Prefill the primary (`CATALOGUE_CURATED`); ask only the disambiguating questions. Refining to a non-primary *mapped* subcategory is `USER_CONFIRMED` (not override).
- **Provenance:** catalogue prefill `CATALOGUE_CURATED`; supplied answers `USER_CONFIRMED`; override authorship `USER_AMENDED`. The computed tier carries no distinct provenance.
- **Tree-version pin-and-resolve:** the question payload carries `tree_version`; the commit echoes it; resolution runs against the pinned version; the snapshot is reproducible against it.

---

## 6. Work items

> WI-1 → WI-8 are the sprint core. WI-3 runs in parallel. WI-9 is separable.

**WI-1 — Decision-tree reference models + migration (DDL only).**
Alembic migration, global reference tables (no `tenant_id`, no RLS): `DecisionTree` (versioned container), `DecisionTreeQuestion` (tree/version FK, text, precedence rung probed, `legal_ref`, order), `DecisionTreeOption` (question FK, label, and the assertion: a rung `PROHIBITED|HIGH|LIMITED` **or** an implied `eu_ai_act_subcategory` code).

**WI-2 — YAML seed + version-aware loader.**
Content in YAML; loaded by a seed script. **Additive-by-version:** explicit `version` in YAML — absent → insert new; present and matching → no-op (idempotent); present and differing → **fail loud** (refuse mutation of a frozen version; require a bump). Encodes the subcategory crosswalk alongside the questions.

**WI-3 — EU AI Act question content authoring (parallel, long pole).**
The Art 5 / Annex III / Art 50 question set as YAML; reviewed on the diff; the version bump is the audit/legal-review boundary.

**WI-4 — `resolve_context_classification` (pure resolver).**
Precedence ladder, fail-closed, subcategory landing, and the three-way outcome including `PROHIBITED_HALT`. No writes. Mirrors `resolve_classification()`'s read-only contract.

**WI-5 — `get_context_questions` / residual computation (pure read).**
Returns the **residual** question set for the current `tree_version` = required-to-resolve **minus** catalogue prefill **minus** answers already supplied by the caller. The node does **not** read intake-context storage; the orchestrator supplies intake-derived answers (see §10). From-scratch (`REQUIRES_CONTEXT`, nothing supplied) yields the full ladder as the worst case.

**WI-6 — Compute-and-record service + transaction.**
Single transaction: pre-check → `resolve_context_classification(...)` (pure) → if `UNRESOLVED` write nothing (`eu_tier` stays `UNCLASSIFIED`) → else flip prior `is_current=false`, insert new snapshot (`version = prior+1`, `is_current=true`, `status = PENDING_REVIEW`, `tier`, `proposed_tier`, `overridden`, `rationale`, `answers_blob`, `basis_*`) → stage `AuditEvent` (`classification.created`) → commit. **Override variant (gated to `system_owner`):** chosen tier ≠ computed → `overridden=true`, `proposed_tier`=engine result, `tier`=user choice, `USER_AMENDED`, justification on the `AuditEvent` (`classification.overridden`). **No `eu_tier` stamp here** — it is not yet signed off.

**WI-7 — Reviewer sign-off action + transaction.**
Single transaction, **gated to `reviewer`**: load the current `PENDING_REVIEW` snapshot → set `status = APPROVED` → stamp `use_case.eu_tier` with the approved tier → stage `AuditEvent` (`classification.signed_off`, with reviewer attribution) → commit. This is the authoritative ratification.

**WI-8 — API endpoints + schemas.** Per §11. Schemas in `app/schemas/`.

**WI-9 — Catalogue confirmation diff (separable).**
Extends WI-5 to build the candidate set from `ProductCategoryEUMapping`, prefill the primary as `CATALOGUE_CURATED`, and serve only disambiguating questions. Deferrable to a fast-follow.

---

## 7. Constraints / non-negotiables

- **Determinism:** `(tree_version, answers)` resolves identically every time.
- **Precedence over ordering:** highest asserted rung wins.
- **Prohibited hard stop is surfaced, not silent:** `PROHIBITED` yields the distinct `PROHIBITED_HALT` outcome with reasoning; override only via the audited `system_owner`→Reviewer path.
- **Fail closed:** `UNRESOLVED` → no snapshot, `UNCLASSIFIED`, never `MINIMAL`.
- **Snapshots hold real tiers only:** `classification.tier ∈ {PROHIBITED, HIGH, LIMITED, MINIMAL}`.
- **`use_case.eu_tier` = the Reviewer-approved tier.** Stamped only at sign-off (WI-7), in the same transaction; reads `UNCLASSIFIED`/pending until then. This enforces §1.5 **and** SoD at the data layer — a computed-but-unreviewed judgement never reads as authoritative.
- **One source of truth:** the `classification` snapshot; `use_case.eu_tier` is its mirror once approved.
- **Provision vs judgement separation:** compute/override = 1st line; sign-off = `reviewer`. Enforced by route gating; SoD conflicts trusted from assignment time (WKF-5), not re-checked.
- **Read/write separation:** resolver pure; writes caller-owned.
- **Atomic audit (tenant plane):** each write commits its `AuditEvent` in the same transaction; never separately. No external-call ordering.
- **Append-only versions; mutable status:** re-computation inserts a new version and flips `is_current`; sign-off mutates `status` on the current row (consistent with the existing `is_current` flip) and is backed by the immutable sign-off `AuditEvent`.
- **Concurrency:** `uq_current_classification` is the guard; a racing writer hits the unique violation and retries.
- **Reference vs tenant boundary:** decision-tree definition global (no RLS); answers tenant-scoped in `answers_blob` under RLS.
- **Node assumes post-clearance invocation:** gate 1 (vendor/product) is the orchestrator's hold; the node does not check vendor clearance.

---

## 8. Acceptance criteria

- [ ] A use case with sufficient supplied answers resolves to a tier; WI-6 writes a `PENDING_REVIEW` snapshot and **does not** stamp `use_case.eu_tier`.
- [ ] A `reviewer` sign-off (WI-7) flips `status` to `APPROVED` and stamps `use_case.eu_tier`; before sign-off, `eu_tier` remains `UNCLASSIFIED`/pending.
- [ ] `resolve_context_classification` is pure, deterministic across repeated calls, and performs no writes.
- [ ] Precedence holds for each pair (`PROHIBITED>HIGH`, `HIGH>LIMITED`, `LIMITED>MINIMAL`), irrespective of answer order.
- [ ] `PROHIBITED` answers yield the `PROHIBITED_HALT` outcome with rationale; after sign-off, `use_case.eu_tier = PROHIBITED`.
- [ ] Incomplete answers → `UNRESOLVED`, no snapshot, `eu_tier = UNCLASSIFIED`; never `MINIMAL`. A completed-but-non-terminal answer set fails loud and persists nothing.
- [ ] `classification.tier` is never written as `UNCLASSIFIED`.
- [ ] Subcategory-identifying answers populate `basis_subcategory_code` + `basis_legal_ref`; non-identifying answers resolve a tier with null basis.
- [ ] Each write commits its snapshot/stamp and `AuditEvent` in one transaction; an injected commit failure rolls back all of it (no partial state, no orphan audit).
- [ ] `answers_blob` pins `tree_version` and is self-contained (per §11).
- [ ] Two concurrent computes on one use case never yield two `is_current=true` rows; the loser retries.
- [ ] **Authorisation:** compute/override rejected (403) for non-first-line and for a `contributor` attempting override (override requires `system_owner`); sign-off rejected (403) for any non-`reviewer`, including first-line; reads succeed for all five roles.
- [ ] The node does not re-check SoD conflicts; role gating is sufficient given assignment-time enforcement.
- [ ] Seed loader: idempotent on unchanged content; inserts on a bumped version; fails loud on changed content under an existing version.
- [ ] **(WI-9)** Catalogue-linked use case: primary subcategory prefilled `CATALOGUE_CURATED`, only disambiguators served; refine-to-sibling records `USER_CONFIRMED`.

---

## 9. Out of scope

- **The cross-gate state machine / orchestrator** and **gates 1, 3, 4, 5** (vendor/product, assessment, treatment, authorisation).
- **Halt enforcement** ("do not advance to assessment" on `PROHIBITED`) — orchestrator, and moot (no assessment gate yet).
- **JIT-vs-curation routing and legible multi-gate status** — orchestrator. The node only emits an outcome (+ reason) for it to consume.
- **Review infrastructure (WKF-2/3/4):** queue, comment threads, request-changes flow, notifications, the full draft→in-review→approved→needs-refresh richness. Only the minimal Reviewer **approve** action is in.
- **Intake-context → answers mapping.** The node accepts caller-supplied answers and does catalogue prefill; deriving answers from captured intake context is the orchestrator's job (see §10).
- **The AIIA itself (Sprint 3)** — classification front-loads it; persist its input data, build none of its logic.
- **AI-assisted classification suggestion** (`AI_SUGGESTED` path); **tenant-customised trees**; **multi-framework resolution**; **per-system role scoping** (additive later — WKF-7; the gate is scope-agnostic by construction).
- **WI-9** may be deferred to a fast-follow if WI-3 content slips.

---

## 10. Dependencies / decision notes

**Verify before WI-7:**
- **`use_case.eu_tier`** (`eu_ai_act_tier`, nullable) is assumed to exist (inferred from the shared enum). The sign-off stamp depends on it. If absent, add additively. Optional hardening: `NOT NULL DEFAULT 'UNCLASSIFIED'` and collapse the `NULL` vs `UNCLASSIFIED` ambiguity.

**Additive schema deltas this sprint:**
- New reference tables (WI-1).
- **`classification.status`** — new enum column (`PENDING_REVIEW`, `APPROVED`; `CHANGES_REQUESTED` / `NEEDS_REFRESH` reserved for the workflow track). Default `PENDING_REVIEW` on compute.
- **New action string `classification.signed_off`** (the only new one; `classification.created` and `classification.overridden` are reused).
- No new tenant answer table — `answers_blob` holds the answers.

**Integration seams:**
- The orchestrator supplies intake-context-derived answers to WI-5/WI-6; the node treats them as caller-supplied answers and computes the residual against them plus catalogue prefill. The node does not read intake-context storage.
- `require_governance_role(...)` must accept a role set (first-line set for compute; `reviewer` for sign-off; `system_owner` for override; all five for reads). Confirm the signature.
- Reuse `resolve_classification()` for the bridge traversal and `ProductCategoryEUMapping` for the candidate set (WI-9).

**Locked decisions (do not relitigate):**
- Node, not orchestrator; gate 2 only.
- Prohibited hard stop is a first-class, in-scope, surfaced outcome (enforcement deferred).
- Provision (1st line) vs judgement (Reviewer sign-off) separation; `eu_tier` stamped at sign-off, not compute.
- Computed tier carries no distinct provenance; provenance tags answers.
- Tree-version pin-and-resolve.
- SoD trusted from assignment time; not re-checked in the node.

**Optional hardenings:** `CHECK (tier <> 'UNCLASSIFIED')` on `classification`; `UNIQUE (use_case_id, version)` for version monotonicity.

---

## 11. Implementation contract

### Services (pure reads)

```
get_context_questions(use_case, supplied_answers) -> QuestionSet
    # residual = required(tree_version) - catalogue_prefill - supplied_answers
    # WI-9 adds candidate-set prefill. No writes.

resolve_context_classification(answers, tree_version)
    -> Outcome{ kind, tier, subcategory_code | None, rationale, missing }
    # kind ∈ {UNRESOLVED, RESOLVED, PROHIBITED_HALT}. Fail-closed; no writes.
```

### Compute-and-record (WI-6) — transaction, no external call

```
1. Pre-check: use case exists; tree_version is servable/pinned.
2. resolve_context_classification(answers, tree_version)   # pure
3. UNRESOLVED -> commit nothing; eu_tier stays UNCLASSIFIED; return outcome
4. RESOLVED | PROHIBITED_HALT:
     - UPDATE prior current row SET is_current = false
     - INSERT snapshot(version = prior+1, is_current = true,
         status = PENDING_REVIEW, tier, proposed_tier, overridden,
         rationale, answers_blob, basis_subcategory_code, basis_legal_ref)
     - stage AuditEvent(classification.created | classification.overridden)
     # NOTE: no eu_tier stamp here
5. COMMIT atomically            # uq_current_classification guards races
```

### Reviewer sign-off (WI-7) — transaction, gated to `reviewer`

```
1. Load current snapshot for use_case (is_current = true, status = PENDING_REVIEW)
2. UPDATE that row SET status = APPROVED
3. UPDATE use_case SET eu_tier = <approved tier>
4. stage AuditEvent(classification.signed_off, actor = reviewer)
5. COMMIT atomically
```

### `answers_blob` shape (self-contained; tree_version pinned)

```json
{
  "tree_version": "<version>",
  "resolution": "FROM_SCRATCH | CATALOGUE_CONFIRMED",
  "outcome": "RESOLVED | PROHIBITED_HALT",
  "resolved_rung": "PROHIBITED | HIGH | LIMITED | MINIMAL",
  "resolved_subcategory_code": "<code | null>",
  "answers": [
    { "question_code": "...", "question_text": "...",
      "option_code": "...", "option_label": "...", "legal_ref": "...",
      "asserts": "rung:HIGH | subcategory:<code>",
      "provenance": "CATALOGUE_CURATED | USER_CONFIRMED | USER_AMENDED" }
  ]
}
```

### Status lifecycle (this sprint)

`PENDING_REVIEW` (on compute) → `APPROVED` (on Reviewer sign-off). `CHANGES_REQUESTED` and `NEEDS_REFRESH` are reserved for the workflow track.

### API (under `/v1`; `tenant_id = ctx.tenant_id`; schemas in `app/schemas/`)

| Endpoint | Method | Purpose | Gate (`require_governance_role`) |
|---|---|---|---|
| `/v1/use-cases/{id}/classification/context` | GET | Residual question set (+ candidate set/prefill in WI-9) and current outcome | all five roles |
| `/v1/use-cases/{id}/classification/context/preview` | POST | Resolve supplied answers **without persisting**; returns outcome + rationale | all five roles |
| `/v1/use-cases/{id}/classification/context` | POST | Submit answers → compute → write `PENDING_REVIEW` snapshot | `system_owner`, `contributor` |
| `/v1/use-cases/{id}/classification/sign-off` | POST | Reviewer approves current pending classification → `APPROVED` + stamp `eu_tier` | `reviewer` |

- Override is a variant of the compute `POST`: when chosen tier ≠ computed tier, the service additionally asserts `system_owner`, else `403`.
- Reads and preview perform no writes and carry no override/sign-off semantics.

---

## 12. Execution protocol

1. **Read before writing.** Study `provision_member`/`provision_tenant` for the transaction/audit idiom, an existing `app/routers/v1/` router and `app/schemas/` for conventions, the `classification` model, and existing YAML reference loaders. Match them.
2. **Additive only.** New reference tables, the `classification.status` column, the `classification.signed_off` action, new services/endpoints. The only touches to existing tables are `classification.status` (additive) and the `use_case.eu_tier` stamp on sign-off.
3. **Headless node — no user-wizard assumptions.** Endpoints are the node's callable interface; do not build queueing, notifications, or multi-gate status. Do not read intake-context storage; accept caller-supplied answers.
4. **Sequence:** WI-1 → WI-2 → WI-4 → WI-5 → WI-6 → WI-7 → WI-8. WI-3 in parallel; WI-9 last or deferred.
5. **One gate per route. SoD is not re-checked** — trust assignment-time enforcement.
6. **Honour fail-closed and the hard stop everywhere.** Never write a tier for `UNRESOLVED`; never let `MINIMAL` be a fallback; always surface `PROHIBITED_HALT` distinctly.
7. **Keep the resolver pure.** No DB access inside `resolve_context_classification`; the caller owns the transaction.
8. Where a fact is unverified (§10), confirm against the codebase before depending on it; invent no columns or signatures.

---

## 13. Validation protocol

**Unit (resolver, pure):** precedence for each adjacent pair irrespective of order; determinism with no writes; fail-closed (incomplete → `UNRESOLVED`, never `MINIMAL`); defect path (complete, no terminal → fails loud); `PROHIBITED` → `PROHIBITED_HALT`; subcategory landing populates / nulls basis correctly.

**Integration (compute, WI-6):** resolution writes exactly one new `is_current`, `PENDING_REVIEW` snapshot, flips the prior, stages one `AuditEvent`, and does **not** stamp `eu_tier`; injected commit failure rolls everything back; `classification.tier = UNCLASSIFIED` never produced; concurrency yields a single current row with the loser retrying; override records `overridden`/`proposed_tier`/`tier`/`USER_AMENDED` + justification on the `AuditEvent`.

**Integration (sign-off, WI-7):** Reviewer approval flips `status` to `APPROVED`, stamps `eu_tier`, and stages `classification.signed_off` with reviewer attribution, atomically; a prohibited classification, once signed off, leaves `eu_tier = PROHIBITED`.

**Authorisation:** compute/override → `403` for non-first-line and for `contributor`-only override; sign-off → `403` for any non-`reviewer` including first-line; context/preview → 200 for all five roles.

**Seed loader:** no-op on unchanged content; new rows on a bumped version; fail loud on changed content under an existing version.

**(WI-9):** catalogue-linked use case prefills the primary subcategory `CATALOGUE_CURATED`, serves only disambiguators; refine-to-sibling records `USER_CONFIRMED`.

**End-to-end:** supplied answers → compute (`PENDING_REVIEW`, `eu_tier` pending) → Reviewer sign-off (`APPROVED`, `eu_tier` stamped) → snapshot reproducible against its pinned `tree_version`.