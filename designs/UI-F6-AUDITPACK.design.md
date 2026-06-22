# UI-F6-AUDITPACK — Design Doc (final)

**Surface:** tenant assurance capstone — control-coverage view + export / audit pack + ATO document. Realises the `UX.md §5` "Evidence / audit-pack" surface and closes EXP-1's render half (frontend). Last tenant surface; completes the tenant plane.
**Plane:** tenant. **Faces:** both, role-conditioned; auditor is the primary persona.
**Status:** DESIGN — final (review findings B1, B2, N1–N4, NB1–NB5 disposed; founder dispositions A1–A7 confirmed). Ready for handoff.
**Backend delta target:** **zero** — every coverage/export route is built and `gov:ALL`. Verify at §0 (V-1/V-2); do not assert.
**Mutations:** **no domain-state mutation; one audit-writing read** (`export.generated`, INV-42) on deliberate generation, plus `evidence.access` (INV-22) per manifest download. No `If-Match`, no act-SoD control, no whose-court row.
**Repo-lag caveat (D-21):** canonicals current through `UI-F5-EVIDENCE`. If a coverage/export surface landed since, re-scope. V-1 covers it.

---

## 1. Resolved decisions

| ID | Decision | Rationale | Refs |
|---|---|---|---|
| DF6-1 | **Topology: dedicated `apps/tenant/app/audit` programme home + per-entity panels.** `/audit` carries the tenant-wide coverage matrix, the framework export, and a pack index. `systems/[id]` (ALTER) gains a system-coverage panel + system-export action. `use-cases/[id]` (ALTER) gains a use-case-coverage panel (APPROVED-gated) + use-case-export action + ATO-document action. | `UX.md §5` names audit-pack as its own surface; the auditor wants one coherent programme home while per-entity artifacts stay where the entity lives. | A1 |
| DF6-2 | **Export/ATO-document generation is a deliberate, user-initiated fetch; coverage eager-loads.** Export routes stage `export.generated` (INV-42, PAT-10/D-35); coverage emits no audit (INV-25). | An audited disclosure must not fire on mount/focus; a pure read may. | A5, V-3, V-8 |
| DF6-3 | **Interactive coverage is not audit-grade.** `GET /coverage` family verdicts (internal `require_evidence_for_satisfied=false`) are labelled interactive posture; the audit verdict is the export-embedded coverage (`true`), which downgrades unsubstantiated `SATISFIED → PARTIAL` and carries `downgraded_unsubstantiated`. The two may differ for one control and are visually distinguished. The interactive route exposes no flag to pass `true` (N1), so the line is structurally non-bypassable. | D-29 honesty distinction; an audit deliverable must not misstate. | DF6-3→INV-51, V-4, N1 |
| DF6-4 | **Coverage matrix is not an obligation set.** The UI renders the `not_an_obligation_set` caveat prominently and presents `unaddressed_controls` as gaps-shown-not-failures. No "% compliant" headline treats unaddressed as fail until applicability (OPEN-3) lands. | D-28: a whole-library denominator falsely fails a minimal-risk use case; the flagged list shows gaps without asserting obligation. | DF6-4→INV-52, N2 |
| DF6-5 | **ATO document carries the drift caveat.** `basis_is_current_state_not_authorisation_snapshot` is always true; the UI states the ATO row is the authoritative authorisation while the referenced assessment/classification are read live and may have drifted. Mirrors F4 (DF4-4). | INV-44 / D-34. | V-6 |
| DF6-6 | **PDF render deferred; interim is an in-DOM audit-pack view + browser print.** F6 renders the structured export as a readable, dense, sectioned view; take-away is print. Templated PDF (EXP-3) and persisted/async export stay deferred. | EXP-1 render-half is frontend/later; print covers MVP take-away without a render pipeline. | A3 |
| DF6-7 | **EXP-2 auditor-scoping stays deferred.** F6 surfaces auditor read on the existing any-governance-role gate; no thin auditor membership scoping this sprint. | EXP-2 post-MVP (STATE deferred); the gate already admits auditor. | A2 |
| DF6-8 | **Coverage defaults to APPROVED-only; `include_unapproved` is a labelled "in-progress, not audit-grade" toggle, default off.** Per-use-case/per-assessment coverage renders only when the governing AIIA is `APPROVED` (else an empty-state), per DF3-2. The `include_unapproved`+interactive combination is doubly removed from audit-grade and never renders adjacent to export-embedded audit-grade coverage without a hard divider. | INV-38: coverage reports on an APPROVED governing-AIIA; an in-progress view must be opt-in and clearly non-audit-grade. | A4, NB4 |
| DF6-9 | **Single-home: lifecycle-posture vs control-coverage vs live-authorisation vs ATO-basis are distinct truths, cross-linked not duplicated.** Dashboard "portfolio posture" (PortfolioHub) = lifecycle rollup; `/audit` coverage = control evidence; F4's ATO terminal (`GET .../authorisation`, live_state) = current authorisation status; F6's ATO document (`GET .../authorisation/document`) = take-away basis. F6 links to these, never restates them. | Single home per truth; pre-empts a duplication finding. | A6 |
| DF6-10 | **ATO-document round handling: default latest, no enumeration call.** The standalone ATO document defaults to the latest round; a prior-round standalone document is a manual `?round=N` deep-link with no enumeration read. All rounds are visible and labelled (`submission_round`) inside the use-case export pack's `atos[]` section — itself a deliberate audited generation, so listing its own rounds costs no extra disclosure. | `GET .../authorisation` is latest-only (verified, N3); the only round list is `atos[]` via the export-staging routes; (a) preserves both zero-delta and DF6-2/INV-53. **Rejected:** (b) a list-ATOs read (breaks zero-delta); (c) picker-generates-export (breaks DF6-2). | B2, N3, V-10 |

