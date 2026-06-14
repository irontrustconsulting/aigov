# IronTrust MVP — Sprint Backlog

Outstanding backend work to complete full MVP scope. Ordered by dependency: each sprint leaves the backend in a state the UX can wire against. Sprint specs for individual sprints are maintained separately.

**Foundation already in place:** tenant provisioning, operator RBAC, identity and membership (admin/member roles), member invite and listing, governance role model with full SoD enforcement (5 roles, 9-pair conflict matrix, assign/revoke/list), AI system register (name-only create/list), use case registration with auto-classification and versioned override, reference data drill-down (categories → vendors → products, EU subcategories), and the tenant-plane audit trail.

---

## Sprint 1 — System Register Enrichment + Catalogue Prefill

### Objective

Right now, registering an AI system captures only a name. This sprint makes the system register meaningful: the user identifies the actual AI product their org is using (selecting from the curated catalogue), captures the contextual metadata needed for assessment (purpose, deployment context, data categories, who is affected), and the platform responds with the confirmed facts it already knows about that product so the user confirms or amends them rather than researching from scratch. This is the "product-driven prefill" thesis (PRD §4.3) applied to intake — the single biggest differentiator.

When a system is linked to a catalogue product, the platform can also immediately tell the user whether that vendor and product have already been cleared by their organisation, so they know upfront whether they're starting from scratch or inheriting prior diligence.

For systems not in the catalogue (custom or in-house), the registration flow degrades gracefully: no prefill, but the same metadata fields are captured. The product never depends on catalogue coverage to function.

### What it builds

- `POST /v1/systems` — expanded to accept `catalogue_product_id` (optional), `owner_user_id`, and structured intake metadata: purpose, deployment context, data categories, affected parties, lifecycle stage, custom/in-house flag.
- `GET /v1/systems/{id}` — returns full system detail with linked product name, vendor name, use case count, and per-use-case lifecycle states.
- `PATCH /v1/systems/{id}` — update system metadata after initial registration.
- `GET /v1/systems/{id}/prefill` — when a catalogue product is linked, returns all `CatalogueFact` rows for that product with full provenance metadata (`source_url`, `source_label`, `last_checked_at`, `provenance` tag). Empty list if no catalogue product. This is what the UX renders as the confirm/amend prefill panel.
- `GET /v1/systems/{id}/approval-status` — reads `VendorApproval` and `ProductApproval` for this tenant and returns clearance state (`NOT_STARTED`, `UNDER_REVIEW`, `APPROVED`, `REJECTED`, `EXPIRED`). Read-only in this sprint; approval record mutations come in Sprint 5.
- `GET /v1/reference/products/{id}` — product detail with vendor name and taxonomy tags (needed by the UX when a user selects a product in the drill-down wizard).

### What it does not include

Mutations to vendor or product approval records — that comes in Sprint 5 alongside the lifecycle gate enforcement. The classification context wizard (what happens when the catalogue cannot determine tier) is Sprint 2. The system-level rollup view showing assessment coverage comes in Sprint 5.

---

## Sprint 2 — EU AI Act Classification Context Wizard

### Objective

The existing classification engine resolves a use case's EU AI Act tier by traversing the catalogue bridge (system → product → category → subcategory). When that bridge exists, it works. When it doesn't — because the system is custom, the product isn't in the catalogue, or the deployment context is genuinely ambiguous — it returns `REQUIRES_CONTEXT`, which is a placeholder, not an answer.

This sprint builds the guided decision tree that resolves `REQUIRES_CONTEXT` into a concrete, defensible tier. The wizard walks the user through the deployment-context characteristics that determine tier under the EU AI Act: is the use case in a high-risk domain (Annex III), does it fall under a prohibited practice, does it trigger a transparency obligation only? The answers are stored with the classification snapshot so the rationale is always traceable — this is the "shown reasoning" part of the §1.5 pattern applied to classification.

The context wizard is also the confirmation path when a catalogue product IS linked: the user reviews the pre-resolved tier and answers any remaining questions the catalogue couldn't answer on its own. Nothing in classification is asserted silently; the user always has the last word.

### What it builds

