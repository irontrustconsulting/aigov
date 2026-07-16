# Product Requirements Document

## AI Risk Assessment SaaS

### ISO/IEC 42001 and EU AI Act Aligned

## 1. Document Purpose

This Product Requirements Document defines the initial product vision, scope, functional requirements, domain model, workflow, and architectural principles for an AI risk assessment SaaS platform.

The platform will operationalise a consulting methodology that integrates:

* ISO/IEC 42001 AI management system requirements
* EU AI Act risk classification and regulatory obligations
* AI-specific technical, operational, data, security, legal, and ethical risks
* Tenant-defined risk tolerance and treatment policies
* Taxonomy-driven assessment workflows
* Product-based assessment prefills derived from publicly available documentation

The product is intended to support both consulting-led assessments and self-service organisational AI governance.

---

# 2. Product Vision

The product will provide a structured, auditable, and assisted approach to assessing AI systems throughout their lifecycle.

Instead of presenting users with a large generic questionnaire, the platform will:

1. Identify the AI system and its operational context.
2. Use controlled taxonomies to minimise free-text input.
3. Allow users to select known AI products from a curated catalogue.
4. Apply safe product-specific and taxonomy-based prefills.
5. Ask only the unresolved or organisation-specific questions.
6. Classify the AI system under the EU AI Act.
7. Generate relevant risk scenarios.
8. Evaluate inherent and residual risk.
9. Apply tenant-defined risk treatment policies.
10. Support human review, override, approval, evidence, and reporting.

The intended user experience is:

> Select the AI product and its context, review the proposed assessment baseline, provide the organisation-specific details, and approve or override the resulting conclusions.

---

# 3. Product Objectives

The product shall:

* Reduce the time required to perform an AI risk assessment.
* Minimise unnecessary free-text input.
* Improve assessment consistency across assessors and organisations.
* Translate ISO/IEC 42001 and EU AI Act requirements into operational workflows.
* Provide traceability from system context to classification, risks, controls, treatment decisions, evidence, and reports.
* Support repeat assessments of the same AI system across lifecycle stages.
* Automate routine decisions while preserving human accountability.
* Maintain a reusable library of AI risks, controls, obligations, products, and assessment rules.
* Produce audit-ready and client-ready assessment outputs.
* Support future integration into a wider AI management system platform.

---

# 4. Target Users

## 4.1 Primary Users

* AI governance professionals
* GRC consultants
* ISO/IEC 42001 implementers and auditors
* AI system owners
* Risk managers
* Compliance teams
* Information security teams
* Legal and privacy teams
* AI product and engineering teams

## 4.2 User Roles

The initial role model should support:

* Platform Administrator
* Tenant Administrator
* Consultant
* AI System Owner
* Assessor
* Evidence Contributor
* Reviewer
* Approver
* Read-Only User

Users may hold multiple roles.

---

# 5. Core Design Principles

## 5.1 One AI System, Multiple Assessments

An AI system is a persistent organisational asset.

Each AI system may have multiple assessments over time, including:

* Concept-stage assessment
* Design-stage assessment
* Development-stage assessment
* Validation assessment
* Pre-deployment assessment
* Production assessment
* Periodic reassessment
* Material-change reassessment
* Incident-triggered reassessment
* Regulatory-change reassessment
* Retirement assessment

Each assessment shall relate to one AI system.

A higher-level engagement or programme may group multiple assessments, but this shall not change the one-system-per-assessment model.

## 5.2 Structured Input Before Free Text

The platform shall prioritise controlled selections over free-text entry.

Free text shall be used mainly for:

* Organisation-specific context
* Deviations from known product behaviour
* Risk rationale
* Override justification
* Evidence descriptions
* Treatment actions
* Custom or previously unknown systems

## 5.3 Product Defaults Are Suggestions, Not Truth

Known AI products may provide:

* System metadata
* Likely capabilities
* Likely intended purposes
* Common deployment patterns
* Classification indicators
* Risk scenarios
* Suggested controls
* Initial questionnaire responses

These values shall be treated as proposed defaults.

The system shall always preserve the distinction between:

