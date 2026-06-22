# DESIGN DOC — UI-F3-ASSESS

**Status:** DESIGN · v2 · review-cleared · **surface** use-case work surface / AIIA authoring mode · **route** `apps/tenant/app/use-cases/[id]` (new) · **face** both, role-conditioned · **backend delta** none (consumed-only) · **schema/route delta** none · **concurrency** first surface to send `If-Match` live (`FE-6`/`PAT-6`) · **closes** F2's per-use-case forward-link void.

## Resolved decisions

| # | Decision | Disposition | Why |
|---|---|---|---|
| A1 | Scope boundary | Author-to-submit *(user)*. Sequencing **contingent on V-1** (B1). | View built once, reused read-only in F4; act-SoD stays one F4 unit. If V-1 shows AIIA create requires sign-off, A4's sign-off precedes a usable F3 on the affected paths. |
| A2 | Evidence-linking | Deferred with the evidence-repository surface | Linking needs evidence to exist; no surface yet. Existing refs read-only, manifest-style, no bytes (`INV-22`). |
| A3 | Coverage panel | Deferred | Headline counts dispositioned items on an `APPROVED` governing AIIA (`INV-38`); `DRAFT` reads near-empty and misleads. |
| A4 | Classification sign-off | F4 (`DF1-3`); ordering contingent on V-1 (B1) | Reviewer act; lives with the queue. |
| A5 | `re-evaluate` lever | In F3, `system_owner`-only | Owner manual lever; STATE names this surface as its home. |
| A6 | Route | `use-cases/[id]` flat | Use-case id is tenant-unique. |
| A7 | Feeders | **PROVISIONAL: defer** (create + author); recommendations read-only. **Not locked pending V-8** (S1). | Create-without-author is a half-surface (`DF1-3`). If V-8 shows a required feeder gates assessment-approval/advance for a tier, defer is a scope hole for that tier (high-risk, DOMAIN §3 centre of gravity) and feeder authoring re-enters F3 for it. |

## 1. Surface intent

The use-case work surface. One use case, its current AIIA assembled at read time (`assemble_aiia_items`, `INV-16`), rendered as the tier-scoped section template with native and feeder-surfaced items, each carrying server-derived provenance, shown reasoning, and disposition. The owner dispositions AI-proposed items, authors response and treatment, links controls, and submits for review. `UX-6` made concrete; the destination F1/F2 point at and never reach.

## 2. Scope and the F3/F4 seam

Two actor modes; the split is on that seam:

| Mode | Acts | Sprint |
|---|---|---|
| Author | item author + control-link + bootstrap + submit | F3 |
| Assure | classification sign-off, review, authorise, queue | F4 |

The assembled-AIIA render is built once in F3 and reused read-only in F4. **Act-SoD (`INV-28`: reviewer ≠ submitter, authoriser ∉ {approver, submitter}) is the reason the assure acts stay one F4 unit** — and that is the only thing `INV-28` governs here. It does not govern the owner-vs-contributor split inside author mode; that is a role-capability gate (B2, §3).

Dependency: the queue links into this view and the review act reads the assembled AIIA, so the view is the floor and the queue is F4 chrome on top.

## 3. Architecture

Route `apps/tenant/app/use-cases/[id]`. Resolved-first `GET /v1/me` role branch (`DF2-5`), then lifecycle and AIIA. Every consumed route PRESENT; ALTER column empty by design.

**Author-mode capability matrix — corrected to the gate seam (B2).** Author mode splits internally on `gov:write` vs `gov:system_owner`. Per `FE-8`, a `system_owner`-gated control is **structurally absent** for a bare contributor, not disabled.

| Act | Route | Gate | system_owner | contributor |
|---|---|---|---|---|
| Bootstrap AIIA | `POST /use-cases/{id}/assessments` | `gov:system_owner` | ✓ | **absent** |
| Author item (create/amend/confirm/delete) | `.../items[...]`, `.../items/{iid}/confirm` | `gov:write` | ✓ | ✓ |
| Control-link | `.../items/{iid}/control-links` | `gov:write` | ✓ | ✓ |
| `re-evaluate` | `POST .../lifecycle/re-evaluate` | `gov:system_owner` | ✓ | **absent** |
| Submit | `POST .../submit` | `gov:system_owner` | ✓ | **absent** |