- `GET /v1/use-cases/{id}/classify/questions` — returns the relevant question set for this use case. Questions are filtered based on what's already known (catalogue facts, any prior context provided), so the user is only asked what the system can't derive on its own. Each question carries its Annex/criteria reference so the user understands the basis.
- `POST /v1/use-cases/{id}/classify/context` — accepts the structured answers, resolves a tier and rationale, and snapshots a new `Classification` row with `answers_blob` populated (the complete audit record of what was asked and answered). Marks the prior `REQUIRES_CONTEXT` snapshot as no longer current.
- Classification responses include the obligation set triggered by the resolved tier: which EU AI Act obligations now apply (conformity assessment, technical documentation, transparency notices, human oversight requirements). This is surfaced as a structured list, not free text.

### What it does not include

The AIIA itself (Sprint 3) — classification gates it but doesn't contain it. Per-use-case obligation tracking as a persistent entity comes later. AI-assisted classification suggestion is post-MVP.

---

## Sprint 3 — AIIA Engine

### Objective

The AI System Impact Assessment is the centre-of-gravity feature. This sprint builds the full backend for creating, populating, and structuring an AIIA aligned to ISO/IEC 42005 — one per use case, with FRIA, DPIA-style, and model/system-risk analyses as first-class feeding sections that push data into the AIIA rather than existing as separate documents.

The AIIA is scoped by the use case's EU AI Act tier: a high-risk use case requires the full section set; minimal-risk is appropriately lighter. This tier-based scoping is what makes the assessment proportionate and defensible rather than a one-size questionnaire.

Pre-fill is a first-class behaviour: on creation, the AIIA is populated with known context (system name, purpose, classification tier and rationale, deployment context captured at intake) so the user is never re-entering facts already given. The system also proposes a relevant risk set from the Risk Library — drawn from OWASP Top 10 for LLMs, NIST/ISO governance themes, and any typical risks associated with the linked catalogue product — so harm identification is driven by curated expertise rather than the user's recall. Every proposed item is tagged `AI_SUGGESTED` and requires human confirmation.

Assessment items are the connective tissue: each item optionally names a library risk, carries a human response and treatment plan, and can be linked to one or more controls. Because controls are cross-mapped across ISO 42001 and the EU AI Act, linking one item to one control simultaneously satisfies both frameworks. This is the "cross-mapping pays off" moment.

### What it builds

- `POST /v1/use-cases/{id}/assessments` — creates the AIIA. Enforced one per use case (the `uq_one_aiia_per_use_case` constraint). On creation: pre-fills standard section prompts from the system register and classification data; proposes a relevant risk set (tagged `AI_SUGGESTED`) based on the use case tier, system modality tags, and any `CatalogueProductRisk` entries for the linked product. If the use case tier is `PROHIBITED`, this endpoint rejects creation — a prohibited practice has no assessment, only a hard stop.
- `GET /v1/use-cases/{id}/assessments` — returns the AIIA and any linked feeder assessments.
- `GET /v1/assessments/{id}` — full assessment with all items, control links, and evidence link stubs.
- `POST /v1/assessments/{id}/feeders` — creates a FRIA, DPIA, or MODEL_RISK feeder linked to this AIIA (`parent_aiia_id`). Feeders share the same item/control/evidence structure as the AIIA; facts entered in a feeder propagate into the AIIA automatically (not re-keyed).
- `GET /v1/assessments/{id}/sections` — returns the tier-based section template: which sections are required, recommended, or not applicable for this use case's tier. This is what the UX uses to render the assessment structure.
- `POST /v1/assessments/{id}/items` — creates an assessment item: prompt (the section question), response (human answer), likelihood and severity scores, mitigation plan (the treatment), and provenance tag. AI-proposed items start as `AI_SUGGESTED`; once a human responds, they become `USER_CONFIRMED` or `USER_AMENDED`.
- `PATCH /v1/assessments/{id}/items/{item_id}` — update response, mitigation plan, scores, and provenance.
- `DELETE /v1/assessments/{id}/items/{item_id}`
- `POST /v1/assessments/{id}/items/{item_id}/control-links` — links an item to a control. Because controls cross-map across frameworks, one link satisfies both ISO 42001 and EU AI Act simultaneously. Carries a `CoverageStatus` (open / partial / satisfied).
- `DELETE /v1/assessments/{id}/items/{item_id}/control-links/{link_id}`
- Reference additions: `GET /v1/reference/risks` (filterable by risk layer, source framework, and tier), `GET /v1/reference/controls` (filterable by framework).

