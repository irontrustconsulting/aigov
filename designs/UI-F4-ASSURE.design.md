# UI-F4-ASSURE — Design Doc (final)

**Surface:** the assurance / act-SoD surface — reviewer sign-off + AIIA review, authoriser authorise + ATO terminal, system_owner reopen.
**Status:** Track confirmed F4. Topology resolved **B**. All backend acts present at HEAD (verified against `API-ROUTES §2/§4/§5` through `UI-F3-ASSESS`). Frontend wire-up; **zero new routes/tables/enums**; at most a conditional response-shape delta (DF3-7 precedent), elected only if §0 verification forces it. No stable-tier change. Six §0 items open at schema-field level only. This doc supersedes the structured proposal and folds every review finding (Appendix C).

---

## 1. Resolved decisions

| id | decision | basis |
|---|---|---|
| F4-track | Build `UI-F4-ASSURE`, the assurance / act-SoD surface | `DF3-3` reserved exactly these acts for F4; F3 built the assembled-AIIA view for read-only reuse here |
| F4-topology | **B** — portfolio whose-court is the entry index; `use-cases/[id]` is the single role-and-state-conditioned act surface; a thin reviewer view off `GET /assessments/review-queue` is the AIIA index | Reuses the landed `FE-11`/`court.ts`/`WhoseCourtIndicator` + `DF2-7` forward-link seam; avoids the fused-inbox dedup + reviewer-act-type disambiguation cost (A). Reviewer-endorsed. **The one decision still cheap to flip** — it changes only the entry index, not the act surfaces |
| F4-reopen-in | Reopen ships in F4, on the authoring surface (`system_owner` branch, APPROVED AIIA) | `APPROVED` is terminal-for-rework without it; reopen is a 1st-line act and belongs where authoring lives, not the reviewer queue. **Not** `OPEN-1` (void/withdraw stays deferred) |
| F4-ato-render | F4 renders the live ATO record (`GET .../authorisation`, `live_state`) as the post-authorise terminal; export-pack/PDF stays deferred | Completes the authorise act and the "authorised" court terminal; render half of EXP-1/EXP-1a is the dedicated audit-pack sprint |
| F4-actsod-posture | act-SoD presentation is **role-branch-first**; a server-computed eligibility boolean is added **only if** §0 V-1 shows the common case is unmet | Assignment SoD (`INV-7`) already makes reviewer≠submitter and authoriser∉{reviewer,submitter} in the common case, so `FE-8` "no approve on what you authored" is met by the role branch alone. The eligibility signal improves only the **across-reassignment edge** (rare). Client never compares raw individual identities; if a signal is needed it is a server boolean, not shipped submitter user_ids |
| F4-v2-posture | If review history is not on `AssessmentDetail`, expose existing `AssessmentReview` rows (comment + `INV-34` membership-joined identity) as a response-shape addition — **never** a durable name/email stamp | `WKF-2` needs attributed request-changes; live attribution already works via the `INV-34` join. `D-25` is one cross-cutting fix, not piecemeal per-sprint stamping |

---

## 2. The acts (all present at HEAD, gov-gated)

| Act | Route | Gate | If-Match | Transition | Surface placement |
|---|---|---|---|---|---|
| Classification sign-off | `POST .../classification/sign-off` | `gov:reviewer` | no | `PENDING_REVIEW → APPROVED`, stamps `eu_tier` (D-9) | `use-cases/[id]`, reviewer branch, classification `PENDING_REVIEW` |
| AIIA review | `POST /assessments/{id}/review` | `gov:reviewer` | **yes** | `IN_REVIEW → APPROVED\|DRAFT` (bounce); APPROVED same-txn advances | `use-cases/[id]`, reviewer branch, AIIA `IN_REVIEW` |
| Reopen | `POST /assessments/{id}/reopen` | `gov:system_owner` | **yes** | `APPROVED → NEEDS_REFRESH` | `use-cases/[id]`, system_owner branch, AIIA `APPROVED` |
| Authorise | `POST /use-cases/{id}/authorise` | `gov:authoriser` | no | only entry to `authorised`; act-SoD in service | `use-cases/[id]`, authoriser branch, state `pending_authorisation` |
| ATO read | `GET /use-cases/{id}/authorisation` | `gov:ALL` | — | most-recent + computed `live_state` | `use-cases/[id]`, any gov role, state `authorised` |

Reviewer AIIA index: `GET /assessments/review-queue` (`gov:reviewer`, `ReviewQueueEntryRead[]`).

---

## 3. Topology B — entry indexes and the single act surface

Three act-sources, asymmetric by design (`API-ROUTES §4` routes authoriser and sign-off work through `blocking.responsible_party`, only AIIA review has a queue route):

