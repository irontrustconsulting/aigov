# Product Requirements Document — IronTrust

## AI Governance Platform · ISO/IEC 42001, ISO/IEC 42005, and EU AI Act aligned

**Version:** 2.0 · supersedes all prior PRDs
**Priority:** `M` = Must · `S` = Should · `C` = Could (all for MVP)
**Lanes:** conceptual model → `DOMAIN.md` · constraints → `INVARIANTS.md` (`INV-n`) · rationale → `DECISIONS.md` (`D-n`) · physical schema → `DATA-MODEL.md` · implementation state → `STATE.md`. This document is the spec. The data model responds to design; it is not fixed here.

---

# 1. Document purpose

This PRD defines the product vision, scope, domain model, functional requirements, and architectural principles for an AI governance SaaS platform that operationalises a risk assessment methodology integrating:

- ISO/IEC 42001 AI management system requirements
- ISO/IEC 42005 AI system impact assessment
- EU AI Act risk classification and regulatory obligations
- AI-specific technical, data, operational, legal, and ethical risks
- Taxonomy-driven, prefill-assisted assessment workflows

---

# 2. Product identity

**A standards-compliant product first; intelligent, AI-driven, and idiot-proof on top.** Where user-friendliness and standards fidelity pull against each other, fidelity wins, and the craft goes into hiding the complexity rather than removing it.

**The product is opinionated and self-service.** It ships one methodology, one lifecycle, one role model, and one set of hard stops. It does not offer a configurable workflow engine, a questionnaire builder, or a per-tenant policy engine. It holds defensible positions and asks the user to confirm or deviate from them, recording the deviation.

The product is sold to and operated by the organisation itself, not delivered through a consulting engagement. Tenant-configurable methodology is a later additive layer over the same engine, not an MVP capability.

**Every artifact the product emits carries a standards conformance target**, not an internally invented shape:

| Artifact | Conformance target |
|---|---|
| AI system inventory | ISO/IEC 42005 AI system record |
| Impact assessment | ISO/IEC 42005 |
| Risk register | The ISO/IEC 42001 risk register an auditor asks for by name |
| Statement of Applicability | The ISO/IEC 42001 SoA |
| Authorisation record | Point-in-time, structured, defensible |

---

# 3. Product vision

Instead of presenting a large generic questionnaire, the platform will:

1. Ask whether the organisation should be doing this kind of thing at all, before asking about any supplier.
2. Let the user select a known product from a curated catalogue instead of describing it from scratch.
3. Use controlled business-language taxonomies to minimise free text.
4. Derive the EU AI Act tier from how the organisation uses the system, and scope the assessment's rigour to it.
5. Apply safe, source-attributed prefills, and ask only the unresolved, organisation-specific questions.
6. Propose the relevant risks and the controls that mitigate them.
7. Score inherent and residual risk from a shipped methodology.
8. Carry those risks into a per-system risk register, and roll them up into an organisation-wide register.
9. Route treatment, review, and authorisation to the right roles under separation of duties.
10. Produce audit-ready outputs: the inventory, the register, the SoA, the coverage view, and the authorisation record.

The intended experience:

> Select what you want to do and the product you want to do it with, review what the platform already knows and proposes, provide only what it cannot know, and approve or deviate from its conclusions.

---

# 4. Product objectives

The product shall:

- Reduce the time required to perform an AI impact assessment.
- Minimise free-text input through controlled taxonomies and product-driven prefill.
- Improve consistency across assessors and organisations by shipping one methodology.
- Translate ISO/IEC 42001, ISO/IEC 42005, and EU AI Act requirements into operational workflows.
- Provide traceability from context to classification, risks, scoring, controls, treatment, evidence, and authorisation.
- Answer, for any organisation, the question its incumbents cannot: what are the current AI risks to this organisation.
- Automate routine derivation while preserving human accountability for every judgement.
- Maintain a reusable curated library of risks, controls, obligations, products, and mappings.
- Support reassessment of an AI system across its lifecycle.

---

# 5. Target users

**Primary buyer:** mid-market organisations needing defensible, completable AI governance.

**Users:** AI system owners, contributors, compliance and GRC teams, risk managers, information security teams, internal and external auditors.

**Design constraint:** the system owner is a first-line governance role *and* a compliance layperson simultaneously. Both are true. The product must not require them to read legal register to describe their own system.

---

# 6. Core design principles

## 6.1 The product spine

Every position the product asserts follows **strong default → shown reasoning → easy override → tracked deviation**. It proposes a confident, standards-grounded answer; shows the basis; accepts a low-friction deviation; records it. This applies to classification, prefill, risk proposal, scoring, and applicability alike.

## 6.2 Structured input before free text

Controlled selections are preferred over free text. Free text is reserved for: organisation-specific context, deviation rationale, override justification, evidence descriptions, mitigation plans, and SoA exclusion justifications.

## 6.3 The corpus and the tenant plane

Two planes, and the line between them is mechanical rather than adjudicated case by case:

- **GLOBAL corpus** — catalogue facts, the risk and control libraries, their cross-maps, the taxonomies and the bridge, methodology defaults and seeded impacts, section templates, the decision tree. Curated, source-attributed, and **not tenant-overrideable**. Its authority derives from being sourced to named frameworks, which leaks away one edit at a time if tenants can rewrite it. Corrected by central curation only.
- **Tenant plane** — everything the product proposes or computes about a tenant's own AI systems. **Overrideable**, with the deviation recorded and disclosed.

Catalogue IP is protected not by un-editability but by scope: a tenant holds only their own copy, so a deviation changes the instance and never the source.

Immutable records — the audit log, the authorisation snapshot, signed-off classification history — are locked by their own integrity rules. A deviation produces a new version; it never mutates history.

