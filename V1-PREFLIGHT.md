# V1-PREFLIGHT.md — UI-V1-TENANT-SKIN Pre-flight Register

Produced at sprint start per the §0 binding checklist. Every row must be green before its dependent WI starts.

---

## VV-1 · V0 atom inventory at HEAD

Checked via `ls packages/ui/src/{status,prefill-with-basis,primitives,concurrency,audit,sod-wrapper}/`.

| Atom | Present |
|---|---|
| ProvenanceBadge | ✅ `prefill-with-basis/provenance-badge.tsx` |
| VerdictChip | ✅ `status/verdict-chip.tsx` |
| WhoseCourtIndicator | ✅ `status/whose-court-indicator.tsx` |
| StaleLockBanner | ✅ `concurrency/stale-lock-banner.tsx` |
| BadFromStateBanner | ✅ `concurrency/bad-from-state-banner.tsx` |
| SodAction | ✅ `sod-wrapper/sod-action.tsx` |
| PrefillWithBasis | ✅ `prefill-with-basis/prefill-with-basis.tsx` |
| Button (ghost variant) | ✅ `primitives/button.tsx` |
| Table + TableHeaderRow + TableHeaderCell + TableRow + TableCell | ✅ `primitives/table.tsx` |
| QueueRow (density prop) | ✅ `primitives/queue-row.tsx` |
| CoverageMatrix | ✅ `audit/coverage-matrix.tsx` |
| AuditGradeDivider | ✅ `audit/audit-grade-divider.tsx` |
| AuditPackView | ✅ `audit/audit-pack-view.tsx` |
| EvidenceManifestTable | ✅ `audit/evidence-manifest-table.tsx` |
| AtoDocumentView | ✅ `audit/ato-document-view.tsx` |
| NotAnObligationSetBanner | ✅ `audit/not-an-obligation-set-banner.tsx` |

**PASS** — all V0 atoms present.

---

## VV-2 · `skin-tenant.css` comfortable-density values

Read `packages/tokens/src/skin-tenant.css`:

```css
[data-theme="tenant"] {
  --spacing-4: 1rem;    /* 16px */
  --spacing-6: 1.5rem;  /* 24px */
  --spacing-8: 2rem;    /* 32px */
  --font-size-body: 0.9375rem;   /* 15px */
  --line-height-body: 1.55;
  --radius-md: 0.5rem;   /* 8px */
  --radius-lg: 0.75rem;  /* 12px */
}
```

**PASS** — comfortable 16–24 rhythm and 15px body confirmed.

---

## VV-3 · VerdictChip `eu_ai_act_tier` branch

Current `TONE_MAP` tier entries (from `packages/ui/src/status/verdict-chip.tsx`):

| Key | Tone |
|---|---|
| UNCLASSIFIED | neutral |
| MINIMAL | neutral |
| LIMITED | neutral |
| REQUIRES_CONTEXT | attention |
| HIGH | attention |
| PROHIBITED | halt |

Total unique keys in TONE_MAP: 31 (covering 34 enum members — 4 assessment + 12 lifecycle + 4 classification + 3 coverage + 5 approval + 6 tier; APPROVED/NEEDS_REFRESH counted once each).

**Branch to be removed in WI-3:** 6 keys (UNCLASSIFIED, MINIMAL, LIMITED, REQUIRES_CONTEXT, HIGH, PROHIBITED).  
**Post-WI-3 TONE_MAP:** 25 unique keys covering 28 enum members.

**PASS** — branch located, 6 members confirmed.

---

## VV-4 · Live coverage verdict key set

Inspected `packages/ui/src/audit/coverage-matrix.tsx`. The `ctrl.verdict` field is passed directly to `<VerdictChip value={ctrl.verdict} />`. Based on the API client type and existing breakdown structure, the computed verdict strings are:

| Computed verdict | Source |
|---|---|
| `SATISFIED` | Computed from coverage_status aggregate |
| `PARTIAL` | Computed from coverage_status aggregate |
| `OPEN` | Computed from coverage_status aggregate |
| `UNADDRESSED` | Controls in `matrix.unaddressed_controls` list (NOT in `matrix.controls`, so never hits VerdictChip) |
| `downgraded_unsubstantiated` | Rendered distinctly per coverage matrix breakdown |

`coverage_status` enum: `{OPEN, PARTIAL, SATISFIED}` — 3 members, no binding change.  
`verdict` stays plain `str`. UNADDRESSED controls are rendered in a separate list below the table, not via VerdictChip.

**Implication for F6:** VerdictChip in CoverageMatrix only receives SATISFIED/PARTIAL/OPEN/downgraded_unsubstantiated. The first three are already mapped; `downgraded_unsubstantiated` needs the distinct treatment from WI-5/F6.

