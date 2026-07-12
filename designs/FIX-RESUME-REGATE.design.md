# DESIGN DOC (FINAL) - FIX-RESUME-REGATE (OPEN-5)

**Draft resume skips derived-field disposition: basis re-derive + pre-commit disposition gate (Path B fact handling)**

**Status:** FINAL, review folded (fresh-chat four-bucket; B1/B2/V1/V2/N1/N2/N3 all dispositioned) - founder decisions DF-RR-1..5 resolved - handoff issued as paired file
**Surface:** `apps/tenant/app/systems/new` (`wizard-state.ts`, `use-case-create-step.tsx`, new gate component)
**Origin:** OPEN-5 (`docs/DECISIONS.md`), coding-agent report
**Lineage:** INV-83, D-74, D-75, FE-32, DM-S3, DM-S4a, DF-D3-1
**Live ceilings (from INDEX; confirmed HEAD in review):** INV-85, D-76, FE-35
**New IDs (provisional; reconcile at handoff, landing order):** FE-36; INV-83 ALTER; DF-RR-1..5; one new D-n (Path B fact-disposition-on-resume policy). Note the OPEN-4 D-77 reclassification is also pending; allocate above D-76 in landing order.
**Delta target:** client-only. 0 backend, 0 schema, 0 migration, 0 route, 0 enum, 0 contract, 0 `draft_blob` shape.
**Binding specimen:** `disposition-gate-spec.html` (Path B wording).

---

## Section 0 - Pre-flight verify checklist (coding agent, before WI-1)

1. Confirm the live `SEED_INTAKE` reducer in `wizard-state.ts`: basis is value-presence keyed (`state.<field> ? "user-set" : fp.<field>.basis`); value seeding uses the empty-guard (`state.<field> ?? fp.<field>.value ?? null`). B changes only the basis expression (SV-1, review-confirmed).
2. Confirm server predicates unchanged at HEAD: `_dispose_intake_prefill` 422s on `basis == "derived" and _submitted(fk) == seed_val and fk not in confirmed_fields` for `operator_role_id`, `lifecycle_stage`; `_dispose_fact_prefill` writes rows only for `fact:` / `fact_amended:` entries, no 422 for absent facts (SV-2/SV-3, review-resolved).
3. Confirm `confirmed_fields` is assembled in `use-case-create-step.tsx::handleSubmit` (the `register.mutate` call), NOT `page.tsx` (B1, review-corrected). Confirm `usePrefill(catalogueProductId)` is cache-shared (same query key as `page.tsx`) when called inside the step.
4. Confirm `SectionGroup` (FE-27) importable here (already consumed by `use-case-create-step.tsx`; formality).

---

## 1. Scope and surface

Fixes OPEN-5: resuming a parked catalogue-linked draft saved at `prefill` or `use-case` produces a guaranteed 422 on Register for unconfirmed derived defaults, with no recovery short of discard, plus a silent fact under-disposition. Scope is the tenant registration wizard client only. Server disposition logic is correct and untouched.

---

## 2. Root-cause analysis (grounded, review-verified)

**F1 - step-skip.** `RESUME_FROM_DRAFT` restores `step` as-saved and resets `confirmedIntakeFields: []` (re-gate, INV-83 B1). The derived-confirm affordance (`DerivedConfirmControl`) lives only in `IntakeCaptureStep`, gated on `prefillBases?.X === "derived"`; resuming past `intake` never reaches it.

**F2 - basis mislabel (load-bearing).** `SEED_INTAKE` computes basis as `state.<field> ? "user-set" : fp.basis`. On resume the restored value is truthy, so basis reads `"user-set"`, so no confirm control renders and no gate fires, while the server (keying off submitted-value-equals-seed) still 422s. `draft_blob` stores the value but never its disposition.

**F3 - silent fact under-disposition.** `_dispose_fact_prefill` writes rows only for `fact:` / `fact_amended:` entries; skipping `prefill` on resume sends none, so no fact rows are written and no 422 fires. Registration succeeds with an incomplete provenance record.

---

