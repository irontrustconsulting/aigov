# CLAUDE.md — IronTrust AI Governance Platform

> How this repository is built and how to work in it. Read before touching code.
> This file is the **engineering ground truth** (architecture, conventions, guardrails).
> It deliberately does **not** restate the product (→ PRD) or the current task (→ active sprint).

---

## 1. Orientation

**Product, in one line:** an AI governance platform for mid-market orgs; the MVP centre of gravity is the ISO/IEC 42005 AI System Impact Assessment, scoped by EU AI Act risk tier. The *why and what* lives in the PRD — read it before any feature work.

**The three documents — keep them in their lanes:**

| Doc | Holds | Read it for |
|---|---|---|
| `docs/PRD.md` | Product: what to build and why | The domain — model, lifecycle, requirements, out-of-scope |
| `CLAUDE.md` (this) | Engineering: how the repo works | Architecture, conventions, guardrails — true every sprint |
| `sprints/*.md` | The current unit of work | The task: goal, work items, acceptance |

If a fact is *what the product is*, it belongs in the PRD; if it's *this task's detail* or *changing status*, it belongs in the sprint. This file holds only what's durable.

**Current work:** `sprints/USE_CASE_CLASSIFICATION.md` — read it first; it is the source of truth for what to build now.

**Naming:** repo `aigov`; DB/Cognito/role prefix `irontrustai`; company IronTrust.

---

## 2. Architecture

### 2.1 Stack

| Layer | Technology |
|---|---|
| API | FastAPI (sync), Python 3.12 |
| ORM | SQLAlchemy 2.0 typed ORM (`Mapped` / `mapped_column`) |
| Migrations | Alembic, via `settings.migration_database_url` |
| Database | PostgreSQL (Docker in dev; `docker-compose.yml`) |
| Object storage | MinIO in dev (S3-compatible); real S3 in prod |
| Auth (tenants) | AWS Cognito — tenant user pool |
| Auth (operators) | AWS Cognito — separate operator pool (Terraform in `infra/`) |
| Infra as code | Terraform (`infra/`) for Cognito; `alembic/sql/00_roles.sh` for DB roles |
| CLI | Typer (`app/cli/admin.py`) |
| AWS SDK | boto3 |
| Config | pydantic-settings, `.env`, `app/config.py` |
| Lint / test | ruff; pytest + httpx |

### 2.2 Two planes — keep them strictly separate

```
TENANT PLANE              PLATFORM PLANE
─────────────────         ──────────────────────────
Customer orgs & users     IronTrust staff (operators)
Cognito tenant pool       Cognito operator pool (separate pool, separate issuer)
irontrustai_app role      irontrustai_platform_ro role
RLS-scoped sessions       BYPASSRLS, fenced by grants
verify_cognito_token      verify_operator_token
```

**Security invariant:** a tenant token must never satisfy operator auth, and vice versa. The two pools have different `iss`/`aud`, so this falls out of the JWT checks automatically. Never share a verifier across planes.

### 2.3 Authorization layers — three, never conflate

1. **PostgreSQL DB roles** — coarse, per *connection type*, not per person. Fixed set: `irontrustai_admin` (DDL/Alembic), `irontrustai_app` (app runtime, NOBYPASSRLS), `irontrustai_resolver` (identity resolution, BYPASSRLS), `irontrustai_provisioner` (tenant creation, BYPASSRLS), `irontrustai_platform_ro` (operator reads, BYPASSRLS), `irontrustai_operator_provisioner` (operator creation, NOBYPASSRLS). **Never add per-feature DB roles.**
2. **Cognito** — authentication only. Answers "who is this?" Nothing about *what they may do* lives in token claims.
3. **Application authz** — fine-grained, DB-authoritative, never read from claims.
   - *Tenant side:* an administrative role on `Membership` **plus** SoD-constrained governance roles. The governance catalogue, the conflict matrix, and the `Membership.role` → administrative-only split are specified in **PRD §4.9.1** and built across the role-management sprints — defer to those, don't hard-code the role set here.
   - *Operator side:* `Operator → OperatorRole → Role → RolePermission → Permission.key`, checked by `require_permission("key")`.

### 2.4 DB session pattern

Every connection type has its own engine + sessionmaker in `app/db/session.py`. **Never reuse an engine across planes or roles.** One engine ↔ one DB role. (`engine`/`SessionLocal` → `irontrustai_app`, RLS-bound; `resolver_engine`, `provisioner_engine`, `platform_ro_engine` likewise.)

### 2.5 Multi-tenancy

Shared DB, row-level security. Every tenant-scoped table carries `tenant_id`; the RLS policy reads `app.current_tenant` (set per-transaction by `get_tenant_db`). **Global/reference tables** (catalogue, controls, risks, taxonomy, governance-role catalogue + conflict matrix) carry no `tenant_id` and are **not** under RLS.

---

## 3. Data model

ORM models live in `app/models/`. Full entity map + DB-enforced guarantees: `app/models/MODELS.md`. Conceptual model (System vs UseCase, the three approval scopes, the assessment hierarchy, catalogue-as-moat): **PRD** — not restated here.

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

### 3.2 Code-enforced invariants (must be respected in code)

