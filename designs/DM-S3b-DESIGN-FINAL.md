# DM-S3b - Dashboard draft-resume indicator + zero-use-case nudge decision (FINAL DESIGN)

**Status:** FINAL - review folded (BL-1, BL-2, NB-1..5, SV-1). Handoff issues alongside.
**Track:** DM (domain-model) follow-on, peeled from DM-S3.
**Plane:** tenant frontend. **Backend / schema / route delta:** 0 (consumes DM-S3 and existing reads only). The conditional nudge retirement (D-67) is gated on §0.2; the route-absence assertions of §0.7 add **tests**, not routes.
**Ground state:** STATE.md `Current through: DM-S3`. Live ceilings (INDEX.md): `INV-79`, `D-66`, `FE-28`. Mints this sprint: `FE-29`, `D-67`, `INV-80`, `DF-S3b-1..3`.
**Canon-lag canary:** verify STATE.md `Current through` still reads `DM-S3` at §0.1; if a sprint landed since sync, stop and re-ground (D-21).
**Source-verified this pass:** `portfolio_rollup` / `system_rollup` carry no lifecycle-state filter; registration is atomic (INV-78); no `DELETE /v1/use-cases/{id}` and no `DELETE /v1/systems/{id}` in canon. Route absence re-confirmed live at §0.7 per D-21 (SV-1). See Appendix B.

---

## §0 Pre-flight verify checklist (coding agent runs before any edit; D-21)

| # | Check | Why | Source of truth |
|---|---|---|---|
| 0.1 | STATE.md `Current through` still `DM-S3`; `FE` ceiling 28, `INV` 79, `D` 66 | Detect canon-lag / a sprint landed since sync | `docs/STATE.md`, `docs/INDEX.md` |
| 0.2 | **Live DB, cross-tenant bare-system count (BL-1).** Run as a **`BYPASSRLS`/superuser** dev connection, **not** `irontrustai_app` (INV-4): `SELECT s.tenant_id, count(*) AS bare FROM system s LEFT JOIN use_case uc ON uc.system_id = s.id WHERE uc.id IS NULL GROUP BY s.tenant_id;`. **Fallback** if only `irontrustai_app` is available: iterate `SELECT id FROM tenant`, and per id `SET LOCAL app.current_tenant = '<id>'` then run the count; accumulate. **Clean iff every tenant returns 0.** | Gates D-67 retirement. Under `irontrustai_app` the unscoped form is RLS-bound to one tenant and returns a false-clean (INV-4) | live dev DB |
| 0.3 | `GET /v1/draft-registrations/active` returns **204 (no body)** when no draft, **200** with the row otherwise | `useActiveDraft()` null-on-204 contract must hold for FE-29 | `app/routers/v1/draft_registrations.py`, `docs/API-ROUTES.md` |
| 0.4 | `useActiveDraft()` present in `apps/tenant/lib/intake/queries.ts` (`staleTime: 0`, null-on-204); `intakeKeys.activeDraft()` invalidation wired by `useRegister` / `useDiscardDraft` | FE-29 reuses this query; no second draft query is minted | `docs/FRONTEND.md` (DM-S3 hook delta) |
| 0.5 | `ResumePrompt` (FE-28) is the sole home of resume/discard actions on `/systems/new` | FE-29 stays navigation-only; single-home for draft mutations | `docs/FRONTEND.md` FE-28 |
| 0.6 | `portfolio_rollup` / `system_rollup` still carry no state filter | Confirms the nudge cannot misfire on a halted-only or held-only system | `app/services/lifecycle_service.py` |
| 0.7 | **Live route-topology re-confirm (BL-2, SV-1).** Inspect the running app's route table (FastAPI `app.routes` or the generated OpenAPI): assert **no** `DELETE /v1/use-cases/{...}` and **no** `DELETE /v1/systems/{...}` and no other route that deletes a `use_case` or `system` row | INV-80 is minted on route absence; per D-21 route absence is reconfirmed live before the invariant ships, not taken from canon alone | running app, `app/routers/v1/use_cases.py`, `app/routers/v1/systems.py` |

**Branch rule:** if §0.2 returns **> 0 rows**, take the *retain* branch of D-67 and stop before deleting any `useSystems()` wiring. If §0.7 finds **any** use-case- or system-removing route, stop: INV-80 is born-false; do not mint it and do not retire (escalate, the canon-lag warning has fired).

---

## Problem

