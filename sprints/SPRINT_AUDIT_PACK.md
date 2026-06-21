# Sprint 7b — Export / Audit Pack — Execution Handoff

**Pairs with:** `sprint-07b-export-pack-DESIGN-v1.5.md` (rationale lives there; this is execution-only)
**Status:** ready · additive · read-assembly + one disclosure write · zero migrations · no new model/enum/role
**Mode:** plan mode — propose edits before applying.
**All verification closed (B1–B6).** One pre-flight micro-confirm (§0).

---

## §0 — Pre-flight (verified values; re-check only if schema moved)

- `audit_event`: `entity_type` NOT NULL, `entity_id` nullable+indexed, `occurred_at` indexed, `detail jsonb`, `source_ip inet`, RLS, immutability trigger. `action` is `varchar(120)` → new action string needs **no migration**.
- **action→entity_id**: natural-object key for most; **link-row id** for `control_link.*`/`evidence.linked/unlinked`; **approval-row id** for `vendor/product_approval.*`; assignment/membership ids (outside closure) for `governance_role.*`/`member.created`.
- **audit `detail` back-ref**: `control_link.deleted`(1378)/`evidence.linked`(1437)/`evidence.unlinked`(1470) carry `{item_id, …}`. `assessment.deleted`(1300)/`evidence.access`(206)/`evidence.deleted`(231) carry `{}`.
- **MICRO-CONFIRM:** `control_link.created` (assessment_service.py:1350) carries `item_id` in `detail` (expected, mirrors 1378). If not → add current `assessment_item_control` ids to closure path (a) for created events only.
- link tables hard-delete (no soft-delete column on `assessment_item_control`; evidence-unlink is a real removal).
- `assessment.use_case_id` + `parent_aiia_id`; `classification.use_case_id`; `lifecycle_transition.use_case_id` (+ `from_state/to_state/occurred_at/actor_user_id [SET NULL]/reason/triggered_by`).
- `deployment_authorisation`: `use_case_id, assessment_id, submission_round, tier(varchar), assessment_version, authorised_by_user_id, authorised_by_name/email (nullable), authorised_at, residual_risk_statement`.
- `classification`: `tier, proposed_tier, overridden, rationale, basis_subcategory_code, basis_legal_ref, status, version, is_current` (no sign-off actor column — from audit).
- Enum labels UPPER (`coverage_status, assessment_status, provenance_confidence`); bind via typed columns (inv 23).
- Any-governance-role read gate: reuse the one on existing all-five-role reads.

---

## §1 — Deliverable

`coverage_service.py` **amendment** (D13) + `export_service.py` + `app/schemas/export.py` + `app/routers/v1/export.py` (registered in `main.py`). New audit action `export.generated`. Self-owned REPEATABLE READ export session. No migration, no model, no enum, no new role.

---

## §2 — `coverage_service` amendment (D13) — do first

Add `require_evidence_for_satisfied: bool = False` to `compute_coverage(...)`. When `True`, per qualifying link compute an **effective** status:
- `SATISFIED` + item has ≥1 `assessment_item_evidence` row → effective `SATISFIED`.
- `SATISFIED` + item has **no** evidence → effective `PARTIAL` (downgrade).
- `PARTIAL`/`OPEN` unchanged.

Roll up effective statuses with the existing ladder. Add a **first-class `downgraded_unsubstantiated` count** to `breakdown` (NOT folded into the partial total). Evidence presence is per item: `EXISTS(assessment_item_evidence WHERE item_id = link.item_id)`. Default `False` leaves 7a coverage endpoints unchanged.

**Live-smoke** the new `EXISTS` join on the real RLS dev DB — it's a new path on built code; confirm it is item-scoped under RLS (no-RLS test DB can't catch a tenant miss).

---

## §3 — Pack shapes & endpoints

Router `app/routers/v1/export.py` → `/v1`; gate = any-governance-role read; no `If-Match`. `/authorisation/document` coexists with lifecycle.py's exact `/authorisation`. All stage `export.generated`. **Every export coverage call passes `require_evidence_for_satisfied=True`** (use-case, system, framework).

