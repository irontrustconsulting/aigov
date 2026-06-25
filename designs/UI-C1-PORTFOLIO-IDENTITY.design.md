# UI-C1-PORTFOLIO-IDENTITY — Final Design Doc

**Status:** FINAL, review folded in, handoff-ready · **Track:** first per-surface composition pass under UI-C0, bundled with the identity fold; this sprint also **completes the UI-C0 `FE-22` set** (`Skeleton`, `ErrorState`) that was owed and blocked on rendered targets · **Plane:** tenant · **Delta:** Part A presentational; Part B one additive **response-schema** field on `MeRead` (not a DB/route/enum change, `DF3-7` precedent) plus a shell revision · **Builds on:** UI-C0 kit (`FE-20..23`, `INV-68..70`, `D-51`) · **Gated on:** F2-0 / V2 (kit and `Skeleton`/`ErrorState` existence at HEAD) · **Feeds:** member management (next); `systems/[id]` drill-in pass (deferred)

Supersedes the review-ready draft. Disposition at §6.

## §0 · Pre-flight verify checklist (binding)

| ID | Check | Why |
|---|---|---|
| F2-0 | Confirm UI-C0 delivered the kit and canon: `packages/ui` exports `PageHeader`, `StatCard`, `DataTable` scaffold, `EmptyState`, `FirstRunPanel`, `SectionHeader`, `ListSelectRow`; `FE-20..23`, `INV-68..70`, `D-51` landed | This sprint composes from the kit |
| V2 | **Live read `packages/ui/src/state` at HEAD: do `Skeleton` and `ErrorState` exist?** | The single fact that sets the sprint's shape (B1/B2). If absent, WI-1 builds them to the targets produced at review; if present, WI-1 conforms them to the targets. Either way the rendered targets are the spec |
| M-1 | Live `pg_policies`: the `tenant` SELECT policy permits `irontrustai_app` to read its own row under `app.current_tenant` (filter column `id` vs `tenant_id`) | Expected pass (`DATA-MODEL`). If it fails, Part B carries a small RLS addition or a resolver read |
| F2-1 | The earlier portfolio target's "Coverage" stat is dropped | `DF6-9` (dashboard issues no coverage/export call) and `INV-52` (no compliance-% headline) forbid it; binding stat row is §2 |
| F2-2 | Live F2 done-checks still pass post-composition: face-branch order (`your-court` vs `portfolio-posture`), no `\d+%` in the DOM (`INV-52`), compact `TierBadge` (`data-variant=compact`) in the use-case list | The composition must not regress the F2 semantic contract |

## §1 · Resolved decisions

| ID | Decision |
|---|---|
| FDD-1 | Part A scope is the landing (`apps/tenant/app/dashboard`) only; `systems/[id]` drill-in is a later pass |
| FDD-2 | Stat row is three lifecycle counts, no coverage, no percentage (§2) |
| FDD-3 | First-run `FirstRunPanel` leads for a governance caller with zero systems; admin-no-role and per-region empties are distinct `EmptyState`s |
| FDD-4 | Identity fold: `tenant_name` on `MeRead`; the logged-in user moves to a top utility bar, the tenant name to the sidebar block |
| C1-1 | This sprint completes the owed UI-C0 `FE-22` primitives `Skeleton` and `ErrorState`, built to the targets rendered at review, so F2 can clear `INV-70` fully (B1/B2) |

## §2 · Part A — F2 portfolio composition pass (present vs ALTER)

**A0 (prerequisite, B1/B2):** build `Skeleton` and `ErrorState` in `packages/ui` to the rendered targets (calm, retryable error with a `Try again` control and a muted danger icon; skeleton placeholders mirroring the composed layout). Without these, loading and error cannot be `FE-22`-composed and `INV-70` cannot clear.

