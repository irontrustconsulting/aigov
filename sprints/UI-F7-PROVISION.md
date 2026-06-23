# SPRINT HANDOFF (execution-only) · `UI-F7-PROVISION` — Operator Provisioning Console

**Status:** ready to execute · plane PLATFORM (operator) · durable route delta +1 (`whoami` struck → `/platform/me` added) · schema/migration delta 0 · rationale lives in `UI-F7-PROVISION_design.md`, not here.

Execution-only. Work items are dependency-ordered. Done-checks are tied to concrete tests. Do not begin a code work item until §0 is cleared; V-A and V-B are blocking pre-flight.

---

## §0 — Pre-flight verify (clear before any code; `D-21`)

Verify live against repo HEAD / dev DB, not the canonicals. Record each outcome at the top of execution.

- [ ] **V-A (BLOCKING)** — `app/auth/operator_authz.py`: is there an authenticated-operator-only dependency (bare `CurrentOperator`, no `require_permission`)? If **absent**, WI-1 grows sub-item **WI-1a** (add that dependency). Do not drop the `/platform/me` gate without it.
- [ ] **V-B (BLOCKING)** — pin the byte-exact permission-key string in the returned `permissions` set (source: `require_permission("tenant:provision")`; `API-ROUTES` writes `operator:tenant:provision`). The literal used by WI-3/WI-5/WI-6 must equal this string exactly. Resolve the canonical disagreement; record the true literal.
- [ ] **V-1** — `ProvisionRequest` fields + validation, `app/schemas/platform.py`.
- [ ] **V-2** — `ProvisionResponse` + `TenantListItem` fields, `app/schemas/platform.py`.
- [ ] **V-3** — `409 AlreadyProvisioned` collision key, `app/services/provisioning.py`.
- [ ] **V-4** — `provision_tenant(source="http")` stages a `PlatformAuditEvent`, `app/services/provisioning.py`.
- [ ] **V-5 / V-C** — confirm only `/platform/whoami` exists (gated `tenant:provision`, `TODO: remove`); reconcile STATE "operator identity endpoint**s**" (plural) vs `API-ROUTES` (one route); confirm no second identity route to subsume.
- [ ] **V-6 / V-D** — operator fetch path: shared `@irontrust/api-client` vs operator-local; confirm `eslint-plugin-irontrust` `no-raw-live-state-query` / `no-client-tenant_id` are route/content-scoped, not blanket, for operator provisioning fetches.
- [ ] **V-7** — `apps/operator/app/` current shell: layout, nav, session-bootstrap, logged-in boundary beyond smoke `/dashboard`.
- [ ] **V-8** — operator-pool auth-code+PKCE web flow works end-to-end; a dev operator with `tenant:provision` exists or is seedable.

---

## WI-1 — Promote `whoami` → durable `GET /platform/me` (backend; N4 four-edit set)

Depends on V-A, V-B, V-5/V-C.

- Add `GET /platform/me`, gated **authenticated-operator-only** (bare `CurrentOperator`; use the V-A dependency, or WI-1a adds it), response `{id, email, display_name, permissions}` (drop `cognito_sub`).
- Remove `GET /platform/whoami` and `app/routers/platform/whoami.py`.
- Keep `require_permission("tenant:provision")` unchanged on `POST /platform/provision` and `GET /platform/tenants`.

**Done-check** (`tests/platform/test_platform_me.py`):
- valid operator **with** `tenant:provision` → 200, `permissions` includes the V-B literal.
- valid operator **without** `tenant:provision` → **200 (not 403)**, `permissions` excludes the V-B literal.
- disabled/unknown operator → 403; no token → 401.
- `GET /platform/whoami` → 404 (route gone).
- `permissions` set never sourced from token claims (resolved through the operator→role→permission chain).

### WI-1a (conditional, only if V-A finds no permission-less resolver)
Add an authenticated-operator-only dependency to `operator_authz` (resolve `CurrentOperator` without a permission assertion). **Done-check:** unit test resolves a permission-poor operator without raising 403.

## WI-2 — Operator nav/layout shell (frontend; A2(b), N2)

Depends on V-7.

