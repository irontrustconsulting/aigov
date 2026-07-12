# HANDOFF (execution-only) UI-F10-CLEARANCE

Rationale lives in `UI-F10-CLEARANCE.design.md`. This file is execution-only. Do not originate visual, layout, or UX decisions (INV-68/D-51); build to the design doc and the rendered your-court/posture specimen. If a visual choice seems needed that the design doc does not specify, stop and flag; do not improvise.

**Plane:** tenant · **Backend delta:** 1 NEW read route plus 1 NEW schema (additive; no table, no enum, no migration) · **Stable tier untouched:** no `approval_status` enum change, no `VerdictChip` label-map change · **Provisional IDs:** INV-86..91, D-77..78 minted above the reviewer-confirmed ceiling (INV-85, D-76, FE-34); re-base above true HEAD at WI-0; never renumber a live id.

---

## WI-0. Pre-flight verification (blocking gate; do before any code)

Run the design doc §0 checklist against the live repo/DB (D-21). Record results. Specifically confirm and note:

1. Live canon ceiling. Re-base INV-86..91, D-77..78, and the DF-CLR-* set above true HEAD. Never renumber a live id.
2. `approval_status` members = {NOT_STARTED, UNDER_REVIEW, APPROVED, REJECTED, EXPIRED} (live `pg_enum`).
3. `approval_status` is fully keyed in `verdict-label-map.ts`; read the authored labels. No map change.
4. `System.catalogue_vendor_id`/`catalogue_product_id` are the linkage columns (nullable, SET NULL); custom systems have both NULL.
5. `PUT /vendors|products/{id}/approval` shapes unchanged; no `lock_version` on the approval tables; routes accept no `If-Match`.
6. The vendor/product gate reads `status` only, not `valid_until` (live `lifecycle_gates.py`).
7. `full_vector` emits `responsible_party == "authoriser"` only from `vendor_gate`/`product_gate`.
8. `GET /systems/{id}/approval-status` existence by live read; do not depend on it either way.
9. `vendor_check`/`product_check` verdict tone in the FE-16 tone map.
10. Current your-court render omits `WhoseCourtIndicator`/`VerdictChip`/chevron; posture region is thin.

**Done-check:** every item above recorded with a live-source citation; provisional IDs re-based; any deviation from the design doc's assumptions raised before proceeding.

---

## WI-1. Backend: clearance-queue read endpoint plus schema (NEW)

Dependency: WI-0.

- NEW schema in `app/schemas/lifecycle.py`: `ClearanceQueueRead`, `VendorClearanceEntry`, `ProductClearanceEntry` per design doc §4 (fields: status, valid_until, decided_by_name, decided_at, note, awaiting_use_case_count, affected_use_case_count, affected_system_count, products[]; product carries vendor_cleared).
- NEW service `clearance_queue(ctx, db)` in `app/services/lifecycle_service.py`:
  - Enumerate catalogue vendors and products linked to the tenant's systems (`System.catalogue_vendor_id`/`catalogue_product_id`), RLS tenant-bounded.
  - Group products under their vendor.
  - Left-join `VendorApproval`/`ProductApproval`; default `status = NOT_STARTED` when no row.
  - `awaiting_use_case_count`: use cases parked at `vendor_check` (vendor) / `product_check` (product).
  - `affected_use_case_count` and `affected_system_count`: the full fan-out set, using the same `catalogue_vendor_id`/`catalogue_product_id` join `fan_out_vendor_approval`/`fan_out_product_approval` use.
  - `decided_by_name`: INV-34 membership join (D-25-guarded).
  - `vendor_cleared`: parent vendor status == `APPROVED`.
  - Include vendor entries with any `awaiting` use case; include products of an in-queue vendor (inert until vendor_cleared) and products with their own `awaiting` use cases.
