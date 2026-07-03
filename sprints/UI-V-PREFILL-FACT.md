# Sprint handoff (execution-only): `UI-V-PREFILL-FACT`

**Rationale lives in `DESIGN-prefill-fact-card-FINAL.md`. This file is execution-only.**
**Adopts A1=a (curated dictionary + humanise), A2=b (typed value node). Gated on founder sign-off of both.**
**Delta:** presentational · 0 backend · 0 schema · 0 route · 0 enum · 0 contract · +2 optional `PrefillWithBasis` props.
**Stamps at close:** FE-33, INV-84 (ceilings FE-32 / INV-83 at HEAD; do not renumber live IDs).
**Binding visual spec:** the rendered specimen `review_catalogue_facts_redesign` (in chat). Build to it, via the §5 token mapping in the design doc.

---

## §0 Pre-flight (block build until all pass)

- [ ] **V-1** Read live `catalogue_fact` rows for the Adobe product: exact `key` set + `value` shapes. Populate `FACT_LABELS` (WI-2) from the live key set, not the seed.
- [ ] **V-2** `SELECT DISTINCT` roll-up of `value` shapes across all products. Confirm every shape routes to a §3 branch (design doc). **Resolve N7:** if any live `value` contains an internal `url` key (seed shows `dpa_available` does), keep the branch-1 `url` sub-branch; if HEAD has none, drop it. Record the finding in the completion note.
- [ ] **V-3** `grep -r "PrefillWithBasis" apps/ packages/` exhaustively. If any consumer other than `prefill-step.tsx` exists, the WI-4 ALTER must preserve its call (`valueLabel` path unchanged).
- [ ] **V-4** Confirm `catalogue_fact.last_checked_at` is tz-aware datetime.
- [ ] **V-5** `grep` `packages/ui` for an existing neutral pill/chip primitive. If found, WI-1 reuses it; if not (expected), build tenant-local per WI-1.

---

## Work items (dependency-ordered)

### WI-1 · Value projection (`FactValue` component + `renderFactValue`)
Locus: `apps/tenant/lib/intake/` (or `_steps/`, co-located).
- Implement the §3 branch order (design doc). Boolean -> neutral Yes/No chip; array -> pill cluster; scalar -> plain text; note-only -> note text; residual -> definition list. **Never `JSON.stringify`, never `String(array)`.**
- Yes/No chip + pill items: tenant-local neutral chrome. Tokens only (`bg-surface-sunken`, `border-hairline`, `text-ink`); `data-fact-value` / `data-bool` attributes for test isolation; **no `--verdict-*` / semantic channel** (INV-63, FE-14, FE-16, FE-24/FE-25 precedent). No literal hex/px.
- `note` renders as a supporting muted line (`text-ink-muted`). Branch-1 `url` sub-branch: include iff V-2 confirms an internal `url` key exists at HEAD.
- **Done-check:** `fact-value.test.tsx` asserts, per §3 branch: `{answer:true,note}` -> "Yes" chip + note line (no JSON); `{answer:false,note}` -> "No" chip + note; `{list:[a,b,c]}` -> N pills, no comma-join; `{regions:[…],note}` / `{models:[…]}` -> pills + note; `{standard}` / `{entity,note}` / `{framework,note}` -> plain value + note; `{note}` -> note as value; an unrecognised multi-key shape -> definition list, **no `JSON.stringify` substring in output**. Assert no element carries a `--verdict-*` / `data-tone` attribute.

### WI-2 · Label projection (`FACT_LABELS` + `labelForFactKey`)
Locus: `apps/tenant/lib/intake/`.
- `labelForFactKey(key) = FACT_LABELS[key] ?? humanise(key)`; `humanise` = `_`->space + capitalise first word; dictionary miss emits `console.warn` (mirrors `verdict-label-map.ts` / D-60).
- Populate `FACT_LABELS` from the V-1/V-2 live key set, acronym-correct (e.g. `sso_saml_available` -> "SSO / SAML available", `dpa_available` -> "DPA available", `eea_entity` -> "EEA contracting entity").
- **Done-check:** `fact-label.test.ts` asserts known keys -> dictionary label; an unknown key -> humanised label + a `console.warn` spy fires once; no underscore reaches output for any live key.

