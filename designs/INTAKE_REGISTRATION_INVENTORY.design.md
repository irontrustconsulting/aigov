# Intake, Registration & Inventory — Design Direction (ratified)

**Status:** DESIGN DIRECTION · v5, ratified (v4 review folded; no blocking findings) · OPEN-INTAKE-A/B/C/D ruled; OPEN-INTAKE-E (inventory identity) flagged minor · carries domain and backend deltas · no IDs minted (candidates in §10) · live mint floors D ≥ 62, INV ≥ 75, FE ≥ 27 (each sprint §0 re-confirms HEAD, D-21) · decomposes per §9.

**v5 changes over v4:** two premise corrections from review, both leaving the decision intact. The §1.3 relocation is recorded as **context fidelity, not classifier wiring** (the tier already resolves per use case without these fields). The §4.4 detail page is recorded as **the existing F6 audit-pack surface gaining an inline per-system record** (pure frontend, no backend delta), with the hashed pack staying on-demand under INV-53. OPEN-INTAKE-E is narrowed to the inventory section, not the whole hub; the vestigial zero-use-case nudge is retired; the migration's real risk (reader enumeration) is named.

---

## 1. The spine

The system is the per-product registered inventory entity; the use case is the unit of assessment that travels the gates (DOMAIN §3; `UseCase.state` carries the lifecycle, the system carries none).

1. **Registration is use-bound, draft-staged, atomically created.** A system is only ever created together with its first use case (REG-2; no bare system). Capture is draft-staged (§3a); the live system-plus-use-case is created atomically at the classification boundary, never incrementally, never as an orphan.
2. **One product, one registered system per tenant `[NOVEL]`.** First governance of a product creates the registered system; subsequent uses attach as new use cases on it. Net-new canon (a `(tenant_id, catalogue_product_id)` constraint absent today, V2), not a DOMAIN §3 ratification. **Edge, deferred:** the same product in two materially different deployments is arguably a second system; the one-system rule holds for the common case, the distinct-deployment case is noted, not foreclosed.
3. **Context lives where it is assessed `[RULED, OPEN-INTAKE-D]`.** `data_categories`, `affected_parties`, `usage_context`, and `human_oversight` (and the `system_data_category` / `system_affected_party` join tables → `use_case_*`) move to the use case; the system keeps deployment-stable facts (operator role, hosting model, lifecycle stage, catalogue link). **Rationale (corrected, N1):** this is **per-use-case context fidelity**, the AIIA, the inventory record, and the audit pack carry the right context for *this* use, and "add a use case" captures distinct context. It is **not** a classifier change: the tier already resolves per use case from the product category bridge (`resolve_classification`: product → `product_category_membership` → `product_category_eu_mapping` → `eu_ai_act_subcategory`) plus the per-use-case context-gate answers (`context_classification`, `answers_blob`); none of the relocated fields feed `resolve_classification`. **The domain sprint must not wire these fields into the classifier, they do not feed it.** The distinct tiers in the inventory specimen come from the context gate, not from these fields. Carries a migration; the real risk is the stranded-reader set (V1), not the move.
4. **Clearances are established once and inherited.** A cleared vendor does not re-run diligence; the use case inherits it (cascading VendorApproval → ProductApproval → use-case authorisation, DOMAIN §5 / APR-3). Confirmed, not novel.

## 2. Routing by what already exists

- **First encounter with a product** → register the use-bound system: system facts plus the first use case's facts, captured then created atomically.
- **Product already registered** → route to **add a use case**; skip system-facts capture. **Route delta (V3):** no by-product systems read exists (`/v1/systems/{id}/approval-status` absent; `GET /v1/systems` is the only read), so recognition is a new endpoint or a client-side resolve; §9.1 owns it.
- **Vendor already cleared** → inherited, no re-run (§1.4).

## 3. The two runs, and how capture persists