DM-S3 shipped server-side draft staging plus the front-door `ResumePrompt` (FE-28) on `/systems/new`. A user who abandons mid-wizard and later lands on the dashboard (F2, the authenticated home) has no signal a parked draft exists; the only discovery path is re-entering `/systems/new`. DM-S3 left DM-S3b owing the dashboard draft indicator (`FE-29`) and a decision on the legacy zero-use-case nudge (the A2 card).

The two are coupled by one fact established this pass: the dashboard's `zeroUseCaseSystems` set (systems in `GET /v1/systems` but absent from `GET /v1/portfolio`) is non-empty **only** for a system with zero use cases, which is unreachable through the API post-DM-S2. The nudge is therefore legacy-only UI, and the `GET /v1/systems` call feeding it is redundant for system counting unless legacy bare rows exist.

---

## Resolved decisions

| ID | Decision | Rationale | Rejected |
|---|---|---|---|
| RD-1 | `FE-29 DraftResumeIndicator` is **navigation-only**: a pointer to `/systems/new`, no resume/discard mutation | Single-home: resume/discard live in FE-28. Duplicating `useDiscardDraft` across two surfaces splits the draft-action home | Carry resume + start-over on the dashboard (duplicates FE-28; surfaces could disagree on draft state) |
| RD-2 | FE-29's query is `useActiveDraft()`, **gated** on `roleKeys.has("system_owner")`, **non-blocking** to portfolio render; on error the banner is silently omitted | Draft endpoints are `gov:system_owner` (DM-S3); a non-owner would 403. The banner is supplementary; FE-28 still catches the draft on `/systems/new` | Add `activeDraft` to the hub loading/error gate (blocks the portfolio on a supplementary read) |
| RD-3 | FE-29 renders in **both** non-admin branches (scaffolded-empty per D-61, and populated `PortfolioHub`); never the admin branch | A new owner with a started-but-unregistered draft sees an otherwise-empty dashboard; the banner is their bridge back. Admin (zero gov roles) cannot hold a draft, so the query never fires there (DF2-5) | Indicator only in the populated branch (misses the highest-value first-run case) |
| RD-4 | FE-29 shows whenever `useActiveDraft()` is non-null, mirroring FE-28's existence test; descriptor degrades to a generic label for an empty `draft_blob` | The two surfaces must never disagree on whether a draft exists. FE-28 resolves `draft_blob.step ?? "drill-down"`, so it already shows for an empty blob; the fallback keeps a null off the user's face (INV-75) | Suppress FE-29 for empty-blob drafts (diverges from FE-28; surface inconsistency) |
| RD-5 | **Retire** the A2 nudge and the dashboard `useSystems()` call; derive `systemCount` from `portfolio.data.length` - **contingent** on §0.2 clean. Authored as **D-67** | Post-DM-S2 every committed system has >=1 use case (INV-78); with no use-case-removal path (INV-80) no new bare system is reachable. If none are legacy-present, the nudge is dead UI and `useSystems()` a redundant request (DF6-9 spirit) | Unconditional retirement (masks a legacy bare system); keep both forever (dead UI + redundant call) |

---

## Design

### 1. `FE-29 DraftResumeIndicator` (NEW kit component)

Home: `packages/ui/src/kit/draft-resume-indicator.tsx`; exported from `packages/ui/src/kit/index.ts` and `packages/ui/src/index.ts`, mirroring FE-28.

Shape (presentational, navigation-only; agent implements to this spec under INV-68 / D-51):

- A single framed banner on the C0 surface ramp with `--elevation-raised` (FE-26), at the top of the page body, above `PageHeader`'s content region.
- Left: authored line "You have a registration in progress." Below it, a muted descriptor from `draft_blob` per the DF-S3b-2 order: `catalogueProductName` -> `name` -> "Untitled registration".
- Right: a single `Link` to `/systems/new` labelled "Resume" with a trailing chevron, styled as the kit's standard inline action (not a primary or destructive CTA).
- No discard control. Discard is reached by resuming, where FE-28 offers "Start over".
- Accent discipline: petrol confined to the D-57 ceiling; no new chroma (D-58).
- Props: `{ productLabel: string | null; href: string }`. The host resolves `productLabel` from the blob; the component renders the fallback when null. `href` is a prop to keep the component free of route knowledge.

States: **present** (non-null) -> banner; **absent / 204** -> render nothing, no reserved space; **query error** -> render nothing (RD-2).

a11y: a `section` with `aria-label="draft-resume"`; the resume affordance is a real link. Axe-clean is a done-check.

### 2. Dashboard wiring (`apps/tenant/app/dashboard/page.tsx` - ALTER)

