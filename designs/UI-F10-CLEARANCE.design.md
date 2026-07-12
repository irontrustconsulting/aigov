# DESIGN (FINAL, forks confirmed) UI-F10-CLEARANCE

Authoriser clearance surface, tenant-nav SoD visibility, and F2 your-court/posture composition.

**Status:** FINAL, review folded, forks confirmed; handoff cut alongside · **Plane:** tenant · **Surface:** NEW (`apps/tenant/app/clearances`) plus ALTER at 3 loci (`dashboard/page.tsx` your-court and posture, `system-detail-client.tsx` whose-court link, `TenantSidebar` nav gating) · **Backend delta:** 1 NEW read route plus 1 NEW schema (additive; no table, no enum, no migration) · **Canon touched (volatile tier):** STATE, DATA-MODEL (route inventory only), INVARIANTS (append), DECISIONS (append), FRONTEND (append), API-ROUTES (append) · **Depends on:** Sprint 5 approval endpoints (built), Sprint 6b authorise act (built, unrelated gate), FE-8/UX-5 SoD-visible, FE-11/D-38 whose-court, FE-24/INV-71/DF-F9-3 tenant-plane nav gating (primary precedent; FE-13 operator-plane is the cross-plane analogue only), D-46/D-57 petrol ceiling, D-58 depth-within-restraint, FE-16/D-60 verdict chip plus label map, FE-26/FE-27 elevation plus SectionGroup, INV-52 no-% headline, DF6-9 no dashboard coverage call, D-61/INV-74 scaffolded-empty, C0 kit plus INV-69/INV-70 · **Binding visual spec:** the rendered your-court/posture specimen (this session) · **Provisional IDs:** minted above the reviewer-confirmed ceiling (INV-85, D-76, FE-34); re-base above true HEAD at §0 if higher; never renumber a live id.

---

## 0. Review disposition (all findings)

| Finding | Disposition |
|---|---|
| B1 label-map collision | Accepted. Struck the proposed-labels block and the conditional `VerdictChip` ALTER. Surface renders existing authored `approval_status` labels; "Cleared" not pursued (OPEN-CLR-6). V-e added. |
| B2 forward-target keys on court, not `blocking.state` | Accepted. DF-CLR-13 pinned to court-resolved routing (`isYourCourt`, `responsible_party == "authoriser"`, FE-11). V-a added; reason_code contingency noted. |
| N1 ceiling/STATE lag | Accepted. SV-6 corrected (live at least INV-85, D-76, FE-34); provisional IDs at INV-86.., D-77..; re-base at §0. |
| N2 SV-12 omits D-61/INV-74 | Accepted. Added to SV-12. |
| N3 nav precedent | Accepted. INV-91 and SV-9 retargeted to FE-24/INV-71/DF-F9-3; FE-13 cross-plane analogue only. |
| N4 blast-radius undercount | Accepted. Schema carries `awaiting_use_case_count` (parked) and `affected_use_case_count` (fan-out set); INV-87 reworded. |
| N5 em dashes | Accepted. Deliverable purged of em dashes. |
| N6 route naming | Noted. `/clearance-queue` follows the top-level `/portfolio` precedent; documented, not changed. |
| V-a..V-e | Folded into Appendix B and §0. |
| Clean items | No action. |

---

## 1. Problem

**1a. Clearance act has no UI.** Use cases linked to a catalogue product park at `vendor_check`, then `product_check`, with `blocking.responsible_party = authoriser` (DOMAIN §6). The blocking act is vendor/product clearance (`PUT /vendors/{id}/approval`, `PUT /products/{id}/approval`, `gov:authoriser`, Sprint 5, with same-request fan-out). That act has no tenant UI. The portfolio hub renders whose-court as text only (A1, read-only). The deployment-authorise act has a UI (`AuthorisePanel`, WI-4) but is gated to `pending_authorisation` (INV-30), a different gate. Custom/in-house systems (both catalogue FKs NULL) auto-pass the vendor/product gates and never appear here.