Then compose the landing; preserve every semantic contract (`DF2-5`, `DF6-9`, `FE-11`, `INV-52`, and the F2 zero-use-case nudge documented in STATE for `UI-F2-PORTFOLIO`).

| Element | Now | Pass |
|---|---|---|
| Page title + register action | H1 plus a `system_owner`-gated underline link | **ALTER** to `PageHeader`: title, subtitle, `system_owner`-gated "Register a system" primary `Button` in the action slot (gate unchanged, absent for non-`system_owner`) |
| Stat row | none | **NEW**: three `StatCard`s, Systems (`GET /systems` count), Use cases under governance (sum `use_case_count`), Awaiting you (whose-court count). Client-derived from existing reads; no coverage, no `%` (`DF6-9`/`INV-52`) |
| Loading | "Loading…" text | **ALTER** to `Skeleton` (built in A0) |
| Error | "Could not load…" text | **ALTER** to `ErrorState` (built in A0) |
| Admin, zero governance roles | bare-sentence empty state, no portfolio call (`DF2-5`) | **ALTER** to `EmptyState`; the no-portfolio-call branch preserved exactly |
| Governance caller, zero systems | falls through to empty sections | **NEW**: `FirstRunPanel` get-started leads (the demo first-run) |
| Your-court section | inline, `WhoseCourtIndicator`, bare empty line | **ALTER** to `SectionHeader` + kit; empty → `EmptyState`. `FE-11` derivation, `your-court` aria-label, face-order unchanged |
| Portfolio posture | inline card, lifecycle rollup, link to `/audit` | **ALTER** to `SectionHeader` + kit; **issues no coverage call** (`DF6-9`); links to `/audit`, never restates coverage |
| Systems list | inline list, compact `TierBadge`, `VerdictChip` | **ALTER** to the `DataTable` scaffold (Name, Tier, lifecycle, whose court). Compact `TierBadge` preserved (`F2-2`) |
| Zero-use-case systems | "register a use case" nudge, excluded from court (F2 surface contract, STATE `UI-F2-PORTFOLIO`) | **ALTER** to the kit, behaviour preserved |

**Face branch preserved:** adoption roles lead with your-court, assurance roles lead with posture; both always render; `f2-portfolio.test` order assertions stay green (`F2-2`).

## §3 · Part B — identity fold

**Backend (one additive response-schema field, `DF3-7` precedent).** `MeRead` gains `tenant_name: str` (required, since a tenant is always named). The `GET /v1/me` handler adds one read on its existing RLS session, `db.get(Tenant, ctx.tenant_id).name`, requiring `from app.models.identity import Tenant` (V4). Read-only composition, no migration, no new table/route/enum.

**Frontend (`FE-20` ALTER).** Add a slim top utility bar carrying the logged-in user (name, email, account menu, sign out); move user identity out of the sidebar foot into it; wire `tenant_name` into the sidebar identity block. Operator shell unaffected (no tenant). This is a utility bar **above the sidebar nav, not a return to top-bar navigation**; the C0 sidebar topology (nav in the sidebar) is unchanged (N2).

