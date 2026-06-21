# DOMAIN.md — IronTrust AI Governance Platform

**Location:** `docs/DOMAIN.md` — single source, mirrored to project knowledge. Updated rarely (stable spec).
**Purpose:** The conceptual model and vocabulary, plus the governing rules stated *as concepts*. This is the orientation file a designer reads first.
**Lanes:** physical schema → `DATA-MODEL.md`; enforcement → `INVARIANTS.md` (`INV-n`); rationale / rejected alternatives → `DECISIONS.md` (`D-n`); per-feature acceptance detail → `REQUIREMENTS.md`. This file names a rule and cites where it is enforced and why; it does not restate either.

---

## 1. What the product is

An AI governance platform for mid-market organisations. The MVP centre of gravity is the **AI System Impact Assessment (AIIA)**, conducted to **ISO/IEC 42005** and scoped by the system's **EU AI Act** risk tier, whose completed output becomes reusable, audit-ready evidence cross-mapped simultaneously to **ISO/IEC 42001** and the EU AI Act.

**Frameworks in scope:** ISO/IEC 42001 (AI management-system controls), ISO/IEC 42005 (how the impact assessment itself is conducted), EU AI Act (risk tiering + conformity obligations). The Risk Library is seeded from the OWASP Top 10 for LLM Applications (technical layer) and NIST AI RMF / ISO governance & fundamental-rights themes.

**The product spine (§1.5 pattern):** every position the product asserts follows *strong default → shown reasoning → easy override → tracked deviation*. It proposes a confident, standards-grounded answer; shows the basis; accepts a low-friction amendment; records any override. This applies to classification, AIIA content, and catalogue prefill. Full statement and rationale: **D-1**.

The MVP hard boundary is §8 below.

---

## 2. Glossary

| Term | Meaning |
|---|---|
| **System** | A registered AI system — the inventory entity. Selected from the catalogue or described as custom/in-house. Holds one or more use cases. |
| **Use case** | The **unit of assessment** — a materially distinct context in which a system is used. Each use case carries its own classification, risk set, residual risk and sign-off. |
| **AIIA** | AI System Impact Assessment. The primary, defensible impact-assessment record, ISO/IEC 42005-aligned. Exactly one per use case. |
| **Feeder** | A feeding analysis that contributes sections to an AIIA: **FRIA** (fundamental-rights), **DPIA** (data-protection), **MODEL_RISK** (model/system technical risk). Not separate documents — structured inputs to the single AIIA. |
| **Classification** | The EU AI Act risk-tier determination for a use case, derived from deployment context. Versioned and snapshotted. |
| **Tier** | The EU AI Act risk level: `PROHIBITED`, `HIGH`, `LIMITED`, `MINIMAL`. Scopes which AIIA sections are mandatory / recommended / not-applicable. |
| **Bridge** | The reference path that auto-resolves a tier from catalogue facts (system → product → product category → EU AI Act subcategory). |
| **Context-question gate** | The decision-tree fallback that resolves a tier by Q&A when the bridge cannot (a use case with no catalogue product or no primary mapping → `REQUIRES_CONTEXT`). |
| **Risk Library** | The source-attributed seed taxonomy of what can go wrong with an AI system; proposes a relevant subset for AIIA harm identification. |
| **Control / cross-map** | A control in the unified library; a cross-map relationship lets one piece of evidence satisfy both an ISO 42001 and an EU AI Act obligation. |
| **Evidence** | A user-origin artifact substantiating an assessment item. Reused across items and assessments; linked to controls only transitively via items. |
| **Vendor / Product** | The supplier organisation and the specific AI product. A product belongs to a vendor. |
| **Approval scope** | One of three inheriting clearance levels: vendor, vendor+product, vendor+product+use-case (§5). |
| **Gate** | A lifecycle checkpoint whose conditions must be met before a use case advances (§6). |
| **Treatment** | The mitigation decision recorded against a dispositioned risk (`MITIGATE`/`ACCEPT`; `TRANSFER`/`AVOID` reserved). |
| **ATO** | Authorisation to Operate — the deployment-authorisation record. Records the basis on which deployment was approved; export-grade and point-in-time. |
| **Residual risk** | The risk remaining after treatment, accepted by the authoriser at authorisation time. |
| **Line of defence** | The governance-role grouping: 1st (own/provide), 2nd (review/authorise), 3rd (assure). |
| **Control coverage** | The programme-level posture: per control, `SATISFIED`/`PARTIAL`/`OPEN`/`UNADDRESSED`, recomputed live from qualifying (dispositioned, approved) links (S7a). Orthogonal to applicability. |
| **Applicability layer** (deferred) | *Which* controls ought to apply to a use case — EU AI Act derived per use case (tier × operator-role → clause → control); ISO 42001 declared as a tenant Statement of Applicability. Recorded design intent, not built (OPEN-3). |
| **Statement of Applicability (SoA)** | The ISO 42001 tenant-level declaration of applicable controls with justified exclusions — the ISO half of the deferred applicability layer. |
| **Export / audit pack** | The complete, traceable governance record of a use case or system as structured JSON — register facts, classification history, assessment record, evidence manifest, coverage, lifecycle trail, ATO(s), audit trail (S7b; EXP-1). |
| **ATO document** | The deployment-authorisation record rendered as a standalone document (EXP-1a), authoritative from the `DeploymentAuthorisation` row; the referenced assessment shown as current state, not reconstructed. |