**1b. Tenant nav leaks an SoD-barred surface.** `TenantSidebar` wires Portfolio, Review queue, Evidence, and Audit flat, ungated. An `authoriser` sees Review queue, a reviewer-only surface; reviewer and authoriser are a hard SoD conflict (D-4, D-10). FE-8/UX-5 say a barred-act surface is not advertised. The tenant-plane gating mechanism exists (Members, FE-24/INV-71/DF-F9-3).

**1c. F2 your-court and posture read as unfinished.** In `dashboard/page.tsx`, your-court is a bare list that imports the kit but uses none of it; posture is a sentence plus a bare link. The fix applies the shipped kit within restraint (D-58, D-57), no new chroma (D-42), no percentage (INV-52), no coverage call (DF6-9). Em-dash separator corrected to a middot.

---

## 2. Resolved decisions

| ID | Decision | Source |
|---|---|---|
| DF-CLR-1 | Build the clearance act mechanism, not an authorise CTA. | DF-1 |
| DF-CLR-2 | Clearance surface and read endpoint ship in one sprint; ordering at implementor discretion. | DF-2 |
| DF-CLR-3 | Dedicated clearance queue is the backbone. Whose-court rows and the system drill-in deep-link into it. Fan-out blast radius shown before the act. | DF-3 |
| DF-CLR-4 | Portfolio hub stays read-only (A1). Whose-court gains navigation only. | DF-4 |
| DF-CLR-5 | Queue lists only entries currently awaiting clearance. Management of already-cleared records deferred (OPEN-CLR-1, confirmed). | DF-5 |
| DF-CLR-6 | `GET /clearance-queue` (NEW) is the single read home. Do not depend on `GET /systems/{id}/approval-status` (SV-2). | this doc |
| DF-CLR-7 | Queue is vendor-grouped with nested products; product control disabled-with-reason until parent vendor `APPROVED`. | APR-2, FE-8 |
| DF-CLR-8 | No optimistic concurrency (no `lock_version`, V-b): no `If-Match`, no 412; last-write-wins upsert; stale-queue 404 refetch. | PAT-6 n/a |
| DF-CLR-9 | Status renders through the existing `VerdictChip` label map (D-60/FE-16/INV-75). `approval_status` is fully keyed; render authored labels as-is, no map change (V-e). | B1 |
| DF-CLR-10 | Tenant-nav rule: hide a sidebar entry only when the caller is SoD-barred from that surface's purpose. Review queue iff `reviewer`; Clearances shows for all governance roles (read is `gov:ALL`; action gated inside the surface); Evidence, Audit, Portfolio unchanged. Backed by INV-91. | 1b, OPEN-CLR-3/5 |
| DF-CLR-11 | Nav changes are SoD-scoped. Evidence (no SoD constraint) and Audit (ungated, OPEN-CLR-5) unchanged; Portfolio global. | this doc |
| DF-CLR-12 | Fold the F2 your-court and posture visual re-treatment in (composition only, within D-58 restraint, no new hue, no %, no coverage call). Built to the rendered specimen. | 1c |
| DF-CLR-13 | The your-court forward affordance is court-resolved via `court.ts`/`isYourCourt` on `responsible_party == "authoriser"` (FE-11), never on `blocking.state` (rollup `GateResultRead.state` carries `use_case.state`, reads `held` under regression). Authoriser-court rows link to `/clearances`; reviewer-court and owner-court rows retain their current `/systems/{id}` destination. roleKey is a total discriminator today because `full_vector` emits `authoriser` only from the vendor and product gates (V-a); if a future gate emits `authoriser`, add a `reason_code` discriminator. | B2 |
| DF-CLR-14 | Include the posture lifecycle-state distribution strip (counts, no %, client-derived from loaded portfolio data, no new call). Minimal fallback retained; default include. | INV-52, DF6-9 |
| DF-CLR-15 | OPEN-CLR-1 confirmed: management of already-cleared records deferred. | chat |
| DF-CLR-16 | OPEN-CLR-2 confirmed: backend-unguarded status transitions accepted for MVP (the `PUT` is a status upsert with no from-state guard; OPEN-CLR-2). | chat |
| DF-CLR-17 | OPEN-CLR-3 confirmed: `GET /clearance-queue` is `gov:ALL` read; the set-clearance action is authoriser-only (server `PUT` stays `gov:authoriser`, INV-86); non-authoriser governance roles get the queue read-only; admin (zero governance roles) gets the empty-state with no queue call. The surface is an inspectable status list, not a worklist; copy and empty-states do not assume the reader is the authoriser. Your court stays strictly action-based and unchanged. | chat |
| DF-CLR-18 | OPEN-CLR-4 confirmed: status select is {UNDER_REVIEW, APPROVED, REJECTED}; NOT_STARTED and EXPIRED omitted (EXPIRED reserved for future auto-expiry). `valid_until` optional on APPROVED, client-side past-date guard, informational (gate reads status only, SV-14), prefilled today plus one year for both vendor and product approval (client-side opinionated default, UX-3; SV-15). | chat |
| DF-CLR-19 | OPEN-CLR-5 confirmed: Audit ungated this sprint; audience deferred to F6. | chat |
| DF-CLR-20 | OPEN-CLR-6 confirmed: render the existing shared `approved` label; no label-map change. | chat |

