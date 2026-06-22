# UI-F2-PORTFOLIO — sprint handoff (execution-only, v0.2)

**For:** Claude Code, VS Code plan mode (propose edits before applying). Rationale lives in `UI-F2-PORTFOLIO-design.md`; this file is execution-only.
**Scope:** tenant app only · **read-only** (`re-evaluate` deferred, A1) · zero new routes · **schema delta conditional on §0 V-2 (B1)**. Wire-up over `API-ROUTES.md @ UI-F1-INTAKE` HEAD.
**Plane:** tenant (`apps/tenant`). Operator console untouched.

---

## §0 — Pre-flight verify (do first; registry can be stale, code wins — `D-21`)

Record `VERIFIED` / `DRIFT` per item before WI-1. Any drift → use the code, flag an `API-ROUTES.md` correction in WI-7. **V-2 is binding and decides whether the sprint stays zero-backend — resolve it before WI-3 scoping.**

1. **V-2 · BINDING (B1).** For a `REQUIRES_CONTEXT` use case, does live `blocking`/`GateResultRead` emit `system_owner` court, or inherit the `PENDING_REVIEW → reviewer` mislabel? Also: exact `responsible_party` field name + full value vocabulary, and whether `contributor` is ever emitted (NB4). Branch:
   - (a) emits owner → WI-3 needs **no** pre-branch; zero-backend holds.
   - (b) mislabels **and** `SystemRollupRead` carries `requires_context` → WI-3 pre-branches client-side; zero-backend holds.
   - (c) mislabels **and** rollup lacks `requires_context` → STOP, escalate: a thin additive rollup field is required (non-zero-backend); do not silently N+1-fetch per use case.
2. `SystemRollupRead` field shape: per-use-case `state`, highest tier, per-use-case `blocking`, **and presence of `requires_context`** (decides V-2 b/c). (V-1)
3. `MeRead`: governance roles as a list, from `governance_role_assignment`, not claims. (V-3)
4. Gates `gov:ALL` on `GET /v1/portfolio` and `GET /v1/systems/{id}/rollup` (admin pre-branch premise). (V-5)
5. `GET /v1/use-cases/{id}/lifecycle` existence + gate + `GateResultRead` fields. (V-6)
6. `SystemRead` shape for a zero-use-case card. (V-4)
7. Frontend seams: live `FE-n`/`D-n` ceilings (mirror is pre-F1 — **not** `FE-10`/`D-37`); `FE-3` palette/type-scale resolved by F1?; F0 authenticated-landing route name; `@irontrust/ui` whose-court indicator state. (V-7)
8. `GET /v1/portfolio` "≥1 use case" filter; resolve A2. (V-8)

Done-check: a `VERIFIED`/`DRIFT` line per item in the PR description; V-2 branch (a/b/c) stated explicitly before WI-3.

---

## Work items (dependency-ordered)

### WI-1 · Contract types
Mirror in `packages/api-client/src/contracts/`: `SystemRollupRead`, `SystemRead`, `UseCaseLifecycleRead`, `GateResultRead`, `MeRead` — matching §0 shapes. Include `requires_context` on the rollup row only if §0 confirms it (V-2b).
**Done-check:** `tsc --strict` passes; types equal live schemas; no field invented beyond §0.

### WI-2 · Data hooks
- `useLiveState` hooks for `GET /v1/portfolio`, `GET /v1/systems/{id}/rollup`, `GET /v1/use-cases/{id}/lifecycle` (`staleTime 0`).
- Cached query for `GET /v1/me`, fetched **first** to drive the admin pre-branch (no rich-feed call for a zero-gov-role caller — NB5).
- `GET /v1/systems` read for the A2 zero-use-case merge.
- **No mutation hook** (`re-evaluate` deferred, A1).
All via the BFF proxy; no direct browser→API; no client `tenant_id`; no `If-Match` header anywhere.
**Done-check:** `eslint-plugin-irontrust` no-raw-live-state-query + package-boundary pass; the three live reads use `useLiveState`; `/me` does not; admin-only path issues no `gov:ALL` read (assert via network spy in test).

