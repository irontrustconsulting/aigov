# UI-V2-DEPTH-LAYOUT — Sprint Handoff (execution-only)

Rationale lives in `UI-V2-DEPTH-LAYOUT-design.md`. Execution-only. Build to the two specimens in the design thread (register-form depth; zero-systems dashboard scaffolded-empty). Do not originate visual/layout/wording design (INV-68/D-51). **Two work streams, kept distinct:** depth+layout (visual) and the `VerdictChip` label map (semantic).

## Binding pre-flight (do first; record each; divergence → stop + escalate)

- **P-0 (canary)** HEAD is UI-C2 full delivery; ceilings INV-73 / D-56 / FE-25; nothing landed since.
- **P-1** `primitives.css`: values of `--paper`/`--surface`/`--surface-sunken`; confirm **no** `--shadow-*`/`--elevation-*` token. Sets WI-1 (new tokens vs deploy; ramp widen).
- **P-2** `dashboard/page.tsx` zero-systems branch — `FirstRunPanel` takeover vs scaffolded-empty. Sets WI-6.
- **P-3** `PageScaffold` consumers (for the additive `width` prop).
- **P-4** `contrast.test.ts` — the full 30-pairing set.
- **P-5** `verdict-chip.tsx` — confirm the chip renders its `value` prop as the visible label (not caller `children`). If it renders `children`, STOP and escalate (the label-map locus changes). Expected: renders `value`.
- **P-6** HEAD-confirm the five verdict-family enums in `pg_enum` match the design's Appendix D (currency check).

## Work items (dependency-ordered)

### WI-1 · FE-26 — elevation + surface-layering tokens
- Add `--elevation-raised` and `--elevation-overlay` shadow tokens (soft, low-spread) to `primitives.css`; reserve dark slots (VDD-4). Deploy the surface ramp: page `--surface`, cards `--paper` + `--elevation-raised`, sunken `--surface-sunken`. Widen ramp steps only if P-1 shows them indistinguishable.
- **Done-check:** tokens present + dark slots reserved; no literal hex/px (INV-63 lint); **if any ramp value changed**, re-run `contrast.test.ts` over all affected pairings and keep green (INV-62); shadows are not added as gate pairings (DF-V2-1).

### WI-2 · FE-27 + FE-21 `[ALTER]` — layout + sectioning
- `SectionGroup` (petrol marker + label + optional sunken sub-panel + divider) in the scaffold area; composes on FE-23 `StatCard`/`SectionHeader`/`DataTable`.
- `PageScaffold` gains `width?: 'default' | 'wide' | 'full'`; `'default'` unchanged `max-w-4xl`.
- D-57: petrol on section markers + group labels only (no input-selection — that stays INV-73).
- **Done-check:** `SectionGroup` renders; `width` additive (all P-3 consumers unchanged at default); axe/lint green.

### WI-3 · FE-16 `[ALTER]` — VerdictChip label map (semantic)
- Add a flat `value`→label map (Appendix D, all 28 members, 25 unique keys) in `packages/ui/src/status/`; `VerdictChip` renders the mapped label from `value`. Keys are the wire `.value` (lowercase) exactly as emitted; **no `.toUpperCase()`** (D-48, DF-V2-4). Tone map + `data-tone` unchanged.
- **Done-check:** every wire value in Appendix D renders its label; an unknown value falls back to the raw value (defensive) and logs; tone unchanged; `verdict-chip.test.tsx` extended; no surface renders a raw verdict-family member.

### WI-4 · INV-75 guard
- Add a lint/test guard that a bare verdict-family member string never reaches user-facing text (the wording analogue of INV-68).
- **Done-check:** guard present and green.

### WI-5 · D-57 petrol deployment
- Apply petrol to section markers and group labels per the specimens; nowhere else new.
- **Done-check:** petrol appears only on the D-46 four uses + section markers + group labels (A4 ceiling); contrast-gated.

### WI-6 · Dashboard re-composition (D-61 + INV-74; proving surface)
- Zero-systems renders the full scaffold: `PageHeader` with the `system_owner`-gated register button, three `StatCard`s reading 0, and a framed `DataTable` with the in-region empty row. Replace the `FirstRunPanel` takeover (if P-2 confirms it) with in-region content; `FirstRunPanel` is **not** deleted (A3).
- Apply depth + the wider/sectioned layout to the populated and empty states.
- **Done-check:** zero-systems shows header + stat cards + framed empty table (no full-surface takeover); populated state inherits depth/layout; status chip reads "Vendor check"; all UI-C1 F2 contracts (`DF2-5`, `DF6-9`, `FE-11`, `INV-52`, face order) preserved; `pnpm --filter tenant test` green.

### WI-7 · Cross-surface regression (label map + tokens are kit-level)
- Confirm F2 detail, F3 (`use-cases/[id]`), F4 (`review-queue`), F6 (`audit`) status chips now render labels (inherited) with no layout break; their full composition is **not** in scope.
- **Done-check:** those surfaces' status chips read humanized; no regressions; no other surface re-composed.

### WI-8 · Canonical update (last)
- **STATE:** record UI-V2-DEPTH-LAYOUT (depth/layout + VerdictChip label map + dashboard scaffolded-empty); **formally retire `UI-V2-OPERATOR-SKIN`** (absorbed into the C-track), reclaiming the V2 designation; note F2 detail and F3–F8 inherit the label map and adopt depth/layout in their passes.
- **DATA-MODEL:** none (0 schema).
- **Append:** FE-26, FE-27, FE-16 `[ALTER]`, FE-21 `[ALTER]`; D-57 (amends D-46), D-58, D-59, D-60, D-61 (supersedes UI-C1 zero-systems); INV-74, INV-75; DF-V2-1..4.
- Never renumber a live id; leave the stable tier untouched except the flagged D-46/FE-16/FE-21 amendments and the D-61 supersession.
- **Done-check:** ids appended above ceilings (INV-73/D-56/FE-25); `UI-V2-OPERATOR-SKIN` retired; D-61 records the supersession with rationale; no live id renumbered.