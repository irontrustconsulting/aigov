# Sprint 6b — Deployment Authorisation & ATO

**Status:** v1 — execution handoff. Plan-mode: propose edits before applying.
**Predecessor:** Sprint 6a (review & sign-off) — must be complete. **Blocks:** Sprint 7 (export/ATO PDF).
**Design:** `docs/AUTHORIZATION.md` — cite §/inv/D/V tags; no rationale restated here.
**Scope:** `DeploymentAuthorisation` (ATO) table, cycle-matched `authorisation_gate`, `authorise_use_case`, `pending_authorisation → authorised` transition, `re_evaluate`/advance ceiling made explicit, prohibited-from-`authorised`, ATO read with `live_state`.
**Out of scope:** design §11 (incl. `deployed`/`retired`, ATO PDF, versioning).

---

## WI-0 — Source verification (gating)
- **V3 (load-bearing):** does Sprint-5 `re_evaluate` in `lifecycle_service.py` already ceiling at `pending_authorisation`, or chase any vector target? Determines whether the stale-ATO hole (design B1/§6.2) was live; WI-3 closes it regardless.
- V6: `DeploymentAuthorisation.assessment_version` source = `Assessment.version` (STATE §5 confirms `version`/`is_current` exist).

**Done when:** `re_evaluate` current behaviour documented from source; `Assessment.version` confirmed as the stamp source.

## WI-1 — Migration: `DeploymentAuthorisation`
Depends: 6a complete, WI-0.
- `lifecycle.py` `DeploymentAuthorisation` `[NEW]` (design §3.3): `id`, `tenant_id`, `use_case_id` (FK), `assessment_id` (FK→`Assessment`, `RESTRICT`), `submission_round` (int), `tier` (text), `assessment_version` (int), `authorised_by_user_id` (FK→`app_user`, `RESTRICT`), `authorised_by_name` (text), `authorised_by_email` (text), `authorised_at`, `residual_risk_statement` (text not null).
- Hand-edit revision (CLAUDE §4): RLS policy reading `app.current_tenant`; `irontrustai_app` DML grants.

**Done when:** `alembic upgrade head` fresh succeeds; `\d deployment_authorisation` shows RLS + app-role grants + `RESTRICT` FKs. **Test area:** migration smoke on real dev DB.

## WI-2 — `authorisation_gate` (cycle-matched) + vector wiring
Depends: WI-1.
- In `lifecycle_gates.py`: `authorisation_gate` = `assessment_approved()` **AND** ∃ `DeploymentAuthorisation` with `submission_round == Assessment.submission_round` (design §6.1, inv 37). Existence-only is **not** sufficient.
- Add `authorisation_gate` to `full_vector()` canonical order after `treatment` (design §6.1).

**Done when:** gate `BLOCK` when no ATO or ATO round ≠ current round; `PASS` only on a matching-cycle ATO with `APPROVED` status; a stale-round ATO yields `BLOCK`. **Test area:** lifecycle gate tests (add round-mismatch case).

## WI-3 — Advance/`re_evaluate` ceiling + prohibited-from-`authorised`
Depends: WI-0/V3, WI-2.
- Make explicit (inv 35): both `advance_use_case()` and `re_evaluate()` cap auto-advance at `pending_authorisation`. `re_evaluate` may hold an already-`authorised` use case (no-op) or regress it to `held`, but never derives entry into `authorised` from a lower state — even with a cycle-matching ATO. `authorised` is entered **only** by `authorise_use_case` (WI-4).
- Add `authorised` to the step-0 prohibited halt source set (design §6.4, inv 33/D8) — bound by-name through the typed column (inv 23/24), via `apply_transition`.

**Done when:** a `held`/`pending_authorisation` use case with a matching ATO is **not** moved into `authorised` by `re_evaluate`; an `authorised` use case regresses to `held` on an upstream lapse; a (defensive) prohibited reclassification halts from `authorised`. **Test area:** lifecycle transition/regression tests + prohibited-supremacy test.

## WI-4 — `authorisation_service.authorise_use_case`
Depends: WI-1, WI-2, WI-3. New file `app/services/authorisation_service.py`. One transaction, no mid-request commit (inv 27 N/A).
- (`authoriser`): recompute `full_vector()` → `409` unless current state is `pending_authorisation` and every gate **below** authorisation passes; `assert_distinct_workflow_actor` (`authoriser ∉ {approved_by, submitted_by}`) → `403`/`409`; insert `DeploymentAuthorisation` stamping `submission_round` (= current), `tier` (snapshot), `assessment_version`, and `authorised_by_name`/`email` (D13); `apply_transition(pending_authorisation → authorised)` (inv 24); audit `authorisation.granted` + `lifecycle.authorised`.

**Done when:** non-eligible authoriser → `403`; wrong state / lapsed upstream gate → `409`; success writes the ATO and transitions; a reopen→re-approve cycle then authorise writes a **new** ATO with the incremented `submission_round` (old ATO untouched). **Test area:** authorisation-service tests + re-authorisation integration.

## WI-5 — Extend pristine-delete with the ATO clause
Depends: WI-1, 6a/WI-6.
- Add to `_is_pristine` (inv 36): also block DELETE when any `DeploymentAuthorisation` row references the assessment.

**Done when:** the assessment of an `authorised` use case → DELETE `409`. **Test area:** pristine-delete tests (add authorised case).

## WI-6 — Endpoints
Depends: WI-4. Routers in `app/routers/v1/`; schemas in `app/schemas/`.
- `POST /v1/use-cases/{id}/authorise` `{residual_risk_statement}` (`authoriser`).
- `GET /v1/use-cases/{id}/authorisation` (any governance role): returns the ATO **plus a computed `live_state`** from the current vector (design §5/NB4, inv 32); `404` if never authorised; actor names via `membership` (inv 34).

**Done when:** authorise endpoint gated + act-SoD enforced; GET returns ATO + `live_state`; after regression `live_state = held` while the ATO row persists; `404` when never authorised. **Test area:** router tests + post-regression read test on real dev DB.

## WI-7 — Audit + docs + live-smoke
Depends: WI-1..6.
- Confirm audit strings: `authorisation.granted`, `lifecycle.authorised`.
- Update STATE.md: §3 capability prose (authorisation/ATO), invariants 29, 32, 33, 35, 37 + the authoriser term of 28; §5 — remove the "authorisation gate (Sprint 6)" deferral, mark `deployed`/`retired` still reserved. Update CLAUDE.md audit-action set.
- Live-smoke the reopen→re-approve→authorise and authorised→held→re-authorise paths against the real RLS dev DB (enum case + `apply_transition` by-name binding + RLS-scoped reads — STATE §4, inv 23/24).

**Done when:** STATE/CLAUDE reflect 6b; both live-smoke paths green on the real schema.

---

### 6b dependency order
WI-0 → WI-1 → WI-2 → WI-3 → WI-4 → {WI-5, WI-6} → WI-7.