* Catalogue default
* Prefilled value
* User-confirmed effective value
* Overridden value

Operational reality shall take precedence over vendor documentation.

## 5.4 Human Accountability

Automated outputs shall be explainable and reviewable.

Users shall be able to override:

* Product prefills
* Classification outcomes
* Risk scores
* Control applicability
* Treatment decisions
* Risk acceptance decisions

Overrides shall require justification where materially relevant and shall be recorded in the audit trail.

---

# 6. Product Scope

## 6.1 In Scope for the Initial Product

* Multi-tenant account structure
* User roles and access control
* Organisation management
* AI system inventory
* Taxonomy-driven system registration
* AI product catalogue
* Product-specific profiles and prefills
* Dynamic assessment questionnaires
* EU AI Act classification
* AI risk identification and scoring
* Tenant-level risk tolerance policy
* Default treatment policy
* Risk treatment overrides
* Control and obligation mapping
* Evidence management
* Assessment review and approval
* Report generation
* Audit logging
* Assessment versioning and reassessment history

## 6.2 Out of Scope for the Initial MVP

* Real-time model performance monitoring
* Automated collection from production AI systems
* Full integration with SIEM, GRC, ticketing, or MLOps platforms
* Automated legal advice
* Fully autonomous risk acceptance
* Model testing or red-team execution
* Vendor document ingestion using web crawling
* Automated verification that vendor documentation remains current
* Cross-tenant benchmarking
* Public marketplace for third-party assessment templates

These may be considered in later releases.

---

# 7. Core User Journey

## 7.1 AI System Registration

The user shall:

1. Select an AI system type.
2. Select a use case category.
3. Select a use case subcategory.
4. Select one or more deployment contexts.
5. Select a known product or choose Other.
6. Review system metadata proposed by the platform.
7. Confirm, amend, or override the proposed values.
8. Add organisation-specific ownership and deployment information.

## 7.2 Assessment Creation

The user shall:

1. Select an existing AI system.
2. Create a new assessment.
3. Select the lifecycle stage.
4. Select the assessment trigger.
5. Select the methodology version.
6. Apply the relevant product and taxonomy profile.
7. Review prefilled assessment information.
8. Complete unresolved contextual questions.

## 7.3 Classification

The platform shall:

1. Evaluate product indicators.
2. Evaluate use case and deployment context.
3. Evaluate prohibited-practice indicators.
4. Evaluate high-risk use case indicators.
5. Evaluate transparency obligations.
6. Produce a calculated classification.
7. Explain which rules were triggered.
8. Allow authorised users to override the classification with justification.
9. Require approval where configured.

## 7.4 Risk Assessment

The platform shall:

1. Seed relevant risk scenarios.
2. Present relevant additional risks based on taxonomy, product, lifecycle stage, and classification.
3. Allow custom risks to be created.
4. Score likelihood, impact, and exposure.
5. Calculate inherent risk.
6. Associate existing controls.
7. calculate control effectiveness.
8. Calculate residual risk.
9. Compare residual risk against tenant tolerance.
10. Propose or apply the default treatment policy.

## 7.5 Treatment and Approval

The platform shall:

1. Propose a treatment decision.
2. Identify whether the risk is within tolerance.
3. Apply policy exceptions and hard stops.
4. Allow an authorised user to override the proposed treatment.
5. Require justification for overrides.
6. Require approval where configured.
7. Produce a formal acceptance record where the final treatment is accept.
8. Set review or expiry dates where required.

## 7.6 Reporting

The platform shall generate:

* AI system profile
* EU AI Act classification summary
* Applicable obligations register
* AI risk register
* Control applicability and implementation report
* Risk treatment plan
* Residual risk summary
* Risk acceptance register
* Evidence index
* Executive assessment summary
* Full audit-ready assessment report

---

# 8. Functional Requirements

# 8.1 Tenant and Organisation Management

The platform shall support multiple tenants.

Each tenant shall have:

* One or more organisations
* Users
* AI systems
* Assessments
* Risk policies
* Reports
* Evidence
* Audit records

Every tenant-owned business record shall include a tenant identifier.

