# FRONTEND.md — IronTrust Frontend Build Conventions

**Location:** `docs/FRONTEND.md` — single source, mirrored to project knowledge. Updated occasionally (a new `FE-n` is appended as a convention stabilises).
**Purpose:** How the UI is *built and rendered* — framework, component library, design tokens, accessibility, and the client↔API contract. The implementation counterpart to `UX.md` / `PLATFORM-UX.md`, which carry intent.
**Lanes:** tenant experience intent → `UX.md`; operator experience intent → `PLATFORM-UX.md`; backend service / concurrency shapes → `PATTERNS.md` (`PAT-n`); this file → how surfaces are rendered and how the client talks to the API.
**ID scheme:** frontend build conventions take **`FE-n`** (parallel to backend `PAT-n`), so designs and reviews can cite them. The *rule* lives once here; rationale stays in `DECISIONS.md` (`D-n`) / `INVARIANTS.md` (`INV-n`) and is cited, not restated.

**Status:** topology resolved (`D-37`); `FE-1..13` populated. Token palette/type-scale specifics and per-surface fetch splits remain `[TBD — per-surface]`.

---

## 1. Stack & framework — `FE-1`

**FE-1 · Two Next.js apps, separate origins; the Next server layer is the BFF.**

- **Framework:** Next.js (App Router) + React + TypeScript (`strict`). Build tooling and package management: pnpm workspace monorepo (Turborepo orchestration).
- **Two apps, separate deployments/origins** — `apps/tenant` and `apps/operator` — never one route-gated app. Origin separation is the structural correlate of plane separation (`INV-1`): a tenant session cookie is physically un-sendable to the operator origin, so token confusion is impossible without app-level discipline.
- **The Next server layer is the BFF** (`D-37`). Cognito tokens live server-side only; the browser holds no token and never calls the API directly (`INV-50`). Browser↔BFF rides an httpOnly + `SameSite` session cookie; BFF↔API forwards `Authorization: Bearer <cognito ID token>` — `verify_cognito_token` requires `token_use=="id"` and reads `custom:tenant_id`/`custom:role`, claims that live on the ID token, not the access token — which preserves `verify_cognito_token` unchanged — additive over greenfield, no backend auth rewrite (`D-22`).
- **Monorepo package boundary.** Shared across both apps: `packages/api-client` (the contract layer, §5/§6), `packages/tokens` (§2), `packages/ui` (§3). **Never shared:** auth context, session cookies, Cognito pool config — each app owns its own, per `INV-1`. Sharing rendering/contract is safe; sharing an auth context is the one thing that would breach plane separation.
- **Desktop-first** (the assurance face is a workstation tool); responsive behaviour per `UX.md`.

## 2. Design tokens & theming — `FE-3`

**FE-3 · One primitive token layer, two theme skins; no magic values.**

- Colour, spacing, type scale, elevation, radius are tokens (`packages/tokens`), surfaced as CSS custom properties and mapped into the Tailwind theme. Components carry **no literal colour/spacing values** — enforced by lint.
- **Two skins over one primitive layer.** The tenant adoption face (friendlier, more spacious) and the operator console (denser, utilitarian) have opposite drivers (`UX.md` §2 / `PLATFORM-UX.md` §2); they consume the same primitive tokens through two theme skins, not two token systems.
- AA contrast is built into the token choices, not bolted on later (ties §4).

## 3. Component library — `FE-4`, `FE-5`, `FE-8`

Built on Radix primitives (accessible, headless) + Tailwind, themed by `FE-3`. Three primitives are load-bearing:

**FE-4 · Structured-input set.** Realises the `UX.md` §3 input-preference order as components: prefilled-confirm → single-select → multi-select → constrained-structured (date/number/bounded enum) → contained free-text (last resort). Select-first by default, realising `UX-2`/`UX-3`.

**FE-5 · Prefill-with-basis control.** The §1.5 spine at field level (`D-1`, `UX-2`/`UX-4`): renders the server-derived provenance badge (`INV-13`, `PAT-8` — fixed 4-value vocabulary, never client-set), the shown basis, and a one-click override whose input is **also a structured pick** plus optional justification; the deviation is tracked server-side. The client never authors a `provenance` value.

