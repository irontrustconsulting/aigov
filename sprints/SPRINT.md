# Sprint: Platform-Operator Provisioning Plane

**Status:** Planned
**Starting point (2026-06-04):** Tenant provisioning is complete end to end — `provision_tenant()` core, admin CLI (`python -m app.cli.admin`: `provision`, `list-tenants`), a dedicated `provisioner` DB role (`BYPASSRLS`; `INSERT`/`SELECT` on `tenant`/`app_user`/`membership` only), the `tenant` table under RLS, and the self-service tenant endpoints removed.

## Goal

A **platform operator** — IronTrust staff, not a member of any tenant — can authenticate and provision a tenant over HTTP, and every provisioning action is attributed and audited.

When this sprint closes there is nothing obvious left before the provisioning story is "done": a working internal console path exists, operators have a real identity, and there is an audit trail of who did what.

## Terms

- **Tenant plane** — the customer-facing application. A customer org and its users; everything scoped by RLS.
- **Platform plane** — the internal control layer. Where tenants get created and managed.
- **Operator** — a person on the platform plane (IronTrust staff). Belongs to no tenant. Today the only operator is whoever runs the CLI; after this sprint, an operator can also act through an HTTP console.

## Authorization model (three layers, kept separate)

Platform access is built from three distinct layers. Conflating any two of them is the main design risk.

