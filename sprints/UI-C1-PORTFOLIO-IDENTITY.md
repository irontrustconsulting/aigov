# UI-C1-PORTFOLIO-IDENTITY — Sprint Handoff (execution-only)

**Status:** READY (gated on WI-0) · **Delta:** Part A presentational; Part B one additive `MeRead` response-schema field (`DF3-7`) + shell revision · **Scope:** `packages/ui` (`Skeleton`, `ErrorState`), `apps/tenant/app/dashboard`, the tenant shell (`FE-20` ALTER), `app/routers/v1/me.py`, `app/schemas/governance.py` (`MeRead`), `@irontrust/api-client`, the volatile canon tier · **Rationale:** see the design doc; this file is execution-only.

Dependency-ordered. **Rendered targets are the binding visual spec** (`INV-68`): `fe22_skeleton_and_error_targets` (skeleton + error), and the C0 `shell_topology_sidebar_vs_topbar` option A for the shell. Build to them.

---

## §0 · Pre-flight (binding) — produce `C1-PREFLIGHT.md`

| ID | Action | Pass condition |
|---|---|---|
| F2-0 | List `packages/ui` exports; confirm `FE-20..23`, `INV-68..70`, `D-51` in canon | Kit + canon present; else UI-C0 is incomplete, stop |
| V2 | Read `packages/ui/src/state` at HEAD | Record whether `Skeleton`/`ErrorState` exist. Sets WI-1 to build (absent) or conform (present) |
| M-1 | `pg_policies` on `tenant`: SELECT policy and its filter column for `irontrustai_app` under `app.current_tenant` | Self-read permitted → WI-3 reads the row directly. If not → escalate; WI-3 carries an RLS addition or resolver read |
| F2-2 | Run the existing `f2-portfolio.test.tsx` green on HEAD | Baseline before composing, to detect regressions |

## WI-0 · Pre-flight

Execute §0; produce `C1-PREFLIGHT.md` with each observed value.

**Done-check:** file exists; every §0 row recorded; `V2` outcome stated explicitly (build vs conform).

## WI-1 · Complete FE-22: `Skeleton` + `ErrorState`

Build (or conform, per `V2`) `Skeleton` and `ErrorState` in `packages/ui/src/state`, exported from the package index, matching `fe22_skeleton_and_error_targets`: `ErrorState` is calm and retryable (muted danger icon, short message, `Try again` control, optional support line); `Skeleton` is pulsing placeholder blocks parameterisable to mirror a surface's layout.

**Done-check:** both exported; match the target; snapshot tests; `axe` clean; `no-literal-token-value` passes (`INV-63`).

## WI-2 · Part A — F2 portfolio composition pass

Compose `apps/tenant/app/dashboard` into the kit per design §2. Preserve exactly: `DF2-5` (admin-zero-role issues no `GET /portfolio`), `DF6-9` (no coverage/export call from the dashboard), the F2 zero-use-case nudge, `FE-11` whose-court derivation, the face-branch order, `INV-52` (no `%`). Replace the bespoke layout with `PageHeader`, three `StatCard`s (§2), `SectionHeader`, the `DataTable` scaffold, and the four states (`EmptyState` admin-no-role and per-region; `FirstRunPanel` governance-zero-systems; `Skeleton` loading; `ErrorState` error).

**Done-check:** the existing `f2-portfolio.test` assertions stay green (face order, no `%`, compact `TierBadge`); a test asserts the dashboard issues no `/coverage` or `/export` request (`DF6-9`); new tests cover the three distinct zero-states and the loading/error states; `axe` clean; surface composes only from the kit (`INV-69`) and defines all four states (`INV-70`).

## WI-3 · Part B backend — `MeRead.tenant_name`

Add `tenant_name: str` to `MeRead` (`app/schemas/governance.py`). In `app/routers/v1/me.py`, add `from app.models.identity import Tenant` and populate from `db.get(Tenant, ctx.tenant_id).name` on the existing RLS session (per `M-1`; if `M-1` failed, apply the escalated read path). No migration.

**Done-check:** `GET /v1/me` returns `tenant_name`; a backend test asserts it equals the caller's tenant name; the RLS session reads it without BYPASS.

## WI-4 · Part B — api-client regen + `MeRead` fixture sweep

Regenerate `@irontrust/api-client` so `MeRead` carries required `tenant_name`. Sweep every `MeRead` fixture/mock across the tenant test suite to add `tenant_name`: the un-cast constructor in `apps/tenant/app/evidence/__tests__/page.test.tsx` (compile break) and the `as unknown as MeRead` mocks in the `dashboard` tests (TS-surviving but body-asserting), plus any others surfaced by typecheck.

**Done-check:** `tsc` passes across the monorepo; the full tenant test suite green; no `MeRead` literal omits `tenant_name`.

## WI-5 · Part B — shell `FE-20` ALTER

Add the slim top utility bar to the tenant shell (logged-in user: name, email, account menu, sign out); move user identity out of the sidebar foot; wire `tenant_name` from `MeRead` into the sidebar identity block. Nav stays in the sidebar (not a top-nav). Operator shell untouched.

**Done-check:** the tenant shell shows the tenant name in the sidebar and the user in the top bar; the C0 sidebar nav is unchanged; the operator shell is unchanged; `axe` clean.

## WI-6 · Canonical update (last)

Append and amend per single-home; never renumber a live id.

- **`FRONTEND.md`:** `FE-20` ALTER note (top utility bar for identity; nav stays in the sidebar). `FE-22` updated: `Skeleton`/`ErrorState` now built, owed-target note removed.
- **`DECISIONS.md`:** append `D-52` (identity split; `tenant.name` column canonical with `MeRead` and `GET /platform/tenants` as plane projections; tenant-plane field single-homed on `MeRead`; rejected alternatives verbatim, per N2/N4). Above the `D-51` ceiling.
- **`DATA-MODEL.md`:** note `MeRead` gains `tenant_name` (read-only composition, `DF3-7`, no migration).
- **`STATE.md`:** mark `UI-C1-PORTFOLIO-IDENTITY` shipped; **split the composition-debt register row** so `F2 dashboard` is cleared (now bound by `INV-69`/`INV-70`) and `F2 systems/[id]` remains owed (N1); record `Skeleton`/`ErrorState` as built; update "Current through".

**Done-check:** `D-52` appended above ceiling with rejected alternatives; debt register split with dashboard cleared and `systems/[id]` owed; `FE-22` and `FE-20` notes updated; a grep confirms no live id renumbered and no stable-tier invariant altered.