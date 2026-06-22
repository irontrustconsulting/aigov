# SPRINT HANDOFF — UI-F3-ASSESS (execution-only)

**Status:** READY pending §0 · route `apps/tenant/app/use-cases/[id]` (new) · backend/schema/route delta none · first surface to send `If-Match` live.

Rationale lives in `UI-F3-ASSESS.design.md`. Code wins over canonicals (`D-21`): a binding §0 contradiction is **halt-and-report**, not silent adaptation.

## §0 (WI-0, run first)

Resolve V-1a, V-1b, V-2, V-3, V-8 (binding) and V-4–V-7; record outcomes. Escalate if: create requires sign-off (B1 → A1/A4 invert) or a required feeder gates (S1 → A7 reopens for that tier).

| ID | Bind | Verify against | Resolves |
|---|---|---|---|
| V-1a | ✔ | bridge snapshot writer (`POST /use-cases`) | bridge snapshot status `APPROVED` vs `PENDING_REVIEW` |
| V-1b | ✔ | `assessment_service.py::create_aiia` | create guard: `snapshot.tier` only, or sign-off/`APPROVED` required |
| V-2 | ✔ | `app/schemas/assessments*.py`, `assemble_aiia_items` | `AssessmentDetail`/item shape; `lock_version` exposure; `surfaces_into`; section template; header identity on `UseCaseWithClassification`; court only from `/lifecycle` |
| V-3 | ✔ | `assessments.py` §5 | five `If-Match` routes carry/return `lock_version` |
| V-8 | ✔ | `lifecycle_gates.py`, `FeederRecommendationRead.required` | feeders non-gating to `APPROVED`/advance |
| V-4 | | `dashboard`, `systems/[id]`, `lib/portfolio/court.ts` | F2 forward-link reality; patch F2 target if absent |
| V-5 | | provenance enum | 4-value, no `USER_PROVIDED`; render-only |
| V-6 | | `FeederRecommendationRead` | shape for read-only surfacing |
| V-7 | | routers | gates exactly as `API-ROUTES` maps |

*Done-check WI-0:* verification note committed; binding items resolved; escalations raised before dependent WIs.

## Work items

**WI-1 · Shell + four-way role branch + header.**
`page.tsx`. `GET /v1/me` first. Branch: admin → admin/empty state, no `gov:ALL` read (`DF2-5`); reviewer/authoriser/auditor → assembled AIIA read-only (no author controls); contributor → item-author mode, bootstrap/submit/re-evaluate **absent** (`FE-8`); system_owner → full. Header identity from `GET /use-cases/{id}`; whose-court from `GET /use-cases/{id}/lifecycle` only (S3), `WhoseCourtIndicator` reused (party/role, never individual). `re-evaluate` lever `system_owner`-only. Patch F2 deep-link if V-4 found none.
*Done-check:* admin issues no `gov:ALL` call; contributor sees no bootstrap/submit/re-evaluate control; reviewer sees read-only view with no author or assure control; court renders party label.

**WI-2 · Bootstrap + assembled read.**
No current AIIA: `system_owner` sees create (`POST /use-cases/{id}/assessments`); contributor sees "a system owner must start the assessment" empty-state. 409 reasons (incl. `PENDING_REVIEW` per V-1) render as blocked states, no create control. Present: `GET .../sections` + `GET /assessments/{aid}`; feeder-surfaced items and any evidence-link refs read-only (no bytes/inline, `INV-22`); feeder-recommendations read-only (A7, shape per V-6). Render all four statuses per design §4 (`NEEDS_REFRESH` author-open).
*Done-check:* native + feeder-surfaced items render non-editable where required; contributor-with-no-AIIA sees empty-state not a create control; `NEEDS_REFRESH` presents author-open and submittable.

**WI-3 · Disposition + authoring ladder.**
Confirm/amend per `FE-5`; `AI_SUGGESTED` blocks authoring-field writes client-side (CATALOGUE_CURATED exempt), server 409 surfaced; provenance render-only, no client `provenance`. `FE-4` inputs; risk/control pickers from `GET /reference/risks|controls`. PATCH-item + confirm send `If-Match`; 412 → reload path, 409 → action void, distinct (`FE-6`); `staleTime:0` + invalidate-after-mutation.
*Done-check:* AI_SUGGESTED item rejects authoring write client-side, server 409 distinct from 412; stale-lock PATCH drives reload, never silent retry; network test asserts `If-Match` IS sent (inverts `DF1-5`); no body carries `provenance`.

**WI-4 · Item create / delete.**
`POST .../items`, `DELETE .../items/{iid}` (`gov:write`, no `If-Match`). Delete governed by authoring-lock (`INV-31`), absent on `IN_REVIEW`/`APPROVED`; no whole-assessment void affordance (`OPEN-1`).
*Done-check:* create/delete work in `DRAFT`/`NEEDS_REFRESH`; delete absent when locked; no void control.

**WI-5 · Control links.**
`POST/DELETE .../items/{iid}/control-links` (`gov:write`), free on any item incl. `AI_SUGGESTED` (asymmetry vs deferred evidence, `INV-20`). Multi-homed control surfaces both framework homes (`CTL-2`).
*Done-check:* link create/delete; permitted on AI_SUGGESTED item; both homes shown.

**WI-6 · Submit + lock.**
`POST .../submit` (`gov:system_owner`, `If-Match`); control absent for contributor (`FE-8`). On success `IN_REVIEW`: body read-only, writes disabled-with-reason (`INV-31`), court → reviewer. 412/409 distinct. Escalate per V-8 before shipping submit for feeder-gated tiers.
*Done-check:* submit sends `If-Match`, absent for contributor; post-submit body locked; court reads reviewer; 412≠409.

**WI-7 · Canonical update (mandatory).**
`STATE.md`: add `UI-F3-ASSESS` block (route, consumed routes, four-way role branch, FE-6-live, four-status render); move to deferred — evidence-linking/repository (A2), coverage panel (A3), feeder create+author (A7, note V-8 contingency), classification sign-off/review/authorise/queue/reopen (F4). Note F2 forward-link void closed. `DATA-MODEL.md`: no schema delta (state explicitly). `API-ROUTES.md`: no route delta, consumed-only (state explicitly). Append `DECISIONS.md` `DF3-n`: A2/A3/A5/A6 locked, A4 (contingent V-1), A7 (provisional, V-8), the gate-seam render correction, `NEEDS_REFRESH` handling, reopen-deferred, FE-6-live inversion of `DF1-5`. Append `INVARIANTS.md` only if execution established a genuinely new convention beyond `FE-6`/`FE-8`/`FE-11`/`INV-13/16/31`; else none. Never renumber a live `INV-n`; leave the stable tier untouched.