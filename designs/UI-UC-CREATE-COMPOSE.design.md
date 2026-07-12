# DESIGN DOC (FINAL) - UI-UC-CREATE-COMPOSE

**Use-case-create step: composition, heightened-duty grouping, defaults discipline**

**Status:** FINAL, review folded (fresh-chat four-bucket, all findings dispositioned) - founder decisions DF-UC-1..5 resolved - handoff issued as paired file
**Surface:** `apps/tenant/app/systems/new/_steps/use-case-create-step.tsx` (registration wizard terminal step)
**Lineage:** DM-S4b, FE-31, INV-82, FE-4, INV-73, FE-26, FE-27, DF-D3-1
**Live ceilings (from INDEX, verified HEAD in review):** INV-85, D-76, FE-33
**New IDs (provisional, reconcile against live ceiling at handoff):** FE-34, FE-35; FE-31 ALTER (wording); DF-UC-1..5
**Delta target:** presentational. 0 backend, 0 schema, 0 migration, 0 route, 0 enum, 0 contract, 0 `draft_blob` shape.
**Grounding:** live code, DATA-MODEL, DECISIONS, FRONTEND, STATE read this session. `data_category` / `affected_party` seed rows absent from the KB mirror, routed to Appendix B (D-21).
**Binding specimen:** `uc-create-step-spec.html`.

---

## Section 0 - Pre-flight verify checklist (coding agent, before WI-1)

1. Confirm `UseCaseCreateStep` is at the read state: title is a raw `<input>`; five vocab fields via `SingleSelect` / `MultiSelectInput`; `title`, `intendedUseCategoryId`, `usageContextId`, `humanOversightTypeId`, `dataCategoryIds`, `affectedPartyIds` all local `useState`, empty init.
2. Dump live `data_category` rows (`code`, `label`, `is_special_category`, `sort_order`, `framework_ref`) and `affected_party` rows (same plus `is_vulnerable_group`) from the tenant DB. Partition and taxonomy baseline (SV-1, SV-2, D-21).
3. Confirm `DataCategoryOut.is_special_category` and `AffectedPartyOut.is_vulnerable_group` are already on the reference reads (`app/schemas/reference.py`; `GET /reference/data-categories`, `GET /reference/affected-parties`). Grouping needs no contract change. (Verified in review.)
4. Confirm `SingleSelect` placeholder (INV-81, FE-4 DM-S4a ALTER) already renders "Select..." here. No work item.
5. Confirm `TextInput` import path from `@irontrust/ui`. Already imported by `intake-capture-step.tsx` in this app; confirm at the import line (SV-5, pre-cleared in review).
6. Confirm `SectionGroup` (`packages/ui/src/scaffold/section-group.tsx`, FE-27) and FE-26 elevation tokens are available for import. Resolved in canon (UI-V2-DEPTH-LAYOUT); not a live-DB item.

---

## 1. Scope and surface

**Surface identity.** Registration wizard terminal step, not `use-cases/[id]` (assessment surface, `assessment-page-client.tsx`). Any "C3 = F3 use-cases/[id]" planning label is a mislabel; the locus is the wizard step above. (Confirmed in review.)

**Canon currency.** STATE current through UI-DRAFT-RESUME-GATE (2026-07-11), a presentational draft-gate fix with zero delta to this step; read code treated as HEAD. Verified against the mirror in review. Only gap: seed enumeration (Appendix B).

