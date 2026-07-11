# Design doc (FINAL): Review-catalogue-facts fact-card visual pass

**Proposed sprint id:** `UI-V-PREFILL-FACT` (visual track; final id at canon stamp)
**Status:** DESIGN v2 FINAL · review folded · B1/N1 resolved · A1=a, A2=b adopted (review-endorsed) · handoff gated on founder sign-off of A1/A2
**Surface:** `apps/tenant/app/systems/new/_steps/prefill-step.tsx` (DM-S2 catalogue-fact confirm step, F1 wizard, post-CAT-4, post-F1-composition)
**Delta class:** presentational · 0 backend · 0 schema · 0 route · 0 enum · 0 contract · **+2 optional `PrefillWithBasis` props** (`label`, `valueContent`; A2=b)
**Ceilings (live HEAD, per review):** FE-32, INV-83 -> stamps resolve to **FE-33 / INV-84**
**Canon touched:** FE-5 (ALTER); FE-33 + INV-84 (new); DF1-8 + UX §3 (canon-accuracy annotation)
**Binding spec:** the rendered specimen in chat (`review_catalogue_facts_redesign`). Token mapping in §5.

---

## §0 Pre-flight verify checklist (D-21)

Grounding was against the seed (`data/seed/catalogue.yaml`) and ORM/schema; the seed is not authoritative for live rows. Before build:

- [ ] **V-1** Read the live `catalogue_fact` rows for the Adobe product in the screenshot: exact `key` set and `value` shapes. Seed excerpts available were other vendors; the specimen labels (`Content provenance (C2PA)`, `Training data`, `Trains on customer content`) are illustrative reconstructions, not verified keys.
- [ ] **V-2** Enumerate the live distinct set of `value` JSON shapes across all seeded products. Confirm §3 branch table is exhaustive; any residual shape falls to branch 5 (definition list), never `JSON.stringify`. **Resolves the N7 conflict** (see Appendix B).
- [ ] **V-3** `grep -r "PrefillWithBasis" apps/ packages/` (exhaustive). Confirm `prefill-step.tsx` is the sole consumer; the FE-5 ALTER (A2=b) keeps `valueLabel` working regardless, but back-compat must be verified, not assumed.
- [ ] **V-4** Confirm `catalogue_fact.last_checked_at` is a tz-aware datetime (schema says yes) so R5's formatter input is stable.
- [ ] **V-5** Confirm no reusable neutral pill/chip primitive exists in `packages/ui` beyond status components (`VerdictChip`, `TierBadge`, `ProvenanceBadge`) and the interactive `MultiSelectInput` toggle-chip. Grounding found none; FE-24 accept-status chip and FE-25 `LogoTile` are inline neutral-chrome precedents, not importable pills. If one is found, reuse it and drop the tenant-local build (N3/SV3).

---

## Problem (unchanged from v1; all live at HEAD per review)

| # | Defect | Root cause | Locus |
|---|---|---|---|
| P1 | Raw JSON in value slot | `factValueLabel` -> `JSON.stringify(value)` for any dict with != 1 key; `{answer, note}` has 2 keys | `prefill-step.tsx` |
| P2 | Comma-jam (`ISO 27001,SOC 2,…`) | `{list:[…]}` is 1-key, so `factValueLabel` returns `String(value.list)`, bare-comma array coercion | same |
| P3 | Provenance badge drifts | FE-5 puts value + `ProvenanceBadge` on one `flex` row; badge anchors to the value, tracks its length | `PrefillWithBasis` (FE-5) |
| P4 | Cards anonymous (no label) | `CatalogueFactOut` carries only snake_case `key` + free-form `value`; step uses `fact.key` as React key only | `prefill-step.tsx` + label projection |
| P5 | Raw ISO timestamp | `basis` interpolates `last_checked_at` verbatim | `prefill-step.tsx` |

**Schema finding (confirmed by review):** `CatalogueFactOut` exposes `key`, `value`, `source_url`, `source_label`, `last_checked_at`, `provenance` only. No server display label. The label is a pure client display projection (D-21 latitude, same as the existing `factValueLabel`).

---

## Resolved decisions

