# DM-S1 — Context Relocation — Execution Handoff

**Execution-only.** Rationale, rejected alternatives, and review history live in `DM-S1-context-relocation-design.md`. Do not originate design here (INV-68): if a work item seems to need a visual, layout, or behavioural choice not specified, stop and flag. Genuine build defects (failing migration, import break) are exempt.

**Mint floors:** D ≥ 62, INV ≥ 75, FE ≥ 27. New ids this sprint: D-63, D-64, INV-76, INV-77, DF-D1-1..4. Never renumber a live id.

---

## §0 — Pre-flight (binding; run before any code; halt on divergence)

- **P-0:** confirm HEAD; floors D ≥ 62 / INV ≥ 75 / FE ≥ 27.
- **P-1 (run FIRST — it drives the cutover):** grep `usage_context_id`, `human_oversight_type_id`, `SystemDataCategory`, `SystemAffectedParty`, `system_data_category`, `system_affected_party`, `data_categories`, `affected_parties` across `app/` and `apps/tenant/`. Confirm every hit is covered by a work item below (the set: `system_service`, `assessment_service`, `export_service`, the system/use-case schemas, `intake-capture-step.tsx`, `wizard-state.ts`, `use-case-create-step.tsx`, `SystemDetailClient`). **Any hit not covered → stop and escalate.**
- **P-2:** confirm `resolve_classification` and the context gate read none of the four.
- **P-3:** confirm `prefill_service` is catalogue-only.
- **P-4:** confirm `SystemRead` carries none of the four.
- **P-5:** capture existing-data shape: `system_data_category` / `system_affected_party` row counts, systems carrying the two FKs, use-case count per such system.
- **P-6:** confirm the live RLS posture of the system join tables; confirm the access path for the new tables.
- **P-7:** confirm MODEL_RISK feeder reads `system.catalogue_product_id` (stays), so only DPIA/FRIA change.

---

## Work items (dependency-ordered)

### WI-1 — Migration
- Add `use_case.usage_context_id` (FK `usage_context`, nullable, `ON DELETE SET NULL`), `use_case.human_oversight_type_id` (FK `human_oversight_type`, nullable, SET NULL).
- Create `use_case_data_category` (`id`, `tenant_id` FK `tenant`, `use_case_id` FK `use_case` CASCADE, `data_category_id` FK `data_category` CASCADE; unique `(use_case_id, data_category_id)`) **with an RLS policy `tenant_id = current_setting(...)`** matching the tenant-scoped table pattern. Create `use_case_affected_party` analogously (`affected_party_id`).
- Backfill: for each `use_case`, copy its system's `usage_context_id` / `human_oversight_type_id`; insert `use_case_data_category` rows from the parent's `system_data_category` and `use_case_affected_party` from `system_affected_party`, setting `tenant_id` from `use_case.tenant_id`.
- Drop `system.usage_context_id`, `system.human_oversight_type_id`; drop tables `system_data_category`, `system_affected_party`.
- Down-path: re-create the system columns/tables and aggregate; mark it a best-effort dev reversal (lossy after use-case divergence), not a true inverse.
- **Done:** `alembic upgrade`/`downgrade` clean on a seeded dev DB; backfilled rows present; system columns/tables absent; `pg_policies` shows RLS on both new tables.

### WI-2 — Models
- `UseCase`: add the two FK columns and `data_categories` / `affected_parties` relationships to new `UseCaseDataCategory` / `UseCaseAffectedParty` (carry `tenant_id`, `use_case_id`, link id). Remove all four from `System`.
- **Done:** models import; relationships load on a use case.

### WI-3 — Schemas
- `SystemCreate`, `SystemUpdate`: remove `usage_context_id`, `human_oversight_type_id`, `data_category_ids`, `affected_party_ids`.
- `SystemDetail`: remove `usage_context`, `human_oversight_type`, `data_categories`, `affected_parties`.
- Use-case create/update schema: add `usage_context_id`, `human_oversight_type_id`, `data_category_ids`, `affected_party_ids`. Use-case read schema: add resolved `usage_context`/`human_oversight_type` (`VocabItemOut`), `data_categories` (`DataCategoryOut`), `affected_parties` (`AffectedPartyOut`).
- `SystemRead`: unchanged.
- **Done:** `SystemCreate` no longer accepts the four; use-case create accepts them; `SystemDetail` omits them; use-case read returns them.

