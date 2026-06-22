# UI-F6-AUDITPACK — Sprint Handoff (execution-only)

**For:** Claude Code (VS Code, plan mode). **Rationale lives in the design doc (`UI-F6-AUDITPACK-design-final.md`), not here.**
**Surface:** tenant audit-pack capstone — coverage view + export/audit pack + ATO document. Last tenant surface.
**Backend delta:** **none expected** (every route built, `gov:ALL`). If §0 finds a gap, stop and report; do not invent a route or widen scope.
**Mutation profile:** no domain-state mutation; one audit-writing read (`export.generated`, INV-42) on deliberate generation; `evidence.access` (INV-22) per manifest download. No `If-Match`, no act-SoD control, no whose-court row.

---

## §0 — Pre-flight (run first; block on failure)

- **V-1 ·** Confirm no coverage/export tenant surface exists at HEAD (`apps/tenant/app/audit`, any coverage panel on `systems/[id]`/`use-cases/[id]`). If present, STOP and report — the sprint re-scopes.
- **V-2 ·** Confirm live gate on every route in `app/routers/v1/coverage.py` and `app/routers/v1/export.py` is any-governance-role (incl. `auditor`), admin → 403, at HEAD (D-21).
- **V-9 ·** Inspect the live `ActorRef` shape used by `LifecycleTrailEntryRead.actor`/`AuditTrailEntryRead.actor` (`app/schemas/export.py`); record whether it carries a resolvable display name or a bare ref. Drives WI-1 trail rendering.
- Design-closed (do not re-verify unless touched): V-3/V-4/V-5/V-6/V-7/V-8/V-10, N1/N2/N3/NB3 — see design doc Appendix B.

---

## Work items (dependency-ordered)

### WI-1 · Shared `@irontrust/ui` components
Build, themed by `FE-3` (assurance skin, `FE-4` density), no literal token values (lint):
1. `CoverageMatrix` — table of `ControlCoverageRead`: `code`/`title`, verdict chip (`SATISFIED`/`PARTIAL`/`OPEN`/`UNADDRESSED`; treat `verdict` as plain str, no enum bind), expandable `breakdown` disclosure (`satisfied`/`partial`/`open`/`downgraded_unsubstantiated` + `contributing_refs`). `downgraded_unsubstantiated` rendered distinctly from `partial`, never folded in.
2. `NotAnObligationSetBanner` — persistent caveat driven by `not_an_obligation_set`; renders `unaddressed_controls[]` under "gaps shown, not an obligation set." No compliance-percentage headline.
3. `AuditGradeDivider` — hard visual divider; required wherever interactive-posture coverage and export-embedded audit-grade coverage could co-render, and around any `include_unapproved=true` view.
4. `AuditPackView` — sectioned renderer for `UseCaseExportRead`/`SystemExportRead`: system context, classification history, assessment (native + feeders via `surfaces_into`), evidence manifest, coverage (audit-grade), lifecycle trail, ATOs, audit trail. Footer: `content_hash` + `generated_at`. Print-friendly layout.
5. `EvidenceManifestTable` — rows id/title/sha256/content_type/size_bytes/back_refs; each download action constructs `GET /v1/evidence/{id}` (hardened). No bytes, no embedded URL (INV-40).
6. `AtoDocumentView` — renders `AtoDocumentRead`; persistent drift caveat (`basis_is_current_state_not_authorisation_snapshot` always true). Authoriser identity from `authorised_by_name`/`_email` (durable; show directly). Trail actors elsewhere follow the V-9 rule (resolved name or ref/role, never fabricated).

**Done-check:** `packages/ui` unit tests — verdict-chip mapping incl. UNADDRESSED; `downgraded_unsubstantiated` never merged into `partial`; manifest row emits a hardened `/evidence/{id}` href and never a raw URL; ATO view always shows the drift caveat.

### WI-2 · Data hooks (`apps/tenant/lib/audit`)
Through the BFF (`FE-9`), `@irontrust/api-client` typed:
1. Coverage hooks (`useTenantCoverage`, `useSystemCoverage`, `useUseCaseCoverage`) — eager, `staleTime: 0` (FE-7, NB5 — applies to the tenant-wide matrix too), params `framework?`/`include_unapproved?`.
2. Export hooks (`useSystemExport`, `useUseCaseExport`, `useFrameworkExport`, `useAtoDocument`) — **deliberate only**: `enabled: false` + manual trigger (refetch/mutation-style). Never eager, never refetch-on-focus (INV-53). `useAtoDocument` takes optional `round`; default call omits it (latest).

**Done-check:** network test `apps/tenant/lib/audit/__tests__/network.test.tsx` — asserts no export/ATO-document request fires on mount or window focus for any F6 surface; asserts coverage requests carry no client-set `require_evidence_for_satisfied` (not a param); asserts coverage hooks use `staleTime: 0`.

