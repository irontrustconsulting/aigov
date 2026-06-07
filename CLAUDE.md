# CLAUDE.md — IronTrust AI Governance Platform

> Agentic development guide. Read this before touching any code. It is the ground truth for architecture, conventions, and implementation status.

---

## 1. Project overview

**Product:** IronTrust — an AI governance platform for mid-market organisations. The MVP centre of gravity is the AI System Impact Assessment (AIIA), aligned to ISO/IEC 42005, scoped automatically by the system's EU AI Act risk classification. FRIA, DPIA and model-risk analyses feed into the AIIA as structured sections.

**PRD:** `docs/PRD.md`. The single authoritative source for what to build and why. Read it in full before starting any feature work.

**Current sprint:** `docs/SPRINT.md` — Platform-Operator Provisioning Plane.

**Active hand-off:** `docs/operator_enforcement.md` — the specific unit of work to execute now.

**Repo name:** `aigov`. **DB/Cognito/role prefix:** `irontrustai`. **Company:** IronTrust.

---

## 2. Architecture

### 2.1 Stack

| Layer | Technology |
|---|---|
| API | FastAPI (sync), Python 3.12 |
| ORM | SQLAlchemy 2.0 typed ORM (`Mapped`/`mapped_column`) |
| Migrations | Alembic, connected to `settings.migration_database_url` |
| Database | PostgreSQL (Docker in dev; `docker-compose.yml`) |
| Object storage | MinIO in dev (S3-compatible); real S3 in prod |
| Auth (tenants) | AWS Cognito — tenant user pool |
| Auth (operators) | AWS Cognito — separate operator user pool (Terraform in `infra/`) |
| Infra as code | Terraform (`infra/`) for Cognito; `alembic/sql/00_roles.sh` for DB roles |
| CLI | Typer (`app/cli/admin.py`) |
| AWS SDK | boto3 |
| Config | pydantic-settings, `.env` file, `app/config.py` |
| Linter | ruff |
| Tests | pytest + httpx (test files not yet written) |

### 2.2 Two planes — keep them strictly separate

```
TENANT PLANE              PLATFORM PLANE
─────────────────         ──────────────────────────
Customer orgs & users     IronTrust staff (operators)
Cognito tenant pool       Cognito operator pool (separate pool, separate issuer)
irontrustai_app role      irontrustai_platform_ro role (reads)
RLS-scoped sessions       BYPASSRLS, fenced by grants
get_tenant_db             get_platform_ro_db  (not yet wired)
verify_cognito_token      verify_operator_token
TenantContext             get_current_operator  (not yet built)
```

**Security invariant:** a tenant token must never satisfy operator auth, and vice versa. The two Cognito pools have different `iss` and `aud` values — this falls out of the JWT checks automatically. Never share a verifier between planes.

### 2.3 Authorization layers (three, never conflate)

1. **PostgreSQL DB roles** — coarse, per *connection type*, not per person. Fixed set: `irontrustai_admin` (DDL/Alembic), `irontrustai_app` (app runtime, NOBYPASSRLS), `irontrustai_resolver` (identity resolution, BYPASSRLS), `irontrustai_provisioner` (tenant creation, BYPASSRLS), `irontrustai_platform_ro` (operator reads, BYPASSRLS), `irontrustai_operator_provisioner` (operator creation, NOBYPASSRLS). Never add per-feature DB roles.

2. **Cognito** — authentication only. Answers "who is this?" Nothing about what they may do lives in the token claims (no role attributes on the operator pool).

3. **Application RBAC** — fine-grained, grows as data. Tenant side: `Membership.role` (admin/reviewer/contributor/auditor_readonly). Operator side: `Operator → OperatorRole → Role → RolePermission → Permission.key`. `require_permission("key")` checks this at runtime.

### 2.4 DB session pattern

Every connection type has its own engine + sessionmaker in `app/db/session.py`. Never reuse an engine across planes. Current engines:

- `engine` / `SessionLocal` → `irontrustai_app` (main app, RLS-bound)
- `resolver_engine` / `ResolverSessionLocal` → `irontrustai_resolver`
- `provisioner_engine` / `ProvisionerSessionLocal` → `irontrustai_provisioner`
- **`platform_ro_engine` / `PlatformROSessionLocal` → `irontrustai_platform_ro`** — not yet wired (see §6)

### 2.5 Multi-tenancy

Shared DB, row-level security. Every tenant-scoped table carries `tenant_id`. RLS policy reads `app.current_tenant` (set per-transaction by `get_tenant_db`). **Global/reference tables** (catalogue, controls, risks, taxonomy) carry no `tenant_id` and are NOT under RLS.

---

## 3. Data model

All ORM models are in `app/models/`. Full entity map in `app/models/MODELS.md`.

### 3.1 Model files

