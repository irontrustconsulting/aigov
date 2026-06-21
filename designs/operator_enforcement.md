# Hand-off: Operator enforcement seam (authZ)

> **Format.** Prescriptive about *what* and *why* — contract, constraints,
> acceptance criteria. The *how* (the code) is left to the agent, which has the
> full repo. Code appears only where it pins a decision, and is marked
> *reference — adapt to the repo*.

## Goal

Wire application-layer authorization for platform operators: resolve the
authenticated operator from the DB, confirm they are active, load their effective
permissions, and gate a route on a specific permission. This is the seam every
platform endpoint sits behind.

## Preconditions (verify, don't redo)

- Migration `cef7211ddfe4_operator_rbac` applied: `operator`, `permission`, `role`,
  `role_permission`, `operator_role` exist; `tenant:provision` + `provisioner` role
  + their link seeded.
- DB roles exist: `irontrustai_platform_ro` (BYPASSRLS, read), with `SELECT` on the
  five RBAC tables granted by that migration.
- `operator_auth.py` exists: `verify_operator_token` -> `OperatorClaims(sub, email, name)`.
- Operator Cognito settings present in config (`cognito_operator_pool_issuer`,
  `cognito_operator_app_client_id`, `cognito_operator_user_pool_id`).

## Scope

Three changes. **No new endpoints, no create-operator, no auditing, no tests** — separate hand-offs.

### 1. Platform read credentials (config)

Add a DB user/password pair and a computed connection URL for `irontrustai_platform_ro`,
**mirroring the existing `provisioner_db_*` fields and the `provisioner_database_url`
property exactly**. Env vars `PLATFORM_RO_DB_USER` / `PLATFORM_RO_DB_PASSWORD`
(password is a secret — no default).

### 2. Platform read engine + dependency (session module)

Add an engine + sessionmaker bound to `settings.platform_ro_database_url`, plus a
`get_platform_ro_db` FastAPI dependency, **mirroring the resolver/provisioner engine
blocks and `get_db`**. Read-only path — this role has no write grants.

### 3. AuthZ module: resolution + permission gate

A new module, **kept separate from `operator_auth.py`** (which is authN), providing:

- **`get_current_operator`** — depends on the operator-token verifier (identity) and
  the platform read session. Resolves the operator by `cognito_sub`, enforces the
  contract below, and returns a **fully-materialized** object (id, cognito_sub, email,
  display_name, and the effective permission set) so nothing lazy-loads after the
  session closes.
- **`require_permission(key)`** — a dependency factory that depends on
  `get_current_operator`, rejects (403) if the key is not among the operator's
  permissions, and otherwise **returns the operator** (so handlers can use it for audit
  attribution later). Intended call shape: `Depends(require_permission("tenant:provision"))`.

Effective permissions are the de-duplicated union of permission keys reachable through
the operator's roles — **roles-only, no direct operator->permission grants** (matches the
schema). Illustrative traversal (*reference — adapt to the repo*):

```
operator_role (operator_id = ?)  ->  role_permission (role_id)  ->  permission.key   [DISTINCT]
```

## Behaviour contract

| Situation | Result |
|---|---|
| No / malformed / expired token | 401 (from the verifier) |
| Valid operator token, no matching `operator` row | 403 — not a recognized operator |
| Operator row exists but `status != ACTIVE` | 403 — account disabled |
| Active operator lacking the required permission | 403 — insufficient permissions |
| Active operator holding the required permission | passes; route receives the resolved operator |

## Constraints (decisions — honour these)

- All DB access in this seam is on `irontrustai_platform_ro`: read-only, no writes.
- **No lazy-create** — an unknown `sub` is rejected (403), never turned into an operator row.
- **Active check** — a disabled operator is rejected (403) even with a valid token.
- **authN/authZ stay separate** — this module is distinct from `operator_auth.py`.
- **Materialize in-request** — return a plain object, not a live ORM row that lazy-loads
  after the session closes.
- 401s are already handled by the verifier; this seam adds only 403s.

## Acceptance criteria

1. App imports and starts with the new config field, engine, and module.
2. All five behaviour-contract rows hold (verify with a temporary guarded route or a unit test).
3. The seam performs reads only — `platform_ro` has no write grants, so no write is attempted.

### Optional verification aid (remove after)

Once a genesis operator exists and can mint a token, a throwaway
`GET /platform/whoami` guarded by `require_permission("tenant:provision")` makes the
contract checkable end to end: valid+permitted -> identity echoed; disabled/unknown/
unpermitted -> 403; no token -> 401.

## Out of scope (later hand-offs)

- `create-operator` CLI (writes via `irontrustai_operator_provisioner`).
- `POST /platform/provision`, `GET /platform/tenants`.
- Auditing (existing `audit_event` table; its schema will inform that hand-off).
- Automated tests.