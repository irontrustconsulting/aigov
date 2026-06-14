# Sprint Handoff — Product-Driven System Intake & Prefill

---

## 1. Sprint title

**Product-Driven System Intake & Prefill** (system register enrichment; the intake half of the "product-driven prefill" thesis, PRD §4.3). Precedes the VDD/approval-mutation sprint ("Sprint 5") and the classification context wizard.

---

## 2. Status going in / context

Today, registering an AI system through `POST /v1/systems` captures little more than a name. The `system` table already carries `catalogue_product_id`, `catalogue_vendor_id`, `owner_user_id`, and a `metadata_blob jsonb`, but the API does not populate them and there is no single-system read, update, prefill, or reference-product-detail endpoint.

This sprint makes the register meaningful: the user identifies the actual catalogue product their organisation uses, captures structured intake metadata from controlled vocabularies, and the platform returns the curated facts it already holds about that product (confirm/amend panel data). Custom/in-house systems flow through the same intake with prefill degraded to empty. This sprint is **read-only with respect to catalogue facts and vendor/product approvals** — it surfaces them, it does not mutate them.

This is **additive**. It introduces new reference vocabularies, new columns on an existing table, two link tables, and five endpoints. It does not redesign identity, auth, tenancy, RLS, the classification engine, or the assessment layer.

---

## 3. Baseline & architectural context

### Stack and conventions
- FastAPI, SQLAlchemy ORM, PostgreSQL, Alembic. API schemas live in `app/schemas/`, separate from ORM models. Routers in `app/routers/v1/`, registered in `app/main.py` under `/v1`.
- **Tenant plane** tables are RLS-scoped via a `tenant_isolation` policy keyed on `current_setting('app.current_tenant')`. **Reference data** is global, read-only, cross-tenant, and unscoped.
- **Audit:** tenant-plane `audit_event` is append-only (DB immutability trigger) and committed atomically in the same transaction as the business rows. Action strings follow `entity.verb`. Platform-plane events use `record_platform_event()` — not relevant to this sprint.
- A Postgres enum type `provenance_confidence` exists (`AI_SUGGESTED`, `CATALOGUE_CURATED`, `USER_CONFIRMED`, `USER_AMENDED`).

### Existing tables this sprint reads or extends
- `system` (tenant plane, RLS): `id`, `tenant_id`, `name`, `owner_user_id → app_user (SET NULL)`, `catalogue_vendor_id → catalogue_vendor (SET NULL)`, `catalogue_product_id → catalogue_product (SET NULL)`, `metadata_blob jsonb NOT NULL`, `created_at`, `updated_at`. Policy `tenant_isolation`. Referenced by `use_case (ON DELETE CASCADE)`.
- `catalogue_fact` (global): `id`, `product_id → catalogue_product (CASCADE)`, `key`, `value jsonb`, `source_url`, `source_label`, `last_checked_at`, `provenance provenance_confidence NOT NULL`, timestamps.
- `catalogue_product`, `catalogue_vendor`, `product_category`, `product_category_membership`, `product_category_eu_mapping`, `eu_ai_act_subcategory` (global): existing catalogue + classification bridge.
- `use_case` (tenant plane): `system_id → system (CASCADE)`, carries lifecycle state.
- `vendor_approval`, `product_approval` (tenant plane): **exist; untouched this sprint.**

### Existing endpoints (do not duplicate)
```
GET  /v1/systems
POST /v1/systems                         ← expand
GET  /v1/reference/product-categories
GET  /v1/reference/product-categories/{category_id}/vendors
GET  /v1/reference/product-categories/{category_id}/products
GET  /v1/reference/eu-ai-act/subcategories
POST /v1/use-cases  (+ classify/override)
```

### Classification interaction
The bridge `system.catalogue_product_id → product_category → eu_ai_act_subcategory` resolves a tier at **use-case creation**, which is unchanged. This sprint only populates `catalogue_product_id`, making the bridge traversable for *future* use cases. `resolve_classification()` is a pure read; `snapshot_classification()` writes. **Neither is invoked by this sprint** — registration creates a system, not a use case.