**FE-8 · SoD-visible action controls.** The visual correlate of act-SoD (`UX-5`, `INV-28`): a control for an act the caller is **structurally barred** from by separation of duties is **not rendered** (not merely disabled) — e.g. no approve control on work the caller authored. **Transient** blocks (wrong lifecycle state, stale lock) render disabled with a reason. The two are distinct: structural bar → absent; transient → disabled-with-reason. **Presentational only:** the backend remains the SoD/authz authority (`D-4`, `INV-7`, `INV-28`, `D-24`) — a control the UI omits or disables is still rejected server-side if invoked; the UI is never the enforcement locus.

Also in `packages/ui`: tables, queue rows, export views; the 412/409 surfaces (`FE-6`); the "whose-court" status indicator (`UX.md` §5). Specify palette-level detail per surface when built.

## 4. Accessibility

Durable intent now, specifics later: **WCAG 2.1 AA** as the working baseline (enterprise + EU buyers expect it), full keyboard operability, visible focus, semantic structure. Radix primitives (`FE-3`/`FE-4`) carry the baseline; the bar is held by automated axe checks plus manual keyboard passes per surface. *[exact target confirmed AA; revisit only if a buyer demands AAA on a surface]*

## 5. Client ↔ API contract — durable (from the backend canon)

These are fixed by the backend; the client honours them from surface one. The *rule* is stated here; implementation lives in §3/§6 and cites back.

- **No token in the browser; no direct browser→API.** Every browser→API call goes through the plane's own BFF; the BFF holds the Cognito token and forwards the bearer. → `INV-50`, `D-37`, `D-22`.
- **Plane-separated auth.** The tenant app authenticates against the **tenant** Cognito pool; the operator console against the **operator** pool — separate auth contexts, separate origins, never shared or interchangeable. → `INV-1`; `PLATFORM-UX.md`.
- **Optimistic concurrency.** Mutations on provenance-bearing rows send an `If-Match` header carrying the expected `lock_version`. The client distinguishes **`412`** (stale lock — reload, re-present, retry) from **`409`** (bad from-state — the action is no longer valid) and surfaces them differently. → `PAT-6`, `INV-14`; impl `FE-6`.
- **Live state is server-computed.** Lifecycle state, gate vector, control coverage, and deployment authority are computed server-side and authoritative only as of the last read. The client refetches after any consequential mutation and never renders a cached lifecycle/authorisation verdict as settled across a transition; "authorised" is read from the computed `live_state`, never inferred from a row's existence. → `INV-25`, `INV-32`; impl `FE-7`.
- **SoD is visible.** A control for an act the caller is barred from by separation of duties is not rendered; transient blocks render disabled-with-reason. → `UX-5`, `INV-28`; impl `FE-8`.
- **`tenant_id` is never client-supplied.** Resolved server-side from token/context; the client never puts `tenant_id` in a request body or a URL it constructs. → `INV-3`.
- **Provenance is server-derived.** The client never sends a `provenance` value; it renders what the server returns and drives the confirm/amend ladder off it. → `INV-13`; impl `FE-5`.
- **Evidence download** is always via the hardened `GET /v1/evidence/{id}` (forced attachment, neutralised content-type); the client never inline-renders evidence bytes. → `INV-22`.

## 6. Client state & data fetching — `FE-2`, `FE-6`, `FE-7`, `FE-9`

**FE-2 · BFF auth & token custody.** Each app's Next server runs the Cognito **authorization-code + PKCE** flow against its pool, owns `login` / `callback` / `logout` / `refresh` route handlers, and keeps the ID/refresh tokens in a **server-side session store keyed by an opaque session id** — the browser cookie carries only the opaque id, never a token (the crisp reading of `INV-50`; this rules out token-bearing encrypted cookies). The session cookie is httpOnly + `SameSite=Lax`, scoped to that app's origin. **CSRF:** state-changing BFF routes additionally enforce an origin / `Sec-Fetch-Site` check — `SameSite` alone is not the whole defence — a named `NFR-1` control. Refresh rotation is server-side; sessions carry an idle timeout and an absolute lifetime. Route protection is BFF middleware on the session cookie. → `INV-1`, `INV-50`, `D-37`, `NFR-1`.

