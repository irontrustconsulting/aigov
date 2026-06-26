# UI-C2-INTAKE-CATALOGUE — Final Design Doc

**Status:** FINAL (v2 review folded) · tenant plane, surface `apps/tenant/app/systems/new` + two kit/shell lifts · larger than a composition pass (intake IA rewrite + FE-25 + FE-4/5/21/23 `[ALTER]`s + additive `logo_url` field & service edit + seed population) · clears F1 composition-debt row + resolves OPEN-C1; burns the audit's Lift A and Lift B · ids above ceilings (FE-25; FE-4/5/21/23 `[ALTER]`; D-55/56; INV-72/73; DF-C2-1..8) confirmed against INV-71/D-54/FE-24 · companion: `UI-C2-INTAKE-CATALOGUE-handoff.md`.

**Binding visual spec:** the four specimens in the design thread — (1) in-place single-open accordion drill-down, (2) FE-4 input-family redesign, (3) drill rung with `LogoTile` logo/monogram + in-house exit + skeleton, (4) empty + error faces.

**v2 review disposition:** both blockers accepted — **B-v2-1** FE-8 removed from Lift A; **B-v2-2** single-line `TextInput` primitive added to FE-4. NB-v2-1..4 and SV-v2-1..4 folded. Mapping in Appendix C.

---

## §0 — Pre-flight verify checklist (binding; live reads before any code; D-21)

| id | Verify (live) | Gates |
|---|---|---|
| **V-0 (canary)** | STATE's `Current through:` line lags (reads UI-C1; body shows UI-F9-MEMBERS shipped). Confirm F9 is true HEAD and nothing landed since touching `systems/new`, FE-4/5, or `ListSelectRow`. | Binds the design to the real baseline (D-21 lag rule). |
| V-1 | `catalogue_vendor.logo_url` / `catalogue_product.logo_url` present in **live DDL** (not only the ORM model) **and** their population counts. **The whole "no migration" premise rests on the live column; the visual win rests on population.** | D2/D1; monogram prevalence. |
| V-2 | `product_category` depth (`parent_id`) + membership attach level. | Accordion leaf-detection recursion + non-leaf-membership branch. |
| V-3 | `ListSelectRow` full content contract (leading slot, label mechanism, chevron) **and an enumeration of its live consumers**. | FE-23 `[ALTER]` sizing; if zero consumers, the ALTER is purely additive and the accordion is its first consumer. |
| V-4 | `get_product_detail` constructor + `ProductDetailOut`/`CatalogueVendorRef` defs. Confirm hand-built and the `vendor=... if vendor else None` against the **required** `vendor` field. | D2 (field alone no-ops; typing direction below). |
| V-5 | **Confirmed-in-code:** `VendorRead`/`ProductRead` declare `logo_url: str \| None = None`. Cheap re-confirm only. | rung render. |
| V-6 | Vendors-per-sub-category distribution. | accordion vendor-level insertion (D-56). |
| V-7 | `systems/new/page.tsx` `system_owner` gate unchanged. | preserve exactly. |
| SV-A1 | FE-4 (`SingleSelect`/`MultiSelectInput`/`FreeText`) + `PrefillWithBasis` source in `packages/ui`. **Pre-stated resolution: design, not build-defect** — the `@source` fix (INV-67/D-49) already ships, so classes generate; the remaining bareness is authored-bare, i.e. genuine INV-68 design. Run to confirm. | Confirms Lift A is designed-here work. |
| SV-B1 | `PageHeader` source + breadcrumb/step-slot usage. Confirm no back affordance + underuse. | Lift B `[ALTER]` shape. |
| SV-C1 | INV-70 state coverage on the Lift-A regression set (F3 `resolved-tier`/`context-gate` forms, F7/F8/F9 forms) — and confirm `IntakeCaptureStep` has **no** vocab loading/error today (NB-v2-2). | Regression done-checks; the add-not-swap state work. |

Divergence on any read stops the sprint and escalates.

---

## Scope