| File | Contents |
|---|---|
| `base.py` | `Base`, `uuid_pk()`, `TimestampMixin`, all enums |
| `identity.py` | `Tenant`, `User`, `Membership` |
| `domain.py` | `CatalogueVendor`, `CatalogueProduct`, `CatalogueFact`, `CatalogueProductRisk`, `System`, `UseCase`, `VendorApproval`, `ProductApproval` |
| `assessment.py` | `Classification`, `Assessment`, `AssessmentItem`, `AssessmentItemControl`, `AssessmentItemEvidence` |
| `knowledge.py` | `Control`, `ControlFrameworkMap`, `Risk`, `RiskControlMap` |
| `lifecycle.py` | `Evidence`, `AuditEvent`, `LifecycleTransition` |
| `taxonomy.py` | `EUAIActCategory`, `EUAIActSubcategory`, `ProductCategory`, `ProductCategoryMembership`, `ProductCategoryEUMapping` |
| `platform_rbac.py` | `Operator`, `Permission`, `Role`, `RolePermission`, `OperatorRole` |

### 3.2 Key modelling decisions

- **System = registered entity; UseCase = unit of assessment.** One System has many UseCases. Classification, AIIA, lifecycle state, and sign-off attach to the UseCase, never to the System.
- **Catalogue is global (cross-tenant).** `CatalogueVendor`/`CatalogueProduct` are reference data — the moat. Tenant inventory (`System`, `UseCase`) references it but doesn't own it.
- **Three inheriting approval scopes:** `VendorApproval` (tenant+vendor) → `ProductApproval` (tenant+product) → `UseCase.state == AUTHORISED`. Each scope has its own `ApprovalStatus`; cascading gates enforce inheritance.
- **Assessment type hierarchy:** `Assessment.type = AIIA` is the primary record; `FRIA`, `DPIA`, `MODEL_RISK` are feeders linked via `parent_aiia_id`. One AIIA per use case (enforced by partial unique index `uq_one_aiia_per_use_case`).
- **AuditEvent is append-only.** INSERT only — the writer holds no UPDATE/DELETE. A Postgres trigger enforces immutability. Never mutate audit rows in code.
- **Evidence files live in S3.** Postgres holds the pointer (`s3_bucket`, `s3_key`, `s3_version_id`) + `sha256`. Never store file bytes in the DB.
- **Operator permissions reach operators only through roles.** No direct operator→permission grants (they rot RBAC). If a one-off is needed, make a role for it.

### 3.3 Enums (from `base.py`)

`Framework`, `EUAIActTier`, `RiskLayer`, `RiskSource`, `ApprovalStatus`, `LifecycleState`, `AssessmentType`, `AssessmentStatus`, `CoverageStatus`, `ProvenanceConfidence`, `UserRole`, `OperatorStatus`

The `EUAIActTier` enum is shared by `UseCase.eu_tier`, `Classification.tier`, and `EUAIActSubcategory.tier` — all map to the same Postgres enum type `eu_ai_act_tier`.

---

## 4. Migrations

Migration chain (in order):
1. `182010f00859_initial_schema.py` — full schema: all tenant, catalogue, domain, assessment, knowledge, lifecycle, and taxonomy tables; RLS policies; audit immutability trigger; partial unique indexes; all initial grants
2. `7b4d1c391113_rls_on_tenant_table.py` — RLS on `tenant` table
3. `c319cbc6fd5b_add_governance_and_product_taxonomy.py` — taxonomy tables
4. `8eda654f48eb_add_legal_ref_to_eu_ai_act_taxonomy.py` — `legal_ref` on `EUAIActSubcategory`
5. `c53be9b832eb_add_reference_url_to_risk.py` — `reference_url` on `Risk`
6. **`cef7211ddfe4_operator_rbac.py`** — `operator`, `permission`, `role`, `role_permission`, `operator_role` tables; seeds `tenant:provision` permission + `provisioner` role + their link; grants to `irontrustai_platform_ro` and `irontrustai_operator_provisioner`

**Alembic notes:**
- `alembic upgrade head` uses `settings.migration_database_url` (the admin role)
- Hand-written SQL (partial unique indexes, RLS policies, triggers, grants) goes IN the migration file — never rely on app startup or separate scripts
- Autogenerate skips the three manually-managed indexes (`uq_one_aiia_per_use_case`, `uq_current_classification`, `uq_one_primary_eu_mapping`) — see `alembic/env.py` `include_object`

---

## 5. Configuration (`app/config.py`)

`Settings` is a pydantic-settings `BaseSettings` loaded from `.env`. The singleton is `settings = get_settings()`. Import it as `from app.config import settings`.

**DB URLs are computed properties** (assembled from component fields). Never store a full URL as a string in `.env`.

### Current config fields