### What it does not include

Evidence file upload (Sprint 4) — items can reference evidence links but the upload mechanism isn't wired yet. Assessment status transitions and review submission (Sprint 6). AI-assisted text drafting is post-MVP. The assessment version/refresh cycle (re-running on material change) is post-MVP.

---

## Sprint 4 — Evidence Repository

### Objective

Evidence is what turns an assessment from a self-declaration into a defensible, audit-ready record. This sprint builds the central evidence repository: upload a file, store it in S3, and link it to one or more assessment items. Evidence is reusable — the same document (a data processing agreement, a model card, a security certification) can satisfy multiple items across multiple assessments without re-uploading.

The storage model keeps file bytes in S3 and a pointer plus integrity hash (`sha256`) in Postgres, so the artifact can be proven unaltered. This is a hard design invariant.

Upload uses a presigned URL pattern: the backend generates a time-limited S3 PUT URL, the client uploads directly to S3, then confirms completion. This keeps large files off the API server.

### What it builds

- `POST /v1/evidence/upload-url` — validates metadata (title, content type, size), creates an `Evidence` row in `pending` state, returns a presigned S3 PUT URL for the client to upload directly.
- `POST /v1/evidence/{id}/confirm` — called by the client after the S3 upload completes. Stores `s3_version_id` and `sha256`; transitions evidence to active state.
- `GET /v1/evidence` — lists all evidence for the tenant with pagination.
- `GET /v1/evidence/{id}` — evidence metadata plus a presigned S3 GET URL for download.
- `POST /v1/assessments/{id}/items/{item_id}/evidence-links` — links existing evidence to an assessment item. The same evidence record can be linked to multiple items across multiple assessments without copying.
- `DELETE /v1/assessments/{id}/items/{item_id}/evidence-links/{link_id}` — removes a link (does not delete the evidence itself).

### What it does not include

Evidence assignment to contributors with due dates and reminders (EVD-3) — post-MVP. Freshness/expiry notifications (EVD-4) — the `expires_at` field is already on the model as a seam; notification logic is post-MVP.

---

## Sprint 5 — Lifecycle State Machine + Cascading Approval Gates

### Objective

The fixed lifecycle is what turns the individual features — registration, classification, assessment, evidence — into a coherent, governed flow with a clear outcome. This sprint wires up the state machine: a use case progresses through gates, cannot skip ahead until each gate's conditions are met, and the system tells the user where they are, why, and whose action is needed next.

The gates are deterministic: vendor clearance → product clearance → intake/prohibited-practice stop → assessment completion → treatment planning → authorisation. Each gate checks the facts that have been captured and either advances the use case or holds it with a clear reason. When a use case is classified as a prohibited practice under the EU AI Act, it halts permanently — this is a non-negotiable hard stop, not an advisory.

Vendor and product approval records are managed here. A tenant's clearance of a vendor or product is their own decision — the shared catalogue facts inform that decision, but approval status is per-tenant. This sprint adds the endpoints to set and update those approval records (the "thin diligence" record — full diligence workflows are post-MVP). The gate logic reads these records on every lifecycle advance, so updating an approval can unblock a held use case.

The system-level rollup view is also completed here: each system shows its use cases' current states, the highest tier present, and any outstanding gate obligations — the portfolio view a compliance lead needs to track their AI programme.

### What it builds

- `advance_use_case` service — evaluates all gates in order for a given use case and transitions to the next state or to `HELD` (with a structured reason) if any gate is unmet. Called automatically after any gate-relevant action (approval record update, classification change, assessment approval). Writes a `LifecycleTransition` row and an `AuditEvent` for every state change.
  - Vendor gate: reads `VendorApproval.status` for the linked vendor; if not `APPROVED`, holds at `VENDOR_CHECK`.
  - Product gate: reads `ProductApproval.status` for the linked product; same logic.
  - Prohibited-practice stop: if `eu_tier == PROHIBITED`, transitions to `HALTED_PROHIBITED` (terminal, cannot be reversed).
  - Assessment gate: AIIA must be in `APPROVED` status.
  - Treatment gate: all assessment items above a risk threshold (likelihood × severity) must have a `mitigation_plan` set.
  - Authorisation gate: resolved by the reviewer/authoriser sign-off in Sprint 6.
