# Design doc (FINAL): Draft resume/discard front-door fix

**Proposed sprint id:** `UI-DRAFT-RESUME-GATE` (final id at canon stamp)
**Status:** DESIGN v2 FINAL · review folded · all SV resolved from repo · handoff follows
**Surface:** `apps/tenant/app/systems/new/page.tsx` (gate + discard wiring), `apps/tenant/app/systems/new/wizard-state.ts` (reducer), `packages/ui/src/kit/resume-prompt.tsx` (FE-28 ALTER)
**Delta class:** presentational + client-state · 0 backend · 0 schema · 0 route · 0 enum · 0 contract · 0 `draft_blob` shape
**Fork settled:** single draft per user, INV-79 / D-66 held.
**Stamps at close:** INV-85, D-76 (next free per INDEX ceiling INV-84 / D-75 / FE-33 with 84 reserved for `UI-V-PREFILL-FACT`). **No new FE-n minted** (FE-28 is an ALTER). Verify ceiling at stamp; if `UI-V-PREFILL-FACT` has not landed, allocate whatever is next free.

---

## §0 Pre-flight verify checklist (D-21)

Most items resolved from the repo at design time (Appendix B). Two remain live for the agent:

- [ ] **V-3** (DB, D-21) `select owner_user_id, count(*) from draft_registration group by 1 having count(*) > 1;` returns zero rows, i.e. INV-79 holds live.
- [ ] **SV-D** `grep -ri "dialog\|modal\|confirm" packages/ui/src` for an existing confirm/dialog primitive. Grounding found none (only `Button` + banner components). If one exists, reuse it for the discard confirm (D-22 additive over greenfield); if not, the inline pattern in WI-3 stands.

---

## Problem

Two reported symptoms plus one latent hazard, all from one root cause.

**S1 (evaporation).** From the portfolio, "Register a system" navigates to `/systems/new`. The front-door gate is `activeDraft.data && state.draftId === null && state.step === "drill-down"`. `step === "drill-down"` and `draftId === null` are session-state proxies for "draft unresolved." On a first-paint race (`useActiveDraft` has `staleTime: 0`; on mount `data` can be momentarily undefined before the shared cache populates), the render falls through to the `switch` and paints `DrillDownStep`. Any interaction fires `DRILL_DOWN_COMPLETE` (step leaves drill-down) then `DRAFT_CREATED` (draftId set), so when `activeDraft.data` populates the gate is now permanently false for the mount. The draft persists server-side but is orphaned from view.

**S2 (feedback-less discard).** The first screenshot is the FE-28 `ResumePrompt` front-door (renders `savedStep` + a "Start over" ghost; SV-A). Its handler is `onStartOver={() => discard.mutate(draft.id)}` with no dispatch and no optimistic state, so clicking it fires the DELETE but nothing re-renders until the cache write lands. It reads as "does nothing."

**S3 (silent clobber, latent).** Under `uq_draft_one_per_user` (INV-79), `useGetOrCreateDraft` returns the existing row. If the user reaches drill-down while a draft exists and advances, `persistTransition` PATCHes the existing `draft_blob`, overwriting the parked registration. The front-door is the sole guard.

**Root cause:** the resume decision gates on the wizard `step`/`draftId` session cursor, not on whether the user has resolved the draft, and the discard affordance gives no feedback. The gate must key on an explicit resolution signal and be unskippable while a draft exists.

---

## Resolved decisions

