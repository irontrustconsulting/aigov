# Sprint hand-off — Use-Case Registration & EU AI Act Classification

**Prerequisite (done):** the systems API (`POST/GET /v1/systems`), the tenant auth chain with `require_governance_role`, and the full data model + seeds — catalogue, product categories, the `product_category_eu_mapping` bridge, and `eu_ai_act_subcategory` rows carrying tier + legal_ref.

**What this sprint does:** let a `system_owner` register a use case and classify it — derive its EU AI Act risk tier from the seeded bridge **at run time**, and persist the result as a tenant-scoped, point-in-time `Classification` snapshot. Backend only; the intake wizard UX (`UX.md` §5) is a later frontend sprint that will call these endpoints.

**Why it's next:** everything downstream (the AIIA) is scoped by this tier, so this is the leg that unblocks the assessment core.

---

## Goal

A `system_owner` registers a `UseCase` under a `System`. The system derives the proposed EU AI Act tier by traversing the seeded bridge, shows the basis, allows a structured override, and writes a tenant-scoped `Classification` snapshot that stamps the tier and its basis at that moment. No tier is ever pre-seeded or pre-baked — it is derived live and snapshotted per use case.

---

## Work items

**1. Use-case registration endpoint + service.**
Add `POST /v1/use-cases` (tenant plane, RLS), gated `require_governance_role("system_owner")`. Create a `UseCase` under a given `System` (the `System` already carries the `CatalogueProduct`), capturing the structured fields the existing `UseCase` model defines. Use the existing model — don't invent fields. Audit the creation.

**2. The classification resolver (run-time derivation).**
A service that derives the proposed tier for a use case by traversing the seeded reference data: the use case's product (via its `System`) → the product's categories (`product_category_membership`) → each category's **primary** `product_category_eu_mapping` → `eu_ai_act_subcategory` → `tier`. Rules:
- Collect the primary mappings across **all** the product's categories; the **highest tier** among them is the proposed tier (single governing tier per use case).
- A product may sit in a mapped *and* an unmapped category — the mapped one still governs; only when **none** of the product's categories has a primary mapping is the result **"requires context"** — an explicit terminal state, *not* an error and *not* a silent null. (The horizontal categories — ML & Data Science Platforms, IDP, Contract & Legal Document AI — are the live examples.) The full context-question wizard is out of scope; this sprint stops at the "requires context" state.

This step reads global reference data only and writes nothing.

**3. Persist the `Classification` snapshot (tenant-scoped).**
Write a `Classification` row (RLS, `tenant_id`, attached to the `UseCase`) using the existing model. It must **stamp the basis as values, not just a foreign key** — the tier, the resolved subcategory code, and the legal_ref text as they are at classification time — so the record is a self-contained, point-in-time audit artefact, immune to later reference-data edits. Respect the existing `uq_current_classification` index: one *current* classification per use case; a re-classification or override inserts a new current row and unsets the prior, preserving history. If the model lacks a column for any stamped basis value, add it (additive migration).

**4. Override — the §1.5 contract.**
Let the owner override the proposed tier with a **structured** choice (a different tier/subcategory) plus an optional justification. An override inserts a new current `Classification` snapshot recording the chosen tier, the original proposal, and the justification — the tracked deviation. Never free-type the tier.

**5. Tests.**
- Product whose category has a primary mapping → the expected tier, basis stamped on the row.
- Product spanning categories with differing tiers → the highest governs.
- Product in a no-primary category (use one of the three named) → "requires context", not an error.
- Override → new current snapshot; prior preserved; `uq_current_classification` still holds.
- `POST /v1/use-cases` without `system_owner` → 403; with it → success.
- Cross-tenant isolation on classifications (RLS): one tenant cannot see another's.

---

## Constraints

- **Derive, never seed.** No stored or pre-baked tier on products/categories — the bridge is the single source; the tier is computed at registration. A DB view over the join is fine; a denormalised tier column is not.
- **Classification is tenant data** — RLS-scoped. The operation reads global reference, writes tenant.
- **The snapshot stamps basis values**, so later edits to the bridge or subcategories cannot rewrite history.
- **Tier changes only via a new current snapshot** — never by mutating an existing `Classification` row.
- Governance authority comes from `require_governance_role`, sourced from the DB (carried over from the untangle).
- The resolution *rules* live in the resolver, not in the data — which is itself why classification is run-time, not seeded.

## Acceptance

- A `system_owner` registers a use case and receives a derived tier with its basis shown.
- All three resolution outcomes behave: primary → tier; multiple → highest; none → "requires context".
- Each classification is a tenant-scoped *current* snapshot with stamped basis; overrides create new current rows and preserve prior ones.
- No tier is read from pre-seeded data — all derivation is live over the bridge.
- Full test suite passes.

## Out of scope

- The AIIA / impact assessment itself — the next sprint (tier-scoped: light for low tiers, fuller for high-risk).
- The full context-question wizard for "requires context" cases — rare per the ~90% mappable reality; the terminal state is the seam it will later plug into.
- The general lifecycle state machine — use simple explicit states/transitions; the orchestration engine comes once there are more stages to orchestrate.
- The intake wizard UX (`UX.md` §5) — a later frontend sprint that consumes these endpoints.
- Role-scoped read access on use cases / classifications — deferred with the rest of the read model to the assessment sprint.

## Note

"Requires context" is a real terminal state of this sprint's resolver, not a stub-to-be-ignored — give it an explicit representation in the result. It is the precise point where the future context wizard will attach.