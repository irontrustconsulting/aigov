# C1-PREFLIGHT.md — UI-C1-PORTFOLIO-IDENTITY

Pre-flight register per §0 of the sprint handoff. All rows recorded before any WI work begins.

| ID | Check | Observed | Result |
|---|---|---|---|
| F2-0 | `packages/ui` exports kit + FE-20..23, INV-68..70, D-51 in canon | `packages/ui/src/index.ts` exports `PageHeader`, `StatCard`, `DataTable`/`DataTableHeader`/`DataTableBody`, `EmptyState`, `FirstRunPanel`, `SectionHeader`, `ListSelectRow`. `FE-20..23` present in `docs/FRONTEND.md` lines 141–144. `INV-68..70` at lines 289–299 in `docs/INVARIANTS.md`. `D-51` at line 483 in `docs/DECISIONS.md`. | GREEN |
| V2 | `packages/ui/src/state` at HEAD: `Skeleton`/`ErrorState` exist? | Directory contains `empty-state.tsx`, `first-run-panel.tsx`, `index.ts` only — `Skeleton` and `ErrorState` are **ABSENT**. → **WI-1 = BUILD** | ABSENT → BUILD |
| M-1 | `pg_policies` on `tenant` table: `irontrustai_app` can SELECT own row under `app.current_tenant` | Single policy `tenant_isolation`, cmd `ALL`, roles `{public}` (covers `irontrustai_app`), qual `id = (current_setting('app.current_tenant', true))::uuid`. `db.get(Tenant, ctx.tenant_id)` inside the RLS session sets `app.current_tenant = ctx.tenant_id`, so the filter is satisfied. Read permitted without BYPASS. | GREEN |
| F2-1 | Design target stat row = 3 lifecycle counts, no "Coverage" stat | Design doc §2 binding stat row: Systems, Use cases under governance, Awaiting you — all client-derived from existing reads. No coverage stat (`DF6-9`, `INV-52`). | GREEN (binding) |
| F2-2 | Existing `f2-portfolio.test.tsx` green on HEAD | All 41 tenant test suites, 200 tests pass. `f2-portfolio.test.tsx` PASS (face-order, no-%, compact TierBadge). | GREEN |

**Summary:** All §0 checks recorded. V2 ABSENT → WI-1 builds `Skeleton` and `ErrorState` from scratch to the rendered targets specified in the design doc. M-1 confirmed: `db.get(Tenant, ctx.tenant_id)` is permitted under the existing `tenant_isolation` RLS policy.
