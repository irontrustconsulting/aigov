# REQUIREMENTS.md — IronTrust AI Governance Platform

**Location:** `docs/REQUIREMENTS.md` — single source, mirrored to project knowledge. Updated rarely (stable spec).
**Purpose:** The durable requirement registers — *what must be built*, with MoSCoW priority and stable IDs for citation. This is the spec, not the status: **implementation state lives in `STATE.md`**, rationale in `DECISIONS.md` (`D-n`), constraints in `INVARIANTS.md` (`INV-n`), the conceptual model in `DOMAIN.md`.

**Priority:** `M` = Must · `S` = Should · `C` = Could (all for MVP).
**`realised by`** lines link each group back to the decisions/invariants that govern it — the reverse of the `refs:` those registers already carry.

---

## Cross-cutting requirement (XCUT)

**XCUT-1** (M) · Wherever the system asserts a position surfaced to the user, it must follow the §1.5 pattern — **strong default → shown reasoning → easy override → tracked deviation**. Applies across classification (CLS), AIIA content (AIIA), and catalogue prefill (CAT).
↳ realised by: D-1; INV-13 (provenance server-derived realises the tracked-deviation term); DOMAIN §1

---

## 4.1 Product Lifecycle, Gates & Interaction Model

### Lifecycle (LFC)

| ID | Requirement | Pri |
|---|---|---|
| LFC-1 | Each use case carries a status reflecting its position in the fixed lifecycle (Requested → Vendor check → Under assessment → Treatment pending → Authorised; plus terminal Halted-prohibited and held states). | M |
| LFC-2 | A use case cannot transition to a later gate until the current gate's conditions are satisfied. | M |
| LFC-3 | Prohibited-practice hard stop at intake: a use case classified as a prohibited practice halts and surfaces the reason; it cannot proceed to assessment. | M |
| LFC-4 | Vendor and product gates read approval status and hold progression if either is uncleared, cascading (vendor → product → use case). | M |
| LFC-5 | Deployment authorisation is recorded (record-only; no technical enforcement of pipelines) and exportable as an ATO-style document. | M |
| LFC-6 | The lifecycle is fixed and opinionated in the MVP; configurability is out of scope. | M |

↳ realised by: LFC-1/2 → INV-24, 25 · LFC-3 → D-7 / INV-26, 33 · LFC-5 → EXP-1a, D-13 · LFC-6 → D-15 · DOMAIN §6

### Interaction model — capture once (IXN)

| ID | Requirement | Pri |
|---|---|---|
| IXN-1 | An uninterrupted registration/intake flow captures the universal, knowable-up-front context (product/vendor, intended uses, data touched, who is affected, deployment context). The user is not marched gate-by-gate during capture. | M |
| IXN-2 | A backend state machine reasons over the captured context and drives the lifecycle, transitioning the use case through gates automatically where context allows. | M |
| IXN-3 | Just-in-time, targeted data requests: the system asks for additional information only when a transition requires it, and explains why. It never asks up front for context that may not be needed. | M |
| IXN-4 | Legible status: the user sees where each use case is, why, what is next, and whose court the ball is in (user / reviewer / vendor / system). | M |
| IXN-5 | Asynchronous sub-flows: steps that cannot complete synchronously run as background sub-flows with status updates rather than blocking the user. | S |

↳ realised by: IXN-1..4 → D-16 · DOMAIN §6

### Layered approval (APR)

| ID | Requirement | Pri |
|---|---|---|
| APR-1 | Data model reserves three inheriting approval scopes: vendor, vendor+product, vendor+product+use-case, each with its own status. | M |
| APR-2 | Cascading gates: vendor clearance is a prerequisite for product clearance, which is a prerequisite for use-case authorisation; an uncleared vendor holds everything downstream. | M |
| APR-3 | Inheritance & work-saving: a new use case of an already-cleared vendor+product inherits both upper clearances; the system tells the user they need only assess their specific use. | M |
| APR-4 | Upward rollup: completed use-case assessments contribute evidence to the product-level approval view. | S |
| APR-5 | Thin vendor-level diligence (financial stability, breach history, certifications not derivable from use-case work) — MVP captures status + basic record. | S |
| APR-6 | Full diligence workflows at vendor and product layers (questionnaires, evidence collection, security/privacy review, decision history). Deferred post-MVP. | C |
| APR-7 | For known SaaS, the catalogue pre-fills vendor/product diligence facts for reviewer confirmation. Deferred; design intent noted. | C |

