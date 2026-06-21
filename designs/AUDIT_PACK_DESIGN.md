# Sprint 7b — Export / Audit Pack — Design Document

**Status:** design · **v1.5, all verification closed** · ready for handoff
**Classification:** additive · read-assembly + one disclosure-audit write · zero migrations · no new model · no new enum · no new DB role · one `coverage_service` parameter added (7a amendment)
**Sprint 7 arc:** 7a coverage (built) → applicability (separate track, deferred) → **7b export pack (this doc)**
**Depends on:** 7a `coverage_service` (built, amended here — D13); 6b `DeploymentAuthorisation` (built); evidence repository + hardened download (built)
**Verification basis:** B1–B6 closed; ephemeral/removal events carry `detail.item_id` (B5) so §4.4(b) is sound; one pre-flight micro-confirm (control_link.created detail)
**Changes from v1.4:** B5 closed — §4.4(b) predicate pinned to `detail->>'item_id' IN (items)`; residual narrowed to `assessment.deleted` (pristine-only) + `evidence.access`-on-unlinked; `evidence.deleted` confirmed correctly out-of-scope (delete guard ⇒ unlinked)
**Changes from v1.1:** **audit closure widened to `assessment_item_control` + `assessment_item_evidence` link-row ids** (B1: link events key to the link row, not the item) and **vendor/product approval-row ids** pinned (D11/D4); lifecycle-trail projection fields pinned (§4.2.6); ATO actor name/email nullable → membership fallback (§4.3); classification sign-off actor sourced from audit not row (§4.2.2); V3–V6 closed (§7)
**Changes from v1.0 (carried):** AIIA section = native items only (D3/inv 41); REPEATABLE READ mechanism pinned (D7); `source_ip` excluded (D12/A#9); `content_hash` canonicalisation (D1); EXP-1 PDF deferral accepted (A#10); router placement (§4.1/§5.2)

---

## 1. Context & objective

PRD §4.10: EXP-1 (export pack for a system or a framework — assessments, evidence, control mapping, audit trail) and EXP-1a (ATO-style deployment-authorisation document). The pack is the audit deliverable: the complete, traceable governance record of an AI system, as structured JSON.

**Accepted scope deviation (A#10):** EXP-1 reads "(PDF + structured data)". 7b ships the structured-data half (JSON) only; PDF rendering is deferred (§10) as a frontend/later layer. EXP-1 is therefore not *fully* satisfied until the PDF render lands — an explicitly accepted MVP stage, not an oversight. Branded export (EXP-3) and auditor-scoped access (EXP-2) are also out (§10).

7b is overwhelmingly **read-assembly over already-immutable data** — classification history is versioned, `LifecycleTransition`/`AuditEvent` are append-only, the ATO is a frozen row. The only live-recomputed parts are current assessment-item state and coverage. There is exactly one genuinely new assembler (feeder-private sections) and one write (the disclosure audit).

---

## 2. Resolved decisions

| # | Decision | Rationale | PRD/inv anchor |
|---|---|---|---|
| D1 | Pack assembled live per request; **no persisted/frozen artifact**. Metadata: `generated_at, scope, content_hash`. **`content_hash` is computed over a canonical serialization** (sorted keys, ISO-8601 UTC timestamps, no insignificant whitespace — JCS/RFC 8785-style), **before** staging `export.generated`, so it lands in the audit `detail`. | Most content is already immutable; a stored export would be a second source of truth. A hash is only reproducible over a canonical form. | inv 25 family; A#3 |
| D2 | Evidence by **manifest** (`id, sha256, filename, content_type, size, back-refs`) — never bytes, never embedded presigned URLs. Retrieval stays on `GET /v1/evidence/{id}`. | Durable JSON with minute-TTL URLs is dead on arrival; bytes belong in S3. | inv 6, 22; A#2 |
| D3 | Assessment section = **native AIIA items only**, **plus** each feeder as a complete sub-record (all sections incl. private) carrying `surfaces_into` cross-refs to the AIIA sections its items map to. **Surfacing is never re-assembled** — the export does **not** call `assemble_aiia_items`. | Re-assembling would double-list every surfacing feeder item and create a second surfacing locus that inv 16 reserves to `assemble_aiia_items`. Native-items + `surfaces_into` pointers respects inv 16 and avoids duplication. | STATE §5; inv 16 |
| D4 | Audit-trail section = **entity-id closure** over the use case's (system's) object graph, `entity_id IN (closure)`. Never the unscoped tenant log. **The closure includes link-row and approval-row ids** because `control_link.*`/`evidence.linked/unlinked` key to the `assessment_item_control`/`assessment_item_evidence` **link-row id**, and `vendor_approval.*`/`product_approval.*` key to the **approval-row id** — not the parent entity (verified, §7 V4). | `audit_event` carries `entity_type`+`entity_id`; a use case's events span many entities, and several key to the join/approval row rather than the parent. | §7 V1, V4; §4.4 |
| D5 | **ATO-basis honesty.** ATO row authoritative (text-stamped tier/identity/residual + `assessment_id, submission_round, assessment_version`); referenced assessment shown as **current state, may have drifted**, never reconstructed. | Assessment is mutable-in-place; AIIA versioning deferred (STATE §5). | STATE §5; inv 32 |
| D6 | Export stages `export.generated` (scope, scope_id, framework_filter, content_hash, manifest summary in `detail`). | Handing over the record is a disclosure/custody act, like `evidence.access`. | inv 5; `evidence.access` precedent |
| D7 | Export request runs at **`REPEATABLE READ`** on a **self-owned session** (the `evidence_service` precedent — STATE §4 third shape): the route depends on `get_tenant_context` (no session), and the export session sets `isolation_level="REPEATABLE READ"` via `execution_options` at acquisition, then `SET LOCAL app.current_tenant` from `ctx.tenant_id`, then assembles — and **owns the `export.generated` commit** itself. Isolation set before the first query; **never** raw `SET TRANSACTION` after `SET LOCAL`. | Multi-use-case pack must be internally consistent; Postgres requires the isolation level before the transaction's first statement, and `SET LOCAL` is a statement. Does not reuse `get_tenant_db` (which would own the commit and run READ COMMITTED). | inv 27 cousin; STATE §4 |
| D8 | Pack shapes: **system**, **use-case**, **ATO document**, **framework** (thin: coverage framework-filtered + substantiation manifest). | System/use-case/ATO are EXP-1/1a core; framework is EXP-1's "or a framework", cheap as `coverage_service` reuse. | PRD §4.10; A#1 |
| D9 | Actor durability: ATO text stamps; other actors join `membership`; `export.generated` generator **inherits** the deferred `AuditEvent` actor-durability gap. | Solving the cross-cutting gap piecemeal is out (STATE §5). | inv 2, 34; STATE §5; A#4 |
| D10 | Gate = existing any-governance-role read dependency (auditor consumes read-only). | EXP-2 scoping deferred. | PRD §2 |
| D11 | The audit closure **includes the system's linked vendor/product approval-row ids** (`vendor_approval.id`/`product_approval.id`, since those events key to the approval row — §7 V4), so `vendor_approval.set`/`product_approval.set` clearance events appear; scoped to the system's *specific* vendor/product — preserving exclusivity. | Vendor/product clearance is part of the gate basis an auditor needs; omitting it leaves "cleared on date X" out of the record. | §4.4; A#8; §7 V4 |
| D12 | `source_ip` is **excluded** from the export audit projection by default; retained internally. | Exporting IP into a deliverable that leaves the system is a privacy expansion (§6 NFR — minimal PII). | §6 NFR; A#9 |
| D13 | **Audit-grade export uses evidence-backed coverage.** A `SATISFIED` link counts as satisfied only if its item carries ≥1 `assessment_item_evidence` row; otherwise it **downgrades to `PARTIAL`** ("asserted, unsubstantiated"), never drops. Implemented as `require_evidence_for_satisfied` on `coverage_service` — passed `True` on **every** export coverage call (use-case, system, framework), `False` (default) for the 7a view. Breakdown carries a **first-class `downgraded_unsubstantiated` count**, not folded into the partial total. | An unsubstantiated satisfaction claim must not read `SATISFIED` in the audit deliverable; downgrade-not-drop keeps a control that *was* assessed from falsely reading `UNADDRESSED`; a distinct count lets an auditor separate it from genuine partials. | 7a D5 (tightened); inv 20; A#7 |
| D14 | **The audit closure scopes ephemeral/removal events by `detail` back-ref, not by current link-row ids.** Link rows hard-delete (no soft-delete column — verified), so a removed link's id is unrecoverable and a current-rows closure drops both the `.created` and `.deleted` events of any removed link (add/remove pairs vanish). `entity_type ∈ {assessment_item_control, assessment_item_evidence}` and `.deleted` events are therefore matched by their `detail` back-reference to an in-scope item/assessment (B5), surviving the row's deletion. Bounded accepted residual: events about a fully-deleted intermediate whose `detail` no longer resolves to a surviving in-scope entity. | A current-rows closure is not merely incomplete on removals — it makes add/remove link pairs invisible entirely. Detail-back-ref survives the hard delete. "Complete closure" → "complete for events resolvable to a surviving in-scope entity." | §4.4; §7 V4, B5; PRD EVD-2 |

---

## 3. Reuse (no foundation is reinvented)

| Existing | Reused for |
|---|---|
| `SystemDetail` assembly | Register-facts section |
| `Classification` (versioned, overrides, sign-offs, text-stamped basis) | Classification-history section — already point-in-time faithful |
| AIIA/feeder item model + control/evidence links | Assessment-record section — extended by the new feeder-private assembler (D3) |
| `coverage_service` (7a) | Coverage section + framework substantiation |
| `Evidence` + `assessment_item_evidence` + hardened `GET /v1/evidence/{id}` | Evidence manifest (D2) + out-of-band retrieval |
| `LifecycleTransition` | Lifecycle-trail section |
| `DeploymentAuthorisation` + `GET .../authorisation` (`live_state`) | ATO section + ATO document |
| `AuditEvent` (`entity_type`/`entity_id`, RLS, immutable) | Audit-trail section (D4) |
| Tenant-plane "no external call" service shape | `export_service`: assemble → stage `export.generated` → flush |
| Any-governance-role read gate | Endpoint gating (D10) |

---

## 4. Pack assembly

### 4.1 Shapes & endpoints

All export endpoints live in a **new `app/routers/v1/export.py`**, registered under `/v1`. `GET /v1/use-cases/{id}/authorisation/document` coexists with lifecycle.py's exact `/authorisation` — distinct exact paths, no conflict.

| Endpoint | Scope | Body |
|---|---|---|
| `GET /v1/systems/{id}/export` | system | register + every use-case record (§4.2) + system coverage + system audit closure |
| `GET /v1/use-cases/{id}/export` | use case | one use-case record (§4.2) |
| `GET /v1/use-cases/{id}/authorisation/document` | ATO | ATO basis document (§4.3); `404` if never authorised |
| `GET /v1/export?framework=` | framework | coverage (framework-filtered) + substantiation manifest |

All stage `export.generated`. No `If-Match`. `framework=` optional on system/use-case shapes.

### 4.2 Use-case record — sections

1. **Register facts** — `SystemDetail` assembly.
2. **Classification history** — all `Classification` rows for the use case (by `use_case_id`), ordered by version; `tier` vs `proposed_tier`, the `overridden` flag, `rationale`, text-stamped basis (`basis_subcategory_code`/`basis_legal_ref`), `status`. The **sign-off actor is not a column** on `classification`; it is captured by the `classification.signed_off` audit event, which the §4.4 closure already collects via the classification id.
3. **Assessment record** — **native AIIA items only** (sections, response, likelihood/severity/residual, mitigation, treatment, provenance), control links, evidence links; **plus each feeder as a complete sub-record including feeder-private sections** (D3), each feeder item carrying `surfaces_into` (the AIIA section_key it maps to, or null if private). No re-assembly, no dedup.
4. **Evidence manifest** — deduped, by reference (D2): `id, sha256, filename, content_type, size, back-refs[item_id]`.
5. **Coverage** — `coverage_service(scope=assessment, require_evidence_for_satisfied=True)` (D13). The system pack's system-coverage and `build_framework_export`'s coverage pass `require_evidence_for_satisfied=True` too — every export coverage call is audit-grade.
6. **Lifecycle trail** — `LifecycleTransition` rows `WHERE use_case_id=:uc` ordered by `occurred_at`; project `from_state, to_state, occurred_at, actor (membership join on actor_user_id — nullable, SET NULL on user delete), reason, triggered_by`.
7. **ATO(s)** — every `DeploymentAuthorisation` row for the use case, each with `live_state`.
8. **Audit trail** — entity-id closure (§4.4).

### 4.3 ATO document (EXP-1a)

The `DeploymentAuthorisation` row(s) — authoritative, durable. Defaults to most recent; `?round=` selects a cycle. Actor attribution prefers the text stamps (`authorised_by_name`/`email`), **falling back to a `membership` join on `authorised_by_user_id` when the stamp is null** (the columns are nullable). Accompanied by the **current** read of the referenced assessment + classification, labelled `basis_is_current_state_not_authorisation_snapshot: true` (D5).

### 4.4 Audit-trail closure (D4, D11, D12, D14)

An event is in the use case's (system's) audit trail if **either**:

**(a) durable-entity closure** — `entity_id ∈` `{use_case_id}` (lifecycle.*) `∪ {classification ids}` `∪ {AIIA id + feeder ids}` `∪ {assessment_item ids}` `∪ {deployment_authorisation ids}` `∪ {linked-evidence ids}` `∪ {vendor/product approval-row ids}`. System pack adds `{system_id}` and unions over its use cases. Captures every event keyed to an entity that still exists (creates + updates).

**(b) ephemeral/removal events** — `entity_type ∈ {assessment_item_control, assessment_item_evidence}` (control-link / evidence-link create **and** delete), matched by `detail->>'item_id' IN (in-scope item ids)` (compared as text — `detail` stores `str(item_id)`; verified for `control_link.deleted`/`evidence.linked`/`evidence.unlinked`, and `control_link.created` per pre-flight). This survives the link row's hard delete.

**Why (b) (D14):** link rows hard-delete (no soft-delete column — verified). A removed link's id is unrecoverable from current tables, so a current-rows closure drops not just the `.deleted`/`.unlinked` event but also the matching `.created` event whenever the link was later removed — add/remove pairs go invisible. The `detail.item_id` back-ref survives the deletion and captures both.

**Bounded residual (accepted, characterised):** two events carry `detail={}` and so can't be use-case-scoped once their row is gone — `assessment.deleted` (only reachable for *pristine, un-worked* assessments → near-zero content) and `evidence.access` on evidence that has since been **unlinked** (caught only while it remains linked, via path (a)'s linked-evidence ids). `evidence.deleted` *also* has `detail={}`, but the delete guard forbids deleting *linked* evidence — so a deleted evidence row was never in this use case's scope, and its exclusion is correct, not a gap. The completeness claim is "complete for events resolvable to a surviving in-scope entity", not "complete closure".

