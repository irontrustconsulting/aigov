# UI-V1-TENANT-SKIN — Sprint Handoff (execution-only)

**Status:** READY · **Delta:** presentational only, 0 backend / 0 schema / 0 route / 0 enum / 0 contract (carries `INV-54`) · **Scope:** `packages/tokens` (`--tier-*`), `packages/ui` (`TierBadge` new, `VerdictChip` ALTER), the tenant app view layers for `UI-F1..F6` · **Rationale:** see the design doc; this file is execution-only.

Work items are dependency-ordered. Each has a done-check tied to a concrete test. Do not start WI-1 before WI-0 passes.

---

## §0 · Pre-flight verification register (binding)

Run all and record in `V1-PREFLIGHT.md` before any code. A WI is blocked until its inputs here are confirmed.

| ID | Action | Pass condition |
|---|---|---|
| VV-1 | List the V0 atoms in `packages/ui` at HEAD | All named components in design doc §0 exist; V1 composes, never re-implements |
| VV-2 | Inspect `skin-tenant.css` | Comfortable density (16 to 24 rhythm, 15px body) present as the composition base |
| VV-3 | Read `packages/ui/.../verdict-chip.tsx` and dump its `eu_ai_act_tier` branch; count current mapped members | Branch located; member count is 34 (4+12+4+3+5+6). If not 34, STOP and reconcile before the ALTER |
| VV-4 | Read the live coverage response and record the exact `verdict` key set | `{SATISFIED, PARTIAL, OPEN, UNADDRESSED, downgraded_unsubstantiated}` as computed strings; `coverage_status` enum remains `{OPEN, PARTIAL, SATISFIED}`; `verdict` is plain `str` |
| VV-5 | Confirm the change set touches only `packages/{tokens,ui}` and `apps/tenant` view files | No file outside the presentational boundary is modified (`INV-54`) |
| VV-6 | Confirm IBM Plex Serif and `lucide-react` installed | Serif available for the document face; Lucide for icons |
| VV-7 | Compute `--brand` vs `--verdict-positive` luminance on a yours-and-approved row; eyeball `--brand` co-occurrence on F2/F4 | Result recorded; flagged for split/nudge only if confusing |
| VV-8 | Add the four `--tier-*` pairings to `contrast.test.ts` and run | All clear AA (text 4.5:1, large 3:1); gate count updated from 20 to 24 |

---

## WI-0 · Pre-flight (blocking)

Execute the §0 register. Produce `V1-PREFLIGHT.md` recording each pass condition with observed values, including the `verdict-chip.tsx` tier-branch dump, the live coverage key set, and the `--tier-*` contrast results.

**Done-check:** `V1-PREFLIGHT.md` exists; every §0 row green; the `VerdictChip` member count reads 34; the coverage key set matches; all `--tier-*` pairings pass.

## WI-1 · `--tier-*` channel tokens + contrast-gate extension

Add the `--tier-*` semantic channel to `packages/tokens` (primitive plus semantic layer): `--tier-minimal`, `--tier-limited`, `--tier-high`, `--tier-prohibited`, with the design-doc §2 provisional values, replaced by any contrast-cleared values from WI-0. Reserve empty dark slots (`D-44`). Extend `contrast.test.ts` to cover the new pairings and update the `INV-62`/`D-47` gate count.

**Done-check:** `tokens.test.ts` asserts the four `--tier-*` tokens and values; `contrast.test.ts` includes the four new pairings, all pass, count is 24; `eslint-plugin-irontrust` reports zero literal-value violations.

## WI-2 · `TierBadge` component (new)

`packages/ui/status/tier-badge.tsx`. Renders all six `eu_ai_act_tier` members: the four magnitudes on `--tier-*`, the two resolution states (`UNCLASSIFIED`, `REQUIRES_CONTEXT`) on `--verdict-*`. `PROHIBITED` carries the `ban` icon. Two variants: compact (label plus tone) and card (reasoning-first: tier hero, basis slot, override-ladder slot).

**Done-check:** `tier-badge.test.tsx` asserts a case per member, asserts magnitudes resolve to `--tier-*` and resolution states to `--verdict-*`, asserts the `ban` icon appears only on `PROHIBITED`, and asserts both variants render; `axe` zero violations.

## WI-3 · `VerdictChip` ALTER (drop tier)

Remove the `eu_ai_act_tier` branch from `VerdictChip`; it now maps `assessment_status`, `lifecycle_state`, `classification_status`, `coverage_status`, `approval_status` only. Leave no dead tier tone branch.

**Done-check:** `verdict-chip.test.tsx` member count updated 34→28; an assertion confirms no `eu_ai_act_tier` member resolves through `VerdictChip` (renders nothing or throws, per the component contract); grep confirms no orphaned tier-tone code path.

## WI-4 · Two density modes (composition)

Implement adoption-comfortable and assurance-dense as composition over `skin-tenant.css`: layout, spacing-step selection, and `density` props on `Table`/`QueueRow`. No new tokens, no second skin.

**Done-check:** `skins.test.ts` (or a density harness) asserts both modes resolve from the one tenant skin with no new token set; a visual snapshot per mode renders.

