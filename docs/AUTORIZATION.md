# Design — Review, Sign-off & Deployment Authorisation

**Status:** Draft v1.1 — incorporates external review round 1 (see Appendix A). For `docs/`; precedes the 6a/6b sprint specs.
**Scope:** PRD §4.9 (WKF-1..8), §4.1.1 (authorisation gate), §4.5 (AIIA sign-off), §4.10 (EXP-1a ATO data). Closes the Sprint-5 seams listed in STATE §5: *"Reviewer AIIA sign-off (an AND-term on the structural `assessment_gate`), Authoriser residual-risk acceptance, `authorised → deployed → retired` transitions."*
**Companions:** `CLAUDE.md` (how we build), `docs/PRD.md` (what/why), `STATE.md` (what exists, invariants 1–27).
**Δ v1→v1.1:** B1 (ATO cycle-binding + `re_evaluate` ceiling), B2 (inv 7 amendment), B3 (status-aware pristine-delete), NB1–NB5 dispositioned, new §0 source-verification checklist, invariants extended to 37.

---

## 0. Source verification before wiring

Verify against live DDL / `app/services/` (not the no-RLS test DB) before any code is written. Several items below gate the soundness of specific decisions.

| # | Verify | Why it matters |
|---|---|---|
| V1 | `Assessment.lock_version` exists (`int not null default 0`). | **Confirmed present** off `\d assessment`; keeps §3.1 `[PRESENT]`. If absent it is `[ALTER]` and WI-1 must add it. |
| V2 | `AssessmentStatus` member set (`DRAFT`/`IN_REVIEW`/`APPROVED`/`NEEDS_REFRESH`) **and** `assessment_status` label case in `pg_enum`. | CHECK literal + `status=:from` binds depend on labels matching member names. `classification_status` and `eu_ai_act_tier.REQUIRES_CONTEXT` were lowercase-broken in Sprint 5 (inv 23). |
| V3 | **`re_evaluate` current behaviour** in `lifecycle_service.py`: does it already ceiling at `pending_authorisation`, or chase any vector target? | Directly determines whether the B1 stale-ATO hole is live in shipped code. v1.1 makes the ceiling explicit regardless (inv 35). |
| V4 | `structural_assessment_readiness()` / `treatment_readiness()` are **extractions** of the Sprint-5 `assessment_gate` structural part and `treatment_gate` as single loci — not re-implementations (as `classification_readiness` was extracted). | Avoids a second divergent definition of the same readiness. |
| V5 | `propose_risk_set()` — does it always yield ≥1 `AI_SUGGESTED` item for every submittable AIIA? | Determines whether the B3 pristine edge is reachable in practice. The B3 fix makes it moot, but worth knowing. |
| V6 | `DeploymentAuthorisation.assessment_version` source = `Assessment.version` (STATE §5 says `version`/`is_current` exist). | Point-in-time stamp source. |
| V7 | `_is_pristine` location/shape (STATE: `assessment_service.py`) for the B3 status-aware extension. | Where the guard change lands. |
| V8 | New tables `AssessmentReview`, `DeploymentAuthorisation` get **RLS policy + app-role grants** as hand-edited migration steps (CLAUDE §4) — autogenerate misses these. | Same class as the Sprint-5 `lifecycle_transition` RLS/grants check. |
| V9 | `ReviewDecision` created with **uppercase** labels (`APPROVED`/`CHANGES_REQUESTED`); CHECK literal matches the stored label. | inv 23. |

---

## 1. Objective

Governance without sign-off is record-keeping. This feature adds the human-act layer on top of the readiness machinery Sprint 5 wired:

1. The 1st-line **system owner submits** a structurally-complete, treated AIIA for review.
2. A 2nd-line **reviewer** examines it and **approves** (recommends) or **requests changes**.
3. A 2nd-line **authoriser accepts the residual risk** and **grants deployment authorisation** (the ATO).

Each step is governance-role-gated, separation-of-duties-checked at the *act* (not only at role assignment), and written to the immutable trail. The output is a structured ATO record — the data Sprint 7's export renders into a document.