The platform shall enforce tenant isolation at both application and database levels.

PostgreSQL row-level security should be used where practical.

---

# 8.2 AI System Registry

Each AI system shall contain:

* System name
* Internal system identifier
* Description
* Organisation
* Business owner
* Technical owner
* AI system type
* Use case category
* Use case subcategory
* Deployment context
* Selected AI product
* Vendor
* Model type
* Deployment model
* Intended purpose
* Geographic scope
* Lifecycle status
* Criticality
* Product-prefill status
* Product-profile version
* Created and updated timestamps

A system may use a known product, an internal system, or Other.

---

# 8.3 Taxonomy Management

The platform shall maintain configurable taxonomies for:

## AI System Types

Examples:

* Generative AI
* Predictive machine learning
* Natural language processing
* Computer vision
* Recommender system
* Decision-support system
* Biometric system
* Autonomous agent
* Hybrid AI system

## Use Case Categories

Examples:

* Customer service
* Human resources
* Recruitment
* Cybersecurity
* Finance
* Fraud detection
* Education
* Healthcare
* Content generation
* Identity verification
* Legal support
* Operations

## Use Case Subcategories

Examples:

* CV screening
* Candidate ranking
* Customer chatbot
* Email summarisation
* Code generation
* Threat detection
* Document classification
* Recommendation
* Credit scoring
* Identity matching

## Deployment Contexts

Examples:

* Internal-only
* Employee-facing
* Customer-facing
* Public-facing
* Back-office support
* Decision support
* Human-in-the-loop
* Human-on-the-loop
* Fully automated
* Embedded into a product
* Critical infrastructure
* API-based integration

Taxonomy records shall be:

* Versionable
* Activatable or deactivatable
* Orderable
* Extensible without code changes

---

# 8.4 Product Catalogue

The platform shall maintain a curated catalogue of known AI products.

Each product shall include:

* Vendor
* Product name
* Product family
* Product version where relevant
* Description
* Public product page
* Public documentation references
* Supported capabilities
* Intended uses
* Known model types
* Deployment methods
* Integration methods
* Data handling characteristics
* Human oversight capabilities
* Customisation capabilities
* Product-profile confidence
* Date last reviewed
* Catalogue status

The catalogue shall support products such as:

* Enterprise generative AI tools
* General-purpose AI platforms
* AI coding assistants
* Embedded enterprise copilots
* Recruitment AI tools
* Fraud detection tools
* Biometric systems
* Customer service tools
* AI development platforms
* AI models exposed through APIs

---

# 8.5 Top-N Product Selection

The product catalogue shall support ranked or curated product lists by:

* AI system type
* Use case category
* Use case subcategory
* Market segment
* Deployment context

The platform shall not treat rankings as objective market truth.

Each ranking shall include:

* Ranking scope
* Rank position
* Source
* Ranking date
* Review date
* Active status

The platform may also support a simpler curated Recommended or Commonly Used flag for the MVP.

---

# 8.6 Product Prefill Profiles

A selected product may prefill:

* AI system type
* Model type
* Vendor type
* Product capabilities
* Deployment model
* Typical intended purpose
* Supported integration patterns
* Typical human oversight model
* Transparency characteristics
* Relevant questions
* Likely risk scenarios
* Suggested controls
* Classification indicators
* Evidence recommendations

Each prefilled value shall include:

* Source
* Confidence
* Profile version
* Date applied
* Whether override is permitted
* Whether the user has confirmed it
* Whether the user has overridden it

Low-confidence values shall not be silently applied.

They shall be shown as suggestions or additional questions.

---

# 8.7 Other and Custom Product Handling

Where the user selects Other:

* The user shall provide a product or system name.
* Product-specific prefills shall not be applied.
* Taxonomy-based defaults shall still be used.
* The platform shall ask additional contextual questions.
* The user may request that the product be added to the managed catalogue.
* Internal and custom-developed systems shall be supported.

---

# 8.8 Questionnaire Engine

The platform shall provide dynamic, versioned questionnaires.

Questions shall support:

* Boolean
* Single select
* Multi-select
* Numeric
* Date
* Text
* Evidence upload
* Scored response
* Confirmation of prefilled values

