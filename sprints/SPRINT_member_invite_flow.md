# Sprint: Tenant-Admin Member Creation

## 1. Sprint title

**Tenant-admin creation of tenant members (additive backend increment).**

A tenant admin creates a new tenant user — a Cognito identity plus a tenant membership with the non-admin `UserRole` and no governance roles — via a `provision_member` service that runs **on the tenant-scoped RLS role** and reuses `provision_tenant`'s Cognito → DB → commit + compensation *choreography* (not its privilege). Cognito owns the invite email and acceptance; governance-role assignment is the existing endpoint.

---

## 2. Status going in / context

**On the ground (reuse the pattern, not the privilege):**

- `provision_tenant(...)` in `app/services/provisioning.py` — the **choreography template**. It runs on `ProvisionerSessionLocal` (`irontrustai_provisioner`, `BYPASSRLS`) **only because it runs before any tenant exists**. Reusable parts: the ordering (Cognito `AdminCreateUser` → identity rows → commit), the **compensation** (best-effort Cognito delete on commit-failure-after-Cognito), and the Cognito helpers. Its `BYPASSRLS` role is **not** reused here.
- The application DB role: `LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE **NOBYPASSRLS**`, with blanket `SELECT/INSERT/UPDATE/DELETE` on all `public` tables (and matching default privileges). **Isolation is enforced entirely by RLS policies, not by table grants.** The role already has INSERT on `app_user`.
- Tenant auth/context chain: Cognito `custom:tenant_id` (immutable) → `TenantContext`; `get_tenant_db` / `SessionLocal` as the RLS app role.
- Models `Tenant`, `User` (`app_user`: `cognito_sub`, `email`, `display_name`; **global, non-RLS**), `Membership` (`user_id`, `tenant_id`, `role: UserRole`); the governance assignment layer and `POST/GET/DELETE /v1/governance-roles/assignments`.
- Audit trails on **both** the platform plane (`record_platform_event`) and the tenant plane.

**Not redoing:** Cognito flows, RLS, governance tables/endpoints, the `membership.role` untangle, or `provision_tenant` itself.

**Privilege boundary (the correction that shapes this sprint):** the tenant admin is tenant-scoped and touches **no** platform DB privilege. Member creation runs on the **RLS app role** with the admin's tenant context; the membership insert is RLS-checked (`WITH CHECK tenant_id = current_tenant`). The only platform-plane resource the flow reaches is **Cognito**, mediated — the app calls `AdminCreateUser` with `custom:tenant_id` pinned to the admin's tenant.

**Where it sits — step 3 of onboarding:** operator provisions tenant + first admin (1–2, done) → **[this sprint] tenant admin creates members** → member accepts via Cognito (4, no app code) → admin assigns governance roles via the existing endpoint (5, no app code).

---

## 3. Goal / contract

A tenant admin can create a tenant user: a **Cognito record** (Cognito sends the invite email) and an **active membership in the admin's own tenant**, `role = UserRole.MEMBER`, **no governance roles**. Creation is atomic with the same orphan-free / compensation guarantees as provisioning, runs entirely on the tenant-scoped RLS role (no platform DB privilege), and is audited on the tenant plane. The member holds zero governance power until the admin assigns roles via the existing endpoint.

---

## 4. Domain model / rules

- **Membership** (existing): created under RLS, scoped to the admin's `tenant_id` (enforced by RLS `WITH CHECK`, not just application code), `role = UserRole.MEMBER`, no governance roles.
- **`app_user`** (existing, **global, non-RLS** — no `tenant_id`): created with the Cognito `sub`; the membership FK requires it first. The app role already has INSERT. Email indexed but not DB-unique; **Cognito is the authority on uniqueness**. Because `app_user` is non-RLS and the role has blanket DML, any read of it must be **driven from `membership`** (RLS-scoped), never queried bare.
- **Cognito**: `AdminCreateUser` with `custom:tenant_id` = the admin's tenant (immutable) and `email_verified = "true"` (admin-vouched). Pins the user to one tenant; an existing email elsewhere fails as `UsernameExistsException`.
- **No new invitation entity**; "invited but not accepted" is **derived from Cognito status** (`FORCE_CHANGE_PASSWORD` vs `CONFIRMED`).
- **Source of truth:** `membership` = belonging; Cognito = identity + acceptance; `governance_role_assignment` = roles (untouched).
- **Invariant:** a created member has a membership (`UserRole.MEMBER`, zero governance roles) **or nothing is persisted**.

---

## 5. Work items