---

## 4. Goal / contract

Deliver five endpoints and the supporting schema so that:

1. A user can register a system linked to a catalogue product (or flagged custom), with structured intake metadata drawn from controlled vocabularies.
2. The platform returns curated catalogue facts for a linked product, with full provenance, for the confirm/amend UX.
3. A user can read full system detail and update system metadata after registration.
4. A user can fetch reference product detail (vendor + taxonomy) for the selection wizard.
5. Systems without a catalogue product degrade gracefully — same metadata capture, empty prefill — with no branch in the product depending on catalogue coverage.

---

## 5. Domain model / rules

### New reference (vocabulary) tables — global, read-only, seeded
Common columns for each: `id uuid pk`, `code varchar(80) unique not null`, `label varchar(255) not null`, `description text null`, `sort_order int not null default 0`, `active boolean not null default true`, `framework_ref varchar(120) null`, `created_at`, `updated_at`. **No `tenant_id`, no RLS.** Select-only; **tenants cannot create vocabulary entries.**

| Table | Extra column | Seed `code`s | `framework_ref` |
|---|---|---|---|
| `operator_role` | — | `provider`, `deployer`, `importer`, `distributor` | EU AI Act Art. 3 |
| `hosting_model` | — | `cloud_saas`, `self_hosted`, `on_premise`, `hybrid`, `edge` | null |
| `usage_context` | — | `internal_only`, `employee_facing`, `customer_facing`, `public_facing` | null |
| `human_oversight_type` | — | `human_in_the_loop`, `human_on_the_loop`, `human_in_command`, `fully_autonomous` | EU AI Act Art. 14 |
| `data_category` | `is_special_category boolean not null default false` | special (`is_special_category=true`): `health`, `genetic`, `biometric_id`, `racial_ethnic_origin`, `political_opinions`, `religious_philosophical_beliefs`, `trade_union_membership`, `sex_life_sexual_orientation`; general (`false`): `identifiers`, `contact_details`, `financial_data`, `location_data`, `behavioural_data`, `employment_data` | EU AI Act / GDPR Art. 9 (special only) |
| `affected_party` | `is_vulnerable_group boolean not null default false` | `employees`, `job_applicants`, `customers_service_users`, `general_public`, `children` (`is_vulnerable_group=true`), `vulnerable_individuals` (`true`) | EU AI Act Art. 27 |

### New columns on `system` (additive)
| Column | Type | Null | Notes |
|---|---|---|---|
| `operator_role_id` | uuid | yes | FK `operator_role`, `ON DELETE SET NULL` |
| `hosting_model_id` | uuid | yes | FK `hosting_model`, `ON DELETE SET NULL` |
| `usage_context_id` | uuid | yes | FK `usage_context`, `ON DELETE SET NULL` |
| `human_oversight_type_id` | uuid | yes | FK `human_oversight_type`, `ON DELETE SET NULL` |
| `lifecycle_stage` | enum | yes | new Postgres enum `system_lifecycle_stage`: `development`, `pilot`, `production`, `retired` |
| `is_custom` | boolean | no | default `false` |

`purpose` (free text) is written to `metadata_blob` under documented key `purpose`. No new prose columns.

### New link tables — tenant plane, RLS
- `system_data_category`: `system_id → system (CASCADE)`, `data_category_id → data_category`, `tenant_id uuid not null`, unique `(system_id, data_category_id)`, RLS `tenant_isolation`.
- `system_affected_party`: `system_id → system (CASCADE)`, `affected_party_id → affected_party`, `tenant_id uuid not null`, unique `(system_id, affected_party_id)`, RLS `tenant_isolation`.

`tenant_id` is denormalised from the parent system at write time for defence-in-depth RLS. (See Decision Note D-4 — match the existing `assessment_item_*` link-table convention if it differs.)