| Endpoint | Scope |
|---|---|
| `GET /v1/systems/{id}/export` | system: register + every use-case record + system coverage (strict) + system audit closure |
| `GET /v1/use-cases/{id}/export` | one use-case record (§4) |
| `GET /v1/use-cases/{id}/authorisation/document` | ATO basis document (§5); `404` if never authorised |
| `GET /v1/export?framework=` | framework: coverage(framework=, strict) + substantiation manifest |

`framework=` optional on system/use-case shapes.

---

## §4 — Use-case record sections

1. **Register facts** — `SystemDetail` assembly.
2. **Classification history** — `Classification` by `use_case_id` ordered by `version`: `tier, proposed_tier, overridden, rationale, basis_subcategory_code, basis_legal_ref, status`. Sign-off actor from the `classification.signed_off` event in the audit closure (no row column).
3. **Assessment record** — **native AIIA items only** (sections, response, likelihood/severity/residual, mitigation, treatment, provenance), control links, evidence links; **plus each feeder as a complete sub-record incl. feeder-private sections**, each feeder item carrying `surfaces_into` (AIIA `section_key` or null). Do **not** call `assemble_aiia_items`; no re-surface, no dedup (inv 41/16).
4. **Evidence manifest** — deduped, by reference: `id, sha256, filename, content_type, size, back-refs[item_id]`. No bytes, no presigned URLs (inv 40/22).
5. **Coverage** — `coverage_service(scope=assessment, require_evidence_for_satisfied=True)`.
6. **Lifecycle trail** — `LifecycleTransition WHERE use_case_id=:uc ORDER BY occurred_at`: `from_state, to_state, occurred_at, actor (membership join on actor_user_id, nullable), reason, triggered_by`.
7. **ATO(s)** — every `DeploymentAuthorisation` for the use case, each with `live_state`. Actor: prefer text stamps; fall back to membership join on `authorised_by_user_id` when null.
8. **Audit trail** — closure (§6).

---

## §5 — ATO document (EXP-1a)

`DeploymentAuthorisation` row(s); default most recent, `?round=` selects a cycle. Plus the **current** read of the referenced assessment + classification, labelled `basis_is_current_state_not_authorisation_snapshot: true` (inv 44). `404` if never authorised.

---

## §6 — Audit-trail closure (durable-entity OR detail-back-ref)

An event is in scope if **(a)** `entity_id IN` `{use_case_id} ∪ {classification ids} ∪ {AIIA id + feeder ids} ∪ {assessment_item ids} ∪ {deployment_authorisation ids} ∪ {linked-evidence ids} ∪ {vendor/product approval-row ids}` (system pack adds `{system_id}`, unions over use cases) — captures events keyed to surviving entities; **OR (b)** `entity_type IN ('assessment_item_control','assessment_item_evidence') AND detail->>'item_id' IN (in-scope item ids, as text)` — captures control/evidence-link create+delete events surviving the link's hard delete.

Project `action, occurred_at, actor (membership-joined), entity_type, entity_id, detail` — **exclude `source_ip`** (inv 45/D12). ORDER BY `occurred_at`.

Residual (documented, accepted): `assessment.deleted` (pristine-only, `detail={}`) and `evidence.access` on since-unlinked evidence (`detail={}`). `evidence.deleted` correctly out of scope (delete guard ⇒ unlinked).

---

## §7 — Service & transaction

```
build_use_case_export(db, use_case_id, *, framework=None) -> UseCaseExportRead
build_system_export(db, system_id, *, framework=None) -> SystemExportRead
build_ato_document(db, use_case_id, *, round=None) -> AtoDocumentRead
build_framework_export(db, framework) -> FrameworkExportRead
```

**Session shape (the `evidence_service` precedent — STATE §4 third shape):** the route depends on `get_tenant_context` (no session), **not** `get_tenant_db`. The service opens its **own** session, sets `execution_options(isolation_level="REPEATABLE READ")` at acquisition (before the first query), then `SET LOCAL app.current_tenant` from `ctx.tenant_id`, assembles, computes canonical `content_hash`, stages `export.generated`, and **owns the commit**. Never raw `SET TRANSACTION` after `SET LOCAL`.

- **`content_hash`:** canonical JSON (sorted keys, ISO-8601 UTC, no insignificant whitespace), computed **before** staging so it lands in `export.generated.detail` (with scope, scope_id, framework_filter, manifest summary).
- **Live-smoke** (inv 27 cousin): the `execution_options`-then-`SET LOCAL` order, and that RLS reads return rows (not silent-zero), on the real dev DB.