## 6.4 The four prefill states

The platform always preserves the distinction between: catalogue default, prefilled value, user-confirmed effective value, and overridden value. **Operational reality supersedes vendor documentation.** Low-confidence values are never silently applied; they are surfaced as suggestions or as additional questions.

## 6.5 Inventory versus analysis

The inventory holds the standing description of an AI system, answerable at registration without having assessed anything. The assessment holds the analysis. Anything requiring assessment thinking belongs to the assessment and is linked from the inventory, never duplicated. Where an attribute sits on the line, its home is the side where it is first produced.

## 6.6 Capture once

Context is captured once and orchestrated in the background. The same fact is never re-keyed across inventory, classification, assessment, and feeders. Roles define who is eligible to act at each gate; the state machine decides when an act is required and routes it.

## 6.7 Human accountability

Automated outputs are explainable and reviewable. **Deliberately not automated:** the assessment conclusion, risk acceptance, and sign-off. These remain human acts so the output survives scrutiny.

## 6.8 Single home

Each truth has one home and is cross-linked, never duplicated.

---

# 7. Domain model

## 7.1 Vocabulary

| Term | Meaning | Plane |
|---|---|---|
| **Use case** | The abstract, product-independent kind of application, in business language: "automated interview scoring". Cleared once, organisation-wide. | GLOBAL |
| **Vendor** | The supplier organisation. Holds reusable vendor-level facts and a vetted status. | GLOBAL / tenant status |
| **Product** | The tenant's registered instance of a catalogue item, or a custom/in-house system: "Workday AI". The grouping layer. | Tenant |
| **AI System** | A Product realised for an approved use case: "Workday AI for automated interview screening". The assessable, inventoried unit per ISO/IEC 42005. | Tenant |
| **AIIA** | AI System Impact Assessment. ISO/IEC 42005-aligned. One current per AI System, with retained history. | Tenant |
| **Feeder** | A feeding analysis contributing sections to an AIIA: FRIA, DPIA, MODEL_RISK. Not separate documents. | Tenant |
| **EU AI Act subcategory** | The specific regulated practice, carrying the tier, fixed by law. | GLOBAL |
| **Tier** | `PROHIBITED`, `HIGH`, `LIMITED`, `MINIMAL`. Scopes assessment rigour. | Tenant (per AI System) |
| **Bridge** | The reference path translating a business use case into its governing EU AI Act subcategory. | GLOBAL |
| **System risk register** | Per AI System: its identified risks, scores, suggested controls, and treatment state. The working surface. | Tenant |
| **Risk register** | Unqualified, the organisation-level register: rolled-up system risk registers plus governance risks. The ISO 42001 audit artifact. | Derived |
| **Exception** | An owned, justified, time-bound acceptance of a named governance gap. | Tenant |
| **ATO** | Authorisation to Operate. Point-in-time record of the basis on which deployment was authorised. | Tenant |

**AI System = Product + use case.** Two AI Systems may share a use case (different products) or a product (different use cases). Same-use-case AI Systems remain separate assessments, because deployment context differs and derives different risk profiles.

## 7.2 The governed flow

1. **Use-case gate** — should the organisation do this kind of thing at all? Product-independent. Prohibition resolves here.
2. **Product gate** — is this product from this vendor acceptable? Vendor vetting is a step within it.
3. **Registration** — the AI System enters the inventory as an ISO 42005 record.
4. **Classification** — the first step of assessment. Bridge or context wizard. Authoritative on reviewer sign-off.
5. **AIIA** — identification only. Proposes risks and suggested controls; the user acknowledges or dismisses each.
6. **Scoring** — each identified risk scored; lands on the system risk register.
7. **Review** — the AIIA is approved on identification and scoring.
8. **Treatment** — a distinct phase on the system risk register. Propose and ratify.
9. **Authorisation** — the ATO, against a single condition set.
10. **Outputs** — register, coverage, SoA, audit pack.

---

# 8. Functional requirements

## 8.1 Cross-cutting (XCUT)

| ID | Requirement | Pri |
|---|---|---|
| XCUT-1 | Wherever the system asserts a position surfaced to the user, it follows the product spine: strong default, shown reasoning, easy override, tracked deviation. | M |
| XCUT-2 | **Plain-versus-formal wording.** The same facts are presented in two registers of language. Compliance-expert roles (reviewer, authoriser, auditor) read formal compliance and legal terminology. First-line roles (system owner, contributor) read plain language. Final outputs and read-only records carry formal wording regardless of reader. Implemented as a single-homed label map: each concept maps once to its plain and its formal label, applied by role and surface, never hand-written per screen. | M |
| XCUT-3 | GLOBAL corpus values are not tenant-overrideable. Tenant-plane proposed and computed values are overrideable with the deviation recorded. | M |
| XCUT-4 | Every override of a system proposal is disclosed to the reviewer at decision time, showing the original proposal, the override, and the rationale. No direction test; no exemptions. Presentation may emphasise, but disclosure is absolute. | M |
| XCUT-5 | No raw enum or internal code is surfaced to a user; all user-facing vocabulary resolves through the label map. | M |

## 8.2 Lifecycle and gates (LFC)