### WI-3 · `/audit` programme home (NEW `apps/tenant/app/audit`)
1. `GET /v1/me` first; reuse `resolveRoleBranch`. Admin (zero gov roles) → empty-state, **no** coverage/export call (DF2-5).
2. Tenant coverage matrix (`useTenantCoverage`) with `NotAnObligationSetBanner`.
3. `include_unapproved` toggle — labelled "include in-progress (not audit-grade)," default **off**; when on, wrap in `AuditGradeDivider` and the not-audit-grade label (DF6-8/NB4).
4. Framework export action (`useFrameworkExport`, user-initiated) → `AuditPackView` (framework pack: coverage + substantiation manifest).
5. Pack index — entry links to per-system / per-use-case packs (navigation only; generation happens on the entity surface).

**Done-check:** `apps/tenant/app/audit` tests — admin renders empty-state with zero network calls; toggle default off; framework export fires only on click; banner present whenever `not_an_obligation_set` is true.

### WI-4 · `systems/[id]` system panels (ALTER)
1. System-coverage panel (`useSystemCoverage`, eager, `staleTime: 0`, banner).
2. System-export action (`useSystemExport`, user-initiated) → `AuditPackView`.
Reuse the existing role branch; no court row, no act control.

**Done-check:** system-export fires only on click; coverage panel eager; both gated to governance-role callers (admin → absent).

### WI-5 · `use-cases/[id]` use-case panels (ALTER)
1. Use-case-coverage panel (`useUseCaseCoverage` via `GET /assessments/{id}/coverage`) — render only when the governing AIIA is `APPROVED`; else empty-state "coverage available after approval" (DF3-2/INV-38). Banner applies.
2. Use-case-export action (`useUseCaseExport`, user-initiated) → `AuditPackView`.
3. ATO-document action (`useAtoDocument`, user-initiated) → `AtoDocumentView`; defaults to latest round; honour a `?round=N` deep-link when present (DF6-10). Round list, when shown, is read from the already-generated use-case export pack's `atos[]` (`submission_round` labels) — never a separate enumeration call. 404 → "never authorised" empty-state.

**Done-check:** coverage panel hidden on non-`APPROVED` governing AIIA; ATO-document and export fire only on click; `?round` deep-link honoured; no enumeration request for rounds.

### WI-6 · `dashboard` link (ALTER, link-only)
PortfolioHub posture section gains a link into `/audit`. Render no coverage truth here (DF6-9).

**Done-check:** dashboard issues no coverage/export call; link present.

### WI-7 · Surface tests (consolidated done-checks)
- No eager export/ATO-document fetch (WI-2 network test) — the load-bearing INV-53 assertion.
- Coverage eager + `staleTime: 0` across all three scopes.
- Admin-no-call on every F6 surface.
- Manifest download via hardened `/evidence/{id}` only.
- Interactive-vs-audit-grade labelling present; `AuditGradeDivider` between the two and around `include_unapproved`.
- `not_an_obligation_set` banner whenever the flag is true.
- ATO-document drift caveat always shown; authoriser name from the durable stamp.

### WI-8 · Canonical update (final; volatile tier only)
- **STATE.md** — add the `UI-F6-AUDITPACK` surface entry under built capabilities: new `apps/tenant/app/audit`; `systems/[id]`/`use-cases/[id]`/`dashboard` ALTER; consumed routes (coverage + export families, `GET /v1/me`, `GET /v1/evidence/{id}`); **zero backend/schema delta**; two-event audit model (`export.generated` per generation, `evidence.access` per download). Note F6 closes the EXP-1 frontend render-half (interim: in-DOM view + print; templated PDF still deferred).
- **DATA-MODEL.md** — no schema change; no edit required beyond confirming zero delta (if a "frontend surfaces" note exists, append F6).
- **API-ROUTES.md** — append a "`UI-F6-AUDITPACK` — no route delta; consumed-only" note listing the consumed coverage/export routes; no route added, removed, or re-gated.
- **INVARIANTS.md** — append **INV-51**, **INV-52**, **INV-53** exactly as worded in the design doc §5 (all CONVENTION). Do not renumber any live INV-n. INV-53 references INV-42; it must not restate the staging fact.
- **DECISIONS.md** — append **DF6-1 … DF6-10** as worded in design doc §1.
- **Leave the stable tier untouched** (`DOMAIN`, `REQUIREMENTS`, `ARCHITECTURE`, `UX`, `PLATFORM-UX`, `PATTERNS`, `FRONTEND`, `INDEX`). If a new `FE-n` feels warranted (eager-vs-deliberate fetch discipline), propose it for review; do not mint it inline.

**Done-check:** INDEX ceilings line updated (INV through 53; DF6 series noted); no stable-tier diff; no live INV-n renumbered.

---

## Appendix A — Open decisions
None. All A1–A7, B2, NB5 resolved (design doc Appendix A/C).

## Appendix B — Review disposition
All findings disposed in the design doc Appendix C. Live binds carried into §0: V-1, V-2 (N4), V-9.