In: the whole `apps/tenant/app/systems/new` surface re-grounded, drill-down rebuilt as an **in-place single-open accordion**; **Lift A** (FE-4 input set incl. a new single-line `TextInput`, + FE-5 layout); **Lift B** (FE-21 back/up); `LogoTile` (FE-25) + `logo_url` plumbing (D2) + seed population (D1).

Lift boundary: A and B are kit/shell; consumers (F3/F7/F8/F9 forms; drill-ins) **inherit** the improvement. They are **not** per-surface composition passes — each of F2–F8 still owes its own (audit C3–C6), out of C2. Lift A/B done-checks are *regression* checks on consumers, not full-composition checks.

Out: per-surface composition of F2–F8; **FE-8/`SodAction`** layout (B-v2-1 — behavioral wrapper, not a bare input; its caption is already styled and its wrapped FE-4 children improve via Lift A; any wrapper composition belongs to the F3/F4 passes where its consumers live); wizard logic, role branch, lifecycle/classification flow, `is_custom` XOR guard, `DrillDownResult` (NB7); the pre-auth marketing funnel. `DF1-3/4/5/8/9` preserved verbatim.

---

## Resolved decisions

| # | Decision | Annotation | Rationale / rejected |
|---|---|---|---|
| D-56 | **Drill-down is an in-place, single-open accordion.** Chosen category expands on the same page to reveal sub-categories; expanding one branch row collapses its branch siblings; selection nests further (sub-category → [vendor level iff >1 vendor] → product); collapse is back. Funnel logic unchanged. **Mixed-node rule (NB-v2-3):** on a non-leaf category that also carries direct product memberships, single-open collapse applies **only among branch siblings**; leaf product rows stay visible within the parent panel. | `[NEW]` (supersedes v1 full-panel rungs) | v1 panel-replacement read as a new screen and lost context; single-open keeps context and fixes "too busy." **Rejected: full-panel sequential rungs**; **rejected: miller columns** (weaker on the adoption face; less aligned with "open up the chosen category"). |
| FE-4 | **`[ALTER]` — input-family visual treatment (Lift A), now including a new single-line `TextInput` primitive.** `TextInput` (single-line; the set had none — `FreeText` is a textarea) for fields like system name; `SingleSelect` real select chrome; `MultiSelectInput` spaced wrapping toggle-chip cluster; `FreeText` proper labelled textarea with the last-resort hint. | `[ALTER]` (kit) | **B-v2-2:** the system-name field is a raw `<input>` today; without a `TextInput` primitive Lift A leaves the surface's first field bare. Closes FE-4's deferred "specify per surface" clause at kit level. **Rejected: per-surface raw-input restyle** (bespoke, INV-69-adjacent); **leaving bare.** |
| FE-5 | **`[ALTER]` — `PrefillWithBasis` layout pass** (v0/v1 touched only its override button). | `[ALTER]` (kit) | Same bare-layout debt; FE-5 is the prefill-confirm rung of the input order. |
| FE-21 | **`[ALTER]` — back/up affordance (Lift B)** in `PageHeader`, populated by every multi-step and drill-in surface. | `[ALTER]` (shell) | No in-app back today; intake's collapse-as-back is the local instance. |
| FE-23 | **`[ALTER]` — `ListSelectRow`**: optional `leading` slot (LogoTile), confirmed label mechanism, and an **additive** branch/disclosure mode — `expanded`/`children`/`onToggle` all optional, **leaf mode the default**, so the shipped shape is preserved for any consumer (NB-v2-1). Single-open state lives in `DrillDownStep`. | `[ALTER]` (additive; sized by V-3) | Keeps the accordion kit-composed, not a one-off (INV-69). |
| FE-25 | **`LogoTile`** — square tile (40px; `size?`), `src` (`logo_url`) else a 1–2 initial monogram on the neutral ramp; neutral chrome only. | `[NEW]` | Reused on vendor + product rows + confirm step → kit primitive (INV-69). |
| INV-72 | Visual-identification chrome (`LogoTile` + monogram) is semantically neutral; never `--verdict-*`/`--tier-*`/`--prov-*`/`--sev-*`. | `[NEW]` | Channel orthogonality (FE-16 family). |
| INV-73 | Form-control selection/active affordances are semantically neutral (neutral or brand-selection), never a semantic channel. | `[NEW]` | Lift A's toggle-chip selected state and `TextInput` active state must not borrow a semantic channel. |
| D-55 | Logo sourcing = curated `logo_url` assets from a controlled origin + monogram fallback; no third-party favicon service (privacy, low-res, runtime dep), no hotlinking (trademark/reliability). | `[NEW]` | Catalogue is curated reference data (INV-48). (NB1: privacy argument stands alone; no INV-50 cite.) |
| D2 | Additive `logo_url: str \| None = None` on `ProductDetailOut` **and** `CatalogueVendorRef`; edit `get_product_detail` to source `product.logo_url`/`vendor.logo_url`; **typing direction (NB-v2-4): keep `vendor: CatalogueVendorRef` required and drop the dead `if vendor else None`** — `catalogue_product.vendor_id` is `NOT NULL`, so vendor is always present and the defensive branch is dead code. | `[ALTER]` schema-response + service code (no migration) | **B1:** hand-built schemas; field alone no-ops. **NB2:** `CatalogueVendorRef` shared with `SystemDetail.catalogue_vendor`; `= None` keeps it harmless there. |
| D1 | Seed `logo_url` population (vendors + products) + assets from a controlled origin. | `[NEW]` data delta (no schema) | Render quality bounded by populated data; scope from V-1. |