**Exclusivity** holds: (b) matches only events whose `detail` back-refs an in-scope item/assessment; `governance_role.*` (assignment id) / `member.created` (membership id) are neither in (a) nor carry an in-scope item back-ref, so they stay out.

Project `action, occurred_at, actor (membership-joined), entity_type, entity_id, detail` — **`source_ip` excluded** (D12), ordered by `occurred_at`. The exact `detail` predicate is pinned by B5.

---

## 5. API & response model

### 5.1 Schema impact

**No new table, no ALTER, no enum, no migration.** All new types are response shapes in `app/schemas/export.py`, NEW: `UseCaseExportRead`, `SystemExportRead`, `AssessmentExportRead`/`FeederExportRead` (incl. `surfaces_into`), `EvidenceManifestEntryRead`, `LifecycleTrailEntryRead`, `AuditTrailEntryRead`, `AtoDocumentRead`, `FrameworkExportRead`.

### 5.2 Service

```
build_use_case_export(db, use_case_id, *, framework=None) -> UseCaseExportRead
build_system_export(db, system_id, *, framework=None) -> SystemExportRead
build_ato_document(db, use_case_id, *, round=None) -> AtoDocumentRead
build_framework_export(db, framework) -> FrameworkExportRead
```

Each: assemble (reads, REPEATABLE READ per D7) → compute canonical `content_hash` → stage `export.generated` → **commit (the self-owned export session owns the commit; not `get_tenant_db`)**. No external call. New audit action: `export.generated` (text column — no migration).

