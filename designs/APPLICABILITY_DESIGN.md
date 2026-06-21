# Sprint 7a — Control Coverage View — Design Document

**Status:** design · **v1.1, review dispositioned** · ready for handoff once Appendix B B1–B4 clear
**Classification:** additive · read-only · zero migrations · no new model · no new enum · no new DB role
**Sprint 7 arc:** 7a coverage view (this doc) → applicability layer (separate track, deferred) → 7b export pack
**Verification basis:** V1–V4 verified against live DDL (in-thread); V5–V8 open (Appendix B), gating the handoff, not the design
**Changes from v1.0:** V2 + `Control` fields closed from DDL; `NEEDS_REFRESH` made explicit (D4/A#6); inv 31 snapshot rationale stated; clause-axis promoted to ship in 7a (A#4); inv 39 wording reconciled; D5→7b consequence recorded

---

## 1. Context & objective

PRD §4.6 CTL-3: "per framework, show which controls are satisfied, partial, or open." This is the payoff of the cross-mapping investment (CTL-1/CTL-2): assessment items were linked to controls, and controls are mapped across frameworks, so the platform can express a programme-level compliance posture for ISO 42001 and the EU AI Act simultaneously.

7a is the read-only coverage engine. It is deliberately the smallest, lowest-risk unit of Sprint 7 and ships **before** the applicability layer, carrying an explicit, honest limitation: it reports *how well addressed* a control is, but cannot yet say *which controls ought to apply* to a given use case. §4.5 records that gap and how it is presented without overstating posture; §8 records where it is filled.

**Why 7a does not wait on applicability.** The applicability layer is two mechanisms with their own scope, default direction, and persisted override state (EU-derived per-use-case obligation set; ISO-declared tenant SoA — §8). Coupling them into 7a would inflate a read-only feature into a multi-table, §1.5-tracked build. Coverage is useful without it and is upgraded by it additively, so 7a ships interim; applicability replaces the denominator later.

---

## 2. Resolved decisions

| # | Decision | Rationale | PRD/inv anchor |
|---|---|---|---|
| D1 | Coverage is recomputed per request, never persisted. | A coverage verdict is a function of current links; persisting it creates a second source of truth that drifts. Mirrors `full_vector`/rollup. | inv 25 |
| D2 | **No propagation.** A control's single verdict projects across every `(framework, clause_ref)` it maps to. | DDL shows `control` is framework-agnostic and *multi-homed* via `control_framework_map` (single `control_id` + `(framework, clause_ref)`; no control↔control pairing). CTL-2 is achieved structurally — the same control under two clause refs — so there is no inter-control inference to design. | PRD §4.6 CTL-2; §7 V2 |
| D3 | Qualifying-link filter excludes links on items whose provenance is `AI_SUGGESTED`. | Control-linking is *not* disposition-gated (inv 20), so links on undispositioned items genuinely exist; they are proposals, not evidenced coverage. | inv 13, 20 |
| D4 | Approved-only headline (`include_unapproved=false`); approval resolved via the **governing AIIA** (`parent_aiia_id` for feeder items), never the item's own assessment status. Governing status `APPROVED` only — `DRAFT` and `NEEDS_REFRESH` are excluded from the headline. | Feeder `status` stays `DRAFT` for the AIIA's whole review lifecycle (6a), so testing a feeder's own status would exclude every feeder item — the check must climb to the AIIA, as the authoring lock does. `NEEDS_REFRESH` (a reopened, now-stale approval) must not count toward *current* posture. | 6a; inv 31; §4.2 |
| D5 | Coverage counts **disposition, not evidence-backing**: a `SATISFIED` link counts without a linked evidence row. | A material share of ISO 42001 Annex A controls are satisfied by documented process, not an artifact; requiring evidence would understate them. **Consequence:** this flows into 7b's export coverage section, so the tighten decision must be settled before export is audit-graded (A#1, A#3). | Appendix A #1 |
| D6 | Rolled-up verdict = `{OPEN,PARTIAL,SATISFIED}` (DB labels) + response-only `UNADDRESSED` (zero links). Not a DB enum. | `coverage_status` has no `UNADDRESSED`/`NOT_APPLICABLE` label; the rolled-up value is a computed superset living only in the response. | §7 V1 |
| D7 | `coverage_status` having no `NOT_APPLICABLE` confirms coverage and applicability are **orthogonal axes**. N/A belongs solely to the applicability layer. | A link asserts *how well evidenced*, never *whether it applies*. No conflict with `SectionApplicability` (AIIA-section scope, not control scope). | §8 |
| D8 | 7a interim denominator = controls **in play** (≥1 qualifying link) for the primary matrix, **plus** a flat `unaddressed_controls` list flagged `not_an_obligation_set`. | Whole-library denominator falsely claims a minimal-risk use case is "failing" high-risk controls; linked-only hides gaps. The flagged list shows gaps without asserting obligation. | §4.5; §8 |
| D9 | Control-axis matrix is the primary deliverable; the framework/clause re-pivot **ships in 7a** (promoted from Should). | The control-axis answers CTL-3; the clause-axis ("is Art. 9 covered?") closes the stronger "framework as first-class axis" reading of CTL-3 at negligible cost (same data re-keyed). | PRD §4.6 CTL-3; A#4 |
| D10 | No audit event. | Coverage is a pure read, not a custody/disclosure act. (Contrast: 7b's export *does* stage `export.generated`.) | reads emit no audit |

---

## 3. Reuse (no foundation is reinvented)

| Existing | Reused for |
|---|---|
| `Control` (`code`, `title` confirmed), `control_framework_map` | Control universe + framework projection (D2) |
| `assessment_item_control` (`coverage`, RLS, `tenant_id`) | The per-link coverage facts the roll-up consumes |
| `assessment_item.provenance` | Disposition filter (D3) |
| `Assessment.status` + `parent_aiia_id` | Governing-AIIA approval resolution (D4) |
| `GET /systems/{id}/rollup`, `/portfolio` | Precedent for scope-keyed read aggregation that never persists; reuse the "any governance role" read gate (B4) |
| `irontrustai_app` + RLS | Coverage runs here; no new role, no migration (inv 4) |

---

## 4. Coverage semantics

### 4.1 Scope → contributing item set

Three scopes, one resolver, all under RLS:

- `tenant`: all `assessment_item` in the tenant (RLS scopes it).
- `system`: items of assessments under the system's use cases — AIIAs **and** their feeders, reached `feeder item → parent_aiia_id → AIIA.use_case_id → system` (B1: confirm feeder `use_case_id` population; the `parent_aiia_id` path must hold regardless).
- `assessment`: `:id` must be an AIIA (`type=AIIA`); items where `assessment.id=:id OR parent_aiia_id=:id`. A feeder id is rejected (422) — a feeder in isolation is not a use-case-assessment unit.

### 4.2 Qualifying-link filter

A link counts iff (a) its item's provenance ≠ `AI_SUGGESTED` (D3), and (b) under the default, the item's **governing AIIA** status is `APPROVED` (D4). The governing AIIA is the item's own assessment if `type=AIIA`, else the assessment at `parent_aiia_id`.

- **`NEEDS_REFRESH` and `DRAFT` are excluded from the headline.** `include_unapproved=true` admits both; each contributing ref carries its governing-AIIA status, so a consumer distinguishes stale-but-previously-approved (`NEEDS_REFRESH`) from never-approved (`DRAFT`). A dedicated stale-only toggle is a possible later refinement, not built in 7a.
- **The link row carries no provenance/timestamp/lock_version (§7 V3); both predicates are read off the *item* and its governing assessment.** This is sound because of inv 31: `create_control_link` is authoring-locked once the AIIA is `IN_REVIEW`/`APPROVED`, so every link on an approved AIIA necessarily predates approval. "Approved AIIA's links" is therefore a coherent point-in-time snapshot, and the link's missing timestamp is harmless — no link can be added after the approval it would be counted under.

### 4.3 Per-control roll-up

Over qualifying links grouped by control:

```
SATISFIED   if any link == SATISFIED
PARTIAL     else if any link == PARTIAL
OPEN        else (≥1 link, all OPEN)
UNADDRESSED else (zero qualifying links)
```

Most-favourable-wins is intentional: a `SATISFIED` link is a human assertion, in an approved and dispositioned item, that the item satisfies the control; multiple items addressing one control are belt-and-braces or cover different facets. Per §1.5 (shown reasoning), the verdict ships with a `breakdown` — counts by status and the contributing `(item_id, assessment_id, governing_status)` refs — so a reviewer sees what the verdict rests on, including any weaker links behind a `SATISFIED`.

### 4.4 Framework projection (D2)

Each control's verdict projects across its `control_framework_map` rows. A `framework=` filter narrows to controls mapped in that framework and shows only that framework's clause_refs. The unique key `(control_id, framework, clause_ref)` permits both *one control → several clauses in a framework* (all listed, same verdict) and *several controls → one `(framework, clause_ref)`* — so the clause-axis re-pivot (D9, shipped in 7a) rolls a clause up over its backing controls with the same ladder. Every projected row cites a concrete `clause_ref` (`NOT NULL`), giving clause-level specificity. **CTL-3's "per framework" reading is met two ways:** the `framework=` filter + `framework_mappings[]` on the control-axis, and the clause-axis projection as a first-class framework→clause view.

### 4.5 Interim denominator (D8) and its relationship to applicability

The primary matrix reports controls **in play** (≥1 qualifying link) as satisfied/partial/open — `UNADDRESSED` cannot appear here by construction. Separately, `unaddressed_controls` lists every library control (optionally framework-filtered) with zero qualifying links in scope, flagged `not_an_obligation_set: true`. This surfaces gaps without asserting that any listed control is *required*, because 7a has no basis to make that claim. The applicability layer (§8) replaces this flat list with an applicable/excluded partition, at which point `UNADDRESSED` becomes meaningful as "applicable but unaddressed."

---

## 5. API & response model

### 5.1 Schema impact

**No new table, no ALTER, no enum, no migration.** All new types are response (Pydantic) shapes in `app/schemas/` (B4), annotated NEW:

| Type | Status | Fields |
|---|---|---|
| `ControlCoverageRead` | NEW (response) | `control_id, code, title, verdict, breakdown{satisfied,partial,open,contributing_refs[{item_id,assessment_id,governing_status}]}, framework_mappings[{framework,clause_ref}]` |
| `FrameworkClauseCoverageRead` | NEW (response) | `framework, clause_ref, verdict, control_ids[]` |
| `CoverageMatrixRead` | NEW (response) | `scope, scope_id, framework_filter, include_unapproved, controls[], frameworks[], unaddressed_controls[], not_an_obligation_set, generated_at` |

### 5.2 Endpoints

Router `app/routers/v1/coverage.py`, registered under `/v1`; gated by the existing "any governance role" read dependency (the auditor persona consumes coverage read-only — PRD §2; exact dependency name to confirm, B4). No `If-Match`, no audit, no write.

| Endpoint | Scope |
|---|---|
| `GET /v1/coverage` | tenant |
| `GET /v1/systems/{id}/coverage` | system |
| `GET /v1/assessments/{id}/coverage` | AIIA (422 on a feeder id) |

All take `framework=` and `include_unapproved=`.

---

## 6. Invariants

38 and 39 are **new appends** to STATE.md §6 (which currently ends at 37); neither revises an existing STATE invariant.

- **38 (new):** Coverage counts only links on dispositioned items; `UNADDRESSED` is a first-class response verdict, never an omission; approval is tested against the governing AIIA (`parent_aiia_id`) at status `APPROVED` only (`DRAFT`/`NEEDS_REFRESH` excluded from the headline), never a feeder's own perpetual-`DRAFT` status. *(§4.2–4.3; inv 13, 20, 31.)*
- **39 (new):** No inter-control coverage propagation exists or is permitted. Cross-framework satisfaction is **structural** — one multi-homed control projected across its `control_framework_map` rows — not inferred between distinct controls. *(Corrects an earlier design-dialogue framing that posited control↔control propagation; §4.4; PRD §4.6 CTL-2.)*
- **23 (applies):** `coverage`/`provenance`/`status` are filtered through typed ORM columns; labels are uppercase member names, and a raw lowercase `.value` comparison would match zero rows.
- **25 (applies):** Coverage is a recomputed cursor; no endpoint persists a verdict.
- **4 (applies):** Runs on `irontrustai_app` under RLS; no new role; no migration.

---

## 7. Source-verification status

| ID | Fact | Status |
|---|---|---|
| V1 | `coverage_status = {OPEN,PARTIAL,SATISFIED}`, uppercase | **Verified** (`enum_range`, in-thread) |
| V2 | `control` framework-agnostic; cross-framework only via `control_framework_map(control_id, framework, clause_ref)` — single `control_id`, `clause_ref NOT NULL`, unique `(control_id,framework,clause_ref)`, **no control↔control pairing** | **Verified** (`\d control`, `\d control_framework_map`, in-thread) — closes the equivalence-table concern |
| V3 | `assessment_item_control`: `coverage NOT NULL`, RLS, unique `(item_id,control_id)`, control FK `RESTRICT`, item FK `CASCADE`, no provenance/timestamp/lock_version | **Verified** (`\d assessment_item_control`, in-thread) |
| V4 | `Control.code`, `Control.title` exist as named | **Verified** (`\d control`, in-thread) |
| V5 | `ProvenanceConfidence.AI_SUGGESTED` label/case | **Needs verification** (B2) — D3 filter depends on it |
| V6 | Feeder `Assessment` `use_case_id` population vs `parent_aiia_id`-only | **Needs verification** (B1) — drives §4.1 system-scope resolver |
| V7 | `assessment_status` label case for `APPROVED` | **Needs verification** (B3) — D4 filter depends on it (inv 23) |
| V8 | "Any governance role" read dependency name/signature; `app/schemas/` target | **Needs confirmation** (B4) |

---

## 8. Sequencing & forward design

**7a → applicability → 7b.** 7a is independent and ships first. The applicability layer and 7b both consume 7a (the export's coverage section is `coverage_service(scope=system)`); 7b additionally needs the applicability partition to be audit-grade — the open Path A/B question (A#3).

**Applicability — recorded design intent (not specced here).** Two mechanisms, both following the classification-override pattern (derive/declare a default, track the deviation as a domain row + audit event):
- *EU AI Act — derived, per use case:* `tier × operator-role (× subcategory) → applicable clause set`, resolved to controls through `control_framework_map`. Operator role is a first-class axis (EU obligations are role-conditioned; already used for feeder applicability). This is CLS-6.
- *ISO 42001 — declared, tenant-level SoA:* default all-applicable, every exclusion justified and audited.

Open forks for review: the EU/ISO split; EU derivation granularity; and whether applicability precedes the export pack (Path B) or follows it (Path A). A#2–#3.

---

## 9. Edge & failure cases

| Case | Handling |
|---|---|
| Control with zero qualifying links in scope | `unaddressed_controls`, flagged not-an-obligation; never dropped |
| Link on `AI_SUGGESTED` item | excluded (D3) |
| Feeder item under an APPROVED AIIA | **qualifies** despite feeder `status=DRAFT` (D4) — the load-bearing case |
| Feeder item under a DRAFT or NEEDS_REFRESH AIIA | excluded at default; appears under `include_unapproved=true`, tagged with governing status |
| Reopened (`NEEDS_REFRESH`) AIIA | drops from headline (stale ≠ current posture); distinguishable from `DRAFT` via `governing_status` on refs |
| Multi-homed control | one verdict, shown under each framework's clause_ref |
| Clause backed by ≥2 controls | clause-axis rolls up over them |
| `assessment` scope given a feeder id | 422 |
| System with no assessments | empty matrix + full `unaddressed_controls`; `200`, never `404` |
| Cross-tenant links | never counted (RLS); smoke-tested on the real RLS dev DB, not the no-RLS test DB |

---

## 10. Deferred

- **Applicability denominator** (§8) — replaces §4.5's flat list; its own sprint(s).
- **Export / audit pack (7b)** — consumes `coverage_service`; adds `export.generated`, feeder-private-section assembly, evidence manifest, ATO document. Inherits D5's disposition-only coverage unless tightened first (A#1).
- **Evidence-backed coverage** — tighten D5 so `SATISFIED` requires a linked evidence row; policy tunable.
- **Stale-only (`NEEDS_REFRESH`) toggle** — distinct from `include_unapproved`; not built in 7a.
- **Coverage snapshots / trend over time** — out; coverage stays a live cursor.

---

## Appendix A — Open decisions (for review disposition)

| # | Decision | Proposed default | Status |
|---|---|---|---|
| 1 | Count `SATISFIED` without an evidence row? | Yes (D5); **settle before 7b audit-grades the export** | open |
| 2 | EU/ISO applicability split + EU granularity (tier×role min vs +subcategory) | split confirmed; tier×operator-role minimum | open |
| 3 | Applicability before export (Path B) or after (Path A)? | Path A — coverage-now, applicability-next | open |
| 4 | Ship clause-axis re-pivot in 7a or defer? | **ship in 7a** — closes CTL-3's framework-axis reading; cheap | proposed-resolved |
| 5 | Default `include_unapproved`? | `false` (approved-only headline) | proposed-resolved |
| 6 | `NEEDS_REFRESH` handling | exclude from headline; admit under `include_unapproved`; tag `governing_status` on refs | proposed-resolved |

## Appendix B — Source-verification register (gates the handoff)

| # | Item | Action before encoding |
|---|---|---|
| B1 | Feeder `Assessment.use_case_id` population | `\d assessment` / inspect a feeder row; confirm `parent_aiia_id → AIIA.use_case_id → system` path for §4.1 |
| B2 | `ProvenanceConfidence` `AI_SUGGESTED` label/case | `SELECT enum_range(NULL::provenance_confidence)` before the D3 WHERE clause |
| B3 | `assessment_status` `APPROVED` label/case | `SELECT enum_range(NULL::assessment_status)` before the D4 filter (inv 23) |
| B4 | "Any governance role" read dependency name/signature; confirm response schemas land in `app/schemas/` | grep the dependency used by the rollup/portfolio router; confirm per CLAUDE.md "Adding an endpoint" |