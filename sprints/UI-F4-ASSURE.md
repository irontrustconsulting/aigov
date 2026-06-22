# UI-F4-ASSURE — Sprint Handoff (execution-only)

Rationale lives in `UI-F4-ASSURE-design.md`. This file is execution-only. Cite IDs, not section numbers.

**Envelope:** frontend wire-up. Zero new routes/tables/enums. At most a conditional additive response-shape delta (WI-9), elected only if §0 forces it. No stable-tier change. Topology B.

---

## §0 — Pre-flight (run live before any WI; D-21). Block on binding items.

- [ ] **V-1 (binding):** read `app/services/assessment_review_service.py::list_review_queue` and `app/schemas` `ReviewQueueEntryRead`. Record: does it act-SoD pre-filter; does it carry submitter party, `submission_round`, `submitted_at`, any `caller_eligible`. → gates WI-2, WI-9.
- [ ] **V-2 (binding):** read `AssessmentDetail` schema + `assemble`/detail handler. Record whether `AssessmentReview` rows (comment + actor) are present on the detail response. → gates WI-7, WI-9.
- [ ] **V-3:** record `AuthoriseRequest` required fields and `DeploymentAuthorisationRead` + `live_state` fields.
- [ ] **V-4:** record `AssessmentReviewCreate` `action` enum values and per-action comment requiredness.
- [ ] **V-6:** record `SignOffRead` fields; confirm sign-off takes no `If-Match`; record 409/403 semantics.
- [ ] **V-5 (non-binding under B):** record whether the assessment gate emits `responsible_party == "reviewer"` for an `IN_REVIEW` AIIA. Note only; no build branch under B.
- [ ] Confirm at HEAD: `GET /assessments/review-queue` `gov:reviewer`; `POST /assessments/{id}/review` + `/reopen` take `If-Match`; `POST /use-cases/{id}/authorise` + `.../classification/sign-off` do not.

If V-1 shows no eligibility signal **and** strict FE-8 for the reassignment edge is wanted → WI-9a. Else default: act-time 403. If V-2 shows no review history **and** attributed request-changes display is wanted → WI-9b. Else default: defer history display.

---

## Work items (dependency-ordered)

### WI-1 · Reviewer review-queue index view  [NEW]
Build `apps/tenant/app/review-queue` (or equivalent index route). Fetch `GET /assessments/review-queue` (`gov:reviewer`). Render `ReviewQueueEntryRead[]` as queue rows (reuse `packages/ui` queue-row primitive); each links to `use-cases/[id]`. Gate the route on a reviewer role from `GET /me`; non-reviewer (incl. auditor) never issues the call.
**Done:** reviewer sees IN_REVIEW rows linking forward; auditor/non-reviewer render gets no queue call (asserted by test — no `review-queue` request fired); admin → empty-state.

### WI-2 · AIIA review panel on `use-cases/[id]`  [ALTER]
Reviewer branch, AIIA `IN_REVIEW`: render the assembled-AIIA read (reuse F3 `assemble_aiia_items` view, read-only) + review controls. Control form per V-4 (`approve` | `request_changes` + comment). Submit `POST /assessments/{id}/review` with `If-Match: lock_version`. Map 412 → `StaleLockBanner` (invalidate + reload); 409 → `BadFromStateBanner` (action void); 403 act-SoD → blocked-reason. Refetch lifecycle + assessment after success (`FE-7`, `staleTime: 0`).
**Done:** network test asserts `If-Match` sent; 412≠409 surfaces distinct (`FE-6`); approve drives same-txn advance visible on refetch; request_changes bounces to DRAFT.

### WI-3 · Classification sign-off panel on `use-cases/[id]`  [NEW]
Reviewer branch, classification `PENDING_REVIEW`: render the classification-snapshot read (tier, basis, context answers) + sign-off control. Submit `POST .../classification/sign-off` (no `If-Match`) per V-6. On success `eu_tier` is stamped → refetch lifecycle (`FE-7`). 409/403 → blocked-reason (no 412 path).
**Done:** sign-off flips snapshot `PENDING_REVIEW → APPROVED`, `eu_tier` visible on refetched lifecycle; no `If-Match` sent (asserted); disambiguation correct — sign-off panel shows for `PENDING_REVIEW`, review panel for `IN_REVIEW`, never both (`DF4-2`).

### WI-4 · Authorise panel + residual-risk input on `use-cases/[id]`  [NEW]
Authoriser branch, state `pending_authorisation`: render assembled-AIIA + classification read + `AuthoriseRequest` input (residual-risk per V-3). Submit `POST /use-cases/{id}/authorise` (no `If-Match`). 409 → `BadFromStateBanner`; 403 act-SoD → blocked-reason. Refetch lifecycle + authorisation after success.
**Done:** authorise transitions to `authorised` (visible on refetch); ATO terminal (WI-5) renders post-success; no `If-Match` sent (asserted).