## WI-5 · Per-surface application F1 to F6 (dependency-ordered)

Apply the design-doc §4 treatments. Behaviour unchanged; presentation only. Per-surface done-checks:

- **F1 `systems/new`** — `TierBadge` card variant on the resolved-tier and context-outcome screens; `PrefillWithBasis` confirm panel; comfortable density. Done-check: `f1-intake.test.tsx` asserts the card variant renders at the resolved-tier step and the override ladder is `SodAction`-absent for non-`system_owner`.
- **F2 `dashboard` / `systems/[id]`** — role-led section order; `WhoseCourtIndicator` cards; `VerdictChip` posture; compact `TierBadge` in the use-case list; no compliance-% headline; posture links to `/audit`, no coverage restated. Done-check: `f2-portfolio.test.tsx` asserts 1st-line leads with whose-court and 2nd/3rd-line with posture, and asserts no coverage value is rendered on the hub.
- **F3 `use-cases/[id]`** — compact `TierBadge` header; `ProvenanceBadge` per item; `AI_SUGGESTED` dashed confirm-or-amend gate; four `assessment_status` states; SoD-visible author controls. Done-check: `f3-assess.test.tsx` asserts the header `TierBadge`, the dashed gate blocks authoring until confirm/amend, and barred acts are absent.
- **F4 `use-cases/[id]` ext / `review-queue`** — compact `QueueRow` with whose-court, attribution, `VerdictChip` state, compact `TierBadge`; assurance acts SoD-visible; sign-off transitions `TierBadge` from resolution state to authoritative tier while `VerdictChip` carries `classification_status`. Done-check: `f4-assure.test.tsx` asserts no `classification_status` member renders on `TierBadge` and no tier member on `VerdictChip`, and asserts the post-sign-off tier transition.
- **F5 `evidence` / `use-cases/[id]` ext** — repository-list shape vs per-item manifest shape kept distinct; download via callback, no URL in DOM; link control disabled-with-reason on an `AI_SUGGESTED` item. Done-check: `f5-evidence.test.tsx` asserts the per-item manifest renders no `link_count`/uploader, the repository row renders both, no evidence URL appears in the DOM, and the link control is disabled-with-reason (not absent) for an `AI_SUGGESTED` item.
- **F6 `audit` ext** — `CoverageMatrix` tones on the computed string set; `downgraded_unsubstantiated` distinct from `PARTIAL`; `NotAnObligationSetBanner` prominent, no compliance-%; `AuditGradeDivider` between interactive and audit-grade; `AuditPackView`/`AtoDocumentView` in serif; ATO drift caveat first; export hooks deliberate-only. Done-check: `f6-auditpack.test.tsx` asserts `downgraded_unsubstantiated` renders distinctly from `PARTIAL`, the document face uses the serif family, the drift caveat renders unconditionally first, and export hooks are not eager (`enabled:false`).

**Done-check (WI-5 overall):** every surface test passes; `axe` zero violations per surface story.

## WI-6 · Accessibility pass

Automated `axe` plus a manual keyboard pass per new/altered surface: visible focus ring, full keyboard operability, `prefers-reduced-motion` honoured.

**Done-check:** `axe` zero violations across the V1 surface suite; a recorded keyboard pass note covering `TierBadge` (both variants), the F4 queue, the F5 link control, and the F6 document face; reduced-motion verified.

## WI-7 · Canonical update (always last)

Append and amend per single-home; never renumber a live id.

- **`FRONTEND.md` (stable tier, flagged edit):** **amend `FE-16`** to (i) add `--tier-*` as a fifth semantic channel (`eu_ai_act_tier` magnitude), (ii) remove `eu_ai_act_tier` from the `VerdictChip` channel enumeration, (iii) state the orthogonality rule across five channels (provenance, verdict, court, severity, tier). This is a stable-tier edit; flag it explicitly in the sprint note.
- **`DECISIONS.md`:** append `D-48` recording the `FE-16` amendment and the tier-channel choice with rejected alternatives (verdict-only: cannot express a 4-step magnitude; `--sev-*` reuse: `FE-16` orthogonality violation and no severity referent per `SV-1`). Append sprint-local `DF-V1-*` for `OPEN-V6` and `OPEN-V7`.
- **`INVARIANTS.md`:** append `INV-64` (tier renders only via `TierBadge` on `--tier-*`; resolution states on `--verdict-*`) and `INV-65` (serif confined to the export face) above the live `INV-63` ceiling. Do not add the dropped composition invariant.
- **`STATE.md`:** mark `UI-V1-TENANT-SKIN` shipped (the `--tier-*` channel, `TierBadge`, `VerdictChip` 34→28, the two density modes, F1 to F6 visual application); update the "Current through" line; record `OPEN-V5` outcome from VV-7.
- **`DATA-MODEL.md`:** no change (no schema, no enum delta).

**Done-check:** the four volatile canonicals plus the flagged `FRONTEND.md` `FE-16` amendment are updated as above; a grep confirms no live `INV-n`/`FE-n`/`D-n` id was renumbered; `D-48` records the amendment and rejected alternatives; `INV-64`/`INV-65` appended; the sprint note flags the stable-tier `FE-16` edit.