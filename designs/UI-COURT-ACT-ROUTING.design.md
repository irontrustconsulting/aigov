# DESIGN (FINAL) · UI-COURT-ACT-ROUTING

**Sprint (provisional):** `UI-COURT-ACT-ROUTING` · fix-class, presentational routing correction
**Status:** DESIGN FINAL · review folded (B1–B3, N1–N3, SV1–SV3) · handoff ready
**Problem:** a your-court entry routes a use-case-scoped act to `/systems/{id}` (a read/rollup surface with no act), stranding the actor one hop short of the affordance.
**Blast radius (ALTER):** `apps/tenant/lib/portfolio/court.ts`, `apps/tenant/app/dashboard/page.tsx`, `apps/tenant/app/systems/[id]/system-detail-client.tsx`, `apps/tenant/app/dashboard/__tests__/f10-clearance-dashboard.test.tsx` + one false comment + one misleading STATE paragraph.
**Backend delta:** none. **Migrations:** 0. **Routes:** 0. **Tables/enums:** 0.
**New IDs (provisional, re-base at build, SV-6):** `D-81`, `INV-92`, `FE-37`.
**Cross-refs:** D-4, D-79, D-80, DF-CLR-13, DF-CLR-21, DF4-1, INV-30, INV-91, DOMAIN §3, UX (court-is-action-based).

---

## 1. Diagnosis (grounded)

The your-court row is action-based: it asserts "this is waiting on you" and must land on the surface that carries the act. Present routing in `dashboard/page.tsx` (matches HEAD):

```
href = isClearanceBlock(court) ? "/clearances" : `/systems/${system.system_id}`
```

Two mis-routes, distinct provenance:

**(a) Owner and reviewer courts: accidental fall-through.** The reported case is Steve Rowe → Microsoft Copilot / Employee Productivity: court `responsible_party="user"`, `reason_code="no_aiia"`, reason "No assessment started for this use case" (matches the live screen). Not a clearance block, so it falls to the `else` and lands on `/systems/{id}`, the rollup. Per DOMAIN §3 the rollup is a view: it never holds the assessment, so it carries no act. The owner's act (`Start assessment`, `useBootstrapAssessment`, `POST /use-cases/{id}/assessments`) lives in `NoAssessmentState` on `apps/tenant/app/use-cases/[id]/assessment-page-client.tsx`, at `/use-cases/{use_case_id}`. The reviewer courts fall through the same `else`; their acts (review panel WI-2, sign-off panel WI-3) also live at `/use-cases/{id}`. No prior decision reasoned these onto `/systems/{id}`: this is a plain fall-through.

**(b) Deployment-authorisation court: a deliberately-preserved-but-wrong destination.** `authorisation_gate` → `no_current_authorisation` → `responsible_party="authoriser"` (INV-30). DF-CLR-21 deliberately kept this on `/systems/{id}` (the non-clearance branch), on the premise that the existing `AuthorisePanel` handled it on the system drill-in. That premise is false: `AuthorisePanel` lives at `apps/tenant/app/use-cases/[id]/_regions/authorise-panel.tsx` (WI-4, DF4-1), on `/use-cases/{id}`, not on `/systems/{id}`. DF-CLR-21's own rejection rationale ("stranding the authoriser away from the existing AuthorisePanel") argues *for* `/use-cases/{id}`, since that is where the panel is. So this destination is corrected, not accidentally overridden: D-81 supersedes DF-CLR-21's non-clearance-destination clause while preserving its clearance discriminator (§3 R6).

## 2. Every non-clearance court's act home is `/use-cases/{id}` (verified)

| Court | Emitter | Act surface | Route |
|---|---|---|---|
| `no_aiia` (owner start) | lifecycle gate → `user` | `NoAssessmentState` (system_owner branch) | `/use-cases/{id}` |
| risk treatment (`treatment_decision_missing`, `mitigation_unsubstantiated`, `acceptance_unjustified`) → `user` | `treatment` gate | assessment items | `/use-cases/{id}` |
| classification sign-off (`tier_not_ratified`) → `reviewer` | classification gate | sign-off panel (WI-3) | `/use-cases/{id}` |
| AIIA review (IN_REVIEW) → `reviewer` | review flow | `review-panel.tsx` (WI-2) | `/use-cases/{id}` |
| deployment authorisation (`no_current_authorisation`) → `authoriser` | `authorisation_gate` | `authorise-panel.tsx` (WI-4, INV-30) | `/use-cases/{id}` |
| vendor/product clearance (`vendor_*`/`product_*`) → `authoriser` | `vendor_gate`/`product_gate` | set-clearance (D-79) | `/clearances` |

