# sprints/ui-f0-foundation.md — UI Foundation (BFF auth plane + shared contract)

**Status:** UI build phase, first sprint · backend complete through S7b · **zero-schema** (no DB/migration change) · carries **at most one thin backend read endpoint** (caller-roles `/me`, conditional on §0-1b) · resolves `FRONTEND.md` §1/§6/§7 into running scaffold · **not a feature surface** — proves the spine end-to-end, then the intake wizard follows.
**For:** Claude Code, VS Code plan mode — propose edits before applying.
**Apply-source for canon:** the filled `FRONTEND.md` (FE-1..10) is the companion design artifact; W8 applies it verbatim. This handoff is execution-only and references FE-n by id (N1).
**Reads:** `FRONTEND.md` (FE-1..10), `UX.md` §2/§3/§5, `PLATFORM-UX.md` §1-3, `ARCHITECTURE.md` §2/§5, `INVARIANTS.md` (INV-1, 3, 13, 14, 25, 28, 32, 34, 49, 50-proposed).

---

## §0 Pre-flight verify (D-21 — do not assume; confirm against live source, not INDEX)

1a. `app/auth/cognito.py` — `verify_cognito_token` reads the bearer from the `Authorization` header only. The bearer-forward BFF depends on this being unchanged. If it reads anything else (cookie, custom header), stop and flag.
1b. **Caller's-own-governance-roles read (B1).** Confirm whether a self-scoped read returning the *authenticated caller's* membership + governance role set exists. STATE lists only assign/revoke/list-by-tenant/list-by-member; `TenantContext` carries `role` (admin/member), not the governance set (ARCH §5). If `list-by-member` is admin-gated or takes a foreign `membership_id`, the caller can't self-serve → **W-BE** is in scope. If a self-read already exists, skip W-BE and record the route W7b consumes.
2. Cognito app clients, **both pools** (Terraform `infra/`): authorization-code + PKCE enabled; callback + logout URLs registered for the two Next origins; refresh-token rotation on; access/refresh/id TTLs recorded. If a Terraform change is needed, stage it as a separate reviewed edit — do not hand-mutate the pool.
3. API CORS posture — with a same-origin BFF the browser never cross-origins to the API. Confirm the API does **not** need browser-facing CORS; if any browser-origin CORS exists, flag it as redundant/contradictory to `INV-50`.
4. `verify_operator_token` plane separation under a shared API origin — confirm that when both BFFs forward to one API origin, operator routes sit under `verify_operator_token` and tenant routes under `verify_cognito_token`, so a tenant bearer cannot satisfy an operator route or vice versa (INV-1 backstop is `iss`/`aud`, but confirm the router-prefix gating).
5. `NFR-1` SSO/SAML — confirm MVP-deferred (STATE does not list it built) so F0 login targets Cognito-native only.
6. Live INV/D ceiling — confirm the highest live ids against **live `INVARIANTS.md` / `DECISIONS.md`** (INDEX says INV-49 / D-36, but INDEX can lag the repo too); confirm no UI/contract INV landed post-S7b sync. Take the next free id; never renumber.
7. `UX.md` §3 cross-tenant-baseline prefill `[VERIFY]` — out of scope for F0 (no prefill *source* wired); must resolve before `FE-5` wires a prefill source. Note, do not action.

## Resolved decisions (rationale in chat design session / FRONTEND.md)

| Fork | Resolution |
|---|---|
| Client↔API topology | BFF, bearer-forwarding; browser holds an opaque session id, never a token (D-37, INV-50) |
| Operator separation | Two apps, separate origins (INV-1) |
| Framework | Next.js App Router + React + TS strict; Next server = BFF |
| Styling | Radix primitives + Tailwind, token-driven |
| Server state | TanStack Query through the BFF; lifecycle/authz/coverage reads routed through `useLiveState` |
| Token store | Server-side store keyed by opaque session id (see Appendix A for backing) |

---

## Work items (dependency-ordered)

**W1 · Monorepo scaffold.** pnpm workspace + Turborepo. `apps/tenant`, `apps/operator` (Next App Router, TS strict). `packages/api-client`, `packages/tokens`, `packages/ui`. Enforce the package boundary: `tokens`/`ui`/`api-client` importable by both apps; auth/cookie/pool config importable by neither (each app owns its own).
↳ done-check: both apps boot; a lint/dep rule fails the build if an app imports another app's auth module.