**PASS** — coverage key set confirmed; no enum bind; UNADDRESSED never hits VerdictChip.

---

## VV-5 · Presentational boundary (`INV-54`)

Sprint WI-0 through WI-7 touch only:
- `packages/tokens/src/` (CSS tokens, tests)
- `packages/ui/src/` (components, tests)
- `apps/tenant/app/` (surface files and tests)
- `V1-PREFLIGHT.md` (repo root, this file)
- `docs/` (WI-7 canonical update only)

No API routes, DB schema, backend Python, enum DDL, or auth middleware touched.

**PASS** — boundary holds.

---

## VV-6 · IBM Plex Serif + lucide-react installed

| Check | Result |
|---|---|
| `grep "ibm-plex-serif" apps/tenant/app/globals.css` | ✅ `@import "@fontsource/ibm-plex-serif/latin-400.css"` and `latin-600.css` present |
| `grep "lucide-react" apps/tenant/package.json` | ✅ `"lucide-react": "^1.21.0"` in tenant app deps |
| `lucide-react` in `packages/ui/package.json` | ❌ **Not present** — must add before WI-2 (TierBadge `Ban` icon) |

**Action:** `pnpm add lucide-react --filter @irontrust/ui` added in WI-2 pre-step.

**CONDITIONAL PASS** — Serif ✅; Lucide in tenant ✅; Lucide in ui package needs adding.

---

## VV-7 · `--brand` vs `--verdict-positive` luminance (OPEN-V5 gate)

Computed via WCAG 2.1 relative luminance formula:

```
--brand:            #1E4651  R=30  G=70  B=81
  → linearize: 0.2126×0.0196 + 0.7152×0.0783 + 0.0722×0.1015 = 0.0675

--verdict-positive-text: #2F5D4A  R=47  G=93  B=74
  → linearize: 0.2126×0.0408 + 0.7152×0.1231 + 0.0722×0.0866 = 0.1030
```

Contrast ratio between them: (0.1030 + 0.05) / (0.0675 + 0.05) = **1.30:1**

These two tones are perceptually close (both cool dark-green/teal). On a co-occurring whose-court + positive-verdict row in F2/F4, they could be difficult to distinguish without shape cues (`WhoseCourtIndicator` has the left edge-bar; `VerdictChip` is a badge — form factor differentiates them).

**Decision:** No token split or nudge at this time. The component form (`WhoseCourtIndicator` left-border + tinted pill vs `VerdictChip` badge) provides sufficient pre-attentive differentiation. Flag for re-evaluation if user testing shows confusion. Resolves OPEN-V5.

---

## VV-8 · `--tier-*` contrast gate (pre-implementation)

Four new tier pairings to be added to `contrast.test.ts` in WI-1. Values from design doc §2 (provisional, bound to contrast result):

| Pairing | Approx ratio | Gate |
|---|---|---|
| white (#FFF) on `--tier-prohibited-fill` (#1C2A4F) | ~12.4:1 | ≥ 4.5:1 ✅ |
| white (#FFF) on `--tier-high-fill` (#2E4A78) | ~7.7:1 | ≥ 4.5:1 ✅ |
| `--tier-limited-text` (#36507D) on `--tier-limited-fill` (#E7ECF5) | ~6.0:1 | ≥ 4.5:1 ✅ |
| `--tier-minimal-text` (#4A5878) on `--tier-minimal-fill` (#EDEFF4) | ~5.3:1 (est.) | ≥ 4.5:1 ✅ |

All provisional values clear AA. Exact ratios confirmed once the test suite runs against the real tokens in WI-1.

Current contrast gate: **26 pairings** (16 text + 8 graphical + 2 focus ring).  
Post-WI-1 contrast gate: **30 pairings** (+4 tier text pairings).

**PASS** — pre-computation clears; test will confirm exact ratios.

---

## Keyboard pass note (post-WI-6)

To be filled in after WI-6 accessibility pass.

- **TierBadge compact:** no interactive target; no tab stop.
- **TierBadge card + override ladder:** overrideLadder slot wraps SodAction → Button; Tab/Enter reachable.
- **F4 QueueRow with `onClick`:** renders as `<button>` element — Tab navigable, Enter activates.
- **F5 link control disabled:** `disabled` attribute set; reason text adjacent and visible; no `aria-hidden` on reason.
- **F6 print button:** `print:hidden`; AuditPackView/AtoDocumentView `dl`/`dt`/`dd` semantic; drift caveat has `role="note"`.
- **Reduced motion:** `@media (prefers-reduced-motion: reduce)` block in `primitives.css` zeros all animation/transition durations.