**In scope:** presentational composition (title primitive, FE-27 sectioning, heightened-duty grouping of the two multiselects), plus a one-line FE-31 canon-accuracy correction (DF-UC-5).
**Out of scope (deferred #1, next sprint):** product-driven prefill of `data_category` / `affected_party` / `intended_use_category`, the INV-83 disposition extension any such default requires, and lifting the use-case fields to wizard-state-controlled (which #1 does where prefill needs it). Rationale in Section 3, DF-UC-1 and DF-UC-5.

---

## 2. Problem statement (grounded)

| # | Defect | Evidence | Cite |
|---|---|---|---|
| P1 | Title uses a raw `<input>`, not the `TextInput` primitive | `<input id="use-case-title" ...>` in the step | FE-4 (UI-C2 ALTER migrated IntakeCaptureStep; this step missed) |
| P2 | Flat 14-chip / 6-chip walls, no hierarchy; heightened-duty items visually indistinguishable from ordinary ones | one `MultiSelectInput` per field over the full vocab | FE-4, INV-73; `is_special_category` / `is_vulnerable_group` on the reads but unsurfaced |
| P3 | No defaults on any field; intended-use single-membership case not preselected | all local `useState`, empty init | FE-31, INV-82; CAT-4 defaults-must-be-dispositioned (INV-83, D-74) |
| P4 | Data-category taxonomy is GDPR Art. 9-led; likely non-exhaustive for a typical AI SaaS; candidate gap: Art. 10 criminal-offence data | screenshot: 8 Art. 9 special categories plus 6 common categories | unverified vs live seed (SV-1, SV-3) |

---

## 3. Resolved decisions (rationale plus rejected alternatives; sprint-local DF-UC-n)

**DF-UC-1 - Scope: presentational only.** Ships Moves 1, 2, 3, plus the DF-UC-5 canon fix. Defaults deferred to #1.
*Why:* even the smallest default trips INV-83. A single-membership `intended_use_category` preselect is a derived default and must be dispositioned before the registration transaction commits (INV-83, D-74), a backend and near-stable-tier change. Product-derived `data_category` / `affected_party` prefill additionally needs a catalogue bridge that does not exist: `_build_field_prefills` seeds only `operator_role_id`, `hosting_model_id`, `lifecycle_stage`, `purpose`; `catalogue_fact` is display-only prefill facts with provenance (CAT-4, D-69) rendered by `FactValue`, and typed curated prefill lives in `catalogue_product.hosting_model_id` / `intended_use` (D-69); neither `catalogue_fact` nor `catalogue_product_risk` maps to these fields. Absent the bridge a default is a guess, and a wrongly pre-ticked special-category selection a user confirms is a worse governance defect than an empty field.
*Rejected:* (a) smuggle the one obvious default in now, drags in the full disposition extension anyway; (b) pull the whole bridge plus INV-83 extension into this sprint, a multi-item backend sprint that blocks the visual fix and contradicts deferred-queue ordering.

**DF-UC-2 - Grouping: labelled heightened-duty subgroups.** Each multiselect partitions into a heightened-duty subgroup and an "Other" subgroup, driven by the flag on the read. Treatment is structural: neutral hairline left rule, subheading, muted Art. reference caption. No `--verdict-*`, no alarm colour, no brand on the subgroup rule (N1). Petrol is reserved to the FE-27 section level (D-57).
*Rejected:* keep flat and weight only special-category chips, leaves the affected-parties wall unsolved and gives weaker structural clarity.

**DF-UC-3 - Taxonomy (P4): separate seed/reference track.** GLOBAL `data_category` change (INV-48) with heightened-duty-flag and classification reach, gated on the live-DB enumeration (SV-1, SV-3). Not folded into this pass; does not block it.
*Rejected:* block this sprint on P4, couples a data-model decision to a UI pass and stalls a zero-risk fix.

**DF-UC-4 - `GroupedMultiSelect` home: tenant-local.** Single consumer; tenant-local composition wrapping the FE-4 `MultiSelectInput` primitive, at `apps/tenant/lib/intake/grouped-multi-select.tsx`. Governing precedent INV-84 (`FactValue`, `apps/tenant/lib/intake/fact-value.tsx`), the exact locus and directory. Chip primitive stays shared (`MultiSelectInput`, `packages/ui`, INV-73 locus).
*Rejected:* promote to `packages/ui` now, no second consumer justifies a shared primitive yet.

**DF-UC-5 - FE-31 restore clause: correct to match DF-D3-1; hold local state.** DF-D3-1 stores only pre-boundary fields in `draft_blob` and explicitly excludes use-case fields (title, vocab selections), which are captured at the atomic boundary step. `toDraftBlob` (`page.tsx`) confirms it: use-case fields are never written. The `RESUME_FROM_DRAFT` line `intendedUseCategoryId: blob.intendedUseCategoryId ?? null` reads a key `toDraftBlob` never writes, so it always resolves to null, and the step does not consume `WizardState.intendedUseCategoryId` (local `useState`). It is doubly dead. FE-31's "persisted to draft blob; restored on `RESUME_FROM_DRAFT`" clause is the inaccuracy. Fix: delete the dead line; correct the FE-31 clause. `GroupedMultiSelect` takes `values` + `onChange`, agnostic to whether the parent holds state locally or in wizard state, so Appendix A's forward-compat guarantee holds regardless; #1 lifts the parent to controlled where prefill needs it, without touching `GroupedMultiSelect`.
*Rejected:* reverse DF-D3-1 and persist use-case fields to `draft_blob` to make resume repopulate them, a `draft_blob` shape change and a reversal of a shipped decision for near-zero functional gain (the use-case step is the terminal pre-commit step), a DM-track sprint, not this pass.

---

## 4. Design

**Move 1 - FE-4 conformance.** Title raw `<input>` becomes the `TextInput` primitive, same chrome, with a placeholder.

**Move 2 - Heightened-duty grouping (the clutter fix).** New tenant-local `GroupedMultiSelect` renders the FE-4 `MultiSelectInput` chip cluster under two labelled subgroups sharing one selection array:
- Data categories: "Special-category data (GDPR Art. 9, heightened duty)" where `is_special_category`; "Other personal data" otherwise.
- Affected parties: "Vulnerable groups (EU AI Act Art. 27, heightened duty)" where `is_vulnerable_group`; "Other affected parties" otherwise.

Partition follows the flag, not the label: if a seed row's flag disagrees with intuition, the grouping follows the flag. Subgroup rule is neutral hairline; no brand, no `--verdict-*` (N1, INV-73, D-57). Selection semantics, the `data_category_ids` / `affected_party_ids` payload, and INV-73 chip tokens are unchanged. Two flat walls become four short clusters.

**Move 3 - FE-27 sectioning + FE-26 elevation.** The single flat card is composed as two `SectionGroup` regions (petrol accent bar and brand label per FE-27 / D-57): "Use & oversight" (title, intended-use category, usage context, human oversight) and "Data & affected parties" (the two grouped multiselects). Card on `bg-paper` + `--elevation-raised` (FE-26). No hand-rolled section chrome; the kit primitive is mandatory here (INV-69 / INV-70; DF-V2-3 earmarked this surface for depth/layout adoption).

**Move 4 - Defaults, held to INV-83 (deferred, no code this sprint).** No silent prefill. `intended_use_category` single-membership auto-select joins the INV-83 disposition set only in #1. `usage_context` and `human_oversight`: placeholder, no default. `data_categories` / `affected_parties`: safe default is empty plus forced affirmation; product-derived prefill waits on the #1 bridge. The specimen renders every field empty.

---

## 5. present-vs-ALTER

| Element | present | ALTER |
|---|---|---|
| Title control | raw `<input className="border-hairline w-full rounded border px-3 py-1.5 text-sm">` | `TextInput` primitive (FE-35 / FE-4), placeholder added |
| Data-categories field | one `MultiSelectInput` over full vocab | `GroupedMultiSelect`: special-category subgroup + other subgroup (FE-34) |
| Affected-parties field | one `MultiSelectInput` over full vocab | `GroupedMultiSelect`: vulnerable-groups subgroup + other subgroup (FE-34) |
| Card / sectioning | single flat card, `space-y-4` | two `SectionGroup` regions (FE-27), card on `bg-paper` + `--elevation-raised` (FE-26) |
| `RESUME_FROM_DRAFT` | dead `intendedUseCategoryId: blob.intendedUseCategoryId ?? null` line | line removed; FE-31 clause corrected (DF-UC-5, DF-D3-1) |
| `title` payload | `title` in `RegistrationCreate` | unchanged |
| `intended_use_category_id` payload | captured this step, in `RegistrationCreate` (FE-31) | unchanged |
| `data_category_ids` / `affected_party_ids` payload | arrays | unchanged (forward-compat for #1) |
| SingleSelect placeholders | "Select..." (INV-81) | unchanged |

---

## 6. Proposed invariants (provisional, reconcile at handoff)

1. **FE-34** - CONVENTION - A vocab multiselect whose options carry a heightened-duty flag (`is_special_category`, `is_vulnerable_group`) renders partitioned under a labelled heightened-duty subgroup via `GroupedMultiSelect`; the partition follows the flag, the subgroup rule is neutral hairline (no brand, no `--verdict-*`), and the selection contract plus INV-73 chip tokens are unchanged. Referenced INV-73, FE-4, D-57, INV-84, DATA-MODEL `data_category` / `affected_party`.
2. **FE-35** - CONVENTION - `UseCaseCreateStep` title uses the `TextInput` primitive; no raw `<input>` remains in the intake wizard. Referenced FE-4.
3. **FE-31 ALTER** - wording correction only: use-case fields (title, intended-use category, vocab selections) are not persisted to `draft_blob` and are not restored on resume, per DF-D3-1; the prior "persisted to draft blob; restored on `RESUME_FROM_DRAFT`" clause is struck. Referenced DF-D3-1, D-66.

No INV-83 amendment this sprint (Move 4 deferred). No new D-n.

---

## 7. Delta summary

Presentational plus one dead-line removal. New tenant-local `grouped-multi-select.tsx`; `use-case-create-step.tsx` rewired to `GroupedMultiSelect` + `TextInput` + two `SectionGroup` regions + FE-26 elevation; one dead line removed in `wizard-state.ts`. 0 backend, 0 schema, 0 migration, 0 route, 0 enum, 0 contract, 0 `draft_blob` shape. Two new CONVENTION FE-n; FE-31 wording ALTER; no INV-n renumber; stable tier untouched.

---

## Appendix A - Forward-links (deferred #1, next sprint)

- Product-driven prefill bridge: catalogue -> `data_category` and catalogue -> `affected_party` (new GLOBAL reference table(s), migration, seed across the ~45 design-partner products).
- Registration-time derivation of proposed selections.
- INV-83 extension to set-valued fields (new disposition shape; scalar `(system_id, field_key)` is insufficient), plus `intended_use_category` single-membership derived default.
- Lift the use-case fields to wizard-state-controlled where prefill needs it; FE-30 basis captions; transient disposition state; contract additions.
- **Forward-compat honoured here:** `GroupedMultiSelect` exposes `values` + `onChange` and is agnostic to the parent's state source, so #1 lifts the parent to controlled and seeds the same `data_category_ids` / `affected_party_ids` arrays without touching `GroupedMultiSelect`.

## Appendix B - Source-verification register (D-21)

| # | Claim needing live-DB confirmation | Status / action |
|---|---|---|
| SV-1 | Full `data_category` seed set (codes, labels, `is_special_category`, `sort_order`) | Open. Dump rows; partition baseline (Move 2) and P4 baseline |
| SV-2 | Full `affected_party` seed set (plus `is_vulnerable_group`) | Open. Dump rows; partition baseline (Move 2) |
| SV-3 | Art. 10 (criminal-offence) and common-SaaS categories (communications content, usage/telemetry, device/technical, audio/voice, imagery) present or absent | Open. Compare live set to candidate additions before any DF-UC-3 track |
| SV-4 | V2 depth/layout foundation for wizard steps | Resolved in canon: FE-26 / FE-27 (UI-V2-DEPTH-LAYOUT). Not a live-DB item |
| SV-5 | `TextInput` exported and importable in this app path | Pre-cleared: imported by `intake-capture-step.tsx`; confirm at import line |