# Sprint 7a — Control Coverage View — Execution Handoff

**Pairs with:** `sprint-07a-control-coverage-DESIGN-v1.1.md` (rationale lives there; this is execution-only)
**Status:** ready · additive · read-only · zero migrations · no new model/enum/role
**Mode:** plan mode — propose edits before applying.
**Verifications (B1–B4) resolved:** feeder carries `use_case_id`+`parent_aiia_id`; `provenance_confidence` + `assessment_status` labels UPPERCASE; response schemas → `app/schemas/`; reuse the existing any-governance-role read gate.

---

## §0 — Pre-flight (confirmed values; re-check only if schema moved)

- `coverage_status` = `{OPEN, PARTIAL, SATISFIED}` (UPPER). Bind via typed column, never `.value`.
- `provenance_confidence` labels UPPER → filter excludes `AI_SUGGESTED`.
- `assessment_status` labels UPPER → headline tests `APPROVED`.
- `control` has `code`, `title`; framework membership only via `control_framework_map(control_id, framework, clause_ref)` (single `control_id`, `clause_ref NOT NULL`, unique `(control_id,framework,clause_ref)`).
- `assessment` carries both `use_case_id` and `parent_aiia_id`.
- `assessment_item_control`: RLS `tenant_isolation`, `coverage NOT NULL`, unique `(item_id,control_id)`, no provenance/timestamp/lock_version on the link.
- Any-governance-role read dependency: reuse the one guarding existing all-five-role reads (e.g. `/systems/{id}/rollup`, `/portfolio`, AIIA/evidence reads). Bind the exact symbol from the repo.

---

## §1 — Deliverable

`coverage_service.py` + `app/schemas/coverage.py` + `app/routers/v1/coverage.py` (registered in `app/main.py`). Three read endpoints. Control-axis matrix **and** clause-axis re-pivot both ship. No write, no audit, no migration.

---

## §2 — Scope → contributing item set

| scope | item set |
|---|---|
| `tenant` | all `assessment_item` (RLS scopes the tenant) |
| `system` | `assessment_item` whose `assessment.use_case_id IN (use_case.id WHERE system_id=:id)` — AIIAs **and** feeders uniformly (both carry `use_case_id`); **no** parent climb here |
| `assessment` | `:id` must be `assessment.type=AIIA` (else **422**); items where `assessment.id=:id OR assessment.parent_aiia_id=:id` |

## §3 — Qualifying-link filter

Join `assessment_item_control → assessment_item`. A link qualifies iff:
1. `assessment_item.provenance != AI_SUGGESTED`, **and**
2. **governing-AIIA status** ∈ allowed set.
   - governing AIIA = item's own assessment if `type=AIIA`, else the assessment at `parent_aiia_id`. **Never** the feeder's own status.
   - `include_unapproved=false` (default): allowed = `{APPROVED}`.
   - `include_unapproved=true`: allowed = `{APPROVED, DRAFT, NEEDS_REFRESH}`.
3. Every contributing ref carries its `governing_status`, so `NEEDS_REFRESH` (stale) is distinguishable from `DRAFT` (never approved).

All predicates read off the *item* and its *governing assessment*, never the link row.

## §4 — Per-control roll-up

```
SATISFIED   if any qualifying link == SATISFIED
PARTIAL     else if any == PARTIAL
OPEN        else (≥1 link, all OPEN)
UNADDRESSED else (zero qualifying links)   # response-only, no DB label
```

Emit `breakdown`: `{satisfied, partial, open}` counts + `contributing_refs[{item_id, assessment_id, governing_status}]`.

## §5 — Framework projection

- Control-axis: each control's verdict + `framework_mappings[{framework, clause_ref}]` from `control_framework_map`.
- `framework=` filter: narrow to controls mapped in that framework; show only that framework's clause_refs.
- Clause-axis (ships in 7a): pivot to `frameworks[{framework, clause_ref, verdict, control_ids[]}]`; a clause backed by N controls rolls up over them with the same ladder.
- `unaddressed_controls`: all library controls (optionally framework-filtered) with zero qualifying links in scope; response flag `not_an_obligation_set=true`.

---

## §6 — Service signature

```
compute_coverage(db, *, scope: Literal["tenant","system","assessment"],
                 scope_id: UUID | None,
                 framework: Framework | None = None,
                 include_unapproved: bool = False) -> CoverageMatrixRead
```

- `assessment` scope asserts AIIA type (422 on feeder/non-AIIA id).
- Single grouped query over qualifying links joined to `control` + `control_framework_map`, RLS-scoped; `framework` filtered in SQL when given. No per-control N+1.
- Builds `unaddressed_controls` from `control` minus the in-play set.
- Pure read: no flush, no audit, no persistence.