---

## 2. What F6 wires (present vs ALTER)

All routes **PRESENT** (built 7a/7b, `gov:ALL`, admin → 403). No route added, removed, or re-gated.

**Coverage — `app/routers/v1/coverage.py` (PRESENT, eager, no audit, `staleTime: 0`):**
- `GET /v1/coverage[?framework][&include_unapproved]` → `CoverageMatrixRead`
- `GET /v1/systems/{id}/coverage[?framework][&include_unapproved]` → `CoverageMatrixRead`
- `GET /v1/assessments/{id}/coverage[?framework][&include_unapproved]` → `CoverageMatrixRead` (422 on a feeder id)

**Export / audit pack — `app/routers/v1/export.py` (PRESENT, user-initiated, stages `export.generated`):**
- `GET /v1/systems/{id}/export[?framework]` → `SystemExportRead`
- `GET /v1/use-cases/{id}/export[?framework]` → `UseCaseExportRead`
- `GET /v1/use-cases/{id}/authorisation/document[?round]` → `AtoDocumentRead` (404 if never authorised)
- `GET /v1/export?framework=` → `FrameworkExportRead`

**Reused reads (PRESENT):** `GET /v1/me` (role branch, DF2-5 pattern) · `GET /v1/evidence/{id}` (hardened manifest download, INV-22).

**Surfaces:**
- `apps/tenant/app/audit` — **NEW**. Programme home: tenant coverage matrix; framework export; pack index.
- `apps/tenant/app/systems/[id]` — **ALTER**. System-coverage panel; system-export action.
- `apps/tenant/app/use-cases/[id]` — **ALTER**. Use-case-coverage panel (APPROVED-gated); use-case-export action; ATO-document action.
- `apps/tenant/app/dashboard` — **ALTER (link only)**. PortfolioHub posture section links into `/audit`; no coverage truth rendered here (DF6-9).

**Shared `@irontrust/ui` (additions, finalised at handoff):** coverage matrix table (verdict chips SATISFIED/PARTIAL/OPEN/UNADDRESSED + breakdown disclosure), not-an-obligation-set banner, audit-pack section renderer, evidence-manifest table (download via hardened route), content-hash/generated-at stamp, ATO-document view with drift caveat. `FE-3` tokens, `FE-4` density, assurance skin.