Question applicability may depend on:

* AI system type
* Use case category
* Use case subcategory
* Deployment context
* Product
* Product capability
* Lifecycle stage
* EU AI Act classification
* Previous responses
* Applicable obligations
* Risk scenarios

Each answer shall record its source:

* User-entered
* Product prefill
* Taxonomy prefill
* Derived by rule
* Imported
* Overridden

The platform shall display only relevant and unresolved questions wherever possible.

---

# 8.9 EU AI Act Classification

The classification engine shall support:

* Prohibited or unacceptable-risk assessment
* High-risk assessment
* Transparency and limited-risk obligations
* Minimal-risk or non-high-risk outcomes
* General-purpose AI considerations where relevant
* Provider, deployer, importer, distributor, and other role considerations
* Context-specific classification
* Override and approval

Product choice alone shall never determine the final classification.

The classification shall be based on:

* Product
* Intended purpose
* Actual use
* Affected persons
* Decision impact
* Sector
* Deployment context
* Level of automation
* Human oversight
* Legal role
* Geographic deployment
* System capabilities

Each classification result shall show:

* Calculated category
* Final category
* Rules triggered
* Rationale
* Evidence references
* Confidence
* Override status
* Approver
* Approval date

---

# 8.10 Risk Library

The product shall maintain a reusable risk scenario library.

Risk domains shall include:

* Technical
* Data
* Operational
* Security
* Legal and regulatory
* Ethical
* Human rights
* Organisational
* Third-party
* Lifecycle
* Model and performance
* Transparency and explainability

A risk scenario shall include:

* Code
* Title
* Description
* Cause
* Event
* Consequence
* Domain
* Applicable system types
* Applicable products
* Applicable use cases
* Applicable lifecycle stages
* Applicable deployment contexts
* Relevant obligations
* Relevant controls
* Default likelihood
* Default impact
* Default exposure
* Source
* Version
* Active status

---

# 8.11 Risk Scoring

The initial scoring model shall support:

* Likelihood: 1–5
* Impact: 1–5
* Exposure: configurable, initially 1–3
* Control effectiveness: configurable percentage or rating

A candidate formula is:

Inherent Risk = Likelihood × Impact × Exposure

Residual Risk = Inherent Risk × (1 − Control Effectiveness)

The scoring model shall be configurable and versioned.

Risk levels shall initially include:

* Low
* Medium
* High
* Critical

The system shall persist both numeric scores and risk bands.

Assessors shall provide rationale for material risk scores.

---

# 8.12 Tenant Risk Tolerance

Each tenant shall define an active risk policy.

The risk policy shall include:

* Risk tolerance level
* Whether tolerance applies to inherent or residual risk
* Default treatment by risk band
* Whether treatment may be applied automatically
* Whether human confirmation is required
* Whether approval is required
* Which roles may override treatment
* Which risk categories cannot be auto-accepted
* Whether acceptance expires
* Required review frequency

The default recommended model is to apply tolerance to residual risk.

Example policy:

* Low: Accept automatically
* Medium: Accept with review
* High: Mitigate
* Critical: Escalate or avoid

---

# 8.13 Risk Treatment Policy

Supported treatment options shall include:

* Accept
* Accept with review
* Mitigate
* Avoid
* Transfer
* Escalate

For each risk, the platform shall record:

* Proposed treatment
* Final treatment
* Decision source
* Whether the decision was auto-applied
* Whether it was overridden
* Override rationale
* Decision maker
* Approver
* Decision date
* Approval date
* Status

---

# 8.14 Policy Exceptions and Hard Stops

The platform shall support exceptions that override normal tolerance rules.

Examples include:

* Prohibited AI practices cannot be accepted.
* Critical risks cannot be auto-accepted.
* Risks linked to mandatory legal obligations cannot be silently accepted.
* High-risk AI systems may require formal human approval.
* Missing mandatory human oversight may force mitigation or escalation.
* Certain security risks in production may require mitigation.
* Certain fundamental-rights risks may require legal or ethics review.

Exceptions shall support:

* Rule conditions
* Forced treatment
* Approval requirement
* Override eligibility
* Escalation role
* Rationale

---

# 8.15 Controls and Obligations

The platform shall maintain separate libraries for:

* Frameworks
* Framework sections
* Regulatory obligations
* Controls
* Control-to-obligation mappings

Framework content shall include:

* ISO/IEC 42001
* EU AI Act
* Internal methodology requirements
* Future optional frameworks

Controls may relate to:

* Governance
* Accountability
* Data quality
* AI lifecycle management
* Human oversight
* Transparency
* Technical documentation
* Record keeping
* Cybersecurity
* Monitoring
* Incident management
* Supplier governance
* Competence
* Impact assessment

Assessment controls shall record:

* Applicability
* Implementation status
* Effectiveness
* Evidence
* Owner
* Target date
* Notes
* Validation status

---

# 8.16 Evidence

Users shall be able to upload or reference evidence.

Evidence may be linked to:

* AI system
* Assessment
* Question response
* Classification result
* Risk
* Control
* Obligation
* Treatment decision
* Report

Evidence records shall include:

* Filename
* Storage location
* File hash
* MIME type
* Evidence type
* Description
* Confidentiality
* Uploader
* Upload date
* Review status
* Version
* Linked entities

The platform shall record evidence access and modification where appropriate.

---

# 8.17 Assessment Reviews and Approvals

The platform shall support:

* Assessor review
* Technical review
* Legal review
* Risk-owner review
* Independent reviewer approval
* Management approval

Review records shall include:

* Review type
* Reviewer
* Decision
* Comments
* Date
* Related assessment version

---

# 8.18 Audit Trail

The platform shall maintain an immutable audit trail for material events.

Audit records shall capture:

* Tenant
* Entity type
* Entity identifier
* Action
* Actor
* Before value
* After value
* Timestamp
* Source
* IP address where appropriate

Material events include:

* System registration
* Prefill application
* Prefill override
* Classification execution
* Classification override
* Risk scoring change
* Control effectiveness change
* Treatment proposal
* Auto-acceptance
* Treatment override
* Approval
* Evidence upload
* Report generation
* Policy change

---

# 9. Data Model Summary

The principal entities are:

## Tenancy and Access

* Tenant
* Organisation
* User
* Role
* User Role

## AI System Registry

* AI System
* AI System Type
* Use Case Category
* Use Case Subcategory
* Deployment Context
* AI Product
* Product Vendor
* Product Profile
* Product Capability
* Product Taxonomy Mapping

## Assessment

* Assessment
* Assessment Review
* Previous Assessment Relationship
* Assessment Response

## Questionnaire

* Questionnaire
* Questionnaire Section
* Question
* Question Option
* Question Applicability Mapping

## Classification

* Classification Rule
* Assessment Classification
* Classification Rule Result

## Risk

* Risk Domain
* Risk Scenario
* Assessment Risk
* Risk Assessment Rationale
* Risk-Control Link
* Risk Treatment Decision
* Risk Acceptance

## Risk Policy

* Tenant Risk Policy
* Risk Policy Rule
* Risk Policy Exception

## Framework and Controls

* Framework
* Framework Section
* Obligation
* Control
* Control-Obligation Mapping
* Assessment Control

## Product Intelligence

* Product Market Ranking
* Product Prefill Rule
* Product-Risk Mapping
* Product-Control Mapping

## Evidence and Reporting

* Evidence Item
* Evidence Link
* Report
* Report Snapshot
* Audit Log

---

# 10. Key Data Relationships

The principal cardinalities are:

* One tenant has many organisations.
* One tenant has many users.
* One organisation has many AI systems.
* One AI system has many assessments.
* One assessment relates to exactly one AI system.
* One assessment may reference a previous assessment.
* One assessment has many responses.
* One assessment has many risks.
* One assessment has many applicable controls.
* One risk may be linked to many controls.
* One control may address many risks.
* One assessment has one calculated classification outcome at a time, with historical rule results.
* One tenant may have multiple risk policies, but only one policy should normally be active for a given scope and date.
* One product may map to multiple system types, use cases, capabilities, risks, controls, and deployment contexts.
* One evidence item may support multiple assessment entities.
* One assessment may produce multiple reports and report snapshots.

