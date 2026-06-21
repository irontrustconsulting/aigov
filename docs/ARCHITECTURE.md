# ARCHITECTURE.md — IronTrust AI Governance Platform

**Location:** `docs/ARCHITECTURE.md` — single source, mirrored to project knowledge. Updated rarely.
**Purpose:** How the repo is built — the durable structural facts that do not move when a route or model is added. This is the engineering ground truth.
**Lanes:** the data-model inventory (model files, tables, enums, indexes) → `DATA-MODEL.md`; constraints → `INVARIANTS.md` (`INV-n`); rationale → `DECISIONS.md` (`D-n`); service-implementation shapes → `PATTERNS.md` (`PAT-n`); current capabilities → `STATE.md`. This file deliberately holds nothing route- or model-sensitive, so it cannot drift as the build grows.

**Naming:** repo `aigov`; DB / Cognito / role prefix `irontrustai`; company IronTrust.

---

## 1. Stack

| Layer | Technology |
|---|---|
| API | FastAPI (sync), Python 3.12 |
| ORM | SQLAlchemy 2.0 typed ORM (`Mapped` / `mapped_column`) |
| Migrations | Alembic, via `settings.migration_database_url` |
| Database | PostgreSQL (Docker in dev) |
| Object storage | MinIO in dev (S3-compatible); real S3 in prod |
| Auth (tenants) | AWS Cognito — tenant user pool |
| Auth (operators) | AWS Cognito — separate operator pool |
| Infra as code | Terraform (`infra/`) for Cognito; `alembic/sql/00_roles.sh` for DB roles |
| CLI | Typer (`app/cli/admin.py`) |
| AWS SDK | boto3 |
| Config | pydantic-settings, `.env`, `app/config.py` |
| Lint / test | ruff; pytest + httpx |

---

## 2. Two planes — strictly separate

```
TENANT PLANE                       PLATFORM PLANE
────────────────────────           ──────────────────────────────
Customer orgs & users              IronTrust staff (operators)
Cognito tenant pool                Cognito operator pool (separate issuer)
irontrustai_app role               irontrustai_platform_ro role
RLS-scoped sessions                BYPASSRLS, fenced by grants
verify_cognito_token               verify_operator_token
```

A tenant token must never satisfy operator auth, and vice versa — the pools have different `iss`/`aud`, so this falls out of the JWT checks. Never share a verifier across planes (**INV-1**).

---

## 3. Authorization — three layers, never conflated (D-24)

1. **PostgreSQL DB roles** — coarse, per *connection type*, not per person. Fixed closed set (§4). Never add a per-feature DB role.
2. **Cognito** — authentication only. Answers "who is this?" Nothing about *what they may do* lives in token claims.
3. **Application authz** — fine-grained, DB-authoritative, never read from claims.
   - *Tenant side:* an administrative role on `Membership` **plus** SoD-constrained governance roles. The role catalogue, conflict matrix, and admin/governance split are the domain model — **DOMAIN §7**; enforcement loci are **INV-7, 28**.
   - *Operator side:* `Operator → OperatorRole → Role → RolePermission → Permission.key`, checked by `require_permission("key")`. Permissions reach operators only through roles (**INV-8**).

---

## 4. DB roles & session model

**One engine ↔ one DB role.** Every connection type has its own engine + sessionmaker in `app/db/session.py`; never reuse an engine across planes or roles.

| Role | Privilege | Purpose | Engine |
|---|---|---|---|
| `irontrustai_admin` | DDL | Alembic migrations | (migration URL) |
| `irontrustai_app` | NOBYPASSRLS, blanket DML | App runtime, RLS-bound | `engine` / `SessionLocal` |
| `irontrustai_resolver` | BYPASSRLS, SELECT-only on identity tables | Identity resolution (breaks the RLS-on-membership deadlock) | `resolver_engine` |
| `irontrustai_provisioner` | BYPASSRLS, INSERT/SELECT on `tenant`/`app_user`/`membership` only | Tenant creation | `provisioner_engine` |
| `irontrustai_platform_ro` | BYPASSRLS | Operator reads | `platform_ro_engine` |
| `irontrustai_operator_provisioner` | NOBYPASSRLS | Operator creation | (operator) |