## 3. Resolved decisions (rationale plus rejected alternatives; sprint-local DF-RR-n)

**DF-RR-1 - Approach: B + E-compact.** Fix F2 at root (B: re-derive basis from value-vs-seed) and surface the confirm affordance at the commit point (E-compact: a pre-commit disposition gate at the foot of the use-case step, shown only when disposition is incomplete). The invariant is "every seeded field dispositioned before commit"; E places the gate at the commit.
*Rejected:* (a) resume-to-intake clamp alone (OPEN-5 candidate): fails without B (F2), and routes upstream instead of gating at commit. (b) B + E-full editable fact cards at the boundary: duplicates the `prefill` surface. (c) persist disposition in `draft_blob`: contradicts INV-83 B1. (d) **editable review-and-submit summary as the terminal disposition surface** (considered late): cleaner than a bolted-on gate in isolation, but it is a third wizard shape, neither the current linear wizard nor the intended context-driven one (conditional field presentation with inline per-field disposition). Inline disposition is the chosen long-run direction, which an end-summary contradicts; an editable summary would be torn out when the intelligent wizard lands. E-compact is inline disposition at the commit point and generalises into a per-screen gate rather than being discarded. Recorded as a forward item (Appendix A).

**DF-RR-2 - Fact handling: E-compact, non-blocking.** The gate shows a facts recap, not editable cards; amendment stays single-home at `prefill` via a Review-facts link. Facts do not hard-gate Register.
*Rejected:* E-full (DF-RR-1(b)).

**DF-RR-3 - B2 = Path B (honest absence, no synthesised confirmation).** Change 3 (commit-time synthesise-all: `confirmedFactKeys = productFactKeys \ amendedFactKeys`) is **dropped**. Because `RESUME_FROM_DRAFT` resets `amendedFactKeys` to `[]`, synthesise-all would re-send a pre-park amended fact as `fact:<key>` and write a false `USER_CONFIRMED` plus `system.field_confirmed` (D-6), a fabricated provenance record, worse than F3's absence. Instead: keep the existing session-array assembly. On resume the arrays are empty, so no fact entries are sent; an unreviewed catalogue fact simply retains its catalogue-curated provenance (its honest seeded state), never a false confirmation. The recap surfaces this as a completable prompt ("N catalogue facts have not been reviewed this session; kept as catalogue values unless reviewed"), converting the silent F3 gap into a visible, truthful, non-blocking nudge.
*Rejected:* (a) Path A (persist `amendedFactKeys` in `draft_blob`, restore on resume): correct but a `draft_blob` shape change and an INV-83 B1 split (amendments durable, confirms transient); heavier, and the founder is relaxed about draft-time bookkeeping, so truthful absence suffices. (b) server default-confirm of absent facts: fabricates provenance. (c) synthesise-all as originally drafted: fabricates provenance on resume (the B2 defect).

**DF-RR-4 - INV-83 re-gate kept.** Enforced end-to-end via B plus the gate.
*Rejected:* relaxing INV-83 (DF-RR-1(c)).

**DF-RR-5 - No resume clamp.** `RESUME_FROM_DRAFT` keeps restoring the saved step; resume lands where the user left off. E makes a clamp redundant.
*Rejected:* resume-to-intake / resume-to-earlier clamp.

---

## 4. Design

**Change 1 (B) - `SEED_INTAKE` basis re-derive.** Compute each seeded field's basis by value-vs-seed: value equals `fp.<field>.value` then basis is `fp.<field>.basis` (a kept derived default re-reads `"derived"` and re-gates; a catalogue field re-reads `"catalogue"`); value differs then `"user-set"` (server derives `USER_AMENDED`). Value seeding keeps the empty-guard. Aligns the client basis with the server 422 predicate.