---

## Drill-down — in-place accordion

Single-open, nesting in place, collapse = back (per the rendered specimen). Branch rows (category / sub-category / vendor) use the FE-23 branch mode; leaf rows (product) use `ListSelectRow` + `LogoTile`. Category branch rows carry no tile (DF-C2-2). Vendor level inserted only when a sub-category has >1 vendor (D-56); single-vendor sub-category expands straight to products. Leaf-detection termination (children empty from `?parent_id`); non-leaf-membership branch per V-2, governed by the mixed-node rule in D-56. Lazy fetch on expand via the existing `anon` routes — no route delta. `DrillDownResult` unchanged; vendor level navigation-only; reducer paths untouched (DF-C2-5).

## Four INV-70 states

Per the specimens: `Skeleton` (loading), `ErrorState` retryable (error), `EmptyState` with in-house exit as action (empty); first-run degenerate on global-reference rungs (DF-C2-3).

## Per-step composition plan

All steps → `PageScaffold` + `PageHeader` (with FE-21 back where multi-step), and consume the styled FE-4/5 family from Lift A. `IntakeCaptureStep`: system-name field swaps the raw `<input>` for the new `TextInput` (B-v2-2); and per NB-v2-2 the six vocab queries get an **added** aggregate step-level loading/error gate (they have none today — this is the INV-70 half that clears the F1 debt row, an add not a swap). `PrefillStep` keeps `DF1-8` on the styled `PrefillWithBasis`. Classification/lifecycle steps re-ground; `NeedsSystemOwner`/`AssuranceReadOnly` as `EmptyState`/`FirstRunPanel` faces. `page.tsx` role guard + `me` states to kit (V-7 preserved).

---

## New invariants

**INV-72** · CONVENTION · Visual-identification chrome (`LogoTile` + monogram) is semantically neutral. ↳ refs FE-25, FE-16, FE-24, INV-64.
**INV-73** · CONVENTION · Form-control selection/active affordances are semantically neutral (neutral or brand-selection), never a `--verdict-*`/`--tier-*`/`--prov-*`/`--sev-*` channel. ↳ refs FE-4, FE-16, INV-72.

## Sprint-local decisions (DF-C2-n)

- **DF-C2-1** single `is_custom` exit, drops catalogue fields structurally (`ck_system_custom_no_catalogue`).
- **DF-C2-2** category branch rows carry no `LogoTile`.
- **DF-C2-3** INV-70 first-run degenerate on global-reference rungs.
- **DF-C2-4** `logo_url` on `ProductDetailOut` is display-only (`DF1-8`).
- **DF-C2-5** `DrillDownResult` + reducer paths unchanged; vendor level navigation-only (NB7).
- **DF-C2-6** drill-down is single-open; collapse is back.
- **DF-C2-7** Lift A and Lift B are kit/shell; consumers inherit; per-surface composition (C3–C6) is separate and out of C2.
- **DF-C2-8** the accordion composes from `ListSelectRow` branch-mode (FE-23 `[ALTER]`), not a one-off (INV-69); mixed-node collapse applies among branch siblings only, leaf rows persist in the parent panel (NB-v2-3).