### 1.1 Resolved decisions

| # | Decision | Rationale |
|---|---|---|
| D1 | Split into **6a** (review/sign-off + queue + gate refactor + re-open) and **6b** (authorisation + ATO). | Clean dependency seam; 6a independently valuable/testable; de-risks the gate refactor before the new state is wired. |
| D2 | Review decisions persist in a **dedicated `AssessmentReview` domain table**, not `AuditEvent.detail`. | Matches *substantive act → domain row + audit event* (cf. `Classification` snapshot + `classification.signed_off`). Review thread is first-class export evidence (WKF-2, EXP-1); typed columns give DB-enforced mandatory-note + queryable history. |
| D3 | **Residual-risk acceptance is the authoriser's act** (PRD §4.9.1). Reviewer *recommends* via AIIA approval; authoriser *accepts* + grants ATO. | The recommend≠accept split is the reason reviewer and authoriser are the separated 2nd-line pair. `residual_risk_statement` lives on the ATO, authored by the authoriser. |
| D4 | Workflow-step SoD is a **distinct check** from assignment SoD; **not** routed through `assert_governance_assignable()`. STATE inv 7 amended to scope it (B2). | Assignment SoD is point-in-time on *roles held*; it does not bind *who did what to this object*. Closes the temporal-role-change hole; the check per-object roles will need. |
| D5 | `assessment_gate` = `structural_assessment_readiness()` **AND** `assessment_approved()`. Submit pre-check = `structural_assessment_readiness()` **AND** `treatment_readiness()`. | Single locus for structural readiness. Treatment-before-submit means the reviewer reviews an already-treated assessment and the approval lock never strands treatment authoring (residual risk is a function of treatment). |
| D6 | Reviewer approve and authoriser authorise are **human-act gates**, never auto-advanced. Both `advance_use_case()` and `re_evaluate()` ceiling at `pending_authorisation` (B1/D10). | Mirrors classification sign-off being the human act that stamps `eu_tier`. |
| D7 | The **NEEDS_REFRESH** trigger in scope is the **explicit audited re-open** of an approved AIIA (`APPROVED → NEEDS_REFRESH`). Automatic/material-change (reclassification) trigger deferred — that path does not exist yet. | WKF-3's `needs refresh` is the post-approved-but-stale state; manual re-open is its correct manual producer. Model is refresh-ready for the later automatic trigger. |
| D8 | **PROHIBITED always forces `halted_prohibited`**, including from `authorised`. Wiring `authorised` extends the step-0 halt source set. | inv 26, unconditionally. `authorised` is not a safe harbour. |
| D9 | Wire **`authorised`** only; `deployed`/`retired` stay reserved/unwired. | PRD §3.2 — record-only authorisation. |
| D10 | **`authorised` is entered only by `authorise_use_case`.** `re_evaluate()` may regress out of it or hold it, but never auto-advance a non-authorised use case into it; its auto-advance ceiling is `pending_authorisation`. *(from B1)* | Crossing into `authorised` is always a human act (inv 30). Covers the regressed-then-upstream-restored case where the submission cycle is unchanged. |
| D11 | **ATO validity is cycle-bound.** The ATO stamps `submission_round` at authorise time; `authorisation_gate` passes only when an ATO's `submission_round` matches the assessment's current `submission_round`. *(from B1)* | A re-submitted cycle (round incremented) orphans the prior ATO, so a re-approved-but-not-re-authorised use case cannot satisfy the gate off a stale ATO. Makes the gate verdict correct, not just the procedure. |
| D12 | **Pristine-delete is status-and-history-aware.** Hard-DELETE blocked unless `status == DRAFT` **and** no `AssessmentReview` and no `DeploymentAuthorisation` row references the assessment. *(from B3)* | Removes reliance on the emergent "submittable ⇒ has a disposition" property; guarantees an approved/reviewed assessment is never pristine-deletable regardless of risk-set contents. Subsumes the old O1 FK question. |
| D13 | **The ATO stamps the authoriser's identity (name + email) as text** at write time. The FK-only attribution gap is **explicitly accepted** for `AssessmentReview`/`submitted_by`/`approved_by`, deferred to the cross-cutting actor-durability fix (STATE §5). *(from NB3; ratify-point)* | The ATO is export-grade and already snapshot-as-text (tier/version); an anonymised-but-retained authoriser must not render it unattributable. Reviews defer rather than half-solve a cross-cutting gap inconsistently. |