---

# 11. Backend Architecture

## 11.1 Architectural Style

The initial product shall use a modular monolith.

This provides:

* Faster implementation
* Simpler transactions
* Easier debugging
* Lower deployment complexity
* Easier evolution while the methodology remains under development

Modules may later be extracted into services if required.

## 11.2 Proposed Stack

* Backend: Python and FastAPI
* ORM: SQLAlchemy 2.x
* Validation: Pydantic
* Database: PostgreSQL
* Database migrations: Alembic
* Object storage: Amazon S3 or compatible service
* Authentication: Amazon Cognito or equivalent OIDC provider
* Frontend: Next.js
* Background jobs: Celery, RQ, or cloud-native job processing
* Cache and queue: Redis where required
* Deployment: AWS
* Infrastructure as code: Terraform
* Reporting: server-side PDF and document generation

## 11.3 Why PostgreSQL

PostgreSQL is preferred because the platform requires:

* Strong relational integrity
* Transactional consistency
* Complex joins and reporting
* JSONB for rule definitions and flexible metadata
* Row-level security
* Mature indexing
* Audit-friendly data modelling
* Support for multi-tenant SaaS architectures
* Good integration with FastAPI and SQLAlchemy

## 11.4 Database Administration

A graphical database administration tool shall be used during development.

Suitable options include:

* pgAdmin
* DBeaver
* DataGrip
* TablePlus

---

# 12. Backend Modules

The backend shall initially contain the following modules:

* Authentication and authorisation
* Tenant and organisation management
* User and role management
* AI system registry
* Taxonomy management
* Product catalogue
* Product intelligence and prefill engine
* Assessment workflow
* Questionnaire engine
* Classification engine
* Risk engine
* Risk policy engine
* Controls and obligations
* Evidence management
* Reporting
* Audit logging
* Notifications

---

# 13. Non-Functional Requirements

## 13.1 Security

The platform shall support:

* Tenant isolation
* Role-based access control
* Row-level security where appropriate
* Encryption in transit
* Encryption at rest
* Secure object storage
* Signed upload and download URLs
* MFA for privileged users
* Secrets management
* Rate limiting
* Input validation
* Audit logging
* Secure administrative separation

## 13.2 Auditability

Every material automated output shall be traceable to:

* Input data
* Taxonomy
* Product profile
* Rule version
* Methodology version
* User confirmation or override
* Decision maker
* Timestamp

## 13.3 Explainability

The platform shall explain:

* Why a question was asked
* Why a field was prefilled
* Why a risk was generated
* Why a classification was assigned
* Why a treatment was proposed
* Why an exception rule was triggered

## 13.4 Maintainability

* Business rules shall not be embedded solely in route handlers.
* Taxonomies and catalogue values shall be database-driven.
* Rules shall be versioned.
* Assessments shall preserve the versions used.
* Framework content shall be separated from assessment-instance data.
* JSONB shall be used selectively for rules and metadata, not as a substitute for proper relational modelling.

## 13.5 Performance

The MVP shall support normal consulting and organisational workloads without microservice decomposition.

Indexes shall be prioritised for:

* Tenant
* Organisation
* AI system
* Assessment
* Assessment status
* Risk level
* Product
* Taxonomy
* Created and updated dates

---

# 14. MVP Scope

## 14.1 MVP Features

The MVP shall include:

* Tenant management
* Organisation management
* Authentication
* Core roles
* AI system registration
* Core taxonomies
* Known product selection
* Other product workflow
* Basic product profiles
* Safe product-based prefills
* One-system-per-assessment model
* Lifecycle-stage assessment
* Dynamic questionnaire
* Initial EU AI Act classification rules
* Risk scenario seeding
* Inherent and residual risk scoring
* Tenant risk tolerance
* Default treatment by risk band
* Override support
* Basic policy exceptions
* Control mapping
* Evidence upload
* Audit trail
* Assessment report generation

## 14.2 MVP Taxonomy Scope

