# DM-S3b - Sprint handoff (EXECUTION ONLY)

**Plane:** tenant frontend. **Backend / schema / route delta:** 0 (tests only added). **Mints:** `FE-29`, `D-67`, `INV-80`, `DF-S3b-1..3`.
Rationale lives in `DM-S3b-DESIGN-FINAL.md`. This file is execution only. Work items are dependency-ordered; do them in order. Do not start WI-1+ until WI-0 passes.

---

## WI-0 - Pre-flight verify (gating; D-21)

0.1 Confirm STATE.md `Current through: DM-S3`; INDEX ceilings `INV-79` / `D-66` / `FE-28`. If any differ, **stop** and report (canon-lag).
0.2 **Cross-tenant bare-system count.** Run as a **`BYPASSRLS`/superuser** dev connection, **not** `irontrustai_app`:
```sql
SELECT s.tenant_id, count(*) AS bare
FROM system s
LEFT JOIN use_case uc ON uc.system_id = s.id
WHERE uc.id IS NULL
GROUP BY s.tenant_id;
```
Fallback (only `irontrustai_app` available): for each `id` in `SELECT id FROM tenant`, `SET LOCAL app.current_tenant = '<id>'` then run the same count; accumulate.
Record the result. **CLEAN = every tenant returns 0.**
0.3 `GET /v1/draft-registrations/active` returns 204 (no body) when no draft, 200 with the row otherwise.
0.4 `useActiveDraft()` exists in `apps/tenant/lib/intake/queries.ts` (`staleTime: 0`, null-on-204); `intakeKeys.activeDraft()` invalidated by `useRegister` and `useDiscardDraft`.
0.5 `ResumePrompt` (FE-28) holds the only resume/discard actions on `/systems/new`.
0.6 `portfolio_rollup` / `system_rollup` carry no lifecycle-state filter.
0.7 **Live route-topology.** From the running app's route table (FastAPI `app.routes` or generated OpenAPI), assert there is **no** `DELETE /v1/use-cases/{...}`, **no** `DELETE /v1/systems/{...}`, and no other route deleting a `use_case` or `system` row.

**Branch rules:**
- §0.2 non-zero -> WI-3 takes the **retain** branch (DF-S3b-3); do not delete `useSystems()`; do not mint D-67's retirement clause.
- §0.7 finds any use-case- or system-removing route -> **stop**: INV-80 is born-false. Do not mint INV-80, do not run WI-3 retirement, report.

**Done-check:** §0.2 result and §0.7 assertions recorded in the completion note; 0.1/0.3-0.6 confirmed.

---

## WI-1 - FE-29 `DraftResumeIndicator` component