| ID | Requirement | Pri |
|---|---|---|
| LFC-1 | Each AI System carries a status reflecting its position in a fixed lifecycle, plus terminal and held states. | M |
| LFC-2 | An AI System cannot transition to a later gate until the current gate's conditions are satisfied. | M |
| LFC-3 | **Prohibited-practice hard stop resolves at the use-case gate**, organisation-level, once per use case, independent of any product. A prohibited use case halts and surfaces the reason; no AI System under it proceeds. | M |
| LFC-4 | The use-case and product gates read clearance status and hold progression if either is uncleared, cascading outward-in. | M |
| LFC-5 | Deployment authorisation is recorded (record-only; no technical enforcement of pipelines) and is exportable. | M |
| LFC-6 | The lifecycle is fixed and opinionated. Configurability is out of scope. | M |
| LFC-7 | **Governance-completeness is a posture distinct from lifecycle state.** An AI System that is registered but unassessed is a tracked governance finding, not a neutral waiting state. The platform reports the count of ungoverned AI Systems. | M |
| LFC-8 | **Treatment is a distinct phase**, entered after AIIA approval and completed before authorisation. | M |
| LFC-9 | Reviewer and authoriser gates are human acts and are never auto-advanced. | M |

## 8.3 Interaction model (IXN)

| ID | Requirement | Pri |
|---|---|---|
| IXN-1 | An uninterrupted intake flow captures the universal, knowable-up-front context. The user is not marched gate-by-gate during capture. | M |
| IXN-2 | A backend state machine reasons over the captured context and drives the lifecycle, transitioning where context allows. | M |
| IXN-3 | Just-in-time, targeted data requests: the platform asks for more only when a transition requires it, and explains why. | M |
| IXN-4 | Legible status: the user sees where each AI System is, why, what is next, and whose court the ball is in. | M |
| IXN-5 | Asynchronous sub-flows run in the background with status updates rather than blocking the user. | S |

## 8.4 Use-case and product clearance (APR)

| ID | Requirement | Pri |
|---|---|---|
| APR-1 | **The use-case gate is outermost.** Before any supplier question, the platform asks whether the organisation should perform this kind of application at all. Clearing it whitelists the use case organisation-wide. | M |
| APR-2 | The organisation's approved use cases are a first-class artifact: the AI applications this organisation has sanctioned. | M |
| APR-3 | **The product gate sits inside the use-case gate.** It answers whether this product from this vendor is acceptable. | M |
| APR-4 | **Vendor vetting is a step within product approval, never a standalone gate.** No approval terminates at a vendor. The approved list is products with their vendors, never bare vendors. | M |
| APR-5 | Vendor is an entity holding reusable vendor-level facts (DPA, sub-processors, residency, security posture, certifications) and a vetted status. A vetted vendor short-circuits the vetting step for that vendor's later products. | M |
| APR-6 | Inheritance and work-saving: a second product for an approved use case starts at the product gate; a second product from a vetted vendor skips vendor vetting. The platform tells the user what they need not repeat. | M |
| APR-7 | Clearance means not-blacklisted. It is a prerequisite for authorisation and is never authorisation itself. | M |
| APR-8 | For known SaaS, the catalogue prefills vendor and product diligence facts for confirmation. | C |
| APR-9 | Full diligence workflows at vendor and product layers (questionnaires, evidence collection, decision history). | C |

## 8.5 AI System inventory (REG)

| ID | Requirement | Pri |
|---|---|---|
| REG-1 | Register an AI System by selecting an approved use case and a product, either from the catalogue or described as custom/in-house. | M |
| REG-2 | **The AI System record is an ISO/IEC 42005 record**, carrying: identification and alternative identifiers, life-cycle stage, a description of what it does and at a high level how it works, functionalities and capabilities (current and planned), dependencies on other systems, purpose and expected outcomes, intended use, and deployment environment (geography, languages, and the technical environment). | M |
| REG-3 | Attributes a third-party deployer cannot reasonably hold (detailed data and algorithm/model information) are marked as-available and do not render the record non-conformant. | M |
| REG-4 | Ownership and organisational attributes: business owner, technical owner, organisation, criticality. | M |
| REG-5 | The product view rolls up its AI Systems: each one's assessment status, the highest tier present, and consolidated outstanding obligations. | M |
| REG-6 | An AI Systems inventory export answers an auditor's request for the inventory without further assembly. | M |

## 8.6 Product catalogue and product-driven prefill (CAT)

| ID | Requirement | Pri |
|---|---|---|
| CAT-1 | Searchable catalogue of known AI products; the user selects the product they use instead of describing it. | M |
| CAT-2 | Each entry carries confirmed factual attributes (provider, model type/family where disclosed, modality, data handling, sub-processors, transparency characteristics, human oversight capabilities) and its business-taxonomy tags. | M |
| CAT-3 | **Catalogue selection prefills facts. It never asserts a tier.** Tier always derives from deployment context via the classification engine. | M |
| CAT-4 | Every prefilled fact shows provenance (source and last-checked date) and a confirm control. Nothing is silently asserted. | M |
| CAT-5 | Graceful fallback: a product not in the catalogue, or custom/in-house, routes into the guided decision tree, never a blank questionnaire. The product never depends on catalogue coverage to function. | M |
| CAT-6 | Entries are versioned with a freshness/last-verified status; stale entries are flagged for re-verification. | S |
| CAT-7 | AI-assisted enrichment drafts catalogue facts from public model cards, documentation, and DPAs for human curation before publishing. | S |
| CAT-8 | Users can request a product be added; coverage gaps are tracked to prioritise curation. | C |

## 8.7 Taxonomy and the bridge (TAX)