### Invariants
1. **Catalogue-or-custom.** DB check constraint: `is_custom = true ⟹ catalogue_product_id IS NULL AND catalogue_vendor_id IS NULL`.
2. **Vendor/product coherence.** When `catalogue_product_id` is set, the service derives and sets `catalogue_vendor_id` from that product's vendor; client-supplied vendor is ignored when a product is present. Vendor-only (product null, vendor set) is legal for "known vendor, uncatalogued product."
3. **Active vocab only.** Every supplied vocab FK / link id must reference an `active = true` seed row; reject otherwise (422).
4. **Owner membership.** `owner_user_id`, when supplied, must correspond to an `app_user` with a `membership` in `ctx.tenant_id` (service-layer pre-check; the FK to global `app_user` cannot enforce this).
5. **Product relink lock.** `PATCH` may not change `catalogue_product_id` when the system already has any `use_case` rows. Reject (409). Reclassification-on-relink is deferred.
6. **Prefill is not 404.** Prefill on a custom/no-product system returns `200` with `[]`.
7. **RLS visibility.** Any read/write targeting a system outside `ctx.tenant_id` resolves to `404` via RLS.

---

## 6. Work items

| # | Item | Surface |
|---|---|---|
| W1 | Migration: 6 vocab tables + `system_lifecycle_stage` enum + seed data | Alembic |
| W2 | Migration: `system` new columns + check constraint + 2 link tables + RLS policies | Alembic |
| W3 | ORM models for vocab tables, link tables, and `system` column additions | `app/models/` |
| W4 | API schemas: `SystemCreate`, `SystemUpdate`, `SystemDetail`, `CatalogueFactOut`, `PrefillResponse`, `ApprovalNotUsed` (n/a), `ProductDetailOut`, vocab `*Out` | `app/schemas/` |
| W5 | Service: `system_service` (create/update/read with derivation + validations + atomic `audit_event`) | `app/services/` |
| W6 | Service: `prefill_service` (pure read of `catalogue_fact` by product) | `app/services/` |
| W7 | Service: reference product-detail read (vendor + taxonomy) | `app/services/` |
| W8 | Expand `POST /v1/systems`; add `GET`/`PATCH /v1/systems/{id}`, `GET /v1/systems/{id}/prefill` | `app/routers/v1/` |
| W9 | Add `GET /v1/reference/products/{id}` to the existing reference router | `app/routers/v1/` |
| W10 | Register any new router in `app/main.py` under `/v1` | `app/main.py` |
| W11 | Tests: migration up/down, RLS isolation, constraints, endpoint contracts, seed verification, regression on existing `POST /v1/systems` | `tests/` |

---

## 7. Constraints / non-negotiables

- **Tenant endpoints** gate with `get_tenant_db` **plus exactly one** of `require_role(...)` or `require_governance_role(...)` — never both. The new `/v1/systems/{id}` endpoints **inherit the gate already on `POST /v1/systems`**; do not re-decide it.
- `tenant_id` is **always** `ctx.tenant_id`, **never** a request-body field.
- API schemas in `app/schemas/`, distinct from ORM models.
- **Tenant audit is atomic.** Add the `audit_event` to the same session and commit it with the business rows. Never commit audit separately. Reads emit **no** audit.
- Action strings: `system.created`, `system.updated`. (`entity.verb`.)
- **No external system calls.** The Cognito 6-step ordering does **not** apply; do not import or imitate it.
- **Do not call** `resolve_classification()` or `snapshot_classification()`; this sprint does not touch classification.
- **Catalogue facts are never authoritative.** Prefill returns them with their `provenance` and source metadata intact. No write-back, no provenance transition this sprint.
- Vocab tables are **global, read-only, select-only.** No tenant vocabulary creation.
- Preserve existing RLS, FK `ON DELETE` semantics, and the immutability trigger. Do not weaken any.

---