- `POST /v1/use-cases/{id}/advance` — explicitly triggers gate evaluation. Called by the UX after the user has taken an action they believe satisfies a gate.
- `GET /v1/use-cases/{id}` — enriched to return current `state`, the reason the use case is in that state (drawn from the latest `LifecycleTransition`), and a structured description of what action is required next and who needs to take it.
- `PUT /v1/vendor-approvals/{vendor_id}` — upserts the tenant's `VendorApproval` record for the given vendor: sets `status` and a thin `diligence_blob` (certifications, breach history summary, validity period). One record per tenant+vendor.
- `PUT /v1/product-approvals/{product_id}` — same for product-level clearance.
- `GET /v1/systems/{id}` — rollup added: per-use-case lifecycle states, highest tier across all use cases, and a count of outstanding obligations (unmet gate conditions) across the system. This is the system dashboard view.

### What it does not include

The authorisation gate itself is not completed here — it requires the reviewer/authoriser sign-off in Sprint 6. Full vendor/product diligence workflows (questionnaires, evidence collection, decision history) are post-MVP; this sprint provides only the thin status record and gate check. The upward rollup of use-case assessment evidence into a product approval view (APR-4) is post-MVP.

---

## Sprint 6 — Review, Sign-off & Deployment Authorisation

### Objective

Governance without sign-off is record-keeping, not governance. This sprint builds the review and authorisation workflow: the 1st-line system owner submits an assessment for review, the 2nd-line reviewer examines it and either approves or requests changes, and the authoriser makes the final risk-acceptance decision and grants deployment authorisation (the ATO). Each step is gated by a governance role and writes to the immutable audit trail.

The separation of duties already enforced at role assignment pays off here: the reviewer cannot be the authoriser (and neither can be the system owner). The platform enforces this at each workflow step, not just at role assignment. A reviewer approving their own assessment is rejected.

The review queue makes the reviewer's outstanding work visible: assessments submitted for review, filterable to show only those the caller is eligible to review. This is the "whose court is the ball in" UX that the interaction model requires (PRD IXN-4).

Deployment authorisation produces a structured ATO record — not a PDF yet (that's Sprint 7's export), but the underlying data: which use case, which assessment, which tier, who authorised it, when, and a residual risk statement. This is what the Sprint 7 export will render into an ATO document.

### What it builds

- `POST /v1/assessments/{id}/submit-for-review` — 1st-line action; gated on `system_owner` governance role. Transitions `AssessmentStatus` from `DRAFT` to `IN_REVIEW`. Assessment must have all required sections answered (tier-based completeness check) before submission is accepted.
- `POST /v1/assessments/{id}/review` — 2nd-line action; gated on `reviewer` governance role. Body: `{ action: approve | request_changes, comment }`. On `approve`: transitions to `APPROVED`, triggers `advance_use_case`. On `request_changes`: returns to `DRAFT` with the comment attached. Rejects if the reviewer is the same person as the system owner (SoD enforcement at the action level).
- `POST /v1/assessments/{id}/authorise` — gated on `authoriser` governance role. Accepts residual risk; sets `approved_by_user_id` and `approved_at`; creates a structured authorisation record; triggers `advance_use_case` (which checks the authorisation gate and moves the use case to `AUTHORISED`). Rejects if the authoriser is the reviewer (SoD).
- `POST /v1/assessments/{id}/refresh` — marks a previously approved assessment as `NEEDS_REFRESH` (used when a material change triggers re-assessment). Moves the use case back to `UNDER_ASSESSMENT`.
- `GET /v1/review-queue` — returns assessments in `IN_REVIEW` state for this tenant. Intended for a reviewer to see their pending work. Filterable by assessment type (AIIA / FRIA / DPIA / MODEL_RISK).
- `POST /v1/assessments/{id}/comments` — adds a review comment; attached to the assessment, attributed to the actor.
- `GET /v1/assessments/{id}/comments` — returns the comment thread in chronological order.
- `GET /v1/use-cases/{id}/authorisation` — returns the structured ATO record: use case context, EU AI Act tier and rationale, assessment ID and status, authoriser identity and timestamp, residual risk summary statement. This is the data source Sprint 7 will render into an exportable document.

