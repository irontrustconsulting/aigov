# AI Governance Platform — MVP PRD (Draft v0.1)

**Product Requirements Document**

**AI Governance Platform — MVP**

*Working specification for design-partner review*

**Document status:** Draft v0.1 — for discussion, expected to change

**Owner:** [You]

**Last updated:** June 2026 *(v0.2 — tenant governance role model & separation-of-duties decisions incorporated; see §4.9)*

**Frameworks in scope:** ISO/IEC 42001 + ISO/IEC 42005 + EU AI Act (cross-mapped); Risk Library seeded from OWASP Top 10 for LLMs + NIST AI RMF / ISO risk themes

**MVP center of gravity:** AI System Impact Assessment (AIIA), aligned to ISO/IEC 42005

**Assessment model:** One AIIA per use case (system = registered entity, use case = unit of assessment, with system-level rollup); FRIA, DPIA & model-risk feed into each AIIA; EU AI Act classification scopes it

# 1. Summary & Strategy

## 1.1 One-line description

An AI governance platform that lets mid-market organisations run a single, defensible AI System Impact Assessment (AIIA) — aligned to ISO/IEC 42005 — scoped automatically by the system's EU AI Act risk classification, with FRIA, DPIA and model-risk analyses feeding into it, and the completed assessment converting into reusable, audit-ready evidence mapped simultaneously to ISO/IEC 42001 and the EU AI Act.

## 1.2 The problem

Organisations deploying AI now face overlapping obligations — the EU AI Act's risk tiering and conformity requirements, and ISO/IEC 42001 management-system controls (with ISO/IEC 42005 setting out how the AI system impact assessment itself should be conducted) — but the operational work is fragmented across spreadsheets, Word templates and email. Impact assessments are done once, stored in a folder, and go stale. The same facts are re-entered into separate FRIA, DPIA and risk documents. Evidence is re-gathered from scratch for every audit. The same control is evidenced three different ways for three different frameworks. This is slow, inconsistent, and hard to defend when an auditor or regulator asks how a conclusion was reached.

## 1.3 The wedge

Lead with the AI System Impact Assessment — the highest-friction, highest-anxiety task — built to ISO/IEC 42005 and scoped by the EU AI Act risk tier, and make its output do double duty as compliance evidence. FRIA and DPIA stop being separate documents and become structured inputs that feed the single AIIA record. Most incumbent tools lead with policy questionnaires or inventories; few make the impact assessment itself rigorous, 42005-aligned, reusable and cross-mapped. That is the opening.

## 1.4 Strategic principles

- Opinionated by default, grounded in standards. The market has an acute shortage of AI governance expertise; buyers largely cannot author correct governance themselves and do not want a blank, configurable canvas. The product's value is productised expertise: it asserts strong, standards-grounded default positions (ISO/IEC 42001, ISO/IEC 42005, EU AI Act) that the user confirms or amends, rather than asking the user to supply answers they do not have. The opinion is the product — but it is always accompanied by visible reasoning and source, and is always overridable (see the cross-cutting pattern below).

- Product-driven, not questionnaire-driven. The hardest part of governance for system owners and BISOs is not the assessment template — it is not knowing how to answer it (which use case does our product fall under? what model does it use?). The platform moves that cognitive load from the user to the system: the user selects the actual product they are using, and a curated catalogue supplies the facts. The user confirms or amends rather than researching from scratch.

- Human-in-the-loop by design. Assessments require judgement; the platform accelerates and structures that judgement but never replaces it. This is what keeps the output defensible to an auditor.

- Automation as connective tissue, not as a black box. Automation earns its place by cross-mapping, pre-filling, surfacing gaps and chasing evidence — not by auto-generating conclusions.

- Evidence-first. Every action a user takes should leave a clean, timestamped, exportable trail. The audit pack is a first-class output, not an afterthought.

- Defensibility over feature count. The buyer is a compliance professional; trust and rigor win over breadth.

## 1.5 Cross-cutting design pattern: strong default, shown reasoning, tracked override

This pattern is the spine of the product and applies everywhere the system asserts a position — classification, AIIA scoping and content, and catalogue facts. It is what separates being opinionated (an asset) from being unaccountable (a liability). For every assertion the product makes:

- Strong default: the system proposes a confident, standards-grounded answer rather than a blank field.

- Shown reasoning: the proposal is accompanied by its basis — the standard/clause/criterion it rests on (e.g., a specific EU AI Act Annex point, an ISO/IEC 42005 consideration) — so it can be interrogated, not merely accepted on faith.

- Easy override: the user can amend or reject the default with minimal friction; the product is a starting point, not an oracle.

- Tracked deviation: any override is recorded with who changed it, when, and ideally why — preserving the audit trail and making divergence from the recommended position visible and defensible.

*Language matters here for both trust and liability: the product offers a “recommended classification” the user confirms; it does not certify the organisation’s compliance. The organisation remains accountable for what it accepts. This keeps the authority the tool projects aligned with the accountability it actually bears.*