| # | Decision | Basis |
|---|---|---|
| R1 | Value rendering is shape-typed, never `JSON.stringify`, never `String(array)`. Algorithm in §3. | P1, P2, D-21 |
| R2 | Field label from `fact.key` via a curated client dictionary + `humanise` fallback + `console.warn` on miss. Mirrors the D-60 / `verdict-label-map.ts` pattern and INV-75's defensive fallback. Home: `apps/tenant/lib/intake/` (tenant display concern; keeps `PrefillWithBasis` vocabulary-agnostic). | P4, D-60, INV-75 (pattern), D-21 |
| R3 | Boolean facts render a **judgement-neutral** Yes/No chip. No `--verdict-*` tone: a fact carries no verdict, and the verdict channel is orthogonal (FE-16). | P1, **FE-16** |
| R4 | `ProvenanceBadge` re-anchors to the card header (top-right, aligned to the label), not the value flex. Styling unchanged (FE-15); position only. | P3, FE-5, FE-15 |
| R5 | `last_checked_at` renders as a formatted date (`1 Apr 2025`); `source_label` links to `source_url` when present. | P5 |
| R6 | One confirm-model caption beside Continue: "Facts you don't amend are recorded as confirmed when you continue." Rendered **only** in the populated path (`facts.length > 0`); **absent** in the `isError` minimal return and the empty-facts path. The existing subtitle ("Amend any that don't apply to your system") is the amend instruction; the caption is the sole confirm-on-continue statement. Complementary, not duplicated. | INV-83, N5 |
| R7 | Fact provenance stays on `ProvenanceBadge`/FE-15. INV-75 does not bind (scope is the five verdict-family enums + tier + vocab; `provenance_confidence` excluded; fact `key`/`value` are JSONB, not enums). Closes a semantic-fidelity debt item, not an INV-75 breach. | INV-75, FE-15 |
| **R8** | **(resolves B1)** Overridden fact (`amended[fact.key]` set) renders the override label as plain value text, **not** the shape-typed node. §3 applies to the unamended branch only. The value-text change is the amendment feedback, keeping the visual and the `fact_amended:<key>` disposition in lockstep. Forward-compatible with OPEN-A3 (value slot shows whatever `amended[fact.key]` holds). | B1, INV-83, DF1-8, R1 |
| **R9** | **(resolves N1)** Badge stays `CATALOGUE_CURATED` in both pre-commit states. It represents the fact's **source**, unchanged by a local override. The override is a **pending disposition**, not a provenance value; per INV-55 no component displays an authored provenance tone. Committed `user-amended` renders post-commit on the system-detail surface (D-75 `field_provenance`). **Rejected:** flipping the badge to `user-amended` pre-commit — conflates source with pending disposition and borrows a committed-provenance tone for an uncommitted state (INV-55). | N1, **INV-55**, FE-15, PAT-8 |

---

## Adopted forks (review-endorsed; founder to confirm or flip in one line)

- **A1 = (a)** curated client dictionary + `humanise` fallback. Review endorsed R2 as single-home-correct. Acronym-faithful for known keys (`eea_entity` -> "EEA contracting entity", `dpa_available` -> "DPA available", `sso_saml_available` -> "SSO / SAML available"); humanise-only would mangle these. Deferred super-option (server `catalogue_fact.display_label` column) stays debt, not this pass.
- **A2 = (b)** typed value node. `PrefillWithBasis` gains `label?: string` + `valueContent?: ReactNode`; back-compatible (`valueLabel` retained). Matches the rendered specimen.

If either flips: A1=b removes the dictionary (humanise-only); A2=a drops `valueContent`, keeps `valueLabel: string`, and the value node degrades to a formatted string (no chips/pills). Each flip changes exactly one § (§4 for A1, §5 + FE-33 for A2).

---

## §3 Value projection algorithm (R1, R8)

Replaces `factValueLabel`. Applies to the **unamended** branch only (R8). Input `value: Record<string, unknown>` -> `ReactNode` (A2=b). Branch order:

1. `answer` present (`boolean`) -> **neutral Yes/No chip** (R3). `note` -> supporting muted line. `url` -> "Source" link **(gated on V-2, see N7 in Appendix B)**.
2. First array-valued key of `list | regions | models` (else any array-valued key) -> **pill cluster**. `note` -> supporting line.
3. First string-valued key of `standard | entity | framework` (else any string-valued non-`note`/`url` key) -> **plain value text**. `note` -> supporting line.
4. Only key is `note` -> the note text **is** the value.
5. Residual (unrecognised multi-key shape) -> **definition list** of `key: value` pairs (`note` excluded, appended as supporting line). Never `JSON.stringify`. This is the guaranteed no-JSON floor.

**SV1 assertion (Appendix B):** the four note-bearing two-key seed shapes — `{answer, note}`, `{regions, note}`, `{entity, note}`, `{framework, note}` — must each route to branch 1/2/3 with the note as a supporting line, and branch 5 must be reached only by genuinely unrecognised shapes. Unit test covers every branch plus the branch-5 floor.

Observed seed shapes (reconfirm by V-2): `{answer, note?, url?}`, `{standard}`, `{list:[…]}`, `{regions:[…], note?}`, `{models:[…]}`, `{entity, note?}`, `{framework, note}`, `{note}`.

---