**3a — Draft staging, the creation boundary, and resume `[RULED, OPEN-INTAKE-C]`.** Capture persists progressively: in-memory while a screen is being filled, persisted to a draft staging record when the screen completes and the user advances, that persisted state feeding forward to prefill the next screen. The draft is **staging, distinct from the live entity**, so atomic use-bound creation (§1.1) holds: the system-plus-use-case is created from the draft at the **creation boundary**, right after the use-facts screen, the first point with enough context to classify and the point a real use case must exist for `Classification` to attach.

Natural screen sequence and persistence points: product selection (also the recognition fork) → system facts (first-time only) → use facts → **[creation boundary]** → just-in-time context loop → classification → whose-court. Pinning the exact decomposition is the wizard sprint's job; the boundaries are the binding shape.

**Resume has two faces and two entries.** Before the boundary the draft is a scratchpad; after it, the entity is a real in-flight system in the inventory (§4) carrying resume on its own row. The pre-creation draft is reachable two ways: a resume-or-start-over prompt on re-entering the Register flow, and a slim "registration in progress" indicator on the dashboard, a workspace cue, deliberately unobtrusive. One active draft per user; resume lands on the screen left; the draft never appears in the inventory table.

**Run one — capture to classification.** One uninterrupted, correctable pass to the EU AI Act tier. Not purely linear: the built `requires_context` just-in-time loop runs (post-creation) before resolution, the "ask just-in-time" half of capture-once / orchestrate-after (D-16 / IXN-1). The break falls at classification because it consumes the up-front context and returns the tier, which forks everything (prohibited halt vs assessment depth).

**Run-one boundary — the post-resolution whose-court verdict, three outcomes:**
- **Prohibited** → hard halt at intake, supreme (D-7 / INV-26, 33).
- **Cleared and the user's court** → use case approved, begin assessment; run two starts.
- **Not prohibited, vendor/product not yet cleared** → parked pending clearance, the authoriser's court, surfaced honestly. Shipped behaviour (FE-11; `whose-court-step` reads `blocking.verdict == "park"`, `responsible_party == "authoriser"`); the contribution is framing it as the deliberate boundary.

**Run two — assessment.** The AIIA and feeders, started only when the court is the user's, uninterrupted, at the tier's depth.

## 4. The register is the AI Systems Inventory

The register is the audit-facing record, the answer to "show me your AI Systems Inventory." **Scope (corrected, N5):** the inventory is the **per-system list**, not the whole dashboard. Today's `PortfolioHub` mixes your-court, posture, and the per-system list; §4 governs the list. The identity decides its contents and presentation:

1. **Drafts never appear in it.** A pre-creation draft is a scratchpad, surfaced only via the §3a resume entries, never an inventory row.
2. **Every system past the creation boundary appears, with honest status, regardless of approval state** — in-flight, pending, authorised, and **halted-prohibited**. The halted system stays in the record: it is the evidence the organisation assessed a prohibited practice and stopped it; hiding it would read as ungoverned. In-flight is shown with honest lifecycle status, not hidden.
3. **Audit-grade status legibility.** Status renders as authored labels, never raw enum members. The `VerdictChip` label map (V2, FE-16 / D-60 / INV-75) is **compliance-grade**, not cosmetic; a raw `vendor_check` facing an auditor is an INV-75 failure, not an ugly chip.
4. **The system detail page is the per-system record `[premise corrected, N2/N3/N4]`.** Drilling into a row opens one system's record. The surface (`systems/[id]`, the UI-F6-AUDITPACK page) is **not a thin rollup**: it already renders the rollup, a coverage panel (`GET /v1/systems/{id}/coverage`), and the on-demand audit-pack export (`/v1/systems/{id}/export`). The delta is that it **gains an inline per-system record** composed on mount from the already-available reads, `SystemDetail` (`GET /v1/systems/{id}`, already returned), the rollup, coverage, and the lifecycle trail, showing the system's deployment-stable facts, its use cases each with tier, status, and their (post-D) distinguishing context, and the coverage and lifecycle depth. **This is a composition pass, pure frontend, no backend delta** (the only shape change is the post-D use-case context, which rides the domain sprint). Two boundaries to hold: the inline record must **agree with the `build_system_export` / `SystemExportRead` assembler's shape, not fork it** (single-home); and the **hashed audit-pack artifact stays the explicit on-demand `/export`, never fired on mount (INV-53, V5)**. "Inline per-system record" and "the audit-pack artifact" are distinct, collapsing them either fires `/export` on load or forks the assembler.