| # | Decision | Basis |
|---|---|---|
| R1 | Single draft per user held (INV-79 / D-66). Client-state + UI fix, no schema change. | founder fork |
| R2 | Add `resumeResolved: boolean` to `WizardState` (initial `false`). Gate becomes `activeDraft.data && !state.resumeResolved`, dropping the `step`/`draftId` proxies (Option A). | S1 |
| R3 | `resumeResolved` flips `true` in **three** transitions: `RESUME_FROM_DRAFT`, a new `DRAFT_DISCARDED`, and `DRAFT_CREATED`. The `DRAFT_CREATED` set-site is **load-bearing, not defensive**: `useGetOrCreateDraft`/`usePatchDraft` call `setQueryData(intakeKeys.activeDraft(), data)`, so `activeDraft.data` is truthy for the whole post-advance session; without the flag the two-condition gate would re-fire over every post-drill-down step. | S1, `mutations.ts` |
| R4 | The front-door is unskippable while an active-draft fetch **succeeds** and the draft is unresolved: no wizard step renders, so drill-down is unreachable and no PATCH can clobber (S3). On `activeDraft.isError`, `data` is undefined, the gate is false, the wizard renders, and clobber prevention falls back to `getOrCreate` SELECT-first plus last-write-wins (DF-D3-5, DF-D3-6). This is unchanged from the current gate (also `activeDraft.data &&`), so no regression. | S3, INV-79, DF-D3-5/6 |
| R5 | "Start over" retired for **Discard** with an inline two-button confirm in `ResumePrompt` ("Discard this registration and start fresh? This cannot be undone." + Discard / Cancel). `onStartOver` renamed `onDiscard`. The page dispatches a new `DRAFT_DISCARDED` on `discard` success, flipping `resumeResolved` before the cache write nulls `activeDraft.data`, so the fresh drill-down renders without a flicker back to the front-door. | S2, founder points 3/4 |
| R6 | Portfolio banner (FE-29) unchanged: navigation-only pointer, no discard control. SV-A confirmed the reported banner was FE-28, so no FE-29 edit exists to revert. | R5, SV-A |
| R7 | Resume restores at the saved pre-boundary step (existing `RESUME_FROM_DRAFT` + `clampStep`; SV-B confirmed it sets `draftId` + `step`). Unchanged. | founder point 3 |
| R8 | `resumeResolved` is client-transient, like `confirmedIntakeFields`/`confirmedFactKeys` (B1, INV-83). It never enters `draft_blob`: `toDraftBlob` is untouched and DF-D3-1 is not amended. | NB-3, DF-D3-1, INV-83 |

---

## Mechanism (R2, R3, R8)

**State (`wizard-state.ts`):** add `resumeResolved: boolean` to `WizardState`; `initialWizardState.resumeResolved = false`. `toDraftBlob` unchanged (R8) so the flag stays transient.

**Reducer transitions:**

| Action | Present | ALTER |
|---|---|---|
| `RESUME_FROM_DRAFT` | `{ ...initialWizardState, ...blob fields, step: clampStep(...), draftId: action.draft.id }` (SV-B) | add `resumeResolved: true` (required: the spread reintroduces `false`) |
| `DRAFT_CREATED` | `{ ...state, draftId }` | add `resumeResolved: true` (load-bearing, R3) |
| `DRAFT_DISCARDED` | absent | new: `{ ...initialWizardState, resumeResolved: true }` |

**Gate (`page.tsx`):**

| Present | ALTER |
|---|---|
| `if (activeDraft.data && state.draftId === null && state.step === "drill-down")` | `if (activeDraft.data && !state.resumeResolved)` |

Because the gate no longer latches on `step`/`draftId`, it reasserts the instant `activeDraft.data` arrives: a first-paint race into drill-down is corrected on data arrival (S1 closed), and `getOrCreate` being async means `resumeResolved` only flips after its round-trip, during which the populated `activeDraft.data` keeps the front-door asserted.

**Discard wiring (`page.tsx`):** `onDiscard={() => discard.mutate(draft.id, { onSuccess: () => dispatch({ type: "DRAFT_DISCARDED" }) })}`.

