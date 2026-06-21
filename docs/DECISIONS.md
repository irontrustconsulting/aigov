# DECISIONS.md — IronTrust AI Governance Platform

**Location:** `docs/DECISIONS.md` — single source, mirrored to project knowledge. Updated once.
**Purpose:** Locked design decisions and the load-bearing rationale (and rejected alternative, where there was one) that an agent needs in order not to undo them. Cited by `D-n`.

**Discriminator:** a decision earns a `D-n` entry only if it carries rationale or a rejected alternative. A bare rule with no "why" stays in `INVARIANTS.md` and is not duplicated here. Where a decision is *realised* by an invariant, this entry cites it (`enforces: INV-n`); the invariant states the constraint, the decision states why it exists.

**Format:** `D-n · Title` / decision + why (+ rejected alternative) / `↳ enforces · refs · source`.
**Provenance note:** `source:` refs (PRD §, sprint design docs) are *historical provenance only* — they survive inside this file because the source documents are being removed. Cross-references between canonicals always use IDs, never §-numbers.

---

**D-1** · §1.5 product spine — strong default → shown reasoning → easy override → tracked deviation
For every position the product asserts (classification, AIIA content, catalogue prefill) it: proposes a confident standards-grounded answer rather than a blank field; shows the basis it rests on (the standard/clause/criterion); accepts a low-friction amendment; and records any override (who, when, ideally why). In code: propose, expose basis, accept amendment, write the delta to `AuditEvent`. **Why:** this is what separates *opinionated* (an asset — the opinion is the product) from *unaccountable* (a liability). The org stays accountable for what it accepts.
↳ refs: cross-cutting (CLS/AIIA/CAT), INV-13 · source: PRD §1.5, §4 cross-cutting

**D-2** · Recommended position, not certification (liability boundary)
The product offers a *recommended* classification/assessment the user confirms; it never certifies the organisation's compliance. Language is deliberate — "recommended," not "compliant." **Why:** keeps the authority the tool projects aligned with the accountability it actually bears. **Rejected:** asserting compliance or certification (false authority, legal exposure).
↳ source: PRD §1.4–1.5

**D-3** · Human-in-the-loop is non-negotiable
Automation accelerates and structures judgement — prefill, cross-mapping, gap detection, drafting — but never authors the assessment conclusion, the risk-acceptance decision, or sign-off. AI output is always marked as a suggestion and requires human acceptance. **Why:** defensibility — an auto-generated conclusion does not survive an auditor. **Rejected:** auto-generating conclusions or tiers.
↳ refs: AIIA-6, RSK-5/7, INV-30 · source: PRD §1.4, §5

**D-4** · SoD is first-class — reviewer recommends, authoriser accepts; PRD §4.9.1 governs
Governance roles are SoD-constrained by a conflict matrix at assignment: every cross-line pair conflicts, only `system_owner + contributor` compose, and reviewer/authoriser are separated (the party that recommends cannot be the party that accepts residual risk). **Why:** a governance product whose own role model let one person perform and approve would undermine the discipline it sells. **Critical:** even where a sprint or design doc misstates this, PRD §4.9.1 is the authority — flag the inversion, never silently encode it.
↳ enforces: INV-7, 28, 29 · refs: WKF-1/5, D-10 · source: PRD §4.9.1

**D-5** · Admin confers no governance power; self-assignment is closed
The administrative axis (`Membership.role`) manages members and assigns governance roles but carries zero governance capability. Assigning governance roles is the *only* point at which administration touches governance — so self-assignment is blocked, closing the sole administration→governance escalation path. **Why:** prevents an admin bootstrapping themselves into sign-off authority.
↳ enforces: INV-7 · refs: WKF-6 · source: PRD §4.9.1

**D-6** · Substantive act → domain row + audit event, not `AuditEvent.detail` alone
Decision-grade governance records — review decisions (`AssessmentReview`), the ATO (`DeploymentAuthorisation`) — are first-class domain tables, not strings in `AuditEvent.detail`. **Why:** domain tables are queryable, reviewable, FK-constrained governance evidence an auditor can interrogate; the audit log is the trail, not the record. **Rejected:** recording review/authorisation decisions only in the audit log.
↳ refs: INV-5; AssessmentReview / DeploymentAuthorisation (DATA-MODEL) · source: S6a design