---

## 6. Invariants

40–45 are **new appends** to STATE.md §6 (currently ends at 39 after 7a).

- **40 (new):** Export references evidence by manifest only — never bytes, never embedded presigned URLs; retrieval is the hardened `GET /v1/evidence/{id}`. *(D2; inv 6, 22.)*
- **41 (new):** The export's AIIA section is **native items only**; feeder content appears solely as full feeder sub-records with `surfaces_into` cross-refs. The export never calls `assemble_aiia_items` and never re-surfaces or duplicates feeder items. *(D3; inv 16.)*
- **42 (new):** Export generation is a disclosure act and stages `export.generated`; it is the only audit-writing read besides `evidence.access`. *(D6; inv 5.)*
- **43 (new):** The export is a live cursor + canonical `content_hash`; no persisted/frozen artifact exists in MVP. *(D1; inv 25 family.)*
- **44 (new):** ATO-basis honesty — the `DeploymentAuthorisation` row is the authoritative basis; the referenced assessment is presented as current state, never reconstructed (until AIIA versioning exists). *(D5; inv 32; STATE §5.)*
- **45 (new):** The audit-trail section is the **durable-entity closure OR detail-back-ref** match — ephemeral/removal events (`assessment_item_control`/`assessment_item_evidence`, `.deleted`) are scoped by their `detail` back-ref to a surviving in-scope entity, since the keyed link/row hard-deletes and a current-rows closure would drop add/remove pairs entirely. Never the unscoped tenant log; `source_ip` excluded. Completeness is "resolvable to a surviving in-scope entity", with a bounded documented residual. *(D4, D11, D12, D14; §4.4; §7 V4, B5.)*
- **23, 25, 4, 2/34 (apply):** typed-column enum binding; live recomputation; `irontrustai_app` under RLS, no new role/migration; actor reads via `membership`.

