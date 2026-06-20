# Sprint 6a — AIIA Review & Sign-off

**Status:** v1 — execution handoff. Plan-mode: propose edits before applying.
**Predecessor:** Sprint 5 (lifecycle/gates/approvals, shipped). **Blocks:** Sprint 6b (authorisation/ATO).
**Design:** `docs/design/sprint-6-review-authorisation-v1.1.md` — work items cite its §/inv/D/V tags; do not restate rationale here.
**Scope:** assessment status lifecycle (`DRAFT→IN_REVIEW→APPROVED`, `reopen→NEEDS_REFRESH`, `changes→DRAFT`), `AssessmentReview` table, review queue, `assessment_gate` refactor, act-level SoD, status-aware authoring lock + pristine-delete. Authorisation/ATO is 6b.
**Out of scope:** everything in design §11; the `DeploymentAuthorisation` table and `authorisation_gate` (6b).

---

## WI-0 — Source verification (gating; no code until clear)
Verify against live DDL / `app/services/`, **not** the test DB.
- V1: `Assessment.lock_version` present (`int not null default 0`) → keeps §3.1 `[PRESENT]`.
- V2: `AssessmentStatus` members incl. `NEEDS_REFRESH`; `assessment_status` label case in `pg_enum` (uppercase member names) — inv 23.
- V4: `structural_assessment_readiness()` / `treatment_readiness()` will be **extractions** of the Sprint-5 `assessment_gate` structural part and `treatment_gate`, single loci (as `classification_readiness` was) — confirm current shapes in `lifecycle_gates.py`.
- V5: whether `propose_risk_set()` always yields ≥1 `AI_SUGGESTED` item (informational; WI-6 is correct regardless).
- V7: `_is_pristine` location/shape in `assessment_service.py`.
- V8: confirm new-table RLS+grants must be hand-edited (CLAUDE §4).
- V9: `ReviewDecision` will be created uppercase; CHECK literal matches stored label.

**Done when:** each item confirmed in writing against `\d`/source; any deviation (e.g. `lock_version` absent → `[ALTER]`) folded back before WI-1.

## WI-1 — Migration: enums, `Assessment` columns, `AssessmentReview`
Depends: WI-0.
- `base.py`: add `ReviewDecision` enum (`APPROVED`, `CHANGES_REQUESTED`, uppercase). Add `AssessmentStatus.NEEDS_REFRESH` if V2 shows it missing.
- `assessment.py` `Assessment` `[ALTER]`: `submitted_by_user_id` (FK→`app_user`, `RESTRICT`, nullable), `submitted_at`, `submission_round` (`int not null default 0`).
- `assessment.py` `AssessmentReview` `[NEW]` (design §3.2): `id`, `tenant_id`, `assessment_id` (FK→`Assessment`, `RESTRICT`), `reviewer_user_id` (FK→`app_user`, `RESTRICT`), `decision` (`ReviewDecision`), `note` (text, nullable), `submission_round` (int), `created_at`.
- Hand-edit the generated revision (CLAUDE §4): RLS policy on `assessment_review` reading `app.current_tenant`; `irontrustai_app` DML grants; `CHECK (decision <> 'CHANGES_REQUESTED' OR note IS NOT NULL)`.

**Done when:** `alembic upgrade head` on a fresh volume succeeds; `\d assessment_review` shows RLS enabled, the CHECK, and app-role grants; `ReviewDecision` labels uppercase in `pg_enum`. **Test area:** migration smoke on real dev DB (STATE §4).

## WI-2 — `assessment_gate` refactor
Depends: WI-1, WI-0/V4.
- In `lifecycle_gates.py`: extract `structural_assessment_readiness()` (current structural logic: AIIA exists, required feeders present, no still-`AI_SUGGESTED` items) and add `assessment_approved()` (`status == APPROVED`). `assessment_gate` = both AND-ed (design §6.1). `create_aiia` and any existing caller of the structural part now call `structural_assessment_readiness()` — one locus, no re-impl.

**Done when:** an AIIA that is structurally complete but not `APPROVED` now yields `assessment_gate = BLOCK` (was PASS); existing structural-readiness assertions unchanged. **Test area:** lifecycle gate tests.

## WI-3 — Act-level SoD predicate + inv 7 amendment
Depends: WI-0.
- New `assert_distinct_workflow_actor(...)` (design §4.4) — the **only** act-time SoD locus; no inline conflict logic elsewhere. Checks used in WI-4: `reviewer ≠ submitted_by`; (authoriser checks land in 6b).
- Amend STATE inv 7 to the revised wording (design §8.1): assignment-time SoD via `assert_governance_assignable()`, act-time via `assert_distinct_workflow_actor()`.