↳ realised by: APR-1..4 → D-17 · DOMAIN §5

---

## 4.2 AI System Register (REG)

| ID | Requirement | Pri |
|---|---|---|
| REG-1 | Register a system either by selecting a known catalogue product or by describing a custom/in-house system. Structured metadata: name, owner, purpose, lifecycle stage, data used, deployment context. | M |
| REG-2 | A registered system has one or more use cases; each is classified by the engine and displays its EU AI Act tier. Classification attaches to the use case, not the system. | M |
| REG-3 | Each system shows, at a glance, its use cases, each use case's assessment status, and consolidated outstanding obligations (the AIIA-1b rollup). | M |
| REG-4 | Re-classification is versioned; history is retained. | S |

↳ realised by: REG-2 → DOMAIN §3 (use case = unit of assessment)

---

## 4.3 Product Catalogue & Product-Driven Prefill (CAT)

| ID | Requirement | Pri |
|---|---|---|
| CAT-1 | Searchable catalogue of known AI products; the user selects the product they use instead of describing it from scratch. | M |
| CAT-2 | Each entry carries confirmed factual attributes (provider, model type/family where disclosed, modality, data-handling and sub-processor info, transparency obligations) and the relevant EU AI Act use-case taxonomy tags. | M |
| CAT-3 | On selection, the system prefills factual fields of the register and assessment. It does NOT assert a risk tier — tier always derives from deployment context via the classification engine. | M |
| CAT-4 | Every prefilled fact shows provenance (source + last-checked date) and a confirm/amend control. Nothing is silently asserted. | M |
| CAT-5 | Graceful fallback: a product not in the catalogue (or custom/in-house) is routed into the guided decision tree, not a blank questionnaire. | M |
| CAT-6 | Entries are versioned with a freshness/last-verified status; stale entries are flagged for re-verification. | S |
| CAT-7 | LLM-assisted enrichment drafts catalogue facts from public model cards, docs and DPAs for human review before publishing (internal curation tooling). | S |
| CAT-8 | Users can request a product be added; coverage gaps are tracked to prioritise curation. | C |

↳ realised by: CAT-3 → D-8 / INV-10 · CAT-4 → D-1 (XCUT-1) · CAT-7 → D-3

---

## 4.4 EU AI Act Risk Classification Engine (CLS)

| ID | Requirement | Pri |
|---|---|---|
| CLS-1 | A guided decision tree/questionnaire walks the user through deployment-context characteristics and assigns a tier (prohibited / high / limited / minimal). Fallback when no catalogue product applies; confirmation path when one does. | M |
| CLS-2 | Classification logic references the relevant Annex/criteria so the result is explainable, not a black box. | M |
| CLS-3 | The result captures a written rationale and the answers that led to it, for audit defensibility. | M |
| CLS-4 | The assigned tier scopes the AIIA — it determines which sections/obligations are mandatory, recommended, or not applicable. | M |
| CLS-5 | Classification is versioned; re-classification on material change is tracked with history. | S |
| CLS-6 | Surfaces the obligation set triggered by the tier (conformity assessment, technical documentation, transparency notices) as a checklist. | S |

↳ realised by: CLS-1 (per use case, from context) → D-8 / INV-10 · CLS-3 → D-1 · sign-off authority → D-9 · resolution discipline → INV-11, 12 · DOMAIN §4

---

## 4.5 AI System Impact Assessment (AIIA)