# 2. Users & Personas

| **Persona** | **Role in the product** | **What they need from the MVP** |
| --- | --- | --- |
| AI Governance / Compliance Lead (primary champion) | Owns the programme, oversees reviews and holds the deployment-authorisation (ATO) decision; does not author the assessments they authorise (separation of duties) | Speed, consistency, a defensible trail, less manual re-work |
| Risk / Legal reviewer | Reviews and signs off high-risk classifications, FRIAs and AIIAs; recommends — distinct from the authoriser, who accepts residual risk | Clear review queue, context, ability to comment and approve |
| Product / ML owner (1st-line owner / contributor) | Registers the system/use case and provides and confirms the facts (1st line); does not review or authorise | A simple guided intake; not drowning in compliance jargon |
| External auditor / certification body | Consumes evidence (read-only or via export) | A clean, complete, traceable evidence pack mapped to controls |

*Note on independence: where the platform is sold to organisations the founder also audits, a clear separation of roles must be maintained. The auditor persona above is a consumer of output, not a buyer in those accounts. The role model enforces this separation in software — see §4.9.1.*

# 3. Scope

## 3.1 In scope (MVP)

- A fixed, opinionated governance lifecycle with gates (vendor check → intake/prohibited-practice stop → assessments → treatment → deployment authorisation), implemented as a determinate state machine; with a capture-once / orchestrate-in-the-background interaction model (its own feature — see 4.1). This is the orchestrating spine.

- Three inheriting approval scopes in the data model (vendor → vendor+product → vendor+product+use-case) with cascading status-check gates; use-case assessments roll up to constitute most of product-level approval (full diligence workflows deferred — see 4.1.4 and 3.2).

- AI system register (lightweight inventory) with per-use-case EU AI Act risk classification.

- Curated product catalogue with product-driven prefill: user selects a known AI product and the system supplies confirmed facts and use-case taxonomy tags for confirmation (its own feature — see 4.3). This is the primary differentiator.

- EU AI Act risk classification engine that scopes the obligations and assessment depth for each system, always derived from deployment context (its own feature — see 4.4).

- AI System Impact Assessment (AIIA) aligned to ISO/IEC 42005 as the primary assessment record — one AIIA per use case, with a system-level rollup — with FRIA, DPIA-style and model/system-risk analyses feeding into each AIIA as structured sections/inputs.

- Unified control library for ISO/IEC 42001 and EU AI Act, cross-mapped so one piece of evidence can satisfy both.

- Risk Library (seed risk taxonomy): a layered, source-attributed library of AI risks seeded from the OWASP Top 10 for LLMs and NIST/ISO governance & fundamental-rights themes, feeding harm identification in the AIIA, AI-enhanced for relevance and freshness (its own feature — see 4.7).

- Evidence repository with immutable audit trail.

- Review & approval workflow with separation-of-duties governance roles and sign-off — roles organised on three lines of defence, reviewer and authoriser separated, governance distinct from administration, self-assignment blocked (see 4.9.1).

- Audit/export pack generation.

- A small set of automation accelerants (see Section 5).

## 3.2 Explicitly out of scope (for MVP)

- Automated discovery of AI assets across cloud/SaaS (high-value, but a later phase).

- Continuous technical monitoring (drift, bias, live model telemetry).

- Agentic / runtime guardrail governance.

- Full vendor- and product-level diligence workflows — questionnaires, evidence collection, security/privacy review, decision history (the three approval scopes, their statuses, the cascading gates, and the upward rollup of use-case evidence into product approval are in scope; only the standalone diligence workflows are deferred — and they are lighter than a classic VDD module because product diligence is mostly the rollup — see 4.1.4).

- Configurable approval workflows / branching approval chains / BPM-style workflow builder (the MVP lifecycle is fixed and opinionated, not configurable).

- Technical enforcement of the deployment gate (blocking CI/CD or deployment pipelines) — the MVP records authorisation only.

- Third-party / vendor AI supply-chain risk module.

- Frameworks beyond ISO 42001 and EU AI Act (NIST AI RMF etc. — design the data model to allow it, but do not build it yet).

*Recording what is deliberately excluded is as important as what is included — it protects the MVP from scope creep during design-partner conversations.*

# 4. Functional Requirements

Each feature below is written as a capability with acceptance-style notes. Priority uses MoSCoW: M = Must, S = Should, C = Could (for MVP).

**Cross-cutting requirement (applies to CLS, AIIA and CAT features): wherever the system asserts a position, it must follow the strong-default / shown-reasoning / easy-override / tracked-deviation pattern defined in Section 1.5. This is a Must for any assertion surfaced to the user.**

## 4.1 Product Lifecycle, Gates & Interaction Model

This is the orchestrating spine that turns the other features into a single coherent flow. It governs an AI use case from intake to deployment authorisation through a fixed, opinionated set of gates — encoding a best-practice governance lifecycle rather than offering a configurable workflow engine. This directly addresses the incumbent gap observed in practice: tools that hold assessment forms but do not orchestrate them toward a decision, leaving respondents unsure what is needed and reviewers without automated gating.

