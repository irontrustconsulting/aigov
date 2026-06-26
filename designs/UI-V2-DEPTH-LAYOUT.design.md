# UI-V2-DEPTH-LAYOUT — Final Design Doc

**Status:** FINAL (v2 review folded) · visual-foundation revision within D-42 + a flagged semantic-fidelity item (the `VerdictChip` label map) · tenant + operator inherit; dashboard is the proving + remediation surface · ids from live ceilings INV-73 / D-56 / FE-25 → FE-26/27, FE-16 `[ALTER]`, FE-21 `[ALTER]`, D-57/58/59/60/61, INV-74/75 · delta: presentational + design-token additions, 0 backend / 0 schema / 0 route · companion: `UI-V2-DEPTH-LAYOUT-handoff.md`.

**v2 review disposition:** all three blockers accepted — **B1** D-57 scoped to section markers + group labels only (input-selection stays on shipped INV-73); **B2** the label map keys on the wire `.value` (lowercase), no `.toUpperCase()` (D-48); **B3** the dashboard zero-state change is recorded as a superseding decision (D-61), and INV-74 is rewritten + forward-scoped so it does not deprecate `FirstRunPanel`. N1–N5 and S1–S3 folded. Mapping in Appendix C.

**Binding visual spec:** the two specimens in this thread — register-form depth direction, and the zero-systems dashboard with depth + scaffolded-empty. (Note: the specimen's petrol-filled selected chips are illustrative only; the shipped INV-73 governs the selected affordance, B1.)

---

## §0 — Pre-flight verify checklist (binding; live reads before any code; D-21)

| id | Verify (live) | Gates |
|---|---|---|
| V-0 (canary) | HEAD is UI-C2 full delivery; ceilings INV-73 / D-56 / FE-25; nothing landed since. | ID baseline. |
| V-1 | `primitives.css` values of `--paper`/`--surface`/`--surface-sunken`; confirm **no** `--shadow-*`/`--elevation-*` token. | FE-26 (new tokens vs deploy; ramp widen). |
| V-2 | `dashboard/page.tsx` zero-systems branch — `FirstRunPanel` takeover (image 1) vs scaffolded-empty. | D-61 / INV-74 remediation. |
| V-3 | `PageScaffold` (`max-w-4xl`) + consumers. | FE-21 `[ALTER]`. |
| V-4 | `contrast.test.ts` (30 pairings at V1) — the full set, since any ramp-value change re-runs all of them (N2). | INV-62. |
| V-5 | `StatCard`/`SectionHeader`/`DataTable`/`EmptyState`/`FirstRunPanel` present in FE-23 kit. | section system composition. |
| V-6 | `verdict-chip.tsx` — confirm it renders its `value` prop as the visible label (not caller `children`). DF-V1-1 (`<VerdictChip value="PARTIAL">`) and the raw-`vendor_check` render strongly indicate this; confirm before committing FE-16 `[ALTER]` (S1). | FE-16 `[ALTER]` locus. |
| V-7 | HEAD-confirm the five verdict-family enums in `pg_enum` match Appendix D (DATA-MODEL §2 currency check, not discovery — N1). | label map completeness. |

Divergence on any read stops the sprint and escalates.

---

## Scope

In: depth + layout foundation (FE-26, FE-27, FE-21 `[ALTER]`, D-57, D-58, INV-74); the semantic-fidelity fold (FE-16 `[ALTER]`, D-60, INV-75, Appendix D); the dashboard re-composition + scaffolded-empty (D-61); the recorded vocab principle (D-59, no build).

Out: full layout re-treatment of F2 detail and F3–F8 (their own passes, inheriting the label map and patterns); the prefill rework (S-B/S-C); directly-rendered enums on F3/F4/F6; any backend/schema change; dark skin (OPEN-V1).

Lift boundary: FE-26/27 and the FE-16 label map are kit-level, so all surfaces inherit; only the dashboard is re-composed here. Other surfaces' done-checks are regression-only.

---

## FRONTEND conventions (FE-n)

- **FE-26 `[NEW]` — Elevation + surface-layering.** Net-new `--elevation-*` shadow tokens (≈2 steps: raised card, overlay) realizing FE-3's unbuilt "elevation"; deployment rules — page on `--surface`, cards on `--paper` + `--elevation-raised`, sub-panels on `--surface-sunken`. Widen the ramp only if V-1 shows it indistinguishable. All pairings stay under INV-62.
- **FE-27 `[NEW]` — Layout + sectioning.** `SectionGroup` (petrol section marker + label + optional `--surface-sunken` sub-panel + divider); two-up/grid field-group guidance; the dashboard stat-row + sectioned-table layout. Composes on the existing FE-23 kit, no new data primitives.
- **FE-16 `[ALTER]` — `VerdictChip` humanized labels.** The chip gains a flat `value`→label map and renders the mapped label instead of the raw `value`; tone map and `data-tone` unchanged. The map keys on the wire `.value` as the server emits it (lowercase snake_case), never `.toUpperCase()` (D-48). Call sites already pass `value` and are unaffected (V-6).
- **FE-21 `[ALTER]` — `PageScaffold` width variants.** `width?: 'default' | 'wide' | 'full'`; `'default'` keeps `max-w-4xl` (every current consumer unchanged). Wide/full unlock side-by-side groups and full-width tables.

---

## Resolved decisions (D-n)

| # | Decision | Rationale / rejected |
|---|---|---|
| D-58 `[NEW]` | **Depth-within-restraint.** Depth from neutral layering, subtle elevation, structure, disciplined accent — never decorative chroma. D-42 stands. | Founder-confirmed. **Rejected:** warmer palette (D-42 signal-preservation holds); flat status quo (the complaint). |
| D-57 `[ALTER of D-46]` | **Petrol deployment extended to section markers and group labels only.** Still one hue, no decorative chroma, contrast-gated. Input-selection affordance is **out of scope** — it is governed by the shipped INV-73 (B1). | The accent confined to four uses never reads as brand. **Rejected:** extending petrol to selected/active input states (collides with INV-73's shipped selection treatment). |
| D-60 `[NEW]` | **Status enums render authored humanized labels.** Each verdict-family member maps to a hand-authored label (Appendix D); the map lives with `VerdictChip` (`packages/ui/src/status/`), mirroring `toTierMember()`'s home. Flat `value`→label; shared values (`approved`, `needs_refresh`) resolve to one label across enums (no conflict). | Single home; British spelling, domain phrasing, acronyms correct. **Rejected:** client-side title-casing the key (mishandles acronyms/spelling/phrasing); backend-supplied label (display concern, no schema reason). |
| D-61 `[NEW, supersedes the UI-C1 zero-systems choice]` | **Dashboard zero-systems renders the scaffolded-empty** — header + zero-value stat cards + framed table with an in-region empty row — superseding UI-C1's shipped "FirstRunPanel for zero-systems." | Founder preference on first real use: empty register must not equal empty screen; the scaffold communicates workspace structure at zero data. **This is a deliberate supersession of a shipped, CLEARED choice, not remediation of a gap** (no canonical ever mandated scaffolded-empty). **Rejected:** the shipped `FirstRunPanel` takeover (defensible at UI-C1, but reads as a bare card hiding the workspace structure). |
| D-59 `[NEW, principle; build deferred]` | **Constrained-vocab-over-free-text; opinionated by default.** Absent values → extend the controlled vocabulary from taxonomies, not a free-text escape. **Single-home:** D-59 is the anchor for the deferred vocab-enrichment sprint; no build detail accretes in this doc (N5). | Founder stance. **Rejected:** free-text "Other" (less analyzable). |

---

## Invariants

- **INV-74 `[NEW]` · CONVENTION · forward-scoped.** A data surface's empty and first-run states retain the surface chrome (nav, header with primary action, stat row, table/section frames); the empty or get-started content renders **within** the retained data region, not as a full-surface replacement. Binds a surface only when that surface's composition pass adopts it (per-surface, like INV-69/INV-70); existing surfaces are not retroactively non-compliant. `FirstRunPanel` (FE-22) remains valid, rendered within retained chrome. ↳ refs INV-70, FE-22, FE-27, D-61.
- **INV-75 `[NEW]` · CONVENTION.** No raw enum member faces the user: the five verdict-family enums render via the `VerdictChip` `value`→label map, `eu_ai_act_tier` via `toTierMember()`, vocabulary fields via `VocabItemOut.label`. A bare snake_case member never reaches the DOM as user-facing text. Scope is these three families only; INV-75 makes **no** claim about the `provenance_confidence` enum (rendered via `ProvenanceBadge`, FE-15), whose ORM-vs-doc member count is an unreconciled HEAD question owned elsewhere (S3). ↳ refs FE-16, D-60, INV-68.

---

## Depth + layout (per the specimens)

Layering (page `--surface` / card `--paper` + elevation / sub-panel `--surface-sunken`), soft low-spread elevation, `SectionGroup` structure, wide/full scaffolds for side-by-side groups and full-width tables, petrol on primary action, section markers, and group labels. Neutral + one hue, D-42 intact.

## Semantic fidelity — VerdictChip labels

The chip keeps its tone map; it gains the flat `value`→label map (Appendix D) and renders the label. Done when no surface renders a raw verdict-family member and all 28 members carry a label.

## Dashboard (D-61 + INV-74)

Per V-2, zero-systems renders the full scaffold — `PageHeader` with the `system_owner`-gated register button, three `StatCard`s reading 0, and a framed `DataTable` whose body shows the in-region empty row. The status chip reads "Vendor check", not `vendor_check`. All UI-C1 F2 contracts preserved (`DF2-5`, `DF6-9`, `FE-11`, `INV-52`, face order). `FirstRunPanel` is not deprecated; the dashboard simply renders its get-started content within retained chrome (A3).

---

## Sprint-local decisions (DF-V2-n)

- **DF-V2-1** Elevation shadows are decorative-neutral and are **not** WCAG text/graphical pairings, so they are not added to `contrast.test.ts`. The real INV-62 exposure is surface-ramp widening (A2/V-1): if any `--paper`/`--surface`/`--surface-sunken` value changes, **all** affected existing pairings (30 at V1) are re-verified, not just new ones (N2).
- **DF-V2-2** `PageScaffold` `width` default is `'default'` (unchanged `max-w-4xl`).
- **DF-V2-3** Only the dashboard is re-composed this sprint; F2 detail and F3–F8 inherit the label map and adopt depth/layout in their own passes.
- **DF-V2-4** The `VerdictChip` label map keys on the wire `.value` exactly as the server emits it (lowercase snake_case); it never `.toUpperCase()`s the incoming value (the D-48 anti-pattern). `vendor_check` is the correct wire value, not a case skew (B2).

---

## Appendix A — Open decisions

- **A1** Elevation steps: two (raised, overlay) recommended.
- **A2** Surface ramp: deploy as-is vs widen (V-1 decides); any change triggers the DF-V2-1 full re-verify.
- **A3 — RESOLVED.** `FirstRunPanel` is retained, not retired; the dashboard renders its get-started content within retained chrome (INV-74). No global deprecation.
- **A4** D-57 accent ceiling = section markers + group labels (no creep to input states).
- **A5 — RESOLVED.** All 28 labels authored (Appendix D); V-7 is a HEAD-confirm read, not discovery.

## Appendix B — Source-verification register

V-0 canary, V-1 (tokens + no shadow), V-2 (dashboard branch), V-3 (PageScaffold consumers), V-4 (full 30-pairing gate), V-5 (FE-23 kit), V-6 (`VerdictChip` renders `value` — S1, strongly indicated by DF-V1-1), V-7 (enum HEAD-confirm). S2 (no second `FirstRunPanel` consumer) is de-risked: INV-74 is forward-scoped, so a second consumer is not retroactively constrained regardless.

## Appendix C — v2 review disposition

| Finding | Disposition |
|---|---|
| **B1** D-57 vs INV-73 | **Accepted.** D-57 scoped to section markers + group labels; input-selection stays on shipped INV-73; specimen note corrected. |
| **B2** wire-value casing | **Accepted.** Map keys on wire `.value` (lowercase); V-8 dropped; DF-V2-4 rewritten; Appendix D re-keyed to wire values. |
| **B3** INV-74 reversal + `FirstRunPanel` deprecation | **Accepted.** D-61 records the supersession (not remediation); INV-74 rewritten to "retain chrome, content within region" + forward-scoped; `FirstRunPanel` retained (A3). |
| **N1** author all 28 | **Folded.** Appendix D carries all 28, gated on V-7 HEAD-confirm. |
| **N2** contrast-gate scope | **Folded.** DF-V2-1 excludes shadows; ramp change re-runs all pairings. |
| **N3** FE-n vs D-n separation | **Folded.** FE conventions and decisions are separate sections. |
| **N4** sprint-label collision | **Folded.** Canon-update formally retires `UI-V2-OPERATOR-SKIN` (absorbed into C-track), reclaiming V2. |
| **N5** D-59 single-home | **Folded.** D-59 noted as the deferred vocab sprint's anchor; no build detail here. |
| **S1** VerdictChip render locus | **Returned.** Renders `value` (DF-V1-1); in-chip map correct; V-6 confirms. |
| **S2** second FirstRunPanel consumer | **De-risked** by INV-74 forward-scoping. |
| **S3** provenance 5th member | **Folded.** INV-75 explicitly excludes provenance; the base.py-vs-doc divergence is flagged as owned elsewhere. |

## Appendix D — Authored verdict label map (all 28; keyed on wire `.value`)

| Enum | Wire value | Label |
|---|---|---|
| approval_status | `not_started` | Not started |
| approval_status | `under_review` | Under review |
| approval_status | `approved` | Approved |
| approval_status | `rejected` | Rejected |
| approval_status | `expired` | Expired |
| assessment_status | `draft` | Draft |
| assessment_status | `in_review` | In review |
| assessment_status | `approved` | Approved |
| assessment_status | `needs_refresh` | Needs refresh |
| classification_status | `pending_review` | Pending review |
| classification_status | `approved` | Approved |
| classification_status | `changes_requested` | Changes requested |
| classification_status | `needs_refresh` | Needs refresh |
| coverage_status | `open` | Open |
| coverage_status | `partial` | Partial |
| coverage_status | `satisfied` | Satisfied |
| lifecycle_state | `requested` | Requested |
| lifecycle_state | `vendor_check` | Vendor check |
| lifecycle_state | `product_check` | Product check |
| lifecycle_state | `intake` | Intake |
| lifecycle_state | `halted_prohibited` | Halted (prohibited) |
| lifecycle_state | `under_assessment` | Under assessment |
| lifecycle_state | `treatment_pending` | Treatment pending |
| lifecycle_state | `pending_authorisation` | Pending authorisation |
| lifecycle_state | `authorised` | Authorised |
| lifecycle_state | `deployed` | Deployed |
| lifecycle_state | `held` | Held |
| lifecycle_state | `retired` | Retired |

Flat map = 25 unique keys (`approved` ×3, `needs_refresh` ×2 share one label each). British spelling, acronyms preserved, domain phrasing.

## Appendix E — Canon-update note (for the handoff)

STATE: record UI-V2-DEPTH-LAYOUT (depth/layout + the VerdictChip label map + the dashboard scaffolded-empty); **formally retire `UI-V2-OPERATOR-SKIN`** as absorbed into the C-track, reclaiming the V2 designation (N4); note F2 detail and F3–F8 inherit the label map and adopt depth/layout in their passes. DATA-MODEL: none (0 schema). Append FE-26, FE-27, FE-16 `[ALTER]`, FE-21 `[ALTER]`; D-57 (amends D-46), D-58, D-59, D-60, D-61 (supersedes the UI-C1 zero-systems choice); INV-74, INV-75; DF-V2-1..4. Extend/re-verify `contrast.test.ts` only if a ramp value changes. Never renumber a live id; stable tier untouched except the flagged D-46/FE-16/FE-21 amendments and the D-61 supersession.