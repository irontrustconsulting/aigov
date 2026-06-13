# Sprint hand-off — Tenant Governance Role Model & Separation of Duties

**Status going in:** design locked; see PRD **v0.2 §4.9.1**. This sprint implements it.

**Builds on:** the proven tenant auth chain (`verify_cognito_token` → `get_tenant_context` → `get_tenant_db` → `require_role`), `app/models/identity.py` (Tenant / User / Membership), and `app/models/rbac.py` (operator RBAC) as the catalogue-plus-assignment pattern to mirror.

**New versus operator RBAC:** the **SoD conflict matrix** and **tenant-scoping (RLS)**. Operators hold multiple roles freely; tenant governance roles do not.

**Sequenced before** the assessment/registration workflow, which will consume these roles at its gates.

**Part 1 of 2.** This sprint is the **additive** governance-role core — new tables and endpoints, no change to anything already running. The `membership.role` untangle and the re-pointing of existing endpoints onto governance roles are split into **`SPRINT_membership_role_untangle.md`**, sequenced immediately after (it can only run once this sprint has created the governance roles to point at).

---

## Goal / contract

A tenant admin can grant and revoke governance roles to members. The system enforces separation of duties at the point of assignment, blocks self-assignment, and keeps governance entirely separate from account administration. Tenant-scoped (org-wide) for the MVP, structured so per-object scope is a later **additive** change, not a rewrite.

## The model (reference — full detail in PRD §4.9.1)

- **1st line:** `system_owner`, `contributor` — **compose** (may be co-held).
- **2nd line:** `reviewer`, `authoriser` — **separated** (conflict).
- **3rd line:** `auditor`.
- Every cross-line pair conflicts. The **only** composable pair is `system_owner` + `contributor`.
- Admin is administrative only and confers no governance power.

---

## Work items

**1. Governance role catalogue — platform reference (no RLS).**
Table `governance_role` (`key`, `name`, `description`, `line_of_defence`). Seed via migration with the five roles above. Global reference data — like the EU AI Act seed, not tenant data. Mirror the operator `role` catalogue.

**2. SoD conflict matrix — platform reference (no RLS).**
Table `governance_role_conflict` (`role_a_id`, `role_b_id`) — one row per conflicting **unordered** pair (use a canonical ordering, e.g. `role_a_id < role_b_id`, to avoid duplicate symmetric rows). Seed the **9** conflict pairs — every pair except `system_owner`+`contributor`. This table *is* the SoD policy; keeping it as data, not code, is deliberate.

**3. Governance role assignment — tenant data (RLS).**
Table `governance_role_assignment` (`id`, `tenant_id`, `membership_id`, `governance_role_id`, `granted_by_membership_id` NULL, `granted_at`). Under RLS scoped by `app.current_tenant`, like other tenant tables. Unique `(tenant_id, membership_id, governance_role_id)`.
**Object-scope seam:** this table is the *single* home of governance grants — never on `membership.role`. The future object-scoped move is *only*: add a nullable `scope_id` (NULL = tenant-wide, preserving every existing grant). Do **not** add it now; just don't foreclose it.

**4. SoD enforcement — one scope-aware function.**
A single service function (e.g. `assert_governance_assignable(membership, role, db)`) that loads the member's current governance roles and rejects the candidate if it conflicts (per the matrix) with any held role → domain error → **409/422**. This is the **only** locus of SoD logic, so object-scope later means generalising this one function. Separately, block self-assignment: the acting admin's membership may not be the subject → **403**. App-layer enforcement is the baseline; a DB-level guard (trigger/exclusion) is optional hardening, deferred.

**5. Role-management endpoints (admin surface).**
- `GET` catalogue (roles + conflicts, for the UI).
- `GET` a member's / the tenant's assignments.
- `POST` assign role to a member — `require_role("admin")`, runs the SoD check, blocks self-assignment, writes audit.
- `DELETE` revoke — `require_role("admin")`, writes audit.
All on the RLS-scoped tenant session. (Governance roles are *assignable* here; making them *gate actions* on existing endpoints is the untangle sprint.)

**6. Audit.** Each grant/revoke → existing `audit_event` (actor membership, subject membership, role, action, timestamp). WKF-8.

**7. Tests.**
- SoD unit: each conflict pair rejected; `system_owner`+`contributor` allowed; self-assign blocked.
- Endpoint integration: admin assigns non-conflicting ✓; conflicting → 409; self-assign → 403; non-admin → 403; cross-tenant isolation via RLS.

---

## Constraints (the soundness that must survive)

- Governance grants live **only** in the assignment table — never on `membership.role` (which Sprint 2 reduces to purely administrative).
- SoD lives behind **one** scope-aware function — the object-scope seam.
- Catalogue + matrix = platform reference (no RLS, migration-seeded); assignments = tenant data (RLS).
- Admin confers no governance power; assigning roles is the only admin→governance touch; self-assignment is blocked.
- Governance roles are read from the DB assignment table, never from token claims.

## Acceptance

- Admin grants `system_owner`→A and `reviewer`→B; granting `reviewer`→A (who holds owner) is rejected with a clear conflict error; `system_owner`+`contributor`→same member succeeds.
- Admin cannot grant any governance role to their own membership (403).
- Non-admin cannot reach the assignment endpoints (403).
- Cross-tenant isolation holds (RLS).
- Every grant/revoke appears in `audit_event`.

## Out of scope

- The `membership.role` → `admin`/`member` untangle and re-pointing existing endpoints (e.g. `/v1/systems`) onto governance roles — **`SPRINT_membership_role_untangle.md`**, sequenced immediately after this one.
- The gated lifecycle / state-machine engine — downstream; this sprint only supplies the catalogue it will later consume.
- Object-scoped (per-system) assignment — additive future.
- External authz engine / IGA — per the build-vs-buy call, keep in-DB now.
- Full self-service member-invite flow — see dependency.

## Dependency / decision notes

- **Testing SoD needs ≥2 members.** Provisioning creates one owner. For this sprint, seed a couple of extra memberships in dev (a tiny seed or CLI, mirroring `create-operator`) so you can assign `system_owner` / `reviewer` / `auditor` to distinct members. The full invite flow is a separate backlog sprint. Members only need to *exist* to test assignment-time SoD; their logging in to act is the later integration walk.
- **The untangle is split out** into `SPRINT_membership_role_untangle.md` and runs immediately after this sprint — decision settled. This sprint stays fully additive (touches no existing endpoint), so it lands and verifies in isolation; the untangle then re-points the existing surface onto the governance roles this sprint creates.
