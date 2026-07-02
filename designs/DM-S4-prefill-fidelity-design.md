# DM-S4a — System-Intake Prefill Fidelity and Form-Defect Fix (FINAL)

**Status:** FINAL · review folded (B1, SV-a/b/c, N1-N6) · handoff cut as paired file. **Supersedes** the proposal draft and the discarded `DM-S4-prefill-fidelity-design.md`.
**Split:** S4a (this) = system-intake prefill plus the form defect, no classifier change. **S4b** (later) = intended-use category, envelope, gate-1 refinement, drop `UseCase.purpose`.
**Floors at entry:** `D-67` · `INV-80` · `FE-29`. **Target ceilings (proposed, append-only):** `D-68`, `D-69`, `D-70` · `INV-81` · `FE-30` · `FE-4` ALTER.
**Delta envelope:** schema **+2 additive nullable columns** on `catalogue_product` · response schema **extended** (`PrefillResponse` gains a typed `field_prefills`) · routes **0** · migrations **1** · curation pass (non-blocking) · one primitive ALTER (`SingleSelect`) · one reducer action + intake-step prop change.
**Out of scope:** `usage_context`, `UseCase.purpose`, the intended-use category, the envelope, and any `resolve_classification` change (all S4b); `D-64` untouched.

---

## Review fold (every finding mapped to its resolution)

| Finding | Disposition | Where folded |
|---|---|---|
| **B1** intake step under-enumerated; resume unsatisfiable | Accepted | WI-5 rewritten: `page.tsx` owns the prefill read and a `SEED_INTAKE` reducer action; `IntakeCaptureStep` becomes wizard-state-controlled; precedence stated. |
| **SV-a** `SingleSelect` empty/unmatched render | Open, gating | §0.1; the WI-6 primitive fix holds whether or not a placeholder exists today. |
| **SV-b** `deployer` `eu_operator_role` code | Open | §0.3. |
| **SV-c / N6** `purpose` is `metadata_blob["purpose"]`, not a column | Accepted | R-3 corrected; WI-3, WI-7, `D-68`, `D-69` reworded; no `system.purpose` column minted. |
| **N1** placeholder + `INV-81` belong in the primitive; `INV-81` is new, not an `INV-75` extension | Accepted | WI-6 (primitive ALTER); `INV-81` bound to `SingleSelect`, decoupled from `INV-75`. |
| **N2** seed `name` from `catalogueProductName`, not a server field | Accepted | WI-3 drops `name` from `field_prefills`; WI-5 seeds `name` client-side. |
| **N3** open `dict` weakens the contract | Accepted | WI-4 defines a typed `FieldPrefills` model with named optional keys. |
| **N4(a)** derived role shown but unconfirmed | Accepted | WI-5/FE-30: basis caption reads "derived, confirm". |
| **N4(b)** S4b must not treat a derived-unconfirmed role as authoritative | Recorded forward | Appendix A: binding S4b constraint; no S4a storage change (founder may override). |
| **N5** shared-resolver blast radius; custom no-op automatic | Accepted | WI-3/WI-5 notes; Appendix A; additive-key tolerance done-check. |

---

## §0 Pre-flight verify checklist (live DDL / HEAD, D-21)

1. **`SingleSelect` empty/unmatched behaviour (GATING).** Open `packages/ui/src/structured-input/single-select.tsx`. Confirm whether it injects a placeholder `<option value="">` when `value === ""` or unmatched. If absent (expected, given `control-links.tsx` prepends its own), P-2 is real and WI-6 adds the placeholder to the primitive. If present, P-2 reduces to the `handleSubmit || null` divergence and WI-6 asserts the existing behaviour; `INV-81` still binds.
2. **`catalogue_product` columns.** Confirm no `hosting_model_id` and no `intended_use` at HEAD (`domain.py`). WI-1 targets.
3. **`deployer` `eu_operator_role`.** Confirm the row exists and capture its exact `code` (WI-3 derivation literal).
4. **`SystemLifecycleStage`.** Confirm `{development, pilot, production, retired}` (enum `system_lifecycle_stage`); `production` is the "deployed" derivation target.
5. **`purpose` storage.** Confirm `system` has **no** `purpose` column and that purpose is written to `metadata_blob["purpose"]` (`system_service.update_system`; `RegistrationCreate.purpose` flows to the blob). No schema delta for purpose.
6. **`PrefillResponse` and shared resolver.** Confirm `{catalogue_product_id, facts[]}` and that `get_prefill_by_product` is shared by `GET /catalogue/products/{id}/prefill` and `GET /systems/{id}/prefill`. Confirm `PrefillStep` reads `prefill.data?.facts` only, so an additive `field_prefills` key is tolerated by the system-prefill consumer.
7. **Draft blob and reducer.** Confirm `draft_blob` persists the five intake fields (`DF-D3-1`) and that the resume action restores them into wizard state before the intake step renders (WI-5 precedence relies on this).

---

## Resolved decisions (settled; not reopened)