**W2 · `packages/tokens` (FE-3).** Primitive token layer (colour/spacing/type/elevation/radius) as CSS custom properties + Tailwind theme mapping; two skins (tenant, operator) over one primitive set. Lint rule rejecting literal colour/spacing in components.
↳ done-check: a component using a hex/px literal fails lint; both skins resolve AA contrast on text tokens (automated check).

**W3 · BFF auth plane, per app (FE-2, INV-1, INV-50, D-37, NFR-1).** In each app: PKCE authorization-code flow against *that app's* Cognito pool; `login`/`callback`/`logout`/`refresh` route handlers; **server-side session store keyed by an opaque session id** (Appendix A) — no token in the browser; httpOnly + `SameSite=Lax` cookie scoped to the app origin; refresh rotation server-side; idle + absolute session lifetime; middleware gating protected routes on the cookie. **CSRF:** origin / `Sec-Fetch-Site` check on every state-changing BFF route.
↳ done-check (tests): login→callback sets the cookie; an unauthenticated hit on a protected route 302s to login; the cookie contains only an opaque id (no token in any browser-visible response or storage); a cross-origin POST to a state-changing BFF route without a same-origin `Sec-Fetch-Site` is rejected; (structural) the tenant cookie is not accepted at the operator origin.

**W4 · `packages/api-client` (FE-6, FE-9, INV-3, INV-13).** Typed fetch wrapper that calls **only** the app's BFF proxy, never the API directly. BFF proxy route forwards the bearer to the API. Wrapper: propagates `If-Match` from a supplied `lock_version`; maps `412`→`StaleLockError`, `409`→`BadFromStateError`, plus `422`/`404` to typed errors; refuses to attach `tenant_id` or `provenance` to any request (compile-time + runtime guard).
↳ done-check (tests): a provenance mutation sends `If-Match`; 412 and 409 produce distinct typed errors; a request constructed with `tenant_id`/`provenance` is rejected before send; browser network trace shows zero direct-to-API calls (all hit the BFF origin).

**W5 · TanStack Query + mandatory live-state discipline (FE-7, INV-25, INV-32).** Query client wired through `api-client`. Lifecycle/gate-vector/coverage/authorisation reads go through a typed `useLiveState` helper: `staleTime: 0`, mandatory invalidate-and-refetch on any consequential mutation, no optimistic rendering of a lifecycle/authorisation verdict, `live_state` read never row-existence. **Enforcement (N6):** a query-key registry + lint rule *routes* all such reads through the helper — a raw default-`staleTime` query against a live-state key fails lint. The helper is mandatory, not merely available.
↳ done-check: a mutation invalidates the relevant live-state queries; a raw live-state query bypassing the helper fails lint (test); reading a cached lifecycle verdict across a transition is impossible through the sanctioned path.

**W6 · `packages/ui` base + flagged primitives (FE-4, FE-5, FE-8).** Radix+Tailwind base set (button, select, multiselect, table, queue row, dialog). The two flagged controls scaffolded: structured-input set (FE-4) and prefill-with-basis (FE-5, rendering the server provenance badge + basis + override→structured pick). SoD-visible action wrapper (FE-8): renders nothing for a structural bar, disabled-with-reason for a transient block — **presentational only; the backend stays the authz authority (D-4, INV-7, INV-28, D-24); a barred control is still backend-rejected if invoked.** The 412/409 surface components. "Whose-court" status indicator.
↳ done-check (tests + axe): prefill-with-basis renders the server provenance value and never emits one on override; the SoD wrapper omits a barred control entirely (not disabled); primitives pass axe AA.

**W-BE · Caller-roles read (CONDITIONAL on §0-1b; backend; read-only; sequence before W7b).** If no self-scoped caller-roles read exists: add `GET /v1/me` returning the caller's **single** membership (one-tenant-per-user, ARCH §5) + governance role set, scoped to `ctx` (`ctx.membership_id`), joining via `membership` (INV-34), never bare `app_user` (INV-2). Gate: any authenticated tenant member; no SoD concern (reading own roles). No schema change. Audit: none (pure read).
↳ done-check (tests): the route returns only the caller's own membership + roles; a caller cannot read another membership's roles through it; RLS-scoped.

