# C0-PREFLIGHT.md — UI-C0-PRODUCTION-FOUNDATION

Pre-flight register executed 2026-06-25 per `sprints/UI-C0-PRODUCTION-FOUNDATION.md §0`. All four rows green.

---

## C-1 · Reactive-item diff audit ✅

Ceilings confirmed by reading live files, not STATE's self-report.

### AppNav persistent header

**Commit:** `ec64c15` — "Add persistent nav header; fix DrillDownStep to traverse category hierarchy"

**Files touched:**
- `apps/tenant/app/_components/app-nav.tsx` — NEW (39 lines). Renders a `border-hairline border-b` top-bar with IronTrust logo → `/dashboard` and four nav links (Portfolio, Review queue, Evidence, Audit). Uses `usePathname()` for active-link highlighting.
- `apps/tenant/app/layout.tsx` — ALTER: imports and renders `<AppNav />` above `{children}` in the root `<body>`.
- Test updates bundled in same commit (DrillDownStep tests, see below).

**§2 reconcile:** STATE's account is confirmed. Disposition: provisional-pending-UI-C0 (code stays live). Superseded by FE-20 sidebar shell.

**Note:** The AppNav commit is bundled with the DrillDownStep two-level-hierarchy fix in the same commit.

---

### Layout and typography pass (26 pages + dashboard)

**Commits:**
- `fc4d021` — "Apply layout and typography to the dashboard page" (1 file: `apps/tenant/app/dashboard/page.tsx`)
- `0c6627f` — "Apply layout and typography to all remaining tenant pages (F1–F6)" (26 files)

**Files touched (27 total):**

`fc4d021`:
- `apps/tenant/app/dashboard/page.tsx`

`0c6627f`:
- `apps/tenant/app/audit/audit-home-client.tsx`
- `apps/tenant/app/evidence/evidence-home-client.tsx`
- `apps/tenant/app/review-queue/review-queue-client.tsx`
- `apps/tenant/app/systems/[id]/system-detail-client.tsx`
- `apps/tenant/app/systems/new/_steps/assurance-readonly.tsx`
- `apps/tenant/app/systems/new/_steps/context-gate-step.tsx`
- `apps/tenant/app/systems/new/_steps/drill-down-step.tsx`
- `apps/tenant/app/systems/new/_steps/intake-capture-step.tsx`
- `apps/tenant/app/systems/new/_steps/needs-system-owner.tsx`
- `apps/tenant/app/systems/new/_steps/prefill-step.tsx`
- `apps/tenant/app/systems/new/_steps/resolved-tier-step.tsx`
- `apps/tenant/app/systems/new/_steps/terminal-prohibited.tsx`
- `apps/tenant/app/systems/new/_steps/use-case-create-step.tsx`
- `apps/tenant/app/systems/new/_steps/whose-court-step.tsx`
- `apps/tenant/app/use-cases/[id]/_regions/aiia-body.tsx`
- `apps/tenant/app/use-cases/[id]/_regions/assessment-header.tsx`
- `apps/tenant/app/use-cases/[id]/_regions/ato-terminal.tsx`
- `apps/tenant/app/use-cases/[id]/_regions/audit-panels.tsx`
- `apps/tenant/app/use-cases/[id]/_regions/authorise-panel.tsx`
- `apps/tenant/app/use-cases/[id]/_regions/control-links.tsx`
- `apps/tenant/app/use-cases/[id]/_regions/feeder-recs.tsx`
- `apps/tenant/app/use-cases/[id]/_regions/item-card.tsx`
- `apps/tenant/app/use-cases/[id]/_regions/review-history.tsx`
- `apps/tenant/app/use-cases/[id]/_regions/review-panel.tsx`
- `apps/tenant/app/use-cases/[id]/_regions/sign-off-panel.tsx`
- `apps/tenant/app/use-cases/[id]/_regions/assessment-page-client.tsx`

**Pattern applied:** `mx-auto max-w-4xl px-6 py-8 space-y-8` containers; `text-2xl font-semibold` H1; `text-lg font-semibold` H2; `border-hairline rounded-lg border p-4` cards; `text-ink-muted text-sm` muted text.

**§2 reconcile:** STATE says "26 remaining tenant app pages" but the dashboard was a separate earlier commit. Touch-set is 27 files across 2 commits. STATE's description is accurate; the two-commit split is a correction. Disposition: provisional-pending-UI-C0 (code stays live). Superseded by FE-21 scaffold.

---

### DrillDownStep UX rewrite