Create `packages/ui/src/kit/draft-resume-indicator.tsx`. Export from `packages/ui/src/kit/index.ts` and `packages/ui/src/index.ts` (mirror FE-28's export path).

Spec:
- `section` with `aria-label="draft-resume"`, framed on the C0 surface ramp with `--elevation-raised` (FE-26). No new chroma; petrol within the D-57 ceiling only.
- Left: line "You have a registration in progress." + a muted descriptor.
- Right: a real `Link` (keyboard-reachable) to the `href` prop, labelled "Resume" with a trailing chevron, styled as the standard inline kit action (not primary/destructive).
- No discard control.
- Props: `{ productLabel: string | null; href: string }`. Render the literal "Untitled registration" when `productLabel` is null.

**Done-checks (component tests, `packages/ui`):**
- renders the resume link to the passed `href` with label "Resume";
- renders `productLabel` when provided; renders "Untitled registration" when `productLabel` is null;
- the resume affordance is an anchor/link element, not a div with onClick;
- axe: zero violations;
- exported from both `kit/index.ts` and `index.ts`.

---

## WI-2 - Dashboard wiring (`apps/tenant/app/dashboard/page.tsx`)

In `PortfolioHub`:
- add `const activeDraft = useActiveDraft({ enabled: roleKeys.has("system_owner") });` (gate via the query's `enabled`).
- build a single `draftBanner` fragment: when `activeDraft.data` is non-null, render `<DraftResumeIndicator productLabel={resolveLabel(activeDraft.data.draft_blob)} href="/systems/new" />`; otherwise `null`. On `activeDraft.isError`, `draftBanner` is `null`.
- `resolveLabel(blob)` returns `blob.catalogueProductName ?? blob.name ?? null` (DF-S3b-2).
- render `draftBanner` as the **first child of `PageScaffold`** in the scaffolded-empty return and in the populated return.
- **do not** render `draftBanner` in the loading or error returns (DF-S3b-1).
- **do not** add `activeDraft` to the hub loading/error gate (keep it `portfolio.isLoading || systems.isLoading`, subject to WI-3's `systems` removal).

Admin branch in `DashboardPage` (zero gov roles): unchanged; the draft query never mounts there.

**Done-checks (`apps/tenant/app/dashboard/__tests__`):**
- system_owner + active draft + zero systems (scaffolded-empty): banner present, links to `/systems/new`;
- system_owner + active draft + populated portfolio: banner present;
- system_owner + no draft (204): no banner;
- system_owner + draft query error: no banner;
- admin (zero gov roles): no banner and `GET /v1/draft-registrations/active` is **not** requested;
- loading state (portfolio pending): no banner rendered;
- error state (portfolio errored): no banner rendered;
- axe: zero violations on the scaffolded-empty + banner and populated + banner states.

---

## WI-3 - Nudge + `useSystems()` retirement (conditional on WI-0 §0.2)

**Branch A - §0.2 CLEAN (zero rows):**
- remove the `zeroUseCaseSystems` filter, the `"zero"`-kind entries in `systemRows`, and the A2 nudge rendering;
- remove the `useSystems` import and call; drop `systems` from the loading/error gate;
- set `const systemCount = portfolio.data.length;`;
- delete the now-dead A2 tests (`page.test.tsx` zero-use-case-system case) and the zero-use-case-system fixture in `a11y.test.tsx`.

**Done-checks (Branch A):**
- new test: the dashboard issues **no** `GET /v1/systems` request in any non-admin branch;
- existing F2 contracts stay green (DF2-5 admin branch, DF6-9 no coverage/export call, FE-11 court derivation, INV-52 no compliance-%);
- `Systems` stat card shows `portfolio.data.length`.

**Branch B - §0.2 NON-ZERO (DF-S3b-3):**
- make **no** change to `zeroUseCaseSystems`, `useSystems()`, or the A2 nudge;
- record the §0.2 count and tenant(s) in the completion note;
- do not author D-67's retirement clause (see WI-5).

---

## WI-4 - INV-80 enforcement test

Add a route-absence test mirroring INV-78's `TestPostSystemsAbsent` (same pattern/location):
- assert the app exposes no `DELETE` route matching `/v1/use-cases/{...}`;
- assert the app exposes no `DELETE` route matching `/v1/systems/{...}`.

**Done-check:** both assertions green against the live app route table.

---

## WI-5 - Canonical update (volatile tier only; never renumber a live INV-n; stable tier untouched)

Coding agent updates, in-repo:

1. **STATE.md** - set `Current through: DM-S3b`. Record: FE-29 dashboard draft-resume indicator; D-67 nudge/`useSystems()` retirement (note which branch executed, A or B, with the §0.2 count); INV-80; DF-S3b-1..3. Update the FE-29 line in the frontend section. Refresh the test counts (`packages/ui`, `apps/tenant`).
2. **FRONTEND.md** - author the `FE-29` entry: `DraftResumeIndicator`, kit component, navigation-only, props `{ productLabel, href }`, rendered in both non-admin dashboard branches, reuses `useActiveDraft()`, excluded from loading/error returns (DF-S3b-1). Cross-ref FE-28, D-66, D-67.
3. **DECISIONS.md** - append **D-67** (text per the final design doc), and **DF-S3b-1**, **DF-S3b-2**, **DF-S3b-3**. If WI-3 took Branch B, mark D-67's retirement clause as *not executed this sprint (legacy rows present)* and keep the decision recorded with the deferred legacy-data task noted.
4. **INVARIANTS.md** - append **INV-80** (CODE, text per the final design doc), enforced by WI-4's test. Do not renumber.
5. **OPEN-1 entry (DECISIONS.md)** - append a back-reference (NB-4): the void/withdraw path must re-evaluate INV-80 and the dashboard bare-system handling, which after D-67 (Branch A) retains no `GET /v1/systems` read to surface a bare system.
6. **INDEX.md** - bump the ceilings line to `INV-80`, `D-67`, `FE-29`; add the DM-S3b one-line summary alongside the DM-S3 entry.
7. **Composition-debt register (STATE.md)** - no new debt row (F2 was cleared at UI-C1); confirm no regression to the F2 row.

**Done-check:** all six canonical files reflect DM-S3b; ceilings consistent across STATE.md and INDEX.md; no live INV-n renumbered; INV-78 unedited.

---

## Full-suite gate

All of `packages/ui`, `packages/tokens`, and `apps/tenant` test suites green. Axe zero violations on the new and altered dashboard states. `eslint-plugin-irontrust/no-literal-token-value` passes (INV-63).