## §4 Label projection (R2, A1=a)

`labelForFactKey(key) = FACT_LABELS[key] ?? humanise(key)`; `humanise` = `_`->space, capitalise first word.

- `FACT_LABELS`: curated client dictionary keyed on the live fact-key vocabulary (populated from V-1/V-2), acronym-correct.
- Keys are an **open** curated set (new products add keys), unlike the closed enum `VerdictChip` maps. Dictionary miss -> `humanise` + `console.warn` (INV-75 defensive-fallback shape, D-60). No throw.
- **Single home:** display projection of `key`, not a second source of the fact (which lives in `catalogue_fact`). Computed tenant-side, passed as the `label` prop, keeping `PrefillWithBasis` vocabulary-agnostic. Locus `apps/tenant/lib/intake/`. A server-side label would supersede this (OPEN-A1 deferred super-option), but only via a schema sprint.

---

## §5 Card layout (present vs ALTER) + token mapping

| Element | Present (FE-5) | ALTER |
|---|---|---|
| Card chrome | `rounded border border-hairline bg-surface p-4` | **Unchanged.** No FE-26 elevation this pass (scope discipline; deferred, Appendix A). |
| Header row | value + `ProvenanceBadge` on one `flex` row | **label (left, medium weight) + `ProvenanceBadge` (right, unchanged styling)** (R4) |
| Value (unamended) | single `valueLabel` string | shape-typed node (§3) via `valueContent` (A2=b) |
| Value (amended) | `amended[fact.key]` string in `valueLabel` | `amended[fact.key]` as plain text (R8); shape-typed node suppressed |
| Basis line | `source_label · checked <ISO>` | `source_label` (link if `source_url`) · `checked <formatted date>` (R5) |
| Override | ghost `Button` (FE-5) | Unchanged affordance; option semantics deferred (OPEN-A3) |
| Step footer | Continue only | Continue + confirm caption (R6), populated path only |

**Token mapping (specimen literal -> token; INV-63 / FE-14, no literal hex/px in build):**

| Specimen literal | Token / component | Note |
|---|---|---|
| card white bg | `bg-surface` | FE-5 chrome retained |
| card / pill / chip border | `border-hairline` | |
| brand petrol `#1E4651` (Continue) | existing primary `Button` | already carries `--color-brand` |
| brand petrol (Override text) | existing ghost `Button` | FE-5 |
| badge dot colour | `ProvenanceBadge` (FE-15) | dot/border in `--prov-catalogue-curated`; **not** brand. Specimen dot was an approximation. |
| pill / chip bg (`surface-0`) | `bg-surface-sunken` | FE-25 neutral-chrome precedent |
| pill / chip / Yes-No chip text | `text-ink` | definite value |
| label | `text-ink` + medium weight | |
| supporting note, source line, caption | `text-ink-muted` | |
| Yes/No chip | neutral chrome (`bg-surface-sunken border-hairline text-ink`), `data-*` tagged, **no `--verdict-*`** | R3, N3 |

**Behaviour unchanged:** `onOverride` updates local `amended` only (DF1-8); its signature carries no provenance (INV-55). `onContinue` emits `(confirmedFactKeys, amendedFactKeys)` (INV-83, FE-32). No mutation, no new network call.

---

## Neutral-chrome disposition (N3 / SV3 / V-5)

The Yes/No chip and pill-cluster items are **tenant-local neutral display chrome**, built inline in a co-located `FactValue` component (`apps/tenant/lib/intake/` or `_steps/`), passed to `PrefillWithBasis` via `valueContent`. Precedents: FE-24 accept-status chip (neutral non-semantic, `data-*` attribute, no `--verdict-*`) and FE-25 `LogoTile` monogram (neutral-ramp tokens, INV-63). Constraints: token-bound only (INV-63, FE-14, no literal hex/px), `data-*` for test isolation, no semantic channel. **Not** hoisted to a shared `packages/ui` primitive: there is a single consumer, and premature sharing is its own erosion (V-5 confirms none exists to reuse). Documented within FE-33, not a separate shared FE stamp — matching the FE-24 precedent of explicit, flagged neutral chrome (not silent absorption).

---

## Proposed canon (agent stamps at close; never renumber live IDs)