---

## 3. Scope

**In:**
- NEW surface `apps/tenant/app/clearances`, the clearance queue: read for every governance role, set-clearance action authoriser-only (DF-CLR-17).
- NEW backend read route `GET /v1/clearance-queue` (`gov:ALL`) plus `ClearanceQueueRead` schema.
- ALTER `dashboard/page.tsx` (`PortfolioHub`): your-court and posture visual re-treatment per the specimen; composition only; all F2 contracts preserved (SV-12).
- ALTER `system-detail-client.tsx`: whose-court navigation link on authoriser-court rows.
- ALTER `TenantSidebar`: Review queue gated to `reviewer`; NEW Clearances entry for all governance roles; Evidence/Audit/Portfolio unchanged (DF-CLR-10/11).
- Consumes unchanged: `PUT /vendors/{id}/approval`, `PUT /products/{id}/approval`, `GET /v1/me`, existing `VerdictChip` label map.

**Out:**
- Full diligence workflows (APR-6); product-approval rollup (APR-4).
- Management of already-cleared records (DF-CLR-15).
- Any dependence on `GET /systems/{id}/approval-status` (SV-2).
- Any change to the approval enum, tables, gate logic, fan-out, or the `VerdictChip` label map.
- Audit nav gating (DF-CLR-19); Evidence nav gating (no SoD constraint).
- Any new API call from the dashboard (DF6-9).
- Any `approval_status` label change (DF-CLR-20).

---

## 4. Backend delta (present-vs-ALTER)

| Item | State | Detail |
|---|---|---|
| `GET /v1/clearance-queue` | NEW | `gov:ALL` (DF-CLR-17). Recomputed live. Returns `ClearanceQueueRead`. Top-level path per the `/portfolio` precedent (N6). |
| `ClearanceQueueRead` schema | NEW | Vendor-grouped. See below. |
| `PUT /vendors/{id}/approval` | PRESENT | Unchanged. `gov:authoriser`. `VendorApprovalCreate {status, valid_until?, note?}`. Emits `vendor_approval.set|updated`. |
| `PUT /products/{id}/approval` | PRESENT | Unchanged. `gov:authoriser`. Same shape. Emits `product_approval.set|updated`. |
| `vendor_approval` / `product_approval` | PRESENT | Unchanged. No `lock_version` (V-b). |
| `approval_status` enum | PRESENT | Unchanged: NOT_STARTED, UNDER_REVIEW, APPROVED, REJECTED, EXPIRED (SV-1). |

**`ClearanceQueueRead` shape** (subject to §0 confirmation of the catalogue vendor↔product FK, V-c):

