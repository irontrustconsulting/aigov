# DATA-MODEL.md — IronTrust AI Governance Platform

**Location:** `docs/DATA-MODEL.md` — single source, mirrored to project knowledge. **Updated each sprint** (the model map's only home now that `app/models/MODELS.md` is removed).
**Purpose:** The structural schema map and the DB-enforced-guarantee catalogue — every table's plane and RLS status, the enums and their label landmines, the manually-managed indexes and constraints, each linked to the `INV-n` it backs.
**Scope (deliberate):** structure + guarantees, **not** a column-by-column dump. Columns drift fastest and the **ORM models in `app/models/` are their authoritative source** (D-21). Read the model for columns; read this for shape, plane, RLS, enums, indexes, and guarantees. Conceptual relationships → `DOMAIN.md`.

**Authoritative inventory:** the table list below is the live `\dt` output (52 tables). Model-file attributions are confirmed against CLAUDE §3.1 where marked, and flagged `verify` where the table post-dates that map.

**Legend** — Plane / RLS:
- `TENANT` — tenant-scoped, carries `tenant_id`, under RLS.
- `GLOBAL` — global reference data, no `tenant_id`, no RLS, cross-tenant (INV-48).
- `IDENTITY` — global, non-RLS, but not reference data; read membership-driven (INV-2).
- `LINK` — junction with **no RLS**; isolation depends on the access path (see §5), not on RLS.
- `PLATFORM` — operator plane.
- `SYSTEM` — framework-owned (Alembic).

---

## 1. Tables by area

### Identity & tenancy — `identity.py` (confirmed)
| Table | Plane | Notes |
|---|---|---|
| `tenant` | TENANT (RLS) | Created only by `provision_tenant()` (D-23). RLS scopes a tenant to its own row. |
| `app_user` | IDENTITY | Global, non-RLS; linked to Cognito via `cognito_sub`; email not DB-unique (INV-9). Never read bare (INV-2, 34). |
| `membership` | TENANT (RLS) | Unit of authorisation. `role` = `UserRole` (ADMIN/MEMBER), administrative axis only. |

### Catalogue — `domain.py` (confirmed)
| Table | Plane | Notes |
|---|---|---|
| `catalogue_vendor` | GLOBAL | `logo_url varchar` column present (nullable). Plumbed to `CatalogueVendorRef.logo_url` in `ProductDetailOut` response (UI-C2, additive — no DDL change). |
| `catalogue_product` | GLOBAL | Belongs to a vendor. `logo_url varchar` column present (nullable). Plumbed to `ProductDetailOut.logo_url` (UI-C2, additive — no DDL change). Assets at `apps/tenant/public/logos/<slug>.png`; seeded via `scripts/seed/seed_logos.py` (D-55). |
| `catalogue_fact` | GLOBAL | Prefill facts with provenance (CAT-4); facts only, never tier (D-8). |
| `catalogue_product_risk` | GLOBAL | Typical risks per product (RSK-4). |

### Register — `domain.py` + link tables
| Table | Plane | Notes |
|---|---|---|
| `system` | TENANT (RLS) | Check constraint `ck_system_custom_no_catalogue` (is_custom + catalogue FK rejected). Deployment-stable fields only: `operator_role_id`, `hosting_model_id`, `catalogue_product_id`, `lifecycle_stage`. `usage_context_id` and `human_oversight_type_id` removed in DM-S1 (D-63). |
| `use_case` | TENANT (RLS) | Carries `state` (`LifecycleState`) and `eu_tier`. `state` written only by `apply_transition` (INV-24). **DM-S1:** gains `usage_context_id` (FK `usage_context`, SET NULL) and `human_oversight_type_id` (FK `human_oversight_type`, SET NULL) — use-distinguishing context (D-63). |
| `use_case_data_category` | TENANT (RLS) | **DM-S1 addition.** Link `use_case ↔ data_category`. `tenant_id` FK; RLS policy `tenant_id = current_setting('app.current_tenant', true)::uuid`; unique `(use_case_id, data_category_id)`. Isolation via RLS (INV-77). |
| `use_case_affected_party` | TENANT (RLS) | **DM-S1 addition.** Link `use_case ↔ affected_party`. Same shape and RLS policy as `use_case_data_category` (INV-77). |

### Draft registrations — `domain.py` (DM-S3)
| Table | Plane | Notes |
|---|---|---|
| `draft_registration` | TENANT (RLS) | **DM-S3 addition.** Server-side draft staging for the registration wizard. `UniqueConstraint(tenant_id, owner_user_id)` enforces one active draft per user (`uq_draft_one_per_user`). RLS policy `tenant_isolation` scopes to `current_setting('app.current_tenant', true)::uuid`; application layer additionally filters `owner_user_id = ctx.user_id` (DF-D3-4). `draft_blob JSONB` stores pre-boundary wizard fields + clamped step cursor. CASCADE FKs to `tenant` and `app_user`. `updated_at` managed by trigger. INV-79, D-66. |

### Approvals — `domain.py` (confirmed)
| Table | Plane | Notes |
|---|---|---|
| `vendor_approval` | TENANT (RLS) | Tenant's clearance of a global vendor. Status = `ApprovalStatus`. |
| `product_approval` | TENANT (RLS) | Tenant's clearance of a global product. |

### Classification & decision tree
| Table | Plane | Notes |
|---|---|---|
| `classification` | TENANT (RLS) — `assessment.py` (confirmed) | Versioned snapshots (`version`/`is_current`); status = `classification_status`. Partial unique `uq_current_classification`. |
| `decision_tree` | GLOBAL | Versioned context-question gate; content-hashed, fails loud on frozen-version mutation. *(file: verify)* |
| `decision_tree_question` | GLOBAL | *(file: verify)* |
| `decision_tree_option` | GLOBAL | *(file: verify)* |

### Assessment — `assessment.py` (confirmed; `assessment_review` is S6a drift)
| Table | Plane | Notes |
|---|---|---|
| `assessment` | TENANT (RLS) | AIIA and feeders share this table; feeder = `parent_aiia_id` set. Self-ref `ON DELETE CASCADE` + `passive_deletes` (INV-47). Status = `AssessmentStatus`; `submission_round` cycle key (INV-37). |
| `assessment_item` | TENANT (RLS) | Provenance = `ProvenanceConfidence`; `lock_version` concurrency (INV-14). `risk_id` FK is RESTRICT (INV-46). `AssessmentItemRead` carries two batch-loaded virtual fields: `control_links: list[ControlLinkRead]` (DF3-7) and `evidence_links: list[ItemEvidenceRead]` (DF5-8, UI-F5-EVIDENCE) — both computed in `assemble_aiia_items`, no N+1. |
| `assessment_item_control` | TENANT (RLS) | `control_id` FK RESTRICT (INV-46). |
| `assessment_item_evidence` | TENANT (RLS) | `UNIQUE(item_id, evidence_id)`; `ON DELETE CASCADE` (INV-19, 20). |
| `assessment_review` | TENANT (RLS) | One row per review decision; `decision` = `ReviewDecision`; `CHECK` note non-null when `CHANGES_REQUESTED`. Append-only by convention (no trigger). |
| `assessment_section_template` | GLOBAL | Keyed `(type, tier, section_key)`; seeded via YAML, not migration. |

### Evidence & lifecycle — `lifecycle.py` (confirmed; `deployment_authorisation` is S6b drift)
| Table | Plane | Notes |
|---|---|---|
| `evidence` | TENANT (RLS) | Pointer-only — bytes in S3 (INV-6); `sha256`, `s3_version_id`. `expires_at` present, unused. |
| `audit_event` | TENANT (RLS) | **Append-only, trigger-enforced** (INV-5). `actor_user_id` FK RESTRICT; no durable name/email (D-25). |
| `lifecycle_transition` | TENANT (RLS) | Staged by `apply_transition`. |
| `deployment_authorisation` | TENANT (RLS) | The ATO. Point-in-time, never mutated (INV-32); stamps `tier`/identity as text (D-13, D-14). `assessment_id` FK RESTRICT. |

### Knowledge libraries — `knowledge.py` (confirmed)
| Table | Plane | Notes |
|---|---|---|
| `control` | GLOBAL | ISO 42001 / EU AI Act. |
| `control_framework_map` | GLOBAL | Cross-map; one evidence satisfies both frameworks (CTL-2). |
| `risk` | GLOBAL | `layer` = `RiskLayer`, `source` = `RiskSource`. |
| `risk_control_map` | GLOBAL | Risk → mitigating control links. |

### Taxonomy — `taxonomy.py` (confirmed)
| Table | Plane | Notes |
|---|---|---|
| `eu_ai_act_category` | GLOBAL | |
| `eu_ai_act_subcategory` | GLOBAL | `tier` = `EUAIActTier`. |
| `product_category` | GLOBAL | |
| `product_category_membership` | GLOBAL | Product ↔ category. |
| `product_category_eu_mapping` | GLOBAL | Partial unique `uq_one_primary_eu_mapping` (one primary). The classification bridge path. |

### Controlled vocabulary — `intake.py` (confirmed)
| Table | Plane | Notes |
|---|---|---|
| `eu_operator_role` | GLOBAL | EU AI Act Art. 3 postures. Named to avoid collision with platform `operator_role`. `GET /v1/reference/operator-roles` (UI-F1-INTAKE WI-0). |
| `hosting_model` | GLOBAL | `GET /v1/reference/hosting-models` (UI-F1-INTAKE WI-0). |
| `usage_context` | GLOBAL | `GET /v1/reference/usage-contexts` (UI-F1-INTAKE WI-0). |
| `human_oversight_type` | GLOBAL | EU AI Act Art. 14. `GET /v1/reference/human-oversight-types` (UI-F1-INTAKE WI-0). |
| `data_category` | GLOBAL | `is_special_category` flag (GDPR/EU AI Act). `GET /v1/reference/data-categories` (UI-F1-INTAKE WI-0). |
| `affected_party` | GLOBAL | `is_vulnerable_group` flag (Art. 27). `GET /v1/reference/affected-parties` (UI-F1-INTAKE WI-0). |

### Governance roles *(file: verify — none in CLAUDE §3.1)*
| Table | Plane | Notes |
|---|---|---|
| `governance_role` | GLOBAL | The five-role catalogue (DOMAIN §7). |
| `governance_role_conflict` | GLOBAL | The SoD matrix as policy-as-data (9 rows). Enforced via `assert_governance_assignable` (INV-7). |
| `governance_role_assignment` | TENANT (RLS) | Tenant-scoped grants; nullable `scope_id` seam reserved (D-22, unbuilt). |

### Platform RBAC — `platform_rbac.py` (confirmed; `platform_audit_event` to verify placement)
| Table | Plane | Notes |
|---|---|---|
| `operator` | PLATFORM | `status` = `OperatorStatus`. |
| `permission` | PLATFORM | |
| `role` | PLATFORM | |
| `role_permission` | PLATFORM | Permissions reach operators only through roles (INV-8). |
| `operator_role` | PLATFORM | Operator ↔ role. `granted_by_id` NULL = genesis bootstrap; non-NULL = granting operator's id. |
| `platform_audit_event` | PLATFORM | Operator-attributed audit (provisioning). |

**Platform RBAC seed rows** (deployment data, migration-embedded per `DF8-1`):
| Entity | Key | Seeded by |
|---|---|---|
| `permission` | `tenant:provision` | `cef7211ddfe4` |
| `permission` | `operator:create` | `c8f3a2e91bd5` (UI-F8) |
| `role` | `provisioner` | `cef7211ddfe4` |
| `role` | `platform_admin` | `c8f3a2e91bd5` (UI-F8) |
| `role_permission` | `provisioner` → `tenant:provision` | `cef7211ddfe4` |
| `role_permission` | `platform_admin` → `tenant:provision` | `c8f3a2e91bd5` (UI-F8) |
| `role_permission` | `platform_admin` → `operator:create` | `c8f3a2e91bd5` (UI-F8) |

### Framework-owned
| Table | Plane | Notes |
|---|---|---|
| `alembic_version` | SYSTEM | Alembic migration cursor. |

---

## 2. Enums

Authoritative inventory from live `pg_enum` — 17 types, all labels **UPPERCASE member names** (see case note below).

| Type | Labels (sort order) | Backs / notes |
|---|---|---|
| `approval_status` | NOT_STARTED, UNDER_REVIEW, APPROVED, REJECTED, EXPIRED | `vendor_approval`, `product_approval` |
| `assessment_status` | DRAFT, IN_REVIEW, APPROVED, NEEDS_REFRESH | `assessment` (WKF-3) |
| `assessment_type` | AIIA, FRIA, DPIA, MODEL_RISK | `assessment.type`, `assessment_section_template.type` |
| `classification_status` | PENDING_REVIEW, APPROVED, CHANGES_REQUESTED, NEEDS_REFRESH | `classification` |
| `coverage_status` | OPEN, PARTIAL, SATISFIED | `assessment_item_control` |
| `eu_ai_act_tier` | PROHIBITED, HIGH, LIMITED, MINIMAL, UNCLASSIFIED, REQUIRES_CONTEXT | shared: `use_case.eu_tier`, `classification.tier`, `eu_ai_act_subcategory.tier`, `assessment_section_template.tier`. UNCLASSIFIED / REQUIRES_CONTEXT are resolution states beyond the four DOMAIN tiers |
| `framework` | ISO_42001, ISO_42005, EU_AI_ACT, NIST_AI_RMF | NIST reserved (out of MVP scope) |
| `lifecycle_state` | REQUESTED, VENDOR_CHECK, PRODUCT_CHECK, INTAKE, HALTED_PROHIBITED, UNDER_ASSESSMENT, TREATMENT_PENDING, PENDING_AUTHORISATION, AUTHORISED, DEPLOYED, HELD, RETIRED | `use_case.state` (DOMAIN §6). DEPLOYED/RETIRED reserved-unwired. **Sort order ≠ lifecycle progression** |
| `operator_status` | ACTIVE, DISABLED | `operator` |
| `provenance_confidence` | AI_SUGGESTED, CATALOGUE_CURATED, USER_CONFIRMED, USER_AMENDED | `assessment_item` (PAT-8) — **4 labels only; no `USER_PROVIDED`** (see §5 flag) |
| `review_decision` | APPROVED, CHANGES_REQUESTED | `assessment_review` |
| `risk_layer` | TECHNICAL_SECURITY, GOVERNANCE_RIGHTS, ADVERSARIAL_THREAT | `risk` (ADVERSARIAL = MITRE ATLAS, post-MVP) |
| `risk_source` | OWASP_LLM, NIST_AI_RMF, ISO_42001, ISO_42005, MITRE_ATLAS, INTERNAL | `risk` |
| `section_applicability` | REQUIRED, RECOMMENDED, NOT_APPLICABLE | `assessment_section_template` |
| `system_lifecycle_stage` | DEVELOPMENT, PILOT, PRODUCTION, RETIRED | `system.lifecycle_stage` |
| `treatment_decision` | MITIGATE, ACCEPT, TRANSFER, AVOID | `assessment_item` (TRANSFER/AVOID reserved) |
| `user_role` | ADMIN, MEMBER | `membership.role` (administrative axis) |

### Label case — RESOLVED (INV-23)
All labels are uniformly UPPERCASE member names in live DDL (verified). The labels that shipped lowercase — `classification_status`, `eu_ai_act_tier.REQUIRES_CONTEXT`, **and `system_lifecycle_stage`** — were all renamed to uppercase in `3a5b36bdd37a`. This **settles the prior STATE contradiction: `system_lifecycle_stage` is fixed** (STATE §5's known-bug entry is stale and is dropped on the STATE rewrite). Durable rule stands: bind through the typed column, never a raw `.value` comparison — the hazard is structural, not a live mismatch (INV-23).

---

## 3. Manually-managed indexes

Hand-written in migrations, skipped by autogenerate (`alembic/env.py` `include_object`):

| Index | Kind | Backs |
|---|---|---|
| `uq_one_aiia_per_use_case` | partial unique | one current AIIA per use case (INV-17) |
| `uq_current_classification` | partial unique | one current `Classification` snapshot per use case |
| `uq_one_primary_eu_mapping` | partial unique | one primary `product_category_eu_mapping` |

`uq_feeder_type_per_aiia` — `UNIQUE(parent_aiia_id, type)`, plain (non-partial), **autogenerate handles it natively** — is *not* in the manually-managed set. It enforces at most one feeder per type per AIIA (relaxable later for multi-component MODEL_RISK — STATE deferred).

---

## 4. DB-enforced guarantees

| Guarantee | Mechanism | INV |
|---|---|---|
| Audit immutability | Postgres trigger + grant (no UPDATE/DELETE) on `audit_event` | INV-5 |
| Evidence is pointer-only | bytes in S3; `sha256`/`s3_version_id` columns only | INV-6 |
| Reference-data FKs block deletion | `ondelete=RESTRICT` on `assessment_item.risk_id`, `assessment_item_control.control_id` | INV-46 |
| Self-referential cascade not masked | `passive_deletes=True` on `Assessment.feeders` (`parent_aiia_id ON DELETE CASCADE`) | INV-47 |
| Global reference tables uncoupled from tenancy | no `tenant_id` column, no RLS policy | INV-48 |
| Tenant isolation | RLS reading `app.current_tenant`; `irontrustai_app` is NOBYPASSRLS | INV-4 |
| Evidence link cascade | `assessment_item_evidence` `ON DELETE CASCADE` + single guarded DELETE | INV-19 |
| Custom-system exclusivity | `ck_system_custom_no_catalogue` check constraint | — |
| Review note required on changes | `CHECK` on `assessment_review` (note non-null when `CHANGES_REQUESTED`) | — |

---

## 5. Drift & verification notes

- **RLS verified live** (`pg_class.relrowsecurity`): the 17 tenant tables are RLS-on; all reference/platform/identity tables are RLS-off — matching the documented rules exactly, with two exceptions below.
- **`system_data_category` / `system_affected_party` dropped in DM-S1.** Both tables and their FKs on `system` (`usage_context_id`, `human_oversight_type_id`) were removed by migration `d82c389d1f07_context_relocation_use_case`. The replacement tables (`use_case_data_category`, `use_case_affected_party`) carry their own `tenant_id` FK and are independently RLS-protected (INV-77, D-63). The prior unresolved isolation question for the old junction tables is now closed: the new tables are correctly RLS-isolated by design.
- **`provenance_confidence` is 4-value by design — confirmed V-2 (UI-V0-VISUAL-FOUNDATION).** `USER_PROVIDED` was considered and **not** added; the four live labels are `AI_SUGGESTED`, `CATALOGUE_CURATED`, `USER_CONFIRMED`, `USER_AMENDED`. Register-derived facts are handled without a `USER_PROVIDED` tag. `PAT-8` is the authoritative implementation shape. No fifth label exists in `pg_enum` and none must be added without a design-review decision.
- **~16 tables post-date CLAUDE §3.1's map** (the six vocab tables, the three decision-tree tables, the three governance-role tables, `assessment_review`, `deployment_authorisation`, `use_case_data_category`, `use_case_affected_party`). This file is now their only documented home — keep it current each sprint.
- **Column detail is intentionally absent** — read the ORM models. If a column-level map is ever wanted, generate it from the models, never hand-maintain it here.
- **`UI-F0-FOUNDATION` touched no schema/DB.** The sprint's one backend addition, `GET /v1/me`, is a read-only composition over `membership`/`governance_role`/`governance_role_assignment` (all pre-existing) — no migration, no new table, no new enum.
- **`MeRead` gains `tenant_name: str` (UI-C1-PORTFOLIO-IDENTITY).** Read-only response-schema composition from `tenant.name` at handler time (`db.get(Tenant, ctx.tenant_id).name` on the existing RLS session — M-1 confirmed). No migration; no new table, enum, or route. Precedent: `DF3-7` (additive response-schema field, non-breaking, distinct from a DB/route/enum delta).
- **`UI-F9-MEMBERS` — 0 migrations.** Pure frontend surface over pre-existing routes. No new table, enum, index, migration, schema field, or backend route. The tenant-wide `GET /governance-roles/assignments` and per-member route both existed at HEAD (P5/P6 confirmed). `assert_governance_assignable` was read-only and not modified.