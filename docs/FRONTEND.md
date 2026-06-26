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
| FE-4 | Structured-input set (input-preference order) **[ALTER UI-C2: input-family visual pass — new `TextInput` single-line primitive (`packages/ui/src/structured-input/text-input.tsx`, `<input type="text">`, same `border-hairline rounded border px-3 py-1.5 text-sm text-ink` chrome, exported from `packages/ui/src/index.ts`); `SingleSelect` gains visible border, caret SVG, `appearance-none`; `MultiSelectInput` replaces checkbox layout with wrapping toggle-chip cluster (selected: `bg-ink text-surface border-ink`; unselected: `bg-surface border-hairline hover:bg-surface-sunken`) (INV-73); `FreeText` gains proper `<label>` pairing and textarea border chrome. `IntakeCaptureStep` system-name raw `<input>` replaced with `TextInput`; vocab aggregate gate added: `Skeleton` while any of the six vocab queries loads; retryable `ErrorState` if any error.]** | UX-2, UX-3, INV-73 |
| FE-5 | Prefill-with-basis control (provenance badge, basis, override→structured pick, tracked deviation) **[ALTER UI-C2: `PrefillWithBasis` layout pass — value + `ProvenanceBadge` on same `flex` row; basis text below; override form with `space-y-3 border-t border-hairline pt-3`; styled inline `<select>` and `<textarea>`; `flex gap-2` button row. `PrefillStep` redundant outer `<li>` border removed — `PrefillWithBasis` now provides its own card chrome (`rounded border border-hairline bg-surface p-4`).]** | D-1, UX-2, UX-4, INV-13, PAT-8 |
| FE-6 | Optimistic-concurrency handling — 412 vs 409 distinct | PAT-6, INV-14 |
| FE-7 | Live-state discipline — server-computed verdicts, refetch on mutation, read live_state | INV-25, INV-32 |
| FE-8 | SoD-visible controls — structural bar absent, transient block disabled-with-reason; presentational only, backend is authz authority | UX-5, INV-28, D-4, INV-7, D-24 |
| FE-9 | TanStack Query through the BFF; mutations always via BFF; no client tenant_id/provenance | INV-3, INV-13 |
| FE-10 | Two-app separate-origin routing; tenant (UX §5) / operator (PLATFORM-UX §3) surfaces; role-aware render | INV-1, INV-49, D-36, UX-5, D-24 |
| FE-11 | Whose-court derivation — direct `blocking.responsible_party` read, no pre-branch, fixed party→role mapping, presentational highlight | D-38, FE-8, INV-28, D-4, D-24 |
| FE-12 | Binary file uploads via dedicated BFF handler (arrayBuffer(), not text()); generic proxy must never handle multipart | INV-18, INV-22, FE-2, NFR-1, INV-50, DF5-2 |
| FE-13 | Operator-console permission-aware render — permission absent → control absent (not disabled); presentational only, `require_permission` is authz authority | INV-8, D-24, D-39, FE-8, PLATFORM-UX §2 |
| FE-14 | Three-layer token architecture — primitive (`packages/tokens/src/primitives.css` `@theme`) → semantic channel (`:root`; `--prov-*`, `--verdict-*`, `--court-*`, `--sev-*`) → component aliases. Components reference semantic tokens only, never primitives or literal hex/px (lint-enforced, `V-4`). Light-first; every token reserves a dark slot (VDD-4). | INV-54, INV-63, D-41, VDD-2, VDD-4 |
| FE-15 | Provenance channel — 4 tones (`--prov-ai-suggested/catalogue-curated/user-confirmed/user-amended`); hue on dot/border only; label always `--ink`; AI-suggested is the sole dashed member. 4-value by design, no `USER_PROVIDED` (V-2, PAT-8). | INV-55, INV-57, D-42, PAT-8 |
| FE-16 | Verdict-tone model — six meaning-class tones (neutral/progress/positive/attention/halt/terminal) serve `assessment_status`, `lifecycle_state`, `classification_status`, `coverage_status`, `approval_status`. `VerdictChip` renders these five enums only. `eu_ai_act_tier` is rendered exclusively via `TierBadge` on a dedicated `--tier-*` magnitude channel (four fill/text pairs for PROHIBITED/HIGH/LIMITED/MINIMAL; resolution states UNCLASSIFIED/REQUIRES_CONTEXT re-use `--verdict-neutral`/`--verdict-attention`). The two channels are orthogonal: magnitude is not a verdict, verdict is not a magnitude. **[Amended UI-V1-TENANT-SKIN / D-48]** **[ALTER UI-V2-DEPTH-LAYOUT / D-60: `VerdictChip` gains a flat `value`→label map (`packages/ui/src/status/verdict-label-map.ts`); it renders `LABEL_MAP[value] ?? value` instead of the raw wire value. Map keys are the wire `.value` exactly as the server emits them (lowercase snake_case); never `.toUpperCase()` (D-48, DF-V2-4). 25 unique keys; shared values (`approved`, `needs_refresh`) resolve to one label each. TONE_MAP + `data-tone` attribute unchanged. Unknown value falls back to raw value + `console.warn` (INV-75 defensive). All F2–F8 surfaces inherit (kit-level). `LABEL_MAP` exported for test coverage.]** | INV-56, INV-64, INV-75, D-43, D-48, D-60, FE-7 |
| FE-17 | Type — IBM Plex Sans (UI), Mono (identifiers / `lock_version` / SHA digests), Serif (exported document face). Self-hosted OFL, latin subset, weights 400/500/600 only. No runtime CDN. Sizes integer px only (no half-px). | INV-58, D-44, V-6 |
| FE-18 | Two-skin model — tenant (comfortable, 16–24px rhythm) and operator (compact, 6–12px) share one primitive/semantic token core; skins override values under `[data-theme="..."]`, never redeclare keys. Operator nav rail carries `--color-brand-strong` (plane-identity marker, INV-1). | INV-59, INV-60, D-45, VDD-5 |
| FE-19 | Motion — 120/180/240ms durations, standard easing, `prefers-reduced-motion` disables all transitions. No celebratory or completion motion. | INV-61, D-46 |
| FE-20 | App shell — `AppShell`/`Sidebar` primitives in `packages/ui/src/shell`. Tenant variant: brand, vertical nav items with active-link highlighting (isActive computed by caller), slim top utility bar at head of main column (logged-in user: display name or email + sign-out; reads cached `["me"]`; `top-utility-bar.tsx`), tenant name in sidebar foot from `MeRead.tenant_name`; no top-bar nav. **[ALTER UI-C1: identity fold — user moves to top utility bar; tenant name wired into sidebar foot; nav stays in sidebar; D-52.]** Operator variant: identical `Sidebar` with `railBg="var(--chrome-rail-bg)"` (INV-60) and custom `nav` slot carrying `RequirePermission`-gated entries (FE-13); replaces the reactive `AppNav` top-bar (provisional, UI-V1). `AppShell` renders `flex h-screen`: fixed-width `Sidebar` + `flex-1 overflow-y-auto main`. | INV-60, INV-68, D-51, D-52, FE-13 |
| FE-21 | Page scaffold — `PageHeader` (title h1, subtitle, primary-action slot, breadcrumb/step slot) and `PageScaffold` (`mx-auto max-w-4xl px-6 py-8 space-y-8`); both in `packages/ui/src/scaffold`. `PageScaffold` is composed inside `AppShell`'s `<main>` by each surface. Supersedes the reactive 26-page `mx-auto max-w-4xl` per-page pattern (provisional, UI-V1); existing surfaces updated in per-surface composition passes (Appendix C register). **[ALTER UI-C2: `PageHeader` gains optional `onBack?: () => void` prop; when present, a `ChevronLeft` icon-button (`aria-label="Go back"`) renders before the title, both wrapped in `flex items-start gap-2`. All existing `PageHeader` consumers are unaffected (prop absent = no change). `DrillDownStep` wires `onBack={exitCustom}` on the main accordion header; confirm stage wires `onBack={() => setSelectedProductId(null)}`.]** **[ALTER UI-V2-DEPTH-LAYOUT: `PageScaffold` gains `width?: 'default' \| 'wide' \| 'full'`; `'default'` keeps `max-w-4xl` (all current consumers unchanged, DF-V2-2); `'wide'` = `max-w-6xl`; `'full'` = no max-w constraint. Unlocks side-by-side groups and full-width tables for future surfaces.]** | INV-68, INV-69, D-51 |
| FE-22 | UI state patterns — `EmptyState` (icon, message, optional action; `role="status"`), `FirstRunPanel` (heading h2, body, action), `Skeleton` (pulsing placeholder blocks; `lines?` param; `SkeletonBlock` single-block variant), `ErrorState` (calm retryable: muted danger icon, message, `Try again` button, optional support line); all in `packages/ui/src/state`. **[UI-C1: `Skeleton` and `ErrorState` now built; owed-target note removed.]** | INV-68, INV-70, D-51 |
| FE-23 | Shared primitive kit in `packages/ui/src/kit` — new: `StatCard` (label, value, optional trend), `SectionHeader` (h2 + optional action), `ListSelectRow` (whole-row button, single trailing chevron, no per-row label); altered: `Button` hierarchy (primary/secondary/ghost review); `DataTable` scaffold extends existing `Table`/`TableBody`/`TableRow` (INV-66) — adds border wrapper, `DataTableHeader`, `DataTableBody` with `EmptyState` fallback; no new `<tbody>` primitive. Cites FE-4/FE-5/FE-8; does not restate them. **[ALTER UI-C2: `ListSelectRow` gains optional `leading?: React.ReactNode` slot rendered immediately before the label in the button body; trailing chevron unchanged. Vendor and product rows pass `<LogoTile …>` as `leading`; category rows omit it. See FE-25.]** **[ALTER UI-C2-FULL: `ListSelectRow` gains branch mode — three optional props: `onToggle?: () => void`, `expanded?: boolean`, `children?: React.ReactNode`. When `onToggle` is provided, the row is a disclosure trigger: clicking calls `onToggle` (not `onClick`); `aria-expanded` reflects `expanded`; the trailing `ChevronRight` rotates 90° when `expanded=true`; `children` render in a `<div>` below the button when `expanded && children`. Leaf rows (no `onToggle`) are unchanged. Single-open state managed by the caller (`DrillDownStep`). (INV-73: chevron rotation uses `transition-transform` class only — no semantic channel colour.)]** | INV-66, INV-68, INV-69, INV-73, D-51, D-56 |
| FE-24 | Members surface: administrative-axis nav + page gating (DF-F9-3) — entry rendered and page calls issued iff `MeRead.role === "admin"`, absent otherwise (zero `GET /v1/members` for non-admin); member list from `GET /v1/members` (INV-2); accept-status chip is **neutral non-semantic chrome** (`data-accept-status` attribute; no `--verdict-*` token — FE-16 untouched); roles-held column from single tenant-wide `GET /governance-roles/assignments` grouped by `membership_id` (no N+1); SoD-visible assign control (INV-71) — resolvable conflict → disabled-with-reason, structural self-assignment bar → control absent + note (INV-56); pending member is assignable; composed from FE-20..FE-23 kit (INV-69) with all four INV-70 states; born-compliant. **P2 note:** live DB contains a 6th role key `system_owner_smoke` (dev artifact, no conflict entries); the client binds the live catalogue verbatim — SoD matrix logic is unaffected. | FE-8, FE-13, FE-16, FE-20..23, INV-2, INV-56, INV-69, INV-70, INV-71, DF-F9-3 |
| FE-25 | `LogoTile` kit component — `packages/ui/src/kit/logo-tile.tsx`. Props: `src?: string | null`, `name: string`, `size?: number` (default 40). Renders `<img src={src} alt={name} className="h-full w-full object-contain">` when `src` is a non-null string; otherwise renders a `<span>` monogram containing 1–2 initials (first letter of each whitespace-delimited word, capped at 2, uppercased). Monogram uses neutral ramp only — `bg-surface-sunken border-hairline text-ink-muted text-xs font-semibold`; no `--verdict-*` or semantic tokens (INV-63). `aria-label={name}` on the outer container. Default size 40px on vendor/product `ListSelectRow` rows (FE-23 `leading` slot); 24px (`size={24}`) for the vendor identity line in the confirm step. Exported from `packages/ui/src/index.ts`. | INV-63, INV-68, INV-69, D-55, D-56, FE-23 |
| FE-26 | Elevation + surface-layering tokens (`packages/tokens/src/primitives.css` `:root`). Two steps: `--elevation-raised` (soft card shadow: `0 1px 3px rgba(0,0,0,0.08), 0 1px 2px rgba(0,0,0,0.04)`) and `--elevation-overlay` (panel overlay: `0 4px 6px rgba(0,0,0,0.07), 0 2px 4px rgba(0,0,0,0.05)`). Deployment rules: page on `--color-surface` (unchanged), cards on `bg-paper` + `shadow-[var(--elevation-raised)]`, sunken sub-panels on `bg-[var(--color-surface-sunken)]`. Shadows are decorative-neutral: not WCAG text/graphical pairings, not added to `contrast.test.ts` (DF-V2-1). Dark slots reserved (VDD-4). `StatCard` updated to `bg-paper` + `--elevation-raised`. | INV-62, INV-63, D-58, DF-V2-1, VDD-4 |
| FE-27 | Layout + sectioning — `SectionGroup` component in `packages/ui/src/scaffold/section-group.tsx`. Props: `title: string`, `children: ReactNode`, `sunken?: boolean`. Renders: petrol accent bar (`w-0.5 bg-brand`) + brand title (`text-brand font-semibold uppercase tracking-wider text-xs`) + children + hairline bottom divider (`border-b border-hairline`, absent on last child). Sunken variant wraps children in `bg-[var(--color-surface-sunken)] rounded-lg p-4`. Composes on the existing FE-23 kit (`StatCard`, `SectionHeader`, `DataTable`). Petrol on marker and label only (D-57). Exported from `packages/ui/src/scaffold/index.ts` and `packages/ui/src/index.ts`. | INV-62, INV-68, D-57, D-58, FE-23 |