---

## 2. Scope

### In scope — 6a
- `Assessment` status lifecycle: `DRAFT → IN_REVIEW → APPROVED`, plus re-open `APPROVED → NEEDS_REFRESH` and bounce `IN_REVIEW → DRAFT` (changes requested).
- `AssessmentReview` table; submit / approve / request-changes / re-open services.
- Review queue (eligibility-filtered).
- `assessment_gate` refactor (D5); `assessment_approved()` AND-term; same-transaction `advance_use_case()` on approve.
- Act-level SoD predicate (D4); STATE inv 7 amendment (B2).
- Status-aware authoring lock incl. feeder items (§4.3).
- Status-and-history-aware pristine-delete guard (D12).

### In scope — 6b
- `DeploymentAuthorisation` (ATO) table, incl. `submission_round` (D11) and stamped authoriser identity (D13).
- `authorisation_gate` (6th gate, cycle-matched per D11); `authorise_use_case` service; `pending_authorisation → authorised` via `apply_transition`.
- Act-level SoD extended to the authoriser; `re_evaluate` ceiling made explicit (D10).
- `authorised` added to the prohibited step-0 halt set (D8).
- ATO read endpoint with computed `live_state` (NB4); Sprint-7 export consumer.

### Out of scope (deferred) — see §11.

---

## 3. Data model changes

`[NEW]` = new table · `[ALTER]` = column add · `[PRESENT]` = exists, now consumed.

### 3.1 `Assessment` `[ALTER]` (`assessment.py`)

| Column | Tag | Note |
|---|---|---|
| `status` (`AssessmentStatus`) | [PRESENT] | Now driven. Members `DRAFT`/`IN_REVIEW`/`APPROVED`/`NEEDS_REFRESH` (V2). |
| `approved_by_user_id`, `approved_at` | [PRESENT] | Stamped on approve; `approved_by_user_id` = reviewer-of-record for act-SoD. |
| `lock_version` (`int not null default 0`) | [PRESENT] | Confirmed (V1). Drives `If-Match` on every status transition. |
| `version`, `is_current` | [PRESENT] | Versioning cycle deferred (§11); `version` does **not** bump on re-approval in MVP — hence cycle discrimination uses `submission_round`, not `version` (D11). |
| `submitted_by_user_id` (FK→`app_user`, `RESTRICT`) | [ALTER] | Current submitter — submitter-of-record for act-SoD + queue filter. |
| `submitted_at` | [ALTER] | — |
| `submission_round` (`int not null default 0`) | [ALTER] | **Load-bearing** (D11): increments on each submit; stamped onto the `AssessmentReview` row and the ATO; the cycle key `authorisation_gate` matches against. |

### 3.2 `AssessmentReview` `[NEW]` — tenant-scoped, RLS (`assessment.py`)

| Column | Note |
|---|---|
| `id`, `tenant_id` | RLS; runs on `irontrustai_app` (no new DB role). RLS policy + grants hand-edited in migration (V8). |
| `assessment_id` (FK→`Assessment`, `RESTRICT`) | `RESTRICT` is safe: the D12 pristine guard prevents deleting an assessment that has review rows, so the FK never fires from a legitimate path. |
| `reviewer_user_id` (FK→`app_user`, `RESTRICT`) | Attribution (FK-only; see D13 / §11 for the accepted durability gap). |
| `decision` (`ReviewDecision` `[NEW enum]`: `APPROVED` / `CHANGES_REQUESTED`) | Uppercase labels (V9). |
| `note` (text, nullable) | `CHECK (decision <> 'CHANGES_REQUESTED' OR note IS NOT NULL)` — DB-enforces the mandatory-note rule. |
| `submission_round` (int) | Binds the review to the cycle it judged. |
| `created_at` | — |

