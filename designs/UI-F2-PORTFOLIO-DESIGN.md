# UI-F2-PORTFOLIO — Inventory / Dashboard + Whose-court · design doc (v0.2, post-review)

**Status:** design-mode · second tenant feature surface after `UI-F1-INTAKE` · tenant plane only · **read-only** (sole mutation deferred, A1) · **zero backend / zero migrations / zero new routes / no `DATA-MODEL` change — conditional on B1/V-2** (`D-22`) · grounds: `UX §2`/`§5`, `FRONTEND FE-1..10`, `DOMAIN §7`, `API-ROUTES.md @ UI-F1-INTAKE` HEAD · route contracts are **registry-asserted, live-confirm at execution** (`D-21`); the registry post-dates the F0-era STATE/SPRINTS · gives F1's whose-court handoff a destination · `A`-pick locked · **v0.2 folds external review B1, N1–N3, NB3–NB5, A1/A2.**

The navigational hub. `UX §5` surfaces 2 (inventory/dashboard) and 6 (whose-court) folded into one role-conditioned surface. First real consumer of `FE-7` (the portfolio is the canonical live-state read) and of the role-aware-render contract (`FE-8`/`FE-10`); promotes the `@irontrust/ui` whose-court indicator from F0 scaffold to a wired surface. `FE-5` (prefill) and `FE-6` (`If-Match`) are **dormant** (read surface; none of F2's routes accept `If-Match`).

**Zero-backend caveat (B1).** The property holds *iff* the live `blocking` vector disambiguates `REQUIRES_CONTEXT` (owner court) from reviewer-pending, **or** `SystemRollupRead` carries per-use-case `requires_context` for a client pre-branch. If neither, the B1 mitigation needs a thin rollup field and F2 is no longer strictly zero-backend. This is the binding pre-flight (V-2).

---

## Resolved decisions (surface-local)

| ID | Decision | Basis |
|---|---|---|
| DF2-1 | F2 = **portfolio landing + system drill-in (rollup)**. Pure wire-up over `GET /portfolio`, `GET /systems`, `GET /systems/{id}/rollup`, `GET /use-cases/{id}/lifecycle`, `GET /me`. No new route; schema delta conditional on B1. | `A`-pick; registry; `D-22` |
| DF2-2 | **Both faces, one surface**, role-conditioned off `GET /me` (server-authoritative roles, never claims). Adoption face = your-court + next action; assurance face = portfolio posture. Not separate routes. | `UX §2`; `D-24`; `FE-10` |
| DF2-3 | **Whose-court is server-computed, client-highlighted, with a `requires_context` pre-branch.** Per use case: if `requires_context` → court = `system_owner` (answer residual context questions), **without** consulting `blocking` (which inherits the `PENDING_REVIEW → reviewer` mislabel, B1); else court = `blocking.responsible_party` (or none). Client highlights "your court" by matching the resolved party against the caller's `/me` roles. Presentational only; backend stays the authz authority. Names the **party/role**, never an individual (`D-25`). | B1; `D-9`; `FE-8`; `INV-28`; `D-4`; `D-25` |
| DF2-4 | Portfolio / rollup / lifecycle reads are **live-state** → routed through `useLiveState` (`staleTime 0`). Authority read from computed `live_state`/`blocking`, never row-existence. (No mutation in F2, so no refetch-after-write path — A1.) | `FE-7`; `INV-25`, `INV-32` |
| DF2-5 | An **admin-only caller** (zero governance roles) is branched **proactively** off `GET /me`, fetched first; the `gov:ALL` rich feed is **never issued** for them (not issue-then-catch — a swallowed 403 is indistinguishable from an expired-session/misconfig 403, NB5). The 403 is the backend safety net only. Admin-only → admin/empty state. | `DOMAIN §7`; NB5; registry gate `gov:ALL` |
| DF2-6 | **No `If-Match` anywhere in F2.** None of its routes accept it. `FE-6` dormant. | registry §5; `PAT-6`, `INV-14` |
| DF2-7 | The **review-queue surface** (`GET /assessments/review-queue` at HEAD per registry) is **out of F2 scope**, deferred. F2 surfaces the reviewer's/authoriser's pending count through the **same** whose-court mechanism and links forward; it does not build the queue UI. | scope; one whose-court mechanism (DF2-3) |
| DF2-8 | *(retired)* `re-evaluate` **deferred** out of F2 to a future use-case-detail/assessment surface. F2 is **read-only**. Keeps the first hub surface lowest-risk; B1 already loads the derivation. | A1; review lean |
| DF2-9 | **Operator console untouched.** No platform capability; `INV-49` not triggered. Tenant app only. | `INV-1`, `INV-49` |

---

## Routes consumed (registry-asserted @ `UI-F1-INTAKE` HEAD; live-confirm `D-21`)

| Method · Path | Gate | Response | Role in F2 |
|---|---|---|---|
| `GET /v1/portfolio` | `gov:ALL` | `SystemRollupRead[]` | The landing feed. One entry per system with ≥1 use case, recomputed live. `useLiveState`. |
| `GET /v1/systems` | `member` | `SystemRead[]` | Zero-use-case systems (not in `/portfolio`); empty-card merge only (A2), never a court-bearing row. |
| `GET /v1/systems/{id}/rollup` | `gov:ALL` | `SystemRollupRead` | System drill-in: use cases + states + highest tier + per-use-case `blocking`. `useLiveState`. |
| `GET /v1/use-cases/{id}/lifecycle` | `gov:ALL` | `UseCaseLifecycleRead` | Per-use-case whose-court detail; `blocking` = first non-advance `GateResultRead` (`responsible_party`) or `null`. `useLiveState`. |
| `GET /v1/me` | `member` | `MeRead` | Role context for the render branch + whose-court match; fetched **first** for the admin pre-branch (DF2-5). Cached (not live-state). |

**Not consumed / corrected (registry-sourced):** `GET /v1/use-cases/{id}` returns `UseCaseWithClassification` (404 if no snapshot), **not** whose-court. `POST /v1/use-cases/{id}/advance` does not exist (registry §4 — retired for auto-advance + `re-evaluate`). `GET /v1/assessments/review-queue` is the HEAD path (registry `assessments.py`), deferred (DF2-7). `POST /v1/use-cases/{id}/lifecycle/re-evaluate` (`gov:system_owner`) exists but is deferred out of F2 (A1).

---

## Role-aware render (the heart of F2)

Resolved court (DF2-3: `requires_context` pre-branch, else `blocking.responsible_party`) is matched against the caller's `/me` governance roles.

| Caller role | Sees | Your-court items (resolved party `==`) | F2 actions |
|---|---|---|---|
| `system_owner` | Their portfolio; next-action prompts | `system_owner` (answer context, create/submit assessment) | none (read-only; `re-evaluate` deferred) |
| `contributor` | Portfolio (gov:ALL read) | `contributor` — **conditional on V-2**: row exists only if `responsible_party` actually emits `contributor`; else dropped (NB4) | none |
| `reviewer` | Portfolio posture | `reviewer` (awaiting review/sign-off) → links toward the deferred queue | none |
| `authoriser` | Portfolio posture | `authoriser` (vendor/product approval, authorisation/ATO) | none |
| `auditor` | Portfolio posture, read-only | **none** (3rd-line, never a blocking party) | none |
| admin-only (no gov role) | Admin/empty state, rich feed never issued (DF2-5) | n/a | none |

The "your court" highlight is the `FE-8` visual correlate (`UX-5`): presentational only, backend remains the authority.

---

## Data-fetching split (`FE-9` / `FE-7`)

- **Landing route:** RSC server-fetch `GET /me` **first** (admin pre-branch, DF2-5); for governance callers, server-fetch `GET /portfolio` and hydrate, then client `useLiveState` (`staleTime 0`) — never a cached query (`FE-7` lint: no-raw-live-state-query). Tokens server-side (`FE-2`).
- **Drill-in:** `GET /systems/{id}/rollup` and `GET /use-cases/{id}/lifecycle` via `useLiveState`.
- **`/me`:** cached query (role context, not a live-state verdict).
- All reads through the BFF proxy (`FE-9`); the client never sets `tenant_id` (`INV-3`).

---

## Schema delta

**Conditional (B1/V-2).** Default expectation: none — pure wire-up (`D-22`). If V-2 shows `blocking` does not disambiguate `REQUIRES_CONTEXT` **and** `SystemRollupRead` does not carry `requires_context`, a thin additive rollup field is required and this line becomes a one-field `[ALTER]` on the rollup projection (no table change). Resolve V-2 before asserting zero-delta.

---

## Invariants honoured (F2-binding, cross-ref)

1. **F2-1** No token in the browser; every read via the plane BFF. → `INV-50`, `D-37`, `FE-1`/`FE-2`.
2. **F2-2** Live-state discipline: portfolio/rollup/lifecycle non-cacheable; authority from computed `live_state`/`blocking`, never row-existence. → `INV-25`, `INV-32`, `FE-7`.
3. **F2-3** SoD-legible whose-court: the `requires_context` pre-branch prevents the owner-context-pending case reading as reviewer court (B1); your-court highlight is presentational, backend authoritative. → `D-9`, `INV-28`, `D-4`, `D-24`, `FE-8`, IXN-4.
4. **F2-4** Roles from `GET /me`, never token claims. → `D-24`.
5. **F2-5** F2 renders no actor identity (party/role only), so it **never enters** the membership-join actor path — `INV-2`/`INV-34` are **not engaged** (the real content of the `D-25` avoidance). → `D-25`; (`INV-2`/`INV-34` not engaged).
6. **F2-6** `tenant_id` never client-supplied. → `INV-3`.
7. **F2-7** No `If-Match` on any F2 route. → registry §5, `PAT-6`, `INV-14`.
8. **F2-8** Tenant plane only; operator console untouched. → `INV-1`, `INV-49`.

---

## Appendix A — decisions (resolved at review)

- **A1 · `re-evaluate` — DEFER (resolved).** Out of F2; F2 is read-only. Moves to a future use-case-detail/assessment surface. Rationale: sole mutation, and B1 already loads the derivation; deferring preserves the lowest-risk hub property.
- **A2 · Zero-use-case systems — SHOW with guard (resolved).** Merged from `GET /systems`, rendered as a distinct "register a use case" empty card (`UX §4` coverage nudge), **excluded** from the whose-court derivation input (no `blocking` vector). The merge must not feed the court computation.

---

## Appendix B — source-verification register (`§0` pre-flight, `D-21`)

Route method/path/gate/response are registry-asserted; field shape lives in `app/schemas/*.py` (code authoritative) / `packages/api-client/src/contracts/`. Confirm live before contract types land. **V-2 is binding** — it gates B1 and the zero-backend property.

- **V-1** `SystemRollupRead` shape: per-use-case entries, `state`, highest tier, per-use-case `blocking`; **and whether it carries per-use-case `requires_context`** (the B1 pre-branch input).
- **V-2 · BINDING** Does the live `blocking`/`GateResultRead` for a `REQUIRES_CONTEXT` use case emit **`system_owner`** court, or inherit the `PENDING_REVIEW → reviewer` mislabel (B1)? Also: the exact `responsible_party` field name and its full value vocabulary, and **whether `contributor` is ever emitted** (NB4 — drives the conditional render row). Outcome decides: (a) emits owner → no pre-branch, zero-backend holds; (b) mislabels but rollup carries `requires_context` → client pre-branch, zero-backend holds; (c) neither → thin rollup field, non-zero-backend.
- **V-3** `MeRead`: governance roles exposed as a list usable for the render branch + match (from `governance_role_assignment`, `D-24`).
- **V-4** `SystemRead` shape: sufficient for a zero-use-case empty card (A2).
- **V-5** Gates `gov:ALL` on `GET /portfolio` and `GET /systems/{id}/rollup` (the entire admin pre-branch premise, DF2-5/N3). Registry-asserted `gov:ALL`; confirm live.
- **V-6** `GET /v1/use-cases/{id}/lifecycle` existence + gate + `GateResultRead`/`blocking` fields (N1). Registry-asserted (`gov:ALL`, `lifecycle.py`); confirm live.
- **V-7** Post-F1 `FE-n` and `D-n` live ceilings (the visible mirror is pre-F1, so ceilings are **not** `FE-10`/`D-37`) so the canonical update takes the **next free ids after F1's**, no collision with F1's `FE-11`/`FE-12`. Also whether F1 resolved the `FE-3` token palette/type-scale (F2 consumes, never re-resolves), the F0 authenticated-landing route name, and the current `@irontrust/ui` whose-court indicator state.
- **V-8** `GET /portfolio` "≥1 use case" filter behaviour; resolve A2 against it.

If any live contract disagrees with the registry, **the code wins** and the registry is stale (`D-21`); flag an `API-ROUTES.md` correction in the canonical update.