| # | Settled | Authority |
|---|---|---|
| R-1 | Prefill is `{value, basis}`: the seeded value is the submitted value; the basis is shown; override is a structured pick with deviation tracked. | `D-1`, UX §3, `FE-5` |
| R-2 | Vocab wherever a vocab exists. The only free-text intake field is the `purpose` capture field, because no taxonomy fits and it is catalogue-seeded and contained. | UX §3 |
| R-3 | The `purpose` capture field is the developer intended-use, documentary, ISO 42005-aligned, catalogue-seeded from `catalogue_product.intended_use`. **Its store of record is `metadata_blob["purpose"]`, not a `system.purpose` column.** | this thread; `D-21`; `domain.py` |
| R-4 | Hosting model, operator role, and lifecycle stage are vocab/enum on both paths. Non-custom seeds or derives; custom is an explicit select with no seed. | UX §3 |
| R-5 | Non-custom derivations: operator role = deployer; lifecycle = production (deployed). Both shown with a "derived, confirm" basis and overridable. | this thread; N4(a) |
| R-6 | Source order is catalogue, then derived, then safe default. Tenant-history is not a source this sprint. | this thread |
| R-7 | Curated prefill knowledge lives in typed columns on `catalogue_product` (`hosting_model_id`, `intended_use`), not in `catalogue_fact`; single-homed and vocab-resolvable. | single-home; `D-21` |
| R-8 | `usage_context` is the audience/exposure axis (`UsageContext` docstring), unrelated to prefill or tiering; untouched here. | `D-64`; `intake.py` |

---

## Scope (dependency-ordered)

### WI-1 · Curated catalogue columns (schema)
Add `catalogue_product.hosting_model_id uuid NULL` (FK `hosting_model`, `ON DELETE SET NULL`) and `catalogue_product.intended_use text NULL`. One migration.

### WI-2 · Curation/seed pass
Populate both columns for the active catalogue (design-partner cohort first). Non-blocking: null `hosting_model_id` falls through to the vocab select; null `intended_use` leaves the purpose field blank.

### WI-3 · Prefill resolver returns typed field prefills (server)
Extend `get_prefill_by_product` to return `field_prefills` carrying only what the client lacks: `hosting_model_id` (from the new column, basis `catalogue`, omitted when null), `purpose` (from `intended_use`, basis `catalogue`, omitted when null), `operator_role_id` (the deployer vocab id, basis `derived`), `lifecycle_stage` (`production`, basis `derived`). **`name` is not included** (N2: seeded client-side from `catalogueProductName`). A field with neither a catalogue value nor a derivation is omitted, never fabricated. Placing the derivation here is sound because a present `product_id` implies `is_custom = false` (`ck_system_custom_no_catalogue`), so the custom path never reaches it.

### WI-4 · Typed response schema and contract
Define `FieldPrefill = {value, basis}` and a `FieldPrefills` model with named optional keys (`hosting_model_id`, `operator_role_id`, `lifecycle_stage`, `purpose`), each value typed per field (uuid, uuid, enum-string, text). Add `field_prefills: FieldPrefills | None` to `PrefillResponse`. Regenerate the `@irontrust/api-client` contract. No open `dict` (N3).

### WI-5 · Wizard seed, resume precedence, and intake-step rewire (client)
- **`page.tsx`** reads `usePrefill(catalogueProductId)` and, on prefill load, dispatches a `SEED_INTAKE` reducer action that fills wizard-state fields **only when empty**: `name` from `catalogueProductName`; `hosting_model_id`, `operator_role_id`, `lifecycle_stage`, `purpose` from `field_prefills`.
- **Precedence:** draft-restored > catalogue/derived > blank. The empty-guard encodes it: resume restores the blob into wizard state before `SEED_INTAKE`, so restored values and user edits are never clobbered.
- **`IntakeCaptureStep`** becomes wizard-state-controlled: its props gain the seed/value inputs and change handlers dispatch to the reducer; it no longer self-initialises via `useState("")`. `handleSubmit` submits the bound values (the seeded id, never `|| null` over a shown value).
- **Basis caption (FE-30):** each seeded field renders its basis beneath the control, reusing `FE-5`'s provenance vocabulary. Derived fields read "derived, confirm" (N4(a)); a user edit clears the basis to user-set.
- **Custom path:** automatic by construction (N5). `usePrefill` is `enabled: Boolean(catalogueProductId)`, so a custom registration fires no request, `field_prefills` is absent, `name` seeds from a null `catalogueProductName` (stays blank), and the selects render the WI-6 placeholder.

### WI-6 · `SingleSelect` placeholder in the primitive (FE-4 ALTER)
The primitive renders a leading non-selectable placeholder option and shows it whenever the bound `value` is empty or unmatched, so the displayed selection always reflects the bound state. Intake is the first consumer; the change is global, so sweep current `SingleSelect` consumers for the cosmetic shift (first-option to placeholder) as a regression check. This is the single home for the display-equals-submit guarantee (`INV-81`), not a per-call-site patch.

### WI-7 · Canonical update (last)
Update `STATE` (intake prefill capability; current-through line) and `DATA-MODEL` (the two `catalogue_product` columns **only**; no `system.purpose` column, N6). Append `D-68`, `D-69`, `D-70`, `INV-81`, `FE-30`, and the `FE-4` ALTER note. Record the N4(b) forward constraint against S4b. Never renumber a live `INV-n`; leave the stable tier untouched.

