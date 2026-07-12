# SPRINT HANDOFF (execution-only) - UI-UC-CREATE-COMPOSE

**Execution-only. Rationale lives in `UI-UC-CREATE-COMPOSE.design.md`. Do not originate design; if a visual change seems needed, flag-and-stop (INV-68, D-51).**
**Surface:** `apps/tenant/app/systems/new/_steps/use-case-create-step.tsx`
**Delta envelope:** presentational plus one dead-line removal. 0 backend, 0 schema, 0 migration, 0 route, 0 enum, 0 contract, 0 `draft_blob` shape. Any deviation is a flag-and-stop.
**Provisional IDs to reconcile in WI-5:** FE-34, FE-35, FE-31 ALTER, DF-UC-1..5. Live ceiling at design time: FE-33.

---

## WI-0 - Pre-flight verify (gate; no code)

Run before WI-1. Record findings inline in the PR description.

1. `psql` dump: `SELECT code,label,is_special_category,sort_order,framework_ref FROM data_category ORDER BY sort_order;` and `SELECT code,label,is_vulnerable_group,sort_order,framework_ref FROM affected_party ORDER BY sort_order;` (SV-1, SV-2).
2. Confirm `DataCategoryOut.is_special_category` and `AffectedPartyOut.is_vulnerable_group` are present on `GET /reference/data-categories` and `GET /reference/affected-parties` responses consumed by `useDataCategories` / `useAffectedParties`.
3. Confirm `TextInput` import from `@irontrust/ui` resolves in `apps/tenant` (grep `intake-capture-step.tsx`).
4. Confirm `SectionGroup` exported from `@irontrust/ui` and FE-26 elevation tokens (`--elevation-raised`) present in `packages/tokens/src/primitives.css`.

**Done-check:** all four confirmed; seed dumps pasted into the PR. If item 2 fails, STOP (grouping needs those flags on the read).

---

## WI-1 - `GroupedMultiSelect` (tenant-local)

Create `apps/tenant/lib/intake/grouped-multi-select.tsx`. Precedent locus: `fact-value.tsx` (INV-84).

- Props: `id: string`, `label: string`, `values: string[]`, `options: { value: string; label: string; group: "duty" | "other" }[]`, `onChange: (next: string[]) => void`, `dutyHeading: string`, `dutyCaption: string`, `otherHeading: string`.
- Renders, under the field `label`: a heightened-duty subgroup (neutral `border-l-2 border-hairline pl-3`, `dutyHeading` in `text-xs font-semibold text-ink`, `dutyCaption` in `text-xs text-ink-muted`) then an "other" subgroup (`otherHeading`), each a `MultiSelectInput` chip cluster over its partition, sharing one `values` array and one `onChange`.
- Empty-partition rule: if a subgroup has no options, omit that subgroup entirely (heading included).
- Tokens: chip states are INV-73 (`MultiSelectInput` owns them). No `--verdict-*`, no `data-tone`, no `border-brand` anywhere in this component.

**Done-check:** `apps/tenant/lib/intake/__tests__/grouped-multi-select.test.tsx` asserts (a) options partition into duty vs other by the `group` field; (b) toggling a chip in either subgroup updates the single `values` array and fires `onChange` once; (c) an all-`other` option set renders no duty heading; (d) rendered DOM carries no `--verdict-*` class and no `border-brand` on the subgroup rule.

---

## WI-2 - Rewire `use-case-create-step.tsx`

Depends on WI-1.