The MVP should begin with a controlled and relatively small set of:

* AI system types
* Use case categories
* Use case subcategories
* Deployment contexts
* Risk domains
* Risk scenarios
* Controls
* EU AI Act classification indicators

## 14.3 MVP Product Catalogue Scope

The first catalogue should prioritise widely used enterprise products that have sufficient public documentation.

Initial product coverage should focus on categories such as:

* Enterprise generative AI assistants
* Coding assistants
* Office productivity copilots
* General-purpose model APIs
* Enterprise AI development platforms
* Customer service AI tools

The initial catalogue should remain curated rather than attempting comprehensive market coverage.

---

# 15. Future Product Capabilities

Potential later capabilities include:

* Automated public documentation ingestion
* Product profile update alerts
* Vendor due diligence
* Model and API version tracking
* Continuous AI system monitoring
* MLOps integration
* Ticketing integration
* GRC platform integration
* Automated evidence collection
* System-level and organisation-level AI risk registers
* AI impact assessments
* Fundamental rights impact assessments
* Regulatory role determination
* Multi-jurisdiction mapping
* Risk benchmarking
* Board dashboards
* AI-assisted narrative generation
* Automated report drafting
* Control testing
* Assurance workflows
* Audit preparation
* Client portal collaboration

---

# 16. Key Risks and Design Safeguards

## Risk: Product documentation may be outdated

Safeguards:

* Record source and review date.
* Assign confidence levels.
* Version product profiles.
* Require user confirmation.
* Flag stale profiles.

## Risk: Product defaults may not represent actual deployment

Safeguards:

* Treat prefills as suggestions.
* Ask contextual questions.
* Allow override.
* Preserve override rationale.
* Use effective confirmed values for scoring and classification.

## Risk: Automated acceptance could create governance exposure

Safeguards:

* Apply tolerance primarily to residual risk.
* Use exception rules.
* Prevent auto-acceptance of prohibited or critical risks.
* Require approval where configured.
* Maintain immutable audit records.

## Risk: A large taxonomy may become difficult to manage

Safeguards:

* Start with a controlled MVP taxonomy.
* Support hierarchy and versioning.
* Deactivate rather than delete used values.
* Govern taxonomy changes.

## Risk: The assessment may become too generic

Safeguards:

* Use product, lifecycle, use case, sector, and deployment context.
* Seed relevant risks.
* Use adaptive questions.
* Allow custom risks and controls.

## Risk: Regulation and standards will change

Safeguards:

* Version frameworks, rules, questionnaires, taxonomies, scoring profiles, and product profiles.
* Preserve the version used by each assessment.
* Support reassessment after regulatory changes.

---

# 17. Initial Success Measures

The product should be evaluated against the following measures:

* Percentage reduction in free-text fields
* Percentage of assessment fields safely prefilled
* Percentage of prefills accepted without modification
* Average time to complete system registration
* Average time to complete an assessment
* Number of questions removed by adaptive logic
* Percentage of risks automatically seeded
* Percentage of treatment decisions generated by policy
* Number of overrides
* Number of stale product profiles
* Assessment completion rate
* Reviewer acceptance rate
* Time required to generate an audit-ready report
* User confidence in classification and treatment explanations

---

# 18. Initial Product Decisions

The following decisions are considered agreed for the initial design:

1. PostgreSQL shall be the primary relational database.
2. The initial architecture shall be a modular monolith.
3. Each assessment shall relate to one AI system.
4. An AI system may have multiple assessments.
5. Assessments shall support lifecycle stages and reassessment triggers.
6. Tenants shall define risk tolerance and treatment policy.
7. Default treatment may be auto-applied where permitted.
8. Overrides shall be supported and auditable.
9. Residual risk shall normally be used for tolerance comparison.
10. Critical, prohibited, and mandatory legal risks shall support hard-stop policies.
11. Free-text input shall be minimised through controlled taxonomies.
12. Known products shall provide safe, source-backed prefills.
13. Product defaults shall remain overridable.
14. Operational reality shall supersede public product documentation.
15. Framework, catalogue, methodology, questionnaire, and rule content shall be versioned.

---
