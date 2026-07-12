# SPRINT HANDOFF (execution-only) - FIX-RESUME-REGATE (OPEN-5)

**Execution-only. Rationale lives in `DESIGN_FIX-RESUME-REGATE.md`. Do not originate design; if a visual change seems needed, flag-and-stop (INV-68, D-51).**
**Surface:** `apps/tenant/app/systems/new` (client only).
**Delta envelope:** 0 backend, 0 schema, 0 migration, 0 route, 0 enum, 0 contract, 0 `draft_blob` shape. Any deviation is a flag-and-stop.
**Provisional IDs to reconcile in WI-6 (landing order, above live ceiling INV-85 / D-76 / FE-35):** FE-36; INV-83 ALTER; one D-n (Path B fact policy); carry-over D-n (OPEN-4 reclassification). DF-RR-1..5 sprint-local.

---

## WI-0 - Pre-flight verify (gate; no code)

Record findings in the PR description.

1. `wizard-state.ts` `SEED_INTAKE`: confirm basis is `state.<field> ? "user-set" : fp.<field>.basis` and value seed is `state.<field> ?? fp.<field>.value ?? null`. The seed value `fp.<field>.value` is in scope for the value-vs-seed compare.
2. `registrations.py`: confirm `_dispose_intake_prefill` 422 predicate (`basis=="derived" and _submitted==seed_val and fk not in confirmed_fields`; fields `operator_role_id`, `lifecycle_stage`) and `_dispose_fact_prefill` (writes only `fact:` / `fact_amended:` entries; no 422 for absent facts) are unchanged at HEAD.
3. `use-case-create-step.tsx`: confirm `confirmed_fields` is assembled in `handleSubmit`. Confirm the step does not yet call `usePrefill`.
4. Confirm `usePrefill(catalogueProductId)` query key matches `page.tsx` so a step-level call is cache-shared.

**Done-check:** all four confirmed in the PR. If item 1 differs, STOP (B edit site moves).

---

## WI-1 - Shared `derivedUnconfirmed` predicate (V2)

Extract to a shared module (e.g. `apps/tenant/lib/intake/derived-unconfirmed.ts`):
`derivedUnconfirmed(prefillBases: IntakePrefillBases | null, confirmedIntakeFields: string[]): IntakeFieldName[]` returning the fields in `["operatorRoleId","lifecycleStage"]` where `prefillBases?.[field] === "derived" && !confirmedIntakeFields.includes(field)`.
Refactor `IntakeCaptureStep` to consume it in place of its inline computation. No behaviour change to the intake step.

**Done-check:** `IntakeCaptureStep` tests green unchanged. New unit test: predicate returns the derived-and-unconfirmed subset for representative basis/confirmed combinations; empty when all confirmed or all non-derived.

---

## WI-2 - `SEED_INTAKE` basis re-derive (B)

In `wizard-state.ts` `SEED_INTAKE`, change each seeded field's basis from the value-presence form to value-vs-seed: basis is `fp.<field>.basis` when the current value equals `fp.<field>.value`, else `"user-set"`. Leave the value seed (`?? fp.<field>.value`) untouched. Apply to all seeded intake fields (`operatorRoleId`, `lifecycleStage`, `hostingModelId`, `purpose`, `name` where seeded).

**Done-check:** new reducer tests: (a) a resume-restored value equal to a derived seed yields basis `"derived"` (not `"user-set"`); (b) a restored value differing from the seed yields `"user-set"`; (c) normal-flow first seed (null prior value) is unchanged; (d) the restored value itself is never overwritten. Existing `SEED_INTAKE` tests green.

---

## WI-3 - Pre-commit disposition gate component (E-compact)

Create `apps/tenant/lib/intake/pre-commit-disposition-gate.tsx`. Props:
`derivedItems: { field: IntakeFieldName; label: string; value: string; options: SelectOption[]; confirmed: boolean }[]`, `onConfirm(field)`, `onChange(field, value)`, `factCount: number`, `onReviewFacts()`.
Render only when `derivedItems` (the unconfirmed set) is non-empty. Per derived item: label, current value, "Derived, confirm or update" caption, Confirm button (`onConfirm`), Change button that reveals the item's `SingleSelect` (`onChange`); a confirmed item shows a confirmed indicator. Facts recap: "{factCount} catalogue facts have not been reviewed this session. They will be kept as recorded in the catalogue unless you review them." plus a Review-facts link (`onReviewFacts`). Compose with `SectionGroup` (FE-27); neutral tokens only; no `--verdict-*`, no `border-brand` on inner rules.