**WI-1 — Shared Cognito helpers.**
Extract `_create_cognito_*` / `_delete_cognito_*` from `provisioning.py` into a shared module so `provision_tenant` and `provision_member` use one copy (parameterise attributes). Refactor `provision_tenant` to consume them — no behavioural change.

**WI-2 — `provision_member` service (tenant-scoped, owns its transaction).**
`provision_member(tenant_id, email, name, actor, source) -> user_id`. Runs on a **tenant-scoped session** — `SessionLocal` as the RLS app role with `app.current_tenant` pinned to `tenant_id` — and **owns its own transaction** (the request-scoped `get_tenant_db` commits at request end and can't express the compensation). Choreography, from `provision_tenant` minus the tenant insert and minus `BYPASSRLS`:
1. Pre-check: reject if a membership for this email already exists in `tenant_id` → `AlreadyProvisioned`.
2. Cognito `AdminCreateUser` (shared helper), `custom:tenant_id = tenant_id` immutable, `email_verified = "true"` (admin-vouched). `UsernameExistsException` → `AlreadyProvisioned`.
3. INSERT `app_user(cognito_sub=sub, …)` directly (the app role already has the grant), flush; INSERT `Membership(user_id, tenant_id, role=UserRole.MEMBER)` under RLS.
4. Stage tenant-plane audit; commit.
5. Commit-failure-after-Cognito → best-effort delete the Cognito user (shared helper), re-raise.

**WI-3 — Create-member endpoint (admin).**
`POST /v1/members` (or house route), `require_role("admin")`, request RLS session for authorisation. Body `{ email, name }`. **`tenant_id` pinned from `ctx.tenant_id`, never the body.** Calls `provision_member(tenant_id=ctx.tenant_id, …, actor=<acting admin>, source="api")`. `AlreadyProvisioned` → `409`. Returns `user_id`/`membership_id`.

**WI-4 — Member listing with accept status.**
Extend the existing tenant-member list (or add `GET /v1/members`). **Drive the query from `membership` (RLS-scoped), joined to `app_user`** — never a bare `app_user` query, since `app_user` is non-RLS and the role can see all of it. Surface Cognito-derived accept status; paginate per house convention.

**WI-5 — Audit (tenant plane).**
`provision_member` records a **tenant-plane** event (the tenant analogue of `record_platform_event`), action e.g. `CREATE_MEMBER`, actor = the acting admin. Not the platform plane.

**WI-6 — Tests.** See §12.

*Deferred follow-ons: resend-invite, remove/deactivate-member.*

---

## 6. Constraints / non-negotiables

- **The tenant admin stays on the tenant-scoped RLS role.** Member creation uses **no** `BYPASSRLS` / platform DB privilege. The membership insert is RLS-checked.
- **The only platform-plane touch is Cognito**, mediated via `AdminCreateUser` with `custom:tenant_id` pinned to the admin's tenant.
- **`tenant_id` is pinned from the authenticated admin context, never the body** — additionally backed by RLS `WITH CHECK` on the membership insert.
- **`app_user` reads are driven from `membership` (RLS), never bare.** The blanket grant + non-RLS `app_user` means a bare query would cross tenants.
- **Replicate the orphan-free ordering and compensation** (Cognito → DB → commit; best-effort Cognito delete on commit failure). The service owns its own (tenant-scoped) transaction to express this.
- `require_role("admin")`; new member gets `UserRole.MEMBER` and **no governance roles**.
- `custom:tenant_id` immutable; Cognito remains the uniqueness authority.
- **Cognito owns invite email + acceptance** — no app-side token, `/accept` endpoint, or invitation table.
- Audit on the **tenant** plane; governance untouched; no JWT-sourced authority.

---

## 7. Acceptance criteria

1. Admin `POST` create-member (new email) → `201`; membership active in the admin's tenant, `role=UserRole.MEMBER`, **no governance roles**; `app_user` created with the Cognito `sub`; invite email sent; `CREATE_MEMBER` audited on the tenant plane.
2. The created member can immediately be granted a governance role via the existing `POST /v1/governance-roles/assignments`.
3. Non-admin → `403`.
4. Email already a member of this tenant → `409` (pre-check).
5. Email already a Cognito user (incl. another tenant) → `409` via `UsernameExistsException`.
6. **Cognito failure → nothing persisted** (no orphan `app_user`/membership).
7. **Commit failure after Cognito → Cognito user best-effort deleted** (or left for the reconciler), error surfaced; no half-created member.
8. The membership insert is **rejected by RLS** if `tenant_id` ≠ the session's tenant (proves the insert runs under RLS, not bypass).
9. Member listing returns **only the caller's tenant members** (driven from RLS-scoped `membership`), never global `app_user` rows; status shows `pending` until Cognito confirmation, then `accepted`.
10. Cross-tenant: admin in A cannot create a member in B; `tenant_id` from context, body `tenant_id` ignored.

---

## 8. Out of scope

- App-side invitation token / accept endpoint (Cognito owns it).
- Governance-role assignment (existing endpoint).
- `membership.role` untangle.
- Multi-tenant identity / adding an existing user to a second tenant (blocked by immutable `custom:tenant_id` + Cognito uniqueness).
- `app_user`-level isolation hardening (pre-existing; it is non-RLS by design — this sprint only ensures its reads are membership-driven).
- Resend-invite, remove/deactivate-member (follow-on).
- Approval gates; UI.

---

## 9. Dependencies / decision notes

- **Privilege boundary (decided):** member creation runs on the tenant-scoped RLS app role with its own transaction, **not** `ProvisionerSessionLocal`.
- **`app_user` insert (resolved):** the app role already holds blanket DML on `public` (incl. `app_user`), so insert directly — no helper or new grant.
- **`email_verified` (decided):** `"true"` — admin-vouched, mirroring provisioning's operator-vouched stance (receiving the Cognito invite proves control of the address).
- **Role value:** `UserRole.MEMBER`; confirm the enum member name in `app.models`.
- **Accept status** derived from Cognito (recommended single source of truth).
- **Conflict semantics** mirror `provision_tenant`: pre-check + Cognito uniqueness → `AlreadyProvisioned` → `409`.

---

## 10. Implementation contract

| Method | Path | Auth | Body | Success |
|---|---|---|---|---|
| POST | `/v1/members` | admin (RLS) | `{ email, name }` | `201 { membership_id, user_id, status }` |
| GET | `/v1/members` | admin (RLS) | `?status=&limit=&cursor=` | `200` members + derived accept status |

**Errors:** `403` non-admin; `409` existing member / existing Cognito user. `tenant_id` always pinned from context.
**Service:** `provision_member(tenant_id, email, name, actor, source)` on a tenant-scoped session it owns; Cognito → DB → commit with compensation; tenant-plane audit.
**Reuse:** shared Cognito helpers; `AlreadyProvisioned`; the ordering/compensation discipline (not the provisioner role).
**Source of truth:** `membership` (belonging), Cognito (identity + accept), governance untouched.

---

## 11. Execution protocol

1. Read the full sprint **and `app/services/provisioning.py`** before acting.
2. Plan mapped to WI-1…WI-6 before coding.
3. Extract shared Cognito helpers (WI-1), refactoring `provision_tenant` without behavioural change.
4. Implement `provision_member` (WI-2) on the **tenant-scoped** role, mirroring ordering/compensation exactly → endpoint (WI-3) → membership-driven listing (WI-4) → tenant audit (WI-5) → tests (WI-6).
5. Reuse the choreography, not the privilege; preserve every §6 constraint — especially RLS-role-only, `tenant_id`-from-context, membership-driven reads, and the compensation path.
6. Validate per §12 before declaring completion; report results.

---

## 12. Validation protocol

**Coverage:** create success / authz (`403`) / conflict (`409`, pre-check and Cognito); the **two failure-ordering paths** (Cognito-fails → nothing persisted; commit-fails-after-Cognito → Cognito user removed/swept, error surfaced); the **RLS-rejects-wrong-tenant** insert (criterion 8); the **membership-driven listing** returning only the caller's tenant (criterion 9); handoff to the governance endpoint; cross-tenant isolation; context-over-body `tenant_id`.

**Constraint checks (explicit):**
- Member creation uses the RLS app role, **not** `ProvisionerSessionLocal` / `BYPASSRLS`; the membership insert is RLS-checked.
- The only platform-plane call is Cognito, with `custom:tenant_id` pinned and immutable.
- `tenant_id` is taken from authenticated context, never the body.
- `app_user` is read membership-driven, never bare.
- Cognito helpers are shared, not duplicated; `provision_tenant` behaviour unchanged.
- New member has `UserRole.MEMBER` and zero governance roles; audit on the tenant plane.

**Reporting:** report the plan-to-work-item mapping, test results per acceptance criterion (including both failure-ordering paths, the RLS-rejection test, and the membership-driven listing test), and the constraint checks. Unverified criteria or unreported constraint checks mean the sprint is **not** complete.
