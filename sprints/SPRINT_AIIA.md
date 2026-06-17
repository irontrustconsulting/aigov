# Sprint: AIIA Core (Phase A)

## 1. Sprint title

**AI System Impact Assessment — creation, population, and structure (ISO/IEC 42005-aligned, EU AI Act tier-scoped).**

Builds the full backend for creating and populating an AIIA — one per use case — with required/recommended sections instantiated from a tier-scoped template, identity-only proposed risks, snapshot-frozen register facts, explicit confirm/amend provenance, control links, optimistic concurrency, and pristine-delete. This is **Phase A** of `docs/AIIA_DESIGN.md` (v2.7, all decisions resolved): a demoable vertical slice. Feeders (FRIA/DPIA/MODEL_RISK) and read-time propagation are **Phase B**, out of scope here.

**Full design spec:** `docs/AIIA_DESIGN.md`. This sprint file is the execution contract; defer to the design doc for rationale and edge-case detail, don't duplicate it.

---

## 2. Status going in / context

**On the ground (reuse, don't rebuild):**

- `Assessment`, `AssessmentItem`, `AssessmentItemControl`, `AssessmentItemEvidence` models exist (`app/models/assessment.py`) with the columns the design doc marks "present." None of the design's required ALTERs exist yet — verified directly against the models and `alembic heads` (`476d462a2a9c`, no `aiia_core_migration.py` on disk).
- `ProvenanceConfidence` enum (`app/models/base.py`) has four values (`AI_SUGGESTED`, `CATALOGUE_CURATED`, `USER_CONFIRMED`, `USER_AMENDED`) — `USER_PROVIDED` is not yet added.
- `Classification` is read-only for this feature: `resolve_classification(system_id, db)` (pure proposal, not override-aware) and `snapshot_classification(...)` (writer) both exist in `app/services/classification.py`. **AIIA creation calls neither** — it reads the use case's current `Classification` row (`is_current=True`) directly for the override-aware effective `tier`, `version`, and rationale/basis.
- Governance role gating (`require_governance_role`) and the tenant-endpoint contract (`get_tenant_db`, `ctx.tenant_id`) are established patterns — see `app/routers/v1/use_cases.py`, `classification_context.py` for the shape to mirror.
- Tenant-plane audit pattern: stage `AuditEvent` in the session, commit atomically with business rows (see `app/services/system_service.py`). No external calls in this feature, so the six-step Cognito-style ordering does **not** apply — it's pure DB.
- No optimistic-concurrency (`If-Match` / `lock_version`) pattern exists anywhere in the codebase yet — this sprint introduces it for the first time.
- The `8b7d2f48a456_governance_role_model.py` migration is the reference pattern for hand-adding RLS policy + reference-data seed in one revision.

**Not redoing:** Classification resolution/override machinery, governance role/SoD model, catalogue/risk/control library seeding (reused read-only), the tenant-endpoint or audit patterns themselves.

---

## 3. Goal / contract

A holder of `system_owner` can create one current AIIA per use case, scoped to its current EU AI Act tier; required sections and identity-only proposed risks are pre-filled; register facts are snapshotted (resolved labels frozen) as `USER_PROVIDED`. `system_owner`/`contributor` can author items, confirm or amend proposed risks (explicit, server-derived provenance, disposition-before-authoring enforced), link controls, and delete a pristine AIIA. All mutations are optimistically concurrent (`If-Match` / `lock_version`) and atomically audited. Reads are gated to any of the five governance roles; reference-library reads are member-level.

---

## 4. Domain model / rules

See `docs/AIIA_DESIGN.md` §3–§4 for full field-level detail. Summary of what this sprint adds:

- **`assessment`**: `tier_snapshot`, `classification_version` (both load-bearing, NOT NULL after backfill), `is_current` (default true), `lock_version` (concurrency token, distinct from the existing run-level `version`), `created_by`. `uq_one_aiia_per_use_case` evolves to `WHERE type='AIIA' AND is_current`.
- **`assessment_item`**: `section_key` (load-bearing — the whole section model keys on it), `residual_likelihood`/`residual_severity` (nullable until a mitigation exists — never default to zero), `selection_basis`, `source_ref`, `created_by`, `lock_version`.
- **`assessment_item_control`**: `tenant_id` + RLS (parity decision), `UNIQUE(item_id, control_id)`, `control_id` FK `CASCADE → RESTRICT`.
- **`assessment_item_evidence`**: `tenant_id` + RLS.
- **`assessment_item.risk_id`** FK: `SET NULL → RESTRICT` (library deletion can't orphan an `AI_SUGGESTED` item's only substance).
- **New global reference table `assessment_section_template`**: `(type, tier, section_key)` unique; `applicability` (new enum `required|recommended|not_applicable`), `prompt`, `iso_42005_clause`, `aiia_target_section_key` (feeder-only; unused this sprint but the column ships now).
- **New enum value**: `provenance_confidence += USER_PROVIDED`.
- **Provenance is server-derived, never client-set** — must not appear in any request body (§4 of the design doc is the authority here; the state machine table there governs confirm/amend/author transitions exactly).
- **Risk proposal is identity-only.** The system proposes `risk_id` + `selection_basis`; it never proposes `likelihood`/`severity`/`mitigation_plan` — those are always authoring fields.

---

## 5. Work items

**WI-1 — Schema migration (`aiia_core_migration`).**
New revision, `down_revision='476d462a2a9c'`. All ALTERs from §4 above; `assessment_section_template` CREATE; RLS policy on the two join tables (mirror `8b7d2f48a456`'s `tenant_isolation` policy verbatim); backfill `tier_snapshot`/`classification_version` from each use case's current `Classification` before the NOT NULL constraint (fails loudly if any use case lacks one — that's a data-integrity bug, not a thing to paper over). If `ALTER TYPE ... ADD VALUE 'user_provided'` can't run in the same transaction as its first use on this PG version, split it into its own preceding revision.

**WI-2 — Section template data-seed migration.**
Separate revision. Section rows for `(AIIA, tier, section_key)` per ISO/IEC 42005 clause, `required`/`recommended`/`not_applicable` per tier. Feeder rows (`FRIA`/`DPIA`/`MODEL_RISK` types, `aiia_target_section_key`) seed now even though feeders aren't built until Phase B — the template is reference data, cheap to seed ahead. Idempotent loader, mirroring `seed_governance_roles.py`.

**WI-3 — ORM model updates.**
`app/models/assessment.py` + `base.py`: add every new column/enum value to match the migration exactly. No behavioural code yet.

**WI-4 — `AssessmentService.create_aiia`.**
`app/services/assessment_service.py` (new). One tenant transaction, no external call:
1. Use case in tenant; read current `Classification` snapshot; reject `PROHIBITED` (409/422) and `REQUIRES_CONTEXT` (409); no current snapshot at all → 409 (data-integrity guard).
2. Assert the `(AIIA, tier_snapshot)` template is non-empty — empty is a seeding bug, fail loudly, never create an empty shell.
3. Pre-fill: required sections → `CATALOGUE_CURATED` items (blank response); register facts → `USER_PROVIDED` snapshot items with `source_ref`, **resolved labels frozen** for FK dimensions (operator-role/hosting-model/usage-context/human-oversight-type names, not just ids); `propose_risk_set(...)` → `AI_SUGGESTED` items with `selection_basis`.
4. Stage one `assessment.created` AuditEvent (template version, proposed risk ids, counts); commit atomically.

**WI-5 — `propose_risk_set(tier, modality_tags, catalogue_product_id, db)`.**
Pure read composition over the Risk Library + `CatalogueProductRisk`. Identity + `selection_basis` only. Deterministic, unit-testable in isolation. No `CatalogueProductRisk`/no product → succeeds with a possibly-empty proposed set (best-effort, not an error).

**WI-6 — Item mutation services.**
- `amend_item` — real content change only → `assessment_item.amended` (field-level before/after); content-less PATCH is a no-op (no event, no provenance change). Conditional update on `lock_version` (`If-Match` mismatch → 412).
- `confirm_item` — `POST .../confirm`; valid only from `AI_SUGGESTED`; conditional `UPDATE ... WHERE provenance IN (valid_from) AND lock_version = :expected` (never read-then-write) → `USER_CONFIRMED` + `assessment_item.confirmed`; 0 rows → 409.
- Disposition-before-authoring: an authoring-only PATCH on a still-`AI_SUGGESTED` item → 409 ("confirm or amend the proposed risk first"). Section-prompt items are exempt.
- `delete_item` — audited cascade of control links.
- Control-link create/delete — `UNIQUE(item_id, control_id)` violation → 409; unknown `risk_id`/`control_id` → 422; bad `coverage` → 422.
- `delete_assessment` — pristine only (no confirms/amends/control-links/feeders); else 409 ("use void — deferred to Sprint 6").

**WI-7 — Router (`app/routers/v1/assessments.py`).**
All 12 endpoints from `docs/AIIA_DESIGN.md` §6, registered under `/v1` in `app/main.py`:

| Endpoint | Gate |
|---|---|
| `POST /v1/use-cases/{id}/assessments` | `system_owner` |
| `DELETE /v1/assessments/{id}` | `system_owner` |
| `GET /v1/use-cases/{id}/assessments` | any of five |
| `GET /v1/assessments/{id}` | any of five |
| `GET /v1/assessments/{id}/sections` | any of five |
| `POST /v1/assessments/{id}/items` | `system_owner`, `contributor` |
| `PATCH /v1/assessments/{id}/items/{item_id}` | `system_owner`, `contributor` |
| `POST /v1/assessments/{id}/items/{item_id}/confirm` | `system_owner`, `contributor` |
| `DELETE /v1/assessments/{id}/items/{item_id}` | `system_owner`, `contributor` |
| `POST /v1/assessments/{id}/items/{item_id}/control-links` | `system_owner`, `contributor` |
| `DELETE /v1/assessments/{id}/items/{item_id}/control-links/{link_id}` | `system_owner`, `contributor` |
| `GET /v1/reference/risks`, `GET /v1/reference/controls` | `require_role` (member) |

`Admin` (the administrative axis) gets 403 on every assessment endpoint, reads included — name the missing role in the 403. The feeder endpoints (`POST/DELETE .../feeders`) are **not** built this sprint (Phase B) — `parent_aiia_id`-bearing rows simply don't exist yet.

**WI-8 — Schemas (`app/schemas/assessment.py`).**
`AssessmentCreate`/`Read`, `AssessmentItemCreate`/`Read`/`Amend`, `SectionRead`, `ControlLinkCreate`/`Read`. Provenance is never an accepted input field on any schema.

**WI-9 — Tests.** See §12.

*Deferred to later sprints (not this one): feeders (Phase B), evidence upload (Sprint 4), status transitions/sign-off/worked-state void (Sprint 6), AI-assisted drafting, AIIA versioning/refresh cycle, system-level rollup (next slice, separate sprint).*

---

## 6. Constraints / non-negotiables

- **Provenance is server-derived, never client-set** — absent from every request body (design doc §4 invariant).
- **The system never proposes scores.** `likelihood`/`severity`/`mitigation_plan`/`residual_*` are always authoring fields, even on a proposed-risk item.
- **Disposition-before-authoring** on `AI_SUGGESTED` items, enforced server-side, not just in the UI.
- **All provenance transitions are conditional updates** (`WHERE provenance IN (...) AND lock_version = :expected`), never read-then-write — a stale read corrupts the audit diff.
- **`If-Match`/`lock_version` on every mutating endpoint** — mismatch is 412, distinct from the 409 a from-state guard produces.
- **Audit atomicity** — every mutation's `AuditEvent` is staged and committed in the same transaction as the business rows; never a separate commit.
- **AIIA creation reads only the current `Classification` snapshot** — never calls `resolve_classification()` or `snapshot_classification()`. Overrides flow through automatically because the snapshot's `tier` already reflects them.
- **Pristine-delete only.** A worked AIIA cannot be hard-deleted; that's a 409 pointing at the (not-yet-built) void path.
- **`tenant_id` always from `ctx.tenant_id`**, never the request body, on every new endpoint.
- **No new DB roles, no per-feature RLS exceptions** — the two join tables get the same `tenant_isolation` policy shape as every other tenant table.
- **Reference-data FK hardening is RESTRICT, not CASCADE/SET NULL** — a library risk/control with assessment references in place cannot be deleted; deprecate via soft-flag instead (soft-flag mechanism itself is out of scope here, just don't let the FK silently strip data).

---

## 7. Acceptance criteria

1. `system_owner` creates an AIIA for a `HIGH`/`LIMITED`/`MINIMAL` tier use case → `201`; required sections present as `CATALOGUE_CURATED` items; register facts present as `USER_PROVIDED` items with frozen resolved labels in `source_ref`; proposed risks present as `AI_SUGGESTED` with `selection_basis`; one `assessment.created` AuditEvent.
2. Create on a `PROHIBITED` use case → blocked, no row. Create on `REQUIRES_CONTEXT` → 409, no row. Use case with no current `Classification` at all → 409.
3. Duplicate AIIA for the same use case (including a simulated race) → 409 via the partial unique index.
4. Empty section template for a resolvable tier → loud failure, not an empty AIIA (proves the seeding-bug guard fires).
5. Authoring-only PATCH on a still-`AI_SUGGESTED` item → 409. Confirm on a non-`AI_SUGGESTED` item → 409. Confirm on `AI_SUGGESTED` → `USER_CONFIRMED` + `assessment_item.confirmed` event. Amend on any state → `USER_AMENDED` (or stays put per the §4 state table) + `assessment_item.amended` with field-level before/after. Content-less PATCH → no-op, no event.
6. Stale `If-Match` on any mutating endpoint → 412. Concurrent confirm/amend race → one wins, loser gets 409 (not a corrupted diff).
7. Control-link create with a known `risk_id`/`control_id`/valid `coverage` → 201; duplicate link → 409; unknown id → 422; bad `coverage` → 422.
8. Deleting a library risk/control referenced by an assessment item → blocked (RESTRICT), not silently nulled/cascaded.
9. Delete a pristine AIIA → cascades, `assessment.deleted` staged. Delete a worked AIIA (any confirm/amend/control-link present) → 409.
10. `admin` (administrative axis, zero governance roles) → 403 on every assessment endpoint, including reads; 403 body names the missing governance role.
11. `GET /v1/assessments/{id}/sections` surfaces recommended sections (not yet instantiated) distinctly from required (already instantiated); `POST /items` against a recommended `section_key` instantiates it.
12. `assessment_item_control` / `assessment_item_evidence` RLS: a cross-tenant read via item-id guessing returns nothing — tenant isolation holds independent of item-first access.
13. Reference-read endpoints (`/v1/reference/risks`, `/controls`) succeed for any authenticated member, no governance role required.

---

## 8. Out of scope

- Feeders (FRIA/DPIA/MODEL_RISK creation, propagation, `aiia_target_section_key` assembly) — Phase B, next sprint.
- Evidence file upload / S3 wiring — Sprint 4 (the join table's `tenant_id`+RLS ships now; the upload path doesn't).
- Status transitions, review, sign-off, worked-state void — Sprint 6.
- AI-assisted text drafting, AI-suggested scoring — post-MVP; `ai_suggested_text` stays null/unused.
- AIIA versioning / refresh-on-material-change — post-MVP; `version`/`is_current` ship as seams only, no refresh logic.
- System-level rollup (AIIA-1b) — scheduled as the immediate next slice after this one, not bundled in.
- Object-scoped (per-system) governance roles, bulk "confirm all."

---

## 9. Dependencies / decision notes

All design decisions are pre-resolved in `docs/AIIA_DESIGN.md` §13 — this sprint implements them, it does not re-decide them. Notable ones load-bearing for execution order:

- **Tier source (decided):** current `Classification` snapshot, read directly — never `resolve_classification()`/`snapshot_classification()`. Get this wrong and overrides silently stop propagating.
- **Snapshot vs reference (decided):** register facts are snapshotted (point-in-time, resolved labels frozen) because the register is mutable-in-place; feeders inherit parent scope and never re-resolve. Risks are referenced at read time (Phase B concern, not this sprint, but the `selection_basis` field ships now so Phase A items already carry it).
- **`lock_version` vs `version` (decided):** two different concurrency concepts on the same row — don't conflate the edit-level optimistic token with the run-level AIIA version.
- **Migration split risk:** confirm the live PG version's behavior for `ALTER TYPE ... ADD VALUE` inside a transaction that also uses the new value before committing to a single-revision approach for WI-1.

---

## 10. Implementation contract

**Service entry points:**
- `AssessmentService.create_aiia(use_case_id, ctx, db) -> Assessment`
- `propose_risk_set(tier, modality_tags, catalogue_product_id, db) -> list[ProposedRisk]`
- `amend_item(item_id, patch, expected_lock_version, ctx, db) -> AssessmentItem`
- `confirm_item(item_id, expected_lock_version, ctx, db) -> AssessmentItem`
- `delete_item(item_id, ctx, db) -> None`
- `delete_assessment(assessment_id, ctx, db) -> None` (pristine-only)
- `create_control_link(item_id, control_id, coverage, ctx, db) -> AssessmentItemControl`
- `delete_control_link(link_id, ctx, db) -> None`

**Router:** `app/routers/v1/assessments.py`, registered in `app/main.py` under `/v1`. Every mutating handler reads `If-Match` from the request header, passes it through as the expected `lock_version`, and translates a 0-row conditional update into 412 (lock mismatch) or 409 (from-state guard) per the design doc's distinction.

**Migration:** `alembic/versions/<rev>_aiia_core_migration.py` (`down_revision='476d462a2a9c'`), plus a second `_aiia_section_template_seed.py` revision for WI-2.

**Audit action strings:** `assessment.created`, `assessment.deleted`, `assessment_item.created`, `assessment_item.amended`, `assessment_item.confirmed`, `assessment_item.deleted`, `control_link.created`, `control_link.deleted`.

---

## 11. Execution protocol

1. Read this file fully **and** `docs/AIIA_DESIGN.md` §3–§11 before writing any code — the design doc is the source of truth for field-level and edge-case detail this file summarizes.
2. WI-1 (migration) and WI-3 (models) together first, hand-editing the autogenerated revision per `CLAUDE.md` §4 — RLS, partial indexes, FK hardening, and the enum-value ALTER all need manual attention; autogenerate misses all of them.
3. WI-2 (seed migration) next — confirm WI-1's `assessment_section_template` shape before writing seed rows.
4. WI-4/WI-5 (creation + risk proposal) — get one demoable "create an AIIA" path working end-to-end before touching item mutation.
5. WI-6 (item mutation services) — this is where every invariant in §6 actually gets enforced; budget the most review time here.
6. WI-7/WI-8 (router + schemas) wire WI-4–6 to HTTP; no new business logic at this layer.
7. WI-9 (tests) validates §7 criteria one-by-one — don't declare a criterion done without a corresponding test.
8. Reuse `require_governance_role`/`get_tenant_db`/the tenant-plane audit pattern exactly as in `use_cases.py`/`system_service.py` — no new auth or session-handling primitives.

---

## 12. Validation protocol

**Coverage:** every numbered item in §7, plus: the full confirm/amend state-machine table (design doc §4) exercised from each of its five `from`-states; both 412 (stale `If-Match`) and 409 (from-state guard) on the same endpoint to prove they're distinguishable; the empty-template loud-failure path; RESTRICT-not-CASCADE on both hardened FKs; RLS on both newly-tenant-scoped join tables independent of item-first access.

**Constraint checks (explicit, report each):**
- No request schema accepts a `provenance` field.
- No score field (`likelihood`/`severity`/`mitigation_plan`/`residual_*`) is ever system-populated, including on `AI_SUGGESTED` items.
- Every provenance transition is a single conditional `UPDATE`, not a read followed by a write.
- Every mutating endpoint enforces `If-Match`.
- Every mutation's `AuditEvent` commits in the same transaction as its business-row change.
- AIIA creation never calls `resolve_classification()` or `snapshot_classification()` — grep the new service file to confirm.
- `tenant_id` on every new endpoint comes from `ctx.tenant_id`.
- Pristine-delete check inspects confirms/amends/control-links/feeders, not just row-presence on the assessment itself.

**Reporting:** report the plan-to-work-item mapping, test results per acceptance criterion, and the constraint checks above. Unverified criteria or unreported constraint checks mean the sprint is **not** complete.
