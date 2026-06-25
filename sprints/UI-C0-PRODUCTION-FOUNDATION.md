# UI-C0-PRODUCTION-FOUNDATION — Sprint Handoff (execution-only)

**Status:** READY · **Delta:** presentational, plus one standing-process guardrail in `CLAUDE.md` and canon · **Scope:** `packages/ui` (shell, scaffold, state patterns, kit), `packages/tokens` if any token gap surfaces, the tenant and operator app shells, `CLAUDE.md`, the volatile canon tier · **Rationale:** see the design doc; this file is execution-only.

Work items are dependency-ordered. Each has a done-check tied to a concrete test or to conformance with a named rendered target. Do not start WI-2 before WI-0 and WI-1 pass.

**Rendered targets (binding visual spec).** Build to these, do not improvise around them (`INV-68`). Provided this session: `shell_topology_sidebar_vs_topbar` (option A is the spec), `f2_portfolio_firstrun_professional_target` (scaffold, `PageHeader`, `StatCard`, `DataTable` empty body, `EmptyState`, `FirstRunPanel`), `f1_category_select_professional_target` (`ListSelectRow`, scaffold). The designer supplies three more before their WI starts: the operator sidebar variant (rail accent), the skeleton-loading state, and the standard error state. If a target is absent when its WI begins, flag and stop.

---

## §0 · Pre-flight verification register (binding)

Run all and record in `C0-PREFLIGHT.md` before any code beyond WI-1.

| ID | Action | Pass condition |
|---|---|---|
| C-1 | Read the actual diffs (not STATE) for `AppNav`, the 26-page layout pass, and the `DrillDownStep` rewrite | Each item's true touch-set recorded; reconcile in the design doc §2 confirmed or corrected |
| C-2 | Grep both `apps/*/app/globals.css` for `@source "../../../packages/ui/src"` | Present in both (`INV-67`); if absent, the kit will not render, fix first |
| C-3 | List `packages/ui` exports at HEAD; read the live `INV`/`FE`/`D` ceilings | Ceilings are `INV-67`, `FE-19`, `D-50`; new ids assign strictly above |
| C-4 | Read the live `provision_tenant`: confirm the owner is granted `ADMIN` with zero governance roles (`OPEN-4`) | Confirmed. Record that this gates the later member sprint and does not close `OPEN-4`. No code change in this sprint |

---

## WI-0 · Pre-flight (blocking)

Execute the §0 register; produce `C0-PREFLIGHT.md` with each observed value, including the three reactive-item diff summaries and the `provision_tenant` grant.

**Done-check:** `C0-PREFLIGHT.md` exists; every §0 row green; the reconcile in design doc §2 is confirmed against the diffs or its corrections are noted.

## WI-1 · Guardrail + STATE hygiene (do early, before any UI build)

Install the no-undesigned-UI rule so the rest of this sprint runs under it.

- Add the operative rule (design doc §3) to `CLAUDE.md` as a standing instruction.
- STATE hygiene: mark the three reactive 2026-06-25 items (`AppNav`, layout pass, `DrillDownStep`) provisional-pending-`UI-C0`, with the explicit note that the code stays live and rendering and provisional means pending re-grounding, not reverted or unbuilt. Leave the four bug fixes and their invariants (`INV-66`, `INV-67`/`D-49`, `D-50`) untouched.

**Done-check:** `CLAUDE.md` carries the operative rule; STATE marks exactly the three reactive items provisional with the live-not-reverted note; a grep confirms no bug-fix invariant was touched.

## WI-2 · App shell (`FE-20`)

Build a shared `AppShell`/`Sidebar` primitive in `packages/ui`. Tenant: replace `AppNav` with the sidebar (brand, vertical nav, account-and-tenant block pinned at the foot). Operator: rework `apps/operator/app/(console)/layout.tsx` to the conforming sidebar with the `--chrome-rail-bg` rail (`INV-60`), preserving the `RequirePermission`/`FE-13` gating logic unchanged.