---

## 7. Source-verification status

| ID | Fact | Status |
|---|---|---|
| V1 | `audit_event`: `entity_type NOT NULL`, `entity_id` (nullable, indexed), `occurred_at` (indexed), `detail jsonb`, `source_ip inet`, RLS, immutability trigger; `action` is `varchar(120)` (text, not enum) → new action string needs no migration | **Verified** (`\d audit_event`) |
| V2 | `assessment` carries `use_case_id` + `parent_aiia_id` | **Verified** (7a B1) |
| Vc | `Control.code`/`title`; `assessment_status.APPROVED` uppercase | **Verified** (7a `\d control`; 7a B3) |
| V3 | `DeploymentAuthorisation` columns: `use_case_id, assessment_id, submission_round, tier (varchar), assessment_version, authorised_by_user_id, authorised_by_name/email (nullable), authorised_at, residual_risk_statement` | **Verified** (`\d deployment_authorisation`) |
| V4 | action → (`entity_type`, `entity_id`) convention: natural-object key for most; **link-row id** for `control_link.*`/`evidence.linked/unlinked`; **approval-row id** for `vendor_approval.*`/`product_approval.*`; assignment/membership ids (outside closure) for `governance_role.*`/`member.created` | **Verified** (audit-staging grep) |
| V5 | `Classification.use_case_id` (NOT NULL, indexed) | **Verified** (`\d classification`) |
| V6 | `LifecycleTransition.use_case_id` (NOT NULL, indexed) + `from_state/to_state/occurred_at/actor_user_id (SET NULL)/reason/triggered_by` | **Verified** (`\d lifecycle_transition`) |
| V7 | `assessment_item_control` / `assessment_item_evidence` hard-delete on removal (no soft-delete column) | **Verified** (`\d assessment_item_control` — no soft-delete column; STATE evidence-unlink "real removal") |
| V8 | `detail` back-ref for ephemeral/removal events: `control_link.deleted` (1378), `evidence.linked` (1437), `evidence.unlinked` (1470) carry `{item_id, …}`; `assessment.deleted`/`evidence.access`/`evidence.deleted` carry `{}` | **Verified** (grep `detail=`) — §4.4(b) uses `detail->>'item_id'`; residual characterised |
| V9 | self-owned export session establishes RLS (`SET LOCAL app.current_tenant`) in correct order vs connection-level isolation; RLS read returns rows not silent-zero; new `EXISTS(assessment_item_evidence …)` join is item-scoped under RLS | **Live-smoke required** (inv 27 cousin; D13 new path) |

---

## 8. Sequencing