1. Title: replace the raw `<input id="use-case-title" ...>` with `TextInput` (same `id`, `value`, `onChange`, `required`), add `placeholder="e.g. Screening inbound support tickets"`. (FE-35)
2. Data categories: replace the `MultiSelectInput` with `GroupedMultiSelect`, mapping `dataCategories.data` to options with `group: is_special_category ? "duty" : "other"`; `dutyHeading="Special-category data"`, `dutyCaption="GDPR Art. 9, heightened duty"`, `otherHeading="Other personal data"`. Keep `values={dataCategoryIds}` / `onChange={setDataCategoryIds}`. (FE-34)
3. Affected parties: replace the `MultiSelectInput` with `GroupedMultiSelect`, mapping `affectedParties.data` to options with `group: is_vulnerable_group ? "duty" : "other"`; `dutyHeading="Vulnerable groups"`, `dutyCaption="EU AI Act Art. 27, heightened duty"`, `otherHeading="Other affected parties"`. Keep `values={affectedPartyIds}` / `onChange={setAffectedPartyIds}`. (FE-34)
4. Sectioning: wrap the form body in two `SectionGroup` regions (FE-27): region 1 `title="Use & oversight"` holds title, intended-use category, usage context, human oversight; region 2 `title="Data & affected parties"` holds the two `GroupedMultiSelect`s. Card container on `bg-paper` + `shadow-[var(--elevation-raised)]` (FE-26). Remove the flat `border-hairline space-y-4 rounded-lg border p-4` card chrome in favour of the `SectionGroup` composition. `PageScaffold` + `PageHeader` retained (INV-69).
5. Do not add any default or prefill to any field. Init state stays empty (Move 4 held, INV-83).
6. Do not change the `RegistrationCreate` payload assembly (`confirmed_fields`, `intended_use_category_id`, `usage_context_id`, `human_oversight_type_id`, `data_category_ids`, `affected_party_ids`, `title`).

**Done-check:** existing `use-case-create-step.test.tsx` green (register handoff via `onCreated` unchanged). Extend it to assert: title renders as `TextInput`; two `SectionGroup` headings present; data-category and affected-party clusters render both subgroups given a mixed-flag vocab fixture; all fields empty on first render.

---

## WI-3 - FE-31 canon-accuracy code fix

Depends on nothing; may land with WI-2.

- In `apps/tenant/app/systems/new/wizard-state.ts`, `RESUME_FROM_DRAFT`: remove the line `intendedUseCategoryId: blob.intendedUseCategoryId ?? null`. The `...initialWizardState` spread already sets it null. (DF-UC-5, DF-D3-1)
- No other reducer change.

**Done-check:** `wizard-state` test green; a `RESUME_FROM_DRAFT` test asserts `intendedUseCategoryId === null` after resume from a blob that omits it (unchanged behaviour, now without the dead read).

---

## WI-4 - Full suite

**Done-check:** `packages/ui`, `packages/tokens`, and `apps/tenant` suites green. `contrast.test.ts` unaffected (no ramp value changes). No new `--verdict-*` or `border-brand` in the two touched tenant files outside `SectionGroup`'s own petrol marker.

---

## WI-5 - Canonical update (volatile tier only)

Reconcile provisional IDs against the live ceiling first (FE ceiling was FE-33; allocate FE-34, FE-35 in order; never renumber a live INV-n; leave the stable tier untouched).

- **FRONTEND.md:** append `FE-34` (heightened-duty `GroupedMultiSelect`, cites INV-73, FE-4, D-57, INV-84, DATA-MODEL `data_category`/`affected_party`) and `FE-35` (`TextInput` in `UseCaseCreateStep`, cites FE-4). Apply the `FE-31` ALTER: strike the "persisted to draft blob; restored on `RESUME_FROM_DRAFT`" clause for use-case fields; note they are not pre-boundary state per DF-D3-1.
- **DECISIONS.md:** append `DF-UC-1..5` (sprint-local), each with rationale and rejected alternatives per the design doc.
- **STATE.md:** set "Current through" to UI-UC-CREATE-COMPOSE; record the presentational delta (new `grouped-multi-select.tsx`; `use-case-create-step.tsx` rewired; one dead line removed in `wizard-state.ts`; 0 backend/schema/route/enum/contract/`draft_blob` delta). Record the deferred **P4 taxonomy-expansion track** (DF-UC-3), gated on SV-1 / SV-3 live-DB dump, in the deferred queue.
- **DATA-MODEL.md:** no schema change; no edit required beyond confirming none is owed.
- Do not touch INVARIANTS.md (no INV minted or altered this sprint).

**Done-check:** INDEX ceilings updated for FE-34/FE-35; STATE "Current through" reflects this sprint; DF-UC-1..5 present in DECISIONS; FE-31 clause corrected; no INV-n renumbered; stable tier untouched.