**Change 2 (E-compact) - pre-commit disposition gate.** New tenant-local component `apps/tenant/lib/intake/pre-commit-disposition-gate.tsx` (INV-84 / `FactValue`, FE-34 / `GroupedMultiSelect` locus precedent; DF-UC-4 single-consumer), rendered at the foot of `UseCaseCreateStep`, shown only when `derivedUnconfirmed` is non-empty. Contents:
- One row per unconfirmed intake-derived field (`operator_role_id`, `lifecycle_stage`): label, current value, "Derived, confirm or update" caption, a Confirm action (`CONFIRM_INTAKE_FIELD`), and a Change action that reveals the field's `SingleSelect` (edit dispatches `SET_INTAKE_FIELD` → basis `"user-set"`, row drops). A confirmed field shows a confirmed indicator.
- A facts recap (Path B wording): count from the product fact set, "have not been reviewed this session; kept as catalogue values unless reviewed", plus a Review-facts link that navigates to `prefill`. Non-blocking.
- The step's Register action is disabled until `derivedUnconfirmed` is empty. Facts never block.
Composed with `SectionGroup` (FE-27), neutral tokens, no `--verdict-*`. Hidden in the normal walked-through flow (fields already confirmed at `intake`).

**Shared predicate (V2).** Extract `derivedUnconfirmed(prefillBases, confirmedIntakeFields): IntakeFieldName[]` into a shared module consumed by both `IntakeCaptureStep` and the gate, so the two cannot diverge or double-count. Predicate: `basis === "derived" && !confirmedIntakeFields.includes(field)` over `operator_role_id`, `lifecycle_stage`.

**Resume-window guard (V1).** The step holds the gate render and disables Register until `usePrefill` has resolved and `SEED_INTAKE` has re-derived bases (`intakePrefillBases` non-null). Fold `usePrefill.isLoading` into the step's existing loading guard (which already gates on `categoryMemberships`). Prevents the null-`intakePrefillBases` window where `derivedUnconfirmed` is falsely empty and a submit 422s.

**Fact assembly (unchanged under Path B).** `confirmed_fields` continues to be assembled in `handleSubmit` from session `confirmedIntakeFields` / `confirmedFactKeys` / `amendedFactKeys`. No synthesise-all. `usePrefill` is called in the step only for the recap count and the loading guard.

---

## 5. present-vs-ALTER (surface enumerated, N1)

| Element | present | ALTER |
|---|---|---|
| `SEED_INTAKE` basis | `state.<field> ? "user-set" : fp.basis` | value-vs-seed: `== fp.value → fp.basis`, else `"user-set"` (B) |
| `SEED_INTAKE` value seed | `state.<field> ?? fp.value ?? null` | unchanged (empty-guard preserved) |
| `derivedUnconfirmed` predicate | inline in `IntakeCaptureStep` | extracted to a shared module, consumed by intake step + gate (V2) |
| Use-case step commit affordance | Register, no disposition gate | pre-commit disposition gate (FE-36), shown when `derivedUnconfirmed` non-empty; Register gated on it (E) |
| Use-case step new deps | receives `confirmedFactKeys` / `amendedFactKeys` props | adds `intakePrefillBases`, `confirmedIntakeFields`, `onConfirmField` (`CONFIRM_INTAKE_FIELD`), `onFieldChange` (`SET_INTAKE_FIELD`), intake vocab (`useOperatorRoles`, `LIFECYCLE_STAGE_OPTIONS`, shared with `IntakeCaptureStep`, N2), and `usePrefill` (facts recap + loading guard, V1) |
| Fact recap wording | (none) | Path B: "not reviewed this session; kept as catalogue values unless reviewed"; never asserts confirmation (B2) |
| `confirmed_fields` fact assembly | session `confirmedFactKeys` / `amendedFactKeys` | unchanged (Change 3 dropped, DF-RR-3) |
| `RESUME_FROM_DRAFT` step | restores saved step | unchanged (no clamp, DF-RR-5) |
| Server disposition logic; `draft_blob` shape | as-is | unchanged |

---

## 6. Proposed invariants (provisional, reconcile at handoff)