**D-7** · Prohibition supremacy is unconditional
A `PROHIBITED` classification forces `halted_prohibited` from any non-terminal state, including `authorised`, with no exception path — read off the current classification snapshot's `tier`, never `eu_tier`. **Why:** a prohibited practice must never sit un-halted merely because it was authorised under an earlier classification. There is no safe-harbour.
↳ enforces: INV-26, 33 · refs: LFC-3 · source: PRD §3.1, §4.1.1

**D-8** · Tier from deployment context, never the catalogue
The catalogue supplies facts only; the EU AI Act tier is always derived from how the organisation *uses* the system (bridge or context-question gate). **Why:** a prefilled fact misread as a tier assertion produces confident wrong classifications — the product's single biggest correctness risk. **Rejected:** deriving tier from the product/catalogue.
↳ enforces: INV-10 · refs: CAT-3, CLS-1 · source: PRD §10 risk, §4.3–4.4

**D-9** · Classification is authoritative only on reviewer sign-off
The context-question gate writes a `PENDING_REVIEW` snapshot and does **not** stamp `use_case.eu_tier`; reviewer sign-off flips it to `APPROVED` and stamps `eu_tier` — the act that makes a classification authoritative. **Why:** classification is a 2nd-line reviewable act, not a 1st-line self-assertion. Recommend ≠ authoritative.
↳ refs: D-4; CLS, WKF-3 · source: STATE context-gate; PRD §4.9.1

**D-10** · Residual-risk acceptance is the authoriser's act
`residual_risk_statement` is authored on the ATO by the authoriser at `authorise_use_case` time — never derived from or assignable to the reviewer's AIIA approval. **Why:** preserves recommend ≠ accept SoD; the reviewer recommends, the authoriser accepts the residual risk.
↳ enforces: INV-29 · refs: D-4, EXP-1a · source: PRD §4.9.1; S6b design

**D-11** · Stale-ATO prevented by the `submission_round` cycle key
An ATO's validity is bound to the `submission_round` it was granted against; `authorisation_gate` passes only when the ATO's `submission_round` equals the AIIA's current one. **Why:** re-evaluation must never let a prior authorisation token auto-restore `authorised` state without a fresh authoriser action — a re-submitted cycle orphans the prior ATO.
↳ enforces: INV-37, 35 · refs: D-12 · source: S6b design

**D-12** · `authorised` is entered only by `authorise_use_case`; re-eval ceiling at `pending_authorisation`
The auto-advance walk has no entry past `pending_authorisation`; only the explicit human act crosses into `authorised`. `re_evaluate`'s restore branch can target only vector-guarded states, so a regressed-then-restored use case lands at `pending_authorisation` and waits for re-confirmation — even when an existing ATO still cycle-matches. **Why:** a cycle-matching ATO must never be sufficient on its own to auto-authorise.
↳ enforces: INV-35 · refs: D-11 · source: S6b design

**D-13** · ATO durable identity stamping (name/email as text)
The ATO stamps `authorised_by_name`/`email` as text at write time, not FK-only. **Why:** the ATO is export-grade and must stay attributable even after a user is anonymized (fields wiped, row kept). This is the one place durable attribution exists today; the general gap is D-25.
↳ refs: D-14, D-25, INV-34 · source: S6b design

**D-14** · Snapshot-as-text for point-in-time auditability
Records that must outlive their mutable-in-place source stamp basis values as text, not FK-only: Classification snapshots stamp basis values; the ATO stamps tier, identity, residual-risk. **Why:** an FK alone breaks when the referent changes or is anonymized — a point-in-time record needs the value frozen.
↳ refs: D-13 · source: STATE classification/ATO

**D-15** · Fixed, opinionated lifecycle — determinate state machine, not a workflow engine
The MVP lifecycle is one fixed flow (vendor → product → intake → assessment → treatment → authorisation), a determinate state machine over known states. Configurability, branching approval chains, and a general event/BPM engine are out of scope. **Why:** the value is productised best-practice, not a blank configurable canvas; over-engineering into a general engine is a named build risk. **Rejected:** a configurable workflow builder.
↳ enforces: INV-24, 25 · refs: LFC-6, scope · source: PRD §4.1, §10 risk

**D-16** · Capture-once / orchestrate-in-the-background
Intake captures the universal, knowable-up-front context in one uninterrupted flow; the state machine then drives the gates, asking for more data just-in-time only when a transition needs it (and explaining why). The user is never marched gate-by-gate during capture. **Why:** makes the lifecycle effortless for a user who doesn't know the process — the differentiator over form-holding incumbents. Provision (1st-line) and judgement (2nd/3rd-line) stay distinct acts, so capture-once and SoD coexist.
↳ refs: IXN-1..5, D-4 · source: PRD §4.1.3