**OPEN-INTAKE-E (minor, narrowed):** the inventory list deserves its own identity rather than living unnamed inside "Portfolio." The fix is **not** a wholesale "Portfolio → AI Systems Inventory" rename, which would subordinate the court and posture content under an inventory label; it is to give the inventory list a named view or section of its own while the assurance-face court/posture keeps its identity. Pin which surface carries the inventory name before settling E.

## 5. Prefill with provenance

Each run presents the platform's best current answer, not blank fields, every value sourced, labelled, and overridable; the user accepts or overrides (CAT-3 / CAT-4; the positive form of D-59). Draft-staging feed-forward (§3a), catalogue facts, and tier/context safe defaults are the prefill sources.

**Accept is not override in the record.** Confirmed-default vs amended is distinct provenance. **Delta (N4, v2):** the `provenance_confidence` ladder is today an `assessment_item` mechanism (PAT-8); register prefill is display-only with presentational override and no write-back (DF1-4, DF1-8). Reaching register fields with faithful provenance is net-new backend, provenance columns plus a write-back path. §9.3 owns it.

## 6. What this changes versus the current build

- **The orphan-system seam (REG-2)** → closed by draft-staged, atomically-created, use-bound registration (§1.1, §3a).
- **The zero-use-case nudge is retired (N6).** The dashboard's non-interactive "no use case registered yet for this system" row exists only because the orphan seam allows use-case-less systems. Once §1.1 closes it, that nudge can never populate; the wizard/inventory sprint retires or repurposes it and reconciles with D-61 scaffolded-empty.
- **Blank-form intake for a known product** → prefilled, accept-or-override (§5).
- **In-run correction** → today in-memory only; §3a gives it a persisted, resumable home with two discovery entries. Whether the reducer also lacks back-transitions is V1 (carried from v2).
- **No known-product / known-vendor routing** → §2 added.
- **The detail page lacks an inline per-system record** → §4.4 composition pass (no backend delta).
- **Resume hidden behind Register** → dual entry (§3a).

## 7. What this confirms in canon (not new)

System/use-case split (DOMAIN §3), capture-once / orchestrate-after (D-16 / IXN-1), prohibited supreme (D-7 / INV-26, 33), inheriting approvals (DOMAIN §5 / APR-3), **per-use-case classification (already real, D-8 / INV-10, via the product bridge plus context gate, not via the relocated fields)**, authorisation a human-act gate only (D-12 / INV-35), prefill-with-provenance (CAT-3 / CAT-4), the whose-court park verdict (FE-11), the existing `systems/[id]` audit-pack surface and `build_system_export` assembler (INV-53). Novel: §1.2 (one-product-one-system), §1.3 (context relocation, as fidelity), §3a (draft staging), §4's inventory-completeness rule, and the run-one boundary as first-class.

## 8. Decisions

- **OPEN-INTAKE-D — RULED.** Relocate the four fields (and join tables) to the use case, for context fidelity (§1.3); the system keeps deployment-stable facts. **Rejected:** duplicate-at-use-case (single-home); materially-different-use-is-a-new-system (contradicts §1.2).
- **OPEN-INTAKE-C — RULED.** Progressive draft staging; draft distinct from the live entity; atomic creation at the classification boundary; dual resume entry; one active draft. **Rejected:** in-memory-only; single final commit; explicit Save button.
- **Inventory contents — RULED (§4).** Drafts out; every committed system in with honest status including halted; in-flight shown; status audit-grade; the per-system record composed inline, distinct from the on-demand hashed pack (INV-53).
- **OPEN-INTAKE-A — RULED:** ratify the honest stop (shipped FE-11 park/authoriser).
- **OPEN-INTAKE-B — RULED:** distinguish, do not blanket. Tier override keeps its CLS-3 justification; non-tier amends are provenance-only (`USER_AMENDED`; XCUT-1 / INV-13).
- **OPEN-INTAKE-E — OPEN (minor):** give the inventory list its own named identity (view/section), not a hub-wide rename. Pin the carrying surface; not blocking.

