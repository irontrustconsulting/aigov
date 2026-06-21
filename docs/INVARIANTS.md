# INVARIANTS.md — IronTrust AI Governance Platform

**Location:** `docs/INVARIANTS.md` — single source, mirrored to project knowledge. Updated once.
**Purpose:** The reviewer's checklist and the hard design constraints. Cited by `INV-n` across all canonicals; never restated elsewhere — other files reference these by ID.

**Enforcement legend** (a reviewer agent concentrates attention on `CONVENTION`):
- `DB` — schema / trigger / constraint. Structurally unviolable.
- `CODE` — one routed locus (a predicate, function, or single-statement shape) all paths go through. Violable only by adding a path that bypasses it.
- `CONVENTION` — discipline only. Nothing structural prevents a violation; review must catch it.

**Format:** `INV-n · ENFORCEMENT · locus` / statement / `↳ origin · refs`.
**Note:** DB *uniqueness* objects (partial indexes `uq_one_aiia_per_use_case`, `uq_current_classification`, `uq_one_primary_eu_mapping`; plain constraint `uq_feeder_type_per_aiia`) are catalogued in `DATA-MODEL.md`. Behavioural invariants here reference them by name rather than restating them.

---

**INV-1** · CODE · `verify_cognito_token` / `verify_operator_token`
Tenant and operator tokens must never satisfy each other's verifiers; never share an auth dependency across planes. Structural backstop: the two Cognito pools have different `iss`/`aud`.
↳ origin: foundations

**INV-2** · CONVENTION · membership join (never bare `app_user`)
Any user listing in a tenant context joins from `membership`; `app_user` is never queried bare. It is global and non-RLS — the join is the only thing scoping the read to the caller's tenant.
↳ origin: foundations · refs: INV-34

**INV-3** · CONVENTION · handler dependency (`ctx.tenant_id`)
On every tenant-mutating endpoint, `tenant_id` is `ctx.tenant_id`, never a request-body field.
↳ origin: foundations

**INV-4** · DB · `irontrustai_app` grant (NOBYPASSRLS)
Tenant-scoped work runs on `irontrustai_app` (NOBYPASSRLS). No BYPASSRLS role for tenant work; isolation is RLS, not table grants.
↳ origin: foundations

**INV-5** · DB · `AuditEvent` immutability trigger + grant
`AuditEvent` is append-only. No UPDATE/DELETE at the application layer; the Postgres trigger is the backstop.
↳ origin: foundations

**INV-6** · CONVENTION · evidence model (pointer-only)
Evidence bytes live in S3; Postgres holds only the pointer (`s3_bucket`, `s3_key`, `s3_version_id`) + `sha256`. Never store file bytes in the DB.
↳ origin: S3–4

**INV-7** · CODE · `assert_governance_assignable` / `assert_distinct_workflow_actor` (governance.py)
SoD goes through exactly two sanctioned loci, never a third inline check. Assignment-time (may this membership hold this role, given what it already holds) → `assert_governance_assignable`. Act-time (did one user perform two distinct workflow roles on one object) → `assert_distinct_workflow_actor`, keyed on `user_id`, not `membership_id`. No inline conflict logic in handlers or services.
↳ origin: S6a (revised) · refs: INV-28

**INV-8** · CONVENTION · operator → role → permission only
Operator permissions reach operators only through roles; no direct operator→permission grants. If a one-off is needed, make a role.
↳ origin: foundations

**INV-9** · CONVENTION · no unique constraint on `app_user.email`
Cognito is the email-uniqueness authority; `app_user.email` is deliberately not DB-unique. Do not add a unique constraint without understanding what Cognito's enforcement implies.
↳ origin: foundations

**INV-10** · CODE · classification resolvers (bridge / context-gate)
Tier is never asserted from catalogue facts alone — it comes from deployment context (bridge or context-question gate). The catalogue informs; it never decides.
↳ origin: classification · refs: D-8

**INV-11** · CODE · `resolve_*` (read) vs `snapshot_`/`compute_`/`sign_off_` (write)
Classification resolution and persistence stay separate on both gates. `resolve_classification`/`resolve_context_classification` never write; `snapshot_classification`/`compute_and_record_classification`/`sign_off_classification` own the transaction. AIIA/feeder creation reads only the current persisted snapshot and never re-enters a resolver.
↳ origin: classification

**INV-12** · CODE · `resolve_context_classification` (fail-closed ladder)
Context-gate resolution is fail-closed: unanswered questions → `UNRESOLVED`, no snapshot. `MINIMAL` is reached only affirmatively (all answered, nothing higher asserted), never as a default or fallback. `PROHIBITED` short-circuits.
↳ origin: classification