## Resolved opens

- **OPEN-C1** — `DrillDownStep` re-ground: resolved (now the accordion). F1 composition-debt row cleared on close.

---

## Appendix A — Open decisions

- **A1 — DROPPED (B2).** OPEN-4 reframe is not part of C2; its own DECISION, reconciled against the wizard gate.
- **A2 — Logo asset hosting:** static app assets vs controlled bucket vs CDN URL. Recommend static/controlled-bucket (same-origin, no third-party leak). Set at handoff.
- **A6 — Branch-row primitive:** FE-23 `ListSelectRow` branch-mode (recommended) vs standalone `DisclosureRow`. Recommend branch-mode — no other surface needs a tree.
- **A7 — RESOLVED:** Lift A folded into C2, founder-confirmed.

## Appendix B — Source-verification register

V-0 canary, V-1 (live DDL + population), V-2, V-3 (+ consumer enumeration), V-4, V-5 (confirmed-in-code), V-6, V-7, SV-A1 (pre-stated: design), SV-B1, SV-C1. INV-64 confirmed as the `--tier-*`/`TierBadge` magnitude invariant.

## Appendix C — Review disposition

**v1 folds retained:** B1 (D2 constructor edit), B2 (drop OPEN-4 reframe), NB1 (INV-50 cite struck), NB2 (`CatalogueVendorRef` `= None`), NB3 (FE-23 leading+label), NB4 (leaf-detection + non-leaf branch), NB5 (specimens), NB6 (STATE header → F9 + C2), NB7 (`DrillDownResult`).

**v2 folds:**
| Finding | Disposition |
|---|---|
| **B-v2-1** FE-8 mis-scoped | **Accepted.** FE-8 removed from Lift A; caption already styled, wrapped FE-4 children improve via Lift A, wrapper composition deferred to F3/F4 passes. |
| **B-v2-2** bare single-line input | **Accepted.** New single-line `TextInput` primitive added to FE-4 `[ALTER]`; `IntakeCaptureStep` adopts it for system name. |
| **NB-v2-1** FE-23 ALTER regression set | **Folded.** ALTER stated additive (optional `expanded`/`children`/`onToggle`, leaf default); V-3 enumerates consumers. |
| **NB-v2-2** capture-step INV-70 is add not swap | **Folded.** Aggregate vocab loading/error gate added; SV-C1 confirms none today. |
| **NB-v2-3** mixed-node interaction | **Folded** into D-56 / DF-C2-8. |
| **NB-v2-4** D2 typing direction | **Folded.** Keep `vendor` required; drop dead `if vendor else None` (vendor_id NOT NULL). |
| **SV-v2-1** HEAD canary | **Folded** as V-0. |
| **SV-v2-2** V-5 in-code; V-1 live DDL | **Folded.** V-5 → confirmed-in-code; V-1 → live DDL + population. |
| **SV-v2-3** SV-A1 pre-state | **Folded.** SV-A1 pre-stated as design (run to confirm). |
| **SV-v2-4** consumer enum into V-3 | **Folded.** |
| Clean items | No action. |

---

## Canon-update note (for the handoff)

STATE: clear F1 row; bump `Current through:` to **UI-F9-MEMBERS and UI-C2**; record UI-C2; record the new **Lift-A primitive-styling** and **Lift-B navigation** debt registers (audit) with burn-down status. DATA-MODEL: additive `logo_url` on `ProductDetailOut`; seed population. Append INV-72, INV-73; D-55, D-56; FE-25; FE-4/FE-5/FE-21/FE-23 `[ALTER]`s (**not FE-8**); DF-C2-1..8. Resolve OPEN-C1. **Do not touch OPEN-4.** Never renumber a live id; stable tier untouched.