One sprint, depends on 7a (built). The **ATO document is independently shippable** (the row is already export-grade). The **audit-trail section is the one separable risk**: if the action→entity convention (B1) proves inconsistent, that section ships in a follow-up while the rest of the pack lands. Everything else is deterministic assembly over verified shapes.

---

## 9. Edge & failure cases

| Case | Handling |
|---|---|
| Use case never authorised | ATO document `404`; use-case pack still emits, ATO section empty |
| `halted_prohibited` use case | pack still emits — the halt is a governance fact |
| System with no use cases / no assessments | structure with empties; `200`, never `404` |
| Re-authorised use case (multiple ATO rows) | full pack lists all cycles; ATO document defaults to most recent (`?round=`) |
| Evidence reused across systems | referenced in each system's pack (RLS-safe) |
| Anonymised actor | ATO text stamps stand; joined actors show user-id/unknown (inherited §5 gap) |
| Assessment drifted since authorisation | ATO document labels referenced assessment current-state, not basis (D5) |
| Vendor/product clearance lapsed since authorisation | clearance events still in the audit closure (D11); current state shown via `live_state` |
| Large pack | accept large JSON for MVP; async/streamed export deferred (§10) |
| Cross-tenant rows | never assembled (RLS); smoke-test on the real RLS dev DB |

---

## 10. Deferred

- **PDF rendering** (EXP-1 render half — A#10) — JSON only; frontend/later layer.
- **Branded/templated export (EXP-3)** — post-MVP.
- **Auditor-scoped read-only access (EXP-2)** — thin membership addition; post-MVP.
- **Persisted/frozen export artifacts + history** — live computation for MVP (D1).
- **Async / streamed export** for outsized packs.
- **AIIA-versioned historical reconstruction** of the ATO basis — blocked on AIIA versioning (STATE §5); D5 labelling is the interim.

---

## Appendix A — Open decisions (for review disposition)

| # | Decision | Default | Status |
|---|---|---|---|
| 1 | Framework-scoped export in 7b or defer? | include — thin coverage(framework=) + substantiation | proposed-resolved |
| 2 | Evidence manifest-by-reference vs embedded URLs | manifest-by-reference (D2) | proposed-resolved |
| 3 | Live pack vs persisted/frozen artifact | live + `content_hash` (D1) | proposed-resolved |
| 4 | `export.generated` durability | inherit `AuditEvent` gap (D9) | proposed-resolved |
| 5 | ATO document most-recent default + `?round=` | yes | proposed-resolved |
| 6 | Linked-evidence custody events in the closure | include (custody is part of the record) | proposed-resolved |
| 7 | (from 7a A#1) disposition-only coverage — settle before export is audit-grade | **tighten — evidence-backed in export (D13)** | **resolved** |
| 8 | Vendor/product approval events in the closure | include, scoped to system's linked vendor/product (D11) | proposed-resolved |
| 9 | `source_ip` in the export audit projection | exclude by default (D12) | proposed-resolved |
| 10 | EXP-1 PDF deferral | accept JSON-only as MVP stage; PDF later | proposed-resolved |

## Appendix B — Source-verification register

| # | Item | Status |
|---|---|---|
| B1 | action → (`entity_type`, `entity_id`) convention | **Closed** — link-row id for control/evidence-link events; approval-row id for approvals; gov-role/member outside closure |
| B2 | `Classification.use_case_id` | **Closed** — present, NOT NULL, indexed |
| B3 | `LifecycleTransition.use_case_id` + trail fields | **Closed** |
| B4 | `DeploymentAuthorisation` column names | **Closed** — `authorised_by_name/email` nullable |
| B5 | `detail` back-ref shape for link/removal events | **Closed** — `control_link.deleted`/`evidence.linked`/`evidence.unlinked` carry `detail.item_id`; §4.4(b) = `detail->>'item_id' IN (items)`. Residual: `assessment.deleted` (pristine-only) + `evidence.access`-on-unlinked carry `detail={}`. **Pre-flight micro-confirm:** `control_link.created` (line 1350) carries `item_id` (expected; if not, add current link-row ids to path (a) for created events). |
| B6 | link-table hard-delete | **Closed** — no soft-delete column on `assessment_item_control`; STATE confirms evidence-unlink hard-removes |