**D-17** · Layered approval; the use-case engine rolls upward; VDD collapses to thin diligence + rollup view
Three inheriting approval scopes (vendor → vendor+product → vendor+product+use-case). The use-case lifecycle is the primary engine and its output rolls **upward**: the first use case of a never-seen product does double duty — it authorises that use case AND constitutes most of product-level approval. Full VDD collapses into (a) thin, genuinely vendor-level diligence plus (b) a product-level rollup *view* over use-case evidence. **Why:** this *reduces* deferred surface area rather than adding a parallel module. **Rejected:** VDD as a separate parallel diligence module.
↳ refs: APR-1..7 · source: PRD §4.1.4

**D-18** · Read-time propagation over materialization
Where one entity's content must appear inside another's read response (feeders → AIIA), assemble a view at read time and tag the source — never copy rows or sync on edit. **Why:** a single read-time assembly locus cannot drift; a materialized copy needs a sync step that goes stale. **Rejected:** writing feeder copies into the AIIA.
↳ enforces: INV-16 · source: STATE patterns; S3–4

**D-19** · Evidence → control is transitive via items; evidence sits outside the provenance machine
There is no direct evidence↔control table — framework satisfaction derives via the item an evidence is linked to and the control-library cross-map. Evidence carries no `ProvenanceConfidence` tag: it's a user-origin artifact, not a system-asserted default. **Why:** keeps the cross-map the single source of framework coverage; evidence is not a §1.5 assertion. **Rejected:** a direct evidence↔control table; tagging evidence with provenance.
↳ enforces: INV-21 · source: STATE evidence

**D-20** · Evidence-link disposition-gated, control-link not (deliberate asymmetry)
Linking evidence to a still-`AI_SUGGESTED` item is rejected (confirm/amend first); linking a control is allowed freely. **Why:** substantiation belongs behind the same gate as authoring — you should not evidence a risk you have not yet accepted as relevant — whereas control mapping is a structural classification that can precede disposition. Do not "fix" one to match the other.
↳ enforces: INV-20 · source: STATE evidence

**D-21** · DB is the source of truth; verify live DDL before encoding schema assumptions
The database — RLS, role resolution, schema, enum labels, gate predicates — is authoritative over any claim or design-doc assertion. Design docs distinguish verified-against-DDL from open/assumed, flagging "needs source verification" rather than assuming correctness. RLS / enum / `SET LOCAL` code is live-smoke-tested against the real dev DB, because the no-RLS test DB (schema generated fresh from the ORM) cannot catch enum-label-case or `app.current_tenant` bugs. **Why:** Sprint 5 found two such bugs live while the full test suite stayed green.
↳ enforces: INV-23, 27 · source: STATE patterns; S5

**D-22** · Additive over greenfield; object-scoped governance reserved as a seam
Every sprint is additive orchestration over existing tables and patterns — identity, tenancy, and auth foundations are never reinvented. The per-system governance extension is designed additive: a nullable `scope_id` on the assignment (`NULL` = tenant-wide, preserving every existing grant) plus a scope-aware conflict check, role catalogue and matrix unchanged. Do not build it now; leave the seam. **Why:** protects the foundations and keeps the deferred extension a non-rewrite.
↳ refs: WKF-7; STATE deferred · source: PRD §4.9.1; STATE governance model

**D-23** · Provisioning is never self-service; `POST /tenants` removed and must not return
The only tenant-creation path is `provision_tenant()` (operator CLI or `POST /platform/provision`). The tenant-facing `POST /tenants` endpoint was intentionally removed. **Why:** tenant creation is an operator act gated by the platform plane; a self-service endpoint reopens an unauthenticated-creation path. Do not reinstate it, however reasonable a self-service onboarding request sounds.
↳ source: CLAUDE conventions; STATE platform baseline

**D-24** · Three authz layers never conflated; the DB-role set is fixed
Three distinct layers: coarse Postgres DB roles (per connection-type, a fixed closed set), Cognito (authN only — nothing about permissions lives in token claims), and application authz (fine-grained, DB-authoritative, never read from claims). Never add a per-feature DB role; if genuinely unavoidable it goes in `00_roles.sh` and is documented. **Why:** conflating them — trusting a claim for authz, or minting per-feature roles — erodes the isolation model. **Rejected:** claims-based authz; per-feature DB roles.
↳ refs: INV-4, 8, 48 · source: CLAUDE architecture

