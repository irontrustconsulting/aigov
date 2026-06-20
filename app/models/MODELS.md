# AI Governance MVP — Data Model & Architecture Notes

Companion to the SQLAlchemy models in `models/`. This covers what the ORM
classes alone can't express: the entity shape, the rationale behind the
database-enforced guarantees, and the auth flow. **Not a schema mirror** —
for the literal current DDL, read the model files and `alembic history`;
this stays useful precisely by not trying to track every column. For *what's
currently built* (the authoritative, frequently-updated answer), see
`STATE.md` §3/§5 — this file's build-order section below is a roadmap, not
a status report.

---

## 1. Entity map (how the pieces relate)

```
Tenant ──< Membership >── User                         (identity / authz)
User.cognito_sub  ── maps to Cognito user pool `sub`

GLOBAL CATALOGUE (reference data, cross-tenant — the moat)
  CatalogueVendor ──< CatalogueProduct ──< CatalogueFact        (provenance per fact)
                                      └──< CatalogueProductRisk >── Risk

GLOBAL CLASSIFICATION GATE 2 (reference data, cross-tenant)
  DecisionTree ──< DecisionTreeQuestion ──< DecisionTreeOption
    (versioned, content-hashed; frozen once seeded — a new version is a new row, never a mutation)

GLOBAL ASSESSMENT SECTION TEMPLATE (reference data, cross-tenant)
  AssessmentSectionTemplate, keyed (type, tier, section_key)
    .aiia_target_section_key → another AssessmentSectionTemplate.section_key on a type=AIIA
      row at the same tier (feeder section → the AIIA section it surfaces into; NULL = feeder-private)

TENANT INVENTORY (tenant-scoped)
  System ──< UseCase                                   (system = entity, use case = unit)
    System.catalogue_vendor_id / catalogue_product_id  (link to catalogue if SaaS)
    System ──< SystemDataCategory >── DataCategory       (multi-select; DPIA feeder pre-fill source)
    System ──< SystemAffectedParty >── AffectedParty     (multi-select; FRIA feeder pre-fill source)

  UseCase ──< Classification        (per use case, versioned, with rationale; two resolution
                                      paths feed it — the catalogue bridge, and gate 2's
                                      DecisionTree — see STATE.md §3)
  UseCase ──< Assessment            (type=AIIA is primary; FRIA/DPIA/MODEL_RISK feed it)
  UseCase ──< LifecycleTransition   (state machine history — apply_transition's sole writer
                                      stages one per hop; STATE.md "Product lifecycle" §3)
  UseCase.held_from_state / .held_reason   (regression hint only, set/cleared by
                                             apply_transition — never the un-hold restore
                                             target; that's the full gate vector's job)

  Assessment ──< Assessment          (self-referential: .parent_aiia_id; a feeder's parent is
                                       always type=AIIA; UNIQUE(parent_aiia_id, type) — at
                                       most one feeder of each type per AIIA)
  Assessment ──< AssessmentItem                       (a finding/answer)
    AssessmentItem ── risk_id ─────────────────> Risk                       (FK: RESTRICT)
    AssessmentItem ──< AssessmentItemControl ──> Control                    (FK: RESTRICT)
    AssessmentItem ──< AssessmentItemEvidence ──> Evidence
    -- AssessmentItemControl / AssessmentItemEvidence carry tenant_id + RLS,
       same as every other tenant table (parity; item-first access is
       defense-in-depth, not the sole isolation mechanism)
    -- AssessmentItemEvidence: UNIQUE(item_id, evidence_id) (§2.9); no direct
       Evidence ──> Control edge — framework satisfaction is transitive,
       through whichever item the evidence is linked to
    -- AssessmentItem.treatment_decision (MITIGATE/ACCEPT, TRANSFER/AVOID
       reserved) + .treatment_rationale: the treatment_gate's input, written
       provenance-neutral through amend_item (never flips provenance the way
       the other authoring fields do — STATE.md inv re: override-rate metric)

THREE INHERITING APPROVAL SCOPES (tenant-scoped)
  VendorApproval   (tenant + catalogue_vendor)         outer gate; vendor_gate reads it
  ProductApproval  (tenant + catalogue_product)         inherits vendor; product_gate reads it
  UseCase.state reaching pending_authorisation           inherits product (the lifecycle's
                                                           forward ceiling this sprint;
                                                           AUTHORISED is Sprint 6)
  Both approval models also carry decided_by_user_id / decided_at / note
  (who cleared it and why) — set by set_vendor_approval/set_product_approval,
  which fan out to every affected use case (STATE.md §3)

KNOWLEDGE CROSS-MAPS (global)
  Control ──< ControlFrameworkMap ── framework + clause_ref   (one control → many frameworks)
  Risk    ──< RiskControlMap ──> Control                       (risk → mitigating controls)

EVIDENCE & AUDIT
  Evidence  → S3 (bucket/key/version) + sha256 in Postgres; upload, repository
              reads, disposition-gated item-linking, and guarded delete are
              all wired (STATE.md §3 "Evidence repository") — this used to
              be schema-only, it no longer is
  AuditEvent → append-only compliance trail (insert only)
```