**W7a · Auth-plane smoke surface, per app (no roles dependency).** An authenticated shell in each app that performs one caller-scoped read that definitely exists (tenant: a tenant-scoped read; operator: an operator identity read), proving login → BFF holds token → bearer forwarded → API returns caller-scoped data → render. No business workflow, no role gating.
↳ done-check (integration): end-to-end auth + bearer-forward + tenant/operator scoping per app/origin; tenant and operator sessions never interchange (re §0-4).

**W7b · Role-aware render (depends on W-BE / §0-1b).** Extend the tenant shell to read the caller's membership + governance roles and render role-aware (FE-10, UX-5) — adoption vs assurance affordances gated by the server-authoritative role set (never token claims, D-24). Presentational only (FE-8).
↳ done-check (integration): the shell renders affordances matching the caller's governance roles from the server read; removing a role server-side changes the rendered affordances on refetch.

**W8 · Canonical update (always last).** Apply the companion `FRONTEND.md` (FE-1..10) verbatim — it is the apply-source, not re-authored here. Update `STATE.md`: add a UI-build entry — F0 foundation built (two Next BFF apps, per-plane auth, shared `api-client`/`tokens`/`ui`, contract plumbing, smoke surfaces are scaffold not feature); record whether W-BE added `GET /v1/me` or an existing self-read was used. `DATA-MODEL.md`: **no change** — state explicitly that F0 touched no schema/DB (W-BE is a read endpoint, no schema). Append `INVARIANTS.md` **INV-50** (browser holds no token; no direct browser→API — all browser→API via the plane's own BFF; cite INV-1, D-37) at the verified next free id. Append `DECISIONS.md` **D-37** (frontend topology: Next BFF per plane, separate origins, bearer-forward preserves `verify_cognito_token` — additive over greenfield; rejected: SPA-direct token-in-browser, cookie-direct-to-API; enforces INV-50; refs INV-1, D-22, D-24). Never renumber a live INV-n/D-n. Leave the stable tier (`DOMAIN`/`REQUIREMENTS`/`ARCHITECTURE`/`UX`/`PLATFORM-UX`/`PATTERNS`) untouched.
↳ done-check: `FRONTEND.md` has no `[TBD]` in §1/§6/§7; STATE reflects F0 + the W-BE outcome; INV-50/D-37 appended at the verified ceiling; no live id renumbered.

---

## Appendix A — open decisions (defer, do not resolve here)

- **BFF session-store backing (N3).** MVP shape is fixed — opaque session id in cookie + server-side token store (INV-50-clean). Backing is open: in-memory is **dev-only / not multi-instance-safe** (breaks refresh continuity and horizontal scale); a shared store (Redis, or a platform-plane session table) is the production shape. Record the chosen MVP tradeoff when W3 lands.
- Token palette / type scale specifics → first feature surface (intake wizard).
- Per-surface RSC-fetch vs client-fetch split → convention set in W5, applied per surface later.
- Whether `ARCHITECTURE.md` should gain a one-line "deployables" note for the two BFF apps → founder call; not auto-edited (stable tier).
- Operator console eventually forking the token primitive layer if density needs diverge hard → revisit; F0 shares the primitive, skins differ.

## Appendix B — source-verification register

| Item | Source to check | Blocks |
|---|---|---|
| `verify_cognito_token` reads bearer header only | `app/auth/cognito.py` | W3, W4 |
| Caller's-own-governance-roles read exists + self-scoped | live routers / STATE governance role mgmt | W-BE, W7b (B1) |
| PKCE/auth-code, callback+logout URLs, refresh rotation, TTLs (both pools) | Terraform `infra/` | W3 |
| API needs no browser-facing CORS (same-origin BFF) | API app config | W4 |
| `verify_operator_token` plane separation holds with both BFFs on one API origin | `app/auth/operator_auth.py` + router prefixes | W7a operator |
| SSO/SAML MVP-deferred | STATE / NFR-1 | W3 login scope |
| INV/D ceiling — confirm against **live** `INVARIANTS.md`/`DECISIONS.md` (not INDEX); no post-sync UI/contract INV | live canon | W8 |
| Cross-tenant-baseline prefill `[VERIFY]` | UX.md §3 / INV-4 | future FE-5 prefill source (not F0) |