| ID | Requirement | Pri |
|---|---|---|
| AIIA-1 | A structured AIIA template aligned to ISO/IEC 42005 (system description & intended use, stakeholders/affected individuals, benefits, potential harms/impacts, likelihood & severity, mitigations, residual risk, sign-off). Harm identification is driven by the Risk Library. | M |
| AIIA-1a | Data model: a system has one or more use cases; each use case has exactly one AIIA. Classification, risk set, residual risk and sign-off attach at the use-case/AIIA level, not the system level. | M |
| AIIA-1b | System-level rollup view aggregates the use-case AIIAs: coverage, highest tier present, consolidated outstanding obligations. | M |
| AIIA-2 | Required sections and depth are scoped by the use case's EU AI Act tier — high-risk surfaces the full set, minimal-risk is appropriately light. | M |
| AIIA-3 | FRIA, DPIA-style and model/system-risk analyses are first-class sections feeding the AIIA; facts entered once propagate and are not re-keyed across documents. | M |
| AIIA-4 | The AIIA pre-fills from the register and classification, so known facts are never re-entered. | M |
| AIIA-5 | Each answer/finding can attach evidence and link to one or more controls. | M |
| AIIA-6 | AI-assisted drafting suggests text and flags gaps/inconsistencies; suggestions are marked and require human acceptance. Conclusions and risk acceptance remain human acts. | S |
| AIIA-7 | The AIIA is versioned and can be re-run/refreshed on a schedule or trigger (material change, re-classification). | S |
| AIIA-8 | Residual-risk summary/heat view across systems, drawn from completed AIIAs. | C |

↳ realised by: AIIA-1a → DOMAIN §3 · AIIA-3 → D-18 / INV-16 · AIIA-6 → D-3 · AIIA-7 → OPEN-2

---

## 4.6 Unified Control Library & Cross-Mapping (CTL)

| ID | Requirement | Pri |
|---|---|---|
| CTL-1 | Pre-loaded control set for ISO/IEC 42001 (Annex A) and EU AI Act obligations. | M |
| CTL-2 | Cross-map relationships so a single piece of evidence/answer can satisfy controls in both frameworks simultaneously. | M |
| CTL-3 | Control coverage view per framework (satisfied / partial / open). | M |
| CTL-4 | Data model designed to add further frameworks later without rework. | S |

↳ realised by: CTL-2 → D-19 / INV-21 (evidence→control transitive via items)

---

## 4.7 Risk Library (RSK)

| ID | Requirement | Pri |
|---|---|---|
| RSK-1 | Human-curated, source-attributed risk entries: source framework, layer, description, typical triggers, links to mitigating controls. | M |
| RSK-2 | MVP seed = OWASP Top 10 for LLMs (full) + a curated NIST/ISO governance & fundamental-rights layer. | M |
| RSK-3 | The library feeds AIIA harm identification: by system type, modality and tier it proposes a relevant subset for confirm/amend. It does not dump the full library. | M |
| RSK-4 | Catalogue products can carry typical associated risks, so product selection prefills likely risks. | S |
| RSK-5 | AI enhancement suggests applicable seed risks, drafts descriptions/candidate mitigations, flags gaps; all AI content is marked and human-confirmed. | S |
| RSK-6 | AI-assisted freshness: surface new seed-source revisions or emerging risk classes for curator review. | S |
| RSK-7 | The AI never authors ground-truth risks unconfirmed: library authority derives from named frameworks; AI proposes relevance/drafts, humans own what lands. | M |

↳ realised by: RSK-3 → D-1 · RSK-5/7 → D-3

---

## 4.8 Evidence & Audit Trail (EVD)

| ID | Requirement | Pri |
|---|---|---|
| EVD-1 | Central evidence repository; evidence can be reused across assessments and controls. | M |
| EVD-2 | Immutable, timestamped audit log of every create/edit/approve/export action with actor identity. | M |
| EVD-3 | Evidence requests can be assigned to a contributor with due dates and reminders. | S |
| EVD-4 | Evidence freshness/expiry flags. | C |

↳ realised by: EVD-1 (evidence→control transitivity) → D-19 / INV-21 · EVD-2 → INV-5 · EVD-3/4 → STATE deferred