### 4.1.1 The gated lifecycle

A use case progresses through fixed gates; it cannot advance until the current gate's conditions are met:

- Vendor & product gates — the product's vendor and the product itself are checked against their approval status (4.1.4). Cascading: an uncleared vendor holds everything; an uncleared product holds its use cases. If clearance is missing, the relevant diligence is triggered. (MVP: the checks and holds; full diligence workflows deferred — see 4.1.4.)

- Intake / prohibited-practice hard stop — the use case is classified (4.4). If it resolves to a prohibited practice under the EU AI Act, the lifecycle halts here and surfaces this; it does not proceed to assessment. This is a strong, defensible opinion the product holds.

- Assessment gate — the required assessments for the use case's tier are run (AIIA per use case, with its feeding analyses). The gate is met when they are complete.

- Treatment gate — identified risks have treatment/mitigation plans in place.

- Authorisation gate — required sign-offs are obtained; the use case is authorised for deployment. Nothing reaches this state until all upstream gates are satisfied.

*MVP implementation: a determinate state machine over a fixed set of states and transitions — not a configurable engine. Because the states are known in advance, the orchestration is largely deterministic rules over captured context. States and sign-offs reuse the workflow/role requirements in 4.9.*

### 4.1.2 Lifecycle requirements

| **ID** | **Requirement** | **Priority** |
| --- | --- | --- |
| LFC-1 | Each use case carries a status reflecting its position in the fixed lifecycle (e.g., Requested → Vendor check → Under assessment → Treatment pending → Authorised for deployment; plus terminal Halted-prohibited and held states). | M |
| LFC-2 | Gating logic: a use case cannot transition to a later gate until the current gate's conditions are satisfied (e.g., cannot reach 'Authorised' until assessments, treatment plans and sign-offs are complete). | M |
| LFC-3 | Prohibited-practice hard stop at intake: a use case classified as a prohibited practice halts and surfaces the reason; it cannot proceed to assessment. | M |
| LFC-4 | Vendor and product gates read their approval status and hold progression if either is uncleared, cascading (vendor → product → use case). Full diligence workflows deferred — see 4.1.4 (APR). | M |
| LFC-5 | Deployment authorisation is recorded (record-only; no technical enforcement of deployment pipelines in MVP) and can be exported as an ATO-style authorisation document. | M |
| LFC-6 | The lifecycle is fixed and opinionated in the MVP (one sensible flow); configurability is out of scope. | M |

### 4.1.3 Interaction model — capture once, orchestrate in the background

The interaction model is what makes the lifecycle feel effortless to a user who does not know the process. It separates data capture from workflow orchestration:

| **ID** | **Requirement** | **Priority** |
| --- | --- | --- |
| IXN-1 | The user completes an uninterrupted registration/intake flow that captures the universal, knowable-up-front context: product/vendor, intended use(s), data touched, who is affected, deployment context. The user is not marched gate-by-gate during capture. | M |
| IXN-2 | A backend state machine then reasons over the captured context and drives the lifecycle: running the vendor check, classification, assessment scoping and risk identification, and transitioning the use case through gates automatically where context allows. | M |
| IXN-3 | Just-in-time, targeted data requests: the system asks the user for additional information ONLY when a transition requires it, and explains why (e.g., 'this use is high-risk, so a fundamental-rights analysis needs these three inputs'). It never asks up front for context that may not be needed. | M |
| IXN-4 | Legible status: the user sees where each use case is in the lifecycle, why, what is next, and whose court the ball is in (user / reviewer / vendor / system). Process state follows the same shown-reasoning principle as substantive assertions (1.5). | M |
| IXN-5 | Asynchronous sub-flows: steps that cannot complete synchronously (e.g., VDD, human catalogue curation, reviewer sign-off) run as background sub-flows with status updates, rather than blocking the user. | S |

### 4.1.4 Layered approval: vendor → product → use case (one lifecycle, three scopes)

Approval is not a single decision and is not generic per vendor. It operates at three inheriting scopes, each approving only what genuinely lives at that scope and inheriting clearance from the scope above:

- Vendor scope — 'is this organisation safe to deal with?' Security posture, financial stability, data-protection practices, certifications, sub-processors, breach history. Largely product- and use-case-independent; assessed once per vendor with a validity period.

- Vendor+Product scope — 'is this specific product acceptable?' Its data handling, residency, training-data practices, specific DPA terms. Two products from one approved vendor can differ here, so vendor approval does not imply product approval.

- Vendor+Product+Use-case scope — 'is it acceptable to use this product for this purpose in our context?' The risk-acceptance / deployment-authorisation decision, inherently per use case because impact is use-case-specific.

