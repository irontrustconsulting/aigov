# DM-S4a — Sprint Handoff (EXECUTION ONLY)

Rationale lives in `DM-S4a-system-intake-prefill-design-FINAL.md`. This file is execution-only. Work items are dependency-ordered. Do not originate visual or UX decisions (INV-68/D-51): build to the FE-30 specimen; if a visual choice is unspecified, stop and flag.

**Entry floors:** `D-67` · `INV-80` · `FE-29`. **Mint at close:** `D-68`, `D-69`, `D-70`, `INV-81`, `FE-30`, `FE-4` ALTER note.

---

## §0 — Pre-flight (block on these before writing)

- [ ] **0.1 (GATING)** Open `packages/ui/src/structured-input/single-select.tsx`. Record whether it injects a placeholder `<option value="">` for empty/unmatched `value`. Outcome decides WI-6 (add placeholder vs assert existing).
- [ ] **0.2** `domain.py`: confirm `catalogue_product` has no `hosting_model_id` and no `intended_use`.
- [ ] **0.3** Confirm a `deployer` `eu_operator_role` row; record its exact `code`.
- [ ] **0.4** Confirm `SystemLifecycleStage = {development, pilot, production, retired}`.
- [ ] **0.5** Confirm `purpose` is written to `metadata_blob["purpose"]`; `system` has no `purpose` column.
- [ ] **0.6** Confirm `get_prefill_by_product` is shared by both prefill routes and that `PrefillStep` reads `prefill.data?.facts` only (additive key tolerated).
- [ ] **0.7** Confirm `draft_blob` persists the five intake fields and the resume action restores them into wizard state before `IntakeCaptureStep` renders.

---

## WI-1 — Schema: curated catalogue columns
Add `catalogue_product.hosting_model_id uuid NULL` (FK `hosting_model.id`, `ON DELETE SET NULL`) and `catalogue_product.intended_use text NULL`. One Alembic migration.
**Done:** migration up and down clean; `\d catalogue_product` shows both columns nullable; FK resolves; existing rows unaffected (both null).

## WI-2 — Curation/seed pass
Populate `hosting_model_id` and `intended_use` for the active catalogue, design-partner cohort first.
**Done:** a sampled curated product returns both via the resolver; an uncurated product returns neither and the form degrades to vocab-select / blank with no error; seed script idempotent.

## WI-3 — Resolver returns typed field prefills
Extend `prefill_service.get_prefill_by_product` to compute `field_prefills`: `hosting_model_id` (column, basis `catalogue`, omit when null), `purpose` (from `intended_use`, basis `catalogue`, omit when null), `operator_role_id` (deployer id from §0.3, basis `derived`), `lifecycle_stage` (`production`, basis `derived`). Do **not** include `name`. Omit any field lacking both a value and a derivation.
**Done:** service test — curated product returns the four with correct bases; uncurated returns only the two derived; no field present without a real value; `get_prefill(system_id)` still returns the same shape via delegation.

## WI-4 — Typed response schema and contract
Add `FieldPrefill {value, basis}` and `FieldPrefills` (named optional keys `hosting_model_id: uuid`, `operator_role_id: uuid`, `lifecycle_stage: str`, `purpose: str`). Add `field_prefills: FieldPrefills | None` to `PrefillResponse`. Regenerate `@irontrust/api-client`.
**Done:** response-schema test asserts each key optional and typed; client contract carries `FieldPrefills`; `PrefillStep` (reads `facts` only) compiles and passes unchanged (additive-key tolerance).

## WI-5 — Wizard seed, resume precedence, intake-step rewire
- `page.tsx`: read `usePrefill(catalogueProductId)`; on load dispatch `SEED_INTAKE` filling wizard-state fields **only when empty** — `name` from `catalogueProductName`; the four from `field_prefills`.
- Reducer: add `SEED_INTAKE` (empty-guarded). Precedence draft-restored > catalogue/derived > blank.
- `IntakeCaptureStep`: convert to wizard-state-controlled; props carry values + change handlers dispatching to the reducer; remove the five `useState("")`; `handleSubmit` submits bound values (no `|| null` over a shown value). Render the FE-30 basis caption per seeded field; derived fields read "derived, confirm"; a user edit clears to user-set.
**Done:** (a) select a curated product, assert each field's input value equals the seed and the basis caption renders; (b) click Continue untouched, assert the payload carries the seeded ids, not null; (c) resume a draft with an edited field, assert the edit survives `SEED_INTAKE`; (d) custom path asserts blank `name` and placeholder selects, no prefill request fired.

## WI-6 — `SingleSelect` placeholder (FE-4 ALTER)
Per §0.1: render a leading non-selectable placeholder and show it when `value` is empty/unmatched, so the display reflects the bound state. Global change; sweep current `SingleSelect` consumers for the cosmetic shift.
**Done:** primitive test — empty/unmatched `value` renders the placeholder, not option one; a matched `value` renders that option; consumer sweep green (no submit-behaviour regressions, only the intended placeholder render).

## WI-7 — Canonical update (last)
- `STATE`: intake-prefill capability; advance the current-through line.
- `DATA-MODEL`: add the two `catalogue_product` columns **only**; do not add a `system.purpose` column.
- Append `D-68`, `D-69`, `D-70`, `INV-81`, `FE-30`, and the `FE-4` ALTER note. Record the N4(b) forward constraint against S4b (re-confirm operator role before obligation derivation).
- Do not renumber any live `INV-n`; leave the stable tier untouched. Record any `DF-S4a-n`.
**Done:** STATE and DATA-MODEL reflect HEAD; appended IDs are the next free slots; no stable-tier edit; INDEX (if touched) consistent with STATE.

---

## Global done-check
`pnpm --filter tenant test`, `pnpm --filter @irontrust/ui test`, and the backend suite green. No `resolve_classification`, `usage_context`, or `UseCase.purpose` change in the diff (those are S4b). Diff touches: 1 migration, `prefill_service`, `schemas/system.py`, api-client contract, `page.tsx`, `wizard-state.ts`, `intake-capture-step.tsx`, `single-select.tsx`, and the canon files.