---

## 4.9 Workflow, Review & Sign-off (WKF)

| ID | Requirement | Pri |
|---|---|---|
| WKF-1 | Two role axes: an administrative role (account management only) and SoD-constrained governance roles (owner, contributor, reviewer, authoriser, auditor) on three lines of defence. Admin confers no governance capability. | M |
| WKF-2 | Review queue; reviewers can comment, request changes, and formally approve with attribution. | M |
| WKF-3 | Status lifecycle for assessments (draft → in review → approved → needs refresh). | M |
| WKF-4 | Notifications for assignments, approvals and due dates. | S |
| WKF-5 | Governance-role assignment enforces a SoD conflict matrix: a user cannot hold conflicting roles. Reviewer and authoriser are separated; an owner/contributor cannot review, authorise or audit the same tenant's work. | M |
| WKF-6 | Self-assignment of governance roles is blocked: an admin cannot grant governance roles to themselves. | M |
| WKF-7 | Governance roles are tenant-scoped in the MVP; the assignment model reserves room for object-scoped (per-system) assignment without rework. | S |
| WKF-8 | Every governance-role grant and revoke is written to the immutable audit trail with actor, subject, role and timestamp. | M |

↳ realised by: WKF-1/5 → D-4 / INV-7 · WKF-6 → D-5 · WKF-7 → D-22 · WKF-8 → INV-5, 8 · WKF-3 → DOMAIN §6 · review/authorise act-SoD → INV-28, D-10 · DOMAIN §7

---

## 4.10 Audit / Export Pack (EXP)

| ID | Requirement | Pri |
|---|---|---|
| EXP-1 | Generate an export pack (PDF + structured data) for a system or a framework: assessments, evidence, control mapping and the audit trail. | M |
| EXP-1a | Generate an ATO-style deployment-authorisation document for an authorised use case (records the basis on which deployment was approved). | M |
| EXP-2 | Read-only auditor access scoped to a system or engagement. | S |
| EXP-3 | Branded/templated export for the buyer's own reporting. | C |

↳ realised by: EXP-1a → D-10, D-13 (durable identity stamping) · EXP-2 → `auditor` role, DOMAIN §7 · EXP-1 not started — STATE deferred

---

## 5. Automation boundary

Automation is applied only where it accelerates without undermining defensibility:
- **Product-driven prefill** — confirmed facts and use-case taxonomy from the catalogue (facts only, never the tier; always user-confirmed).
- **Cross-mapping** — one answer/evidence item propagates to all linked controls across both frameworks.
- **Pre-fill** — register data and classification flow into new assessments automatically.
- **AI-assisted drafting & gap detection** — marked as suggestions, always requiring human acceptance.
- **Evidence chasing** — assignment, reminders, freshness flags.
- **Regulatory-mapping maintenance** (internal) — keep control mappings current as guidance evolves.

**Deliberately NOT automated:** the assessment conclusion, risk-acceptance decisions, and sign-off — these remain human acts so the output survives scrutiny.
↳ realised by: D-3 · the human-act gate terms → INV-30

---

## 6. Non-functional requirements (NFR)

*(IDs added for citability; content from PRD §6. Mechanisms live in `ARCHITECTURE.md`.)*

| ID | Requirement |
|---|---|
| NFR-1 Security | SOC 2 controls from day one; encryption at rest and in transit; SSO/SAML for the enterprise tier. |
| NFR-2 Data residency | EU data-residency option (the ICP sells into the EU). |
| NFR-3 Multi-tenancy | Strict tenant isolation; row-level separation. *(Mechanism: RLS — ARCHITECTURE; INV-4, 40.)* |
| NFR-4 Auditability | Audit log is append-only and exportable. *(Mechanism: INV-5.)* |
| NFR-5 Reliability | Defined backup/restore; basic uptime targets appropriate to early stage. |
| NFR-6 Privacy | GDPR-aligned data handling; DPA available; minimal PII collection. |
| NFR-7 Usability | A non-technical compliance user can complete an assessment without training. |