The set is created by `alembic/sql/00_roles.sh` (runs once on volume init). Tenant-scoped work runs only on `irontrustai_app` (**INV-4**). Adding a role: don't (§9).

---

## 5. Identity & auth chains

### Identity (mechanical)

```
Tenant ←── Membership(role: UserRole) ──→ User (app_user)
```

- **Tenant** — the org unit. Created only by `provision_tenant()` (D-23). No public creation path.
- **User** (`app_user`) — a human identity. **Global, non-RLS**, linked to Cognito via `cognito_sub`. Email is not DB-unique — Cognito is the uniqueness authority (**INV-9**). Access to any tenant is always mediated by a `Membership` row; `app_user` is never read bare (**INV-2**).
- **Membership** — the unit of authorisation, RLS-scoped to its tenant. `role` (`ADMIN`/`MEMBER`) is the administrative axis only — zero governance power (DOMAIN §7).
- **One tenant per user** — Cognito `custom:tenant_id` is immutable; multi-tenant identity is blocked by design.

### Tenant auth chain

```
verify_cognito_token
  └─ get_tenant_context  →  TenantContext (DB-authorised identity)
       └─ get_tenant_db   →  RLS-scoped Session (app.current_tenant set per-transaction)
            ├─ require_role("admin"|"member")        — administrative axis
            └─ require_governance_role("key"…)       — governance axis (DB lookup)
```

`TenantContext` carries `user_id`, `membership_id`, `tenant_id`, `role` (authoritative from the membership row, not the token), `email`, `name`. The two gate dependencies guard different axes and **must not be combined on one endpoint**: `require_role` for administrative actions, `require_governance_role` for workflow actions. `tenant_id` is always `ctx.tenant_id`, never a request body field (**INV-3**).

### Operator auth chain

```
verify_operator_token  →  get_current_operator  →  require_permission("key")
```

Wholly separate from the tenant chain; tokens cannot satisfy each other's verifiers (**INV-1**).

---

## 6. Multi-tenancy & RLS

Shared database, Postgres row-level security.

- Every tenant-scoped table carries `tenant_id`. The RLS policy reads `app.current_tenant`, set `SET LOCAL` per-transaction inside `get_tenant_db` — transaction-local, so it cannot leak across pooled connections.
- **Global reference tables carry no `tenant_id` and are not under RLS** — catalogue, controls, risks, taxonomy, governance-role catalogue + conflict matrix, decision tree, assessment section templates. Cross-tenant by design, readable from any session (**INV-40**).
- `irontrustai_app` is `NOBYPASSRLS` with blanket DML; isolation is enforced entirely by RLS, not by table grants (**INV-4**).
- A mid-request `db.commit()` resets `SET LOCAL` settings including `app.current_tenant`; any path that commits mid-request on an RLS-bound session must re-set it (**INV-27**). RLS/enum/`SET LOCAL` code is live-smoke-tested against the real dev DB (D-21).

---

## 7. Migrations

The chain lives in `alembic/versions/`; check `alembic history` / `alembic heads` before adding a revision.

- `alembic upgrade head` uses `settings.migration_database_url` (the admin role).
- **Hand-written SQL — partial unique indexes, RLS policies, triggers, and all grants — goes IN the migration file**, never in app startup or a separate script, so it reproduces on a fresh environment.
- Autogenerate misses the manually-managed partial indexes and all RLS/triggers/grants — always hand-edit the generated revision. (The specific manual indexes are catalogued in DATA-MODEL.)
- Reference-table *row content* follows the YAML + loader convention (`data/seed/`, `scripts/seed/`), not a migration; migrations still hand-edit RLS/grants/partial indexes.

---

## 8. Configuration (`app/config.py`)