**Commits:**
- `81d0cfe` — "Simplify DrillDownStep: flat category list → direct product browse" (3 files)
- `ec64c15` (same as AppNav commit) — "fix DrillDownStep to traverse category hierarchy" (restores two-level hierarchy: top-level → sub-category → products)

**Files touched:**
- `apps/tenant/app/systems/new/_steps/drill-down-step.tsx` — altered in both commits
- `apps/tenant/app/systems/new/__tests__/a11y.test.tsx`
- `apps/tenant/app/systems/new/_steps/__tests__/drill-down-step.test.tsx`

**§2 reconcile:** The rewrite is two commits, not one. Current state (post-ec64c15): two-level category → sub-category hierarchy. STATE's description of the two-level hierarchy is accurate. Disposition: provisional-pending-UI-C0 (`OPEN-C1`). Re-grounded at F1 per-surface pass.

---

## C-2 · @source directive in both globals.css ✅

```
apps/tenant/app/globals.css:13:@source "../../../packages/ui/src";
apps/operator/app/globals.css:13:@source "../../../packages/ui/src";
```

Both present. INV-67 satisfied.

---

## C-3 · packages/ui exports at HEAD + live ceilings ✅

**packages/ui/src/index.ts exports (at HEAD):**

Primitives: `Button`, `ButtonProps`, `ButtonVariant`, `Select`, `Dialog`, `Table`, `TableBody`, `TableHeaderRow`, `TableRow`, `TableCell`, `TableHeaderCell`, `TableDensity`, `QueueRow`, `QueueRowDensity`

Structured input: `PrefilledConfirm`, `SingleSelect`, `SelectOption`, `MultiSelectInput`, `ConstrainedNumberInput`, `ConstrainedDateInput`, `FreeText`

Prefill: `PrefillWithBasis`, `PrefillWithBasisProps`, `StructuredOption`, `ProvenanceBadge`, `Provenance`

SoD: `SodAction`, `SodActionProps`

Concurrency: `StaleLockBanner`, `BadFromStateBanner`

Status: `WhoseCourtIndicator`, `VerdictChip`, `VerdictTone`, `TierBadge`, `TierBadgeProps`, `TierMember`, `toTierMember`

Evidence: `EvidenceTable`, `EvidenceRow`, `EvidenceUploadControl`, `EvidenceLinkPicker`, `EvidencePickerRow`, `EvidenceManifestChip`, `ManifestLink`

Audit: `CoverageMatrix`, `NotAnObligationSetBanner`, `AuditGradeDivider`, `AuditPackView`, `EvidenceManifestTable`, `AtoDocumentView`

**Live ceilings confirmed:**
- `INV-67` — last invariant in `docs/INVARIANTS.md` (confirmed via grep). New ids assign at `INV-68` and above.
- `FE-19` — last FE convention in `docs/FRONTEND.md` (line 140, motion). New ids assign at `FE-20` and above.
- `D-50` — last decision in `docs/DECISIONS.md` (global 401 redirect). New ids assign at `D-51` and above.

---

## C-4 · provision_tenant — ADMIN grant, zero governance roles ✅

**Source:** `app/services/provisioning.py` line 108–110:

```python
session.add(
    Membership(user_id=user.id, tenant_id=tenant_id, role=UserRole.ADMIN)
)
```

`Membership` is created with `role=UserRole.ADMIN` only. No governance role rows are inserted. Zero governance roles confirmed.

**Implications:**
- Owner reaches member management (ADMIN-gated surface). ✅
- Self-assignment block (INV-7/D-5) means owner cannot self-assign a governance role. This is `OPEN-4` — not closed or altered by this sprint.
- Member sprint (next) is unblocked: owner invites others and assigns governance roles to those other memberships.

---

## Design doc §2 reconcile — final

| Change | §2 bucket | Confirmed | Correction |
|---|---|---|---|
| AppNav | reactive design | ✅ | Bundled with DrillDownStep ec64c15 commit (not separate commit) |
| Layout/typography pass | reactive design | ✅ | Two commits (fc4d021 + 0c6627f), 27 files total |
| DrillDownStep | reactive design | ✅ | Two commits (81d0cfe + ec64c15); current state is two-level hierarchy |
| Tailwind @source fix | bug fix | ✅ | — |
| TableBody hydration fix | bug fix | ✅ | — |
| Stale class replacement | bug fix | ✅ | — |
| Global 401 redirect | bug fix | ✅ | — |

All four preflight checks green. Proceed to WI-1.