**FE-9 · Server-state library; all mutations through the BFF.** TanStack Query (React Query) is the server-state cache, fetching through the BFF proxy. Reads may be RSC server-fetched (token already server-side) or client-fetched via the BFF; **mutations always route through the BFF** (token custody). The client never sets `tenant_id` (`INV-3`) and never sends `provenance` (`INV-13`).

**FE-6 · Optimistic-concurrency handling.** The client carries `lock_version`/ETag and sends `If-Match` on provenance-bearing mutations. On **412**: invalidate, refetch, re-present the fresh row, let the user retry — never silently retry. On **409**: treat the action as void, surface that the state moved on. The two are never collapsed. → `PAT-6`, `INV-14`.

**FE-7 · Live-state discipline.** Lifecycle state, gate vector, coverage, and authorisation are treated as non-cacheable verdicts: `staleTime: 0` for those reads, mandatory invalidate-and-refetch after any consequential mutation, and no optimistic rendering of a derived lifecycle verdict as settled. Deployment authority is read from `live_state`, never row-existence. → `INV-25`, `INV-32`.

## 7. Routing & surface structure — `FE-10`

**FE-10 · Two-app, separate-origin topology; role-aware rendering from server-authoritative roles.**

- **Two apps, never a shared route tree** (`INV-1`, `FE-1`). Each app's BFF owns its auth routes; protected routes gate on the session cookie. Plane separation is origin-level.
- **Tenant app** carries both faces on one capture-once spine (`UX.md` §2 — adoption vs assurance are role-conditioned renderings, not separate apps). Surfaces map to `UX.md` §5: intake/registration wizard · inventory/dashboard · review queue · assessment (AIIA) view · evidence/audit-pack · "whose-court" status. Each surface is designed just-in-time against the principles and the two faces (`UX.md` §5).
- **Operator console** (the separate app) maps to `PLATFORM-UX.md` §3: provisioning · operator RBAC · catalogue/reference curation · curation-task inbox. Every platform capability is UI-operated (`INV-49`, `D-36`); the console never renders a tenant face.
- **Role-aware rendering** (`UX-5`) reflects governance role from the server-authoritative context (never token claims — `D-24`); structurally-barred controls are absent (`FE-8`). Operator-console permission-aware rendering follows `FE-13` (cross-ref).

## 8. Whose-court derivation — `FE-11`