| Locus | Present | ALTER |
|---|---|---|
| `PortfolioHub` | fetches `usePortfolio()` + `useSystems()`; computes `zeroUseCaseSystems`; renders A2 "zero" rows | hoist `useActiveDraft()` (gated `roleKeys.has("system_owner")` via `enabled`); build a `draftBanner` fragment once; render it as the first child of `PageScaffold` in the scaffolded-empty return **and** the populated return |
| loading / error returns | wrap `<PageScaffold>` with `Skeleton` / `ErrorState` | **no banner** here (DF-S3b-1, NB-5): `activeDraft` may still be loading and the banner is non-blocking (RD-2) |
| `systemCount` | `systems.data.length` | `portfolio.data.length` (D-67, if §0.2 clean) |
| `zeroUseCaseSystems` + `useSystems()` | present | **removed** (D-67, if §0.2 clean); else retained unchanged (DF-S3b-3) |
| hub loading/error gate | `portfolio.isLoading \|\| systems.isLoading` | drop `systems` from the gate iff `useSystems()` is removed; never add `activeDraft` to the gate (RD-2) |
| admin branch (`DashboardPage`, zero gov roles) | unchanged | unchanged - no draft query fires here (DF2-5) |

The `draftBanner` fragment has a single definition, rendered in the two `PortfolioHub` return paths only. It is the sole new element in the scaffolded-empty branch; D-61 / INV-74 chrome is otherwise untouched.

### 3. Nudge retirement (D-67, conditional on §0.2)

**If §0.2 clean (zero rows, all tenants):** delete the `zeroUseCaseSystems` filter, the `"zero"`-kind rows in `systemRows`, and the `useSystems()` import and call; re-point `systemCount` to `portfolio.data.length`. Remove the dead A2 tests and the zero-use-case a11y fixture; add a test asserting the dashboard requests **no** `GET /v1/systems`.

**If §0.2 returns rows (DF-S3b-3):** leave the nudge and `useSystems()` exactly as-is; record the count and tenant(s) in the handoff completion note; do **not** mint D-67's retirement clause; raise a separate legacy-data task (out of scope here).

---

## Decisions (authored; append-only)

**D-67** · Zero-use-case nudge and dashboard `useSystems()` retirement, gated on a verified-zero cross-tenant legacy bare-system count
Retire the A2 "register a use case" nudge and the dashboard's `useSystems()` call, deriving `systemCount` from `portfolio.data.length`, **when** the §0.2 cross-tenant count is zero. When non-zero, retain both unchanged and raise a separate legacy-data task (DF-S3b-3). Reachability basis: post-DM-S2 every committed system is constructed with its first use case atomically (INV-78), and no API path removes a use case (INV-80); a zero-use-case system is therefore legacy pre-DM-S2 data only, and the nudge plus the `GET /v1/systems` read that feeds it are otherwise dead.
Rejected: (a) unconditional retirement (silently masks a legacy bare system, since no `GET /v1/systems` read would remain to surface it); (b) keep both indefinitely (carries dead UI and a redundant dashboard request, against the DF6-9 no-extra-call discipline).
↳ origin: DM-S3b · refs: INV-78, INV-80, DF6-9, RD-5

---

## Invariants (authored; numbered, append-only)

**INV-80** · CODE · No use-case-removal path exists
No router exposes a route that deletes a `use_case` row (no `DELETE /v1/use-cases/{id}`, no system `DELETE` cascading into `use_case`). Enforced by a route-absence test mirroring INV-78's `TestPostSystemsAbsent` (NB-3, BL-2). This is the single novel guarantee; system-construction atomicity is INV-78's home and is cited, not re-asserted. Together with INV-78 they entail that any zero-use-case system is legacy pre-DM-S2 data.
**Seam:** a future void/withdraw path (OPEN-1) that removes a use case reopens bare-system reachability and must re-evaluate the dashboard's bare-system handling, which after D-67 has no `GET /v1/systems` read to surface it (NB-4). The OPEN-1 entry carries a back-reference to this invariant and to D-67.
↳ origin: DM-S3b · refs: INV-78, OPEN-1, D-67

No edit to any live INV-n. Stable tier untouched.

---

## Sprint-local decisions (DF; append-only)

**DF-S3b-1** · `draftBanner` excluded from the hub loading and error returns (NB-5)
The `draftBanner` renders only in the settled scaffolded-empty and populated returns, never in the `Skeleton` / `ErrorState` returns. `activeDraft` may still be loading there and the banner is non-blocking (RD-2). Done-checks assert no banner in the loading and error states.
↳ origin: DM-S3b · refs: RD-2