| ID | Requirement | Pri |
|---|---|---|
| TAX-1 | **A user-facing business vocabulary** of hierarchical use-case categories in familiar language, which the registration wizard drills through. A product may belong to many. | M |
| TAX-2 | **A governance vocabulary** of EU AI Act categories and subcategories, where the subcategory carries the tier, fixed by law. | M |
| TAX-3 | **The bridge**: a many-to-many mapping from business use case to EU AI Act subcategory, with a primary marking the proposed default. Per the single-governing-tier rule, the primary points at the highest-risk applicable subcategory: propose the stricter classification and let the user justify down. | M |
| TAX-4 | A business use case with no EU AI Act trigger carries no primary mapping and routes to the context-question wizard. This is the designed path for minimal-risk applications, not an exception. | M |
| TAX-5 | Supporting controlled vocabularies: AI system types, deployment contexts, data categories, affected parties, human oversight types. | M |
| TAX-6 | Taxonomy records are versionable, activatable, orderable, and extensible without code changes. Values in use are deactivated, never deleted. | M |
| TAX-7 | Each bridge mapping carries its mapping confidence and its legal reference, so the basis is inspectable. | S |

## 8.8 EU AI Act classification (CLS)

| ID | Requirement | Pri |
|---|---|---|
| CLS-1 | **Classification is the first step of assessment**, not part of registration. It is analysis, not description. | M |
| CLS-2 | Two resolution paths, one tier vocabulary: the **bridge** auto-resolves from the declared use case and catalogue facts where a primary mapping exists; the **context-question wizard**, a versioned decision tree, resolves by structured Q&A when it does not. | M |
| CLS-3 | **The tier is always a function of how the organisation uses the system, never of the product alone.** | M |
| CLS-4 | Classification logic references the relevant Annex or Article so the result is explainable, not a black box. | M |
| CLS-5 | The result captures a written rationale and the answers that led to it. | M |
| CLS-6 | The assigned tier scopes the AIIA: it determines which sections are mandatory, recommended, or not applicable. | M |
| CLS-7 | Classification is authoritative only on reviewer sign-off. Resolution and persistence are strictly separate; resolution is fail-closed. | M |
| CLS-8 | `MINIMAL` is only ever an affirmative determination, never a fallback default. | M |
| CLS-9 | Classification is versioned and snapshotted; history is retained. | M |
| CLS-10 | The tier's triggered obligation set is surfaced as a checklist. | S |

## 8.9 AI System Impact Assessment (AIIA)

| ID | Requirement | Pri |
|---|---|---|
| AIIA-1 | **One current AIIA per AI System**, ISO/IEC 42005-aligned, with a retained history of superseded versions. The constraint is currency, not lifetime count. | M |
| AIIA-2 | The AI System is the unit of assessment. Two AI Systems sharing a use case remain separate assessments. | M |
| AIIA-3 | The tier scopes the section set: mandatory, recommended, or not applicable. | M |
| AIIA-4 | FRIA, DPIA, and model-risk analyses are feeders contributing sections to the single AIIA, not separate documents. | M |
| AIIA-5 | Facts captured at registration and classification prefill the AIIA and are never re-keyed. | M |
| AIIA-6 | **The AIIA identifies and stops.** Its output is a set of identified risks plus their suggested controls. It does not ask any actor to treat, score-and-treat, or accept anything. | M |
| AIIA-7 | Against a proposed risk the user may **acknowledge** that it applies, or **dismiss** it as not applicable with a reason. The user cannot amend a proposed risk: risk definitions are corpus. The word "accept" does not appear at identification; acceptance is a treatment choice. | M |
| AIIA-8 | A dismissal is a deviation from a system proposal and is disclosed to the reviewer under XCUT-4. | M |
| AIIA-9 | Reassessment produces a new current version superseding a retained prior. The refresh trigger and versioning are in scope. | M |
| AIIA-10 | Cadence- and trigger-driven reassessment (scheduled review, material change, incident, regulatory change). | S |
| AIIA-11 | User-added risks, guided so each is mapped to controls and mitigations. | C |

## 8.10 Risk library (RSK)

| ID | Requirement | Pri |
|---|---|---|
| RSK-1 | Human-curated, source-attributed risk entries: source framework, layer, description, typical triggers, links to mitigating controls. | M |
| RSK-2 | Seed: OWASP Top 10 for LLM Applications (full) plus a curated NIST/ISO governance and fundamental-rights layer. | M |
| RSK-3 | The library feeds AIIA identification: by system type, modality, and tier it proposes a **relevant subset** for acknowledgement. It does not dump the full library. | M |
| RSK-4 | Catalogue products carry typical associated risks, so product selection prefills likely risks. | M |
| RSK-5 | **Each risk carries a domain**: technical, data, operational, legal, or ethical. The register groups by domain. | M |
| RSK-6 | **Each risk carries seeded defaults**: default likelihood, default impact, and default exposure inputs. | M |
| RSK-7 | **Each risk carries a scope**: system-relevant (proposed per AIIA, rolled up) or organisation-level (register-native, belonging to no AI System). | M |
| RSK-8 | **Each risk may carry a protected-harm tag.** Tagging is applied only to obvious harms; contestable cases are left untagged. In MVP the protected-harm set is exactly `{safety}`. | M |
| RSK-9 | The library's authority derives from named frameworks. AI proposes relevance and drafts; humans own what lands. AI never authors ground-truth risks unconfirmed. | M |
| RSK-10 | AI-assisted freshness: surface new seed-source revisions and emerging risk classes for curator review. | S |

## 8.11 Risk scoring methodology (SCR)