### What it does not include

Notifications for review assignments and approvals (WKF-4) — post-MVP. Read-only auditor-scoped access (EXP-2) — post-MVP. Assessment versioning and refresh scheduling (AIIA-7) — the `NEEDS_REFRESH` trigger is included, but the version-bump and re-assessment cycle management is post-MVP.

---

## Sprint 7 — Control Coverage View + Export / Audit Pack

### Objective

The compliance output is a first-class product deliverable, not an afterthought. This sprint builds two things: a cross-framework control coverage view that shows which controls are satisfied, partial, or open across this tenant's assessments; and a structured export pack that a compliance professional or auditor can take away as the complete, traceable record of an AI system's governance.

The control coverage view is the output of the cross-mapping investment made in the data model: because assessment items were linked to controls and controls are mapped across frameworks, the platform can show — for ISO 42001 and the EU AI Act simultaneously — which controls have been evidenced and which are still open. This is what converts individual assessment work into a programme-level compliance posture.

The export pack is the audit deliverable: a structured JSON export (with PDF rendering deferred to a later layer or handled by the frontend) that contains the full assessment record — classification history, all assessment sections and their responses, evidence references, control links, and the lifecycle transition trail. The ATO-style deployment authorisation document is a structured record of the basis on which a use case was authorised for deployment, exportable on its own.

### What it builds

- `GET /v1/coverage` — returns per-framework control coverage across this tenant's approved assessments. For each control in the library, returns `CoverageStatus` (open / partial / satisfied) derived from `AssessmentItemControl` links across all approved assessments. Includes a summary count per framework.
- `GET /v1/coverage/{framework}` — same, filtered to a single framework (`iso_42001` or `eu_ai_act`).
- `GET /v1/use-cases/{id}/export` — structured JSON export of a single use case's full governance record: system context, classification history (all versions), assessment sections and items with responses, evidence references, control links with coverage status, lifecycle transition trail, and the authorisation record if present.
- `GET /v1/systems/{id}/export` — system-level export pack aggregating all use cases under the system into a single governance record.
- `GET /v1/use-cases/{id}/authorisation-document` — structured ATO-style record: use case identity, EU AI Act tier and classification rationale, assessment summary (sections, residual risk statement), authoriser identity and timestamp, and a complete list of evidence items referenced. This is the standalone deployment authorisation artefact.

### What it does not include

PDF rendering — the export endpoints return structured JSON; rendering into a formatted document is a frontend concern or a later layer. Branded/templated export (EXP-3) — post-MVP. Read-only auditor-scoped access (EXP-2) — this would be a thin addition to the membership model; deferred post-MVP.

---

## Post-MVP (not blocking UX wiring)

These features have seams in the data model but no sprint is planned for them in the MVP phase.

| Feature | Seam in place | Status |
|---|---|---|
| AI-assisted AIIA drafting | `ai_suggested_text` on `AssessmentItem` | Post-MVP (S priority) |
| Evidence assignment / reminders | `EVD-3` — no model addition needed | Post-MVP (S priority) |
| Evidence freshness flags | `expires_at` on `Evidence` | Post-MVP (C priority) |
| Catalogue entry freshness / versioning | `last_verified_at` on vendor/product | Post-MVP (S priority) |
| Notifications (review assignments, approvals) | `WKF-4` | Post-MVP (S priority) |
| Product approval rollup from use-case evidence | `APR-4` | Post-MVP (S priority) |
| Read-only auditor-scoped access | `EXP-2` | Post-MVP (S priority) |
| Branded/templated export | `EXP-3` | Post-MVP (C priority) |
| MITRE ATLAS risk layer | `ADVERSARIAL_THREAT` enum reserved | Post-MVP |
| Per-system (object-scoped) governance roles | Nullable `scope_id` seam designed | Post-MVP |
| Full vendor/product diligence workflows | `APR-6` | Post-MVP |