- NEW route in `app/routers/v1/lifecycle.py`: `GET /clearance-queue`, gate `require_governance_role(*_ALL_GOVERNANCE_ROLES)`, response `ClearanceQueueRead`. Top-level path (sibling of `/portfolio`).

**Done-check (tests, `app/tests`):**
- Vendor with a use case parked at `vendor_check` and no approval row appears with `status = NOT_STARTED` and `awaiting_use_case_count >= 1`.
- `affected_use_case_count` counts all use cases on the vendor's systems, and exceeds `awaiting_use_case_count` when some use cases on those systems are not parked at the gate.
- Product `vendor_cleared` is true iff the parent vendor is `APPROVED`.
- Each of the five governance roles receives 200; admin (zero governance roles) receives 403.
- Counts are RLS tenant-bounded (a second tenant's systems never appear).
- `GET /clearance-queue` added to the API-ROUTES table (gate `gov:ALL`).

---

## WI-2. api-client plus hooks (NEW/ALTER)

Dependency: WI-1.

- Extend the generated api-client with `GET /v1/clearance-queue` and the `ClearanceQueueRead` types.
- NEW hook `useClearanceQueue()` (enabled only when the caller holds at least one governance role).
- Mutation hooks for the existing PUTs (`useSetVendorApproval(vendorId)`, `useSetProductApproval(productId)`) if not already present; on success invalidate `["clearance-queue"]` and `["portfolio"]`.

**Done-check:** type-check passes; `useClearanceQueue` issues `GET /clearance-queue` only for governance-role callers; mutation hooks target the existing `PUT` routes and invalidate both query keys.

---

## WI-3. Clearance surface (NEW)

Dependency: WI-1, WI-2. Build to the design doc §5 and the specimen. Born INV-69/INV-70 compliant (`PageScaffold`/`PageHeader`, C0 kit, `Skeleton`/`ErrorState`/`EmptyState`).

- NEW route `apps/tenant/app/clearances` plus `ClearanceQueue` client.
- Role branch (`GET /v1/me` first): admin (zero governance roles) renders `EmptyState`, no queue call; any governance role renders the read-only queue; `authoriser` additionally renders the set-clearance action.
- Read view: vendor-grouped, nested products; per entry render name, status `VerdictChip` (authored labels from the existing map, no local strings), `awaiting`/`affected` counts, `decided_by_name`/`decided_at`, `note`.
- Set-clearance action (authoriser only): per vendor and product row; product action disabled-with-reason until `vendor_cleared` (INV-88). Form: `status` `SingleSelect` over {UNDER_REVIEW, APPROVED, REJECTED}; `valid_until` optional date, prefilled today plus one year when status is APPROVED, client-side past-date guard, labelled informational; `note` `FreeText`. Confirm step shows the fan-out preview (the `affected_*` counts). Submit `PUT` (no `If-Match`); on success invalidate clearance-queue plus portfolio and refetch. Handle 403 and 404 (404 refetches).
- Copy: the surface is an inspectable status list, not a worklist; empty-states and headings do not assume the reader is the authoriser.

**Done-check (RTL tests):**
- Admin: `EmptyState`, no `GET /clearance-queue` call.
- Auditor, reviewer, and system_owner: read-only queue renders, no set-clearance control present.
- Authoriser: set-clearance control present.
- Product action disabled-with-reason when parent vendor is not `APPROVED`.
- Status chip renders the authored `approval_status` label.
- `status` select offers exactly {UNDER_REVIEW, APPROVED, REJECTED}.
- Selecting APPROVED prefills `valid_until` to today plus one year; a past date is rejected client-side.
- Confirm step displays `affected_use_case_count`.
- Successful submit invalidates `["clearance-queue"]` and `["portfolio"]`.

---

## WI-4. TenantSidebar nav gating (ALTER)

Dependency: WI-3 (route exists).

- ALTER `apps/tenant/app/_components/tenant-sidebar.tsx`: gate the Review queue entry to callers holding `reviewer`; add a Clearances entry rendered for every caller holding at least one governance role; leave Evidence, Audit, and Portfolio unchanged. Gate off cached `["me"].governance_roles` (FE-24 pattern).

**Done-check (tests):**
- Authoriser: no Review queue entry; Clearances entry present.
- Reviewer: Review queue present; Clearances present.
- System_owner: no Review queue; Clearances present.
- Auditor: no Review queue; Clearances present.
- Admin (zero governance roles): neither Review queue nor Clearances (existing admin behaviour); Portfolio always present.

---

## WI-5. Dashboard your-court re-treatment (ALTER)

Dependency: WI-3 (route exists). Build to the specimen.

- ALTER the your-court section in `apps/tenant/app/dashboard/page.tsx`: edge-barred rows in a raised card (`WhoseCourtIndicator` "yours"), `VerdictChip` for the blocking state (existing labels), middot separator (remove the em-dash), muted reason subtext, trailing chevron, whole-row actionable.
- Forward target court-resolved via `court.ts`/`isYourCourt` on `responsible_party == "authoriser"`: authoriser-court rows link to `/clearances`; all other courts retain the current `/systems/{id}` destination. Do not key on `blocking.state`.

**Done-check (tests):**
- An authoriser-court row links to `/clearances`.
- A reviewer-court and an owner-court row retain `/systems/{id}`.
- No em-dash in the your-court DOM.
- `VerdictChip` present per row; no `%` anywhere in the dashboard (INV-52).
- Face-order preserved (adoption leads with your-court, assurance with posture).
- The zero-systems scaffolded-empty branch (D-61/INV-74) is unchanged.

---

## WI-6. Dashboard posture re-treatment (ALTER)

Dependency: WI-5 (same file; sequence to avoid churn). Build to the specimen.

- ALTER the posture section in `dashboard/page.tsx`: `SectionGroup` panel with the plain line, a lifecycle-state distribution strip (counts, no percentage, derived client-side from `portfolio.data[].use_cases[].state`), and the audit link promoted to a bordered affordance. No new API call.

**Done-check (tests):**
- No `/coverage` or `/export` call issued from the dashboard (DF6-9).
- No `%` in the posture region (INV-52).
- Distribution counts equal the client-side tally of `use_cases[].state`.
- Audit affordance present and links to `/audit`.

---

## WI-7. system-detail-client deep-link (ALTER)

Dependency: WI-3 (route exists).

- ALTER `system-detail-client.tsx`: add an additive navigation link to `/clearances` on authoriser-court use-case rows (`isYourCourt`); other courts unchanged.

**Done-check (test):** an authoriser-court use-case row links to `/clearances`; non-authoriser courts retain their current destination.

---

## WI-8. Canonical update (MUST be the last work item)

Dependency: WI-1 through WI-7 green.

- Update STATE: add the `UI-F10-CLEARANCE` surface section (new `clearances` surface, `GET /clearance-queue` consumed route, nav gating, dashboard your-court/posture re-treatment); record the clearance surface as born INV-69/INV-70 compliant in the composition-debt register (no row owed); record the deferred items (already-cleared management, EXPIRED auto-expiry, `valid_until` enforcement) in the deferred register.
- Update DATA-MODEL route inventory: add `GET /clearance-queue` (`gov:ALL`).
- Update API-ROUTES: add the `GET /clearance-queue` row.
- Append INVARIANTS: INV-86..91 (re-based above the live ceiling).
- Append DECISIONS: D-77, D-78, and the sprint-local DF-CLR-1..20.
- Do not renumber any live INV-n. Do not touch the stable tier: no `approval_status` enum change, no `VerdictChip` label-map change.

**Done-check:** canon files updated; ID ceilings advanced with no renumber of any existing id (grep the prior ceiling values to confirm they are unchanged); STATE deferred and composition-debt registers reflect this sprint; a full test run is green.