**INV-13** · CODE · provenance server-derived + disposition-before-authoring
AIIA/feeder provenance is always server-derived; no request schema accepts a `provenance` field. A still-`AI_SUGGESTED` item blocks authoring-field writes until confirmed or amended.
↳ origin: S3–4

**INV-14** · CODE · single conditional UPDATE (from-state in WHERE)
Provenance transitions are single conditional UPDATEs — never read-then-write; the from-state guard lives in the WHERE clause so a stale read can't corrupt the audit diff. `412` (lock mismatch) and `409` (bad from-state) are deliberately distinguishable.
↳ origin: S3–4

**INV-15** · CODE · feeder scope copy-at-creation
A feeder's scope (`tier_snapshot`/`classification_version`) is copied from its parent AIIA at creation and never re-resolved. Parent and feeder must always agree.
↳ origin: S3–4

**INV-16** · CODE · `assemble_aiia_items` (read-time only)
Feeder propagation into the AIIA is read-time reference only — never copy a feeder item into the AIIA, never write back. `assemble_aiia_items` is the single assembly locus.
↳ origin: S3–4 · refs: D-18

**INV-17** · CODE · `_is_pristine` (assessment_service.py)
Pristine-delete only, AIIA + feeders: a hard DELETE is permitted only with no confirmed/amended items, no control links, no evidence links, and (for an AIIA) no feeders. A worked assessment must be voided instead — not yet built (see STATE deferred).
↳ origin: S3–4 · refs: INV-36

**INV-18** · CODE · upload route (no `get_tenant_db` dependency)
No DB transaction or connection is held across a slow external call that doesn't need one. Evidence upload's S3 put runs with nothing open; the route depends on `get_tenant_context`, not `get_tenant_db`. Contrast Cognito provisioning, which deliberately holds a transaction to compensate on failure — know which shape a new external-call path needs before writing it.
↳ origin: S3–4

**INV-19** · CODE · single guarded DELETE (`NOT EXISTS` inline)
Evidence pristine-delete is a single guarded statement, never check-then-delete. The `assessment_item_evidence` `ON DELETE CASCADE` makes a separate `SELECT count` then `DELETE` racy; the `NOT EXISTS` guard must live in the same statement as the `DELETE`.
↳ origin: S3–4

**INV-20** · CODE · evidence-link vs control-link gating (deliberate asymmetry)
Evidence-linking is disposition-gated (a still-`AI_SUGGESTED` item rejects an evidence link); control-linking is not. Documented asymmetry — do not "fix" one to match the other without re-reading why.
↳ origin: S3–4 · refs: D-20

**INV-21** · CONVENTION · no direct evidence↔control table
Evidence → control is transitive via items only; never add a direct evidence↔control table. Framework satisfaction derives from the control-library cross-map through whichever item the evidence is linked to.
↳ origin: S3–4 · refs: D-19

**INV-22** · CODE · presigned download hardening
Presigned evidence downloads are always hardened: forced `Content-Disposition: attachment`, content-type neutralised off a safe allow-list, signed against the public (not internal) S3 endpoint. Never serve evidence inline.
↳ origin: S3–4

**INV-23** · CONVENTION · typed-column bind (never raw `.value`)
Every by-name enum is stored by Postgres **member name**, not `.value` — a raw `.value` bind silently matches zero rows wherever an enum's `.value` differs in case from its member name. Bind through the typed column; never hand-write a `.value` comparison. All enum labels are uniformly UPPERCASE member names in live DDL (verified `pg_enum`) after fix `3a5b36bdd37a`, which renamed the labels that had shipped lowercase (`classification_status`; `eu_ai_act_tier.REQUIRES_CONTEXT`; `system_lifecycle_stage`). The hazard is structural, not historical: the no-RLS test DB generates enums fresh from the ORM and can never catch a label-case mismatch — only checking real `pg_enum` can. Verify before encoding any raw label comparison.
↳ origin: S5 · fix `3a5b36bdd37a`

**INV-24** · CONVENTION · `apply_transition` sole writer
`apply_transition` is the sole writer of `use_case.state`. No other path may construct `UPDATE … SET state`, directly or via the ORM instance attribute. Nothing structural enforces this — review must catch violations.
↳ origin: S5 · refs: INV-25

**INV-25** · CONVENTION · recompute `full_vector` at every consequential read/write
The full gate vector is source of truth; persisted `use_case.state` is a cursor. No gating decision (advance, regress, an authorisation attempt) reads persisted `state` alone — recompute via `full_vector`/`re_evaluate`. A status `GET` shows the computed verdict and never persists it.
↳ origin: S5

