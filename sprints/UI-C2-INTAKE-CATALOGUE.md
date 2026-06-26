# UI-C2-INTAKE-CATALOGUE — Sprint Handoff (execution-only)

Rationale lives in `UI-C2-INTAKE-CATALOGUE-design.md`. Execution-only. Build to the four specimens in the design thread (in-place accordion; FE-4 input redesign; drill rung + LogoTile + skeleton; empty + error faces). Do not originate visual/layout/composition design (INV-68/D-51) — flag and stop on any gap not covered here. **FE-8/`SodAction` is explicitly NOT in scope** (it is a behavioral wrapper, not a bare input).

## Binding pre-flight (do first; record each; divergence → stop + escalate)

- **P-0 (canary)** STATE `Current through:` lags (reads UI-C1; body shows F9 shipped). Confirm UI-F9-MEMBERS is true HEAD and nothing landed since touching `systems/new`, FE-4/5, or `ListSelectRow`.
- **P-1** Live **DDL** read: `logo_url` column exists on `catalogue_vendor` and `catalogue_product` (not just the ORM). Then `count(*) FILTER (WHERE logo_url IS NOT NULL), count(*)` on each. Sets WI-7 scope; the "no migration" premise rests on the live column.
- **P-2** `product_category` `parent_id` depth + which level `product_category_membership` attaches; record any product on a non-leaf category. Sets WI-8 recursion + mixed-node branch.
- **P-3** `ListSelectRow` source: leading-slot + label mechanism + chevron, **and enumerate live consumers**. If zero, the branch-mode ALTER is purely additive.
- **P-4** `get_product_detail` constructor + `ProductDetailOut`/`CatalogueVendorRef` defs; confirm `vendor` is required and the `if vendor else None` is dead (vendor_id NOT NULL).
- **P-5** Confirm-in-code: `VendorRead`/`ProductRead` carry `logo_url` (cheap).
- **P-6** Vendor-per-sub-category distribution has both 1 and >1 cases.
- **P-7** `systems/new/page.tsx` `system_owner` gate unchanged.
- **P-8** FE-4 (`SingleSelect`/`MultiSelectInput`/`FreeText`) + `PrefillWithBasis` source — confirm authored-bare (classes generate post-INV-67, so this is design work). Confirm `IntakeCaptureStep` uses a raw `<input>` for system name and has no vocab loading/error today.
- **P-9** `PageHeader` source + breadcrumb/step-slot usage — confirm no back affordance.

## Work items (dependency-ordered)

### WI-1 · Lift A — input-family kit visual pass (FE-4 + FE-5)
- FE-4 `[ALTER]`: add a single-line **`TextInput`** primitive; style `SingleSelect` (select chrome), `MultiSelectInput` (spaced wrapping toggle-chip cluster per specimen), `FreeText` (labelled textarea + last-resort hint). Selected/active states use a neutral or brand-selection token, never a semantic channel (INV-73).
- FE-5 `[ALTER]`: `PrefillWithBasis` full layout pass.
- **Not FE-8.**
- **Done-check:** `TextInput` built + tested; the four primitives match the specimen; `no-literal-token-value` lint (INV-63) + axe zero violations; **regression:** F3 `resolved-tier`/`context-gate` forms, F7/F8 forms, F9 dialogs render correctly with no layout break (SV-C1 set). `packages/ui` suite green.

### WI-2 · Lift B — `PageHeader` back/up affordance (FE-21 `[ALTER]`)
- Add an optional back/up control to `PageHeader`; wire it on at least one multi-step/drill-in surface as the reference consumer.
- **Done-check:** affordance renders + navigates; existing `PageHeader` consumers unaffected (additive prop).

### WI-3 · FE-23 `[ALTER]` — `ListSelectRow` (additive)
- Optional `leading` slot (LogoTile), confirmed label mechanism, and branch mode (`expanded`/`children`/`onToggle` optional; **leaf default**).
- **Done-check:** existing consumers (per P-3) unaffected; leaf-mode shape unchanged; branch-mode tests cover expand/collapse + children render.

### WI-4 · FE-25 `LogoTile`
- `src?`, `name`, `size?` (40px default); renders `src` else monogram on neutral ramp; `alt`/`aria` from `name`.
- **Done-check:** logo-present + monogram-fallback tests; lint/axe green.