### WI-3 · Whose-court derivation util
Pure function in `packages/ui` (or `apps/tenant/lib`): per use case, resolve court =
1. **if `requires_context` (V-2b) → `system_owner`** (the B1 pre-branch), **without** reading `blocking`; *(omit this step only if §0 V-2a proved the gate already emits owner court)*
2. else → `blocking.responsible_party` (or none).
Then match the resolved party against caller `/me` roles → `{ your_court, party_label }`. Party/role label only, no actor identity. Zero-use-case systems (A2) are **excluded from the input** (no `blocking`).
**Done-check:** unit tests over the role matrix — `REQUIRES_CONTEXT` use case resolves to `system_owner` not `reviewer` (the B1 regression test); `system_owner`/`reviewer`/`authoriser` each flag only their party; `contributor` row present iff §0 says it is emitted, else asserted absent (NB4); `auditor` → never your-court; admin-only → empty; `null` blocking → not your-court; a zero-use-case system never produces a court row.

### WI-4 · Portfolio landing surface
Realise the F0 authenticated-landing route (name per §0) as the portfolio home.
- Fetch `GET /me` first; **if zero governance roles → render admin/empty state and issue no portfolio read** (NB5/DF2-5).
- Else RSC server-fetch `GET /portfolio`, hydrate; role-conditioned render (`FE-10`/`FE-8`): adoption face leads with your-court, assurance face leads with posture.
- Promote the `@irontrust/ui` whose-court indicator scaffold to a wired component bound to the resolved court (WI-3).
- Merge A2 zero-use-case systems as distinct "register a use case" empty cards.
**Done-check:** e2e per role renders the correct your-court set; `REQUIRES_CONTEXT` use case shows owner court on the hub (B1); admin-only path shows the admin/empty state with **no** `gov:ALL` request on the wire; zero-use-case card renders and is non-interactive as a court row; `axe` clean; keyboard pass; live reads refetch (not cached).

### WI-5 · System drill-in
`/systems/{id}` rollup view: use cases + states + highest tier + per-use-case resolved court; forward links per state (`REQUIRES_CONTEXT` → F1 context gate, etc. — link to existing F1 surfaces, build none).
**Done-check:** e2e drill-in renders rollup; per-use-case court correct (incl. B1 case); forward links resolve to existing surfaces; live-state refetch on return.

### WI-6 · Tokens
Use only the F1-landed `FE-3` palette/type-scale; no literal colour/spacing values; add no token primitives.
**Done-check:** no-literal-token-value lint passes.

### WI-7 · Canonical update (last; verify ceilings live before appending — never renumber a live id)
1. **STATE.md** — append a `UI-F2-PORTFOLIO` capability entry (portfolio landing + system drill-in + whose-court with the `requires_context` pre-branch; routes consumed; read-only; A2 shown). Update "Current through" to `UI-F2-PORTFOLIO`. Deferred register: review-queue and `re-evaluate`-on-hub still deferred.
2. **DECISIONS.md** — append the durable F2 decisions (whose-court = server-computed + `requires_context` pre-branch + client-highlighted/presentational; proactive admin branch; F2 read-only) at the **next free `D-n`** (verify live ceiling; do not collide with F1's).
3. **FRONTEND.md** — append **one** `FE-n` at the next free id (verify live ceiling; no collision with F1's `FE-11`/`FE-12`): *whose-court derivation — pre-branch on `requires_context` to owner court (avoiding the `PENDING_REVIEW → reviewer` mislabel), else server `responsible_party`; client highlights against the caller's server-authoritative roles; presentational only, backend is the authz authority* (cites `D-9`, `FE-8`, `INV-28`, `D-4`, `D-24`). Add to the `FE-n` index.
4. **INDEX.md** — update Current-scope/ceilings for F2.
5. **DATA-MODEL.md / API-ROUTES.md** — change **only** if §0 V-2c forced a thin rollup field (then record the `[ALTER]` projection field + note) or §0 found route drift (then correct `API-ROUTES.md`). Otherwise untouched.
6. **No `INVARIANTS.md` append** (F2 adds no backend invariant; binding rules are existing `INV-n` + the new `FE-n`). Stable tier otherwise untouched; renumber no live id.
**Done-check:** live ceilings confirmed before each append; new `FE-n`/`D-n` next-free and non-colliding; STATE "Current through" = `UI-F2-PORTFOLIO`; INDEX ceilings updated; diff touches only STATE/DECISIONS/FRONTEND/INDEX (+ DATA-MODEL/API-ROUTES only under the §0-V-2c / drift exceptions).