**Proposed decision `D-52`:** identity is split, tenant in the sidebar, user in the top utility bar. The canonical home of the tenant name is the `tenant.name` column; `MeRead` (tenant plane) and `GET /platform/tenants` (operator plane) are two plane-scoped projections of it, so the tenant-plane field is single-homed on `MeRead` with no second tenant-plane route (N4). **Rejected:** a dedicated tenant-plane `GET /v1/tenant` (a second tenant-plane home for the same fact; moot since no such route exists, `D-22`); keeping user identity in the sidebar foot and adding tenant name beside it (two identities crowding one block, the founder's stated dislike). The reversal of FE-20's "no top-bar" stance is recorded here: FE-20 removed a top-bar *nav*; this adds a top *utility* bar for identity only, nav stays in the sidebar (N2).

## §4 · Canon impact

- `FE-20` **ALTER**: shell gains the top utility bar (§3), one sprint after FE-20 landed.
- `FE-22`: `Skeleton` and `ErrorState` move from owed to built (A0); update FE-22 and STATE accordingly.
- `MeRead` gains `tenant_name` (`DATA-MODEL` note: read-only response-schema composition, no migration, `DF3-7`).
- `D-52` minted, above the `D-51` ceiling.
- Composition-debt register **split** (N1): the live single row `F2 portfolio (dashboard, systems/[id])` becomes two, dashboard **cleared** (now bound by `INV-69`/`INV-70`), `systems/[id]` still owed.
- No new `INV`/`FE`.

## §5 · Deferred

`systems/[id]` drill-in composition pass (`FDD-1`). Member management is the sprint after this one. The operator sidebar rendered target (third owed C0 target) is unrelated to this tenant sprint and produced when the operator surfaces are composition-passed.

## §6 · Review disposition

| Finding | Fold |
|---|---|
| B1 (blocking) loading/error compose against unbuilt `Skeleton`/`ErrorState` | Targets rendered at review; A0 builds them this sprint; `V2` added to pre-flight as the gating existence check |
| B2 (blocking) `INV-70` clearance fails as a consequence | Resolved by scoping A0 in (not descoping); full `INV-70` clearance restored for the dashboard |
| N1 debt-register clearance inconsistent | §4 splits the row: dashboard cleared, `systems/[id]` owed; canonical-update encodes the split |
| N2 FE-20 "no top-bar" reversed | §3 clarifies it is a utility bar for identity only, nav stays in the sidebar; `D-52` records the rationale and the rejected sidebar-foot alternative verbatim |
| N3 sprint-local `A2`/`A6` cited as stable | Re-homed: the nudge cites the F2 surface contract (STATE `UI-F2-PORTFOLIO`); `DF6-9` cited directly |
| N4 `tenant_name` single-home wording | `D-52` states the `tenant.name` column is canonical; `MeRead` and `GET /platform/tenants` are plane projections; single-home claim scoped to the tenant plane |
| N5 status-line "schema field" reads as DB schema | Re-worded "response-schema field"; `DF3-7` precedent cited (additive response-schema field, non-breaking, distinct from route/table/enum delta) |
| V1 `tenant` RLS self-read | Endorsed; carried as M-1 with the contingency branch |
| V2 `Skeleton`/`ErrorState` existence | Now the gating pre-flight; sets WI-1 to build-or-conform |
| V3 `MeRead` fixture/type blast radius | Handoff done-checks enumerate the fixture sweep (the un-cast `evidence` test compile-breaks; the `as unknown as MeRead` dashboard mocks survive TS but must gain the field) and the `@irontrust/api-client` regen |
| V4 `me.py` import | Handoff names `from app.models.identity import Tenant` |
| Clean items | Carried: stat row compliance, `DF2-5` branch, face-order/`TierBadge`/no-`%`, `FirstRunPanel` first-run, `D-52` ceiling, `D-22` |

## Appendix A · Open decisions

| ID | Decision | Disposition |
|---|---|---|
| OPEN-C1 | `DrillDownStep` ratification | F1's pass, not this sprint |

## Appendix B · Source-verification register

| ID | Item | Action |
|---|---|---|
| F2-0 | UI-C0 kit + canon landed | Confirm before composing |
| V2 | `Skeleton`/`ErrorState` exist at HEAD | Live read `packages/ui/src/state`; sets WI-1 to build or conform |
| M-1 | `tenant` RLS self-read for `tenant_name` | Live `pg_policies`; expected pass, contingency carried |
| F2-1 | "Coverage" stat dropped | Binding stat row is §2 |
| F2-2 | F2 semantic contract intact | Existing F2 done-checks stay green |
| V3 | `MeRead` fixture/type sweep | Enumerate in the handoff done-checks |
| V4 | `Tenant` import in `me.py` | Named in the handoff |