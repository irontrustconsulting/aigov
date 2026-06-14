# STATE.md — IronTrust AI Governance Platform

**Purpose:** A curated context artifact for design and review agents without direct repo access. It describes what is on the ground, what patterns exist, what must not be reinvented, and what is deliberately deferred. It is not a code inventory, not a changelog, and does not duplicate `CLAUDE.md`.

**Companion documents:**
- `CLAUDE.md` — durable engineering rules: stack, DB role model, session model, code conventions. Read for *how we build*.
- `docs/PRD.md` — product requirements. Read for *what to build and why*.
- `STATE.md` (this) — implementation state. Read for *what already exists and what must not be reinvented*.
- `sprints/*.md` — the active unit of work.

---

## How to use this file in prompts

| Task | Relevant sections |
|---|---|
| Designing a new feature / sprint | §3 (what exists) + §5 (deferred) — avoid building over existing work or into deferred scope |
| Writing a sprint spec | §4 (patterns) — reference the right seams; §2 (baseline) — anchor architectural decisions |
| Reviewing an implementation | §6 (invariants) as checklist; §4 (patterns) as the reference for correct shape |
| Generating an implementation plan | §2 (baseline) + §4 (patterns) for orientation; §5 to know where to stop |

Do not treat STATE.md as the sole source of truth for specific field names, function signatures, or SQL details. If a design depends on these, verify against the code.

---

## 1. Platform baseline

### Identity and membership

The core chain is:

```
Tenant ←── Membership(role: UserRole) ──→ User (app_user)
```

- **Tenant**: the organisational unit. Created only by `provision_tenant()` (operator CLI or `POST /platform/provision`). Never self-service; no public creation endpoint.
- **User** (`app_user`): a human identity. **Global, non-RLS.** Linked to Cognito via `cognito_sub`. Email is not DB-unique — Cognito is the uniqueness and invite authority. A user's access to any tenant is always mediated by a `Membership` row.
- **Membership**: the unit of authorisation. RLS-scoped to its tenant. `role` (`ADMIN` or `MEMBER`) is the administrative axis only — it confers no governance power.
- **`app_user` is not RLS-protected**: any read of users within a tenant context must join from `membership`, never query `app_user` directly. The app DB role can see all rows; only the membership join restricts scope to the caller's tenant.
- **One tenant per user**: Cognito `custom:tenant_id` is immutable. A user cannot belong to multiple tenants; multi-tenant identity is blocked by design.

### Auth and context (tenant side)

```
verify_cognito_token
  └── get_tenant_context  →  TenantContext (DB-authorised identity)
        └── get_tenant_db  →  RLS-scoped Session (app.current_tenant set per-transaction)
              ├── require_role("admin"|"member")      — administrative axis
              └── require_governance_role("key"...)   — governance axis (DB lookup)
```

`TenantContext` carries `user_id`, `membership_id`, `tenant_id`, `role` (authoritative from the membership row, not the token), `email`, `name`. It is the resolved, DB-verified identity for every tenant request.

The two gate dependencies guard different axes and must not be combined on the same endpoint. `require_role` is for administrative actions (member management, governance role assignment). `require_governance_role` is for workflow actions (system registration, classification override, future approval). `tenant_id` is always sourced from `ctx.tenant_id`, never from request body.

**Platform operators** use a wholly separate chain (`verify_operator_token` → `get_current_operator`) with permission-based authZ (`require_permission("key")`). Tenant and operator tokens cannot satisfy each other's verifiers.

### Multi-tenancy and RLS

Shared database with Postgres row-level security. RLS policies read `app.current_tenant` (set `SET LOCAL` per-transaction inside `get_tenant_db`) — transaction-local, cannot leak across pooled connections.

Global reference tables (catalogue, controls, risks, taxonomy, governance role catalogue and conflict matrix) have no `tenant_id` and no RLS. They are cross-tenant by design and readable from any session. Tenant data always carries `tenant_id`.

The app DB role (`irontrustai_app`, `NOBYPASSRLS`) has blanket DML on all `public` tables. Tenant isolation is enforced entirely by RLS, not by table grants. Privilege-elevated DB roles exist for provisioning and identity resolution; each is bound to exactly one engine/sessionmaker and may not be shared across purposes.