Implementation-level vocabulary (submission round / cycle key, pristine-delete, lock-version concurrency, read-time propagation) is defined where it lives — `PATTERNS.md` and `STATE.md`.

---

## 3. The assessment model (centre of gravity)

A **system is the registered entity; a use case is the unit of assessment.** Impact is a function of the context of use — the same system used for internal knowledge search versus an HR eligibility decision carries materially different impact — so each materially distinct use case gets its own AIIA, with its own classification, risk set, residual risk and sign-off.

```
System  (inventory entity)
  └─ Use case  (unit of assessment)              ← classification, risk set, residual risk, sign-off attach HERE
       └─ AIIA  (exactly one per use case)
            ├─ feeder: FRIA         (fundamental-rights analysis)
            ├─ feeder: DPIA         (data-protection analysis)
            └─ feeder: MODEL_RISK   (model/system technical-risk analysis)
```

- **One AIIA per use case.** Feeders are first-class sections that feed the AIIA, not separate documents — facts entered once propagate rather than being re-keyed across FRIA/DPIA/model-risk.
- **System-level rollup** aggregates the use-case AIIAs for inventory and reporting: coverage (are all use cases assessed?), highest tier present, consolidated outstanding obligations. The rollup is a view; it never holds the assessment itself.
- Harm identification is driven by the Risk Library, not the user's recall: the product proposes a relevant subset for confirm/amend (per D-1), never dumps the full library.

Cross-references: REQUIREMENTS AIIA-1..8, RSK-1..7; feeder read-time assembly → D-18 / INV-16.

---

## 4. EU AI Act classification

Classification is the gate that scopes everything downstream: the tier decides which obligations apply and how deep the AIIA goes. **It runs per use case, and the tier is always a function of how the organisation *uses* the system, never of the product alone** (D-8 / INV-10). The catalogue supplies facts in; deployment context decides the tier.

| Tier | Effect |
|---|---|
| `PROHIBITED` | Hard stop. The lifecycle halts at intake and surfaces the reason; it never proceeds to assessment. Supreme from any state (D-7 / INV-26, 33). |
| `HIGH` | Full AIIA section set surfaced; feeders required per their applicability rules. |
| `LIMITED` | Transparency-weighted obligations; lighter section set. |
| `MINIMAL` | Appropriately light. Only ever an affirmative determination, never a fallback default (INV-12). |

**Two resolution paths, same tier vocabulary:**
- **Bridge** — auto-resolves from catalogue facts where a primary mapping exists.
- **Context-question gate** — a versioned decision tree resolves by Q&A when the bridge returns `REQUIRES_CONTEXT`.