---

## 3. Role branch (reuse 5-way `resolveRoleBranch`, F4)

F6 has no domain-state act, so the branch collapses to gov-role-vs-admin plus face lean (presentational). No act-SoD absence to compute.

| Caller | `/audit` + panels | Face lean |
|---|---|---|
| **auditor** (primary) | Full: coverage + export + ATO doc, read-only | Assurance, dense |
| **reviewer / authoriser** | Full read | Assurance |
| **system_owner / contributor** | Full read (coverage is a posture signal; export available) | Adoption-leaning |
| **admin** (zero gov roles) | Empty-state; **no** coverage/export call issued (DF2-5; all routes `gov:ALL` → 403) | n/a |

No `FE-8` act-bar and no `FE-11` court row — there is no act to bar and no court to route.

---

## 4. Load-bearing display semantics

**4.1 Coverage honesty (DF6-3, DF6-4).** `CoverageMatrixRead.controls[]` carries `verdict` (plain str: `SATISFIED`/`PARTIAL`/`OPEN`/`UNADDRESSED` — UNADDRESSED has no DB enum, do not type-bind) and a `breakdown` (`satisfied`/`partial`/`open`/`downgraded_unsubstantiated` + `contributing_refs`). `UX-4` reasoning-first: the breakdown is the shown reasoning and is always reachable.
- Interactive panels (`require_evidence_for_satisfied=false`, internal): `downgraded_unsubstantiated` is always 0; a `SATISFIED` may be unsubstantiated. Label: interactive posture, not audit-grade.
- Export-embedded coverage (`*ExportRead.coverage`, `true`): unsubstantiated `SATISFIED` shows as `PARTIAL`; `downgraded_unsubstantiated` is first-class and rendered distinctly from genuine partials. Label: audit-grade.
- `not_an_obligation_set` (true until applicability lands) drives a persistent caveat banner; `unaddressed_controls[]` renders under "gaps shown, not an obligation set," never a fail denominator.
- The `include_unapproved`+interactive combined state (DF6-8/NB4) is doubly non-audit-grade and never renders adjacent to export-embedded audit-grade coverage without a hard divider.

**4.2 Export pack view (DF6-2, DF6-6).** User clicks "generate audit pack" → one fetch → `export.generated` staged. Renders the payload sectioned: system context, classification history (all versions), assessment (native + feeder via `surfaces_into`, never `assemble_aiia_items` — INV-41), evidence manifest, coverage (audit-grade), lifecycle trail, ATOs, audit trail. Shows `content_hash` (INV-43/D-30) and `generated_at`. Print-to-PDF is the take-away. Re-generating is a fresh audited event; the UI makes that explicit (no silent re-fetch on focus/mount).

**Two-event audit model (NB2):** one `export.generated` per pack/ATO-document generation (INV-42), plus one `evidence.access` per manifest download (INV-22). Stated so the handoff done-checks do not assume a write-free surface.

**4.3 Evidence manifest (INV-22, INV-40).** Manifest rows render id/title/sha256/content_type/size_bytes/back_refs. **No bytes, no embedded URL** — each download constructs the hardened `GET /v1/evidence/{id}` (forced attachment, neutralised content-type), identical to F5 (DF5-3). The manifest never carries a URL.

**4.4 ATO document (DF6-5, DF6-10).** User-initiated. Defaults to the latest round; a prior-round standalone document is a `?round=N` deep-link (no enumeration read). All rounds are visible/labelled in the use-case export pack's `atos[]`. Renders `ato` + `current_assessment_summary` + `current_classification_summary` under the drift caveat (always-true `basis_is_current_state_not_authorisation_snapshot`; INV-44/D-34). The ATO authoriser identity (`authorised_by_name`/`authorised_by_email`) is durable-stamped (D-13/D-14, the D-25 exception) and reliably present — it does **not** inherit the §4.5 bare-ref hedge. 404 → "no authorisation document; this use case has never been authorised."