```
ClearanceQueueRead:
  vendors: list[VendorClearanceEntry]

VendorClearanceEntry:
  catalogue_vendor_id: UUID
  vendor_name: str
  status: ApprovalStatus            # NOT_STARTED if no VendorApproval row
  valid_until: datetime | None
  decided_by_name: str | None       # INV-34 membership join, D-25-guarded
  decided_at: datetime | None
  note: str | None
  awaiting_use_case_count: int      # parked at vendor_check; enqueue reason
  affected_use_case_count: int      # full fan-out set re-evaluated on commit (INV-87)
  affected_system_count: int
  products: list[ProductClearanceEntry]

ProductClearanceEntry:
  catalogue_product_id: UUID
  product_name: str
  status: ApprovalStatus
  valid_until / decided_by_name / decided_at / note
  vendor_cleared: bool              # parent vendor status == APPROVED
  awaiting_use_case_count: int      # parked at product_check
  affected_use_case_count: int
  affected_system_count: int
```

Both counts derive from the same `System.catalogue_vendor_id`/`catalogue_product_id` join `fan_out_*` uses, so preview and actual fan-out cannot diverge (V-c).

---

## 5. Frontend (present-vs-ALTER)

| Region | State | Detail |
|---|---|---|
| `apps/tenant/app/clearances` route plus `ClearanceQueue` | NEW | Born INV-69/INV-70 compliant. Read for every governance role; action authoriser-only. |
| `TenantSidebar` | ALTER | Review queue iff `reviewer`; NEW Clearances entry for all governance roles; Evidence/Audit/Portfolio unchanged. Gate off cached `useMe().governance_roles` (FE-24). |
| `dashboard/page.tsx` your-court | ALTER | Edge-barred rows (`WhoseCourtIndicator` "yours", D-46/D-57), `VerdictChip` blocking state (existing labels), middot separator, muted reason, trailing chevron, whole-row actionable; court-resolved forward target (DF-CLR-13). Preserves FE-11, INV-52, DF2-5, DF6-9, D-61/INV-74, face-order. Built to specimen. |
| `dashboard/page.tsx` posture | ALTER | `SectionGroup` panel: plain line, lifecycle-state distribution strip (counts, no %, client-derived, DF-CLR-14), audit link as a bordered affordance. No coverage call (DF6-9). Built to specimen. |
| `system-detail-client.tsx` | ALTER | Additive navigation link to `/clearances` on authoriser-court rows (`isYourCourt`). |

**Clearance surface role branch (`GET /v1/me` first):** any governance role issues `GET /clearance-queue` and gets the read-only queue (vendor-grouped, nested products, status `VerdictChip` via existing map, `awaiting`/`affected` counts, `decided_by`/`at`, `note`); `authoriser` additionally gets the set-clearance action per vendor and product row (product action disabled-with-reason until vendor `APPROVED`, INV-88); admin (zero governance roles) gets the empty-state with no queue call. The surface reads as an inspectable status list, not a worklist; copy and empty-states do not assume the reader is the authoriser (DF-CLR-17).

**Set-clearance action (authoriser only):** `status` `SingleSelect` over {UNDER_REVIEW, APPROVED, REJECTED} (DF-CLR-18); `valid_until` optional date, prefilled today plus one year on APPROVED, client-side past-date guard, labelled informational (SV-14/SV-15); `note` `FreeText`; a confirm step shows the fan-out preview (`affected_*` counts); submit `PUT` (no `If-Match`, DF-CLR-8); on success invalidate clearance-queue plus portfolio and refetch. Errors: 403 (should not render), 404 (stale, refetch). No 412; no 409 from-state guard (DF-CLR-16).

**Nav-gating defence in depth:** the sidebar gate is presentational; each surface's own empty-state and the server gate remain the authority (FE-8).

**Status copy:** authored `approval_status` labels from the existing map (DF-CLR-9/20, V-e). No surface-local status strings.

---

## 6. Invariants and decisions (proposed; provisional numbers above the reviewer-confirmed ceiling; re-base at §0)