The Review queue (`review-queue-client.tsx`) holds no act: every row links to `/use-cases/{use_case_id}` (Topology B, DF4-1). DF4-2 confirms both reviewer acts map to the same `reviewer` court and the use-case surface disambiguates by object state, not by routing. **Conclusion: the reviewer fork is closed by canon. Every non-clearance court routes to `/use-cases/{id}`, with no `/review` exception.**

## 3. Resolved decisions

| # | Decision | Rationale | Rejected |
|---|---|---|---|
| R1 | Retire `/systems/{id}` as a court destination | It is a read/rollup (DOMAIN §3); an action-based worklist must land on the act. No court's act lives there. | Keep `/systems/{id}` for non-clearance courts (the present defect). |
| R2 | Every use-case-scoped court routes to `/use-cases/{use_case_id}` | That surface already role-branches to the correct act for owner, reviewer, and authoriser. No new act surface built. | Add a `Start assessment` control onto the rollup: violates single-home (act home is `/use-cases/{id}`) and DOMAIN §3; fixes only the owner, leaves the authoriser mis-route. |
| R3 | Clearance courts keep `/clearances` | Clearance is vendor/product-scoped, not use-case-scoped (D-79, DF-CLR-21). | Route clearance to `/use-cases/{id}`: no per-use-case act exists for a vendor/product-scoped block. |
| R4 | One shared resolver `courtHref(court, useCaseId)` in `court.ts`; both call sites consume it | Prevents the two-site divergence DF-CLR-21 already guarded against; single-homes the routing truth. | Inline the href at each call site (present shape; divergence risk). |
| R5 | Reviewer fork closed by canon, not by founder decision | §2: Review queue funnels to `/use-cases/{id}`; both reviewer acts live there (WI-2, WI-3, DF4-1, DF4-2). | Route reviewer courts to `/review`: reproduces the defect for reviewers. |
| R6 | D-81 supersedes DF-CLR-21's non-clearance-destination clause | DF-CLR-21 kept the deployment-authorisation court on `/systems/{id}` on a false AuthorisePanel-location premise; its own anti-stranding rationale argues for `/use-cases/{id}`. The `reason_code` clearance discriminator (DF-CLR-21) is retained unchanged. | Leave DF-CLR-21's destination clause live (perpetuates the authoriser mis-route). |

## 4. Present vs ALTER

| File | State | Change |
|---|---|---|
| `apps/tenant/lib/portfolio/court.ts` | ALTER | Add `courtHref(court: ResolvedCourt \| null, useCaseId: string): string`. Clearance block → `/clearances`; else (including `court === null`) → `/use-cases/${useCaseId}`. The null branch is unreachable from both call sites (your-court entries always carry a non-null court; `vendor`/`system` parties are excluded by `isYourCourt`), and is defined only so the resolver is total: it is not a latent bug. Reuses `isClearanceBlock` (D-79, DF-CLR-21). No change to `resolveCourt`/`ResolvedCourt`/`isYourCourt`. |
| `apps/tenant/app/dashboard/page.tsx` | ALTER | Replace the inline ternary with `courtHref(court, useCase.use_case_id)`. `use_case_id` is already in scope (row key). Delete the false DF-CLR-13 comment ("AuthorisePanel on the system drill-in"). |
| `apps/tenant/app/systems/[id]/system-detail-client.tsx` | ALTER | The additive clearance deep-link on authoriser-court rows routes through `courtHref` (single-home). The per-use-case title link to `/use-cases/{id}` is unchanged (V-4). The existing DF-CLR-13 deep-link comment here is accurate and stays. |
| `apps/tenant/app/dashboard/__tests__/f10-clearance-dashboard.test.tsx` | ALTER | The live test asserting the deployment-authorisation row keeps `/systems/{id}` now asserts `/use-cases/{use_case_id}`; rename accordingly. Confirm no owner/reviewer routing test in this file (or any dashboard court test) asserts `/systems/{id}`; if present, flip to `/use-cases/{id}`. |
| `docs/STATE.md` | ALTER (canonical-update WI) | Correct the F10 re-treatment paragraph: non-clearance courts route to `/use-cases/{id}`, not `/systems/{id}`; strike the "existing AuthorisePanel" phrasing that implies the drill-in. |

No copy change on the destination: the `no_aiia` court reason ("No assessment started for this use case") stays; on `/use-cases/{id}` the owner sees the `Start assessment` button (or a 409 blocked-reason if classification is not ready, `classification_readiness()`, V-1b). Steve's use case is `limited_risk`, so bootstrap succeeds (confirm SV1).

## 5. Invariants

**INV-92 (CONVENTION, new).** A your-court entry routes to the surface that carries its act. Use-case-scoped courts route to `/use-cases/{use_case_id}`; clearance courts (vendor/product-scoped, D-79) route to `/clearances`. A court never routes to a read or rollup surface (`/systems/{id}` is not an act home, DOMAIN §3). Cross-refs: D-4, D-79, D-80, D-81, INV-30, INV-91.