The fold: the use-case lifecycle is the primary engine, and its output rolls UPWARD. The first use case of a never-seen product does double duty — it authorises that use case AND generates most of the evidence that constitutes product-level approval (much of 'is this product acceptable?' is established by assessing the product in use). The first product from a never-seen vendor triggers the thin, genuinely vendor-level diligence as the outer gate. Subsequent use cases of an already-cleared product inherit vendor and product clearance and add only their own use-case assessment.

*Consequence for scope: this collapses 'VDD' from a separate parallel module into (a) a thin vendor-level diligence step (the part that does not emerge from use-case work — e.g. financial stability, breach history) plus (b) a product-level rollup VIEW over evidence the core use-case flow already captures. Net, this reduces the deferred surface area rather than adding to it.*

| **ID** | **Requirement** | **Priority** |
| --- | --- | --- |
| APR-1 | Data model reserves three inheriting approval scopes now: vendor (a product belongs to a vendor), vendor+product, and vendor+product+use-case, each with its own status. [Reserve now.] | M |
| APR-2 | Cascading gates: vendor clearance is a prerequisite for product clearance, which is a prerequisite for use-case authorisation. An uncleared vendor holds everything downstream. [MVP — gates read status.] | M |
| APR-3 | Inheritance & work-saving: a new use case of an already-cleared vendor+product inherits both upper clearances; the system tells the user they need only assess their specific use ('this vendor and product are already cleared'). | M |
| APR-4 | Upward rollup: completed use-case assessments contribute evidence to the product-level approval view, so product approval is largely constituted by use-case work rather than a separate questionnaire. | S |
| APR-5 | Thin vendor-level diligence (the genuinely vendor-specific part: financial stability, breach history, certifications not derivable from use-case work). [MVP captures status + basic record; full diligence workflow deferred.] | S |
| APR-6 | Full diligence workflows at vendor and product layers — questionnaires, evidence collection, security/privacy review, decision history. [Deferred post-MVP — now lighter, since product diligence is mostly the rollup of APR-4.] | C |
| APR-7 | Future synergy: for known SaaS vendors/products, the catalogue (4.3) pre-fills vendor- and product-level diligence facts (certifications, sub-processors, DPAs, residency) for reviewer confirmation — the prefill thesis applied to vendor/product risk. [Deferred; design intent noted.] | C |

## 4.2 AI System Register

| **ID** | **Requirement** | **Priority** |
| --- | --- | --- |
| REG-1 | User can register an AI system either by selecting a known product from the catalogue (see 4.3) or by describing a custom/in-house system. Structured metadata captured: name, owner, purpose, lifecycle stage, data used, deployment context. | M |
| REG-2 | A registered system has one or more use cases; each use case is classified by the classification engine (4.4) and displays its resulting EU AI Act tier. Classification attaches to the use case, not the system. | M |
| REG-3 | Each system shows, at a glance, its use cases, each use case's assessment status, and consolidated outstanding obligations (the rollup of AIIA-1b). | M |
| REG-4 | Re-classification is versioned; history is retained. | S |

## 4.3 Product Catalogue & Product-Driven Prefill

The core differentiator. A curated catalogue of known AI products (and the SaaS tools that embed them), each pre-mapped to relevant EU AI Act use-case taxonomy and enriched with confirmed facts drawn from public sources. The user selects the product they actually use; the system supplies what it knows so the user confirms or amends rather than researching from a blank form.

| **ID** | **Requirement** | **Priority** |
| --- | --- | --- |
| CAT-1 | Searchable catalogue of known AI products. User selects the product they are using (e.g., a named image-generation or text tool) instead of describing it from scratch. | M |
| CAT-2 | Each catalogue entry carries confirmed factual attributes (e.g., provider, model type/family where disclosed, modality, data-handling and sub-processor info, relevant transparency obligations) and the relevant EU AI Act use-case taxonomy tags. | M |
| CAT-3 | On selection, the system PREFILLS factual fields of the register and assessment. It does NOT assert a risk tier — tier always derives from the user's deployment context via the classification engine (4.4). | M |
| CAT-4 | Every prefilled fact shows provenance (source + last-checked date) and a confirm / amend control. Nothing is silently asserted; the user remains accountable for what they accept. | M |
| CAT-5 | Graceful fallback: if the product is not in the catalogue (or is custom/in-house), the user is routed into the guided decision tree (4.4) rather than a blank questionnaire. The product never depends on catalogue coverage to function. | M |
| CAT-6 | Catalogue entries are versioned and have a freshness/last-verified status; stale entries are flagged for re-verification. | S |
| CAT-7 | LLM-assisted enrichment drafts catalogue facts from vendors' public model cards, documentation and DPAs for human review before publishing. (Internal curation tooling.) | S |
| CAT-8 | Users can request a product be added; coverage gaps are tracked to prioritise curation. | C |

## 4.4 EU AI Act Risk Classification Engine