```python
# App
app_env, debug

# DB components
postgres_user, postgres_password, postgres_db   # admin/Alembic
app_role, app_runtime_password                  # main app runtime
resolver_db_user, resolver_db_password          # identity resolver
provisioner_db_user, provisioner_db_password    # tenant provisioner
db_host, db_port

# S3
s3_endpoint_url, s3_region, s3_access_key, s3_secret_key, s3_evidence_bucket

# Cognito — tenant pool
cognito_region, cognito_user_pool_id, cognito_app_client_id

# Cognito — operator pool
cognito_operator_pool_issuer          # full issuer URL (used by verifier)
cognito_operator_app_client_id        # checked as `aud`
cognito_operator_user_pool_id         # bare pool id (used by boto3 admin calls)
```

### Computed URL properties

`database_url`, `migration_database_url`, `resolver_database_url`, `provisioner_database_url`

**`platform_ro_database_url` is NOT YET ADDED** — it's the first task in the current hand-off.

---

## 6. Implementation status

### ✅ Complete

| Area | What's done |
|---|---|
| Core framework | FastAPI app, config, DB wiring, Alembic |
| DB roles | All 6 DB roles defined in `00_roles.sh` and env-driven |
| All ORM models | Every table from the PRD data model is defined and migrated |
| Seed data | EU AI Act taxonomy, product categories, controls (ISO 42001 + EU AI Act), OWASP LLM Top 10 risks, risk-control maps, starter catalogue |
| Tenant auth | Cognito JWT verification (`cognito.py`), tenant context resolution (`context.py`), RLS-scoped sessions |
| Tenant RBAC | `Membership.role` + `require_role()` dependency |
| Tenant provisioning | `provision_tenant()` service + `provision`/`list-tenants` CLI commands |
| Reference API | `/v1/reference/product-categories` drill-down, vendors in category, products in category, EU AI Act subcategories |
| Systems API | `GET/POST /v1/systems` (tenant-scoped, RLS) |
| Operator Cognito pool | Terraform in `infra/`; applied — pool IDs in `.env` |
| Operator token verifier | `app/auth/operator_auth.py` — `verify_operator_token` → `OperatorClaims` |
| Operator RBAC schema | Migration `cef7211ddfe4`: `operator`/`permission`/`role`/`role_permission`/`operator_role` tables; `tenant:provision` permission + `provisioner` role seeded; grants applied |

### 🔲 Current hand-off: operator enforcement seam (`docs/operator_enforcement.md`)

Three changes only. No new endpoints, no create-operator, no tests (separate hand-offs).

**1. `app/config.py` — add platform_ro DB credentials**
```python
platform_ro_db_user: str          # env var PLATFORM_RO_DB_USER
platform_ro_db_password: str      # env var PLATFORM_RO_DB_PASSWORD (secret, no default)

@property
def platform_ro_database_url(self) -> URL:
    return URL.create("postgresql+psycopg",
        username=self.platform_ro_db_user,
        password=self.platform_ro_db_password,
        host=self.db_host, port=self.db_port, database=self.postgres_db)
```
Mirror the existing `provisioner_db_*` / `provisioner_database_url` pattern exactly.

**2. `app/db/session.py` — add platform_ro engine + dependency**
```python
platform_ro_engine = create_engine(settings.platform_ro_database_url, ...)
PlatformROSessionLocal = sessionmaker(bind=platform_ro_engine, ...)

def get_platform_ro_db() -> Generator[Session, None, None]:
    ...  # mirror get_db
```
Read-only path — this role has no write grants.

**3. New module `app/auth/operator_authz.py` (distinct from `operator_auth.py`)**

Provides two things:
- `get_current_operator` — depends on `verify_operator_token` (identity) + `get_platform_ro_db` (session). Resolves operator by `cognito_sub`. Enforces: operator row must exist (no lazy-create → 403), `status == ACTIVE` (→ 403). Returns a fully-materialized plain object (id, cognito_sub, email, display_name, effective permission set) — no lazy-loading after session closes.
- `require_permission(key)` — dependency factory; depends on `get_current_operator`; 403 if key not in operator's permissions; otherwise returns the operator (for audit attribution).

Effective permissions = DISTINCT union of `permission.key` values reachable via:
`operator_role (operator_id=?) → role_permission (role_id) → permission.key`

Behaviour contract:

| Situation | Result |
|---|---|
| No / malformed / expired token | 401 (from verifier) |
| Valid token, no matching operator row | 403 |
| Operator row exists, `status != ACTIVE` | 403 |
| Active operator, lacking permission | 403 |
| Active operator, has permission | passes; returns operator |

All DB access reads from `irontrustai_platform_ro` only. No writes, ever.

**Acceptance:** app imports and starts; all 5 contract rows hold; no writes attempted from this seam.

### 🔲 Next sprint items (after current hand-off)

In the order defined in `docs/SPRINT.md`:

- `create-operator` CLI command (`python -m app.cli.admin create-operator`) — boto3 `AdminCreateUser` against the operator pool + insert `operator` row with roles. Uses a new `irontrustai_operator_provisioner` engine (already exists in DB, not yet in session.py).
- `POST /platform/provision` — platform router, gated by `get_current_operator` + `require_permission("tenant:provision")`, calls existing `provision_tenant()`.
- `GET /platform/tenants` — same gate.
- Operator-action auditing — append-only `audit_event` rows for every privileged action, attributed to verified operator (not a string).
- Tests — see `docs/SPRINT.md §7` for the full test matrix.

### 🔲 Post-sprint / PRD features not yet started

All PRD sections beyond the provisioning plane: use-case intake flow, classification engine (EU AI Act tier derivation), AIIA engine, lifecycle state machine, review/sign-off workflow, export/audit pack. The data model for all of these is already fully defined and migrated — the API and service layers are what's missing.

---

## 7. Conventions

### Code style
- Ruff for linting + formatting (`ruff check .`, `ruff format .`). Config in `pyproject.toml`.
- SQLAlchemy 2.0 typed ORM everywhere — `Mapped[T]` + `mapped_column(...)`. No `Column(...)` syntax.
- Pydantic v2 schemas for all API shapes. Keep ORM models and Pydantic schemas in separate trees (`app/models/` vs `app/schemas/`).
- FastAPI dependencies for all cross-cutting concerns (auth, DB sessions, role checks). Never inline these in handlers.

### Adding a new DB role
Don't. The role set is fixed (see §2.3). If genuinely needed, add it to `00_roles.sh` AND document it in `CLAUDE.md`.

### Adding a new migration
```bash
alembic revision --autogenerate -m "short_description"
# Then hand-edit: add partial indexes, RLS policies, grants, triggers — autogenerate misses these
```
Always apply grants in the migration, not in `00_roles.sh` (so they reproduce on a fresh environment).

### Adding a new endpoint
1. Create or reuse a router file under `app/routers/v1/` (tenant plane) or `app/routers/platform/` (operator plane, to be created).
2. Include the router in `app/main.py` under the appropriate prefix.
3. Gate tenant routes with `Depends(get_tenant_db)` / `Depends(require_role(...))`. Gate platform routes with `Depends(require_permission("key"))`.
4. Pydantic `*Read`/`*Create` schemas go in `app/schemas/`.

### Provisioning flow (never self-service)
The only way to create a tenant is through `provision_tenant()` — CLI or (soon) `POST /platform/provision`. The tenant-facing `POST /tenants` endpoint is intentionally removed and must not be reinstated.

### Cross-cutting design pattern (PRD §1.5)
Every assertion the system makes must follow: **strong default → shown reasoning → easy override → tracked deviation**. In code this means: propose a confident answer, expose the basis/rationale, accept a human amendment, write the delta to `AuditEvent`. This applies to classification results, AIIA content, and catalogue prefill facts.

---

## 8. Dev environment

```bash
# Start Postgres + MinIO
docker compose up -d

# Install deps
pip install -e ".[dev]"

# Run migrations
alembic upgrade head

# Seed reference data
python -m scripts.seed.seed_all

# Start the API
uvicorn app.main:app --reload

# CLI
python -m app.cli.admin --help
```

Key URLs in dev: API at `http://localhost:8000`, MinIO console at `http://localhost:9001`.

Health checks: `GET /health` (liveness), `GET /health/db` (readiness).

---

## 9. File map (non-obvious locations)

| Path | What's there |
|---|---|
| `docs/PRD.md` | Full product requirements |
| `docs/SPRINT.md` | Current sprint definition |
| `docs/operator_enforcement.md` | Active hand-off for operator authZ seam |
| `app/models/MODELS.md` | Data model notes + DB-enforced guarantees |
| `alembic/sql/00_roles.sh` | Creates all PostgreSQL DB roles (runs once on volume init) |
| `data/seed/` | YAML seed files for all global reference data |
| `scripts/seed/` | Python loaders for each seed file |
| `infra/` | Terraform for operator Cognito pool |
| `app/auth/cognito.py` | Tenant Cognito JWT verifier |
| `app/auth/operator_auth.py` | Operator Cognito JWT verifier (authN only) |
| `app/auth/context.py` | Tenant authZ: TenantContext, get_tenant_db, require_role |
| `app/services/provisioning.py` | provision_tenant() — the only tenant creation path |

---

## 10. Out of scope (MVP hard boundary — do not build)

Per PRD §3.2: automated AI asset discovery, continuous technical monitoring, agentic/runtime guardrail governance, full vendor diligence workflows (questionnaires, security review), configurable workflow engine, CI/CD deployment gate enforcement, third-party supply-chain risk module, frameworks beyond ISO 42001 and EU AI Act (NIST AI RMF reserved in data model only).