### WI-4 — `system_service`
- `create_system` / `update_system`: stop writing the four.
- `_load_system_full`: drop the two `selectinload`s.
- `_build_detail` / `get_system_detail`: stop assembling the four.
- Move `_replace_data_categories` / `_replace_affected_parties` to the use-case service, rekeyed on `use_case_id`, setting `tenant_id`.
- **Done:** `get_system_detail` returns without the four; `create_system` ignores them if passed.

### WI-5 — Use-case service
- Create/update writes `usage_context_id`, `human_oversight_type_id`; replaces `use_case_data_category` / `use_case_affected_party` rows with `tenant_id` set.
- **Done:** `POST /v1/use-cases` with the four persists them on the created use case.

### WI-6 — `assessment_service` feeder retarget
- DPIA feeder snapshot: read `UseCaseDataCategory where use_case_id` (was `SystemDataCategory where system_id`); `source_ref` → `use_case_data_category:{id}`.
- FRIA feeder snapshot: read `UseCaseAffectedParty`; `source_ref` → `use_case_affected_party:{id}`.
- DPIA applicability/basis: recompute from the use case's own categories — `has_special_category` → required + special-category basis; `has_data_category` → required + personal-data basis; else NOT_APPLICABLE.
- MODEL_RISK: leave untouched.
- **Done:** use case with a special-category data category → DPIA applicability required with special-category basis and the DPIA feeder pre-fills items from `use_case_data_category`; use case with no data categories → DPIA NOT_APPLICABLE; FRIA pre-fills from `use_case_affected_party`; `source_ref` uses the new strings; existing feeder tests retargeted and green.

### WI-7 — `export_service`
- `_use_case_record`: source the four from the use case.
- `build_system_export` / `get_system_detail`: no longer carry the four at system level.
- **Done:** the per-use-case export record carries the four; the system-level export shape is minus the four; `content_hash` recomputes without error.

### WI-8 — Frontend thread
- `intake-capture-step.tsx`: remove the four from the `SystemCreate` body; write them into wizard state.
- `wizard-state.ts`: carry the four across steps.
- `use-case-create-step.tsx`: add the four to the `POST /v1/use-cases` body.
- `SystemDetailClient`: move the four from system-level display to per-use-case display.
- **Done:** a full intake run (system step → use-case step) lands the four on the **created use case**, asserted end-to-end; the system detail page no longer shows them at system level.

### WI-9 — Classifier (assert untouched)
- No change to `resolve_classification` or the context gate.
- **Done:** classification tests green and unchanged; an assertion confirms the four are not read in tiering.

### WI-10 — Isolation
- **Done:** a cross-tenant read of `use_case_data_category` / `use_case_affected_party` under the wrong tenant context returns nothing (RLS), asserted as for the parent tables.

### WI-11 — Canon update (mandatory; last)
- **STATE:** intake writes deployment-stable facts only; use-distinguishing context (`usage_context`, `human_oversight`, data categories, affected parties) on the use case; `SystemDetail` drops the four; DPIA/FRIA feeder pre-fill and DPIA applicability now per-use-case (DF-D1-4, a recorded behavioural change); classifier unchanged; new join tables DB-enforced RLS.
- **DATA-MODEL:** drop the four from `system` and the two system join tables; add the two FKs to `use_case` and `use_case_data_category` / `use_case_affected_party` with `tenant_id` + RLS; note the existing link-table isolation question (§5) remains open for the older tables, resolved here only for the new ones.
- **Append:** D-63, D-64, INV-76, INV-77, DF-D1-1..4.
- Never renumber a live id; leave the stable tier untouched.
- **Done:** canonicals updated; new ids appended above floors; no renumbering; STATE "Current through" advanced to DM-S1.

---

**Full suite green before done.** Existing tests retargeted where they assert system-level context; new tests cover WI-5, WI-6 (the feeder done-checks), WI-8 (end-to-end persist), and WI-10 (RLS).