The two many-to-many cross-maps (`ControlFrameworkMap`, `RiskControlMap`) are
the technical heart: they're why one evidence item can satisfy ISO 42001 and
the EU AI Act at once, and why naming a risk surfaces its treating controls.

`Assessment`'s self-reference is the same shape twice: an AIIA's own items are
native; a feeder's items surface into the AIIA only at *read* time (joined via
`AssessmentSectionTemplate.aiia_target_section_key`), never copied or written
back. See STATE.md's "Established patterns" for the read-time-reference
pattern this produced.

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

### 2.3 One *current* AIIA per use case
A use case may have many feeder assessments but exactly one *current* `AIIA`.
Enforced with a partial unique index (can't be done with a column constraint;
illustrative — confirm exact DDL against the migration, not this doc):
```sql
CREATE UNIQUE INDEX uq_one_aiia_per_use_case
  ON assessment (use_case_id)
  WHERE type = 'AIIA' AND is_current;
```
Note the enum value is the Postgres-native label (`'AIIA'`, matching the
Python enum's *name*, not its lowercase `.value`) — SQLAlchemy's default
`Enum(...)` binds by name unless `values_callable` overrides it.

### 2.4 One current classification per use case
```sql
CREATE UNIQUE INDEX uq_current_classification
  ON classification (use_case_id)
  WHERE is_current = true;
```

### 2.5 One primary EU AI Act mapping per product category
```sql
CREATE UNIQUE INDEX uq_one_primary_eu_mapping
  ON product_category_eu_mapping (product_category_id)
  WHERE is_primary = true;
```
These three (§2.3–§2.5) are the full set of hand-managed partial unique
indexes — skipped by Alembic autogenerate (`alembic/env.py`'s
`include_object`), so any migration touching these tables must add/preserve
them by hand. See CLAUDE.md §3.2.

### 2.6 Feeder cardinality
At most one feeder of each type (`FRIA`/`DPIA`/`MODEL_RISK`) per AIIA — a
plain, non-partial constraint, so (unlike §2.3–§2.5) Alembic autogenerate
handles it natively:
```sql
ALTER TABLE assessment
  ADD CONSTRAINT uq_feeder_type_per_aiia UNIQUE (parent_aiia_id, type);
```
`parent_aiia_id` is `NULL` on every AIIA row itself; Postgres never treats two
`NULL`s as equal under a unique constraint, so this only ever constrains
feeders.

### 2.7 Reference-data FK hardening
`AssessmentItem.risk_id` and `AssessmentItemControl.control_id` are
`ON DELETE RESTRICT`, not `CASCADE`/`SET NULL` — deleting a referenced
library `Risk`/`Control` is blocked rather than silently orphaning an
assessment item or stripping a coverage record. Deprecate library entries via
a soft-flag instead of deleting them.

### 2.8 Native enums
The models use SQLAlchemy `Enum(..., name=...)`, which creates Postgres native
enum types. Adding a value later needs `ALTER TYPE ... ADD VALUE` (Alembic
won't autogenerate that — write it by hand, and don't use the new value in
the same migration/transaction that adds it). This is why `Framework` and
`RiskSource` already include reserved post-MVP values (NIST, ATLAS): adding the
*rows* later needs no migration, only the *enum* would.

**This by-name convention is easy to break by hand, and was** — `eu_ai_act_tier`'s
`REQUIRES_CONTEXT` was added as lowercase `'requires_context'` (mismatched
against its four uppercase siblings), and `classification_status` was created
with **all four** labels lowercase. Both made the affected value un-writable
from the ORM (any INSERT/UPDATE setting that member raised "invalid input
value" at the DB) — `classification_status` being broken meant every
`snapshot_classification`/`compute_and_record_classification` call failed
outright, since the column's default is `ClassificationStatus.PENDING_REVIEW`.
Caught only by live-testing against the real migrated dev DB — the test suite
is built via `Base.metadata.create_all()`, which regenerates these enum types
fresh from the ORM and is therefore always self-consistent, so it can never
catch this class of drift between the ORM's assumption and a hand-written
migration's actual DDL. Fixed (Sprint 5,
`alembic/versions/3a5b36bdd37a_fix_enum_label_case.py`, non-destructive
`ALTER TYPE … RENAME VALUE`) along with the same bug on the (unused)
`system_lifecycle_stage` type. **Before adding the next hand-written enum
value, verify its label case against `pg_enum` directly — don't assume.**

### 2.9 Evidence-link uniqueness
One evidence item links to a given assessment item at most once — a plain,
non-partial constraint (like §2.6, Alembic autogenerate handles it natively):
```sql
ALTER TABLE assessment_item_evidence
  ADD CONSTRAINT uq_assessment_item_evidence UNIQUE (item_id, evidence_id);
```
Added by `evidence_link_migration.py`, which also **drops** the single-column
`ix_assessment_item_evidence_item_id` index — the new composite index already
serves `item_id` as its leftmost prefix, so the standalone index became
redundant. `ix_assessment_item_evidence_evidence_id` is kept (it backs the
pristine-delete guard's `NOT EXISTS` and the repository's `link_count`
subquery, neither of which the item_id-leading composite can serve).

---

## 3. Cognito ↔ app boundary

* Cognito owns authentication. `User` rows are provisioned explicitly (member
  invite / tenant provisioning), not created lazily on first login.
* The JWT from Cognito gives you `sub` and `email`. It does NOT decide
  authorization — the DB does, on two separate axes (see CLAUDE.md §2.3 /
  STATE.md §2): `Membership.role` (administrative: admin/member, zero
  governance power) and `governance_role_assignment` (five SoD-constrained
  roles: system_owner, contributor, reviewer, authoriser, auditor). Don't
  re-derive the role list here — it has already changed shape once; point at
  CLAUDE.md/STATE.md instead of hard-coding it in a second place.
* Keep roles in the DB, never in Cognito groups or token claims, so
  multi-tenant role differences and the SoD conflict matrix stay under your
  control.
* Set `app.current_tenant` (for RLS) from the resolved membership at the start
  of each request's DB session.

---

## 4. Async seam (don't build now, don't paint yourself in)

The lifecycle state machine should be callable by a background worker, not only
inline in a request. Built (Sprint 5) as `apply_transition(db, use_case, event,
to_state, actor_user_id, reason, *, held_reason=None)` — a discrete function
with no side-effects beyond writing `LifecycleTransition` + `AuditEvent`,
exactly as planned here. The approval fan-out (`set_vendor_approval`/
`set_product_approval` → `fan_out_vendor_approval`/`fan_out_product_approval`)
is the seam's first real exercise: each affected use case is re-evaluated in
its **own** short-lived session (opened, RLS tenant-context set, committed,
closed — `app/services/lifecycle_service.py::_fan_out`), inline-looped today.
Swapping the loop for an SQS-driven worker later is a small change, not a
rewrite, because the per-use-case unit of work is already isolated exactly
that way. One gotcha the inline version had to learn the hard way: a session
that commits mid-request loses its `SET LOCAL app.current_tenant` — re-set it
after every such commit, fan-out included (STATE.md inv 27).

---

## 5. Build order (thin end-to-end first, then deepen)

Original sequencing, with status. **Status here is a snapshot — STATE.md §3/§5
is the authoritative, currently-maintained answer to "what's built"; this
list exists for the *order and rationale*, not as a live tracker.**

1. ✅ **Foundations**: base, identity, tenancy + RLS, Cognito auth, audit_event
   + the immutability trigger.
2. ✅ **Knowledge seed**: Control + ControlFrameworkMap (ISO 42001 ↔ EU AI Act),
   Risk + RiskControlMap (OWASP LLM technical layer + NIST/ISO governance layer).
3. ✅ **System + UseCase** with full structured intake context capture.
4. ✅ **Classification** — two gates now: the catalogue-bridge auto-resolve, and
   (for what the bridge can't resolve) a versioned decision-tree
   context-question gate with Reviewer sign-off as the act of record. The
   `PROHIBITED` hard stop is a first-class outcome (`PROHIBITED_HALT`) on the
   gate-2 resolver.
5. ✅ **Assessment/AIIA** (one per use case) + AssessmentItem linking risks,
   controls, and now evidence (see 8 below); tier-scoped section templates;
   FRIA/DPIA/MODEL_RISK feeders that pre-fill from the register and surface
   into the AIIA by read-time reference, not copy.
6. ✅ **Lifecycle state machine + cascading gates** (vendor → product → intake
   → assessment → treatment, ceiling at `pending_authorisation`) and the
   status/rollup surface. `apply_transition`/`advance_use_case`/`full_vector`/
   `re_evaluate`, five gate predicates, the manual re-evaluate lever, system/
   portfolio rollup. The authorisation gate itself (`pending_authorisation →
   authorised`) is Sprint 6.
7. ✅ **Catalogue** (vendor/product/fact/risk) + product-driven prefill
   (display-only; tenant confirm/amend not yet wired).
8. ✅ **Evidence → S3** (versioned + hashed): proxied upload (hash-then-put
   outside any DB transaction, S3-compensated on commit failure), paginated
   repository with presigned hardened download, disposition-gated item
   linking, single-statement guarded delete. EVD-3/EVD-4 (assignment/
   reminders, freshness notifications), AV scanning, and supersession/
   versioning chains remain unbuilt — see STATE.md §5.
9. ⬜ **Export / audit pack (EXP-1)**. Not started; the evidence presigned-
   download primitive is its eventual consumer (and the feeder design
   reserves the seam for feeder-private sections).
10. ✅ **Approvals + inheritance** (VendorApproval/ProductApproval). Set/update
    endpoints (`authoriser`-gated), gate reads (auto-pass with no catalogue
    link — that *is* inheritance, no separate code), and the per-use-case
    fan-out on every approval change.
11. ⬜ **AI-assist** (suggest relevance, draft, freshness) — still last, on top
    of the now-working base, always human-confirmed. `AssessmentItem
    .ai_suggested_text` is the reserved seam; today's `AI_SUGGESTED` items
    (proposed risks) are deterministic catalogue/library lookups, not
    LLM-generated — that distinction matters, don't blur it when this lands.

---

## 6. Pydantic / ORM separation (reminder)

Keep these model classes (persistence) separate from Pydantic request/response
schemas (the API surface). They will diverge — the API often exposes computed
rollups (e.g. system coverage, control-coverage-by-framework) that aren't
single tables. Build read-model/Pydantic "view" schemas for those rather than
contorting the ORM.