- **Reviewer AIIA review** → index: `review-queue` view ([NEW]). Each row links to `use-cases/[id]`.
- **Authoriser authorise** → index: portfolio whose-court ([PRESENT], `responsible_party == "authoriser"`, `DF2-7` links forward).
- **Reviewer classification sign-off** → index: portfolio whose-court ([PRESENT], `responsible_party == "reviewer"` while snapshot `PENDING_REVIEW`, settled at `D-38`/F2 §0/V-2).

`use-cases/[id]` ([ALTER]) is extended to a role-and-state-conditioned act surface. It disambiguates the reviewer's two acts by **object state**, not court vocabulary (both map to `"reviewer"`): classification `PENDING_REVIEW` → sign-off panel; AIIA `IN_REVIEW` → review panel. The assembled AIIA read ([PRESENT], `assemble_aiia_items`/`INV-16`, F3) is reused read-only beneath both reviewer and authoriser act panels.

### Role branch on `use-cases/[id]` (extends the F3 four-way branch)

| Caller | Sees |
|---|---|
| system_owner | F3 author mode + reopen control when AIIA `APPROVED` ([NEW]) |
| reviewer | assembled-AIIA read + review controls when AIIA `IN_REVIEW`; classification-snapshot read + sign-off control when classification `PENDING_REVIEW` ([NEW]); review-history of any prior bounce |
| authoriser | assembled-AIIA + classification read + authorise control (residual-risk input) when state `pending_authorisation`; ATO terminal when `authorised` ([NEW]) |
| auditor | read-only assembled AIIA (`gov:ALL`) + ATO (`gov:ALL`) only; **never the queue** (`gov:reviewer` → 403); no act controls; never a court row |
| admin | empty-state, no `gov:ALL` call (`DF2-5`) |

---

## 4. Invariants and conventions the surface must honour

1. **INV-28** (act-SoD locus, `assert_distinct_workflow_actor`): reviewer≠`submitted_by`; authoriser∉{`approved_by`,`submitted_by`}. The backend is the enforcement authority; the UI is presentational (`FE-8`). Act-SoD bites only across role reassignment (assignment SoD `INV-7` covers the common case); the across-reassignment edge degrades to act-time 403 surfaced as a blocked reason, unless §0 V-1 elects a server eligibility boolean.
2. **D-4 / D-10 / INV-29** (reviewer recommends via `review(APPROVED)`; authoriser accepts via `authorise`): F4 realises the **act-SoD thread (INV-28, D-10)**, distinct from `WKF-5`'s assignment matrix (`INV-7`). No "act-level half of WKF-5."
3. **INV-30** (human-act gates never auto-advanced): review, sign-off, authorise are explicit human acts; never inferred.
4. **INV-32** (read deployment authority from `live_state`, never row-existence): the ATO terminal is authority-as-of-last-read; refetch after any consequential mutation (`FE-7`). **INV-44** is the S7b export drift invariant — cited only as the **precedent** for carrying a drift caveat on the rendered terminal, not as the live-state rule.
5. **INV-34** (actor identity via `membership` join, never bare `app_user`): review-history attribution and the ATO authoriser identity render from the membership join.
6. **FE-6** (412 `StaleLockBanner` ≠ 409 `BadFromStateBanner`, never collapsed): review and reopen send `If-Match`; authorise and sign-off do not and so have no 412 path (409/403 only).
7. **FE-7** (live-state discipline, `staleTime: 0` on lifecycle/authorisation reads; refetch on mutation).
8. **FE-8** (SoD-visible: structural bar absent, transient block disabled-with-reason; presentational only): structural absence via the role branch; transient (wrong state, stale lock) disabled-with-reason; act-SoD edge per §4.1.
9. **FE-11 / D-38** (whose-court is a direct `blocking.responsible_party` read, fixed party→role map, presentational highlight): reused, **not** re-derived. `court.ts` and `WhoseCourtIndicator` are landed; F4 adds forward-link targets only.
10. **D-24** (authz from server-authoritative context, never token claims): role branch reads `GET /me`.
11. **D-25** (actor-attribution durable stamping is one deferred cross-cutting fix): any V-2 response-shape addition exposes existing `AssessmentReview` rows via the `INV-34` join; **no** durable name/email stamping in F4.

### New local decisions to append (`DF4-n`)

- **DF4-1** Topology B: portfolio whose-court is the entry index; `use-cases/[id]` is the single role-and-state-conditioned act surface; `review-queue` view is the reviewer AIIA index.
- **DF4-2** The reviewer's two acts (classification sign-off, AIIA review) both map to `"reviewer"` court; the act surface disambiguates by object state (classification status vs assessment status), never by court vocabulary.
- **DF4-3** act-SoD presentation is role-branch-first; the across-reassignment edge degrades to act-time 403; a server-computed eligibility boolean is added only if §0 V-1 forces it. The client never compares raw individual identities (`D-25`/`FE-11` spirit preserved).
- **DF4-4** ATO terminal read governed by `INV-32` (`live_state`); drift caveat carried in the spirit of `INV-44` (precedent only).
- **DF4-5** Reopen completes the rework loop (`APPROVED → NEEDS_REFRESH`); `APPROVED` is terminal-for-rework without it. Not `OPEN-1` (void/withdraw remains deferred).
- **DF4-6** (conditional) Backend response-shape deltas (eligibility boolean and/or `AssessmentReview` history on `AssessmentDetail`) are additive (DF3-7 precedent), `D-25`-guarded, and land only if §0 V-1/V-2 force them.