Role branch (four-way):
- **system_owner** — full author mode.
- **contributor** — item-author + control-link only; bootstrap, submit, re-evaluate absent (`FE-8`). On a use case with no AIIA, an empty-state "a system owner must start the assessment" (parallels F1's capture empty-state), never a dead create control.
- **reviewer / authoriser / auditor** — assembled AIIA rendered read-only; no author controls, no assure controls (F4). This is the view F4 reuses.
- **admin** (zero governance) — admin/empty state; no `gov:ALL` read issued (`DF2-5`).

Reads/writes by region:

| Region | Reads | Writes | If-Match |
|---|---|---|---|
| Header / whose-court | `GET /use-cases/{id}` (identity), `GET /use-cases/{id}/lifecycle` (court) | `re-evaluate` (owner) | — |
| Section template | `GET /assessments/{aid}/sections` | — | — |
| AIIA body | `GET /assessments/{aid}` | `POST/PATCH/DELETE .../items[...]`, confirm | PATCH + confirm: **yes** |
| Authoring fields | `GET /reference/risks\|controls` | (via amend) | — |
| Control links | (in item) | `POST/DELETE .../items/{iid}/control-links` | — |
| Feeder recs (read-only, A7) | `GET .../feeder-recommendations` | — | — |
| Submit | — | `POST .../submit` (owner) | **yes** |

Bootstrap 409 set (`PROHIBITED`/`REQUIRES_CONTEXT`/no-snapshot/already-exists, plus context-path `PENDING_REVIEW` per V-1) renders the reason, not a create control.

## 4. Status handling (N2)

`AssessmentStatus` is four-valued. The surface renders all four:

| Status | Authoring | Submit | Source |
|---|---|---|---|
| `DRAFT` | open | available (owner) | bootstrap |
| `NEEDS_REFRESH` | **open** (authoring-unlocked, `INV-31`) | available (owner) | reopen (post-F4) or backend |
| `IN_REVIEW` | locked, disabled-with-reason (`FE-8` transient, `INV-31`) | — | post-submit |
| `APPROVED` | locked | — | post-review (F4) |

`NEEDS_REFRESH` is explicitly handled: a reopened or backend-set AIIA presents author-open and resubmittable. The `reopen` act itself (`APPROVED → NEEDS_REFRESH`, `gov:system_owner`) is **deferred**: `APPROVED` is unreachable until F4 review ships, so reopen has nothing to act on in an F3-only world; it lands with F4.

## 5. Invariants the design honors

| # | Invariant | How honored |
|---|---|---|
| 1 | `INV-13`, `FE-5`, `PAT-8` | Provenance render-only; `AI_SUGGESTED` item blocks authoring-field writes (CATALOGUE_CURATED exempt per `PAT-8`); client never sends `provenance`. |
| 2 | `INV-14`, `FE-6` | PATCH-item, confirm, submit send `If-Match`; 412 → invalidate/refetch/re-present/retry; 409 → action void; never collapsed. Other writes never send it. |
| 3 | `INV-20`, `D-20` | Control-link free on any item; evidence-link disposition-gated (deferred, A2). |
| 4 | `INV-16`, `D-18`, `PAT-7` | Feeder-surfaced items render as read-only references; no write-back. |
| 5 | `INV-31` | Authoring-lock by status (§4): `IN_REVIEW`/`APPROVED` locked, disabled-with-reason; `DRAFT`/`NEEDS_REFRESH` open. **Item-delete (`DELETE .../items/{iid}`, `gov:write`) is governed here, not by the pristine predicate (N1).** |
| 6 | `INV-25`, `INV-32`, `FE-7` | Lifecycle/gate vector `staleTime: 0`; invalidate-and-refetch after every mutation. |
| 7a | `FE-8`, `UX-5`, `D-4`, `D-24`, DOMAIN §7 | Role-capability gate (B2): `system_owner`-gated controls absent for contributor; role from server-authoritative `GET /v1/me`, never claims. |
| 7b | `INV-28` | Act-SoD: review/authorise acts absent in F3, reserved as one F4 unit. |
| 8 | `FE-11`, `D-25` | Whose-court names party/role, never individual. |

Note (N1): `INV-17`/`INV-36` (`_is_pristine`, whole-assessment hard-delete) are **not** in F3 scope; `DELETE /assessments/{id}` is not consumed. No whole-assessment void affordance is rendered (`OPEN-1`).

## §0 — Pre-flight verify checklist

Resolves against live code/DDL per `D-21`. Binding items block the design.

| ID | Bind | Verify against | Resolves |
|---|---|---|---|
| V-1a | ✔ | bridge snapshot writer (`POST /use-cases`) | Does a bridge-resolved snapshot carry `APPROVED` or `PENDING_REVIEW`? (S2) |
| V-1b | ✔ | `assessment_service.py::create_aiia` | Is the create guard purely `snapshot.tier`, or does it additionally require sign-off/`APPROVED`? (S2) Together V-1a+V-1b settle B1: if create requires sign-off, A1/A4 sequencing inverts and F3 cannot bootstrap on the affected path before F4. The `PENDING_REVIEW` exposure is identical on bridge and context paths until V-1a/b resolve; no path is assumed "unaffected." |
| V-2 | ✔ | `app/schemas/assessments*.py`, `assemble_aiia_items` | `AssessmentDetail` + assembled-item shape: disposition/provenance fields, `lock_version` exposure (body vs ETag), feeder-surfaced marking (`surfaces_into`), section template (required/recommended/N-A). **Includes (S3):** header identity fields present on `UseCaseWithClassification`; whose-court sourced only from `/lifecycle`. |
| V-3 | ✔ | `assessments.py` §5 | Five `If-Match` routes carry and return `lock_version`; header mechanism (`PAT-6`). |
| V-8 | ✔ | `lifecycle_gates.py` assessment gate, `FeederRecommendationRead.required` semantics | Are recommended/required feeders **non-gating** to AIIA `APPROVED`/advance? **Scope-gating, not an execution branch (S1):** a required gating feeder makes A7's defer a scope hole for that tier; resolve before A7 locks. |
| V-4 | | `dashboard`, `systems/[id]`, `lib/portfolio/court.ts` | F2 forward-link reality (`DF2-7` vs STATE); does F3 also patch F2's target? |
| V-5 | | provenance enum | 4-value, no `USER_PROVIDED`; render-only. |
| V-6 | | `FeederRecommendationRead` | Shape for read-only surfacing. |
| V-7 | | routers | Gates exactly as `API-ROUTES` maps; drives the §3 matrix and `FE-8`. |

## Appendix A — Open decisions / contingencies

No free decisions. Contingencies: **V-1a+V-1b** gate A1/A4 sequencing (B1); **V-8** gates the A7 lock (S1). Both resolve at §0; if either inverts its assumption, escalate before the dependent work item.

## Appendix B — Source-verification register

V-1a, V-1b, V-2, V-3, V-4, V-5, V-6, V-7, V-8 above.

## Appendix C — Review disposition

| Finding | Disposition |
|---|---|
| B1 | Accepted. "Common case unaffected" parenthetical removed; V-1 split (V-1a/b) and made binding; A1/A4 sequencing marked contingent. |
| B2 | Accepted. §3 matrix rebuilt on the `gov:write` vs `gov:system_owner` seam; contributor render specified absent per `FE-8`; citation corrected to `FE-8`/`UX-5`/`D-4`/`D-24`; `INV-28` retained only for the F3/F4 act-SoD seam (§2, inv 7b). |
| N1 | Accepted. Item-delete recited to `INV-31` (inv 5); `INV-17`/`INV-36` noted out-of-scope; `OPEN-1` no-void note kept. |
| N2 | Accepted. `NEEDS_REFRESH` render specified (§4, author-open, submittable); `reopen` stated deferred with reason. |
| S1 | Accepted. V-8 re-weighted as scope-gating; A7 unlocked (PROVISIONAL) pending V-8. |
| S2 | Accepted. V-1 split into V-1a (bridge snapshot status) and V-1b (create guard). |
| S3 | Accepted. Folded into V-2 (header identity fields; court only from `/lifecycle`). |
| Clean | Acknowledged; carried unchanged. |