## 9. Decomposition into sprints

1. **Domain / data-model sprint (backend-led).** **First task: enumerate every reader of the four fields and join tables before moving them (V1)** — `get_system_detail` / `_build_detail`, `_load_system_full`, `build_system_export` + `_use_case_record`, `prefill_service`, the `SystemCreate` / `SystemUpdate` / `SystemDetail` schemas, `intake-capture-step.tsx`, `SystemDetailClient`, so none is stranded. Then the §1.3 relocation migration; use-bound atomic registration and the orphan-system closure (REG-2); the §3a draft-staging record, creation boundary, and in-flight register signal; the §1.2 constraint (V2) and the distinct-deployment edge; the recognition by-product read (V3). No `SystemDetail` backend delta (it is already returned).
2. **Wizard restructure (UI).** Two-run flow, first-time-vs-add-a-use-case routing, per-screen persist-on-transition, the dual resume entry and resume-or-start-over UX, the retirement of the zero-use-case nudge (N6), in-run correction (V1), the `requires_context` loop, and the run-one whose-court boundary.
3. **Prefill rework (UI + backend).** Prefill-with-provenance and the accept-or-override ladder, including the net-new register-field provenance columns and write-back, carrying semantic-fidelity S-B and S-C.
4. **Related — F2/F6 detail composition pass.** The inline per-system record (§4.4) on the V2 foundation and the label map, composed from `SystemDetail` + rollup + coverage + lifecycle trail, agreeing with `build_system_export`'s shape and keeping the hashed pack on-demand (INV-53, V5). Pure frontend; C-track sequenced, not one of the three intake sprints.

V2 depth/layout and the `VerdictChip` label map are upstream; all of the above inherit them.

## 10. Candidate canon (minted at sprint time, above live floors D ≥ 62 / INV ≥ 75 / FE ≥ 27)

Use-bound-registration invariant (no bare system, REG-2); use-distinguishing context on the use case as fidelity (§1.3); the §1.2 product→system constraint (with the deployment-edge rider); the §3a draft-staging model, creation boundary, and in-flight register signal; the inventory-completeness rule (§4); the inline per-system record distinct from the hashed pack (INV-53); run-one boundary at classification with the three-outcome verdict; the prefill accept-or-override provenance discipline and its register-field write-back. Each authored by its sprint.

## Appendix — review disposition (v2 + v4 folded)

v2: B1 → OPEN-INTAKE-D (ruled relocate); N1 (one-product-one-system reframed novel + deployment edge); N2 (whose-court shipped, framing is the contribution); N3 (`requires_context` loop); N4 (register-field provenance net-new); N5 (REG-2); N6 → OPEN-INTAKE-C (ruled); A/B resolved.
v4: **N1** (§1.3 corrected to context-fidelity, not classifier wiring); **N2/N3** (§4.4 corrected, `systems/[id]` is the existing F6 audit-pack surface, inline-record composition is pure frontend, no `SystemDetail` backend delta); **N4** (inline record bound to `build_system_export`, hashed pack on-demand under INV-53); **N5** (OPEN-INTAKE-E narrowed to the inventory section, not the hub); **N6** (vestigial nudge retired). New verifies **V1** (reader enumeration, now §9.1 first task) and **V5** (INV-53 scope); **V2–V4** carried as sprint §0 verifies.

---

**Ratified (OPEN-INTAKE-E minor, open).** Decomposes per §9, domain sprint first, opening with the reader enumeration (V1) before the migration. Each sprint produces its own design doc and execution-only handoff through fresh-chat review.