**4.5 Trail actor attribution (D-25).** Audit/lifecycle trail `actor` is an `ActorRef` on `LifecycleTrailEntryRead`/`AuditTrailEntryRead`. Where it resolves a display name (INV-34 read-time join), render it; where it is a bare ref (D-25 deferred gap), render the ref/role and never fabricate a name — same posture as DF5-11. This hedge applies to the trail actors only, never the ATO authoriser (§4.4). V-9 confirms the live `ActorRef` shape for the trails.

---

## 5. Invariant candidates (CONVENTION; append at sprint close, do not renumber)

F6 is pure frontend, so its new constraints are discipline-only (review-caught), tagged CONVENTION. Next free ids above the INV-50 ceiling.

- **INV-51 · CONVENTION ·** Interactive coverage (`require_evidence_for_satisfied=false`) is never presented as the audit verdict; the audit-grade verdict is the export-embedded coverage (`true`). The two may legitimately differ for one control and must be visually distinguished. The interactive route exposes no flag to request `true`, so the line is structurally non-bypassable. ↳ refs: D-29, DF6-3
- **INV-52 · CONVENTION ·** The coverage matrix visibly carries `not_an_obligation_set` and renders `unaddressed_controls` as gaps, not failures; no compliance-percentage headline treats unaddressed as fail until applicability (OPEN-3). The `include_unapproved`+interactive combined state is hard-divided from audit-grade coverage. ↳ refs: D-28, OPEN-3, DF6-4, DF6-8
- **INV-53 · CONVENTION ·** The client issues an export/audit-pack or ATO-document fetch only on explicit user action, never as an eager mount/focus fetch — because each such read stages a disclosure event (the staging fact lives in **INV-42**, not restated here). Coverage reads are exempt (no audit). ↳ refs: INV-42, PAT-10, D-35, DF6-2

Reused, not re-minted: **INV-42** (export staging), INV-22 (hardened evidence download + `evidence.access`), INV-40 (manifest never bytes/URL), INV-41 (export AIIA section shape), INV-44/D-34 (ATO drift), INV-25 + FE-7 (live coverage, `staleTime: 0`), INV-43/D-30 (content_hash), INV-34 (ATO authoriser via membership join).

---

## §0 — Pre-flight verify checklist (D-21)

Closed at design (source-attested, Appendix B): V-3, V-4, V-5, V-6, V-7, V-8, V-10, plus N1/N2/N3/NB3. Remaining live binds for the agent:

| V | Item | Why binding |
|---|---|---|
| V-1 | No coverage/export tenant surface (`apps/tenant/app/audit`, coverage panels) has landed since the F5 sync. | Repo-ahead-of-canonical; would re-scope the sprint. |
| V-2 | Live gate on every coverage + export route is any-governance-role incl. auditor, admin → 403, at HEAD. | The role branch and the auditor-persona claim depend on it. |
| V-9 | Live `ActorRef` shape in export trails (`LifecycleTrailEntryRead.actor`/`AuditTrailEntryRead.actor`) — resolvable display name vs bare ref. | Binds §4.5 — render what exists, no fabrication (D-25). ATO authoriser is out of scope here (durable, §4.4). |

---

## Appendix A — Decisions (all resolved; founder-confirmed)

A1 dedicated `/audit` home → **DF6-1**. A2 EXP-2 deferred → **DF6-7**. A3 PDF deferred → **DF6-6**. A4 `include_unapproved` exposed, default off, hard divider → **DF6-8**. A5 export user-initiated → **DF6-2**. A6 single-home posture → **DF6-9**. A7 framework export on `/audit` → confirmed (DF6-1 pack index). B2 round picker → **DF6-10 (option a)**. NB5 tenant-wide `staleTime` → honour FE-7 `staleTime: 0` on all coverage including the tenant-wide matrix (correctness over perf for an audit tool; workstation surface).

## Appendix B — Source-verification register

