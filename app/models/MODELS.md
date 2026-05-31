# AI Governance MVP — Data Model & Architecture Notes

Companion to the SQLAlchemy models in `models/`. This covers what the ORM
classes alone can't express: the database-enforced guarantees, the auth flow,
and a build order that gets you to a working end-to-end slice fast.

---

## 1. Entity map (how the pieces relate)

```
Tenant ──< Membership >── User                         (identity / authz)
User.cognito_sub  ── maps to Cognito user pool `sub`

GLOBAL CATALOGUE (reference data, cross-tenant — the moat)
  CatalogueVendor ──< CatalogueProduct ──< CatalogueFact        (provenance per fact)
                                      └──< CatalogueProductRisk >── Risk

TENANT INVENTORY (tenant-scoped)
  System ──< UseCase                                   (system = entity, use case = unit)
    System.catalogue_vendor_id / catalogue_product_id  (link to catalogue if SaaS)

  UseCase ──< Classification        (per use case, versioned, with rationale)
  UseCase ──< Assessment            (type=AIIA is primary; FRIA/DPIA/MODEL_RISK feed it)
  UseCase ──< LifecycleTransition   (state machine history)

  Assessment ──< AssessmentItem                       (a finding/answer)
    AssessmentItem ── risk_id ─────────────────> Risk
    AssessmentItem ──< AssessmentItemControl ──> Control
    AssessmentItem ──< AssessmentItemEvidence ──> Evidence

THREE INHERITING APPROVAL SCOPES (tenant-scoped)
  VendorApproval   (tenant + catalogue_vendor)         outer gate
  ProductApproval  (tenant + catalogue_product)         inherits vendor; mostly a rollup
  UseCase.state == AUTHORISED                            inherits product

KNOWLEDGE CROSS-MAPS (global)
  Control ──< ControlFrameworkMap ── framework + clause_ref   (one control → many frameworks)
  Risk    ──< RiskControlMap ──> Control                       (risk → mitigating controls)

EVIDENCE & AUDIT
  Evidence  → S3 (bucket/key/version) + sha256 in Postgres
  AuditEvent → append-only compliance trail (insert only)
```

The two many-to-many cross-maps (`ControlFrameworkMap`, `RiskControlMap`) are
the technical heart: they're why one evidence item can satisfy ISO 42001 and
the EU AI Act at once, and why naming a risk surfaces its treating controls.

---

## 2. Guarantees the database must enforce (not just app code)

These are deliberately pushed into Postgres because, for a compliance product,
app-code-only enforcement is not defensible.

### 2.1 Tenant isolation — Row-Level Security (RLS)
Pooled multi-tenancy means every tenant-scoped table carries `tenant_id`.
Add RLS so a leak in app code can't cross tenants:

```sql
ALTER TABLE use_case ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON use_case
  USING (tenant_id = current_setting('app.current_tenant')::uuid);
-- repeat for every tenant-scoped table
```
Set `app.current_tenant` per request/transaction from the authenticated
membership. The catalogue/knowledge tables are global and are NOT under RLS.

### 2.2 Audit immutability
`audit_event` must be insert-only:
```sql
REVOKE UPDATE, DELETE ON audit_event FROM app_rw_role;
CREATE OR REPLACE FUNCTION block_mutation() RETURNS trigger AS $$
BEGIN RAISE EXCEPTION 'audit_event is append-only'; END; $$ LANGUAGE plpgsql;
CREATE TRIGGER audit_no_update BEFORE UPDATE OR DELETE ON audit_event
  FOR EACH ROW EXECUTE FUNCTION block_mutation();
```

### 2.3 One AIIA per use case
A use case may have many feeder assessments but exactly one of type `AIIA`.
Enforce with a partial unique index (can't be done with a column constraint):
```sql
CREATE UNIQUE INDEX uq_one_aiia_per_use_case
  ON assessment (use_case_id)
  WHERE type = 'aiia';
```

### 2.4 One current classification per use case
```sql
CREATE UNIQUE INDEX uq_current_classification
  ON classification (use_case_id)
  WHERE is_current = true;
```

### 2.5 Native enums
The models use SQLAlchemy `Enum(..., name=...)`, which creates Postgres native
enum types. Adding a value later needs `ALTER TYPE ... ADD VALUE` (Alembic
won't autogenerate that — write it by hand). This is why `Framework` and
`RiskSource` already include reserved post-MVP values (NIST, ATLAS): adding the
*rows* later needs no migration, only the *enum* would.

---

## 3. Cognito ↔ app boundary

* Cognito owns authentication. On first login, look up `User` by `cognito_sub`;
  create the `User` row if absent (JIT provisioning).
* The JWT from Cognito gives you `sub` and `email`. It does NOT decide
  authorization — your `Membership.role` does. Resolve the active tenant from
  the membership (and, if a user has several, from an explicit tenant switch).
* Keep roles in `Membership`, never in Cognito groups, so multi-tenant role
  differences and your four roles (admin/reviewer/contributor/auditor_readonly)
  stay under your control.
* Set `app.current_tenant` (for RLS) from the resolved membership at the start
  of each request's DB session.

---

## 4. Async seam (don't build now, don't paint yourself in)

The lifecycle state machine should be callable by a background worker, not only
inline in a request. Keep each transition a discrete function
`apply_transition(use_case, event) -> new_state` with no inline side-effects
beyond writing `LifecycleTransition` + `AuditEvent`. For the MVP you can call it
synchronously; later, an SQS-driven worker calls the same function. This keeps
IXN-2/IXN-5 (background orchestration, async sub-flows) a small change, not a
rewrite.

---

## 5. Suggested build order (thin end-to-end first, then deepen)

1. **Foundations**: base, identity, tenancy + RLS, Cognito login, audit_event
   + the immutability trigger. Get one authenticated user into one tenant.
2. **Knowledge seed (data, not much code)**: load Control + ControlFrameworkMap
   (ISO 42001 ↔ EU AI Act) and Risk + RiskControlMap (OWASP LLM + NIST/ISO).
   This is your expertise as rows; do it against your real 45-product engagement.
3. **System + UseCase** with intake context capture.
4. **Classification** (per use case) with rationale + the prohibited hard stop.
5. **Assessment/AIIA** (one per use case) + AssessmentItem linking risks,
   controls, evidence; the cross-map coverage view.
6. **Lifecycle state machine + cascading gates** (vendor → product → intake →
   assessment → treatment → authorisation) and the status surface.
7. **Catalogue** (vendor/product/fact/risk) + product-driven prefill, narrow
   seed; guided fallback when absent.
8. **Evidence → S3** (versioned + hashed) and the export/ATO pack.
9. **Approvals rollup** (VendorApproval/ProductApproval) + inheritance.
10. **AI-assist** (suggest relevance, draft, freshness) — last, on top of a
    working base, always human-confirmed.

Reaching a thin version of steps 1–6 gives you the first demoable spine; 7–10
deepen it to full MVP scope.

---

## 6. Pydantic / ORM separation (reminder)

Keep these model classes (persistence) separate from Pydantic request/response
schemas (the API surface). They will diverge — the API often exposes computed
rollups (e.g. system coverage, control-coverage-by-framework) that aren't
single tables. Build read-model/Pydantic "view" schemas for those rather than
contorting the ORM.