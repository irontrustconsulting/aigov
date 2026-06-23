# DESIGN DOC (FINAL) · `UI-F7-PROVISION` — Operator Provisioning Console

**Status:** FINAL, review folded · plane **PLATFORM (operator)** · type: frontend feature surface + 1 durable-route promotion · **durable route delta +1** (`whoami` struck, `/platform/me` added; raw-route replace) · **schema/migration delta 0** · new app: none (`apps/operator` present, F0) · new convention **FE-13** · new decision **D-39** · depends on `UI-F0-FOUNDATION` (operator BFF, operator-pool PKCE, generic proxy, CSRF guard, shared packages), `POST /platform/provision`, `GET /platform/tenants` · brings provisioning into **`INV-49`** compliance (live gap removed; the convention stays live, N1) · honours `PLATFORM-UX` §1–2, `D-23`, `INV-1`, `INV-8`, `INV-50`, `D-37`, `D-24`.

---

## Resolved decisions

| ID | Decision | Disposition |
|---|---|---|
| **A1** | Durable operator identity endpoint | Promote `GET /platform/whoami` → durable `GET /platform/me`, re-gated **authenticated-operator-only**, response `{id, email, display_name, permissions}`. Sole backend item; `→ D-39`. |
| **A2** | Console scope ceiling / IA seed | (b) Minimal operator nav shell; provisioning surface live; the three unbuilt operator surfaces (RBAC, curation, inbox) visible-disabled as *unbuilt* placeholders. Permission-absence is a distinct axis from unbuilt (N2). |
| **A3** | `PLATFORM-UX` §3 fill protocol | Fill the provisioning-console intent into §3; the one sanctioned stable-tier touch (the doc's own fill-as-you-go), named in the canonical-update. |
| **A4** | Tenant-list affordances | Read-only list; no per-tenant mutation (no backend exists). |
| **D-39** *(new)* | Durable operator identity contract | `GET /platform/me`, authenticated-operator-only, is the operator-plane analogue of `GET /v1/me`: DB-authoritative identity + permission set for permission-aware render. Promotes the F0 `whoami` verification aid. Additive over greenfield (`D-22`); never reads authz from claims (`D-24`). |
| **FE-13** *(new)* | Operator-console permission-aware rendering | Controls for a permission the operator lacks are **absent** (not disabled); presentational only, `require_permission` is the authz authority. The platform-plane analogue of `FE-8`, grounded on `INV-8`/`D-24` (distinct from `FE-8`'s act-SoD grounding, N3). |

---

## Review disposition

| Finding | Class | Disposition |
|---|---|---|
| **B1** · list read is itself `tenant:provision`-gated; gating only the form reissues the 403 A1 removes | Blocking | **Accepted, closed.** §3.2 now branches at surface root: zero-`tenant:provision` operators issue **no** `GET /platform/tenants` and render **no** form (`DF2-5`/`DF5-7` pattern). |
| **N1** · `INV-49` is `CONVENTION`, upheld not closed | Non-blocking | **Accepted.** Reframed "closes" → "brings into compliance, gap removed." Canonical-update barred from striking `INV-49`/`D-36`. |
| **N2** · unbuilt-placeholder vs permission-absent collision | Non-blocking | **Accepted.** Third axis stated (§3.6): unbuilt → visible-disabled; permission-lacking → absent; any future permission-gated surface adopts absence. |
| **N3** · `FE-13` placement | Non-blocking | **Accepted.** `FE-13` as operator-plane permission analogue citing `INV-8`/`D-24`/`FE-8`; one-line `FE-10` cross-ref, no `FE-8` restatement. |
| **N4** · A1 is remove + add + re-gate + narrow | Non-blocking | **Accepted.** Four edits enumerated in the canonical-update item; durable-route delta `+1`, raw-route replace; `cognito_sub` dropped from the response. |
| **V-A..V-D** | Needs source verification | **Accepted, appended** to Appendix B; V-A and V-B flagged binding pre-flight. |
| `INV-50`/`D-37`, `INV-1`, `D-23`, `D-22`, `FE-7` N/A, no SoD/prohibition/schema | Clean | Noted; carried unchanged. |

---

## 1. Problem and frame

Provisioning is a platform capability that requires ongoing interactive operation, yet today it is operable only via CLI and raw HTTP. That is a live `INV-49`/`D-36` gap: a platform feature that needs interactive operation is not done until its operator UI is built. `INV-49` is a standing `CONVENTION`, not a ticket; this sprint **brings provisioning into compliance** with it (removing the live gap for that one capability), and the convention remains live, judging every later operator surface (N1).

Every other operator surface (RBAC, catalogue curation, curation-task inbox) is genuine future work needing new backend. Provisioning is the one whose backend is fully built (`POST /platform/provision`, `GET /platform/tenants`, both gated `tenant:provision`). This sprint builds its console: the first real feature surface on the F0 operator foundation, and the IA seed for the operator track.

Not tenant self-service. The console wraps `POST /platform/provision`; `POST /tenants` stays removed (`D-23`). The CLI persists as bootstrap/break-glass only.

## 2. PRESENT vs ALTER/NEW

| Element | State | Note |
|---|---|---|
| `apps/operator` (port 3001), operator BFF, operator-pool PKCE, in-memory session store (`lib/auth/in-memory-session-store.ts`, dev-only), generic proxy `app/api/proxy/[...path]/route.ts`, `Sec-Fetch-Site`/`Origin` CSRF guard | **PRESENT** (F0) | Smoke `/dashboard` only; calls `GET /platform/whoami` |
| `@irontrust/tokens` (two skins via `[data-theme]`), `@irontrust/ui`, `@irontrust/api-client`, `packages/eslint-plugin-irontrust` | **PRESENT** (F0) | Operator-plane usability of the shared client and lint rules is V-6/V-D |
| `POST /platform/provision` → `ProvisionResponse` (201); `409 AlreadyProvisioned`; gate `tenant:provision` | **PRESENT** | exact request/response/collision-key: V-1, V-2, V-3 |
| `GET /platform/tenants` → `TenantListItem[]`; gate `tenant:provision`; cross-tenant read | **PRESENT** | columns: V-2 |
| `GET /platform/whoami` → `{id, cognito_sub, email, display_name, permissions}`; gated `tenant:provision`; `TODO: remove` | **PRESENT** | struck this sprint (A1/N4) |
| `GET /platform/me` (durable identity contract) | **NEW** (A1/`D-39`) | authenticated-operator-only; `{id, email, display_name, permissions}`; sole backend item |
| `apps/operator/app/provisioning` (list + create) | **NEW** | this sprint |
| `apps/operator` nav/layout shell | **NEW** (A2) | provisioning live; unbuilt surfaces visible-disabled |
| `FE-13` operator permission-aware render primitive | **NEW** | §3.2, §3.6 |
| `PLATFORM-UX` §3 provisioning-console intent | **ALTER** (stable tier, sanctioned fill, A3) | |

## 3. Design

### 3.1 Surface topology
`apps/operator/app/provisioning` (NEW): a single dense surface, two regions, a **tenant list** (`GET /platform/tenants`) and a **provision action** (form → `POST /platform/provision`). Operator-plane register per `PLATFORM-UX` §2: information density over friendliness, operational vocabulary, no adoption layering, no prefill ladder (a tenant-thesis mechanism that does not belong here). Desktop-only workstation tool (`FE-1`).

### 3.2 Identity, permission-aware render, and the root branch (B1 closed)
The console reads the caller's operator identity and permission set once at the surface root, via the durable `GET /platform/me` (`D-39`), the platform-plane analogue of the tenant app's `GET /v1/me` (`D-24`, `FE-10`). `/platform/me` is gated authenticated-operator-only (not `tenant:provision`), so a permission-poor operator gets a 200 with a permission set, never a blanket 403.

Because `GET /platform/tenants` carries the same `tenant:provision` gate as provision (there is no list-but-not-provision operator), the branch gates **both** the list read and the form, at the root:

- **`tenant:provision ∈ permissions`:** render the list (issue `GET /platform/tenants`) and the provision form.
- **`tenant:provision ∉ permissions`:** render a permission-appropriate empty state. Issue **no** `GET /platform/tenants`. Render **no** form. This is the established "zero gated permission → issue no gated call" pattern (`DF2-5`, `DF5-7`).
- **Unauthenticated:** handled upstream by the F0 BFF middleware (login redirect); never reaches the branch.

The backend keeps `require_permission("tenant:provision")` on both routes as the authz authority (`INV-8`, `D-24`); the client branch is presentational only and never substitutes for it (`FE-13`).

### 3.3 Provision flow
Form captures the `ProvisionRequest` structured fields (exact set and validation: **V-1**): org name, slug, owner email, owner name. Client-side validation mirrors server constraints (slug format, email shape) to fail early; the server remains authority. Submit posts through the operator BFF proxy (`INV-50`, never browser→API direct). Outcomes:

- **201:** render `ProvisionResponse` (`tenant_id`, `owner_id`; exact shape V-2), then invalidate and refetch the list (`FE-9`).
- **409 `AlreadyProvisioned`:** distinct "already provisioned" state, not a generic error; the collision key (V-3) drives which field is flagged.
- **403:** should not occur for a permission-gated caller; if it does, treat as a stale-permission signal, refetch `GET /platform/me`, re-branch (§3.2). This path is correct only because the §3.2 branch exists.

Every successful provision is attributable on the platform audit plane (`PLATFORM-UX` §2). The console relies on `provision_tenant(source="http")` staging a `PlatformAuditEvent` (**V-4**; `platform_audit_event` confirmed present, `DATA-MODEL`); the console adds no audit of its own.

### 3.4 Tenant list
`GET /platform/tenants`, read-only this sprint (A4). Columns from `TenantListItem` (V-2). No per-tenant mutation (suspend, edit, delete); no backend exists for it. The list is the post-provision confirmation surface and the cross-tenant operator inventory.

### 3.5 Data-fetch path
Reads and the mutation route through the operator BFF proxy (`INV-50`). Whether the shared `@irontrust/api-client` is reused (its tenant-plane guards against client-supplied `tenant_id`/`provenance` are inert here, since `ProvisionRequest` carries neither) or the operator app uses a thinner local fetch is **V-6**; either way BFF-mediated. No `useLiveState`: nothing here is a lifecycle/gate/coverage/authorisation verdict, so `FE-7` does not apply, and the `no-raw-live-state-query` lint rule must not fire on these reads (**V-D**).

### 3.6 Nav shell and the unbuilt-vs-permission-absent distinction (N2)
The A2(b) nav shell renders the operator surface map. Two distinct axes govern visibility:

- **Unbuilt** surfaces (RBAC, curation, inbox) render **visible-disabled** ("not yet available"): roadmap signalling, with no capability behind the row, shown to every operator.
- **Permission-lacking** controls render **absent** (`FE-13`): the provisioning nav entry is present iff `tenant:provision ∈ permissions`; for a permission-poor operator it is absent, and the main pane shows the §3.2 empty state.

Forward rule (binds future operator sprints): when an unbuilt surface is built and is itself permission-gated, its nav entry adopts `FE-13` absence, never a greyed row, so a real capability is never leaked behind a visible-disabled placeholder.

## 4. Conventions and invariants this sprint touches or adds

1. **`INV-49`** (CONVENTION) — provisioning brought into compliance; the convention stays live (N1). Not struck.
2. **`INV-50`** (CONVENTION) — upheld: all operator browser→API via the operator BFF; no token in browser.
3. **`INV-1`** — upheld: operator origin only, operator pool only, no tenant face.
4. **`INV-8`** — upheld: operator authority is permission-through-role; the console gates on permissions, the backend enforces them.
5. **`D-24`** — upheld: three authz layers unconflated; permissions read DB-authoritative via `/platform/me`, never from claims.
6. **`FE-13`** (CONVENTION, new) — operator-console permission-aware rendering; controls for an unheld permission are absent, presentational only, `require_permission` is authority. Cites `INV-8`, `D-24`, `FE-8`, `PLATFORM-UX` §2. Lives in `FRONTEND.md` (FE register), with a one-line `FE-10` cross-ref (N3).

No `DB` or `CODE` invariant is added; `INVARIANTS.md` and `DATA-MODEL.md` are untouched (schema delta 0; `FE-13` is a frontend convention, not an `INV-n`).

## 5. Out of scope (named)
Operator RBAC management UI; catalogue/reference curation; curation-task inbox; per-tenant mutation (suspend/edit/delete); operator self-management; persistent (non-in-memory) operator session store (the F0 MVP in-memory store stands until a dedicated hardening sprint). These are the rest of `PLATFORM-UX` §3 and remain future operator sprints.

---

## Appendix A — Open decisions (resolved)
A1–A4 resolved in the Resolved-decisions table above. No open decisions remain at execution time. Flip A2 to a provisioning-only surface (no shell) if the IA seed is unwanted; the rest of the design is unaffected.

## Appendix B — Source-verification register (verify live before execution; `D-21`)

| ID | Item | Where | Binds | Pre-flight |
|---|---|---|---|---|
| **V-A** | Does `operator_authz` expose an authenticated-operator-only dependency (bare `CurrentOperator`, no `require_permission`)? `whoami.py` only resolves the operator *through* `require_permission("tenant:provision")`; `ARCHITECTURE` §3 documents only `require_permission(...)`. | `app/auth/operator_authz.py` | A1 feasibility; if absent, WI-1 grows a sub-item (add the dependency) | **BINDING** |
| **V-B** | Byte-exact permission-key string as it appears in the returned `permissions` set. Source: `require_permission("tenant:provision")`; `API-ROUTES` writes the gate `operator:tenant:provision`. | `app/auth/operator_authz.py`, `permission` seed | `FE-13` match + the B1 branch gate on byte-for-byte equality; a wrong literal silently never matches | **BINDING** |
| **V-1** | `ProvisionRequest` exact fields + validation (slug format/uniqueness, email, owner_name required) | `app/schemas/platform.py` | the form | |
| **V-2** | `ProvisionResponse` + `TenantListItem` exact fields (id, org_name, slug, created_at, owner, status?) | `app/schemas/platform.py` | success view, list columns | |
| **V-3** | `409 AlreadyProvisioned` trigger key (slug vs org collision) | `app/services/provisioning.py` | conflict UX, which field is flagged | |
| **V-4** | `provision_tenant(source="http")` stages a `PlatformAuditEvent` | `app/services/provisioning.py` | the attribution claim (§3.3) | |
| **V-5** | Confirm only `/platform/whoami` exists (gated `tenant:provision`, `TODO: remove`); no durable `/platform/me` | `app/routers/platform/`, `API-ROUTES` | A1, the backend item | |
| **V-C** | Reconcile STATE "operator identity endpoint**s**" (plural) against `API-ROUTES` (only `/platform/whoami`); confirm no second identity route A1 should subsume | `app/routers/platform/`, `STATE`, `API-ROUTES` | reinforces V-5 | |
| **V-6** | How `apps/operator` smoke surface fetches (shared `@irontrust/api-client` vs operator-local); whether tenant-plane guards are inert for operator calls | `apps/operator/...`, `packages/api-client` | the data-fetch path (§3.5) | |
| **V-D** | Confirm `packages/eslint-plugin-irontrust` `no-raw-live-state-query` / `no-client-tenant_id` rules are route/content-scoped, not blanket, so they do not fire on operator provisioning fetches | `packages/eslint-plugin-irontrust` | §3.5; a blanket rule would reject the operator fetch | |
| **V-7** | `apps/operator` current shell: layout, nav, session-bootstrap, logged-in boundary beyond smoke `/dashboard` | `apps/operator/app/` | where the surface slots in (A2) | |
| **V-8** | Operator-pool app-client supports auth-code+PKCE web flow end-to-end; a genesis/dev operator with `tenant:provision` exists or is seedable | `infra/cognito_operator.tf`, operator seed path | being able to load and exercise the console | |