Rules (INVARIANTS):
1. **INV-86 (CONVENTION)** Setting a vendor/product clearance is an authoriser-only act; the set-clearance control renders only for `authoriser`, absent otherwise. Reading the clearance list is not gated by this invariant (the read is `gov:ALL`, DF-CLR-17). Refs FE-8, D-4.
2. **INV-87 (CONVENTION)** The clearance surface shows the fan-out blast radius, the set of use cases re-evaluated on commit (not merely those parked), before the act commits. Clearance is vendor/product-scoped. Refs IXN-4, APR-2.
3. **INV-88 (CONVENTION)** A product's clearance control renders disabled-with-reason until its parent vendor is `APPROVED`. Refs APR-2, FE-8.
4. **INV-89 (CONVENTION)** The clearance surface is born INV-69/INV-70 compliant. Refs INV-68, INV-69, INV-70.
5. **INV-90 (CONVENTION)** The portfolio hub remains read-only; whose-court supplies navigation only. Refs A1, D-38, FE-11.
6. **INV-91 (CONVENTION)** A tenant sidebar entry is hidden only when the caller is barred from that surface's purpose by separation of duties. Review queue renders iff the caller holds `reviewer` (reviewer/authoriser hard conflict); Clearances renders for every governance role (reading the clearance status list breaches no SoD; the set-clearance action is gated inside, INV-86); Evidence, Audit, Portfolio are navigable by any governance role. Server gate and surface empty-state remain the authority. Refs FE-8, UX-5, D-4, D-10, FE-24, INV-71.

Rationale (DECISIONS):
- **D-77** Clearance is surfaced via a dedicated queue plus a single read endpoint (`GET /clearance-queue`, `gov:ALL` read, action authoriser-only), court-resolved routing, no dependence on `GET /systems/{id}/approval-status`. Rejected: embedding on the system drill-in (implies system-scope against the fan-out); deriving from the portfolio rollup (no vendor/product identity). Refs D-22, APR-2, INV-86..88.
- **D-78** Tenant-nav visibility rule (rationale for INV-91): a sidebar entry is navigation, not a worklist; hide it only when SoD bars the caller from the surface's purpose. Review queue is hidden from non-reviewers on SoD grounds; Clearances is a read-everywhere, act-restricted destination like Portfolio. Rejected: authoriser-only Clearances nav (treats navigation as a worklist); reading FE-8 as act-controls-only (leaves the Review-queue leak unspecified). Refs FE-8, UX-5, D-4, FE-24.

The F2 re-treatment (DF-CLR-12) mints no new invariant: composition fidelity under the already-cleared INV-69/INV-70 binding for F2; must not regress any F2 contract (SV-12).

---

## Appendix A. Forks (all confirmed; none open)

- OPEN-CLR-1 confirmed: management of already-cleared records deferred (DF-CLR-15).
- OPEN-CLR-2 confirmed: backend-unguarded status transitions accepted (DF-CLR-16).
- OPEN-CLR-3 confirmed: `gov:ALL` read, action authoriser-only, read-only queue for non-authorisers, admin empty-state (DF-CLR-17).
- OPEN-CLR-4 confirmed: status select {UNDER_REVIEW, APPROVED, REJECTED}; `valid_until` optional on APPROVED, past-date guard, informational, prefilled today plus one year for vendor and product (DF-CLR-18).
- OPEN-CLR-5 confirmed: Audit ungated this sprint (DF-CLR-19).
- OPEN-CLR-6 confirmed: render the existing shared `approved` label (DF-CLR-20).

---

## Appendix B. Source-verification register (run at §0, D-21)