Promoted to its own feature because it is the gate that scopes everything downstream: the tier determines which obligations apply and how deep the AIIA must go. Classification runs per use case (a system with several use cases is classified several times — see AIIA-1a), because the tier is always a function of how the organisation USES the system, never of the product alone. Catalogue prefill (4.3) feeds facts in, but the deployment-context questions here decide the tier.

| **ID** | **Requirement** | **Priority** |
| --- | --- | --- |
| CLS-1 | A guided decision tree / questionnaire walks the user through deployment-context characteristics and assigns an EU AI Act risk tier: prohibited, high-risk, limited-risk, or minimal-risk. This is the fallback path when no catalogue product applies, and the confirmation path when one does. | M |
| CLS-2 | Classification logic references the relevant Annex/criteria (e.g., high-risk use cases, prohibited practices, transparency-only obligations) so the result is explainable, not a black box. | M |
| CLS-3 | The result captures a written rationale and the answers that led to it, for audit defensibility. | M |
| CLS-4 | The assigned tier scopes the AIIA: it determines which sections/obligations become mandatory, recommended, or not applicable (see 4.5, AIIA-2). | M |
| CLS-5 | Classification is versioned; re-classification on material change is tracked with history. | S |
| CLS-6 | Surfaces the obligation set triggered by the tier (e.g., conformity assessment, technical documentation, transparency notices) as a checklist. | S |

## 4.5 AI System Impact Assessment (AIIA) — primary assessment, ISO/IEC 42005-aligned

The center of gravity. The AIIA is the primary, defensible impact-assessment record, structured to ISO/IEC 42005, with FRIA, DPIA-style and model/system-risk analyses as sections that feed into it rather than separate documents.

Unit of assessment — one AIIA per use case. A system is the registered entity, but impact is a function of the context of use: the same system used for internal knowledge search versus an HR or eligibility decision carries materially different impact. Therefore each materially distinct use case of a system gets its own AIIA, with its own EU AI Act classification, risk set, residual risk and sign-off. A system-level view rolls these up for inventory and reporting. This keeps the system central (satisfying the 'it is a system impact assessment' reading of 42005) while giving each context of use the individual analysis an auditor can interrogate — e.g., 'show me the impact analysis for the HR use specifically.'

| **ID** | **Requirement** | **Priority** |
| --- | --- | --- |
| AIIA-1 | A structured AIIA template aligned to ISO/IEC 42005 (e.g., system description and intended use, stakeholders and affected individuals, benefits, potential harms/impacts, likelihood and severity, mitigations, residual risk, sign-off). Harm identification is driven by the Risk Library (4.7) rather than left to the user's recall. | M |
| AIIA-1a | Data model: a system has one or more use cases; each use case has exactly one AIIA. Classification (4.4), relevant risk set (4.7), residual risk and sign-off all attach at the use-case/AIIA level, not the system level. | M |
| AIIA-1b | System-level rollup view aggregates the use-case AIIAs: overall coverage ('are all use cases assessed?'), highest tier present, and consolidated outstanding obligations — for inventory and reporting. | M |
| AIIA-2 | The AIIA's required sections and depth are scoped by the use case's EU AI Act tier from 4.4 — a high-risk use case surfaces the full set; a minimal-risk one is appropriately light. | M |
| AIIA-3 | FRIA, DPIA-style and model/system-risk analyses are first-class sections that feed the AIIA; facts entered once propagate, so they are not re-keyed across documents. | M |
| AIIA-4 | The AIIA pre-fills from the system register and classification, so known facts are never re-entered. | M |
| AIIA-5 | Each answer/finding can attach evidence and link to one or more controls (see 4.6). | M |
| AIIA-6 | AI-assisted drafting suggests text and flags gaps/inconsistencies; suggestions are clearly marked and require human acceptance. Conclusions and risk acceptance remain human acts. | S |
| AIIA-7 | The AIIA is versioned and can be re-run/refreshed on a schedule or trigger (e.g., material change, re-classification). | S |
| AIIA-8 | Residual-risk summary/heat view across systems, drawn from completed AIIAs. | C |

## 4.6 Unified Control Library & Cross-Mapping

| **ID** | **Requirement** | **Priority** |
| --- | --- | --- |
| CTL-1 | Pre-loaded control set for ISO/IEC 42001 (Annex A controls) and EU AI Act obligations. | M |
| CTL-2 | Cross-map relationships so a single piece of evidence/answer can satisfy controls in both frameworks simultaneously. | M |
| CTL-3 | Control coverage view: per framework, show which controls are satisfied, partial, or open. | M |
| CTL-4 | Data model designed to add further frameworks later without rework. | S |

## 4.7 Risk Library (seed risk taxonomy)

The missing knowledge layer for risk identification. A layered, source-attributed library of what can actually go wrong with an AI system, so that harm identification in the AIIA is driven by curated expertise rather than the user's imagination. Risks sit at different layers and a given system draws only the relevant subset — that selective relevance is the opinionated intelligence.

**Layers and MVP seed sources:** 