### WI-3 · Basis line (date format + source link)
Locus: `prefill-step.tsx` (or a small helper).
- Format `last_checked_at` as `D MMM YYYY` (British, `1 Apr 2025`). Compose basis as `source_label · checked <date>`; wrap `source_label` in a link to `source_url` when `source_url` is present.
- **Done-check:** test asserts an ISO input renders `1 Apr 2025` (no `T00:00:00Z`); `source_url` present -> anchor with that href; absent -> plain text.

### WI-4 · `PrefillWithBasis` ALTER (FE-5)
Locus: `packages/ui/.../prefill-with-basis.tsx`.
- Add optional `label?: string` (render in the header, left) and `valueContent?: ReactNode` (render as the value when provided, else fall back to `valueLabel`). **Retain `valueLabel: string`** for back-compat (V-3).
- Re-anchor `ProvenanceBadge` to the header row (top-right, aligned to `label`), off the value flex (R4). Badge styling unchanged (FE-15).
- **Done-check:** `prefill-with-basis.test.tsx` (extend): `label` renders in the header; badge is a sibling of `label` in the header row, not adjacent to the value; `valueContent` node renders when passed; omitting `valueContent` renders `valueLabel` unchanged (back-compat); `onOverride` signature still carries no provenance param (INV-55, existing assertion retained).

### WI-5 · `prefill-step.tsx` wiring
Locus: `apps/tenant/app/systems/new/_steps/prefill-step.tsx`.
- Remove `factValueLabel`. Per fact: `label={labelForFactKey(fact.key)}`; basis via WI-3.
- **Amended branch (R8):** when `amended[fact.key]` is set, pass the override label as plain value (`valueLabel={amended[fact.key]}`, no `valueContent`). **Unamended branch:** pass `valueContent={<FactValue value={fact.value} />}` (WI-1). Badge `provenance={fact.provenance}` in both states — no flip (R9).
- Confirm caption (R6): render "Facts you don't amend are recorded as confirmed when you continue." beside Continue **only** in the populated path (`facts.length > 0`). **Absent** from the `isError` minimal return and any empty-facts render. Subtitle text unchanged.
- No change to `onContinue` payload (`confirmedFactKeys` / `amendedFactKeys`, INV-83, FE-32).
- **Done-check:** `prefill-step.test.tsx`: a `{answer,note}` fact renders a Yes/No chip + note, **no raw JSON** in the DOM; a `{list:[…]}` fact renders pills, **no comma-join string**; each card shows its `labelForFactKey` label; overriding a fact swaps the value slot to the override label and the badge stays `catalogue_curated` (R9); Continue still emits the fact split unchanged; the caption is present with facts and absent in the error/empty returns.

### WI-6 · Canonical update (last)
- **STATE.md / DATA-MODEL.md:** no schema/route/enum change; add a STATE entry for `UI-V-PREFILL-FACT` (presentational; FE-33, INV-84; files touched).
- **Append** FE-33 (FRONTEND) and INV-84 (INVARIANTS) exactly as worded in the design doc. Do not renumber live IDs. Stable tier untouched.
- **Annotate** DF1-8 and UX §3 with `[Clarified by CAT-4: value not written back; disposition recorded per INV-83]` (N2 single-home accuracy; mirrors D-68's supersede note). Do not delete the original text.
- Record the V-2 / N7 `url`-sub-branch outcome and the V-1 live key set in the completion note.
- **Done-check:** `INV-84` and `FE-33` present with correct cross-refs; DF1-8 + UX §3 carry the CAT-4 clarification; no live INV-n renumbered; grep shows no orphaned `factValueLabel`.

---

## Guardrails
- No literal hex/px in any new chrome (INV-63, FE-14; lint-enforced V-4).
- No `--verdict-*` / semantic-channel token on fact values or the Yes/No chip (FE-16, INV-84).
- Client authors no provenance value; badge shows only server-provided `fact.provenance` (INV-55, R9).
- No new network call, no mutation, no write-back (DF1-8; INV-83 disposition path unchanged).
- If a visual decision beyond this handoff is needed, flag-and-stop; do not improvise canon (INV-68 / D-51).