**INV-26** · CODE · `advance_use_case` step-0 (snapshot tier)
Prohibited is terminal, supreme, and read off the current classification snapshot's `tier`, never `eu_tier`. Fires from any non-terminal state including `held` — `eu_tier` is never stamped `PROHIBITED` on the context path, so reading it would silently let a prohibited practice sit un-halted.
↳ origin: S5 · refs: INV-33

**INV-27** · CONVENTION · re-`set_config` after mid-request commit
A mid-request `db.commit()` resets `SET LOCAL`-scoped settings, including `app.current_tenant`. Any code that commits mid-request on an RLS-bound session must immediately re-`set_config` (`_set_tenant_context`), or every later RLS-scoped query on that session silently returns zero rows. Caught only by live-smoke-testing against real RLS-enabled Postgres.
↳ origin: S5

**INV-28** · CODE · `assert_distinct_workflow_actor` (act-level SoD)
Act-level SoD is distinct from assignment SoD and lives only in `assert_distinct_workflow_actor`: `reviewer ≠ submitted_by` (6a); `authoriser ∉ {approved_by, submitted_by}` (6b).
↳ origin: S6a · refs: INV-7

**INV-29** · CODE · `residual_risk_statement` authored on ATO
Residual-risk acceptance is the authoriser's act — `residual_risk_statement` is authored on the ATO at `authorise_use_case` time, never derived from or assignable to the reviewer's AIIA approval.
↳ origin: S6b · refs: D-10

**INV-30** · CODE · human-act gate terms (no auto-derive)
Reviewer/authoriser gates are human-act gates, never auto-advanced. `assessment_approved()` is satisfied only by `record_review(APPROVED)`; `authorisation_gate`'s human-act term only by `authorise_use_case`. `advance_use_case`/`re_evaluate` never derive either.
↳ origin: S6a/6b

**INV-31** · CODE · `_assert_authoring_unlocked`
AIIA authoring is status-locked: item and feeder-item writes are rejected (`409`) while the parent AIIA is `IN_REVIEW` or `APPROVED`; a feeder item's lock resolves through `parent_aiia_id`, since the feeder's own `status` never moves.
↳ origin: S6a

**INV-32** · CONVENTION · read `live_state`, never row-existence
The ATO is a point-in-time fact; deployment authority is the live vector. A `DeploymentAuthorisation` row is never mutated; re-authorisation always writes a new row. Consumers read the computed `live_state` (`GET …/authorisation`), never infer "currently authorised" from a row's mere existence.
↳ origin: S6b

**INV-33** · CODE · state-agnostic halt legality + step-0
`authorised` is not a safe harbour from prohibition: `apply_transition`'s `halt` legality is state-agnostic (`from_state not in _TERMINAL_STATES`) and `advance_use_case`'s step-0 PROHIBITED check runs regardless of starting state — reclassification to `PROHIBITED` forces `halted_prohibited` directly from `authorised`, with no special-casing required.
↳ origin: S6b · refs: INV-26

