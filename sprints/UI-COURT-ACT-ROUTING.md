# HANDOFF · UI-COURT-ACT-ROUTING (execution-only)

**Class:** presentational routing correction. **Backend delta:** none. **Migrations:** 0. **Routes:** 0. **Tables/enums:** 0.
**Rationale lives in `UI-COURT-ACT-ROUTING.design.md`; do not re-derive it here.**
**Guardrail (INV-68/D-51):** implement only. If any step needs a visual/layout/UX decision not specified here, stop and flag; do not improvise and do not record an undesigned decision in canon.

---

## §0 Pre-flight (do first; do not edit until all pass)

- [ ] **P1.** Read at HEAD: `apps/tenant/lib/portfolio/court.ts`, `apps/tenant/app/dashboard/page.tsx`, `apps/tenant/app/systems/[id]/system-detail-client.tsx`, `apps/tenant/app/dashboard/__tests__/f10-clearance-dashboard.test.tsx`. Confirm the dashboard court href is still `isClearanceBlock(court) ? "/clearances" : \`/systems/${system.system_id}\``. If a later sprint already re-routed it, STOP and report.
- [ ] **P2.** Enumerate every `(responsible_party, reason_code)` pair emitted by `app/services/lifecycle_gates.py`. Confirm each non-clearance pair's act surface is `/use-cases/{id}`. If any non-clearance pair's act is NOT `/use-cases/{id}`, STOP and report (INV-92 would need an explicit `courtHref` branch, out of this handoff's scope).
- [ ] **P3.** Confirm SV1: `NoAssessmentState` system_owner branch (`apps/tenant/app/use-cases/[id]/assessment-page-client.tsx`) renders `Start assessment` and does not 409 for a `limited_risk` use case.
- [ ] **P4.** Confirm `use_case_id` is in scope at the dashboard court call site and the system-detail deep-link site.
- [ ] **P5 (id re-base).** Live ceilings: `INV-91`, `D-80`, `FE-36`. Mint `INV-92`, `D-81`, `FE-37`. If any is taken at HEAD, take the next free id and record the re-base. Never renumber a live id.

---

## Work items (dependency-ordered)

### WI-1 · `courtHref` resolver in `court.ts`
- ALTER `apps/tenant/lib/portfolio/court.ts`: add
  `export function courtHref(court: ResolvedCourt | null, useCaseId: string): string`
  returning `"/clearances"` when `court && isClearanceBlock(court)`, else `\`/use-cases/${useCaseId}\``.
- Do not modify `resolveCourt`, `ResolvedCourt`, `isClearanceBlock`, or `isYourCourt`.
- **Done-check:** unit test `courtHref`: clearance-block court → `/clearances`; `user` court → `/use-cases/{id}`; `authoriser` + `no_current_authorisation` court → `/use-cases/{id}`; `reviewer` court → `/use-cases/{id}`; `null` → `/use-cases/{id}`.

### WI-2 · Dashboard consumes `courtHref` (depends on WI-1)
- ALTER `apps/tenant/app/dashboard/page.tsx`: replace the inline `href` ternary in the `yourCourtEntries` map with `courtHref(court, useCase.use_case_id)`.
- Delete the DF-CLR-13 comment asserting "AuthorisePanel on the system drill-in" (false; P3 confirmed the panel is at `/use-cases/{id}`).
- **Done-check:** existing dashboard render/court tests green except the routing assertions rewritten in WI-4.

### WI-3 · System-detail deep-link via `courtHref` (depends on WI-1)
- ALTER `apps/tenant/app/systems/[id]/system-detail-client.tsx`: route the additive clearance deep-link on authoriser-court rows through `courtHref`. Leave the per-use-case title link to `/use-cases/{id}` (V-4) unchanged. Leave the existing (accurate) DF-CLR-13 deep-link comment.
- **Done-check:** `systems/[id]/__tests__/page.test.tsx` clearance deep-link test green (`/clearances`); V-4 title-link test green (`/use-cases/{id}`); link counts unchanged.

### WI-4 · Rewrite the deployment-authorisation routing test (depends on WI-2)
- ALTER `apps/tenant/app/dashboard/__tests__/f10-clearance-dashboard.test.tsx`: the test asserting a deployment-authorisation (`no_current_authorisation`) authoriser-court row keeps `/systems/{id}` now asserts `href === \`/use-cases/${use_case_id}\``; rename to reflect the new destination.
- Confirm (P4/SV2) no owner/reviewer routing test in this file (or any dashboard court test) asserts `/systems/{id}`; if present, flip to `/use-cases/{id}`.
- **Done-check:** full `f10-clearance-dashboard.test.tsx` suite green; no assertion in the dashboard test tree targets `/systems/{id}` as a court destination.

### WI-5 · Full regression
- **Done-check:** `apps/tenant` unit/integration suite green; `packages/ui` unchanged (no touch); typecheck and lint clean (`no-literal-token-value` untouched).

### WI-6 · Canonical update (last; volatile tier only)
- **STATE.md:** correct the `UI-F10-CLEARANCE` F2 re-treatment paragraph: non-clearance courts route to `/use-cases/{id}` (not `/systems/{id}`); strike the "existing AuthorisePanel" phrasing implying the system drill-in. Add a `UI-COURT-ACT-ROUTING` entry: presentational routing correction, `courtHref` single-home in `court.ts`, 0 backend/schema/route delta.
- **DATA-MODEL.md:** no change (no schema delta); state so explicitly in the sprint note.
- **INVARIANTS.md:** append `INV-92` (CONVENTION) per design §5, including the standing-enforcement clause tying it to the P2 emitter enumeration. Cross-ref D-4, D-79, D-80, D-81, INV-30, INV-91.
- **DECISIONS.md:** append `D-81` per design §3 R1/R2/R6; it must state that it supersedes DF-CLR-21's non-clearance-destination clause and retains DF-CLR-21's `reason_code` clearance discriminator. Append `FE-37` per design Appendix A1.
- Do not renumber any live INV-n / D-n / FE-n. Leave the stable tier untouched.
- **Done-check:** ceilings advanced to the minted ids; INDEX ceiling line updated; `docs/` "Sync now" reminder noted for the founder.