---

## §0 Pre-flight verify checklist (run live before building; D-21)

| id | item | binding? | drives |
|---|---|---|---|
| V-1 | Does `list_review_queue` pre-filter act-SoD eligibility, and what does `ReviewQueueEntryRead` carry (submitter party, `submission_round`, `submitted_at`, any `caller_eligible`)? | binding | review-act FE-8; whether DF4-6 eligibility field is needed |
| V-2 | Does `AssessmentDetail` carry review history / latest `request_changes` comment? | binding | WKF-2 attribution; whether DF4-6 history field is needed |
| V-3 | `AuthoriseRequest` required fields (residual-risk statement) and `DeploymentAuthorisationRead`/`live_state` shape | yes | authorise input + ATO terminal render |
| V-4 | `AssessmentReviewCreate` exact `action` values and per-action comment requiredness | yes | review control form |
| V-5 | Does the assessment gate emit `responsible_party == "reviewer"` for an `IN_REVIEW` AIIA blocked on `assessment_approved` (INV-30)? | non-binding under B | only matters for a fused inbox (A); under B the surfaces are separate, overlap benign; the review-queue view is the canonical reviewer source regardless of the answer |
| V-6 | `SignOffRead` shape; sign-off 409/403 semantics (no If-Match) | yes | sign-off control + error surfacing |

V-5 is re-scoped per review: per-use-case double-court cannot occur (gates sequential, `blocking` is the first non-advance gate, exactly one court at a time), and reviewer-vs-owner classification disambiguation is already settled (`D-38`/F2 §0/V-2). Only the assessment-gate party emission is open, and only A would care.

---

## Appendix A — Open decisions

- **A-1 (founder).** Topology B is resolved on the reviewer's recommendation and my agreement; flip to A or C is cheap pre-execution (entry index only). No other decision is gated on it.
- **A-2 (resolved at §0).** Whether DF4-6 backend deltas land at all is decided by V-1/V-2 outcomes. Default is no delta (role branch + act-time 403 for V-1; deferred history display for V-2). Elect the additive field only if strict FE-8-absence for the reassignment edge (V-1) or attributed request-changes display (V-2) is wanted this sprint.

## Appendix B — Source-verification register

See §0. All six are schema-field-level; `API-ROUTES` deliberately stops at schema names (`ReviewQueueEntryRead`, `AssessmentReviewCreate`, `AuthoriseRequest`, `SignOffRead`, `DeploymentAuthorisationRead`, `AssessmentDetail`). Verify against live schemas/handlers per `D-21`; routes, gates, transitions, and the If-Match set are already pinned at HEAD and need no re-verification.

## Appendix C — Review disposition

| Finding | Disposition |
|---|---|
| Blocking: none | n/a |
| NB-1 OPEN-1 mis-cite | **Accepted.** Reopen relieves the rework dead-end, not the void/withdraw gap. OPEN-1 dropped; replaced with "APPROVED is terminal-for-rework without reopen" (F4-reopen-in, DF4-5). |
| NB-2 WKF-5/INV-28 loose | **Accepted.** Reframed: F4 realises the act-SoD thread (INV-28, D-10), distinct from WKF-5's assignment matrix (INV-7). (§4.2) |
| NB-3 INV-44 export-scoped | **Accepted.** ATO live read governed by INV-32; INV-44 cited only as the drift-caveat precedent. (§4.4, DF4-4) |
| NB-4 auditor cannot read queue | **Accepted.** Auditor surface tightened to assembled AIIA (`gov:ALL`) + ATO (`gov:ALL`) only; never the `gov:reviewer` queue; no court row. (§3 role table) |
| NB-5 Q3 D-25 guard | **Accepted and bound.** Any V-2 change exposes existing `AssessmentReview` rows via the INV-34 join, never durable name/email stamping. (F4-v2-posture, DF4-6, §4.11) |
| NSV V-1..V-4,V-6 legitimate | **Accepted.** Carried in §0 / Appendix B unchanged. |
| NSV V-5 mis-framed | **Accepted.** Re-scoped to the single assessment-gate party-emission check; non-binding under B. (§0) |
| Q2 → B | **Adopted**, marked founder-flippable (A-1). |
| Q3 thin change | **Refined.** Tightened below the review's recommendation: role branch meets FE-8 in the common case; eligibility boolean is elected only if V-1 forces it; never client identity comparison. (F4-actsod-posture, DF4-3) |