---

## §8 — Schemas (`app/schemas/export.py`, all NEW response shapes)

`UseCaseExportRead, SystemExportRead, AssessmentExportRead/FeederExportRead (incl. surfaces_into), EvidenceManifestEntryRead, LifecycleTrailEntryRead, AuditTrailEntryRead, AtoDocumentRead, FrameworkExportRead`. Coverage `breakdown` includes `downgraded_unsubstantiated`.

---

## §9 — Invariants

- **40** evidence by manifest only; **41** native AIIA items only, no `assemble_aiia_items`, no re-surface/dup; **42** stages `export.generated`; **43** live cursor + canonical `content_hash`; **44** ATO-basis honesty; **45** audit closure = durable-entity-id OR detail-back-ref (ephemeral/removal via `detail.item_id`), `source_ip` excluded.
- **23** typed-column enum binding; **25** live recompute; **4** `irontrustai_app` under RLS, no role/migration; **2/34** actor via membership; **27 cousin** SET LOCAL ordering on the self-owned session.

---

## §10 — Migrations

**None.** New audit action is a text value. If autogenerate proposes anything, stop.

---

## §11 — Tests

Logic:
1. strict coverage: `SATISFIED`+evidence → satisfied; without → `PARTIAL`; `downgraded_unsubstantiated` count distinct from partial total.
2. strict downgrade doesn't yield `UNADDRESSED` when the only link was an unevidenced `SATISFIED`.
3. 7a coverage endpoints unchanged (default `False`); strict passed on use-case/system/framework export.
4. AIIA section = native items only; feeder-private sections present w/ `surfaces_into`; no duplication.
5. evidence manifest deduped, by reference, no URLs/bytes.
6. ATO document: most-recent default, `?round=`; `404` never-authorised; basis labelled current-state.
7. never-authorised / `halted_prohibited` / empty-system → `200` with empties, never `404`.
8. `content_hash` stable across identical-state generations; changes on state change.
9. **closure removal-pair:** link a control + an evidence to an item, then unlink both → the export audit trail shows all four events (create + delete of each), via `detail.item_id` (the rows are gone).

Live RLS/enum DB (mandatory — inv 23/27):
10. self-owned export session: `execution_options`→`SET LOCAL` order holds; RLS reads return rows (no silent-zero).
11. strict-mode `EXISTS(assessment_item_evidence …)` join is item-scoped under RLS.
12. closure path (b) excludes other use cases' link events (`detail.item_id` filter is exclusive).
13. cross-tenant rows never assembled; enum projections match UPPER labels.

---

## §12 — Work items (dependency-ordered)

| WI | Item | Depends | Done-check |
|---|---|---|---|
| 0 | confirm §0 (incl. the control_link.created:1350 micro-confirm) | — | all hold |
| 1 | `coverage_service` strict mode + `downgraded_unsubstantiated` | 0 | tests 1,2,3,11 |
| 2 | `app/schemas/export.py` | 0 | shapes per §8 |
| 3 | self-owned REPEATABLE READ export session (execution_options→SET LOCAL→owns commit) | 0 | test 10 (live) |
| 4 | feeder-private assembler (native items + feeder sub-records + `surfaces_into`) | 2 | test 4 |
| 5 | evidence manifest + lifecycle trail + classification history + ATO assemblers | 2,4 | tests 5,6 |
| 6 | audit closure (a) entity-ids ∪ (b) `detail->>'item_id'` | 2 | tests 9,12 (live) |
| 7 | `export_service` build_* (assemble → canonical content_hash → stage → commit) | 1,3,4,5,6 | test 8 |
| 8 | router + `main.py` + any-governance-role gate | 7 | tests 6,7 |
| 9 | tests incl. live RLS/enum/isolation smoke | 8 | tests 9–13 green on real dev DB |

---

## §13 — Out of 7b

PDF render (EXP-1 half — JSON only) · branded export (EXP-3) · auditor-scoped access (EXP-2) · frozen/persisted export artifacts + history · async/streamed export · AIIA-versioned ATO-basis reconstruction · applicability layer (separate track).