- Technical / application-layer security — seeded in full from the OWASP Top 10 for LLM Applications (e.g., prompt injection, insecure output handling, training-data poisoning).

- Governance / fundamental-rights layer — seeded from NIST AI RMF and ISO/IEC 42001/42005 risk themes (bias and fairness, transparency, human oversight, harms to rights and safety).

- Deferred to post-MVP: adversarial-threat depth (MITRE ATLAS). The data model should accommodate it without rework.

| **ID** | **Requirement** | **Priority** |
| --- | --- | --- |
| RSK-1 | Human-curated, source-attributed risk entries. Each carries: source framework, layer, description, typical triggers, and links to mitigating controls (tying into the Control Library, 4.6). | M |
| RSK-2 | MVP seed = OWASP Top 10 for LLMs (full) + a curated NIST/ISO governance & fundamental-rights layer. | M |
| RSK-3 | The library feeds the AIIA harm identification: based on system type, modality and EU AI Act tier, the product PROPOSES a relevant subset of risks for the user to confirm/amend (per the §1.5 pattern). It does not dump the full library on the user. | M |
| RSK-4 | Catalogue products (4.3) can carry typical associated risks, so product selection prefills likely risks (e.g., image generator → provenance/deepfake/IP; LLM chatbot → OWASP LLM set). | S |
| RSK-5 | AI enhancement: suggest which seed risks apply to a described system, draft risk descriptions and candidate mitigations from context, and flag gaps ('similar systems usually also flag X'). All AI-generated content is clearly marked and human-confirmed before it enters an assessment. | S |
| RSK-6 | AI-assisted freshness: surface when seed sources have new revisions (e.g., an OWASP update) or when incident patterns suggest an emerging risk class, for curator review. | S |
| RSK-7 | The AI never authors ground-truth risks unconfirmed: the library's authority derives from named frameworks; AI proposes relevance and drafts, humans own what lands. Unsourced AI-invented risks must not be presented with the same authority as seed entries. | M |

## 4.8 Evidence & Audit Trail

| **ID** | **Requirement** | **Priority** |
| --- | --- | --- |
| EVD-1 | Central evidence repository; evidence can be reused across assessments and controls. | M |
| EVD-2 | Immutable, timestamped audit log of every create/edit/approve/export action with actor identity. | M |
| EVD-3 | Evidence requests can be assigned to a contributor with due dates and reminders. | S |
| EVD-4 | Evidence freshness/expiry flags. | C |

## 4.9 Workflow, Review & Sign-off

Governance roles are modelled on three lines of defence and are deliberately separated from account administration. Administration (managing members, assigning roles, configuring the org) carries no governance capability: governance is exercised only through explicitly granted governance roles, and those roles are constrained by separation of duties. This matters doubly for a product whose own subject is governance — a role model that let one person both perform and approve would undermine the discipline the product sells.

### 4.9.1 Roles & separation of duties

Two distinct axes:

- **Administrative role** — account level only: manage members, assign governance roles, configure org settings. Admin is *not* a governance role and confers *no* governance power; being an admin grants no sign-off authority. Assigning governance roles is the only point at which administration touches governance, which is why self-assignment is closed (WKF-6).

- **Governance roles** — the SoD-constrained functional roles, organised on three lines of defence:
  - **1st line — own / provide.** *System/product owner* (registers the system/use case, provides and confirms the facts, owns the use case) and *Contributor* (supplies requested evidence/facts). Both are 1st-line "doing" roles and may be co-held.
  - **2nd line — review / authorise.** *Reviewer* (reviews and signs off classification, FRIA and the AIIA; recommends) and *Authoriser* (accepts residual risk and grants deployment authorisation / ATO). These two are **separated**: the party that recommends cannot be the party that accepts the risk.
  - **3rd line — assure.** *Auditor* (independent, read-only assurance that the process was followed).

Separation of duties is enforced as a **conflict matrix at the point of role assignment**: a user cannot be granted a governance role that conflicts with one they already hold. Every cross-line pair conflicts (an owner/contributor cannot review, authorise or audit; a reviewer cannot audit; reviewer and authoriser cannot be co-held); within a line, only *owner + contributor* compose. Because that one composable pair exists, the rule is a matrix rather than a blanket "one governance role per person".

Governance roles are **tenant-scoped** in the MVP — a user holds a role org-wide rather than per system, so they pick a lane across the tenant. Object-scoped assignment (different roles on different systems) is a deliberate later extension and is designed to be **additive, not a rewrite**: a nullable scope on the assignment (NULL = tenant-wide, preserving every existing grant) plus a scope-aware conflict check, leaving the role catalogue and conflict matrix unchanged.

Because the interaction model captures context once and orchestrates gates in the background (4.1.3), roles define *who is eligible* to act at each gate; the state machine decides *when* an action is required and routes it to an eligible, non-conflicting holder. Filling the intake is a 1st-line act (providing context); the judgement acts the gates demand — review, authorisation, audit — remain with the separated 2nd/3rd-line roles. Capture-once and separation of duties therefore coexist: provision and judgement are different acts held by different roles.