**Done-check:** the tenant shell matches the `shell_topology_sidebar_vs_topbar` option-A target; the operator shell matches the operator-rail target and a test asserts the `RequirePermission` gating is unchanged (nav entries still absent without permission, `FE-13`); `axe` zero violations on both shells; the old `AppNav` import is gone.

## WI-3 · Page scaffold (`FE-21`)

Build `PageHeader` (title, subtitle, primary-action slot, breadcrumb/step slot) and the scaffold (content width, section rhythm, shell-to-content relationship). Supersede the 26-page `mx-auto max-w-4xl` pattern with the scaffold on the shell level so margins are intentional. Do not yet re-compose surface internals (that is the per-surface passes).

**Done-check:** `PageHeader` renders the four slots and matches the header in the `f2_portfolio_firstrun_professional_target`; a snapshot test fixes the scaffold; `axe` clean.

## WI-4 · UI state patterns (`FE-22`)

Build `EmptyState` (icon, line, optional action), `FirstRunPanel`, skeleton loaders, and the standard error state, all in `packages/ui`.

**Done-check:** `EmptyState` and `FirstRunPanel` match their appearance in the portfolio target; skeleton and error match their supplied targets; each has a snapshot test; `axe` clean on each.

## WI-5 · Shared primitive kit (`FE-23`)

Build the new composition primitives only; cite, do not duplicate, `FE-4`/`FE-5`/`FE-8`.

- `StatCard` — NEW; matches the portfolio target stat row.
- `DataTable` scaffold — extend existing `Table`/`TableBody`/`TableRow` (`INV-66`) with wrapper, header row, empty body; do not re-implement the primitive.
- `SectionHeader` — NEW.
- `ListSelectRow` — NEW; matches the `f1_category_select_professional_target` row (whole-row target, single trailing chevron, no per-row label).
- `Button` — ALTER, refine hierarchy (primary/secondary/ghost); `ghost` already exists.

**Done-check:** each primitive matches its named target; `DataTable` test asserts it composes the existing `TableBody` (no duplicate `<tbody>` primitive); `ListSelectRow` test asserts no per-row action label and a single chevron; `axe` clean across the kit; `eslint-plugin-irontrust/no-literal-token-value` passes (`INV-63`).

## WI-6 · Canonical update (always last)

Append and amend per single-home; never renumber a live id.

- **`FRONTEND.md`:** append `FE-20` (shell), `FE-21` (scaffold), `FE-22` (state patterns), `FE-23` (primitive kit, citing `FE-4`/`FE-5`/`FE-8`, not restating). Assign above the `FE-19` ceiling.
- **`INVARIANTS.md`:** append `INV-68` (no-undesigned-UI guardrail, `CONVENTION`, refs `D-51`); `INV-69` (compose-from-kit, no bespoke layout or one-off component) and `INV-70` (every data surface defines empty/first-run/loading/error), both carrying the **forward-scope clause**: binds a surface only once its UI-C0 composition pass has cleared it in the composition-debt register, plus all surfaces built after UI-C0. Assign above `INV-67`.
- **`DECISIONS.md`:** append `D-51` (guardrail rationale and rejected alternatives, design doc §3); `INV-68` refs it.
- **`STATE.md`:** mark `UI-C0-PRODUCTION-FOUNDATION` shipped (shell both planes, scaffold, state patterns, kit); record the composition-debt register (design doc Appendix C) as the remediation tracker; update the "Current through" line. The three reactive items, already marked provisional in WI-1, are noted superseded where the foundation replaced them.
- **`CLAUDE.md`:** the operative guardrail rule (already added in WI-1) stands; confirm it references `INV-68`.

**Done-check:** `FE-20..23`, `INV-68..70`, `D-51` appended above their ceilings; `INV-69`/`INV-70` carry the forward-scope clause; the composition-debt register is in STATE; a grep confirms no live `INV-n`/`FE-n`/`D-n` id was renumbered and no bug-fix invariant altered; `INV-68` and `D-51` cross-reference each other.