---

## 2. Governance role model

Two axes are strictly and permanently separated:

- **Administrative axis** (`UserRole` on `Membership`): account management only — managing members, assigning governance roles. Zero governance power.
- **Governance axis** (`governance_role_assignment`): five roles on three lines of defence.

| Role | Line | Composable with |
|---|---|---|
| `system_owner` | 1st | `contributor` only |
| `contributor` | 1st | `system_owner` only |
| `reviewer` | 2nd | — |
| `authoriser` | 2nd | — |
| `auditor` | 3rd | — |

Every cross-line pair conflicts. `system_owner + contributor` is the only composable pair. The conflict matrix is policy-as-data in the `governance_role_conflict` table (9 rows); `assert_governance_assignable()` is the **single locus** that enforces it — all new assignment paths must go through it. Self-assignment (admin granting to themselves) is blocked.

Governance roles are currently **tenant-wide**, not per-system. The per-system extension is designed as additive (a nullable `scope_id` on `governance_role_assignment`, `NULL` = tenant-wide, preserving every existing grant). Do not build it now; leave the seam.

---

## 3. Implemented capabilities

### AI system register and classification
- Systems and use cases can be registered. A system is the entity; each use case is the unit of assessment with its own classification and lifecycle state.
- EU AI Act classification is resolved automatically on use case creation by traversing the seeded reference bridge (`system → catalogue_product → product_category → eu_ai_act_subcategory`). When the bridge cannot resolve a tier — because the system has no catalogue product or no primary mapping — it returns `REQUIRES_CONTEXT`, which is the designed seam for the future context-question wizard.
- Classification snapshots are versioned. Overrides are tracked with the proposed tier, override tier, justification, and actor in both the `Classification` row and an `AuditEvent`.

### Member management
- A tenant admin creates members via a single endpoint: Cognito invite + `Membership(UserRole.MEMBER, zero governance roles)` created atomically in a service-owned transaction with Cognito compensation on failure.
- Member listing is driven from `membership` (RLS-scoped), joined to `app_user`, with Cognito-derived accept status (`pending` / `accepted`). Never queried bare from `app_user`.

### Governance role management
- Full assignment lifecycle: assign, revoke, list by tenant, list by member. SoD enforced at assignment via `assert_governance_assignable()`.
- Read-only catalogue endpoint returns all five roles and the full conflict matrix.

### Reference data (read-only, cross-tenant)
- Product category hierarchy, vendors and products by category, EU AI Act subcategory list. All global; no tenant scoping.
- Seeded: control library (ISO 42001 / EU AI Act with cross-map), risk library (OWASP LLM Top 10 + NIST/ISO governance layer with risk-to-control links), EU AI Act taxonomy (categories, subcategories, tiers, legal refs), product category taxonomy, and the governance role catalogue.

### Platform (operator-facing)
- Tenant provisioning: creates tenant + owner in Cognito and DB, orphan-free.
- Tenant listing and operator identity endpoints.

### Audit trail
- **Tenant plane** (`AuditEvent`): append-only, RLS-scoped. Used by classification snapshots, overrides, governance grant/revoke, and member creation. Postgres trigger enforces immutability at the DB level.
- **Platform plane** (`PlatformAuditEvent`): operator-attributed. Used by tenant provisioning.

---

## 4. Established patterns

### Adding a tenant endpoint
1. Router in `app/routers/v1/`; registered in `app/main.py` under `/v1`.
2. Gate with `get_tenant_db` plus either `require_role(...)` or `require_governance_role(...)` — not both.
3. `tenant_id` is always `ctx.tenant_id`, never a request body field.
4. API schemas live in `app/schemas/`, separate from ORM models.

### Services that call external systems (Cognito or otherwise)
Such a service owns its own DB session and must follow this ordering:
```
1. Pre-check in DB  (fail fast before any external call)
2. Optional DB inserts + flush  (uncommitted)
3. External call  → failure → rollback; nothing persisted
4. DB inserts that depend on the external result
5. Stage AuditEvent
6. Commit  → failure → best-effort compensate external; re-raise
```
This pattern is implemented in `provision_tenant` and `provision_member`. Shared Cognito helpers (`create_cognito_user`, `delete_cognito_user`, `get_cognito_user_status`) live in `app/services/cognito_helpers.py`. Reuse them; do not duplicate.