| **ID** | **Requirement** | **Priority** |
| --- | --- | --- |
| WKF-1 | Two role axes: an administrative role (account management only) and SoD-constrained governance roles (owner, contributor, reviewer, authoriser, auditor) organised on three lines of defence. Admin confers no governance capability. | M |
| WKF-2 | Review queue; reviewers can comment, request changes, and formally approve with attribution. | M |
| WKF-3 | Status lifecycle for assessments (draft → in review → approved → needs refresh). | M |
| WKF-4 | Notifications for assignments, approvals and due dates. | S |
| WKF-5 | Governance-role assignment enforces a separation-of-duties conflict matrix: a user cannot hold conflicting roles. Reviewer and authoriser are separated; an owner/contributor cannot review, authorise or audit the same tenant's work. | M |
| WKF-6 | Self-assignment of governance roles is blocked: an admin cannot grant governance roles to themselves, closing the only administration→governance escalation path. (Reviewable later if a real need emerges.) | M |
| WKF-7 | Governance roles are tenant-scoped in the MVP; the assignment model reserves room for later object-scoped (per-system) assignment without rework. | S |
| WKF-8 | Every governance-role grant and revoke is written to the immutable audit trail with actor, subject, role and timestamp. | M |

## 4.10 Audit / Export Pack

| **ID** | **Requirement** | **Priority** |
| --- | --- | --- |
| EXP-1 | Generate an export pack (PDF + structured data) for a system or a framework, including assessments, evidence, control mapping and the audit trail. | M |
| EXP-1a | Generate an ATO-style deployment-authorisation document for an authorised use case (records the basis on which deployment was approved). | M |
| EXP-2 | Read-only auditor access scoped to a system or engagement. | S |
| EXP-3 | Branded/templated export for the buyer's own reporting. | C |

# 5. Where Automation Lives

A deliberate note, because the MVP's differentiator is automation but its center of gravity is human-judgement assessments. These must not conflict. Automation is applied only where it accelerates without undermining defensibility:

- Product-driven prefill: selecting a known product pulls confirmed facts and use-case taxonomy from the catalogue, removing the research burden from the user. (Facts only — never the tier; always confirmed by the user.)

- Cross-mapping: one answer/evidence item automatically propagates to all linked controls across both frameworks. (The single biggest time-saver.)

- Pre-fill: register data and risk classification flow into new assessments automatically.

- AI-assisted drafting & gap detection: suggests wording and flags missing or inconsistent answers — always marked as a suggestion, always requiring human acceptance.

- Evidence chasing: automatic assignment, reminders and freshness flags.

- Regulatory mapping maintenance (internal): a process to keep control mappings current as guidance evolves.

*What is deliberately NOT automated: the assessment conclusion itself, risk acceptance decisions, and sign-off. These remain human acts, by design, so the output survives scrutiny.*

# 6. Non-Functional Requirements

| **Area** | **Requirement** |
| --- | --- |
| Security | SOC 2 controls implemented from day one; encryption at rest and in transit; SSO/SAML for the enterprise tier. |
| Data residency | EU data residency option (the ICP sells into the EU). |
| Multi-tenancy | Strict tenant isolation; row-level separation. |
| Auditability | Audit log is append-only and exportable. |
| Reliability | Defined backup/restore; basic uptime targets appropriate to early stage. |
| Privacy | GDPR-aligned data handling; DPA available; minimal PII collection. |
| Usability | A non-technical compliance user can complete an assessment without training. |

# 7. Success Metrics

## 7.1 Product validation (design-partner phase)

- Time to complete a first full assessment, vs. the partner's current spreadsheet/Word process (target: meaningful reduction).

- Evidence reuse rate — % of evidence items satisfying more than one control.

- Number of assessments that survived contact with a real auditor without rework.

- Override rate on the product's default classifications and recommendations — the key signal of whether the opinionated defaults are right. A low, stable override rate (with overrides clustering on genuinely ambiguous cases) validates the opinions; a high or scattered rate shows where defaults need adjustment.

- Acceptance vs. resistance: do users trust and act on the defaults, or work around them?

- Weekly active use by the champion during the program.

## 7.2 Commercial validation

- At least 2–3 design partners converting to paid at GA.

- 1–2 partners willing to be a public reference / case study.

# 8. Build Sequence (suggested)

Order matters: build the spine (data model + control library), then the assessment flow on top of it, then evidence/export, then the automation layer.

- Foundations: data model for systems, use cases, vendors and products with three inheriting approval scopes (vendor / vendor+product / vendor+product+use-case), controls, cross-maps, risks, evidence, audit log, and lifecycle states; auth, plus the tenant governance role model and SoD enforcement (admin vs governance roles, conflict matrix, blocked self-assignment) — built before the assessment flow that consumes it, since the gates route work to eligible role-holders.

- Control library + cross-mapping (ISO 42001 ↔ EU AI Act).