- **`AuditEvent` is append-only.** INSERT only; the writer holds no UPDATE/DELETE and a Postgres trigger enforces immutability. Never mutate audit rows.
- **Evidence bytes live in S3.** Postgres holds the pointer (`s3_bucket`, `s3_key`, `s3_version_id`) + `sha256`. Never store file bytes in the DB.
- **Operator permissions reach operators only through roles.** No direct operator→permission grants. If a one-off is needed, make a role.
- **Three manually-managed partial unique indexes** — `uq_one_aiia_per_use_case`, `uq_current_classification`, `uq_one_primary_eu_mapping` — are hand-written in migrations and skipped by autogenerate (`alembic/env.py` `include_object`).

### 3.3 Enums (from `base.py`)

`Framework`, `EUAIActTier`, `RiskLayer`, `RiskSource`, `ApprovalStatus`, `LifecycleState`, `AssessmentType`, `AssessmentStatus`, `CoverageStatus`, `ProvenanceConfidence`, `UserRole`, `OperatorStatus`.

`EUAIActTier` is shared by `UseCase.eu_tier`, `Classification.tier`, and `EUAIActSubcategory.tier` — all the same Postgres type `eu_ai_act_tier`.

---

## 4. Migrations

The chain lives in `alembic/versions/`; check `alembic history` / `alembic heads` before adding a revision.

**Conventions:**
- `alembic upgrade head` uses `settings.migration_database_url` (the admin role).
- Hand-written SQL — partial unique indexes, RLS policies, triggers, **and all grants** — goes IN the migration file, never in app startup or a separate script, so it reproduces on a fresh environment.
- Autogenerate misses the three manually-managed indexes (§3.2) and RLS/triggers/grants — always hand-edit the generated revision.

---

## 5. Configuration (`app/config.py`)

`Settings` is a pydantic-settings `BaseSettings` loaded from `.env`; the singleton is `settings = get_settings()` — import `from app.config import settings`. **DB URLs are computed properties** assembled from component fields (user/password/host/port/db) — never store a full URL string in `.env`. The current field set lives in the file; add new credentials by mirroring the existing `*_db_user` / `*_database_url` pattern.

---

## 6. Conventions

### Code style
- Ruff for lint + format (`ruff check .`, `ruff format .`); config in `pyproject.toml`.
- SQLAlchemy 2.0 typed ORM everywhere — `Mapped[T]` + `mapped_column(...)`. No legacy `Column(...)`.
- Pydantic v2 for all API shapes. Keep ORM models (`app/models/`) and schemas (`app/schemas/`) in separate trees.
- Cross-cutting concerns (auth, DB sessions, role checks) are FastAPI dependencies — never inlined in handlers.

### Adding a DB role
Don't. The set is fixed (§2.3). If genuinely unavoidable, add it to `00_roles.sh` **and** document it here.

### Adding a migration
```bash
alembic revision --autogenerate -m "short_description"
# then hand-edit: partial indexes, RLS policies, grants, triggers (autogenerate misses these)
```

### Adding an endpoint
1. Router under `app/routers/v1/` (tenant) or `app/routers/platform/` (operator).
2. Include it in `app/main.py` under the right prefix.
3. Gate tenant routes with `Depends(get_tenant_db)` + the appropriate role/governance dependency; gate platform routes with `Depends(require_permission("key"))`.
4. `*Read` / `*Create` schemas in `app/schemas/`.

### Provisioning is never self-service
The only way to create a tenant is `provision_tenant()` — CLI or `POST /platform/provision`. The tenant-facing `POST /tenants` endpoint was intentionally removed and must not be reinstated.

### The system's core UX contract (PRD §1.5)
Every assertion follows: **strong default → shown reasoning → easy override → tracked deviation.** In code: propose a confident answer, expose its basis, accept a human amendment, write the delta to `AuditEvent`. Applies to classification, AIIA content, and catalogue prefills.

---

## 7. Dev environment

```bash
docker compose up -d                 # Postgres + MinIO
pip install -e ".[dev]"              # deps
alembic upgrade head                 # migrations
python -m scripts.seed.seed_all      # seed reference data
uvicorn app.main:app --reload        # run API
python -m app.cli.admin --help       # CLI
```

API `http://localhost:8000`; MinIO console `http://localhost:9001`. Health: `GET /health` (liveness), `GET /health/db` (readiness).

---

## 8. File map (non-obvious locations)

| Path | What's there |
|---|---|
| `docs/PRD.md` | Product requirements (authoritative domain spec) |
| `docs/SPRINT_*.md` | Sprint hand-offs (current units of work) |
| `app/models/MODELS.md` | Data-model notes + DB-enforced guarantees |
| `alembic/sql/00_roles.sh` | Creates all DB roles (runs once on volume init) |
| `data/seed/` | YAML seed files for global reference data |
| `scripts/seed/` | Python loaders per seed file |
| `infra/` | Terraform for the operator Cognito pool |
| `app/auth/cognito.py` | Tenant Cognito JWT verifier |
| `app/auth/operator_auth.py` | Operator Cognito JWT verifier (authN only) |
| `app/auth/context.py` | Tenant authz: `TenantContext`, `get_tenant_db`, `require_role` |
| `app/services/provisioning.py` | `provision_tenant()` — the only tenant-creation path |

---

## 9. Out of scope

The MVP hard boundary is **PRD §3.2** — defer to it rather than duplicating the list. In short: no automated asset discovery, runtime monitoring/guardrails, configurable workflow engine, CI/CD gates, or frameworks beyond ISO 42001 + EU AI Act. If a task drifts toward any of these, stop and check the PRD.