- `apps/operator` layout + nav shell. Nav lists the operator surface map.
- Provisioning entry follows `FE-13`: present iff the V-B literal ∈ permissions (from WI-3's `/platform/me` read), absent otherwise.
- The three unbuilt surfaces (RBAC, curation, inbox) render visible-disabled "not yet available."

**Done-check** (`apps/operator` shell test):
- shell renders with operator skin (`[data-theme]` operator).
- operator **with** permission sees the provisioning entry; operator **without** does not (absent, not disabled).
- unbuilt entries render disabled for all operators.

## WI-3 — Identity bootstrap + root branch (frontend; B1)

Depends on WI-1, WI-2.

- Surface root reads `GET /platform/me` through the operator BFF proxy.
- Three-way branch:
  - V-B literal ∈ permissions → render list region (WI-4) + form region (WI-5).
  - V-B literal ∉ permissions → permission-appropriate empty state; **issue no `GET /platform/tenants`**; render no form.
  - unauthenticated → upstream BFF login redirect (F0; no new code).

**Done-check** (`apps/operator/.../provisioning.test.tsx`):
- permission-poor operator: assert **zero** network calls to `GET /platform/tenants` and no form in the DOM (the B1 regression guard).
- permitted operator: list + form both mount.

## WI-4 — Tenant list (frontend; A4)

Depends on WI-3.

- `GET /platform/tenants` via the operator BFF proxy; columns from `TenantListItem` (V-2); read-only.
- Wire query invalidation key for post-provision refetch (WI-5).

**Done-check:** list renders the V-2 columns; mutating provision (WI-5) invalidates and refetches; no per-tenant mutation control present.

## WI-5 — Provision form (frontend)

Depends on WI-3, WI-4, V-1, V-2, V-3.

- Capture `ProvisionRequest` (V-1); client validation mirrors server constraints; submit via the operator BFF proxy (`INV-50`).
- 201 → render `ProvisionResponse` (V-2), invalidate + refetch the list.
- 409 `AlreadyProvisioned` → distinct conflict state flagging the V-3 collision field.
- 403 → refetch `GET /platform/me`, re-branch (WI-3).

**Done-check** (`provisioning.test.tsx`):
- happy path: provision → 201 → list shows the new tenant.
- duplicate → 409 → conflict state on the V-3 field, no generic error.
- 403 → triggers `/platform/me` refetch.

## WI-6 — `FE-13` permission-gated render primitive (frontend)

Depends on WI-3.

- Factor the permission-gated-absent render into a reusable operator-plane control (the `FE-13` primitive), analogous to the tenant `SodAction` wrapper; gate on a permission literal present in the `/platform/me` set.

**Done-check:** control absent when the permission is absent, present when held; backend remains authority (manual: a forged direct call to `POST /platform/provision` without the permission still returns 403).

## WI-7 — Canonical update (volatile tier + sanctioned stable touches)

Append-only; never renumber a live `INV-n`/`D-n`/`FE-n`.

- **`API-ROUTES.md`**: strike the `GET /platform/whoami` row; add `GET /platform/me` (gate: authenticated-operator-only; response `{id, email, display_name, permissions}`).
- **`STATE.md`**: update the platform/operator-facing "operator identity endpoint(s)" line to `/platform/me` (durable) replacing `/platform/whoami`; add the `UI-F7-PROVISION` surface (`apps/operator/app/provisioning` + nav shell) under the UI build phase; record provisioning's `INV-49` gap as brought-into-compliance. **Do not** mark `INV-49`/`D-36` resolved or struck (N1).
- **`DECISIONS.md`**: append **`D-39`** (durable operator identity contract, A1) and the sprint-local `DF7-n` decisions (root-branch B1 fix; nav unbuilt-vs-absent axis N2; FE-13 placement N3). Do not strike `INV-49`/`D-36`.
- **`FRONTEND.md`**: append **`FE-13`** (operator-console permission-aware render) to §7 area and the `FE-n` index; add a one-line cross-ref from `FE-10` to `FE-13` (N3). No `FE-8` restatement.
- **`PLATFORM-UX.md` §3**: fill the provisioning-console intent into the `*[to design when built]*` placeholder (A3); the one sanctioned stable-tier touch.
- **`INVARIANTS.md`**: no change (no new `INV-n`; schema delta 0).
- **`DATA-MODEL.md`**: no change (schema delta 0).

**Done-check:** `INDEX` ceilings line and the `FE-n`/`D-n` indices reflect `FE-13`/`D-39`; no live id renumbered; stable tier otherwise untouched beyond the `FE-10` cross-ref and the `PLATFORM-UX` §3 fill.

---

## Appendix B — Source-verification register
Carried from `UI-F7-PROVISION_design.md` Appendix B (V-A, V-B binding pre-flight; V-1..V-8, V-C, V-D). Clear in §0 above.