| ID | Requirement | Pri |
|---|---|---|
| SCR-1 | `Inherent = Likelihood × Impact × Exposure`. Likelihood 1–5, Impact 1–5, Exposure 1–3. | M |
| SCR-2 | `Residual = Inherent × (1 − ControlEffectiveness)`. | M |
| SCR-3 | **Impact is corpus.** Seeded per library risk, not tenant-amendable. Impact is a property of the risk, being the harm if it materialises, which is a normative judgement grounded in the standard. | M |
| SCR-4 | **Likelihood is a tenant claim.** Seeded as a default, amendable, recorded, and disclosed. It is a property of the deployment, which only the tenant can assess. | M |
| SCR-5 | **Exposure is derived, not typed.** Computed from structured deployment attributes the AI System declares (scale, criticality, user base). Those declarations are tenant claims: amendable, recorded, disclosed. | M |
| SCR-6 | **Control effectiveness is derived, not claimed:** `0.90 × (implemented ÷ SoA-applicable)`, computed from evidenced control coverage. | M |
| SCR-7 | The effectiveness denominator is the SoA-**applicable** set. Applicable-but-not-implemented remains in the denominator and correctly reduces effectiveness. Only justified inapplicability leaves it. | M |
| SCR-8 | Control effectiveness is capped at 0.90. No control eliminates risk; residual risk always exists. | M |
| SCR-9 | Risk bands: **Low, Moderate, High, Critical**, derived from the score. Both the numeric score and the band are persisted. | M |
| SCR-10 | Band rules: **Critical** hard-stops authorisation. **High** and **Moderate** require treatment. **Low** defaults to accept. | M |
| SCR-11 | **The methodology is data, not code**: matrix, seeded defaults, band thresholds, band rules, the protected-harm set, and the treatment options are configuration. Per-tenant methodology is a later additive layer requiring no rewrite. | M |
| SCR-12 | The methodology is versioned; an assessment preserves the version it was scored under. | M |
| SCR-13 | Weighted control contribution: each risk-control mapping carries a weight, so a control that substantially addresses a risk counts for more than one that partially contributes. | S |

## 8.12 Risk treatment (TRT)

| ID | Requirement | Pri |
|---|---|---|
| TRT-1 | Treatment operates on the **system risk register**, per risk, per AI System, after AIIA approval. | M |
| TRT-2 | **Risk ownership**: the platform defaults the risk owner to the system owner for every risk. The Compliance Officer confirms, thereby assigning ownership. Confirmation is the opening act of the treatment phase and gates everything after it. | M |
| TRT-3 | **Four response options**: MITIGATE, ACCEPT, AVOID, TRANSFER. | M |
| TRT-4 | **Propose and ratify.** The risk owner selects the response and, where treatment is required, sets the treatment plan, linked control, target date, and resulting residual. The set returns to the Compliance Officer for **treatment authorisation**, an act distinct from the ATO. | M |
| TRT-5 | **The round trip is triggered by deviation from the default, not by band.** A low-band risk taking the accept default is closed by the risk owner's confirmation. A low-band risk with an elected treatment round-trips. Everything above low round-trips, because treatment is required. | M |
| TRT-6 | **Critical round-trips.** What is ratified is the mitigation plan and its claimed residual, not the response option: the residual is the only thing that clears the hard stop. | M |
| TRT-7 | **No automated acceptance.** ACCEPT is the platform's default response for low-band risks, but requires explicit human confirmation by the risk owner. The confirmation step is the fork at which an owner may instead elect to treat. | M |
| TRT-8 | **Critical risks cannot be accepted.** The response set collapses to mitigate or avoid. | M |
| TRT-9 | **A protected-harm risk always requires treatment, at every band.** ACCEPT is unavailable regardless of score or exposure. | M |
| TRT-10 | **AVOID is a decision not to proceed.** It produces no residual and terminates the AI System's path to authorisation. | M |
| TRT-11 | **TRANSFER requires linked third-party assurance evidence** to be recordable, and never clears a hard stop. It shifts the bearer, not the harm. | M |
| TRT-12 | **The organisation-wide control case**: a control whose reach is organisation-wide closes its risk across all contributing AI Systems in one act, and the rollup reflects this. | M |
| TRT-13 | Every treatment record carries: proposed response, final response, decision maker, ratifier, decision date, ratification date, rationale, target date, and status. | M |

## 8.13 Risk register (RRG)

| ID | Requirement | Pri |
|---|---|---|
| RRG-1 | **System risk register**, per AI System: its identified risks with score, band, suggested controls, owner, treatment state, and residual. The working surface where substrate and treatment state live. | M |
| RRG-2 | **Risk register**, unqualified, means the **organisation-level register**: the rolled-up system risk registers plus governance risks. It is the ISO/IEC 42001 artifact an auditor asks for by name and must satisfy that request unaided. | M |
| RRG-3 | The organisation-level register is **derived and always current**: a read-time rollup with no independent state, no separate refresh, and no lifecycle of its own. It is computed from the assessments and cannot drift from them. | M |
| RRG-4 | **Deduplication**: one row per risk, listing its contributing AI Systems. Treating a risk on one AI System drops that system from the contributing set; the row persists until all contributors are treated. | M |
| RRG-5 | **Governance risks**: organisation-level risks belonging to no AI System. They appear only when at least one is present. | M |
| RRG-6 | Governance risks have an organisation-scope treatment home, since no system register sits beneath them. | M |
| RRG-7 | The register groups by risk domain and is filterable by band, status, contributing product, and AI System. | M |
| RRG-8 | The register is export-grade and forms part of the audit pack, in formal wording. | M |
| RRG-9 | The ISO/IEC 42001 at-least-annual risk review is surfaced and tracked as a governance cadence obligation. | S |

## 8.14 Exception management (EXC)

| ID | Requirement | Pri |
|---|---|---|
| EXC-1 | An exception is a first-class governance object recording an accepted governance gap with an owner, a justification, and an expiry. | M |
| EXC-2 | **A valid exception clears a named authorisation condition while it is live.** It is not a blanket override of the gate. | M |
| EXC-3 | Governance-incompleteness is exception-clearable. | M |
| EXC-4 | **Critical risk is never exception-clearable. A protected-harm risk is never exception-clearable, at any band.** | M |
| EXC-5 | On expiry, the cleared condition snaps back to failing and the authorisation basis is pulled. | M |
| EXC-6 | Every exception grant, extension, and expiry is written to the audit trail. | M |