### Auditing
- **Tenant plane**: add an `AuditEvent` to the session and commit it atomically with the business rows. Never commit audit separately.
- **Platform plane**: use `record_platform_event()` from `app/services/audit.py`.
- Action strings follow a `entity.verb` convention (`classification.created`, `classification.overridden`, `governance_role.granted`, `member.created`).

### Classification read / write separation
`resolve_classification()` is pure read and safe to call multiple times. `snapshot_classification()` writes; the caller owns the transaction. Always separate these concerns.

### Provenance (§1.5 pattern)
Every system-proposed value (on `AssessmentItem` or `CatalogueFact`) carries a `ProvenanceConfidence` tag: `AI_SUGGESTED`, `CATALOGUE_CURATED`, `USER_CONFIRMED`, or `USER_AMENDED`. AI-suggested values must never be presented as authoritative. Any override writes a new `AuditEvent`.

---

## 5. Deferred / not yet implemented

The following have model definitions or designed seams but no service or router code.

| Area | What exists | What's missing |
|---|---|---|
| **AIIA / Assessment engine** | `Assessment`, `AssessmentItem`, control and evidence link models | Create/read/update flows; tier-based section scoping |
| **FRIA / DPIA / Model risk** | `Assessment` subtype model (`parent_aiia_id`) | Creation, linking to AIIA |
| **Lifecycle state machine** | `LifecycleState` enum, `LifecycleTransition` model; use cases created in `REQUESTED` state | Transition logic, gate enforcement, prohibited-practice hard stop |
| **Cascading approval gates** | `VendorApproval` / `ProductApproval` models | Status management, gate reads, cascading logic |
| **Classification context-question wizard** | `REQUIRES_CONTEXT` as the explicit return value | The question flow that resolves a concrete tier from deployment-context answers |
| **Evidence repository** | `Evidence` model (pointer + sha256) | Upload endpoint, S3 wiring, `AssessmentItemEvidence` creation |
| **Review / sign-off workflow** | `AssessmentStatus` enum | Review queue, status transitions, wiring to lifecycle gates |
| **Export / audit pack** | — | Not started |
| **Member deactivation / resend invite** | — | Deferred follow-on; not designed yet |
| **AI-assisted drafting** | `ai_suggested_text` field on `AssessmentItem` | No generation or suggestion flows |
| **Per-object governance roles** | Nullable `scope_id` seam described | Not built; do not add it yet |

---

## 6. Invariants future work must not break

1. **Plane separation.** Tenant and operator tokens must never satisfy each other's verifiers. Never share auth dependencies across planes.
2. **`app_user` reads are membership-driven.** Any user listing in a tenant context joins from `membership`; `app_user` is never queried bare.
3. **`tenant_id` from context, never body.** On every tenant-mutating endpoint, `tenant_id` is `ctx.tenant_id`.
4. **No `BYPASSRLS` for tenant-scoped work.** Tenant services run on the `irontrustai_app` role (`NOBYPASSRLS`).
5. **`AuditEvent` is append-only.** No UPDATE or DELETE at the application layer. The Postgres trigger is the backstop.
6. **Evidence bytes live in S3.** Postgres holds only the pointer (`s3_bucket`, `s3_key`, `s3_version_id`) and `sha256`. Never store file bytes in the DB.
7. **SoD checks go through `assert_governance_assignable()` only.** No inline conflict logic in handlers or new services.
8. **Operator permissions reach operators only through roles.** No direct operator → permission grants.
9. **Cognito is the uniqueness authority for email.** `app_user.email` is not DB-unique by design. Do not add a unique constraint without understanding what Cognito's uniqueness enforcement implies.
10. **Classification tier is never asserted from catalogue facts alone.** Tier comes from deployment context, resolved through the taxonomy bridge. The catalogue informs; it never decides.
11. **Three partial unique indexes are hand-managed in migrations.** `uq_one_aiia_per_use_case`, `uq_current_classification`, `uq_one_primary_eu_mapping` are not generated by Alembic autogenerate. Any migration touching those tables must handle them manually.