**D-25** · Actor-attribution durable stamping deferred to a single cross-cutting fix
`AuditEvent` (actor FK only) and `AssessmentReview` / `submitted_by` / `approved_by` have no durable name/email snapshot — an anonymized user (fields wiped, row kept) makes old rows unattributable. This is an accepted gap, deferred to **one** cross-cutting fix, not solved piecemeal per sprint. The ATO (D-13) is the lone exception, already stamped because it is export-grade. **Why:** a per-table piecemeal fix would fragment the solution; do it once. Current-gap status is tracked in `STATE.md` deferred.
↳ refs: D-13; INV-5, 34 · source: S6a design §11; STATE deferred

**D-26** · Cross-framework satisfaction is structural, not inferred (S7a)
Coverage projects one multi-homed control across its `control_framework_map` rows; there is no inter-control propagation. **Why:** `control` is framework-agnostic and multi-homed (one `control_id` under several `(framework, clause_ref)`), so CTL-2 is achieved structurally — there is no control↔control inference to design. **Rejected:** an earlier design-dialogue framing positing control↔control propagation.
↳ enforces: INV-39 · refs: D-19 · source: S7a D2

**D-27** · Coverage and applicability are orthogonal axes (S7a)
A coverage verdict asserts *how well evidenced* a control is, never *whether it applies*. `coverage_status` has no `NOT_APPLICABLE` label by design; N/A belongs solely to the deferred applicability layer. **Why:** keeps the two axes from conflating — a control out of scope is an applicability fact, not a coverage one.
↳ refs: OPEN-3 · source: S7a D7

**D-28** · Interim coverage denominator = controls-in-play + flagged unaddressed list (S7a)
Until applicability lands, the matrix reports controls with ≥1 qualifying link, plus a separate flat `unaddressed_controls` list flagged `not_an_obligation_set`. **Why:** a whole-library denominator falsely fails a minimal-risk use case on high-risk controls; a linked-only view hides gaps. The flagged list shows gaps without asserting obligation. Applicability replaces it with an applicable/excluded partition later.
↳ refs: OPEN-3 · source: S7a D8

**D-29** · Coverage counts disposition; the audit-grade export counts evidence (S7a → S7b)
The interactive view counts a `SATISFIED` link without an evidence row (`require_evidence_for_satisfied=false`) — many ISO 42001 controls are satisfied by documented process, not an artifact. The **export** passes `true` on every coverage call: an unsubstantiated `SATISFIED` **downgrades to `PARTIAL`** ("asserted, unsubstantiated"), never drops, and carries a first-class `downgraded_unsubstantiated` count. **Why:** an unsubstantiated claim must not read `SATISFIED` in an audit deliverable, but downgrade-not-drop keeps an assessed control from falsely reading `UNADDRESSED`; the distinct count separates it from genuine partials.
↳ refs: INV-20 · source: S7a D5, tightened by S7b D13

**D-30** · Export is a live pack + canonical `content_hash`, never a frozen artifact (S7b)
The pack is assembled live; metadata carries `generated_at, scope, content_hash`, the hash computed over a canonical serialization (sorted keys, ISO-8601 UTC, no insignificant whitespace — JCS/RFC 8785) *before* staging `export.generated`. **Why:** most content is already immutable, so a stored export would be a second source of truth; a hash is only reproducible over a canonical form. **Rejected:** persisted/frozen export artifacts (deferred).
↳ enforces: INV-43 · refs: PAT-10 · source: S7b D1

**D-31** · Export references evidence by manifest, never bytes or URLs (S7b)
Evidence appears as a manifest (`id, sha256, filename, content_type, size, back-refs`); retrieval stays on the hardened `GET /v1/evidence/{id}`. **Why:** durable JSON carrying minute-TTL presigned URLs is dead on arrival, and bytes belong in S3. **Rejected:** embedded presigned URLs / inlined bytes.
↳ enforces: INV-40 · refs: INV-6, 22 · source: S7b D2

**D-32** · Export AIIA section = native items + `surfaces_into`, never re-assembled (S7b)
The export lists native AIIA items only, plus each feeder as a full sub-record (incl. private sections) carrying `surfaces_into` cross-refs; it never calls `assemble_aiia_items`. **Why:** re-assembling would double-list every surfacing feeder item and create a second surfacing locus that INV-16 reserves to `assemble_aiia_items`. **Rejected:** calling the AIIA assembler in the export.
↳ enforces: INV-41 · refs: INV-16, D-18 · source: S7b D3