---

## Invariants and decisions to mint (proposed)

1. **D-68 · Prefill is `{value, basis}` and the seed is the submission.** A prefilled or derived field seeds the bound value; shown equals submitted; the basis renders; override is a structured pick with tracked deviation. The `purpose` field's store of record is `metadata_blob["purpose"]` (no `system.purpose` column). Refs: `D-1`, UX §3, `INV-75`, `D-21`.
2. **D-69 · Curated prefill knowledge lives in typed `catalogue_product` columns.** `hosting_model_id` (vocab FK) and `intended_use` (text) are curated catalogue content, single-homed, distinct from the free-form `catalogue_fact` panel; `intended_use` seeds the `purpose` capture field, it is not itself a `system` column. Refs: `R-7`, `D-21`, single-home.
3. **D-70 · Structured-field defaults derive from `is_custom`.** Non-custom derives operator role = deployer and lifecycle = production, both overridable with a "derived, confirm" basis; custom seeds neither. Tenant-history as a prefill source is rejected this sprint. Refs: `R-5`, `R-6`.
4. **INV-81 · CONVENTION · `SingleSelect` never renders a value its bound state does not hold.** When `value` is empty or unmatched, the primitive shows a placeholder, never a silent first option; the submitted value always equals the displayed value. A new display-equals-submit constraint (distinct from `INV-75`, which governs raw-null-on-the-face). Locus: `packages/ui/src/structured-input/single-select.tsx`. Refs: `FE-4` ALTER, `D-68`.
5. **FE-30 · Intake-capture prefill basis caption.** Seeded intake fields render a basis caption beneath the control using `FE-5`'s provenance vocabulary; derived fields read "derived, confirm"; a user edit clears to user-set. Refs: `FE-5`, `INV-75`.
6. **FE-4 ALTER · `SingleSelect` placeholder.** The primitive gains the empty/unmatched placeholder render (the `INV-81` locus).

---

## Present-vs-ALTER summary

| Surface | Present | ALTER |
|---|---|---|
| `catalogue_product` | no `hosting_model_id`, no `intended_use` | `+ hosting_model_id uuid NULL` (FK), `+ intended_use text NULL` |
| `get_prefill_by_product` | returns `facts[]` | also returns typed `field_prefills` (no `name`) |
| `PrefillResponse` / api-client | `{catalogue_product_id, facts[]}` | `+ field_prefills: FieldPrefills \| None` |
| `page.tsx` (wizard) | no intake prefill read | reads `usePrefill`, dispatches `SEED_INTAKE` (empty-guarded) |
| `wizard-state` reducer | restores fields on resume | `+ SEED_INTAKE` action; precedence draft > catalogue/derived > blank |
| `IntakeCaptureStep` | five `useState("")`, self-init | wizard-state-controlled; props carry seeds; basis captions |
| `SingleSelect` | first-option when empty/unmatched (pending SV-a) | placeholder when empty/unmatched (`INV-81`) |
| `handleSubmit` | `operatorRoleId \|\| null` | submits the bound id; no display/submit divergence |
| `usage_context`, `UseCase.purpose`, classifier | unchanged | unchanged (S4b) |

---

## Appendix A — Open items

- **Founder decision (N4(b)):** S4a does not add a confirmation-provenance bit; it records a binding constraint that **S4b must re-confirm operator role before deriving obligations** (`OPEN-3`), never treating a derived-never-confirmed posture as authoritative. Override: add a provenance bit to `RegistrationCreate`/`field_prefills` in S4a (small WI-3/WI-4 addition) so S4b inherits it. Recommendation: record forward, do not grow S4a.
- **Custom path (N5):** no enforcement needed. The no-seed, explicit-select behaviour is automatic because `usePrefill` does not fire without a product.
- **FE-30 specimen:** the basis-caption treatment is the one visual the agent builds to; a rendered specimen is the binding spec and is produced before handoff execution (show-don't-tell).

---

## Appendix B — Source-verification register

| SV | Claim | Verify against | Blocks |
|---|---|---|---|
| SV-a | `SingleSelect` injects no placeholder for empty/unmatched (P-2 real). | `packages/ui/src/structured-input/single-select.tsx` @ HEAD | P-2 framing, `INV-81`, WI-6 |
| SV-b | A `deployer` `eu_operator_role` row exists; capture its `code`. | live data / `intake.py` seed | WI-3 derivation |
| SV-c | `purpose` is `metadata_blob["purpose"]`, no `system.purpose` column. | `domain.py`, `system_service` @ HEAD | WI-3/WI-7 framing (confirmed in review) |
| SV-d | `field_prefills` additive key tolerated by the system-prefill consumer (`PrefillStep` reads `facts` only). | `prefill-step.tsx` @ HEAD | WI-4 blast radius |
| SV-e | Draft blob persists the five intake fields; resume restores before intake render. | `DF-D3-1`, reducer @ HEAD | WI-5 precedence |