- Risk Library seed (OWASP LLM in full + curated NIST/ISO governance/rights layer), with risk-to-control links.

- AI system register + use-case intake flow (uninterrupted context capture).

- Product catalogue + product-driven prefill (seed narrowly with the products design partners actually use), with the guided fallback path.

- EU AI Act risk classification engine (per use case; consumes catalogue facts, decides tier from deployment context; prohibited-practice hard stop).

- AIIA engine, ISO/IEC 42005-aligned (one per use case, tier-based scoping, FRIA/DPIA/model-risk as feeding sections, pre-fill, evidence linking).

- Lifecycle state machine + cascading gates (vendor → product → intake → assessment → treatment → authorisation) and the background orchestration / just-in-time data requests / status surfacing; use-case evidence rolls up to product approval.

- Review/sign-off workflow + audit trail surfacing.

- Export/audit pack + ATO-style deployment authorisation.

- Automation accelerants (AI-assist drafting, gap detection, evidence chasing).

# 9. Open Questions & the Discovery Approach

Discovery model: because the market lacks the expertise to specify the 'correct' product, discovery does not ask partners what to build. Instead, the opinionated MVP is built first, and partners critique something tangible — 'here is how and why the product classifies and assesses this; show me where it is wrong.' A wrong-but-concrete opinion elicits far better feedback than an abstract questionnaire. Post-MVP discovery then adjusts the defaults where they prove wrong in practice.

The questions below are therefore framed as reactions to the built product, not as requirements-gathering:

- When the product hands you a confident, reasoned classification or assessment, do you trust it and accept it — or do you fight it? Where is the line between helpful opinion and overreach?

- Which 30–50 AI products do your teams actually use? (This is the initial catalogue seed list — coverage of these is what makes or breaks the demo.)

- Does the fixed lifecycle (vendor → intake → assessment → treatment → authorisation) match how approvals actually flow in your org, or are there gates we're missing or over-imposing?

- At intake, how much context can a requester realistically supply up front before they get stuck — i.e., where is the natural boundary between 'capture once' and 'ask just-in-time'?

- When a system owner or BISO fills in an assessment today, where exactly do they get stuck — and is it the use-case mapping, the product facts, or something else?

- For your catalogued products, which public sources do you trust for the facts (model cards, DPAs, sub-processor lists), and how current do they need to be?

- Within the AIIA, which feeding analysis is most painful today — FRIA, DPIA, or model risk? Build that section deepest first.

- Does your certification body expect the impact assessment to follow ISO/IEC 42005 structure explicitly, or is alignment in substance enough?

- What does your auditor actually accept as evidence? What format must the export take?

- Who signs off on a high-risk classification in your organisation, and what do they need to see?

- How are you running impact assessments today, and what specifically is slowest?

- Does the EU AI Act tier genuinely change how deep your impact assessment goes, or do you assess everything to the same depth regardless?

- Would cross-mapping to a third framework (e.g., NIST AI RMF) change the buying decision?

- What single thing, if this tool did it, would make you switch from your current process?

# 10. Key Product Risks

| **Risk** | **Mitigation** |
| --- | --- |
| Product catalogue coverage is too thin to be useful, or facts go stale. | Seed the catalogue narrowly around the products design partners actually use (deep, not broad); treat curation as a staffed, ongoing function with freshness flags and LLM-assisted enrichment under human review; degrade gracefully to the guided path when a product is absent. |
| Catalogue is misread as asserting a risk tier, producing confident wrong classifications. | Hard rule: the catalogue supplies facts only; tier is always derived from deployment context. Show provenance and require confirmation on every prefilled fact. |
| Control mappings go stale as regulation/guidance evolves. | Treat mapping maintenance as a core ongoing function, not a one-off; design the data model for versioned mappings. |
| Risk Library curation is heavy, or AI enhancement invents unsourced risks. | Seed shallow but correct for MVP (OWASP LLM full + curated NIST/ISO layer); defer ATLAS. Keep the seed human-curated and source-attributed; AI only proposes relevance/drafts/freshness and is always human-confirmed (RSK-7). |
| Over-fitting the product to one vocal design partner. | Triangulate across all partners; only build shared pain into the core. |
| Automation perceived as undermining defensibility. | Keep human sign-off mandatory; mark all AI suggestions clearly. |
| The product's own role model lets one person both perform and approve — undermining the separation of duties the product exists to enforce. | Governance roles are SoD-constrained by a conflict matrix enforced at assignment; reviewer and authoriser are separated; admin carries no governance power and cannot self-assign governance roles (see 4.9.1). |
| Scope creep from exciting-but-later features (discovery, monitoring, agents). | Hold the line on Section 3.2; revisit only after GA. |
| The backend orchestration / state machine is over-engineered into a general workflow engine. | MVP implements only the fixed, known set of states and transitions (determinate rules over captured context); configurability and a general event engine are explicitly out of scope (LFC-6, 3.2). |