**Done-check:** unit tests: (a) hidden when the unconfirmed set is empty; (b) Confirm fires `onConfirm(field)`; (c) Change reveals the select and fires `onChange`; (d) recap renders `factCount` and never contains the word "confirmed" applied to facts (assert Path B wording); (e) no `--verdict-*` / `border-brand` in the DOM; (f) facts recap has no gating effect.

---

## WI-4 - Wire the gate into `use-case-create-step.tsx`

Depends on WI-1, WI-2, WI-3.
1. Add props/wiring: `intakePrefillBases`, `confirmedIntakeFields`, `onConfirmField` (`CONFIRM_INTAKE_FIELD`), `onFieldChange` (`SET_INTAKE_FIELD`); intake vocab via the shared hooks (`useOperatorRoles`, `LIFECYCLE_STAGE_OPTIONS`) used by `IntakeCaptureStep` (share, do not duplicate).
2. Call `usePrefill(catalogueProductId)` for the facts recap count and the loading guard.
3. Loading guard (V1): hold the gate render and disable Register until `usePrefill` has resolved and `intakePrefillBases` is non-null; fold into the existing guard (which already gates on `categoryMemberships`).
4. Compute the unconfirmed set via the shared `derivedUnconfirmed`; render `PreCommitDispositionGate` with the mapped `derivedItems`; wire `onReviewFacts` to navigate to `prefill`.
5. Gate Register: disabled while the unconfirmed set is non-empty. Facts never block.
6. `handleSubmit` / `confirmed_fields` assembly: unchanged (session arrays). Do NOT synthesise facts (Path B, Change 3 dropped).

**Done-check:** integration tests: (a) resume to `use-case` with an unconfirmed derived default renders the gate and disables Register; confirming enables it and a subsequent register carries the derived key in `confirmed_fields` (no 422); (b) normal walked-through flow hides the gate and is unaffected; (c) a resume submit fired during the prefill-loading window is prevented (Register disabled until bases re-derived); (d) on resume with facts unreviewed, `confirmed_fields` carries no `fact:` entries and the server writes no fact rows (truthful absence; no false `USER_CONFIRMED`); (e) Review-facts navigates to `prefill`.

---

## WI-5 - Full suite

**Done-check:** `apps/tenant`, `packages/ui`, `packages/tokens` suites green. No new `--verdict-*` or `border-brand` outside `SectionGroup`'s own marker in the touched files.

---

## WI-6 - Canonical update (volatile tier only)

Reconcile provisional IDs against the live ceiling first (allocate FE-36 above FE-35; D-n above D-76 in landing order; never renumber a live INV-n; stable tier untouched).

- **INVARIANTS.md:** apply the **INV-83 ALTER** in place (append the resume basis-re-derive clause, the pre-commit-gate satisfiability clause, and the catalogue-fact "retains catalogue-curated provenance on resume, never synthesised confirmed" clause; keep "no change to server predicates" and "not persisted in `draft_blob`" explicit). Do not renumber INV-83.
- **FRONTEND.md:** append `FE-36` (pre-commit disposition gate; cites INV-83, D-74, FE-27, FE-32, INV-84).
- **DECISIONS.md:** append the **Path B fact-disposition-on-resume D-n**; append `DF-RR-1..5` (sprint-local, with rejected alternatives per the design doc); mark **OPEN-5 resolved** by this sprint. Record the **intelligent-wizard forward item** (conditional field presentation, inline per-field disposition; adjacent to deferred #1 and OPEN-3; post-MVP).
- **Carry-over (unrelated to OPEN-5):** append the **OPEN-4 reclassification D-n** (single-operator tenants supported via multiple memberships; genesis API self-assignment deferred to exception management; reclassifies OPEN-4 from "blocks MVP" to deferred/out-of-MVP-scope). Keep as a distinct DECISIONS entry, not entangled with the OPEN-5 code.
- **STATE.md:** set "Current through" to FIX-RESUME-REGATE; record the client-only delta (files: `wizard-state.ts`, new `derived-unconfirmed.ts`, new `pre-commit-disposition-gate.tsx`, `use-case-create-step.tsx`; 0 backend/schema/route/enum/contract/`draft_blob` delta); mark OPEN-5 resolved and OPEN-4 reclassified; carry the intelligent-wizard forward item in the deferred queue.
- **DATA-MODEL.md:** no schema change; confirm none owed.

**Done-check:** INDEX ceilings updated (FE-36, the two D-n); INV-83 ALTER in place with no renumber; DF-RR-1..5 and both D-n present; OPEN-5 marked resolved; OPEN-4 reclassified; STATE "Current through" reflects this sprint; stable tier untouched.