**Authoritative only on reviewer sign-off** (D-9): the context gate writes a `PENDING_REVIEW` snapshot and does not stamp the use case's tier; reviewer sign-off makes it authoritative. Resolution and persistence are kept strictly separate (INV-11); resolution is fail-closed (INV-12).

Cross-references: REQUIREMENTS CLS-1..6.

---

## 5. The three approval scopes

Approval is not a single decision and is not generic per vendor. It operates at three inheriting scopes, each approving only what genuinely lives at that scope and inheriting clearance from the scope above:

| Scope | Question it answers | Cadence |
|---|---|---|
| **Vendor** | Is this organisation safe to deal with? (security posture, financial stability, breach history, certifications, sub-processors) | Once per vendor, with a validity period. Largely product- and use-case-independent. |
| **Vendor + Product** | Is this specific product acceptable? (its data handling, residency, training-data practices, DPA terms) | Per product. Two products of one approved vendor can differ — vendor approval does not imply product approval. |
| **Vendor + Product + Use-case** | Is it acceptable to use this product for this purpose in our context? | Per use case — this is the risk-acceptance / deployment-authorisation decision (the ATO). |

- **Cascading:** vendor clearance is a prerequisite for product clearance, which is a prerequisite for use-case authorisation. An uncleared vendor holds everything downstream.
- **Inheritance:** a new use case of an already-cleared vendor+product inherits both upper clearances and adds only its own use-case assessment.
- **Upward rollup (the fold):** the use-case lifecycle is the primary engine and its output rolls upward — the first use case of a never-seen product authorises that use case *and* constitutes most of product-level approval. Full vendor/product diligence collapses to thin vendor-level diligence plus a product-level rollup view (D-17), which is why it is a smaller deferred surface, not a parallel module.

Cross-references: REQUIREMENTS APR-1..7.

---

## 6. The governance lifecycle

A use case progresses through a **fixed, opinionated** set of gates — a determinate state machine over known states, not a configurable workflow engine (D-15 / INV-24, 25). The interaction model is **capture-once / orchestrate-in-the-background**: intake captures the knowable-up-front context in one uninterrupted flow, then the state machine drives the gates, asking for more data just-in-time only when a transition needs it (D-16).

**States** (conceptual; physical enum + label casing → `DATA-MODEL.md`):

| State | Kind | Meaning |
|---|---|---|
| `requested` | normal | Use case registered, not yet checked. |
| `vendor_check` → `product_check` | normal | Vendor then product approval-status gates (cascading; auto-pass when no catalogue link). |
| `intake` | normal | Context captured; prohibited-practice hard stop evaluated here. |
| `under_assessment` | normal | Required assessments (AIIA + feeders) being worked. |
| `treatment_pending` | normal | Identified risks await treatment/mitigation plans. |
| `pending_authorisation` | normal | All upstream gates satisfied; awaiting the authoriser. **Auto-advance ceiling.** |
| `authorised` | normal (ceiling) | Deployment authorised. Entered **only** by the explicit authoriser act (D-12 / INV-35). |
| `halted_prohibited` | terminal | Prohibited practice. Forced from any non-terminal state, supreme (D-7 / INV-26, 33). |
| `held` | regression | An upstream clearance lapsed; parked at the earliest unsatisfied gate, caught lazily. |
| `deployed`, `retired` | reserved | Members exist but unwired — `authorised` is the lifecycle ceiling by design (scope §8). |

**Gate sequence** (PRD-conceptual): vendor & product gates → intake / prohibited-practice hard stop → assessment gate → treatment gate → authorisation gate. A gate cannot be crossed until its conditions hold; reviewer and authoriser gates are **human-act gates, never auto-advanced** (INV-30). The full gate vector is the source of truth; persisted state is a cursor (INV-25).

Cross-references: REQUIREMENTS LFC-1..6, IXN-1..5.

---

## 7. Governance roles & separation of duties

Two axes are strictly and permanently separated:

- **Administrative axis** (`Membership.role`: `ADMIN` / `MEMBER`) — account management only (manage members, assign governance roles, configure org). **Zero governance power.** Assigning governance roles is the only point administration touches governance, which is why self-assignment is closed (D-5 / INV-7; REQUIREMENTS WKF-6).
- **Governance axis** — the SoD-constrained functional roles, on three lines of defence:

| Role | Line | Act | Composable with |
|---|---|---|---|
| `system_owner` | 1st — own / provide | registers the system/use case, provides and confirms facts, owns the use case | `contributor` |
| `contributor` | 1st — own / provide | supplies requested evidence/facts | `system_owner` |
| `reviewer` | 2nd — review / authorise | reviews and signs off classification, FRIA, AIIA — **recommends** | — |
| `authoriser` | 2nd — review / authorise | accepts residual risk; grants deployment authorisation (ATO) | — |
| `auditor` | 3rd — assure | independent, read-only assurance that the process was followed | — |

**Conflict matrix (the rule):** the only composable pair is `system_owner + contributor`; **all other nine role pairs conflict** — including the same-line `reviewer + authoriser` pair, which is explicitly separated so the party that recommends cannot be the party that accepts residual risk (D-4, D-10). The matrix is policy-as-data; assignment-time enforcement is the single locus `assert_governance_assignable` (INV-7), act-time enforcement (e.g. a reviewer cannot review their own submission) is `assert_distinct_workflow_actor` (INV-28).

**Scope:** governance roles are **tenant-wide** in the MVP. Per-system (object-scoped) assignment is a deliberate later, additive extension — a nullable `scope_id` on the assignment, `NULL` = tenant-wide, preserving every grant; do not build it now (D-22; REQUIREMENTS WKF-7).

**Persona → role mapping** (personas are consumers of the role model, not a separate axis):

| Persona | Role |
|---|---|
| AI Governance / Compliance Lead | `authoriser` — holds the ATO decision; does not author what they authorise |
| Risk / Legal reviewer | `reviewer` — recommends |
| Product / ML owner | `system_owner` / `contributor` (1st line) |
| External auditor / certification body | `auditor` — read-only consumer of evidence |

**Independence note:** where the platform is sold to organisations the founder also audits, the `auditor` persona is a consumer of output, not a buyer in those accounts; the role model enforces that separation in software.

Cross-references: REQUIREMENTS WKF-1..8.

---

## 8. Scope boundary (MVP hard line)

**In scope (MVP):**
- The fixed gated governance lifecycle (determinate state machine) with capture-once interaction (§6).
- Three inheriting approval scopes with cascading status-check gates and upward rollup (§5).
- AI system register (lightweight inventory) with per-use-case EU AI Act classification.
- Curated product catalogue with product-driven prefill — the primary differentiator (facts only, never tier).
- EU AI Act classification engine (per use case, from deployment context).
- AIIA aligned to ISO/IEC 42005 (one per use case, system-level rollup) with FRIA/DPIA/model-risk feeders.
- Unified control library (ISO 42001 ↔ EU AI Act), cross-mapped.
- Risk Library (OWASP LLM Top 10 full + curated NIST/ISO governance & rights layer).
- Evidence repository with immutable audit trail.
- Review & approval workflow with SoD governance roles and sign-off.
- Audit/export pack + ATO-style deployment-authorisation document.
- A small set of automation accelerants (prefill, cross-mapping, gap detection, evidence chasing).

**Out of scope (deferred — do not build; if a task drifts here, stop):**
- Automated discovery of AI assets across cloud/SaaS.
- Continuous technical monitoring (drift, bias, live model telemetry).
- Agentic / runtime guardrail governance.
- Full vendor/product diligence *workflows* (questionnaires, evidence collection, security/privacy review, decision history) — the scopes, statuses, cascading gates and upward rollup are in scope; only the standalone diligence workflows are deferred (D-17).
- Configurable approval workflows / branching chains / BPM-style builder (the lifecycle is fixed, D-15).
- Technical enforcement of the deployment gate (blocking CI/CD) — the MVP records authorisation only.
- Third-party / vendor AI supply-chain risk module.
- Frameworks beyond ISO 42001 + EU AI Act (the data model allows later addition; do not build).

Cross-references: D-15, D-17, D-22; INVARIANTS as the constraint layer throughout.