### WI-5 · D2 — confirm-step logo plumbing
- Add `logo_url: str | None = None` to `ProductDetailOut` + `CatalogueVendorRef`. Edit `get_product_detail` to source `product.logo_url`/`vendor.logo_url`. Keep `vendor: CatalogueVendorRef` required; **delete the dead `if vendor else None`**.
- **Done-check:** `get_product_detail` returns `logo_url`; `SystemDetail` path unchanged (`= None`); existing reference + system tests green; no migration in the diff.

### WI-6 · D1 — seed `logo_url` + assets (scope from P-1)
- Populate `logo_url` for the curated catalogue (vendors + products); add assets at the controlled origin (A2).
- **Done-check:** P-1 re-read shows curated rows non-NULL; each resolves to a served asset; uncurated rows NULL (monogram path).

### WI-7 · `DrillDownStep` — in-place accordion (depends on WI-3, WI-4, P-2, P-6)
- Single-open accordion: branch rows (category/sub-category/vendor) via FE-23 branch mode; leaf rows (product) via `ListSelectRow` + `LogoTile`; category rows no tile.
- Vendor level only when >1 vendor (auto-skip to products on single vendor). Leaf-detection termination. Mixed-node (non-leaf with direct memberships, per P-2): branch-sibling collapse only, leaf rows persist in the parent panel.
- Four INV-70 states to spec; in-house exit at any level. `DrillDownResult` `{isCustom, catalogueProductId, catalogueProductName}` unchanged; vendor level navigation-only; reducer paths untouched.
- **Done-check:** funnel incl. single-vendor auto-skip; single-open collapse among branch siblings; all four states; in-house exit → `{isCustom:true, catalogueProductId:null}`; catalogue product → `{isCustom:false, catalogueProductId:<id>}`; `DrillDownResult` shape unchanged; `apps/tenant/lib/intake/__tests__` green.

### WI-8 · Remaining `systems/new` steps re-ground (depends on WI-1, WI-2, WI-3)
- All steps → `PageScaffold` + `PageHeader` (back where multi-step); consume the styled FE-4/5 family.
- `IntakeCaptureStep`: system-name → new `TextInput`; **add** an aggregate step-level loading/error gate over the six vocab queries (none today — INV-70 add, not swap).
- `PrefillStep` keeps `DF1-8` on styled `PrefillWithBasis`. `page.tsx` guard + `me` states to kit (P-7 preserved). Classification/lifecycle steps re-ground; `NeedsSystemOwner`/`AssuranceReadOnly` as `EmptyState`/`FirstRunPanel`.
- **Done-check:** no `mx-auto max-w-4xl` or bespoke `<p>Loading…</p>`/`<p role="alert">` left in `systems/new`; capture step shows skeleton/error while vocab loads; role branch + all DF1 semantics covered by existing tests; `pnpm --filter tenant test` green.

### WI-9 · Confirm step tiles (depends on WI-4, WI-5)
- Product + vendor `LogoTile` from `logo_url`; monogram fallback.
- **Done-check:** tiles light when seeded, monogram otherwise; names unchanged.

### WI-10 · Canonical update (last)
- **STATE:** clear the F1 composition-debt row; bump `Current through:` to **UI-F9-MEMBERS and UI-C2**; add the UI-C2 capability entry; record the new **Lift-A primitive-styling debt** and **Lift-B navigation debt** registers (from the triage audit) with burn-down status.
- **DATA-MODEL:** additive `logo_url` on `ProductDetailOut`/`CatalogueVendorRef` (response shape, no DDL); seed `logo_url` population.
- **Append:** INV-72, INV-73; D-55, D-56; FE-25; FE-4/FE-5/FE-21/FE-23 `[ALTER]`s (**not FE-8**); DF-C2-1..8. Resolve OPEN-C1.
- **Do not touch OPEN-4.**
- Never renumber a live id; leave the stable tier untouched.
- **Done-check:** ids appended above ceilings (FE-24/D-54/INV-71); `Current through:` reflects F9 + C2; OPEN-C1 resolved; OPEN-4 unchanged; no live id renumbered.