---

## §7 — Endpoints & schemas

Router `app/routers/v1/coverage.py` → `/v1`; gate = any-governance-role read dependency; no `If-Match`.

| Endpoint | Scope | Query params |
|---|---|---|
| `GET /v1/coverage` | tenant | `framework`, `include_unapproved` |
| `GET /v1/systems/{id}/coverage` | system | `framework`, `include_unapproved` |
| `GET /v1/assessments/{id}/coverage` | AIIA (422 on feeder id) | `framework`, `include_unapproved` |

Schemas → `app/schemas/coverage.py`:
- `ControlCoverageRead`: `control_id, code, title, verdict, breakdown{satisfied,partial,open,contributing_refs[{item_id,assessment_id,governing_status}]}, framework_mappings[{framework,clause_ref}]`
- `FrameworkClauseCoverageRead`: `framework, clause_ref, verdict, control_ids[]`
- `CoverageMatrixRead`: `scope, scope_id, framework_filter, include_unapproved, controls[ControlCoverageRead], frameworks[FrameworkClauseCoverageRead], unaddressed_controls[{control_id,code,title,framework_mappings}], not_an_obligation_set, generated_at`

---

## §8 — Invariants enforced

- **38 (append to STATE §6):** coverage counts only dispositioned-item links; `UNADDRESSED` is a first-class verdict; approval tested against the governing AIIA at `APPROVED` (`DRAFT`/`NEEDS_REFRESH` excluded from headline), never the feeder's own status.
- **39 (append):** no inter-control propagation; cross-framework satisfaction is structural (multi-homed control across map rows).
- **23:** all enum filters bind through typed columns (labels UPPER).
- **25:** recomputed cursor, never persisted.
- **4:** `irontrustai_app` under RLS; no role, no migration.

---

## §9 — Migrations

**None.** If autogenerate proposes anything, stop — the design is read-only.

---

## §10 — Tests

Logic (harness OK):
1. ladder precedence SATISFIED > PARTIAL > OPEN.
2. `AI_SUGGESTED`-item link excluded.
3. zero-link control → `unaddressed_controls`, absent from primary matrix.
4. multi-homed control: same verdict under each framework; `framework=` narrows clause_refs.
5. one control → multiple clauses in one framework: all listed.
6. clause backed by 2 controls: clause-axis rolls over both.
7. `assessment` scope with a feeder id → 422.
8. `breakdown` counts + `contributing_refs` (incl. `governing_status`) correct.

Live RLS/enum DB (mandatory — inv 23/27; no-RLS test DB cannot catch these):
9. feeder item under an **APPROVED** AIIA qualifies (feeder `status=DRAFT`).
10. feeder item under a **DRAFT** AIIA excluded at default; appears under `include_unapproved=true` tagged `DRAFT`.
11. item under a **NEEDS_REFRESH** AIIA excluded at default; appears under `include_unapproved=true` tagged `NEEDS_REFRESH` (distinct from DRAFT).
12. cross-tenant `assessment_item_control` rows never counted (RLS).
13. coverage/provenance/status filters match real UPPER labels.
14. system scope spans multiple use cases and pulls feeder-item links via `use_case_id`.

---

## §11 — Work items (dependency-ordered)

| WI | Item | Depends | Done-check |
|---|---|---|---|
| 0 | confirm §0 values unchanged against live DDL | — | all §0 lines hold |
| 1 | `app/schemas/coverage.py` (three Read types) | 0 | shapes match §7 |
| 2 | scope→item-set resolver (`use_case_id` for system; `id OR parent_aiia_id` for assessment; 422 on feeder) | 1 | tests 7, 14 |
| 3 | qualifying-link filter (provenance + governing-AIIA status via `parent_aiia_id`; `include_unapproved` set) | 2 | tests 2, 9, 10, 11 |
| 4 | per-control roll-up + `breakdown` w/ `governing_status` | 3 | tests 1, 8 |
| 5 | control-axis + clause-axis projection + `framework=` filter + `unaddressed_controls` | 4 | tests 3, 4, 5, 6 |
| 6 | router + `main.py` registration + any-governance-role read gate | 5 | routes return matrix; non-governance rejected |
| 7 | tests incl. live RLS/enum smoke | 6 | tests 12, 13 green on real dev DB |

---

## §12 — Out of 7a

Export pack (7b) · applicability/obligation layer (separate track) · evidence-backed coverage (D5 tighten — settle before 7b audit-grades) · stale-only toggle · coverage snapshots/trend · PDF/branded/auditor-scoped export.