**D-33** · Audit-trail closure = entity-id OR detail-back-ref; completeness bounded and honest (S7b)
The audit section is an entity-id closure (including link-row and approval-row ids, since those events key to the join/approval row, not the parent) **plus** a `detail->>'item_id'` back-ref for ephemeral/removal events. **Why:** control/evidence link rows hard-delete, so a current-rows closure drops both the `.created` and `.deleted` of any removed link — add/remove pairs vanish; the `detail` back-ref survives the deletion. Completeness is stated as "resolvable to a surviving in-scope entity," with a characterised bounded residual (`assessment.deleted` pristine-only; `evidence.access` on since-unlinked evidence) — not an overclaimed "complete closure."
↳ enforces: INV-45 · refs: INV-5, 19 · source: S7b D4, D14

**D-34** · ATO-basis honesty — current state, never reconstructed (S7b)
The export's ATO document treats the `DeploymentAuthorisation` row (text-stamped tier/identity/residual) as authoritative, and shows the referenced assessment/classification as **current state, may have drifted**, labelled as such — never reconstructed to the authorisation moment. **Why:** the assessment is mutable-in-place and AIIA versioning is deferred, so a faithful historical reconstruction isn't available; honest labelling beats a false snapshot.
↳ enforces: INV-44 · refs: INV-32, OPEN-2 · source: S7b D5

**D-35** · Export runs REPEATABLE READ on a self-owned session that owns its commit (S7b)
The export route depends on `get_tenant_context` (no session); the export opens its own session, sets `REPEATABLE READ` before the first query, then `SET LOCAL app.current_tenant`, assembles, and owns the `export.generated` commit. **Why:** a multi-use-case pack must be internally consistent (snapshot isolation), Postgres requires the isolation level before the transaction's first statement, and reusing `get_tenant_db` would own the commit and run READ COMMITTED. **Rejected:** `get_tenant_db` / READ COMMITTED for the pack.
↳ refs: PAT-10; INV-27 (ordering cousin) · source: S7b D7

**D-36** · Platform functionality is UI-operated; CLI is bootstrap/break-glass only
Every platform-plane capability that requires ongoing operator interaction is built as operator-console UI, not left as a CLI/script affordance. CLI/scripts are reserved for what must precede or underlie the UI itself — DB-role creation (`00_roles.sh`), first-operator seeding, the first tenant before any console exists. **Why:** an operator-facing capability with no UI quietly becomes "ops runs a script," which has no audit trail discipline, no SoD surface, and doesn't scale past the founding team — the UI is the enforcement point for those properties, so a platform feature that needs interactive operation isn't done until its operator UI ships with it. **Rejected:** shipping backend capability with a CLI/script as the interim operator interface and deferring the UI as follow-on work — the deferral never closes in practice.
↳ enforces: INV-49 · refs: INV-1 · source: platform-UI rule (retroactively closed at UI-F0-FOUNDATION — cited as INV-49/D-36 by `PLATFORM-UX.md`, `UX.md`, `FRONTEND.md`, `INDEX.md` since before this sprint, but never appended until now)

**D-37** · Frontend topology: Next BFF per plane, separate origins, bearer-forward (UI-F0-FOUNDATION)
Each plane (tenant, operator) gets its own Next.js app whose server layer is the BFF: it runs the Cognito authorization-code+PKCE flow against that plane's own pool, holds the resulting ID token server-side keyed by an opaque session id, and forwards the bearer to the FastAPI backend, which is unchanged. Plane separation is structural at the origin level — a tenant session cookie is physically un-sendable to the operator origin. **Why:** keeps the existing `verify_cognito_token`/`verify_operator_token` contract untouched (additive, not a backend auth rewrite) while making token custody and plane separation a frontend architectural property, not a discipline to remember. **Rejected:** SPA-direct token-in-browser (violates INV-50, exposes the token to XSS); cookie-direct-to-API (couples the API to browser cookie/CORS concerns it does not otherwise need, and still risks token-in-browser if the cookie itself carries the token rather than an opaque id).
↳ enforces: INV-50 · refs: INV-1, D-22, D-24 · source: UI-F0-FOUNDATION

---

## UI-F1-INTAKE local decisions (`DF1-n`)

Sprint-local decisions, scoped to the intake wizard — a separate id series from the global `D-n` sequence (the design doc minted these; only the ones an agent needs to not silently undo are promoted here at sprint close).