**FE-11 · Whose-court is a direct `blocking.responsible_party` read, mapped through a fixed party→role table.** No pre-branch: court is read directly off the per-use-case `blocking` vector, always — the gate logic (`app/services/lifecycle_gates.py`) already resolves a `REQUIRES_CONTEXT`/`UNCLASSIFIED` use case correctly between the reviewer (classification still `PENDING_REVIEW`) and the owner (once it isn't), so no client-side special case is needed or correct. `responsible_party`'s vocabulary (`"user"|"reviewer"|"authoriser"|"vendor"|"system"`) is distinct from the governance-role vocabulary — map `"user"`→`system_owner`, `"reviewer"`/`"authoriser"` 1:1, `"vendor"`/`"system"`→ no role (never anyone's court, since neither is a governance role). The client matches the resolved role against the caller's server-authoritative `GET /v1/me` roles to highlight "your court" — presentational only, the backend remains the authz authority. → `D-38`, `FE-8`, `INV-28`, `D-4`, `D-24`.

## 9. Binary file upload — `FE-12`

**FE-12 · Binary file uploads must route through a dedicated BFF handler; never through the generic proxy.**

The generic BFF proxy (`app/api/proxy/[...path]/route.ts`) reads the request body via `await request.text()`, which UTF-8-decodes the raw bytes. For binary files (PDF, images, ZIP), this silently corrupts byte sequences that are not valid UTF-8 and corrupts the multipart boundary. The result arrives at the API as a malformed body with a mismatched SHA-256.

Any route that accepts a file upload (`multipart/form-data`) **must** have a dedicated Next.js route handler that:
1. Reads the body as `await request.arrayBuffer()` — preserves binary content verbatim.
2. Forwards the `Content-Type` header including the `boundary=` parameter — the API needs the boundary to parse the multipart body.
3. Enforces the same CSRF check (`isSameOriginRequest`) and session gate (`getSession`) as every other state-changing BFF route (`FE-2`, `NFR-1`).
4. Applies a client-side size ceiling (50 MB) before the API call to surface a friendly error early.

**Current instance:** `apps/tenant/app/api/evidence-upload/route.ts` for `POST /v1/evidence`. Any future multipart upload route must follow this pattern, not the generic proxy.

**Why not fix the proxy:** the generic proxy is a pass-through router; switching all requests to `arrayBuffer()` would break form-body routes that send `application/x-www-form-urlencoded` or `application/json` and legitimately rely on text decode. The dedicated handler is the narrower, safer fix.

→ `INV-18`, `INV-22`, `FE-2`, `NFR-1`, `INV-50`; rationale `DF5-2`.

## 10. Operator-console permission-aware rendering — `FE-13`

**FE-13 · Controls for an operator permission the caller does not hold are absent, not disabled. Presentational only; `require_permission` is the authz authority.**

The operator-plane analogue of `FE-8` (tenant act-SoD absence), grounded on `INV-8`/`D-24` rather than act-SoD:

- **Permission held:** the control renders normally.
- **Permission not held:** the control is **absent** from the DOM — never disabled, never greyed. No capability is leaked behind a visible placeholder.
- **Presentational only:** a forged direct call to a permission-gated API route still returns 403. The UI absence is a usability/non-disclosure choice; the backend `require_permission` dependency is the enforcement locus.

**Implementation:** `apps/operator/components/require-permission.tsx` (`RequirePermission` component). Usage pattern: wrap any permission-gated nav entry or control in `<RequirePermission permission="tenant:provision" permissions={permissions}>...</RequirePermission>`. The permission keys come from `GET /platform/me` (`D-39`); the byte-exact key for provisioning is `'tenant:provision'`.

**Nav shell axis:** operator nav distinguishes `FE-13` permission-absence (absent) from unbuilt-surface visibility (visible-disabled). When an unbuilt surface is built and permission-gated, its entry adopts `FE-13` absence, never a greyed placeholder (`DF7-2`).

→ `INV-8`, `D-24`, `D-39`, `FE-8`, `PLATFORM-UX §2`; source `UI-F7-PROVISION`.

---

### FE-n index

| ID | Convention | Cites |
|---|---|---|
| FE-1 | Two Next.js apps, separate origins; Next server is the BFF; pnpm-workspace monorepo with shared contract/token/ui packages, never-shared auth | INV-1, INV-50, D-37, D-22 |
| FE-2 | BFF auth: PKCE auth-code, opaque-session-id + server-side token store, httpOnly+SameSite=Lax cookie, CSRF origin check, bearer-forward to API, per-pool/per-origin scope | INV-1, INV-50, D-37, NFR-1 |
| FE-3 | One primitive token layer, two theme skins; no magic values; AA contrast baked | UX.md §2, PLATFORM-UX §2 |
| FE-4 | Structured-input set (input-preference order) | UX-2, UX-3 |
| FE-5 | Prefill-with-basis control (provenance badge, basis, override→structured pick, tracked deviation) | D-1, UX-2, UX-4, INV-13, PAT-8 |
| FE-6 | Optimistic-concurrency handling — 412 vs 409 distinct | PAT-6, INV-14 |
| FE-7 | Live-state discipline — server-computed verdicts, refetch on mutation, read live_state | INV-25, INV-32 |
| FE-8 | SoD-visible controls — structural bar absent, transient block disabled-with-reason; presentational only, backend is authz authority | UX-5, INV-28, D-4, INV-7, D-24 |
| FE-9 | TanStack Query through the BFF; mutations always via BFF; no client tenant_id/provenance | INV-3, INV-13 |
| FE-10 | Two-app separate-origin routing; tenant (UX §5) / operator (PLATFORM-UX §3) surfaces; role-aware render | INV-1, INV-49, D-36, UX-5, D-24 |
| FE-11 | Whose-court derivation — direct `blocking.responsible_party` read, no pre-branch, fixed party→role mapping, presentational highlight | D-38, FE-8, INV-28, D-4, D-24 |
| FE-12 | Binary file uploads via dedicated BFF handler (arrayBuffer(), not text()); generic proxy must never handle multipart | INV-18, INV-22, FE-2, NFR-1, INV-50, DF5-2 |
| FE-13 | Operator-console permission-aware render — permission absent → control absent (not disabled); presentational only, `require_permission` is authz authority | INV-8, D-24, D-39, FE-8, PLATFORM-UX §2 |