## 8.15 Control library, coverage, and applicability (CTL)

| ID | Requirement | Pri |
|---|---|---|
| CTL-1 | Pre-loaded control set for ISO/IEC 42001 Annex A and EU AI Act obligations. | M |
| CTL-2 | Cross-map relationships so a single piece of evidence satisfies controls in both frameworks simultaneously. | M |
| CTL-3 | Control coverage view per framework: satisfied, partial, open, unaddressed. Recomputed live from qualifying links on approved assessments; never persisted. | M |
| CTL-4 | **The applicability layer** determines, per organisation and per control, whether the control applies and why. Determination is deterministic, from catalogue facts, deployment context, tier, risk set, and coverage, via curated rules. | M |
| CTL-5 | With applicability determined, coverage is an obligation view, not merely a set of gaps. | M |
| CTL-6 | The data model admits further frameworks without rework. | S |

## 8.16 Statement of Applicability (SOA)

| ID | Requirement | Pri |
|---|---|---|
| SOA-1 | Produce an ISO/IEC 42001 Statement of Applicability: per Annex A control, its **applicability**, its **implementation status**, and the **justification for inclusion or exclusion**, with the risk assessment and treatment as the basis. | M |
| SOA-2 | The SoA has three states per control: applicable and implemented; applicable and not implemented, justified; not applicable, justified. | M |
| SOA-3 | The platform determines applicability automatically; the user confirms or amends. | M |
| SOA-4 | **The authoriser is the SoA authority.** | M |
| SOA-5 | **An exclusion requires an authored human justification.** A generated exclusion justification is not defensible. | M |
| SOA-6 | The SoA is export-grade, part of the audit pack, and in formal wording. | M |

## 8.17 Evidence and audit trail (EVD)

| ID | Requirement | Pri |
|---|---|---|
| EVD-1 | Central evidence repository; evidence is reusable across assessments and controls. | M |
| EVD-2 | Immutable, timestamped, append-only audit log of every material action with actor identity, before and after values. Exportable. | M |
| EVD-3 | Evidence records carry filename, storage location, content hash, MIME type, type, description, confidentiality, uploader, upload date, and linked entities. | M |
| EVD-4 | Evidence access is recorded. | M |
| EVD-5 | **Per-evidence-item review attestation**: where evidence is linked to the object under review, the review surface presents it and the reviewer attests, per item, that they have examined it. Each attestation is logged and tied to the decision and its submission round. Where no evidence is linked, the surface states so rather than showing an empty affirmation. | M |
| EVD-6 | Evidence requests can be assigned to a contributor with due dates and reminders. | S |
| EVD-7 | Evidence freshness and expiry flags. | C |

## 8.18 Workflow, roles, review, and sign-off (WKF)

| ID | Requirement | Pri |
|---|---|---|
| WKF-1 | Two role axes: an **administrative** axis (account management only, zero governance capability) and a **governance** axis of five SoD-constrained roles on three lines of defence. | M |
| WKF-2 | The governance roles: `system_owner` and `contributor` (1st line, own and provide); `reviewer` (2nd line, review and recommend); `authoriser` (2nd line, authorise and accept, surfaced as **Compliance Officer / Manager**); `auditor` (3rd line, read-only assurance). | M |
| WKF-3 | **Conflict matrix**: the only composable pair is `system_owner + contributor`. All other pairs conflict, including `reviewer + authoriser`, so the party that recommends is not the party that accepts. Enforced at assignment and at the act. | M |
| WKF-4 | Self-assignment of governance roles is blocked. | M |
| WKF-5 | Review queue; reviewers comment, request changes, or approve with attribution. | M |
| WKF-6 | The AIIA is reviewed and approved on **identification and scoring**. Treatment is not a precondition of review. | M |
| WKF-7 | A reviewer cannot review their own submission. | M |
| WKF-8 | **The authoriser holds the three compliance-authority acts**: risk acceptance, risk-ownership confirmation, and SoA confirmation. No sixth role is introduced. | M |
| WKF-9 | Every governance-role grant and revoke is written to the audit trail. | M |
| WKF-10 | Governance roles are tenant-scoped; the assignment model reserves room for object-scoped assignment without rework. | S |
| WKF-11 | Notifications for assignments, approvals, and due dates. | S |

## 8.19 Authorisation (ATO)

| ID | Requirement | Pri |
|---|---|---|
| ATO-1 | The authoriser accepts the residual posture and grants the authorisation to operate. Only this act moves an AI System to authorised. | M |
| ATO-2 | **The gate is a single condition set. All must hold; any one failing is a hard stop:** governance-complete; no unresolved critical risk; no untreated high or moderate risk; no untreated protected-harm risk at any band; lows explicitly confirmed; lifecycle prerequisites met (use case and product cleared, classification approved, review signed off). | M |
| ATO-3 | **Residual risk is computed, never authored.** The ATO records the acceptance act and **snapshots the computed residual posture** at the moment of authorisation. | M |
| ATO-4 | The ATO carries no narrative basis. The methodology dictates what may be accepted and exceptions govern deviation; the reasoning lives in the per-risk treatment decisions and the exceptions, structured and checkable. An optional comment field exists for incidental context: never required, never gating, never read as the basis or the residual. | M |
| ATO-5 | The ATO is point-in-time: it stamps the tier, the authoriser's durable identity, the assessment version and cycle, and the residual posture. It is never mutated; a re-authorisation writes a new record. | M |
| ATO-6 | **A new current AIIA version invalidates the ATO.** An ATO is bound to the submission round it was granted against, and the gate passes only while they match. A reassessed AI System must be re-authorised. | M |
| ATO-7 | A prohibited classification overrides an existing authorisation from any state, with no exception path. | M |