**INV-34** · CONVENTION · actor-identity via membership
Actor-identity reads join via `membership`, never bare `app_user` (INV-2 applied to the review queue, review history, and the ATO's authoriser identity).
↳ origin: S6b · refs: INV-2

**INV-35** · CODE · `_GATE_FNS`/`_ADVANCE_TABLE` ceiling
`authorised` is entered only by `authorise_use_case`. `advance_use_case`'s gate-driving structures have no entry past `pending_authorisation`, so a cycle-matching ATO is never sufficient on its own to cross into `authorised`. `re_evaluate` may hold an already-`authorised` use case in place (no-op, full vector still all-advances) or regress it to `held`, but its restore branch can only target a vector-guarded state — never `authorised` — so a regressed-then-restored use case always lands at `pending_authorisation` and waits for re-confirmation.
↳ origin: S6b

**INV-36** · CODE · `_is_pristine` (status + history)
Pristine-delete is status-and-history-aware: a hard DELETE is blocked unless `status == DRAFT` **and** no `AssessmentReview`/`DeploymentAuthorisation` row references the assessment — on top of INV-17's existing conditions.
↳ origin: S6a/6b · refs: INV-17

**INV-37** · CODE · `authorisation_gate` cycle match
`authorisation_gate` matches by cycle: it passes only when a `DeploymentAuthorisation`'s `submission_round` equals the assessment's current `submission_round` — existence alone is insufficient; a re-submitted cycle orphans the prior ATO.
↳ origin: S6b

**INV-38** · CODE · `coverage_service` qualifying-link filter (S7a)
Control coverage counts only links on dispositioned items (item provenance ≠ `AI_SUGGESTED`); `UNADDRESSED` is a first-class response verdict (zero qualifying links), never an omission. Approval is tested against the **governing AIIA** (`parent_aiia_id` for a feeder item) at status `APPROVED` only — `DRAFT`/`NEEDS_REFRESH` are excluded from the headline, never a feeder's own perpetual-`DRAFT` status.
↳ origin: S7a · refs: INV-13, 20, 31

**INV-39** · CODE · cross-framework satisfaction is structural (S7a)
No inter-control coverage propagation exists or is permitted. Cross-framework satisfaction is structural — one multi-homed control projected across its `control_framework_map` rows — never inferred between distinct controls.
↳ origin: S7a · refs: D-19; INV-21

**INV-40** · CODE · export references evidence by manifest only (S7b)
The export references evidence by manifest (`id, sha256, filename, content_type, size, back-refs`) — never bytes, never embedded presigned URLs; retrieval stays on the hardened `GET /v1/evidence/{id}`.
↳ origin: S7b · refs: INV-6, 22

**INV-41** · CODE · export AIIA section is native items only (S7b)
The export's AIIA section is native items only; feeder content appears solely as full feeder sub-records carrying `surfaces_into` cross-refs. The export never calls `assemble_aiia_items` and never re-surfaces or duplicates feeder items — `assemble_aiia_items` stays the single surfacing locus.
↳ origin: S7b · refs: INV-16; D-18

**INV-42** · CODE · export generation stages `export.generated` (S7b)
Export generation is a disclosure/custody act and stages `export.generated` — the only audit-writing read besides `evidence.access`.
↳ origin: S7b · refs: INV-5

**INV-43** · CONVENTION · export is a live cursor + canonical `content_hash` (S7b)
The export is recomputed live per request, plus a canonical `content_hash` (sorted keys, ISO-8601 UTC, no insignificant whitespace — JCS/RFC 8785-style, computed *before* staging the audit so it lands in `detail`). No persisted/frozen export artifact exists in MVP.
↳ origin: S7b · refs: INV-25

**INV-44** · CODE · ATO-basis honesty (S7b)
The `DeploymentAuthorisation` row is the authoritative basis; the referenced assessment is presented as **current state, may have drifted**, never reconstructed (until AIIA versioning exists) — labelled `basis_is_current_state_not_authorisation_snapshot`.
↳ origin: S7b · refs: INV-32; OPEN-2

**INV-45** · CODE · audit-trail closure = entity-id OR detail-back-ref (S7b)
The export's audit-trail section is the durable-entity-id closure **or** a `detail` back-ref match — ephemeral/removal events (`assessment_item_control`/`assessment_item_evidence`, `.created`/`.deleted`) are scoped by `detail->>'item_id' IN (in-scope items)`, since the keyed link row hard-deletes and a current-rows closure would drop add/remove pairs entirely. Never the unscoped tenant log; `source_ip` excluded. Completeness is "resolvable to a surviving in-scope entity," with a bounded documented residual (`assessment.deleted` pristine-only; `evidence.access` on since-unlinked evidence).
↳ origin: S7b · refs: INV-5, 19

---

## Promoted from `CLAUDE.md` §3.2 (numbered above the live ceiling)

> Long-standing schema/code rules promoted from CLAUDE §3.2. They post-date STATE §6's sprint-numbered invariants (1–45), so they take the next free ids — an id is an identifier, not a chronology.

**INV-46** · DB · reference-data FK `ondelete=RESTRICT`
FKs from assessment items into library tables (`AssessmentItem.risk_id`, `AssessmentItemControl.control_id`) are `RESTRICT`, not `CASCADE`/`SET NULL` — deleting a referenced library risk/control is blocked rather than silently orphaning or stripping assessment records. Deprecate library entries via a soft-flag instead.
↳ origin: foundations (promoted from CLAUDE §3.2)

**INV-47** · CODE · `passive_deletes=True` on deferred cascades
Self-referential relationships meant to defer to a DB-level `ON DELETE CASCADE` must carry `passive_deletes=True` (`Assessment.feeders`), or SQLAlchemy nulls a loaded child's FK on parent delete instead of trusting the DB cascade. Apply to any future self-referential relationship of this shape.
↳ origin: S3–4 (promoted from CLAUDE §3.2)

**INV-48** · DB · global reference tables carry no `tenant_id`, no RLS
Catalogue, controls, risks, taxonomy, governance-role catalogue + conflict matrix, decision tree, and assessment section templates are cross-tenant by design: no `tenant_id` column, no RLS policy, readable from any session. Tenant data always carries `tenant_id`.
↳ origin: foundations (promoted from CLAUDE §3.2)