1. **INV-83 ALTER** - extend the transience rule: on `RESUME_FROM_DRAFT` a restored seeded value re-derives its basis by value-vs-seed (a kept derived default re-reads `"derived"` and re-gates); the re-gate is satisfiable at the pre-commit disposition gate, not only the intake step; a catalogue fact not re-reviewed on resume retains catalogue-curated provenance and the client never synthesises a `USER_CONFIRMED` for it. No change to server predicates or the "not persisted in `draft_blob`" rule. Refs: D-74, D-75, FE-32, FE-36, D-6, DF-D3-1.
2. **FE-36** - CONVENTION - the registration wizard renders a pre-commit disposition gate at the foot of the use-case step when any intake-derived default is undispositioned; inline confirm/amend for the derived fields (the only hard gate) plus a non-blocking facts recap (Path B wording, never asserting confirmation) with a Review link to `prefill`; composed with `SectionGroup`, no `--verdict-*`; the gate and `IntakeCaptureStep` share the `derivedUnconfirmed` predicate. Refs: INV-83, D-74, FE-27, FE-32, INV-84.
3. **New D-n (Path B policy)** - on resume, catalogue facts not re-reviewed retain catalogue-curated provenance; the client never synthesises `USER_CONFIRMED` for an unreviewed fact; the pre-commit recap surfaces the gap as a completable, non-blocking prompt. Durable (source-of-truth for fact disposition on resume), so a definite D-n, not a sprint-local DF (N3). Number reconciled at landing.

---

## 7. Delta summary

Client-only. `wizard-state.ts` (`SEED_INTAKE` basis); new shared `derivedUnconfirmed` module; new `pre-commit-disposition-gate.tsx`; `use-case-create-step.tsx` (gate render, Register gate, new deps, `usePrefill` for recap + V1 guard). 0 backend, 0 schema, 0 migration, 0 route, 0 enum, 0 contract, 0 `draft_blob` shape. INV-83 ALTER; new FE-36; new D-n (Path B); DF-RR-1..5. No INV renumber; stable tier untouched.

---

## Review findings, folded

- **B1 (blocking, accepted):** `confirmed_fields` locus corrected to `use-case-create-step.tsx::handleSubmit`; `usePrefill` called in the step (cache-shared) for the recap; `page.tsx` reference removed. Under Path B no commit-time assembly change remains.
- **B2 (blocking, founder call = Path B):** synthesise-all dropped; unreviewed facts retain catalogue-curated provenance; recap never asserts confirmation; specimen wording updated.
- **V1 (accepted):** resume-window race closed by folding `usePrefill.isLoading` + null-`intakePrefillBases` into the step guard; added to Section 0 and done-checks.
- **V2 (accepted, strengthened):** `derivedUnconfirmed` extracted to a shared module rather than asserting byte-identity.
- **N1 (accepted):** step's new prop/wiring/vocab/`usePrefill` surface enumerated in Section 5.
- **N2 (accepted):** two-homes for the intake selects acknowledged (gate is the commit-point net, intake step primary); shared vocab hooks, no duplication.
- **N3 (accepted):** Path B fact policy minted as a definite D-n, not agent's-call.

---

## Appendix A - Forward items (post-MVP)

- **Intelligent wizard:** conditional field presentation and inline per-field disposition keyed off product archetype or classification (a note-taker sees a reduced field set; an autonomous HR screener the full battery). Requires a rule layer; adjacent to deferred #1 (product-driven prefill) and OPEN-3 (applicability). E-compact generalises into the per-screen gate this implies, so nothing here is throwaway. Recorded for post-MVP weighing.
- **Carry-over (unrelated to OPEN-5):** the OPEN-4 reclassification decision (single-operator tenants supported via multiple memberships; genesis API self-assignment deferred to exception management) is a pending canon item to record; provisional D-n above D-76, landing order.

## Appendix B - Source-verification register (D-21)

| # | Item | Status |
|---|---|---|
| SV-1 | Exact `SEED_INTAKE` basis expression and value empty-guard | Confirm at WI-0; B touches only the basis expression (review-confirmed implementable) |
| SV-2 | Skipping `prefill` on resume drops fact dispositions, no 422 (silent) | Resolved (`_dispose_fact_prefill`); re-confirm at HEAD |
| SV-3 | No client-side pre-submit disposition gate exists today | Resolved; E is genuinely new surface |