**Done when:** a `reviewer == submitted_by` review attempt is rejected by the predicate; no second conflict-logic path exists. **Test area:** SoD tests.

## WI-4 — `assessment_review_service` (submit / record_review / reopen)
Depends: WI-1, WI-2, WI-3. New file `app/services/assessment_review_service.py`. Simple tenant-plane shape (STATE §4) — no mid-request commit. Every status write is a single conditional `UPDATE … WHERE id=:id AND lock_version=:expected AND status=:from` → `412` (stale lock) vs `409` (bad from-state), inv 14.
- `submit_for_review` (`system_owner`): pre-check `structural_assessment_readiness()` AND `treatment_readiness()` → `409`; `DRAFT|NEEDS_REFRESH → IN_REVIEW`; bump `submission_round`; stamp `submitted_by/at`; audit `assessment.submitted`.
- `record_review` (`reviewer`): `assert_distinct_workflow_actor` (`reviewer ≠ submitted_by`); require `IN_REVIEW`. `APPROVED` → `APPROVED`, stamp `approved_by/at`, insert `AssessmentReview`, audit `assessment.review_recorded`, **then `advance_use_case()` in the same transaction**. `CHANGES_REQUESTED` → `DRAFT`, insert `AssessmentReview` (note non-null by CHECK), audit.
- `reopen` (`system_owner`): `APPROVED → NEEDS_REFRESH`; audit `assessment.reopened` + `assessment.needs_refresh`; no advance call.

**Done when:** the §7.1 status cycle is traversable; stale `If-Match` → `412`, wrong from-state → `409`; approve advances the use case single-hop `under_assessment → pending_authorisation` (treatment already satisfied, design §6.2). **Test area:** assessment-review service tests + lifecycle-advance integration.

## WI-5 — Status-aware authoring lock (incl. feeders)
Depends: WI-1.
- In `assessment_service.py` item-mutation paths (`amend_item`, `confirm_item`, control-link, evidence-link): reject (`409`) when the **parent AIIA** status ∈ `{IN_REVIEW, APPROVED}` (inv 31). Lock must reach feeder items (resolve parent via `parent_aiia_id`).

**Done when:** item write and feeder-item write under `IN_REVIEW`/`APPROVED` → `409`; both allowed under `DRAFT`/`NEEDS_REFRESH`. **Test area:** assessment-item + feeder mutation tests.

## WI-6 — Status-and-history-aware pristine-delete
Depends: WI-1, WI-5. (ATO clause added in 6b WI-5.)
- Extend `_is_pristine` (design §4.5, inv 36): block DELETE unless `status == DRAFT` **and** no `AssessmentReview` row references the assessment — on top of inv 17's existing conditions.

**Done when:** an all-blank `APPROVED` AIIA (no risks, no feeders) → DELETE `409`; a never-reviewed `DRAFT` pristine AIIA → DELETE `200`. **Test area:** pristine-delete tests (add the all-blank-approved case).

## WI-7 — Endpoints + queue
Depends: WI-4. Routers in `app/routers/v1/`, registered in `app/main.py`; `*Read`/`*Create` schemas in `app/schemas/`.
- `POST /v1/assessments/{id}/submit` (`system_owner`, `If-Match`).
- `POST /v1/assessments/{id}/review` `{decision, note}` (`reviewer`, `If-Match`).
- `POST /v1/assessments/{id}/reopen` (`system_owner`, `If-Match`).
- `GET /v1/assessments/review-queue` (`reviewer`): `status = IN_REVIEW AND submitted_by != caller`; actor names resolved via `membership` join, never bare `app_user` (inv 34).

**Done when:** gates enforced; queue excludes the caller's own submissions; submitter/reviewer names resolve through `membership`. **Test area:** router tests + RLS-scoped queue test on real dev DB.

## WI-8 — Audit + docs + live-smoke
Depends: WI-1..7.
- Confirm audit action strings emitted: `assessment.submitted`, `assessment.review_recorded`, `assessment.reopened`, `assessment.needs_refresh`.
- Update STATE.md: §3 capability prose (review/sign-off), invariants 28, 30 (partial — authoriser term in 6b), 31, 34, 36 + revised inv 7; §5 (review/sign-off no longer fully deferred). Update CLAUDE.md audit-action set.
- Live-smoke the full path against the real RLS dev DB (`docker compose up -d`, `alembic upgrade head`, real `SessionLocal`) — enum case + RLS-scoped queue (STATE §4, inv 23).

**Done when:** STATE/CLAUDE reflect 6a; live-smoke green on the real schema, not just the test suite.

---

### 6a dependency order
WI-0 → WI-1 → {WI-2, WI-3} → WI-4 → {WI-5, WI-6, WI-7} → WI-8.