### 3.3 `DeploymentAuthorisation` (ATO) `[NEW]` — tenant-scoped, RLS (`lifecycle.py`)

Point-in-time record of record. Append-only in spirit: never mutated/deleted; re-authorisation writes a new row. Multiple rows may exist per use case (one per authorised cycle); the gate keys off the current-cycle match (D11).

| Column | Note |
|---|---|
| `id`, `tenant_id` | RLS (V8). |
| `use_case_id` (FK), `assessment_id` (FK, `RESTRICT`) | Navigation. |
| `submission_round` (int, stamped) | **The cycle key.** = the assessment's `submission_round` at authorise time; `authorisation_gate` requires `ATO.submission_round == Assessment.submission_round` (D11). |
| `tier` (text-stamped) | Snapshot-as-text (CLAUDE §6). |
| `assessment_version` (int, stamped) | Point-in-time record only — *not* the cycle key (versioning deferred; `version` doesn't move on re-approval). Source `Assessment.version` (V6). |
| `authorised_by_user_id` (FK, `RESTRICT`) | — |
| `authorised_by_name`, `authorised_by_email` (text, stamped) | **Durable attribution** (D13) — survives later anonymisation of the user, since the ATO is export-grade. |
| `authorised_at` | — |
| `residual_risk_statement` (text, not null) | Authoriser's residual-risk acceptance. §1.5 strong-default: prefilled draft as a *structured echo* of the AIIA's residual items, confirmed/amended (a generated narrative is deferred AI-assist). |

### 3.4 Enums / audit actions `[ALTER]`
- `ReviewDecision` `[NEW]`, uppercase (V9); `AssessmentStatus` member coverage confirmed (V2).
- New `entity.verb` audit actions: `assessment.submitted`, `assessment.review_recorded`, `assessment.reopened`, `assessment.needs_refresh`, `authorisation.granted`, `lifecycle.authorised`.

---

## 4. Services & control flow

### 4.1 `assessment_review_service` (6a) — tenant-plane, no external call
Simple shape (STATE §4): pre-check → stage business rows + `AuditEvent` → `flush`; `get_tenant_db` commits the request atomically. No mid-request commit (inv 27 N/A). Every status write is a single conditional `UPDATE … WHERE id=:id AND lock_version=:expected AND status=:from` → `412` (stale lock) vs `409` (bad from-state), per inv 14.

- **`submit_for_review`** (`system_owner`): pre-check `structural_assessment_readiness()` AND `treatment_readiness()` (D5) → `409` if either fails; `DRAFT|NEEDS_REFRESH → IN_REVIEW`; **bump `submission_round`**; stamp `submitted_by/at`; audit `assessment.submitted`.
- **`record_review`** (`reviewer`): act-SoD `reviewer ≠ submitted_by_user_id` → `409`; require `IN_REVIEW`. On `APPROVED`: → `APPROVED`, stamp `approved_by/at`, write `AssessmentReview`, audit, **then `advance_use_case()` in the same transaction** (D6). On `CHANGES_REQUESTED`: → `DRAFT`, write `AssessmentReview` (note required by CHECK), audit.
- **`reopen`** (`system_owner`): `APPROVED → NEEDS_REFRESH` (D7); audit `assessment.reopened` + `assessment.needs_refresh`. No `advance` call — regression caught lazily on next recompute (§6.3).

### 4.2 `authorisation_service` (6b)
- **`authorise_use_case`** (`authoriser`): recompute `full_vector()` → reject `409` unless current state is `pending_authorisation` and every gate **below** authorisation passes; act-SoD `authoriser ∉ {approved_by_user_id, submitted_by_user_id}`; write `DeploymentAuthorisation` stamping the current `submission_round`, `tier`, and authoriser `name`/`email` (D11/D13); `apply_transition(pending_authorisation → authorised)` (inv 24); audit `authorisation.granted` + `lifecycle.authorised`. One transaction, no mid-request commit.

### 4.3 Authoring lock (status-aware)
Item/feeder-item writes (`amend_item`, `confirm_item`, control/evidence links) are gated on the parent AIIA's status: **locked** in `{IN_REVIEW, APPROVED}`, **unlocked** in `{DRAFT, NEEDS_REFRESH}`. → A feeder-item write while the parent AIIA is `IN_REVIEW`/`APPROVED` returns `409` (the lock must reach feeder items, which surface into the AIIA).

### 4.4 Act-level SoD predicate (D4 / B2)
A dedicated predicate `assert_distinct_workflow_actor(...)`, separate from `assert_governance_assignable()` and now sanctioned by the amended inv 7. Compares the acting `user_id` against recorded actors: `reviewer ≠ submitted_by`; `authoriser ∉ {approved_by, submitted_by}`. In the steady tenant-wide state these hold automatically (cross-line conflict matrix), so the check is belt-and-suspenders that additionally closes the temporal hole (role revoked/re-granted between acts) and carries into per-object roles. → Same reviewer doing both the classification sign-off **and** the AIIA review on one use case is **allowed** — both are 2nd-line review acts, not a recommend/accept pair.

### 4.5 Pristine-delete guard (D12 / B3)
Extend `_is_pristine` (`assessment_service.py`, V7) so hard-DELETE is blocked unless `status == DRAFT` **and** no `AssessmentReview` and no `DeploymentAuthorisation` row references the assessment — in addition to the existing item/control-link/evidence-link/feeder conditions (inv 17). This holds regardless of whether `propose_risk_set()` happens to yield a dispositionable item (V5).

---

## 5. API surface (tenant plane, `app/routers/v1/`)

| Method · Path | Gate | Notes |
|---|---|---|
| `POST /v1/assessments/{id}/submit` | `system_owner` | `If-Match`; pre-checks structural + treatment readiness; bumps `submission_round`. |
| `POST /v1/assessments/{id}/review` `{decision, note}` | `reviewer` | `If-Match`; act-SoD; note required when `CHANGES_REQUESTED`. |
| `POST /v1/assessments/{id}/reopen` | `system_owner` | `If-Match`; `APPROVED → NEEDS_REFRESH`. |
| `GET /v1/assessments/review-queue` | `reviewer` | `status = IN_REVIEW AND submitted_by != caller`. Actor names resolved via `membership` join (inv 34), never bare `app_user`. |
| `POST /v1/use-cases/{id}/authorise` `{residual_risk_statement}` | `authoriser` | Recompute vector; act-SoD; writes cycle-stamped ATO + transition. |
| `GET /v1/use-cases/{id}/authorisation` | any governance role | Returns the ATO **plus a computed `live_state`** from the current vector (NB4) so "an ATO exists" is not read as "currently authorised". `404` if never authorised. Actor names via `membership` (inv 34). |

---

## 6. Gate model changes

### 6.1 The vector (canonical order)
`vendor → product → classification_readiness → assessment → treatment → authorisation` `[NEW: authorisation]`.

`assessment_gate` `[REFACTOR]` = `structural_assessment_readiness()` **AND** `assessment_approved()` (`status == APPROVED`).
`authorisation_gate` `[NEW]` = `assessment_approved()` **AND** ∃ `DeploymentAuthorisation` with `submission_round == Assessment.submission_round` (D11). Existence-only matching is explicitly **not** sufficient — the cycle key is required.

### 6.2 Auto-satisfiable vs human-act gates (D6 / D10)
Vendor, product, classification-readiness, treatment are auto-satisfiable — the advance loop walks them. The `assessment_approved()` term and the whole `authorisation_gate` are satisfied **only** by an explicit human act. Therefore **both** `advance_use_case()` and `re_evaluate()` cap their auto-advance at `pending_authorisation`; `authorised` is entered only by `authorise_use_case` (inv 35). `re_evaluate` may leave an already-`authorised` use case in place (no-op) or regress it to `held`, but never derives entry into `authorised` from a lower state — even when a cycle-matching ATO exists.

→ **Treatment-pending is a pass-through (NB1).** Because treatment authoring is required *before* submit (D5) and item writes lock at `IN_REVIEW`/`APPROVED`, treatment is recorded during `under_assessment`. After approval the advance loop transits `under_assessment → treatment_pending → pending_authorisation` in a single hop, since `treatment_gate` is already satisfied. `treatment_pending` remains a real park state only for the regression case (a treatment decision later removed). This is a deliberate re-layering of Sprint 5's "treatment happens in `treatment_pending`" model.

### 6.3 Regression (reuse, no new machinery)
A re-open (`APPROVED → NEEDS_REFRESH`) fails `assessment_approved()` → on next consequential read/write, `full_vector`/`re_evaluate` regresses the use case to `held`, even from `authorised` (inv 25). After re-author + re-submit, `submission_round` has incremented, so the prior ATO no longer cycle-matches (D11) → `authorisation_gate` cannot pass off the stale ATO; the use case ceilings at `pending_authorisation` until a fresh `authorise_use_case` writes a new ATO. No scheduler.

### 6.4 Prohibited supremacy (D8)
`authorised` is added to the set of source states the step-0 prohibited check can halt from (inv 26, off snapshot `tier`, never `eu_tier`). Fires today only if a reclassification path can run post-authorisation — none does yet (§11) — so defensive until that work lands.

---

## 7. State machines

### 7.1 Assessment status
```
DRAFT ──submit──▶ IN_REVIEW ──approve──▶ APPROVED ──reopen──▶ NEEDS_REFRESH
  ▲                   │                                            │
  └──changes_requested┘                                            │
  ▲──────────────────────────────submit──────────────────────────┘
```
Bounce on changes → `DRAFT`. Re-submit from `NEEDS_REFRESH` → `IN_REVIEW` (bumps `submission_round`). No `CHANGES_REQUESTED` *status* — that's a `ReviewDecision` on the review row; the assessment returns to `DRAFT` (PRD WKF-3).

### 7.2 Lifecycle (delta)
`… → pending_authorisation ──authorise──▶ authorised`. `deployed`/`retired` remain reserved. `apply_transition` is the sole writer (inv 24).

---

## 8. Invariants

### 8.1 Amendment to an existing STATE invariant (B2)
- **inv 7 (revised):** *Assignment-time* SoD goes through `assert_governance_assignable()` only. *Act-time* workflow SoD — distinctness of actors across submit/review/authorise on a given object — goes through `assert_distinct_workflow_actor()` only. These are the two sanctioned SoD loci; no other inline conflict logic in handlers or services.

### 8.2 New invariants (extend STATE §6)
28. **Act-level SoD is distinct from assignment SoD and lives only in `assert_distinct_workflow_actor()`** (sanctioned by revised inv 7): `reviewer ≠ submitted_by`; `authoriser ∉ {approved_by, submitted_by}`. (D4)
29. **Residual-risk acceptance is the authoriser's act.** Reviewer recommends via AIIA approval; the authoriser authors `residual_risk_statement` and grants the ATO. Never assign residual acceptance to the reviewer. (D3)
30. **Reviewer/authoriser gates are human-act gates, never auto-advanced.** (D6)
31. **AIIA authoring is status-locked.** Item and feeder-item writes rejected (`409`) while the parent AIIA is `IN_REVIEW` or `APPROVED`. (§4.3)
32. **The ATO is a point-in-time fact; deployment authority is the live vector.** The row is never mutated; a regressed/refreshed use case loses `authorised` on recompute. Re-authorisation = new row. Consumers must read `live_state`, not ATO existence. (§6.3, NB4)
33. **`authorised` is not a safe harbour from prohibition.** Reclassification to `PROHIBITED` forces `halted_prohibited` from `authorised`. (D8)
34. **Actor-identity reads join via `membership`, never bare `app_user`** (inv 2 applied to the review queue, review history, and ATO reads).
35. **`authorised` is entered only by `authorise_use_case`.** Both `advance_use_case()` and `re_evaluate()` cap auto-advance at `pending_authorisation`; `re_evaluate` may hold or regress an `authorised` use case but never derive entry into it. (D10, B1)
36. **Pristine-delete is status-and-history-aware.** Hard-DELETE blocked unless `status == DRAFT` and no `AssessmentReview`/`DeploymentAuthorisation` row references the assessment, on top of inv 17's conditions. (D12, B3)
37. **`authorisation_gate` matches by cycle.** It passes only when an ATO's `submission_round` equals the assessment's current `submission_round`; existence alone is insufficient. (D11, B1)

Preserved & relied on: 2, 5, 14, 17 (extended by 36), 24, 25, 26, 27 (N/A — no mid-request commit here).

---

## 9. Edge & failure cases

- Submit a structurally-incomplete or untreated AIIA → `409` (reused readiness predicates).
- Submit an already-`IN_REVIEW`/`APPROVED` assessment → `409` (bad from-state).
- Two reviewers act concurrently → conditional `UPDATE WHERE status=IN_REVIEW`; loser `412`/`409`.
- `reviewer == submitter` / `authoriser ∈ {reviewer, submitter}` → `403`/`409` (inv 28).
- `request_changes` with no note → `422` (+ DB CHECK backstop).
- Edit an `APPROVED`/`IN_REVIEW` AIIA or its feeder items → `409` (inv 31). Only `reopen` unlocks.
- Authorise when not at `pending_authorisation`, or an upstream gate lapsed → recompute vector first, `409`.
- **Reopen → re-approve → no re-authorise** → `submission_round` incremented; stale ATO no longer cycle-matches (inv 37); use case ceilings at `pending_authorisation`; `re_evaluate` cannot restore `authorised` (inv 35). *(B1 — the case this fix exists for.)*
- **Authorised use case regresses to `held` on a transient upstream lapse, then upstream restored** → same submission cycle, ATO still matches, but inv 35 caps `re_evaluate` at `pending_authorisation` → authoriser must re-confirm. *(B1 second case.)*
- **All-blank AIIA with no proposed risks / no required feeders** passes both readiness checks vacuously, gets approved → still **not** pristine-deletable (inv 36). *(B3.)*
- Post-authorisation reclassification to `PROHIBITED` → `halted_prohibited` from `authorised` (inv 33; defensive until a reclassification path exists).
- `GET …/authorisation` after regression → returns the ATO with `live_state = held` (inv 32/NB4).
- ATO requested for a never-authorised use case → `404`.

---

## 10. Sequencing

### Sprint 6a — Review & sign-off
1. §0 verification (V1–V2, V4–V5, V7–V9); `ReviewDecision` enum; `Assessment` column adds (§3.1); `AssessmentReview` table + CHECK + RLS/grants migration (hand-edited, CLAUDE §4).
2. Refactor `assessment_gate` → `structural_assessment_readiness()` + `assessment_approved()` (§6.1); confirm extractions, not re-impls (V4).
3. `assessment_review_service` (§4.1); act-SoD predicate + **inv 7 amendment** (§4.4/§8.1); status-aware authoring lock incl. feeders (§4.3); **status-aware pristine guard** (§4.5).
4. Endpoints (§5, rows 1–4); same-transaction `advance_use_case()` on approve; `membership`-join actor reads (inv 34).
5. Audit actions wired.

**Done-check:** DRAFT→IN_REVIEW→APPROVED moves; approve advances the use case (single-hop through `treatment_pending`) toward `pending_authorisation`; self-review rejected; re-open regresses an advanced use case to `held`; feeder edits locked under review; an all-blank approved AIIA is not pristine-deletable. Live-smoke against the real RLS dev DB (STATE §4).

### Sprint 6b — Deployment authorisation
1. §0 verification (V3 — `re_evaluate` behaviour; V6); `DeploymentAuthorisation` table (incl. `submission_round`, identity stamps) + RLS/grants migration.
2. `authorisation_gate` cycle-matched (§6.1, inv 37); add `authorised` to prohibited step-0 halt set (§6.4); make `re_evaluate` ceiling explicit (inv 35).
3. `authorisation_service` (§4.2); act-SoD extended to authoriser; `pending_authorisation → authorised` via `apply_transition`.
4. Endpoints (§5, rows 5–6) incl. computed `live_state` (NB4); §1.5 residual prefill (structured echo).
5. Audit actions wired.

**Done-check:** a fully-treated, approved use case is authorisable only by a non-reviewer/non-submitter authoriser; produces a cycle-stamped, identity-stamped ATO; reopen→re-approve forces re-authorisation (no stale-ATO restore); a regressed `authorised` use case is not auto-restored by `re_evaluate`; prohibited halts from `authorised`; `GET …/authorisation` surfaces `live_state`. Live-smoke as above.

---

## 11. Deferred

Notifications (WKF-4) · auditor-scoped read-only access (EXP-2) · ATO PDF/export (Sprint 7) · assessment versioning + version-bump on re-approval (AIIA-7) · automatic NEEDS_REFRESH trigger (needs a post-approval reclassification path; only the data models are refresh-ready) · worked-state void path (approved AIIA stays immutable-until-reopen; pristine-delete remains the only removal, now status-gated) · `deployed`/`retired` transitions (PRD §3.2) · per-object governance roles (queue filter + act-SoD predicate written to extend cleanly; `scope_id` seam unbuilt) · AI-*generated* residual narrative · **standalone (non-decision) reviewer comments** (WKF-2 — note-on-decision covers MVP; free-floating comments post-MVP) (NB5) · **durable actor attribution for `AssessmentReview`/`submitted_by`/`approved_by`** — accepted FK-only gap, deferred to the cross-cutting actor-durability fix (STATE §5); the ATO stamps identity now (D13) (NB3).

---

## 12. Open / ratify

- **R1 (NB3 scope):** ratify that durable identity is stamped on the **ATO only**, with the FK-only gap accepted for review/submission/approval columns (D13). If the review thread must also be export-grade, the same text-snapshot extends there.
- **R2 (V3):** the one source-check that determines whether B1 was *live* in shipped code — does Sprint-5 `re_evaluate` already ceiling at `pending_authorisation`? v1.1 closes the door regardless (inv 35).

Resolved since v1: O1 (subsumed by D12), O2 (`submission_round` now load-bearing per D11), O3 (residual prefill = structured echo, ratified by review).

---

## Appendix A — External-review disposition (round 1)

| Finding | Severity | Disposition | Where |
|---|---|---|---|
| B1 — stale-ATO auto-restore into `authorised` | Blocking | **Accepted (both fixes)** — cycle-bound ATO + explicit `re_evaluate` ceiling | D10, D11, inv 35, inv 37, §6.1–6.3 |
| B2 — act-SoD breaches inv 7 | Blocking | **Accepted** — inv 7 scoped to assignment-time; act-time locus named | §8.1, D4 |
| B3 — `_is_pristine` not status-aware | Blocking | **Accepted** — status-and-history-aware guard | D12, inv 36, §4.5 |
| NB1 — treatment-pending pass-through re-layering | Non-blocking | **Accepted** — called out; single-hop transit confirmed | §6.2 |
| NB2 — enum label case | Non-blocking | **Accepted** — into §0 checklist | V2, V9 |
| NB3 — actor durability / anonymisation | Non-blocking | **Accepted w/ modification** — ATO stamps identity; rest deferred (ratify R1) | D13, §11, R1 |
| NB4 — ATO existence ≠ current authority | Non-blocking | **Accepted** — computed `live_state` on the read | §5, inv 32 |
| NB5 — no standalone comment | Non-blocking | **Deferred** — note-on-decision covers MVP | §11 |
| V1–V9 — source verifications | — | **Accepted** — §0 checklist | §0 |
| Clean items (inv 24/26/27/14, D6, D4 dual-review, D2, D3, scope) | — | **Acknowledged** — no change | — |