- **SV-1** `approval_status` members (DATA-MODEL §2). Re-read live `pg_enum`.
- **SV-2** `GET /systems/{id}/approval-status` conflict (SPRINTS.md vs F1 STATE). Live read authoritative; do not depend on it (DF-CLR-6).
- **SV-6** Live ceiling at least INV-85, D-76, FE-34; STATE current-scope lags. Re-base every provisional ID above true HEAD.
- **SV-7** Whose-court link insertion points; `court.ts` `isYourCourt` reuse; no hub mutation (A1).
- **SV-8** No decision mandates a flat/global tenant nav.
- **SV-9** Sidebar reads `governance_roles` from cached `["me"]` (FE-24 pattern, no extra fetch).
- **SV-11** `vendor_check`/`product_check` verdict tone in the FE-16 tone map (specimen shows attention; confirm).
- **SV-12** F2 re-treatment preserves DF2-5, DF6-9, FE-11, INV-52, D-61/INV-74, and face-order, and stays INV-69/INV-70 (F2 CLEARED at UI-C1).
- **SV-14** The vendor/product gate reads `VendorApproval`/`ProductApproval.status` only, not `valid_until`, so `valid_until` is non-gating and informational (underwrites DF-CLR-18).
- **SV-15** The `valid_until` prefill (today plus one year) and past-date guard are client-side only; the `PUT` sends the resolved value; no backend default is introduced.
- **V-a (underpins B2)** `full_vector` emits `responsible_party == "authoriser"` only from `vendor_gate`/`product_gate` (`_VECTOR_STATES` stops at `TREATMENT_PENDING`; `pending_authorisation` is the auto-advance ceiling, no vector gate, INV-30). Pin by live read; if a future gate emits `authoriser`, add a `reason_code` discriminator.
- **V-b** No `lock_version` on the approval tables; live `PUT` routes accept no `If-Match` (DF-CLR-8).
- **V-c** Catalogue vendor↔product FK for nesting; RLS-bounding of affected-count queries; reuse the `fan_out_*` join so preview and actual fan-out cannot diverge.
- **V-d** Confirm the current your-court render omits `WhoseCourtIndicator`/`VerdictChip`/chevron and the posture region is thin, so the ALTER does not regress StatCard/DataTable chrome (UI-C1/UI-V2).
- **V-e (underpins B1)** Read the live authored `approval_status` labels; write copy against them.

---

## §0. Pre-flight verify checklist (implementor runs before building)

1. Re-confirm live canon ceiling; re-base all provisional IDs (INV-86..91, D-77..78, DF-CLR-*) above true HEAD; never renumber a live id (SV-6).
2. Re-read `approval_status` from live `pg_enum` (SV-1); read the authored labels (V-e).
3. Confirm `System.catalogue_vendor_id`/`catalogue_product_id` linkage (both nullable, SET NULL); custom systems both NULL (V-c).
4. Confirm `PUT /vendors|products/{id}/approval` shapes and that they accept no `If-Match` (V-b).
5. Confirm no `lock_version` on the approval tables (V-b).
6. Resolve the `approval-status` route conflict by live read; do not depend on it (SV-2).
7. Confirm `approval_status` is fully keyed in the `VerdictChip` label map; make no map change (DF-CLR-9/20, V-e).
8. Confirm the catalogue vendor↔product FK and reuse the `fan_out_*` join for both counts (V-c).
9. Confirm the tenant-plane nav pattern (FE-24/INV-71/DF-F9-3), no canon mandating flat nav (SV-8), sidebar reads `governance_roles` from cached `["me"]` (SV-9).
10. Confirm the vendor/product gate reads status only, not `valid_until` (SV-14).
11. Confirm `vendor_check`/`product_check` verdict tone (SV-11).
12. Confirm court-resolved routing keys on `responsible_party == "authoriser"`, and `full_vector` emits `authoriser` only from the vendor/product gates (V-a).
13. Confirm the F2 re-treatment preserves all F2 contracts (SV-12) and the posture strip is client-derived (V-d).

---

## Next steps (workflow)

The execution-only handoff (`HANDOFF_UI-F10-CLEARANCE.md`) is cut alongside this doc. It carries no rationale (it lives here), work items dependency-ordered with done-checks tied to concrete tests, ending in the canonical-update work item.