## 8.20 Export and audit pack (EXP)

| ID | Requirement | Pri |
|---|---|---|
| EXP-1 | Generate an audit pack for an AI System or a product: the ISO 42005 inventory record, classification history, the assessment, an evidence manifest, control coverage, the risk register, the SoA, the lifecycle trail, the ATO, and the audit trail. Content-hashed; evidence referenced by manifest rather than embedded. | M |
| EXP-2 | Generate the ATO document for an authorised AI System. | M |
| EXP-3 | Generate the organisation-level risk register as a standalone artifact. | M |
| EXP-4 | Generate the Statement of Applicability as a standalone artifact. | M |
| EXP-5 | Generate the AI Systems inventory as a standalone artifact. | M |
| EXP-6 | PDF and document rendering of the above. | S |
| EXP-7 | Read-only auditor access scoped to a product or engagement. | S |
| EXP-8 | Branded or templated export for the buyer's own reporting. | C |

## 8.21 AI assistance (AIA)

| ID | Requirement | Pri |
|---|---|---|
| AIA-1 | **All AI-originated content is marked as AI-generated** wherever it is surfaced. | M |
| AIA-2 | **All AI-originated content is human-confirmed before it enters the record.** | M |
| AIA-3 | **AI may propose, draft, enrich, and suggest. It is never the source of a normative assertion, and its output never becomes GLOBAL corpus without curation.** | M |
| AIA-4 | **The platform distinguishes deterministic proposals from AI proposals.** A deterministic catalogue or library lookup is not AI-suggested and is never labelled as such; both exist and carry different confirmation obligations. | M |
| AIA-5 | AI-assisted AIIA drafting: suggests wording, flags gaps and inconsistencies. | S |
| AIA-6 | AI-assisted applicability enrichment. | S |
| AIA-7 | AI-assisted catalogue enrichment for curator review. | S |

---

# 9. Non-functional requirements (NFR)

| ID | Requirement |
|---|---|
| NFR-1 Security | SOC 2 controls from day one; encryption at rest and in transit; SSO/SAML for the enterprise tier. |
| NFR-2 Data residency | EU data-residency option. |
| NFR-3 Multi-tenancy | Strict tenant isolation with row-level separation, enforced at both application and database levels. |
| NFR-4 Auditability | Every material automated output is traceable to its input data, taxonomy, catalogue profile, rule version, methodology version, user confirmation or override, decision maker, and timestamp. The audit log is append-only and exportable. |
| NFR-5 Explainability | The platform explains why a question was asked, why a field was prefilled, why a risk was proposed, why a tier was assigned, why a treatment was proposed, and why a hard stop fired. |
| NFR-6 Maintainability | Business rules are not embedded in route handlers. Taxonomies, catalogue values, and the methodology are data-driven and versioned. Assessments preserve the versions they used. Framework content is separated from assessment-instance data. |
| NFR-7 Reliability | Defined backup and restore; uptime targets appropriate to stage. |
| NFR-8 Privacy | GDPR-aligned handling; DPA available; minimal PII collection. |
| NFR-9 Usability | A non-technical system owner can complete their part of an assessment without training and without reading legal terminology. |

---

# 10. MVP scope boundary

## 10.1 In scope

Multi-tenancy with row-level isolation; authentication; five governance roles with SoD enforcement; the use-case gate and product gate with vendor vetting inside product approval; the AI System inventory as an ISO 42005 record; the product catalogue with product-driven prefill and the four prefill states; the business taxonomy, the governance taxonomy, and the bridge; classification via bridge and context wizard; the AIIA (identification only, tier-scoped, with feeders); the risk library with domains, scopes, seeded defaults, and protected-harm tagging; **the risk scoring methodology**; the system risk register; the treatment phase with four options and propose-and-ratify; the organisation-level risk register with governance risks; exception management; the applicability layer; the Statement of Applicability; control coverage; the evidence repository with per-item review attestation; review and sign-off; authorisation and the ATO; the audit pack; the audit trail; assessment versioning; AI assistance.

## 10.2 Out of scope

Consulting-led delivery mode. Per-tenant configurable methodology, risk tolerance, and treatment policy (a later additive layer over the same engine). A configurable workflow engine or approval-chain builder. A dynamic questionnaire builder. Governance roles beyond the five, and multi-role holding. Cadence- and trigger-driven reassessment scheduling. The annual-review cadence obligation. User-added risks. Weighted control contribution. Real-time model performance monitoring. Automated collection from production AI systems. Integration with SIEM, GRC, ticketing, or MLOps platforms. Automated legal advice. Model testing or red-team execution. Vendor documentation ingestion by crawling. Cross-tenant benchmarking. A marketplace for third-party templates. Technical enforcement of the deployment gate. Frameworks beyond ISO/IEC 42001, ISO/IEC 42005, and the EU AI Act. Scoped auditor access.

---

# 11. Success measures

**Product validation (design-partner phase)**

- Time to complete a first full assessment versus the partner's current process.
- Evidence reuse rate: proportion of evidence items satisfying more than one control.
- Assessments surviving contact with a real auditor without rework.
- **Override rate on the platform's defaults** — the key signal of whether the opinions are right. A low, stable rate with overrides clustering on genuinely ambiguous cases validates them; a high or scattered rate shows where defaults need adjustment.
- Proportion of assessment fields safely prefilled, and of prefills confirmed without amendment.
- Proportion of risks proposed automatically versus added manually.
- Time to produce the risk register, the SoA, and an audit pack.
- Governance-completeness: proportion of the inventory assessed rather than merely registered.