| Claim | Source | State |
|---|---|---|
| Coverage routes, gate, params (`framework`/`include_unapproved` only — no `require_evidence_for_satisfied`), 422-on-feeder | `app/routers/v1/coverage.py` | Verified (N1) |
| Export routes, gate, 404-on-never-authorised, `?round` | `app/routers/v1/export.py` | Verified |
| `CoverageMatrixRead` carries literal `not_an_obligation_set: bool`, `unaddressed_controls`, `verdict` str, `downgraded_unsubstantiated` | `app/schemas/coverage.py` | Verified (N2) |
| `downgraded_unsubstantiated` non-zero only under `require_evidence_for_satisfied=true`; export passes `true`, interactive computes `false` | `STATE.md` 7a/7b, D-29, coverage.py | Verified (V-4) |
| Export stages `export.generated`; `_export_session`; PAT-10/D-35; INV-42 the only audit-writing read besides `evidence.access` | `INVARIANTS.md` INV-42, `PATTERNS.md` PAT-10 | Verified (V-3, V-8, B1) |
| `UseCaseExportRead`/`SystemExportRead`/`AtoDocumentRead`/`FrameworkExportRead`; manifest-only evidence; `content_hash`; `basis_is_current_state_not_authorisation_snapshot` always true | `app/schemas/export.py` | Verified (V-6, V-7) |
| `DeploymentAuthorisationRead.submission_round: int` labellable; `GET .../authorisation` latest-only; no non-export round-list route | `app/schemas/lifecycle.py`, `app/routers/v1/lifecycle.py` | Verified (N3, V-10, B2) |
| ATO authoriser durable-stamped (`authorised_by_name`/`_email`), D-13/D-14, INV-34, the D-25 exception | `app/schemas/lifecycle.py`, INV-34/44 | Verified (NB3) |
| 5-way `resolveRoleBranch`; DF2-5 admin-no-call; `gov:ALL` → 403 | `STATE.md` F3/F4 | Verified — reconfirm gate at HEAD (V-2) |
| Trail `ActorRef` resolvability | — | **Open — V-9** |
| Repo not ahead of F5 sync; gate at HEAD | — | **Open — V-1/V-2** |

## Appendix C — Review disposition

| Finding | Class | Disposition |
|---|---|---|
| B1 INV-53 duplicates INV-42 | Blocking | **Accepted.** INV-53 reworded to the frontend-only constraint, refs INV-42; INV-42 added to §5 reused set. |
| B2 `?round` enumeration gap | Blocking | **Accepted.** Verified no zero-delta enumeration source; resolved via DF6-10 (option a). V-10 promoted then closed. |
| N1 `require_evidence_for_satisfied` not client-settable | Needs SV | **Closed.** Not a coverage route param; structurally non-bypassable (INV-51 notes it). |
| N2 `not_an_obligation_set` literal field | Needs SV | **Closed.** Literal `bool` on `CoverageMatrixRead`. |
| N3 `submission_round` labellable / round-list source | Needs SV | **Closed.** Field present; `GET .../authorisation` latest-only; only `atos[]` lists rounds — drives DF6-10. |
| N4 repo-ahead + gate-at-HEAD | Needs SV | **Open (live).** Cannot close from the mirror; carried as V-1/V-2. |
| NB1 status-line precision | Non-blocking | **Accepted.** "No domain-state mutation; one audit-writing read." |
| NB2 second audit event | Non-blocking | **Accepted.** Two-event model stated (§4.2). |
| NB3 ATO authoriser ≠ bare ref | Non-blocking | **Accepted.** §4.4 carries no hedge; §4.5 hedge scoped to trail actors. |
| NB4 doubly-not-audit-grade combined state | Non-blocking | **Accepted.** INV-51+INV-52 jointly cover; hard divider (DF6-8). |
| NB5 tenant-wide `staleTime` | Non-blocking | **Accepted.** Honour FE-7 `staleTime: 0` across coverage. |
| Clean set | Clean | Acknowledged, no change. |