**DF1-3** · Reviewer sign-off is out of F1 scope
F1 ends at `PENDING_REVIEW` on the context path; whose-court (WI-9) routes to "with the reviewer" and stops there — `POST .../classification/sign-off` is not wired. **Why:** sign-off belongs to the assurance face's review queue (a separate, not-yet-built surface); wiring the act without the queue/attribution surface it lives in would be a half surface, not a deferred one.

**DF1-4** · Prefill is catalogue-fact-only
WI-6 renders only `CatalogueFactOut` rows from `GET /systems/{id}/prefill` — the AI-suggested and cross-tenant-baseline prefill sources `UX.md` §3 describes are not wired. **Why:** those sources are flagged `[VERIFY]`/deferred in `UX.md` §3 (`OPEN-3`-adjacent), and the catalogue-fact route is the only landed prefill backend.

**DF1-5** · `If-Match` is dormant in F1
No F1 hook ever sets `If-Match` (`FE-6` stays dormant) — asserted by test (`apps/tenant/lib/intake/__tests__/network.test.tsx`). **Why:** every F1 mutation is a create or a state-machine-driven write, not the `lock_version`-guarded amend pattern `FE-6`/`PAT-6` exists for; none of the consumed routes accept the header.

**DF1-8** · Prefill is display-only; no write-back
WI-6's "amend" control updates only local wizard display state and never issues a mutation. **Why:** the structured WI-5 fields already submitted via `POST /v1/systems` are the system of record for the tenant's asserted truth; there is no backend route to write back an amended catalogue fact, and adding one would create two sources for the same fact.

**DF1-9** · Vocab-list routes added despite F1's "zero backend" framing
Six read-only `GET /v1/reference/{operator-roles,hosting-models,usage-contexts,human-oversight-types,data-categories,affected-parties}` routes were added (`app/routers/v1/reference.py`), reusing existing schemas (`VocabItemOut`/`DataCategoryOut`/`AffectedPartyOut`, already defined for `SystemDetail`) and the same any-member gate as the neighbouring `risks`/`controls` reads. **Why:** WI-5's structured selects for these six FK fields had no source of options — only FK-validation against them existed on write, never a listing route; the gap was found at this sprint's §0 pre-flight and the addition was scoped and approved before WI-5 was built. "Zero backend" covered migrations/schema (genuinely zero here — no new model, no new migration, no `DATA-MODEL` table/column change); it did not anticipate every read route the wizard would need. **Rejected:** stubbing the six selects against a hardcoded client-side list — risks drifting from the seeded DB and from the real FK ids the classification/AIIA logic depends on.
↳ refs: `DATA-MODEL` Controlled vocabulary · source: this sprint's §0 pre-flight

---

## OPEN — unresolved design questions affecting future work

**OPEN-1** · Worked-state void / withdraw path
A reviewed or approved assessment has no void/withdraw path — pristine hard-delete is the only removal today, and it is blocked the moment an assessment is worked. The void mechanics (who can void, what state it lands in, audit shape) are undesigned. Blocks any "retract an approved assessment" flow.
↳ refs: INV-17, 36; STATE deferred

**OPEN-2** · AIIA versioning / `NEEDS_REFRESH` triggers
The re-run cycle — detect material change → re-snapshot → flag `needs_refresh` — is unbuilt, though the fields exist (`Assessment.version`/`is_current`, `tier_snapshot`/`classification_version`). What counts as a *material change*, and what auto-fires a refresh, is undecided. Deferred post-MVP.
↳ refs: AIIA-7; STATE deferred

**OPEN-3** · Applicability layer (deferred — recorded design intent)
*Which* controls ought to apply to a use case, replacing 7a's interim flagged-unaddressed list with an applicable/excluded partition (at which point `UNADDRESSED` becomes "applicable but unaddressed"). Two mechanisms, both following the classification-override pattern (derive/declare a default, track the deviation as a domain row + audit event):
- **EU AI Act — derived, per use case:** `tier × operator-role (× subcategory) → applicable clause set`, resolved to controls via `control_framework_map`. Operator role is a first-class axis (EU obligations are role-conditioned). This is CLS-6.
- **ISO 42001 — declared, tenant-level:** a Statement of Applicability, default all-applicable, every exclusion justified and audited.
Path A confirmed (coverage shipped first, applicability next). Open forks: EU/ISO split granularity (tier×role minimum vs +subcategory). Not built.
↳ refs: D-27, D-28; CLS-6