**1. DB roles (PostgreSQL) — coarse, few.** Connection credentials describing what a *connection* may touch. Never one per business permission — that is an anti-pattern (secret sprawl, and Postgres can't see which operator sits behind a pooled connection). For this plane:

- `irontrustai_provisioner` — unchanged. The narrow tenant-creation write path only (`INSERT`/`SELECT` on `tenant`/`app_user`/`membership`), plus `INSERT` **only** on the audit table. Console CRUD must not leak into it.
- `irontrustai_platform` — **new**. The admin consoles' connection: read/write on the platform-management tables, `BYPASSRLS` where a table spans tenants. May later split into `_ro`/`_rw` so reporting can't write. This is the *whole* DB-role growth story — it does not expand per feature.
- `irontrustai_admin` — unchanged. Migrations only (Alembic).

**2. Operator identity (Cognito) — authN.** The operator pool answers "who is this person", nothing more. No `custom:tenant_id` (operators aren't tenant members); authorization is **not** carried in Cognito attributes.

**3. Application RBAC — fine-grained, grows freely.** What a given operator may do, enforced in the app. Each operator has a set of permissions stored as **data** in the DB (against an `operator` record), mirroring how `membership.role` works tenant-side. Each platform route declares its requirement — `require_permission("tenant:provision")`, `require_permission("plan:write")`, and so on — checked after `get_current_operator` establishes identity. Adding a discriminated action later is *data plus one line*, not a schema or role change.

Why this shape: least privilege from day one (an operator holds only granted permissions, never a superuser), and the permission catalogue grows as consoles are built without re-architecture. **This sprint builds the seam and defines exactly one permission (`tenant:provision`); it does not enumerate future roles.**

Per-table note for later: platform-management tables split into *global* (no `tenant_id`, no RLS) and *per-tenant platform data* (`tenant_id`, possibly RLS) — the latter is why `irontrustai_platform` needs `BYPASSRLS`. Tag each table when designing its grants.

## In scope — critical path

Built in order; each item depends on the one above it.

### 1. Operator Cognito pool (infra)
Stand up a **second** user pool, separate from the customer pool, with its own app client; MFA on. Add config/env for its pool ID, region, and client ID. Authored in **Terraform** (declarative, in-repo, reproducible) rather than the console. The pool only does authN — no `custom:tenant_id`, no role attributes.
**Done when:** the pool exists via `terraform apply` and its identifiers are wired into config.

### 2. Operator bootstrapping (CLI)
A `create-operator` command (`python -m app.cli.admin create-operator`) using boto3 `AdminCreateUser` against the **operator** pool, and creating the matching `operator` record with its granted permissions. Onboards the first operator and solves the chicken-and-egg: authenticated by possession of credentials in a trusted shell, like `provision`. Creating operators is a credential-gated CLI capability, held by no operator permission. The first run is the genesis bootstrap — no prior operator to attribute it to — logged as a system event (see item 6).
**Done when:** the command creates the Cognito user, creates the `operator` record with permissions, and sends the invite.

### 3. Operator token verification (authN)
A JWKS verifier for the operator pool (distinct issuer/audience from the tenant verifier) plus a `get_current_operator` FastAPI dependency. **Security-critical:** discriminate by issuer/pool so a tenant token can never satisfy operator auth, and an operator token can never satisfy tenant auth. The two planes must not bleed into each other.
**Done when:** `get_current_operator` accepts a valid operator token and rejects tenant tokens and unauthenticated callers.

### 4. Operator record & permission enforcement (authZ / RBAC seam)
An `operator` table (Cognito sub, email, status) with permissions stored as **data**, and a `require_permission(...)` dependency that loads the caller's permissions and checks the route's requirement after `get_current_operator`. Permissions are data, not hardcoded role checks — this is the seam the whole platform RBAC story hangs off. This sprint defines exactly one: `tenant:provision`.
**Done when:** `require_permission("tenant:provision")` allows an operator holding it and rejects (403) one who does not.

### 5. Platform provisioning endpoint
`POST /platform/provision` on a dedicated platform router, gated by `get_current_operator` + `require_permission("tenant:provision")`, taking the full input (org name, slug, owner email, owner name) and calling the existing `provision_tenant()`. Same core, additional doorway — not a rewrite. Also relocate the cross-tenant read as `GET /platform/tenants` behind the same gate (replacing the CLI-only `list-tenants` reach, or sitting alongside it).
**Done when:** an operator with `tenant:provision` can provision over HTTP, producing the same tenant + owner + membership the CLI does.

### 6. Operator-action auditing
Attribute every privileged action to a **verified** operator — never a generic source, never a self-asserted string. Audit record per action: **actor** (verified operator sub + email), **action** (`PROVISION_TENANT`, `CREATE_OPERATOR`), **target** (tenant id/slug or operator email), **timestamp**, **outcome**. HTTP takes the actor from the verified token; the CLI `provision` path authenticates the running operator against the pool, so its actor is verified too. **Append-only:** the writer holds `INSERT` only (no `UPDATE`/`DELETE`). The sole exception is the genesis bootstrap (item 2), logged as a `system` event because no operator exists yet.
**Done when:** every provision (HTTP and CLI) and operator creation writes an append-only audit row with a verified actor, except the genesis bootstrap (system event).

### 7. Tests
- Operator token accepted on platform routes; tenant token and unauthenticated requests rejected.
- Operator token rejected on tenant routes (cross-plane isolation, both directions).
- `require_permission` allows a permitted operator and returns 403 for an unpermitted one.
- End-to-end HTTP provision creates tenant + owner + membership identically to the CLI.
- Append-only audit row written for HTTP and CLI provisions, each with a verified actor.

## Decisions settled

- First operator onboarded via the `create-operator` CLI command (no HTTP bootstrap).
- Separate Cognito pool for operators (authN only; no role attributes), provisioned via **Terraform**, MFA on from day one.
- New route `POST /platform/provision`; the old `POST /tenants` is **not** revived.
- Same FastAPI app, separate platform router (not a separate service) for now.
- Sprint boundary runs through auditing (item 6), not just the endpoint.
- **Authorization is three-layered** (see *Authorization model*): coarse DB roles, Cognito for authN, application RBAC for fine-grained per-action permissions. Fine-grained discrimination is **never** done via Postgres roles.
- **DB roles:** `irontrustai_provisioner` stays narrow (+ append-only `INSERT` on audit); new `irontrustai_platform` (read/write on platform tables, `BYPASSRLS`) for the consoles; `irontrustai_admin` for migrations. No per-feature role growth.
- **Platform RBAC seam built this sprint**, permissions stored as data; exactly one permission defined now (`tenant:provision`). No superuser.
- **Operator creation** stays a credential-gated CLI capability, held by no operator permission.
- **Audit** is append-only (writer holds `INSERT` only) and always attributed to a verified operator; the CLI `provision` path authenticates the operator (no `cli` source, no self-asserted email). Only the genesis bootstrap is a system event.

## Decisions still open

- Whether the CLI `provision` command is retained long-term once the HTTP endpoint exists, or kept only as a break-glass path. Doesn't block the sprint.
- Mechanics of CLI operator authentication (interactive Cognito auth vs a short-lived operator token passed in). To settle at the start of item 3/5.

## Loose ends folded in

- Clean up the `globex-test` tenant and its Cognito user (tied to a real inbox; will collide on a re-run).
- Optional: add a `[project.scripts]` entry (`irontrust-admin = "app.cli.admin:app"`) for ergonomics.

## Out of scope (deliberately deferred)

- Additional permissions and the admin consoles beyond the `tenant:provision` seam (the RBAC *mechanism* is built now; populating it grows with each console).
- A formal operator-role catalogue / grouping of permissions into named roles (start with permissions assigned directly; group them once there are enough to warrant it).
- Operator self-service or operator-managed operator onboarding (stays CLI-only this sprint).
- Splitting `irontrustai_platform` into `_ro`/`_rw` (single read/write role to start).
- A tenant-facing "show me my org" read (a separate, properly-scoped tenant-plane feature).