**DF-S3b-2** · Descriptor resolution order
FE-29's descriptor resolves `draft_blob.catalogueProductName` -> `draft_blob.name` -> "Untitled registration". The host computes `productLabel`; the component renders the literal fallback when null (INV-75 keeps a raw null off the face).
↳ origin: DM-S3b · refs: INV-75, DF-D3-1

**DF-S3b-3** · Retain branch when §0.2 is non-zero
If the §0.2 cross-tenant count is non-zero, the nudge and `useSystems()` are left unchanged, D-67's retirement clause is not minted, and the legacy count and tenant(s) are recorded in the handoff completion note for a separate legacy-data task.
↳ origin: DM-S3b · refs: D-67, BL-1

---

## Appendix A - Open decisions

**OPEN-DM-S3b-A (resolved by §0.2):** the legacy bare-system count is the sole gate on D-67; answered live, not from canon (D-21). Default recommendation: retire.
**OPEN-DM-S3b-B (resolved to prose spec):** the reviewer found FE-29 clean from the §1 prose spec; no rendered specimen is required. A specimen remains available on request before the agent builds.
**OPEN-DM-S3b-C (resolved to mirror):** RD-4 (show empty-blob, mirroring FE-28) is ratified; the reviewer confirmed FE-28 already shows for an empty blob, so the surfaces agree.

---

## Appendix B - Source-verification register

| Ref | Claim | Status | Source |
|---|---|---|---|
| SV-A | Portfolio projection has no lifecycle-state filter; halted/held use cases are included | **Verified** | `portfolio_rollup` / `system_rollup`, `app/services/lifecycle_service.py` |
| SV-B | A system absent from `/portfolio` but present in `GET /v1/systems` has exactly zero use cases | **Verified** (follows from SV-A + the JOIN) | `app/services/lifecycle_service.py` |
| SV-C | Registration is atomic; `POST /v1/systems` removed | **Verified** | INV-78; `app/routers/v1/registrations.py` |
| SV-D | No `DELETE /v1/use-cases/{id}` and no `DELETE /v1/systems/{id}` route in canon | **Verified in canon; re-confirmed live at §0.7** (D-21, SV-1) | `docs/API-ROUTES.md`, `use_cases.py`, `systems.py` |
| SV-E | `GET /draft-registrations/active` is 204-on-empty / 200-with-row | Verified in canon; re-confirm live at §0.3 | `app/routers/v1/draft_registrations.py`, `docs/API-ROUTES.md` |
| SV-F | `useActiveDraft()` exists, null-on-204, `staleTime: 0` | Verified in canon; re-confirm at §0.4 | `docs/FRONTEND.md` DM-S3 delta |
| SV-G | Cross-tenant count of legacy zero-use-case systems | **Needs verification (gating)** - §0.2, run BYPASSRLS (BL-1) | live DB (D-21) |

---

## Appendix C - Review disposition

| Finding | Disposition |
|---|---|
| **BL-1** §0.2 unsound under RLS | Fixed: §0.2 now mandates a `BYPASSRLS`/superuser connection (or per-tenant `SET LOCAL app.current_tenant` iteration); INV-4 caveat stated; branch rule explicit |
| **BL-2** INV-80 premise not re-verified; no enforcement | Fixed: §0.7 adds a live route-topology re-confirm; INV-80 re-tagged CODE and backed by a route-absence test mirroring `TestPostSystemsAbsent`; born-false stop rule added to the branch rule |
| **NB-1** D-67 unauthored | Fixed: D-67 authored above (folds RD-5) |
| **NB-2** DF-S3b-1/3 undefined | Fixed: DF-S3b-1 (loading/error exclusion), DF-S3b-2 (descriptor order), DF-S3b-3 (retain branch) all authored |
| **NB-3** INV-80 tag + single-home | Fixed: INV-80 is CODE with an enforcing test; wording tightened so the novel guarantee (no use-case-removal path) is the home, INV-78 cited for construction |
| **NB-4** OPEN-1 blind spot | Fixed: INV-80 seam note carries a back-reference; the canonical-update work item appends it to the OPEN-1 entry |
| **NB-5** banner in loading/error | Fixed: DF-S3b-1 + the §2 table row + explicit done-checks |
| **SV-1** route check live | Fixed: §0.7 |
| **SV-2 / Clean items** | No change; acknowledged |

---

## Scope boundaries

In scope: FE-29 component, dashboard wiring across both non-admin branches, conditional nudge + `useSystems()` retirement (D-67), INV-80 enforcement tests, canonical update.
Out of scope: legacy bare-system migration/void (raised only if §0.2 returns rows, DF-S3b-3); any draft mutation on the dashboard; any change to FE-28, the draft endpoints, the portfolio projection, or `GET /v1/systems`.