**Traversal coverage:**
- fresh mount, draft exists: `resumeResolved` false, `activeDraft.data` truthy -> front-door, drill-down blocked (S3 guard). ✓
- Resume -> `resumeResolved` true -> saved step. ✓
- Discard -> `DRAFT_DISCARDED`, `resumeResolved` true, cache nulled -> fresh drill-down. ✓
- fresh registration -> advance -> `DRAFT_CREATED` sets `resumeResolved` true; the cache-resident new draft cannot re-fire the front-door. ✓
- post-registration -> `resumeResolved` already true; `useRegister` invalidates `activeDraft` -> null. ✓
- `activeDraft.isError` -> gate false -> wizard renders; DF-D3-5/6 fallback (R4). ✓

---

## Discard affordance (R5, FE-28 ALTER)

`packages/ui/src/kit/resume-prompt.tsx`:

| Aspect | Present | ALTER |
|---|---|---|
| Props | `onResume`, `onStartOver` | rename `onStartOver` -> `onDiscard` |
| Secondary button | "Start over" (ghost) | "Discard" (ghost), opens an inline confirm in place ("Discard this registration and start fresh? This cannot be undone." + Discard / Cancel), component-local `useState`. No modal. |
| Primary | Resume | unchanged |

`onDiscard` fires only on the confirm's Discard; Cancel returns to the Resume/Discard view.

---

## Proposed canon (agent stamps next free IDs at close; never renumber live IDs)

- **INV-85** · CONVENTION · The registration front-door gates on an explicit draft-resolution flag (`resumeResolved`), never on the wizard `step`/`draftId` cursor. While an active-draft fetch succeeds and the draft is unresolved, no wizard step renders: a server draft is never reachable-for-overwrite nor orphaned-from-view. `resumeResolved` is client-transient (not in `draft_blob`). (refs: R2, R3, R4, R8, INV-79, DF-D3-1)
- **D-76** · "Start over" retired for **Discard** with confirmation; single-draft held (INV-79); the FE-28 front-door is the sole resume/discard authority; the FE-29 banner is navigation-only. (refs: R5, R6, D-66)
- **FE-28 ALTER** (not a new stamp) · `onStartOver` -> `onDiscard`; "Start over" -> "Discard" with inline confirm. **FE-29** unchanged.

---

## Appendix A — open decisions

**OPEN-A1 · Resume landing step.** Assumed saved step (R7, existing `clampStep`). Confirm.
**OPEN-A2 · Discard confirm surface.** Assumed inline (R5). Flag if you want a modal.
**OPEN-A3 · Portfolio CTA copy (deferred).** "Register a system" could relabel to "Resume registration" when a draft exists. Deferred; the front-door already makes state honest.

---

## Appendix B — source-verification register (resolved at design time unless noted)

| ID | Claim | Outcome |
|---|---|---|
| SV-A | Reported banner identity | **FE-28 front-door**, not FE-29. `ResumePrompt` renders `savedStep` + "Start over" ghost; `page.tsx` passes `savedStep`. SV-1 collapsed; FE-29 needs no revert. |
| SV-B | `RESUME_FROM_DRAFT` sets `draftId` + `step` | **Confirmed.** Ends `step: clampStep(...), draftId: action.draft.id`; ALTER adds `resumeResolved: true`. |
| SV-C | Invalidation graph / re-fire | **Confirmed + corrected.** `getOrCreate`/`patch` `setQueryData(activeDraft)`; `discard` sets null; `useRegister` invalidates. `activeDraft.data` truthy mid-session, so the `DRAFT_CREATED` set-site is load-bearing (R3). |
| SV-D | Existing confirm primitive | Grounding found none in `packages/ui`. Agent greps to confirm (§0); inline pattern otherwise. |
| V-3 | INV-79 holds live | **Open** (DB read, agent). |

---

## Not in scope

Multi-draft / concurrent registrations (INV-79 retained; revisit on evidence the design partner parks registrations). Portfolio CTA relabel (OPEN-A3). Any change to `draft_blob`, DF-D3-1, the draft endpoints, or atomic-discard-on-register.