**Standing enforcement (ties INV-92 to §0 P2, not a one-off).** Any new `(responsible_party, reason_code)` pair minted in `app/services/lifecycle_gates.py` must declare its act surface before `courtHref` is extended to route it. The P2 emitter enumeration is the recurring enforcement point: a pair whose act is `/use-cases/{id}` must not be given a bespoke non-act destination, and a pair with a new act surface must extend `courtHref` explicitly rather than fall through.

## 6. §0 pre-flight verify checklist (D-21, run at build before any edit)

- [ ] **P1 (currency).** Re-read `court.ts`, `dashboard/page.tsx`, `system-detail-client.tsx`, and `f10-clearance-dashboard.test.tsx` at HEAD. The live "No assessment started" copy and the quoted ternary both match the KB, so this surface is current; confirm no later sprint touched court routing.
- [ ] **P2 (emitter enumeration).** From live `app/services/lifecycle_gates.py`, enumerate every `(responsible_party, reason_code)` pair. Confirm each non-clearance pair's act resolves on `/use-cases/{id}` (SV3). Guard against a third latent mis-route; empirical backing for INV-92.
- [ ] **P3 (comment/paragraph correction).** Confirm the `dashboard/page.tsx` DF-CLR-13 comment asserts "AuthorisePanel on the system drill-in" (false) and mark for deletion. Confirm the STATE F2 paragraph's "existing AuthorisePanel" phrasing (misleading, not false) and mark for correction. The `system-detail-client.tsx` comment is accurate: leave it.
- [ ] **P4 (scope).** Confirm `use_case_id` is in scope at the dashboard court call site (row key) and at the system-detail deep-link site.
- [ ] **P5 (id re-base).** Re-base `D-81`/`INV-92`/`FE-37` against the live ceiling; INV/D re-base against `INV-91`/`D-80`, FE against `FE-36` (INDEX's "FE-1..33 populated" lags the repo: FE-34 `GroupedMultiSelect`, FE-35 `TextInput`, FE-36 pre-commit disposition gate are live). Never renumber a live id (SV-6).
- [ ] **SV1 (owner affordance).** Confirm `NoAssessmentState` system_owner branch renders `Start assessment` at `/use-cases/{id}` with no 409 for a `limited_risk` use case. The owner fix rests on this.
- [ ] **SV2 (test inventory).** Confirm `f10-clearance-dashboard.test.tsx` is the only routing test asserting `/systems/{id}` and no separate owner/reviewer routing test exists; extends B1/P4.
- [ ] **SV3 (see P2).** Emitter enumeration stays in the handoff, not folded away.

## Appendix A — Open decisions

- **A1 (fold FE-37?).** FE-37 ("court routing single-homed in `courtHref()`; no call site inlines a court href") overlaps INV-92's mechanism. Keep FE-37 as a distinct frontend contract (client-contract shape) versus fold the single-home clause into INV-92 and drop FE-37. Default: keep FE-37. Re-base at build (P5).
- **A2 (out of scope, noted).** The F1 intake terminal `apps/tenant/app/systems/new/_steps/whose-court-step.tsx` is a status read ("With you: start the assessment to continue."), not an act: after registration the user lands there and must navigate onward. Same read-vs-act shape as this fix but a distinct surface. Candidate follow-up: give the intake terminal a forward affordance via `courtHref`. Not folded here to keep the blast radius to the your-court routing defect.

## Appendix B — Source-verification register

| ID | Claim to verify | Target (file:line at HEAD) |
|---|---|---|
| SV-A | `courtHref` inputs available; `isClearanceBlock` unchanged; null branch total | `apps/tenant/lib/portfolio/court.ts` |
| SV-B | Dashboard court call site has `useCase.use_case_id` in scope | `apps/tenant/app/dashboard/page.tsx` (yourCourtEntries map) |
| SV-C | System-detail deep-link site and per-use-case `/use-cases/{id}` title link; comment accurate | `apps/tenant/app/systems/[id]/system-detail-client.tsx` |
| SV-D | Owner `Start assessment` affordance + 409 blocked-reason path (SV1) | `apps/tenant/app/use-cases/[id]/assessment-page-client.tsx` (NoAssessmentState) |
| SV-E | `authorisation_gate` emits `authoriser`/`no_current_authorisation` (INV-30) | `app/services/lifecycle_gates.py` |
| SV-F | Review queue rows link to `/use-cases/{id}`; no `/review` act surface | `apps/tenant/app/review-queue/review-queue-client.tsx` |
| SV-G | Live deployment-authorisation routing test asserting `/systems/{id}` (to flip); false DF-CLR-13 comment in `dashboard/page.tsx`; misleading STATE F2 paragraph | `apps/tenant/app/dashboard/__tests__/f10-clearance-dashboard.test.tsx`; `dashboard/page.tsx`; `docs/STATE.md` |