### WI-5 · ATO terminal render on `use-cases/[id]`  [NEW]
Any gov role, state `authorised`: fetch `GET /use-cases/{id}/authorisation`; render most-recent ATO with authoriser identity (INV-34 join), tier/residual text-stamps, and `live_state` (`INV-32`) — never infer "authorised" from row existence. Carry a drift caveat when `live_state` diverges from the snapshot basis (spirit of `INV-44`, `DF4-4`). 404 (never authorised) → no terminal.
**Done:** terminal reads `live_state`; a forced drift renders the caveat; 404 path renders nothing (test).

### WI-6 · Reopen control on `use-cases/[id]`  [NEW]
system_owner branch, AIIA `APPROVED`: render reopen control. Submit `POST /assessments/{id}/reopen` with `If-Match`. 412/409 distinct (`FE-6`). On success `APPROVED → NEEDS_REFRESH`; the F3 author surface re-opens (`DF3-4`).
**Done:** reopen flips to `NEEDS_REFRESH`, authoring fields unlock on refetch; `If-Match` sent; 412≠409 (asserted).

### WI-7 · Review-history display on `use-cases/[id]`  [NEW]
Render prior review decisions + the latest `request_changes` comment with actor (INV-34 join), visible to system_owner (and reviewer/authoriser as context). Source: `AssessmentReview` rows from `AssessmentDetail` if V-2 confirms them present; else gated on WI-9b. Never stamp durable name/email (`D-25`).
**Done:** a bounced system_owner sees the request-changes comment + attributed actor; identity is read from the membership join, not a stamped field (asserted).

### WI-8 · act-SoD + role-branch presentation (`FE-8`)  [ALTER]
Structural absence via the role branch (a caller not in a branch never sees its controls). Transient blocks (wrong state, stale lock) disabled-with-reason. Across-reassignment act-SoD edge: default to act-time 403 surfaced as blocked-reason. Auditor: read-only assembled AIIA + ATO only, no queue, no act controls, no court row. Reuse `court.ts`/`WhoseCourtIndicator` for forward-links; do **not** re-derive whose-court (`FE-11`).
**Done:** each role branch renders only its controls (test matrix: system_owner/reviewer/authoriser/auditor/admin); auditor issues no `gov:reviewer` call; forward-links resolve to the correct act panel.

### WI-9 · Conditional backend response-shape delta (elect per §0)  [ALTER, conditional]
Land only if §0 forces it. Additive only (DF3-7 precedent); no route/table/enum change.
- **WI-9a (if V-1 + strict-FE-8 elected):** add server-computed `caller_eligible: bool` to `ReviewQueueEntryRead` (and/or the authorise eligibility hint on the lifecycle/rollup read). Do **not** ship raw submitter identity to the client. Update `API-ROUTES` schema note.
- **WI-9b (if V-2 + attributed-display elected):** expose existing `AssessmentReview` rows (comment + membership-joined identity, INV-34) on `AssessmentDetail`. No durable stamping (`D-25`). Update `API-ROUTES` schema note.
**Done:** if elected, response carries the additive field; no migration; existing callers unbroken. If not elected, this WI is a no-op recorded as such.

### WI-10 · Canonical update (always last)
- Update `STATE.md`: add the `UI-F4-ASSURE` capability block (surface, route, role branch, consumed routes, topology B, FE-6 callers); move the F4-deferred rows (review-queue UI, classification sign-off, authorise, reopen) from deferred to implemented.
- Update `API-ROUTES.md §6`: add the F4 consumption note; record any WI-9 response-shape delta against the affected schema row.
- Update `DATA-MODEL.md`: no change expected (no schema delta). State "no change" explicitly if true.
- Append to `DECISIONS.md`: `DF4-1..DF4-6` (see design doc §4). Record A-1/A-2 dispositions if resolved at execution.
- Append to `INVARIANTS.md`: none expected (WI-9 deltas are additive fields, not new constraints). Add an `INV-n` only if execution introduces a genuinely new server-enforced constraint; if so, append at the next free id, never renumber a live `INV-n`.
- Leave the stable tier (`DOMAIN`, `REQUIREMENTS`, `ARCHITECTURE`, `UX`, `PLATFORM-UX`, `PATTERNS`, `FRONTEND`, `INDEX`) untouched. If a new FE convention seems warranted by act-SoD presentation, **flag it for the founder** — do not self-promote an `FE-n` (`FE-8` already covers SoD-visible).
**Done:** volatile-tier docs reflect HEAD; no stable-tier diff; no renumbered ids.