`Settings` is a pydantic-settings `BaseSettings` loaded from `.env`; the singleton is `settings = get_settings()` (`from app.config import settings`). **DB URLs are computed properties** assembled from component fields (user/password/host/port/db) — never store a full URL string in `.env`. Add new credentials by mirroring the existing `*_db_user` / `*_database_url` pattern.

---

## 9. Conventions

### Code style
- Ruff for lint + format (`pyproject.toml`).
- SQLAlchemy 2.0 typed ORM everywhere — `Mapped[T]` + `mapped_column(...)`; no legacy `Column(...)`.
- Pydantic v2 for all API shapes. ORM models (`app/models/`) and schemas (`app/schemas/`) live in separate trees.
- Cross-cutting concerns (auth, DB sessions, role checks) are FastAPI dependencies — never inlined in handlers.

### Adding a DB role
Don't — the set is fixed (§4). If genuinely unavoidable, add it to `00_roles.sh` and document it here (D-24).

### Adding a migration
```
alembic revision --autogenerate -m "short_description"
# then hand-edit: partial indexes, RLS policies, grants, triggers
```

### Adding an endpoint
1. Router under `app/routers/v1/` (tenant) or `app/routers/platform/` (operator); include it in `app/main.py` under the right prefix.
2. Gate tenant routes with `Depends(get_tenant_db)` **plus** `require_role` *or* `require_governance_role` (never both); gate platform routes with `Depends(require_permission("key"))`.
3. `*Read` / `*Create` schemas in `app/schemas/`.
4. `tenant_id` is `ctx.tenant_id`, never a body field (INV-3).

Service-implementation shapes (external-call choreography, the slow-external-no-transaction shape, single-conditional-UPDATE concurrency, read-time propagation, the provenance machine) are in **PATTERNS.md** — follow them rather than improvising.

### Provisioning is never self-service
The only way to create a tenant is `provision_tenant()` (CLI or `POST /platform/provision`). The tenant-facing `POST /tenants` endpoint was intentionally removed and must not be reinstated (D-23).

### The §1.5 UX contract in code
Every assertion follows strong default → shown reasoning → easy override → tracked deviation: propose a confident answer, expose its basis, accept a human amendment, write the delta to `AuditEvent`. Applies to classification, AIIA content, catalogue prefills (D-1).

---

## 10. Dev environment

```
docker compose up -d                 # Postgres + MinIO
pip install -e ".[dev]"              # deps
alembic upgrade head                 # migrations
python -m scripts.seed.seed_all      # seed reference data
uvicorn app.main:app --reload        # run API
python -m app.cli.admin --help       # CLI
```

API `http://localhost:8000`; MinIO console `http://localhost:9001`. Health: `GET /health` (liveness), `GET /health/db` (readiness).

---

## 11. File map (durable, non-obvious locations)

| Path | What's there |
|---|---|
| `docs/*.md` | The canonical knowledge base (this file and its siblings) |
| `sprints/*.md` | Sprint hand-offs (current units of work) |
| `alembic/sql/00_roles.sh` | Creates all DB roles (runs once on volume init) |
| `data/seed/` | YAML seed files for global reference data |
| `scripts/seed/` | Python loaders per seed file |
| `infra/` | Terraform for the operator Cognito pool |
| `app/db/session.py` | Per-role engines + sessionmakers (§4) |
| `app/auth/cognito.py` | Tenant Cognito JWT verifier |
| `app/auth/operator_auth.py` | Operator Cognito JWT verifier (authN only) |
| `app/auth/context.py` | Tenant authz: `TenantContext`, `get_tenant_db`, `require_role` |
| `app/services/provisioning.py` | `provision_tenant()` — the only tenant-creation path |
| `app/services/cognito_helpers.py` | Shared Cognito helpers — reuse, don't duplicate |

*(The `app/models/` inventory and per-service listing live in DATA-MODEL / STATE, which are updated each sprint; this map holds only durable locations.)*