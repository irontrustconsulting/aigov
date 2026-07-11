# Sprint handoff (execution-only): `UI-DRAFT-RESUME-GATE`

**Rationale lives in `draft-resume-gate.design.md`. This file is execution-only.**
**Delta:** presentational + client-state · 0 backend · 0 schema · 0 route · 0 enum · 0 contract · 0 `draft_blob` shape.
**Stamps at close:** INV-85, D-76 (next free; verify ceiling). **No new FE-n** (FE-28 is an ALTER).

---

## §0 Pre-flight (block build until both pass)

- [ ] **V-3** (DB, D-21) `select owner_user_id, count(*) from draft_registration group by 1 having count(*) > 1;` -> zero rows (INV-79 holds live).
- [ ] **SV-D** `grep -ri "dialog\|modal\|confirm" packages/ui/src`. If a reusable confirm/dialog primitive exists, use it in WI-3 (D-22). If not, build the inline confirm as specified.

---

## Work items (dependency-ordered)

### WI-1 · `wizard-state.ts` — `resumeResolved` flag + `DRAFT_DISCARDED`
- Add `resumeResolved: boolean` to the `WizardState` interface; set `resumeResolved: false` in `initialWizardState`.
- Add `{ type: "DRAFT_DISCARDED" }` to `WizardAction`.
- Set `resumeResolved: true` in three reducer cases:
  - `RESUME_FROM_DRAFT` return object (the `...initialWizardState` spread reintroduces `false`, so set it explicitly; do not disturb the existing `draftId` / `step: clampStep(...)` restore).
  - `DRAFT_CREATED` return object.
  - new `DRAFT_DISCARDED`: `return { ...initialWizardState, resumeResolved: true };`
- **Do not** add `resumeResolved` to `toDraftBlob` (it stays transient, R8/DF-D3-1 unamended).
- **Done-check:** `wizard-state.test.ts` asserts: `initialWizardState.resumeResolved === false`; `RESUME_FROM_DRAFT` yields `resumeResolved === true` and preserves `draftId === draft.id` and `step === clampStep(blob.step)`; `DRAFT_CREATED` yields `resumeResolved === true`; `DRAFT_DISCARDED` yields `{ ...initial, resumeResolved: true }` (step `drill-down`, `draftId` null); `toDraftBlob(...)` output contains no `resumeResolved` key.

### WI-2 · `page.tsx` — gate re-key + discard wiring
- Replace the front-door condition `activeDraft.data && state.draftId === null && state.step === "drill-down"` with `activeDraft.data && !state.resumeResolved`.
- Change the discard handler to `onDiscard={() => discard.mutate(draft.id, { onSuccess: () => dispatch({ type: "DRAFT_DISCARDED" }) })}` (prop renamed per WI-3).
- **Done-check:** `page.test.tsx` asserts: (a) `system_owner` + active draft on fresh mount -> `ResumePrompt` shown, no wizard step; (b) Resume -> wizard renders at saved step, `ResumePrompt` gone; (c) Discard confirm -> `discard.mutate` called with the draft id, `ResumePrompt` gone, drill-down shown; (d) **regression:** after a fresh registration advances past drill-down (`DRAFT_CREATED` fired, draft written to cache via `setQueryData`), `ResumePrompt` does **not** reappear over the intake step; (e) `activeDraft.isError` -> wizard renders (no front-door).

### WI-3 · `resume-prompt.tsx` (FE-28 ALTER)
- Rename prop `onStartOver` -> `onDiscard`. Update the kit export and the type.
- Relabel the ghost button "Start over" -> "Discard".
- Discard opens an inline confirm in place (component-local `useState`): copy "Discard this registration and start fresh? This cannot be undone.", buttons Discard (fires `onDiscard`) and Cancel (returns to the Resume/Discard view). No modal. If SV-D found a primitive, use it instead of hand-rolling.
- **Done-check:** `resume-prompt.test.tsx` asserts: the secondary button reads "Discard" (not "Start over"); clicking it does **not** call `onDiscard` immediately but reveals the confirm; the confirm's Discard calls `onDiscard` once; Cancel dismisses the confirm without calling `onDiscard`; Resume still calls `onResume`.

### WI-4 · Canonical update (last)
- **STATE.md:** add a `UI-DRAFT-RESUME-GATE` entry (client-state + UI; INV-85, D-76; files touched; 0 schema/route/contract/`draft_blob` delta). **DATA-MODEL.md:** no change.
- **Append** INV-85 (INVARIANTS) and D-76 (DECISIONS) as worded in the design doc. Do not renumber live IDs; verify the ceiling first and bump if `UI-V-PREFILL-FACT` already consumed the number.
- **Amend the FE-28 entry** (FRONTEND) in place: `onStartOver` -> `onDiscard`, "Start over" -> "Discard" with inline confirm. Do **not** mint a new FE-n. **FE-29** entry unchanged.
- Stable tier untouched.
- **Done-check:** INV-85 + D-76 present with correct cross-refs; FE-28 entry reflects the rename + confirm; no new FE-n added; no live ID renumbered; `grep -r "onStartOver" apps/ packages/` returns nothing.

---

## Guardrails
- No `draft_blob` shape change; `resumeResolved` never serialised (INV-83 transient posture).
- No backend, route, enum, or contract change.
- Discard remains single-homed on the FE-28 front-door; the FE-29 banner gains no mutation.
- If a change beyond this handoff seems needed, flag-and-stop; do not improvise canon (INV-68 / D-51).