- **INV-84** · CONVENTION · Catalogue-fact values render shape-typed; `JSON.stringify` and array-to-string coercion never reach the DOM; boolean facts render judgement-neutral (no `--verdict-*`); an overridden fact renders its override label, keeping the visual and the `fact_amended:<key>` disposition in lockstep. Asserted by a projection unit test covering every §3 branch, the branch-5 floor, and the overridden branch. (refs: R1, R3, R8, FE-16, INV-83, D-21)
- **FE-33** · Catalogue-fact card — header-anchored `ProvenanceBadge` (source; unflipped pre-commit, R9), field label via `labelForFactKey` (tenant-local dictionary + `humanise` + `console.warn`), shape-typed value node (unamended) / override label (amended), formatted `last_checked_at` with `source_url` link, confirm caption (populated path only). `PrefillWithBasis` gains `label` + `valueContent` (back-compat `valueLabel`). Yes/No chip + pill cluster are tenant-local neutral chrome (neutral-ramp tokens, `data-*`, no `--verdict-*`), per FE-24/FE-25. (refs: FE-5, FE-15, FE-16, FE-24, FE-25, INV-55, INV-63, INV-83, D-60, R2, R4, R5, R6, R8, R9)

---

## Review disposition (every finding addressed)

| Finding | Disposition |
|---|---|
| B1 (blocking) | Resolved: R8 (overridden value state specified; §3 unamended-only; INV-83 lockstep). |
| N1 | Resolved: R9 (badge stays CATALOGUE_CURATED; flip rejected on INV-55). Reasoned disagreement with reviewer framing, grounded. |
| N2 | Appendix B canon-accuracy item; handoff canon-update WI annotates DF1-8 + UX §3 with CAT-4 clarification. |
| N3 | Neutral-chrome disposition §; specimen attached (rendered in chat); token-bound (INV-63/FE-14); FE-24/FE-25 precedent; documented in FE-33, not silent. |
| N4 | R3 re-cited to FE-16 only; INV-64 dropped. |
| N5 | R6 render condition specified; subtitle vs caption reconciled. |
| N6 | Status line corrected to "+2 optional props". |
| N7 | Surfaced as a seed-vs-HEAD conflict (Appendix B); `url` sub-branch retained, gated on V-2. |
| SV1 | §3 SV1 assertion + Appendix B. |
| SV2 | V-3 retained in §0. |
| SV3 | Resolved via V-5; no primitive to reuse; tenant-local chrome. |
| Clean (R1,R2,R5,R7, delta, IDs) | Carried unchanged. |

---

## Appendix A — open decisions

**OPEN-A3 · Override affordance semantics (product, not visual — deferred as debt).** The override offers only "Not applicable to my system": semantically weak for boolean/scalar facts and never lets a user assert a corrected value. Out of scope for a visual pass; not silently changed. Later options: keep; add free-text amend; add per-shape override inputs. R8 is forward-compatible with any of these (value slot shows whatever `amended[fact.key]` holds).

**OPEN-A4 · FE-26 card elevation (deferred).** FE-26 deploys cards on `bg-paper` + `--elevation-raised`. Not adopted this pass to keep the diff minimal; FE-5's flat `bg-surface` chrome retained. Adopt in a later depth pass if desired.

**Founder confirmation gate:** handoff adopts A1=a, A2=b. Flip either in one line and the noted § re-cuts.

---

## Appendix B — source-verification register

| ID | Claim | Method | Blocks |
|---|---|---|---|
| V-1 | Adobe product's live `catalogue_fact` keys + value shapes | live DB read (D-21) | §4 dictionary; specimen labels |
| V-2 | Full live distinct set of `value` shapes covered by §3; **resolves N7** | live DB roll-up | §3 exhaustiveness; branch-1 `url` sub-branch |
| V-3 | `prefill-step.tsx` is the sole `PrefillWithBasis` consumer | exhaustive grep | FE-5 ALTER back-compat |
| V-4 | `last_checked_at` is tz-aware datetime | schema (confirmed) | R5 formatter |
| V-5 | No reusable neutral pill/chip primitive | grep `packages/ui` | N3 tenant-local build |
| **N7 conflict** | Seed shows value-internal `url` on `dpa_available` (Copilot Studio: `{answer:true, url:…}`); review reports none at live HEAD. **D-21: DB decides.** Retain §3 branch-1 `url` sub-branch; drop only if V-2 confirms absence at HEAD. | V-2 | §3 branch 1 |
| **N2 canon-accuracy** | DF1-8 ("prefill display-only; no write-back") and UX §3 predate CAT-4. Value is still not written back (DF1-8 core holds), but a disposition **is** recorded (INV-83). Annotate both `[Clarified by CAT-4: value not written back; disposition recorded per INV-83]`, mirroring D-68's `[Partially superseded by CAT-4]` note. | handoff canon-update WI | single-home accuracy |

---

## Not in scope

AI-suggested / cross-tenant-baseline prefill sources (DF1-4). Fact value write-back (DF1-8; disposition via INV-83 is the only server effect). Server-side fact label column (OPEN-A1 super-option). Override affordance semantics (OPEN-A3). FE-26 card elevation (OPEN-A4). Other F-surface composition passes (C-track).