## 8. Acceptance criteria

**Registration — `POST /v1/systems`**
- [ ] Accepts optional `catalogue_product_id`, `owner_user_id`, `operator_role_id`, `hosting_model_id`, `usage_context_id`, `human_oversight_type_id`, `lifecycle_stage`, `is_custom`, `data_category_ids[]`, `affected_party_ids[]`, `purpose`; plus existing `name`.
- [ ] `tenant_id` is taken from context, not the body; a body `tenant_id` is ignored/rejected.
- [ ] When `catalogue_product_id` is set, `catalogue_vendor_id` is derived from the product's vendor and persisted; a conflicting client vendor is overridden.
- [ ] `is_custom = true` with any catalogue FK set is rejected (422) by validation and impossible at DB level (check constraint).
- [ ] Inactive or non-existent vocab ids are rejected (422).
- [ ] `owner_user_id` not a member of the tenant is rejected (422).
- [ ] On success, one `audit_event` with action `system.created` is committed atomically with the system and link rows.
- [ ] Existing minimal payload (`name` only) still succeeds — no regression.

**Read — `GET /v1/systems/{id}`**
- [ ] Returns full metadata, resolved vocab `label`s, `is_custom`, linked product name and vendor name (null when absent), use-case count, and per-use-case lifecycle states.
- [ ] A system in another tenant returns `404`.

**Update — `PATCH /v1/systems/{id}`**
- [ ] Updates supplied metadata fields and link sets; emits one `system.updated` audit event atomically.
- [ ] Changing `catalogue_product_id` when use cases exist returns `409`.
- [ ] Re-derives `catalogue_vendor_id` if the product changes (and no use cases exist).

**Prefill — `GET /v1/systems/{id}/prefill`**
- [ ] Linked product → returns all `catalogue_fact` rows with `key`, `value`, `source_url`, `source_label`, `last_checked_at`, `provenance`.
- [ ] No product / custom → `200` with `[]` (not `404`).
- [ ] Emits no audit event.

**Reference — `GET /v1/reference/products/{id}`**
- [ ] Returns product `id`, `name`, `vendor {id, name}`, category tags, and mapped EU AI Act subcategories.
- [ ] Unknown id → `404`.