**Commercial validation**

- Design partners converting to paid at GA.
- Partners willing to be a public reference.

---

# Appendix A — Change record

This version reconciles the original PRD with the shipped specification. The body above is the spec; this appendix records what changed for readers holding a prior version.

## A.1 Product identity

The prior PRD committed to supporting both consulting-led assessments and self-service governance. These demand opposite architectures, and the ambiguity was the source of most divergence between intent and implementation. **Resolved: opinionated, self-service.** Consequences: tenant risk policy becomes a post-MVP layer; the policy exception rule engine becomes methodology parameters; the nine-role multi-hold model becomes five roles with a conflict matrix; the dynamic questionnaire engine becomes tier-scoped section templates; the Consultant role is not built.

## A.2 Recovered

The following were in the original PRD as MVP and had fallen out of the working specification:

| Recovered | Original source |
|---|---|
| The risk scoring engine as MVP core | §2.6–10, §14.1 |
| `Inherent = L × I × E`; `Residual = Inherent × (1 − CE)`; exposure 1–3 | §8.11 |
| Per-risk seeded default likelihood, impact, and exposure | §8.10 |
| No autonomous risk acceptance | §6.2 |
| Risk domains | §8.10 |
| The four prefill states; operational reality supersedes vendor documentation | §5.3 |
| Tier never determined by product choice alone | §8.9 |
| The business use-case taxonomy | §8.3 |

## A.3 Changed

| Area | From | To |
|---|---|---|
| Clearance order | Vendor → product → use case, vendor outermost | **Use case → product**, use case outermost; vendor vetting is a step inside product approval, never a standalone gate |
| Prohibition | Checked at intake per registration against a classified tier | Resolved at the **use-case gate**, once per use case, organisation-level |
| Vocabulary | System (inventory) holds use cases (assessed) | **AI System = Product + use case**; the AI System is the assessed unit; the use case is the abstract, product-independent application type |
| Classification | Part of registration | **The first step of assessment** |
| Treatment | A gate inside the AIIA flow, pre-review, decided by the system owner | **A distinct phase** after AIIA approval, on the system risk register, propose-and-ratify |
| Review | Gated on treatment completion | Approved on **identification and scoring** |
| Residual risk | A statement authored by the authoriser at ATO time | **Computed**, snapshotted at authorisation; no prose |
| Registration | Complete on its own terms | **Inventory-complete, not governance-complete**; unassessed is a tracked finding |
| Risk register | An organisation-wide residual view, `C` priority, post-MVP | **`M` priority**: the ISO 42001 audit artifact, MVP core |
| Applicability layer | Deferred | **MVP**, because the SoA depends on it |
| AI | Post-MVP | **MVP**, sequencable last |

## A.4 Retired

Nine roles and multi-hold; the Consultant role; the dynamic questionnaire engine; tenant risk tolerance policy; the exception rule engine (its rules survive as methodology parameters); "Accept with review" and "Escalate" as distinct treatment options (both are the propose-and-ratify round trip); the lifecycle-stage assessment taxonomy (concept, design, validation, and so on — `lifecycle_stage` remains an inventory attribute); the prior PRD's data model summary, which is superseded by design.

---

# Appendix B — Open items

| ID | Item | Owner |
|---|---|---|
| O-1 | **Band thresholds.** `L × I × E` spans 1–75 and skews low: roughly two thirds of reachable combinations land at 18 or below and only three reach 57 or above. Equal quartiles over the range would make Critical nearly unreachable and quietly disable the hard stop. The cut lines must be set deliberately against the shape of the scale. | Founder (methodology) |
| O-2 | **Partial coverage counting.** Coverage has a partial state. Does a partially-satisfied control count as implemented, as a half, or as nothing in the effectiveness denominator (SCR-6)? | Founder (methodology) |
| O-3 | **Exposure outranking impact.** `L=5, I=2, E=3` scores 30; `L=5, I=5, E=1` scores 25. A trivial-impact risk at full exposure outranks a catastrophic one at pilot scale, which sits oddly with impact being the locked normative axis. Either narrow exposure's swing or floor the band on critical impact. | Founder (methodology) |
| O-4 | **AVOID's terminal state.** TRT-10 terminates the path to authorisation; the lifecycle has no state for a deliberate decision not to proceed. | Design |
| O-5 | **Governance risk scope split (RSK-7).** Which governance-layer library risks are system-relevant versus organisation-level, and the organisation-scope treatment home (RRG-6). | Founder (curation) |
| O-6 | **Use-case gate object (APR-1).** Organisation-level approval of a business use case has no home in the current clearance model. | Design |
| O-7 | **Protected-harm tagging pass (RSK-8).** Obvious harms only. This decides what the product will never let a customer accept. | Founder (curation) |
| O-8 | **Impact seeding pass (RSK-6).** Seeded impacts determine criticality floors. | Founder (curation) |

---

# Appendix C — Source verification

To be confirmed against the live database and HEAD before any design encodes them (D-21).

| ID | Claim |
|---|---|
| SV-1 | The two vocabularies and the bridge exist as described (TAX-1..3), with the business vocabulary hierarchical and user-facing. |
| SV-2 | A business category with no EU trigger carries no primary mapping and routes to the context wizard (TAX-4). |
| SV-3 | No scoring, banding, or criticality logic exists at HEAD; the likelihood, severity, and residual fields are unwritten by the current flow. |
| SV-4 | The risk-control map carries a strength qualifier and risks map to many controls (SCR-13). |
| SV-5 | The shipped clearance model is vendor-outermost and is superseded by APR-1..7. |
| SV-6 | Live `INV-n` / `D-n` / `FE-n` ceilings before minting. The index lags the repository. |