**Cross-cutting**
- [ ] Migration applies and rolls back cleanly; all six vocabularies seed with the exact `code`s in §5.
- [ ] Link tables enforce tenant isolation under RLS (a cross-tenant session cannot read another tenant's selections).

---

## 9. Out of scope

- **VDD / approval status** — no `GET /v1/systems/{id}/approval-status`, no mutations. `vendor_approval` / `product_approval` are untouched. (Sprint 5.)
- **Confirm/amend write-back** of catalogue facts and any `USER_CONFIRMED` / `USER_AMENDED` provenance transition. Prefill is display-only.
- **Classification context wizard** (`REQUIRES_CONTEXT` resolution).
- **Per-use-case overrides** of operator role and human oversight type (captured at system level only).
- **Contextual vulnerability** modelling beyond the inherent `is_vulnerable_group` flag.
- **Reclassification on product relink** (relink is locked when use cases exist).
- **System-level assessment-coverage rollup.**
- **Tenant-created vocabulary** of any kind.

---

## 10. Dependencies / decision notes

- **D-1 — Deployment is three dimensions, not one.** `operator_role`, `hosting_model`, and `usage_context` are orthogonal axes (legal posture / where it runs / who it's exposed to) and are modelled as three separate single-select vocabularies. Do not collapse them.
- **D-2 — Vocab-backed selections are relational, prose is blob.** Single-selects are typed FK columns; multi-selects (`data_category`, `affected_party`) are link tables; `purpose` is free text in `metadata_blob`. This preserves FK integrity and join-ability for the DPIA/FRIA sprints. Do not store vocab selections as JSON arrays in the blob.
- **D-3 — `affected_party` brought forward deliberately.** Its structure is committed now so the FRIA sprint is plumbing; its seed is a conservative, **additive-safe** core. The FRIA sprint may **extend** the seed but must not rename/remove seeded `code`s (that would orphan tenant selections).
- **D-4 — Link-table RLS convention.** Spec adds `tenant_id` + `tenant_isolation` to the link tables. If the existing `assessment_item_control` / `assessment_item_evidence` tables rely on parent-scoping instead of a denormalised `tenant_id`, follow that existing convention for consistency.
- **D-5 — `owner_user_id` FKs global `app_user`.** Tenancy is enforced in the service, not the FK.
- **D-6 — Convention facts to confirm from the codebase before writing W3/W2:** the ORM `Base` / timestamp + tenant mixins, how RLS policies are declared in migrations, and the existing reference-data seed mechanism (data migration vs seed script vs fixtures). Match them; do not introduce a new pattern.

---

## 11. Implementation contract

### Request — `POST /v1/systems` (`SystemCreate`)
```jsonc
{
  "name": "string (required)",
  "is_custom": false,
  "catalogue_product_id": "uuid|null",
  "catalogue_vendor_id": "uuid|null",   // ignored when product present; derived
  "owner_user_id": "uuid|null",
  "operator_role_id": "uuid|null",
  "hosting_model_id": "uuid|null",
  "usage_context_id": "uuid|null",
  "human_oversight_type_id": "uuid|null",
  "lifecycle_stage": "development|pilot|production|retired|null",
  "data_category_ids": ["uuid", "..."],
  "affected_party_ids": ["uuid", "..."],
  "purpose": "string|null"
}
```

### Request — `PATCH /v1/systems/{id}` (`SystemUpdate`)
All fields optional; same shape. `catalogue_product_id` change rejected (409) if use cases exist. Link arrays, when present, **replace** the existing set.

### Response — `GET /v1/systems/{id}` (`SystemDetail`)
```jsonc
{
  "id": "uuid",
  "name": "string",
  "is_custom": false,
  "catalogue_product": { "id": "uuid", "name": "string" } | null,
  "catalogue_vendor":  { "id": "uuid", "name": "string" } | null,
  "owner_user_id": "uuid|null",
  "operator_role":       { "id": "uuid", "code": "string", "label": "string" } | null,
  "hosting_model":       { "id": "uuid", "code": "string", "label": "string" } | null,
  "usage_context":       { "id": "uuid", "code": "string", "label": "string" } | null,
  "human_oversight_type":{ "id": "uuid", "code": "string", "label": "string" } | null,
  "lifecycle_stage": "string|null",
  "data_categories": [ { "id": "uuid", "code": "string", "label": "string", "is_special_category": true } ],
  "affected_parties": [ { "id": "uuid", "code": "string", "label": "string", "is_vulnerable_group": false } ],
  "purpose": "string|null",
  "use_case_count": 0,
  "use_case_lifecycle_states": [ { "use_case_id": "uuid", "state": "string" } ],
  "created_at": "ts", "updated_at": "ts"
}
```

### Response — `GET /v1/systems/{id}/prefill` (`PrefillResponse`)
```jsonc
{
  "catalogue_product_id": "uuid|null",
  "facts": [
    {
      "key": "string",
      "value": { },                 // jsonb passthrough
      "source_url": "string|null",
      "source_label": "string|null",
      "last_checked_at": "ts|null",
      "provenance": "AI_SUGGESTED|CATALOGUE_CURATED|USER_CONFIRMED|USER_AMENDED"
    }
  ]
}
```
`facts` is `[]` when no product is linked.

### Response — `GET /v1/reference/products/{id}` (`ProductDetailOut`)
```jsonc
{
  "id": "uuid",
  "name": "string",
  "vendor": { "id": "uuid", "name": "string" },
  "categories": [ { "id": "uuid", "name": "string" } ],
  "eu_ai_act_subcategories": [ { "id": "uuid", "code": "string", "label": "string" } ]
}
```

### Service ordering — `system_service.create` / `.update`
```
1. Resolve ctx.tenant_id.
2. Pre-checks (fail fast, 422/409 before any write):
   - is_custom vs catalogue FK invariant
   - owner_user_id ∈ tenant membership (if supplied)
   - all vocab / link ids exist and are active
   - (update) product change blocked if use_cases exist
3. Derive catalogue_vendor_id from product when product present.
4. Upsert system row + replace link rows.
5. Write metadata_blob (purpose, etc.).
6. Stage audit_event (system.created | system.updated) in the SAME session.
7. Commit atomically.
```
Reads (`prefill`, reference product) own a read-only session and stage no audit.

---

## 12. Execution protocol

1. **Inspect conventions first (D-6).** Read one existing tenant-plane model, one existing Alembic migration (note RLS policy declaration + immutability trigger), and the current reference-seed mechanism. Mirror them.
2. **W1 migration** — create the `system_lifecycle_stage` enum and the six vocab tables; seed them with the exact `code`s in §5. Reference tables: no `tenant_id`, no RLS.
3. **W2 migration** — add the `system` columns + check constraint; create the two link tables with `tenant_id`, unique constraints, FKs, and the `tenant_isolation` RLS policy (per D-4). Backfill legacy `system` rows: `is_custom = false`, new FKs/links null.
4. **W3 models** — vocab models, link models, and `system` column additions, using the existing Base/mixins.
5. **W4 schemas** — request/response models in `app/schemas/` per §11; never reuse ORM models as schemas.
6. **W5–W7 services** — `system_service` (ordering in §11), `prefill_service`, reference product read. Reuse existing membership/lookup helpers; do not duplicate.
7. **W8–W10 routers** — expand `POST /v1/systems`; add `GET`/`PATCH /v1/systems/{id}` and `/prefill` under the gate inherited from `POST /v1/systems`; add `GET /v1/reference/products/{id}` to the existing reference router following its auth pattern; register in `app/main.py` if a new router module is introduced.
8. **W11 tests** — see §13.

Stop and surface a question rather than invent if any item in D-6 cannot be confirmed from the codebase.

---

## 13. Validation protocol

**Migration**
- `alembic upgrade head` then `alembic downgrade -1` (twice) applies and reverts cleanly with no orphaned objects.
- Seed assertion: each vocabulary contains exactly the §5 `code`s; `data_category` special rows have `is_special_category = true`; `affected_party` `children` and `vulnerable_individuals` have `is_vulnerable_group = true`.

**RLS / isolation**
- A session set to tenant A cannot read tenant B's `system`, `system_data_category`, or `system_affected_party` rows.
- Vocab tables are readable without a tenant context (global).

**Constraints**
- Inserting a `system` with `is_custom = true` and a non-null catalogue FK fails at the DB (check constraint).
- Duplicate `(system_id, data_category_id)` / `(system_id, affected_party_id)` insertion fails (unique).

**Endpoint contracts**
- `POST` with full payload → 201, correct derivation, one `system.created` audit row, link rows present.
- `POST` minimal (`name` only) → 201 (regression guard).
- `POST` with inactive vocab id / non-member owner / `is_custom`+product → 422.
- `GET {id}` cross-tenant → 404; same-tenant → full detail with resolved labels and use-case rollup.
- `PATCH` product change with existing use cases → 409; without → re-derives vendor, one `system.updated` audit row.
- `prefill` linked product → fact list with provenance; custom → `200 []`; no audit row written.
- `reference/products/{id}` → product + vendor + taxonomy; unknown → 404.

**Audit integrity**
- Exactly one audit row per successful create/update; none on any read; the immutability trigger still rejects updates/deletes to `audit_event`.

**Definition of done:** all §8 acceptance criteria checked, all §13 validations green, no modification to `vendor_approval`, `product_approval`, the classification engine, or existing auth/tenancy primitives.