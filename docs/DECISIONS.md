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

**D-38** · Whose-court is a direct `blocking.responsible_party` read, mapped through a fixed party→role table (`UI-F2-PORTFOLIO`)
Court is read directly from `blocking.responsible_party` on every use case, with no pre-branch — the design doc's B1 hypothesis (a `PENDING_REVIEW → reviewer` mislabel needing a client-side `requires_context` pre-branch to `system_owner`) does not hold against live code: `app/services/lifecycle_gates.py`'s `classification_readiness` already disambiguates a `REQUIRES_CONTEXT`/`UNCLASSIFIED` use case correctly — `"reviewer"` while the classification snapshot is `PENDING_REVIEW` (the reviewer must act before the owner can), `"user"` once it isn't — and F1's own test suite already encodes this as correct behaviour. `SystemRollupRead`/`UseCaseRollupEntry` carries no `requires_context` field, confirming no pre-branch input exists. Because the gate's `responsible_party` vocabulary (`"user"|"reviewer"|"authoriser"|"vendor"|"system"`) is distinct from the governance-role vocabulary (`system_owner|contributor|reviewer|authoriser|auditor`), a fixed mapping resolves the match: `"user"`→`system_owner`, `"reviewer"`/`"authoriser"` 1:1, `"vendor"`/`"system"`→ no role (never anyone's court). The client highlight is presentational only; the backend remains the authz authority. **Why:** live verification at this sprint's binding pre-flight item (`V-2`) showed the hypothesised bug doesn't exist — implementing the described pre-branch would have actively overwritten a legitimate reviewer-court result with an incorrect owner one. **Rejected:** the design doc's `requires_context`-pre-branch algorithm, once V-2 resolved against live code.
↳ refs: `FE-8`, `INV-28`, `D-4`, `D-24` · source: `UI-F2-PORTFOLIO` §0 pre-flight (V-2)

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

## UI-F3-ASSESS local decisions (`DF3-n`)

Sprint-local decisions, scoped to the use-case work surface.

**DF3-1** · Evidence-linking deferred with the evidence-repository surface (A2 locked)
F3 renders `source_ref` fields as manifest-style text only — no bytes/inline (INV-22) — and reads existing `evidence_links` via `source_ref`. The evidence-link creation/management UI is deferred until the evidence-repository surface ships. **Why:** linking needs evidence to exist; there is no surface yet for creating or browsing evidence items.

**DF3-2** · Coverage panel deferred (A3 locked)
The headline control-coverage count is not shown on the F3 surface. **Why:** the coverage view reports on a governing-AIIA that is `APPROVED` (INV-38); showing counts on a `DRAFT` assessment would mislead (near-zero at start, meaningless as a progress signal).

**DF3-3** · Classification sign-off / review / authorise / queue / reopen reserved for F4 (act-SoD)
All assurance acts (`POST .../review`, `POST .../classification/sign-off`, `POST .../authorise`, `POST .../reopen`) are absent from F3. **Why:** act-SoD (INV-28) — the reviewer must not be the submitter, the authoriser must not be the approver; grouping all assurance acts into one F4 unit is the only shape that enforces this across the full lifecycle. The assembled-AIIA view built in F3 is reused read-only in F4.

**DF3-4** · `NEEDS_REFRESH` is author-open and resubmittable
A reopened or backend-flagged `NEEDS_REFRESH` AIIA presents with authoring fields unlocked (INV-31) and the submit control visible (`system_owner`). The `reopen` act itself (`APPROVED → NEEDS_REFRESH`) is **deferred**: `APPROVED` is unreachable until F4 ships, so reopen has no state to act on in an F3-only world.

**DF3-5** · FE-6 live — inverts DF1-5 dormancy
`If-Match` is sent on PATCH items, confirm items, and submit (`PAT-6`/INV-14). 412 (stale lock → `StaleLockBanner`, invalidate + reload) ≠ 409 (bad from-state → `BadFromStateBanner`, action void) — never collapsed. This is the first frontend surface to exercise the FE-6 concurrency path. Asserted by network test.

**DF3-6** · Feeder authoring remains provisional; V-8 is a confirmed scope hole (A7 not locked)
V-8 resolved at §0: required feeders DO gate `structural_assessment_readiness` (a missing `REQUIRED` feeder parks the use case with `"required_feeder_missing"`). A7's provisional defer is therefore a confirmed scope hole for any tier that has a `REQUIRED` feeder applicability. The feeder create+author UI is not built; the server-side gate will naturally block submit and advance for affected tiers. This must be revisited before any high-risk or regulated-AI tier is put into full-flow testing. **Why not build it now:** feeder authoring without the full feeder-surface (its own sections, item template, submission) is a half-surface (`DF1-3`-analogous). The full surface lands as its own sprint. **Rejected:** auto-creating required feeders silently — feeder creation is a `gov:write` act that must be human-initiated.

**DF3-7** · Backend additive delta: control_links in AssessmentItemRead (not a "backend delta none" violation)
`control_links: list[ControlLinkRead] = []` was added to `AssessmentItemRead` in `app/schemas/assessment.py`, and `assemble_aiia_items` was updated to batch-load them via `_batch_control_links`. The design doc's "backend delta none" referred to new routes, tables, and enum values — none of which changed. Adding a field to an existing response schema is an additive, non-breaking change. **Why needed:** there is no `GET` endpoint for control links on an item; without this field, control links would be invisible on page load after a browser refresh, making the feature unusable in practice. **Rejected:** client-side-only tracking of control links via React Query cache (lost on page refresh, poor UX for an audit-oriented governance tool).

---

## UI-F4-ASSURE sprint-local decisions

**DF4-1** · Topology B — portfolio whose-court is the entry index; `use-cases/[id]` is the single role-and-state-conditioned act surface
The reviewer AIIA queue (`apps/tenant/app/review-queue`) is a thin reviewer-only index linking to `use-cases/[id]`. Authoriser and reviewer sign-off work is surfaced from the portfolio whose-court forward-link (`DF2-7`). All acts land on `use-cases/[id]`. **Why:** reuses the landed `FE-11`/`court.ts`/`WhoseCourtIndicator` + the `DF2-7` forward-link seam; avoids fused-inbox dedup + reviewer-act-type disambiguation cost of Topology A. **Rejected:** a unified-queue index fusing all assurance acts (more dedup complexity, harder disambiguation).
↳ refs: DF2-7, FE-11, D-38

**DF4-2** · Reviewer's two acts disambiguated by object state, not court vocabulary
Both classification sign-off (`PENDING_REVIEW`) and AIIA review (`IN_REVIEW`) route `responsible_party == "reviewer"` in the lifecycle court. The act surface disambiguates by checking classification status and AIIA status independently; both panels can coexist if both conditions hold simultaneously (sequential in the normal case, but the surface handles both). **Why:** court vocabulary is presentation-level, not a routing key; duplicating a routing-key concept into the court string would violate FE-11. **Rejected:** separate court strings for the two reviewer acts (would require a stable-tier change to the lifecycle model).

**DF4-3** · act-SoD presentation is role-branch-first; across-reassignment edge degrades to act-time 403
Assignment SoD (`INV-7`) ensures reviewer ≠ submitter and authoriser ∉ {reviewer, submitter} in the common case; the role branch alone meets FE-8 structural absence for those branches. The across-reassignment edge (reviewer was reassigned after submitting) degrades to act-time 403 at the server (`assert_distinct_workflow_actor`, INV-28) surfaced as a blocked-reason via `BadFromStateBanner`. WI-9a (server-computed `caller_eligible` field) not elected: queue pre-filters `submitted_by_user_id != ctx.user_id` already, and the edge is rare. Client never compares raw individual identities (D-25/FE-11 spirit preserved).
↳ refs: INV-7, INV-28, D-4, FE-8, DF4-6

**DF4-4** · ATO terminal governed by INV-32 (`live_state`); drift caveat in the spirit of INV-44
The ATO terminal reads `live_state` from `GET /use-cases/{id}/authorisation` (never infers "authorised" from row existence). A drift caveat is shown when `live_state ≠ "authorised"` — in the spirit of INV-44 (the export-pack drift rule), cited only as precedent. INV-44 is the export-scoped rule; INV-32 is the live-state authority for the rendered terminal. **Why:** authority as of last read, not authority as of issue date — the rendered terminal must distinguish these.
↳ refs: INV-32, INV-44

**DF4-5** · Reopen ships in F4, on the authoring surface (`system_owner` branch, APPROVED AIIA)
`APPROVED → NEEDS_REFRESH` completes the rework loop; without reopen, `APPROVED` is terminal-for-rework. Reopen belongs where authoring lives, not the reviewer queue. Not OPEN-1 (void/withdraw — reopen is rework, not withdrawal). **Why:** the F3 surface is where the owner authorises and reviews their work; reopen is a natural extension of the owner's act set. **Rejected:** separate surface or placing reopen on the reviewer queue (wrong actor, wrong surface).
↳ refs: DF3-4, INV-31, OPEN-1

**DF4-6** · Backend response-shape deltas are additive; WI-9a not elected, WI-9b elected
Per §0 V-1: `list_review_queue` pre-filters submitter; no `caller_eligible` field needed for the common case. WI-9a not elected. Per §0 V-2: `AssessmentDetail` had no review history. WI-9b elected: `reviews: list[AssessmentReviewRead] = []` added to `AssessmentDetail`; `reviewer_display_name` from INV-34 membership join; no durable name/email stamp (D-25). Same additive pattern as DF3-7; no migration required; existing callers unbroken.
↳ refs: DF3-7, INV-34, D-25

---

## UI-F5-EVIDENCE sprint-local decisions

**DF5-1** · Closes DF3-1 — evidence linking ships with the evidence-repository surface
The evidence-link creation/management UI and the evidence repository are built together in one sprint rather than independently. **Why:** linking needs evidence to exist; building the repository without linking would deliver a write-only surface; building linking without a repository would require out-of-band evidence creation. The atomic delivery also defers one additive backend delta (`evidence_links` on `AssessmentItemRead`) until the field is actually consumed.
↳ refs: DF3-1

**DF5-2** · Upload routes through a dedicated BFF handler, not the generic proxy
`POST /v1/evidence` (multipart) routes through `apps/tenant/app/api/evidence-upload/route.ts`, not through `apps/tenant/app/api/proxy/[...path]/route.ts`. **Why:** the generic proxy reads `await request.text()` to forward the body; `request.text()` UTF-8-decodes binary bytes, corrupting the file content and producing a mismatched SHA-256 (confirmed by test). The dedicated handler reads `request.arrayBuffer()` and preserves the `Content-Type` header's `boundary=` parameter verbatim. **Rejected:** patching the generic proxy to use `arrayBuffer()` — the proxy is a general-purpose router; changing it to never call `text()` on any request could break form-body routes that legitimately need text decoding.
↳ enforces: INV-18; refs: FE-12, INV-22, NFR-1

**DF5-3** · Download is on-intent: `GET /evidence/{id}` fetched only on explicit click
`useEvidenceDetail(id, enabled)` is enabled only when the user clicks "Download"; the result URL is consumed once and the pending ID cleared. No per-row prefetch at list render time. **Why:** `GET /evidence/{id}` stages `evidence.access` in the audit log (INV-22); prefetching it for every visible row would inflate the audit trail without user intent.
↳ refs: INV-22, FE-7

**DF5-4** · No `If-Match` on evidence-link mutations
`POST .../evidence-links` and `DELETE .../evidence-links/{evidence_id}` carry no `If-Match` header. **Why:** the link table has no `lock_version` column; link idempotency is structural (`UNIQUE(item_id, evidence_id)`), not optimistic-concurrency guarded. `FE-6` dormant for these routes.
↳ refs: FE-6, PAT-6, API-ROUTES §5

**DF5-5** · Link is disposition-gated: `AI_SUGGESTED` items reject evidence linking
The server rejects `POST .../evidence-links` on an `AI_SUGGESTED` item (INV-20); the UI shows the link button disabled-with-reason, not absent, so a reviewer can see that linking exists but is blocked until the item is confirmed/amended. **Why:** a confirmed item carries the human's authoring intent; linking evidence to an unconfirmed suggestion would let a machine-proposed assessment accrue human-authored evidence without human endorsement.
↳ enforces: INV-20; refs: FE-8, DF5-5

**DF5-6** · Delete disabled-with-reason when `link_count > 0`; not absent
Evidence delete is structurally blocked server-side when linked (INV-19); the UI renders the control disabled-with-reason (not absent) when `link_count > 0`. **Why:** the user needs to know the evidence is linked and understand why deletion is blocked — absent-control gives no affordance to discover and fix the blocker. Asymmetry with SoD-barred controls (FE-8): SoD bars are structural (role-permanent); link-count blocks are transient (unlink first, then delete).
↳ enforces: INV-19; refs: FE-8

**DF5-7** · Admin (zero governance roles) → empty-state; no evidence request issued
The evidence repository home issues no `GET /v1/evidence` when the caller holds no governance role. **Why:** `GET /v1/evidence` is `gov:ALL`-gated; issuing it for an admin would return a 403 with no useful recovery path, adding noise. Consistent with the same branch in UI-F3-ASSESS and UI-F2-PORTFOLIO (DF2-5).
↳ refs: DF2-5

**DF5-8** · `ItemEvidenceRead` on `AssessmentItemRead` is a self-describing manifest; no `download_url`
The batch-loaded `evidence_links` field carries `title`, `sha256`, `content_type`, `size_bytes` — enough to display and audit — but never `download_url`. **Why:** including `download_url` would batch-generate presigned S3 URLs for every item on every AIIA page load, triggering `evidence.access` audit events without user intent (DF5-3) and adding S3 signing cost to every assembled-items read.
↳ refs: DF5-3, INV-22

**DF5-9** · Unlink path param is `evidence_id`, not a link-row id
`DELETE .../evidence-links/{evidence_id}` targets the natural key of the association, not the surrogate `assessment_item_evidence.id`. **Why:** the client never reads the link-row id (it's not in `ItemEvidenceRead`); requiring the client to do a separate lookup to recover the surrogate id before unlinking adds a round-trip with no benefit. The server uses `(item_id, evidence_id)` as the unique key for the delete.
↳ refs: DF5-8

**DF5-10** · Link/unlink invalidates AIIA-detail only; lifecycle key not invalidated
`useLinkEvidence` and `useUnlinkEvidence` call `queryClient.invalidateQueries({ queryKey: assessKeys.assessment(assessmentId) })` only. The lifecycle / whose-court key (`lifecycleKey(useCaseId)`) is not invalidated. **Why:** evidence linking has no effect on lifecycle state or gate readiness (`lifecycle_gates.py` does not read `assessment_item_evidence`). Invalidating the lifecycle key would trigger an unnecessary re-evaluate round-trip. D-29 (`require_evidence_for_satisfied`) is an export-layer concern, not a real-time gate.
↳ refs: D-29, FE-7, INV-25

**DF5-11** · Uploader display name omitted from MVP; `uploaded_by_user_id` is a bare UUID
`EvidenceTable` and `EvidenceDetailRead` carry `uploaded_by_user_id` as a UUID. The UI does not resolve or display the uploader's name. **Why:** there is no member-level `GET /v1/members/{id}` endpoint (the route is `admin`-gated), and no join in the evidence read path (D-25 deferred). Adding a per-row lookup to resolve names would introduce N+1 or a second query per page load; adding a join to `evidence_service` would widen scope beyond this sprint.
↳ refs: D-25

---

## UI-F6-AUDITPACK sprint-local decisions

**DF6-1** · Topology: dedicated `/audit` programme home + per-entity panels
`apps/tenant/app/audit` carries the tenant-wide coverage matrix, the framework export, and a pack index. `systems/[id]` (ALTER) gains a system-coverage panel + system-export action. `use-cases/[id]` (ALTER) gains a use-case-coverage panel (APPROVED-gated) + use-case-export action + ATO-document action. `UX.md §5` names audit-pack as its own surface; the auditor wants one coherent programme home while per-entity artefacts stay where the entity lives.
↳ refs: A1

**DF6-2** · Export/ATO-document generation is a deliberate, user-initiated fetch; coverage eager-loads
Export routes stage `export.generated` (INV-42, PAT-10/D-35); coverage emits no audit (INV-25). An audited disclosure must not fire on mount/focus; a pure read may.
↳ refs: A5, INV-42, INV-53

**DF6-3** · Interactive coverage is not audit-grade
`GET /coverage` family verdicts (internal `require_evidence_for_satisfied=false`) are labelled interactive posture; the audit verdict is the export-embedded coverage (`true`), which downgrades unsubstantiated `SATISFIED → PARTIAL` and carries `downgraded_unsubstantiated`. The two may differ and are visually distinguished. The interactive route exposes no flag to request `true` (N1), so the line is structurally non-bypassable.
↳ enforces: INV-51; refs: D-29

**DF6-4** · Coverage matrix is not an obligation set
The UI renders the `not_an_obligation_set` caveat prominently and presents `unaddressed_controls` as gaps-shown-not-failures. No "% compliant" headline treats unaddressed as fail until applicability (OPEN-3) lands. D-28: a whole-library denominator falsely fails a minimal-risk use case; the flagged list shows gaps without asserting obligation.
↳ enforces: INV-52; refs: D-28, OPEN-3

**DF6-5** · ATO document carries the drift caveat
`basis_is_current_state_not_authorisation_snapshot` is always true; the UI states the ATO row is the authoritative authorisation while the referenced assessment/classification are read live and may have drifted. Mirrors F4 (DF4-4). `AtoDocumentView` renders the caveat unconditionally — no conditional branch.
↳ refs: INV-44, D-34, DF4-4

**DF6-6** · PDF render deferred; interim is an in-DOM audit-pack view + browser print
F6 renders the structured export as a readable, dense, sectioned view; take-away is browser print-to-PDF. Templated PDF (EXP-3) and persisted/async export stay deferred. EXP-1 render-half is frontend/later; print covers MVP take-away without a render pipeline.
↳ refs: A3

**DF6-7** · EXP-2 auditor-scoping stays deferred
F6 surfaces auditor read on the existing any-governance-role gate; no thin auditor-membership scoping this sprint. EXP-2 post-MVP; the gate already admits auditor.
↳ refs: A2

**DF6-8** · `include_unapproved` is a labelled "in-progress, not audit-grade" toggle, default off
Per-use-case/per-assessment coverage renders only when the governing AIIA is `APPROVED` (else an empty-state), per INV-38/DF3-2. The `include_unapproved`+interactive combination is doubly non-audit-grade and never renders adjacent to audit-grade export-embedded coverage without an `AuditGradeDivider`. INV-38: coverage reports on an APPROVED governing-AIIA; an in-progress view must be opt-in and clearly labelled.
↳ enforces: INV-51, INV-52; refs: A4, INV-38, DF3-2

**DF6-9** · Single-home: lifecycle posture, control coverage, authorisation status, and ATO basis are distinct truths, cross-linked not duplicated
Dashboard "portfolio posture" (`PortfolioHub`) = lifecycle rollup; `/audit` coverage = control evidence; F4's ATO terminal (`GET .../authorisation`, `live_state`) = current authorisation status; F6's ATO document (`GET .../authorisation/document`) = take-away basis. F6 links to these truths, never restates them. Dashboard issues no coverage/export call.
↳ refs: A6

**DF6-10** · ATO-document round handling: default latest; no enumeration call
The standalone ATO document defaults to the latest round; a prior-round standalone document is a manual `?round=N` deep-link with no enumeration read. All rounds are visible and labelled (`submission_round`) inside the use-case export pack's `atos[]` — itself a deliberate audited generation (INV-53), so listing its own rounds costs no extra disclosure. **Rejected:** (b) a list-ATOs read (breaks zero-delta); (c) picker-generates-export (breaks DF6-2/INV-53).
↳ refs: B2, N3, INV-53, DF6-2

---

**D-39** · Durable operator identity contract — `GET /platform/me`
`GET /platform/me`, gated authenticated-operator-only (`get_current_operator`, no permission assertion), is the operator-plane analogue of `GET /v1/me`: DB-authoritative identity + effective permission set, safe for permission-aware render without blanket-gating on any specific permission. Promotes the F0 `GET /platform/whoami` verification aid (which was gated `require_permission("tenant:provision")` — unsuitable as the identity bootstrap for a permission-poor operator). Response drops `cognito_sub` (not needed by any consumer). Additive over greenfield (`D-22`); permissions resolved from the DB operator→role→permission chain, never from token claims (`D-24`).
↳ enforces: INV-8, INV-50 · refs: FE-13, A1/N4 (UI-F7-PROVISION) · source: UI-F7-PROVISION design doc A1

**DF7-1** · Root-branch B1 fix — zero-permission operator issues no gated call
Because `GET /platform/tenants` carries the same `tenant:provision` gate as `POST /platform/provision`, there is no "list-but-not-provision" operator role. The provisioning surface branches at the root on `'tenant:provision' ∈ permissions` (from `GET /platform/me`): with permission → issue both `GET /platform/tenants` and render the form; without permission → render empty state and issue **no** `GET /platform/tenants`. This prevents the zero-permission operator from receiving a 403 on the list call that would mask the real empty state. Follows the established "zero gated permission → issue no gated call" pattern (DF2-5, DF5-7).
↳ refs: D-39, FE-13, INV-8, D-24 · source: UI-F7-PROVISION design doc B1

**DF7-2** · Nav unbuilt-vs-absent axis — two distinct visibility states
Operator nav distinguishes two axes: (a) **unbuilt** surfaces render visible-disabled ("not yet available") to all operators — roadmap signalling, no capability behind the row; (b) **permission-lacking** controls render **absent** (`FE-13`) — a held permission governs presence. Forward rule: when an unbuilt surface is built and is permission-gated, its nav entry adopts FE-13 absence, never a greyed row.
↳ refs: FE-13 · source: UI-F7-PROVISION design doc N2/A2

**DF7-3** · FE-13 placement — operator-plane permission analogue, not a restatement of FE-8
`FE-13` is the operator-console analogue of `FE-8`: structural permission absence → not rendered. Its grounding is distinct — `INV-8`/`D-24` (operator authority is permission-through-role; permissions read DB-authoritative via `/platform/me`) rather than FE-8's act-SoD grounding. Lives in `FRONTEND.md` FE register with a one-line `FE-10` cross-reference; no `FE-8` restatement.
↳ refs: FE-8, FE-13, INV-8, D-24 · source: UI-F7-PROVISION design doc N3

---

**D-40** · API-ROUTES gate-column annotation for permissions whose key begins with `operator:`
The `operator:<perm>` shorthand (§1) expands to `require_permission("<perm>")`. For the permission key `operator:create`, the shorthand would render as `operator:operator:create` — a double-prefix that is both confusing and technically incorrect (it implies `require_permission("operator:create")` only if `<perm>` = `operator:create`, not if `<perm>` = `create`). Decision: when a platform permission key already starts with `operator:`, write the bare permission key in the gate column (e.g. `operator:create`), not the double-prefixed shorthand. **Why:** the shorthand's purpose is human legibility — it should not obscure the literal it expands to. **Rejected:** `operator:operator:create` (confusing); stripping the `operator:` prefix from the key (`create` alone — ambiguous with no namespace).
↳ refs: §3 operators routes, WI-7 (UI-F8) · source: UI-F8-OPERATOR-RBAC V-β/NB5

**DF8-1** · Platform RBAC seed expansion via migration revision, not seed loader
New permission/role rows for `UI-F8-OPERATOR-RBAC` are inserted in a new Alembic revision (`c8f3a2e91bd5`) following the `cef7211ddfe4` precedent — deployment data lives in the migration chain, not in a separate seed loader. `INV-48` scopes the seed loader to GLOBAL reference data only; PLATFORM-plane RBAC tables are not listed there. **Why:** migrations reproduce atomically in every environment, with full up/down symmetry; a side-channel seed loader creates ordering risk and duplicates the migration boundary.
↳ refs: INV-48, cef7211ddfe4 · source: UI-F8-OPERATOR-RBAC V-α

**DF8-2** · Shared `operator:create` gate for `GET /platform/operators` and `GET /platform/roles`
Both list routes share the `operator:create` gate rather than introducing a separate read-only permission. **Why:** there is no "list-but-not-create" operator role today; splitting gates would require a new permission with no holder. The surface branches at the root: without `operator:create` nothing is rendered and no gated call is issued (`DF7-1` pattern). **Rejected:** a separate `operator:read` permission (premature — no use case for a read-only operator manager).
↳ refs: DF7-1, D-40 · source: UI-F8-OPERATOR-RBAC DF7-1 (shared gate decision)

**DF8-3** · Operator status toggle and role re-grant/revoke deferred
`UI-F8-OPERATOR-RBAC` creates operators and lists them, but does not implement ACTIVE↔DISABLED status toggle or role re-grant/revoke mutations. **Why:** the operator pool is small at MVP; the genesis bootstrap loop and minting of new provisioners are the critical unblocked paths; the mutations require careful audit and UX design (who can revoke a `platform_admin`?). `INV-49`/`D-36` remain live and continue to govern future operator-management surfaces.
↳ refs: INV-49, D-36 · source: UI-F8-OPERATOR-RBAC sprint scope

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

**OPEN-4** · Genesis governance role bootstrap gap
When a tenant is first provisioned, the owner is the only member and holds the `ADMIN` administrative role with zero governance roles. D-5 blocks self-assignment — the acting admin cannot assign governance roles to their own membership. In a single-member or newly-provisioned tenant this means no one can assign the owner a governance role via the API; the owner is stranded at the "no portfolio to show" empty state. Current dev workaround: direct DB insert into `governance_role_assignment`. Path to resolution: (a) `provision_tenant` accepts an optional initial governance role and seeds the assignment at creation time, bypassing the self-assignment gate (provisioner is the granting actor); or (b) explicit grace exception for the membership created during `provision_tenant` in `assert_governance_assignable`. Not built; blocks real single-person onboarding.
↳ refs: D-5, INV-7; discovered: genesis bootstrap test 2026-06-24
---

## UI-V0-VISUAL-FOUNDATION decisions

**D-41** · Design-system foundation first: V0 core → V1 tenant skin → V2 operator skin (VDD-1)
Three-phase rollout. V0 installs the token core, two skins, and component treatments without committing to per-surface visual specifics that belong to V1/V2. This avoids speculative surface-level design before real usage is observed.
**Rejected:** combined restyle sprint per surface (no shared token foundation; visual drift inevitable); big-bang V0+V1+V2 (blocks shipping on unresolved per-surface design).
↳ refs: FE-14, INV-54

**D-42** · Neutral-evidentiary palette; chromatic colour reserved for semantic channels only (VDD-2)
The neutral ramp is grey-white with a single deep petrol-slate brand accent. Chromatic colour (`--prov-*`, `--verdict-*`, `--sev-*`) is rationed to its semantic channel and never used decoratively. This prevents colour inflation where meaning is diffused.
**Rejected:** branded chromatic identity (saturated greens/ambers/reds across the chrome → dilutes the signal meaning of verdict/severity tones).
↳ refs: FE-15, FE-16, INV-63

**D-43** · IBM Plex open-source type stack; self-hosted OFL (VDD-3)
IBM Plex Sans (UI), Mono (identifiers), Serif (export document face). OFL licence, self-hosted via `@fontsource`, no runtime CDN dependency. Mono carries `lock_version` and SHA-256 digests — critical for audit legibility.
**Rejected:** licensed type (ongoing cost, IP risk for EU buyers); Google Fonts CDN (CSP/privacy boundary issue for enterprise procurement); system-ui stack (no Mono for identifier legibility).
↳ refs: FE-17, INV-58, V-6

**D-44** · Light-first; dark slot reserved per token (VDD-4)
Every primitive and semantic token has an empty dark-mode comment slot (`/* dark: TBD */`). Dark ships as a skin override, not a rework. This makes V0 the complete contract for dark without building it yet.
**Rejected:** defer dark entirely (forces a rework of every token file when dark lands); build both now (unblocks V0 shipment on unresolved dark-mode UX research).
↳ refs: FE-14, OPEN-V1

**D-45** · Two skins = tenant vs operator; adoption/assurance is density within the tenant skin (VDD-5)
One token core, two `[data-theme]` overrides. The operator skin is the plane-separation marker (INV-1 / INV-60); the tenant skin is the adoption face. Adoption vs assurance posture is spacing- and component-default-driven inside the tenant skin, not a third theme.
**Rejected:** third adoption theme (explosion of skin maintenance overhead); no skins, single stylesheet (impossible to achieve plane-distinct rail without a scoping mechanism).
↳ refs: FE-18, INV-60, D-22

**D-46** · Brand accent deep petrol-slate `#1E4651` (VDD-6)
Primary action, focus ring, brand mark, your-court edge-bar. 9.30:1 on `--paper`, 10.24:1 on `--surface` — well above AA text threshold. The evidentiary governance context calls for a serious, trustworthy hue rather than a consumer-product accent.
**Rejected:** lighter accent (WCAG failure on light surfaces); saturated blue/teal (reads as software-generic rather than governance-specific).
↳ refs: FE-14, INV-62

**D-47** · Contrast gate test as build-blocking CI check (WCAG enforcement hook, SV-7)

`packages/tokens/src/__tests__/contrast.test.ts` computes the WCAG 2.1 relative-luminance formula directly against token values and fails the build on any text pairing under 4.5:1 or graphical pairing under 3:1. This is the executable form of INV-62. Rationale: invariant 9 (now INV-62) must be verified, not merely asserted — a future token edit that silently breaks contrast is a regression the human eye would not catch without a CI gate.
**Rejected:** relying on jest-axe colour-contrast (jsdom has no real layout, so `getComputedStyle` on elements with no real paint reports "incomplete" rather than pass/fail — an unreliable signal).
↳ refs: INV-62, FE-14, V-7

**D-48** · Tier-magnitude channel (`--tier-*`) is a fifth semantic channel, orthogonal to verdict-tone (amends FE-16)
`eu_ai_act_tier` has four magnitude tiers (PROHIBITED → MINIMAL) and two resolution states (UNCLASSIFIED, REQUIRES_CONTEXT). The magnitude tiers need a dedicated `--tier-*` channel (navy-slate family, four fill/text pairs) because their semantics are ordinal risk magnitude, not verdict classification. The resolution states (inherently verdict-class: "not yet known") re-use `--verdict-neutral` and `--verdict-attention` — the `--verdict-*` channel already covers "unknown / needs action" semantics. `VerdictChip` drops the tier branch (WI-3): mixing magnitude display into the verdict chip would violate channel orthogonality and confuse the two distinct meaning spaces.
**Rejected:** routing all six tier values through `VerdictChip` on `--verdict-*` (blurs magnitude-vs-verdict distinction; no four-step magnitude ladder available in six verdict tones); reusing `--sev-*` (severity is a future-facing channel with no current referent per SV-1 — borrowing it prematurely would collide when `--sev-*` ships).
**toTierMember() wire-format bridge:** The DB enum (`high_risk`, `limited_risk`, etc.) is snake_case, while the display type `TierMember` uses magnitude words (`HIGH`, `LIMITED`). The `toTierMember()` utility in `tier-badge.tsx` owns this mapping; callers must use it rather than `.toUpperCase()`.
↳ origin: UI-V1-TENANT-SKIN · refs: FE-16, INV-64, INV-56

**OPEN-V1** · Dark skin timing
Token layer reserves dark slots now. Dark skin ships as a later `skin-dark.css` override, not a rework. No timeline set; deferred until user research on operator console use in low-light environments.
↳ refs: D-44, FE-14

**OPEN-V2** · Lucide icon set selected (ISC) — resolved at V0 implementation ✅ CLOSED
Lucide (ISC, outline-first, outline-only) selected over Phosphor (MIT) and Tabler-outline (MIT) for ecosystem traction and outline-default posture. `lucide-react` installed in `apps/tenant`, `apps/operator`, and `packages/ui` (added at V1 for TierBadge `Ban` icon). V-6 confirmed ISC is within the permissive gate. Icon assignments per surface finalised at V1: `Ban` for PROHIBITED tier, `QueueRow` for review-queue entries.
↳ refs: V-6, D-43

**OPEN-V3** · Adoption density mode is purely composition-driven — no named sub-tokens needed ✅ CLOSED
Resolved at V1 against adoption surfaces (`systems/new`, `dashboard`, `review-queue`). `QueueRow density="compact"` / `density="comfortable"` props deliver both modes via class composition; no `--density-*` CSS variable is declared in `skin-tenant.css`. Guard added to `skins.test.ts` (V1DD-3).
↳ refs: FE-18, D-45

**OPEN-V4** · Per-surface visual specifics for F1–F8
Just-in-time at V1/V2. `UX §5` will be populated per surface as visual design is validated.
↳ refs: FE-14, UX §5

**OPEN-V5** · `--brand` vs `--verdict-positive` isoluminance — resolved at V1 ✅ CLOSED
VV-7 confirms 1.30:1 ratio between `--brand` (#1E4651) and `--verdict-positive` (#2F5D4A). Form differentiation is the mitigation: `WhoseCourtIndicator` uses a left edge-bar while `VerdictChip` is a rounded badge — two distinct visual affordances, not just colour. No token split or nudge at this time. Reopens only if user testing on the portfolio hub or review queue shows confusion.
↳ refs: FE-15, FE-16, FE-18

**DF-V1-1** · `downgraded_unsubstantiated` distinct marker = inline "downgraded" tag (resolves OPEN-V6)
Coverage matrix verdict `downgraded_unsubstantiated` renders as `<VerdictChip value="PARTIAL">` (attention tone) plus `<span data-verdict="downgraded">downgraded</span>`. Rationale: shares the PARTIAL attention signal (accurate — the control IS partially covered) while providing a distinct text tag for the downgrade reason. Rejected: hatched/diagonal fill (CSS-only, inaccessible without extra ARIA; brittle across printers); separate "DOWNGRADED" chip member (would require new VerdictChip key for a coverage-specific concept).
↳ origin: UI-V1-TENANT-SKIN · refs: INV-51, FE-16

**DF-V1-2** · `--sev-*` channel deferred (OPEN-V7 opened)
The severity channel (`--sev-*`) was reserved at V0 but has no current referent (no severity field in any schema at HEAD). Deferred until a severity concept materialises in the data model. Do not borrow `--sev-*` for tier or any other purpose while its semantics are unresolved.
↳ origin: UI-V1-TENANT-SKIN · refs: D-48, SV-1

**OPEN-V6** · `downgraded_unsubstantiated` distinct marker — resolved at V1 ✅ CLOSED
See DF-V1-1.
↳ refs: INV-51, FE-16

**OPEN-V7** · `--sev-*` severity channel — no current data-model referent; deferred
Reserved in the token layer at V0. No severity field exists in any schema at HEAD. Deferred until a severity concept materialises. Open until a schema change introduces a severity dimension.
↳ refs: D-48, SV-1

**D-49** · Tailwind v4 `@source` directive is the canonical way to make app builds scan `packages/ui`
Tailwind v4 auto-detection does not follow symlinks into sibling monorepo packages. Rather than duplicating component source into each app or adding a post-build copy step, each app's `globals.css` carries `@source "../../../packages/ui/src"` before `@import "tailwindcss"`. This is the minimal, stable solution: it is explicit, version-control visible, and fails loudly (missing utility classes) rather than silently if removed.  
Rejected: `content` array in a Tailwind config file (Tailwind v4 uses CSS-first config; a JS config file for this alone would be a regression); duplicating component source (violates single-home; maintenance burden).
↳ origin: post-UI-V1 correction (2026-06-25) · refs: INV-67, FE-14

**D-50** · Global 401 redirect lives in `createQueryClient`'s `QueryCache.onError`
When a BFF proxy call returns 401 (session cookie present but server-side store empty — e.g. after a dev-server restart), React Query marks the query failed and the UI showed a generic error message. The correct behaviour is an immediate redirect to `/api/auth/login`. The handler belongs in `createQueryClient` (`packages/api-client`) because: (a) it is shared across both apps, (b) it fires for every query globally without requiring per-surface wiring, and (c) `QueryCache.onError` is the idiomatic TanStack Query v5 location for cross-cutting error handling. The `retry` function is also set to return `false` for 401 to skip the pointless retry round-trip. The underlying session store (in-memory, dev-only) is a known limitation; this handler is the correct client-side recovery regardless of the store implementation.  
Rejected: per-query `onError` (requires wiring at every call site); middleware-only check (middleware sees only the cookie, not store validity; cannot redirect on 401 without a server round-trip).
↳ origin: post-UI-V1 correction (2026-06-25) · refs: INV-50, UI-F0-FOUNDATION session store note

**D-51** · No-undesigned-UI guardrail: agent does not originate visual or composition design
Observed at the 2026-06-25 reactive pass: the coding agent improvised visual and UX changes (AppNav top-bar, 26-page layout pass, DrillDownStep UX) without a design spec, then logged those improvisations into canon as shipped work. Aesthetic debate with an agent has no design authority to draw on, so the agent iterates and records — proliferating provisional design decisions that are difficult to retract without canon pollution. The rule routes design back to the design plane (design doc → execution-only handoff) and keeps the agent in its implementor lane. The exemption boundary (defect vs design) is drawn explicitly: a defect is a behaviour the surface was specified to have and does not exhibit; design is any unspecified visual or UX choice. The exemption preserves the agent's ability to fix real build issues (broken redirects, hydration errors, absent-token class references) without asking for permission.
Rejected: (a) letting the agent iterate UI reactively against user complaints — the origin of the erosion described above; (b) a purely advisory CLAUDE.md note with no `CONVENTION` invariant — no review hook would catch recurrence.
↳ origin: UI-C0-PRODUCTION-FOUNDATION · refs: INV-68

**D-53** · Members UI scope = full: list + invite + SoD-visible assign/revoke
The Members surface ships with the complete management set: member list (name / email / admin role / accept-status / roles-held), invite, and per-member governance-role assign/revoke with the SoD conflict matrix surfaced before the act. Half-scope (CRUD-only, role assignment deferred) would leave the multi-person review-to-authorise loop undemonstrable, which is the sprint's thesis objective.  
Rejected: list + invite only (deferred role assignment), which would require a second sprint and leave the SoD constraint invisible in the UI, making the governance model appear opaque to admins.
↳ origin: UI-F9-MEMBERS · refs: D-4, INV-7, INV-71, FE-24

**DF-F9-1** · OPEN-4 deferred — no self-assignment or SoD relaxation this sprint (sprint-local)
OPEN-4 (genesis governance-role bootstrap gap: an admin cannot obtain a governance role through the UI because self-assignment is blocked by D-5) remains open. The dev workaround (direct `governance_role_assignment` insert) is the only path for an owner to self-assign during development. The consequence is accepted and documented: a no-governance-role admin invites and staffs others but cannot obtain a governance role themselves through the UI. No self-assign relaxation, provision seed, or runtime grace is added.  
Rejected: resolving OPEN-4 now via provision seed or runtime grace — insufficient justification at this sprint; compliance with D-5/INV-7 is the current stance until a compelling reason to relax is established.
↳ origin: UI-F9-MEMBERS (sprint-local DF) · refs: OPEN-4, D-5, INV-7

~~**DF-F9-2**~~ · **Struck** (was: additive `MeRead` admin flag). Pre-sprint review B1: `MeRead` already carries `role`. No backend delta required. Number retired; not renumbered.
↳ origin: UI-F9-MEMBERS review (B1)

**D-54** · Cognito tenant pool email delivery via SES rather than Cognito default
`COGNITO_DEFAULT` sends invite emails from AWS's shared `no-reply@verificationemail.com` address. That shared sender's reputation is degraded by unrelated AWS customers; Gmail applies DMARC alignment checks that the shared sender cannot satisfy for our domain, causing invite emails to be silently filtered for `@gmail.com` recipients. Switching to `DEVELOPER` mode routes outbound email through SES using the verified `irontrustconsulting.co.uk` domain identity: the FROM address is `info@irontrustconsulting.co.uk`, DKIM is signed under our domain, and SPF aligns — all three authentication signals satisfy Gmail's bulk-sender rules. The `irontrustconsulting.co.uk` domain and `info@irontrustconsulting.co.uk` address were already verified in SES (production sending, not sandbox) in `eu-west-2`. Change is a single `email_configuration` block in `infra/cognito_tenant.tf`; no code, schema, or auth-flow change.  
Rejected: leaving `COGNITO_DEFAULT` — worked for `@irontrustconsulting.co.uk` recipients (corporate mail server, lower spam threshold) but consistently failed for Gmail recipients, making the invite flow unreliable at MVP.  
↳ origin: operational fix 2026-06-25 · refs: infra/cognito_tenant.tf

**DF-F9-3** · Tenant-plane administrative-axis nav + page gating (sprint-local)
The Members nav entry renders and the page issues its gated calls iff `MeRead.role === "admin"` (lowercase string literal, P3-confirmed); non-admin callers see no entry and the page issues zero `GET /v1/members` calls (the not-authorised treatment pattern, distinct from a disabled entry). This convention is new ground: tenant-plane `admin`/`member` gating is not covered by FE-8 (act-SoD), FE-13 (operator permission-absence), or any prior tenant-plane convention. Absence (not disabled) matches the DF7-1/DF2-5/DF5-7 established zero-call-for-unauthorised-role pattern.  
Rejected: render-then-403 (shows a non-functional entry; masks the empty state behind an access error).
↳ origin: UI-F9-MEMBERS (sprint-local DF) · refs: FE-8, FE-13, INV-68, FE-24

**D-55** · Catalogue logo assets served from Next.js `public/` at relative paths
Logo files for `catalogue_vendor` and `catalogue_product` rows are placed at `apps/tenant/public/logos/<slug>.png` and served by the Next.js static asset handler. `logo_url` values in DB are relative paths (`/logos/<slug>.png`), making them deployment-neutral. `scripts/seed/seed_logos.py` fetches 128 × 128 PNG per vendor via Google's public favicon service (`www.google.com/s2/favicons?domain=…&sz=128`); falls back to an inline SVG monogram on fetch failure. Intentionally unresolvable dev-artifact vendors (`SmokeVendor-*`) are skipped and retain `logo_url = NULL`, driving the `LogoTile` React-level monogram.  
Rejected: (a) external CDN path at runtime — introduces dependency and deployment coordination burden; (b) absolute URL in DB — ties data to a specific origin; (c) Clearbit Logo API — now requires authentication; Google favicon service is public and returns indexed 128 × 128 PNGs for all major software vendors.
↳ origin: UI-C2-INTAKE-CATALOGUE · refs: FE-25, scripts/seed/seed_logos.py

**D-56** · `DrillDownStep` in-place single-open accordion (not filter chips, not discrete panel steps)
The provisional `DrillDownStep` (post-V1 UX rewrite) exposed vendors as optional filter chips on the product rung. The UI-C2 partial commit (`c6da0ec`) replaced that with a four-rung panel-replacement funnel; the full UI-C2 delivery replaces that in turn with an in-place single-open accordion: category rows expand inline to reveal sub-category rows; sub-category rows expand to reveal vendor rows (when >1 vendor) or product rows (single-vendor auto-skip, INV-72); product rows are leaves that emit `DrillDownResult`. No page transitions — all levels live in a single `PageScaffold`. Single-open state is managed by three `expandedXxxId` state variables: expanding one branch collapses the open sibling at the same level. `DrillDownResult` shape unchanged (DF-C2-5).
Rejected: (a) filter chips — misrepresents the vendor-product relationship; (b) discrete panel-replacement steps — transitions impose a "going somewhere" mental model for what is a narrowing drill-down within one view; panel steps also require bespoke back-navigation state that the accordion state naturally handles.
↳ origin: UI-C2-INTAKE-CATALOGUE · refs: INV-72, FE-25, FE-23, OPEN-C1, DF-C2-6, DF-C2-7, DF-C2-8

**OPEN-C1** · `DrillDownStep` funnel IA provisional shape — **resolved at UI-C2 full delivery ✅ CLOSED**
The post-V1 `DrillDownStep` (two-level hierarchy with vendor filter chips) was marked provisional pending a design-driven F1 per-surface composition pass. Resolved: rebuilt as in-place single-open accordion per D-56; `LogoTile` branding on vendor and product rows per FE-25; all four INV-70 states at every accordion level; vendor level present only when >1 vendor (DF-C2-7); mixed-node direct-product rows persist regardless of sub-category expansion (DF-C2-8); F1 composition pass complete. See `STATE.md §UI-C2`.
↳ refs: D-56, INV-72, FE-25, FE-23, DF-C2-6, DF-C2-7, DF-C2-8

**DF-C2-1** · `LogoTile` size choices — 40px default; 24px for vendor in confirm step (sprint-local)
The vendor/product row `LogoTile` uses the default 40px. The vendor logo rendered alongside the product name in the confirm step uses `size={24}` to avoid dominating the compact identity line (`<LogoTile … size={24} />`). No additional size variants required at this sprint.
↳ origin: UI-C2-INTAKE-CATALOGUE · refs: FE-25, D-56

**DF-C2-2** · Vendor auto-skip via `useEffect` + `vendorAutoSkipPrevented` ref (sprint-local)
The single-vendor auto-skip is implemented as a `useEffect` watching `[expandedSubcategoryId, expandedVendorId, vendors.data]`. A `useRef(false)` guard (`vendorAutoSkipPrevented`) is reset to `false` in `toggleSubcategory` and `toggleCategory` on each new sub-category or category selection, so the auto-skip fires normally each time. Back-navigation from the confirm stage sets `selectedProductId → null` without touching `expandedVendorId`; the re-trigger condition (`expandedVendorId === null`) is not met, so no additional guard is needed on back. This avoids a `useCallback`-heavy or state-machine approach for what is a simple navigation guard.
↳ origin: UI-C2-INTAKE-CATALOGUE · refs: INV-72, D-56

**DF-C2-3** · In-house exit at every rung (sprint-local)
The `"Not in catalogue / in-house"` secondary button is rendered at every funnel rung (top-category, sub-category, vendor, product). This ensures a system_owner is never stranded after drilling into the wrong branch — they can always exit to the custom/in-house path without pressing Back repeatedly.
↳ origin: UI-C2-INTAKE-CATALOGUE · refs: D-56

**DF-C2-4** · Inline mutation errors use `<div role="alert">` not `<ErrorState>` (sprint-local)
`<ErrorState>` (with a `Try again` button) fits full-page or full-section data load failures where the error replaces the failed content. Form mutation errors (submit failures on `IntakeCaptureStep`, `UseCaseCreateStep`, etc.) occur while the form stays visible and the user must correct and retry manually — a retry button would re-submit without correction and is misleading. Inline `<div role="alert" className="text-sm text-danger">` is the correct pattern for in-form mutation errors.
↳ origin: UI-C2-INTAKE-CATALOGUE · refs: FE-22, INV-70

**DF-C2-5** · `DrillDownResult` shape unchanged — vendor selection is navigation-only (sprint-local)
The `DrillDownResult` type (`{isCustom, catalogueProductId, catalogueProductName}`) is not extended to include `vendorId`. The vendor rung serves only to narrow the product list and is not propagated to the reducer or to `POST /v1/systems`. The server derives the vendor from the selected `catalogue_product_id` (existing `catalogue_vendor_id` derivation unchanged).
↳ origin: UI-C2-INTAKE-CATALOGUE · refs: D-56

**DF-C2-6** · Category-level rows carry no `LogoTile` (sprint-local)
Top-category and sub-category rows in the accordion render without a `LogoTile` leading slot. Categories are organisational containers, not branded products; no logo data exists for them in the schema. Only vendor and product rows carry `LogoTile` — vendor rows in the multi-vendor level (logo_url from `VendorRead`); product leaf rows at all product levels (logo_url from `ProductRead`). This is the only accordion level where `ListSelectRow` appears without a `leading` prop.
↳ origin: UI-C2-INTAKE-CATALOGUE · refs: FE-25, FE-23, D-56

**DF-C2-7** · Vendor level is navigation-only and appears only when >1 vendor (sprint-local)
The vendor expansion level in `DrillDownStep` is rendered only when the expanded sub-category returns more than one vendor (`vendors.data.length > 1`). When exactly one vendor exists, the vendor rung is auto-skipped (INV-72) and the product list is shown directly below the sub-category row. When zero vendors exist, an `EmptyState` with in-house exit is shown (DF-C2-3). Vendor rows are disclosure triggers (`onToggle` branch mode, FE-23) that expand the product list below them; they have no `onClick` action and emit no `DrillDownResult` (DF-C2-5).
↳ origin: UI-C2-INTAKE-CATALOGUE · refs: INV-72, D-56, DF-C2-5, FE-23

**DF-C2-8** · Mixed-node rule: branch-sibling collapse only; leaf rows persist (sprint-local)
A category may have both sub-category branches AND direct product memberships at the same node (`ProductCategoryMembership` at non-leaf nodes, confirmed by schema P-2). When `expandedCategoryId` is set and both sub-category and direct-product lists are non-empty, single-open collapse applies only among the branch sub-category rows (expanding one sub-category collapses its sibling if open); the direct product leaf rows are always visible in the parent panel regardless of which sub-category is expanded or collapsed. This prevents the direct products from being hidden behind a branch collapse state that the user cannot reason about.
↳ origin: UI-C2-INTAKE-CATALOGUE · refs: D-56, FE-23, INV-72

**D-57** · Petrol deployment extended to section markers and group labels only [amends D-46]
`--color-brand` (petrol) was confined to four uses: primary action button, focus ring, your-court edge-bar, and brand logo link (D-46). This extends the ceiling to include section-marker accent bars and group-label text in `SectionGroup` (FE-27). Still one hue; still contrast-gated; still no decorative chroma. Input-selection affordances remain governed by INV-73 (shipped; out of scope for this amendment). The A4 ceiling now = four D-46 uses + section markers + group labels.
Rejected: extending petrol to selected/active input states (collides with INV-73's shipped selection treatment).
↳ origin: UI-V2-DEPTH-LAYOUT · refs: D-46, INV-73, FE-27, DF-V2-3

**D-58** · Depth-within-restraint: depth from neutral layering, subtle elevation, structure, disciplined accent — never decorative chroma
The visual improvement mandate is met by: a neutral surface ramp (page → card → sunken), soft low-spread shadows (`--elevation-raised`/`--elevation-overlay`), `SectionGroup` structure, and one hue (petrol, within D-57 ceiling). Warmer palettes, additional accent hues, and ornamental motion are explicitly rejected. D-42 stands.
Rejected: (a) warmer palette (D-42 signal-preservation; no warm signal channel exists for warmth to borrow from); (b) flat status quo (the complaint that drove the sprint); (c) decorative chroma (D-42 chromatic restraint).
↳ origin: UI-V2-DEPTH-LAYOUT · refs: D-42, D-46, D-57, FE-26, FE-27

**D-59** · Constrained-vocab-over-free-text; opinionated by default [principle; build deferred]
Absent values → extend the controlled vocabulary from taxonomies, not a free-text escape hatch. This is the anchor decision for the deferred vocab-enrichment sprint; no build detail accretes in this sprint.
Rejected: free-text "Other" (less analyzable, harder to report across tenants).
↳ origin: UI-V2-DEPTH-LAYOUT (principle only; build deferred)

**D-60** · Status enums render authored humanized labels via VerdictChip label map
Each of the five verdict-family enums maps to a hand-authored label (Appendix D of design doc; 25 unique keys). The map (`packages/ui/src/status/verdict-label-map.ts`) lives with `VerdictChip`, mirroring `toTierMember()`'s home. Keys are the wire `.value` (lowercase snake_case) exactly as the server emits them; never `.toUpperCase()` (D-48). Shared values (`approved`, `needs_refresh`) resolve to one label each (no conflict). British spelling, domain phrasing, acronyms preserved.
Rejected: (a) client-side title-casing the key (mishandles acronyms, British spelling, domain phrasing); (b) backend-supplied label (display concern — no schema reason to pollute the wire contract).
↳ origin: UI-V2-DEPTH-LAYOUT · refs: D-48, FE-16 ALTER, INV-75, DF-V2-4

**D-61** · Dashboard zero-systems renders scaffolded-empty (supersedes UI-C1 zero-systems choice)
The dashboard's `systemCount === 0 && portfolio.data.length === 0` branch previously rendered a `FirstRunPanel` full-surface takeover (UI-C1 shipped choice, defensible at the time). This sprint supersedes that choice with scaffolded-empty: retained `PageHeader` (with `system_owner`-gated register button) + three `StatCard`s reading 0 + framed `DataTable` with in-region `emptyMessage`. The get-started content is within the retained data region, not replacing it. This is a **deliberate supersession of a shipped, CLEARED choice**, not remediation of a gap. `FirstRunPanel` (FE-22) is globally retained; the dashboard simply no longer uses it in this branch.
Rejected: retaining the `FirstRunPanel` takeover (reads as a bare card hiding workspace structure; founder preference on first real use).
↳ origin: UI-V2-DEPTH-LAYOUT · refs: INV-74, FE-22, FE-27, D-58

**DF-V2-1** · Elevation shadows excluded from contrast.test.ts (sprint-local)
`--elevation-raised` and `--elevation-overlay` are decorative-neutral box-shadows; they are not WCAG 1.4.3 text pairings or 1.4.11 graphical-element pairings. They are not added to `contrast.test.ts`. The real INV-62 exposure from this sprint is surface-ramp widening: if any `--color-paper`/`--color-surface`/`--color-surface-sunken` value changes in a future sprint, the full 30-pairing set must be re-verified (not just the changed pair).
↳ origin: UI-V2-DEPTH-LAYOUT · refs: INV-62, FE-26

**DF-V2-2** · `PageScaffold` `width` default is `'default'` (unchanged `max-w-4xl`) (sprint-local)
All current `PageScaffold` consumers pass no `width` prop; at `'default'`, the rendered class is `max-w-4xl` — identical to the previous hardcoded value. No consumer migration required.
↳ origin: UI-V2-DEPTH-LAYOUT · refs: FE-21 ALTER

**DF-V2-3** · Only the dashboard is re-composed this sprint (sprint-local)
F2 detail and F3–F8 inherit the VerdictChip label map (kit-level) and will adopt depth/layout (`SectionGroup`, elevation, wide scaffold) in their own per-surface composition passes. Cross-surface regression for this sprint is label-render + layout-break only; full recomposition is deferred.
↳ origin: UI-V2-DEPTH-LAYOUT · refs: FE-26, FE-27, D-58

**DF-V2-4** · VerdictChip label map keys on wire `.value` exactly (sprint-local)
The `LABEL_MAP` in `verdict-label-map.ts` keys on the wire `.value` as the server emits it (lowercase snake_case). The chip never calls `.toUpperCase()` on the value before the label lookup. `vendor_check` is the correct wire value; the DB stores `VENDOR_CHECK` (uppercase), but the API serialiser emits lowercase. The TONE_MAP uses `.toUpperCase()` for its own lookup and is unchanged.
↳ origin: UI-V2-DEPTH-LAYOUT · refs: D-48, D-60, FE-16 ALTER, INV-75

**D-63** · Use-distinguishing context (`usage_context`, `human_oversight`, data categories, affected parties) belongs on `use_case`, not `system`
A system may have multiple use cases with different purposes, oversight models, and data profiles. Attaching these facts to `system` causes fidelity loss when a system is re-used across use cases with different profiles, and conflates deployment-stable facts (product, hosting model, operator role) with use-distinguishing context. From DM-S1, `usage_context_id`/`human_oversight_type_id` are FK columns on `use_case`; `data_category_ids`/`affected_party_ids` are persisted in `use_case_data_category`/`use_case_affected_party` (RLS-isolated, `tenant_id`-partitioned, INV-77). The system registration payload retains only deployment-stable facts.
Rejected: keeping both tables (duplicates the source of truth across two levels — unresolvable when they diverge); adding a many-to-many at system level as a default (same problem — which use case does the default apply to?).
↳ origin: DM-S1 · refs: INV-76, INV-77, DF-D1-1..4

**D-64** · Classifier (`resolve_classification`) is unchanged; context fields are not tiering inputs
The four context fields relocated in D-63 do not feed the EU AI Act tier resolution. `resolve_classification` reads only `system.catalogue_product_id` and the global taxonomy bridge. `usage_context` and `human_oversight_type` are captured for DPIA/FRIA feeder pre-fill and export context, not for tier derivation. DPIA applicability is driven by the data category profile (special-category → REQUIRED; any category → RECOMMENDED; none → NOT_APPLICABLE) — evaluated against `use_case_data_category`, not the classifier logic. The context gate tree is similarly unchanged.
Rejected: using context fields as additional tiering inputs — the EU AI Act's Annex III mapping is product/application-category-based; adding context signals without a legal mandate would obscure the classification rationale.
↳ origin: DM-S1 · refs: INV-76, D-63

**DF-D1-1** · Backfill is system-to-first-use-case (sprint-local)
The DM-S1 migration backfills each system's context values to the system's first use case by `created_at` ordering. Systems with zero use cases lose the data (acceptable: those systems have no AIIA, so the context was never used). Systems with multiple use cases pick up identical context on every use case — a known imprecision accepted as a one-time migration artefact; operators are expected to correct per-use-case values after DM-S1 ships.
↳ origin: DM-S1 (sprint-local DF) · refs: D-63

**DF-D1-2** · Transitional capture — four fields captured in intake-capture-step, threaded to use-case-create-step (sprint-local)
In the DM-S1 wizard flow, the four context fields are still presented on the intake-capture-step form (alongside system-level fields); on form submit, they are collected into an `IntakeCaptureContext` object and carried in wizard state to the use-case-create-step, where they are included in the `UseCaseCreate` POST body. This is a transitional arrangement; DM-S2 moves the capture form controls to the use-case step. The contract change (`SystemCreate` drops the four; `UseCaseCreate` gains them) is permanent from DM-S1.
↳ origin: DM-S1 (sprint-local DF) · refs: D-63, INV-76

**DF-D1-3** · Export shape: four context fields added to `UseCaseExportSectionsRead` (sprint-local)
`SystemDetail` no longer carries the four context fields, so the export pack's per-use-case section (`UseCaseExportSectionsRead`) is extended with `usage_context`, `human_oversight_type`, `data_categories`, `affected_parties`. `_load_use_case_context` in `export_service.py` resolves them at pack-build time. This shifts the `content_hash` for all existing exports — correct and expected.
↳ origin: DM-S1 (sprint-local DF) · refs: D-63

**DF-D1-4** · DPIA/FRIA feeder pre-fill and DPIA applicability now read from `use_case_*` tables (sprint-local)
The FRIA feeder snapshot reads `use_case_affected_party where use_case_id == use_case.id`; source_ref is `use_case_affected_party:{link.id}`. The DPIA feeder snapshot reads `use_case_data_category where use_case_id == use_case.id`; source_ref is `use_case_data_category:{link.id}`. The DPIA applicability check (`feeder_recommendations_for`) also queries `use_case_data_category`. All three were previously reading from `system_*` tables. The AIIA overview pre-fill for `usage_context` and `human_oversight_type` now reads `use_case.usage_context_id` / `use_case.human_oversight_type_id` (previously `system.*`).
↳ origin: DM-S1 (sprint-local DF) · refs: D-63, D-64

**D-62** · Proxy 401 clears the session cookie; proactive refresh failure is non-destructive
Two related BFF session behaviours fixed as a unit (origin: post-UI-V2-DEPTH-LAYOUT ops debug).
(1) When `getSession()` returns null — cookie present but UUID not in the in-memory store (common after a dev-server restart, where the store is wiped but the browser retains the old cookie) — the proxy's 401 response now deletes the session cookie (`Set-Cookie: irontrustai_tenant_session=; Max-Age=0`). The browser removes the stale cookie; the `createQueryClient` 401 handler navigates to login; the callback sets a fresh cookie; the next proxy call succeeds. Without this, the old cookie blocked recovery until the user cleared cookies manually, causing an infinite login-redirect loop.
(2) The proactive refresh path added in UI-V2-DEPTH-LAYOUT previously called `sessionStore.destroy()` in its catch block, then returned null. A Cognito network hiccup therefore evicted a perfectly valid session and re-entered the same redirect loop (D-50 handler → login). Fixed by: on refresh failure, return the existing session unchanged. The API rejects a genuinely expired token with 401, and D-50's handler converts that to a single clean re-login — no loop.
Rejected for (1): clearing the cookie in middleware (middleware only checks cookie presence and cannot distinguish a stale UUID from a valid one without calling `getSession()`, which would couple the middleware to the store and defeat the cheap-check intent). Rejected for (2): retaining destroy-on-failure (the problem it solved — forwarding a stale token — is already handled by the API returning 401 → D-50).
↳ origin: ops debug post-UI-V2-DEPTH-LAYOUT · refs: D-50, INV-F0-5 (session cookie httpOnly)

**D-52** · Identity split — tenant name in sidebar foot, user in top utility bar
The tenant name goes in the sidebar foot (wired from `MeRead.tenant_name`); the logged-in user (display name or email + sign-out) moves to a slim top utility bar at the head of the main content column (`apps/tenant/app/_components/top-utility-bar.tsx`). Nav stays in the sidebar — this is not a return to top-bar navigation; the C0 sidebar topology is unchanged. The canonical home of the tenant name is the `tenant.name` column; `MeRead` (tenant plane) and `GET /platform/tenants` (operator plane) are two plane-scoped projections of it, so the tenant-plane field is single-homed on `MeRead` with no second tenant-plane route needed or added.
Rejected: (a) a dedicated tenant-plane `GET /v1/tenant` route (a second home for the same fact; `D-22`; no such route exists and none is added); (b) keeping user identity in the sidebar foot and adding tenant name beside it (two identities crowding one block). The reversal of `FE-20`'s "no top-bar" stance is scoped here: `FE-20` removed a top-bar *navigation*; this adds a top *utility* bar for identity only — nav remains in the sidebar.
↳ origin: UI-C1-PORTFOLIO-IDENTITY · refs: FE-20 ALTER, INV-68, D-22

**D-65** · Registration is one atomic act — system, use case, and classification snapshot in a single transaction
A `System` cannot exist without a first `UseCase` and a `Classification` snapshot (REG-2). `POST /v1/registrations` creates all three in one transaction via `db.flush()` calls inside the handler; `get_tenant_db` commits at request end. If any step fails, the entire transaction rolls back — no orphan rows. `POST /v1/systems` is removed (INV-78).
Rejected: keeping `POST /v1/systems` and enforcing linkage via application logic (fragile; the seam can be exploited by any client that calls the old endpoint, or by a test fixture, or by a transient failure between the two calls). Rejected: a deferred job to link system → use case (eventual consistency for a workflow that is always synchronous in the UI is unnecessary complexity).
↳ origin: DM-S2 · refs: INV-78, INV-27

**DF-D2-1** · System-stable facts captured at intake step, no network call (sprint-local)
In the DM-S2 wizard, the intake-capture step collects only system-stable facts (`name`, `operatorRoleId`, `hostingModelId`, `lifecycleStage`, `purpose`) and dispatches `INTAKE_DONE` directly without a network call. These facts are held in wizard state until `POST /v1/registrations` fires at the use-case step.
↳ origin: DM-S2 (sprint-local DF) · refs: D-65, DF-D1-2

**DF-D2-2** · By-product prefill re-keyed before system exists (sprint-local)
The prefill step now calls `GET /v1/catalogue/products/{product_id}/prefill` (not the by-system route) because no system ID exists yet at this wizard step. `usePrefill` is re-keyed to `catalogueProductId`; `enabled: Boolean(catalogueProductId)` — disabled for custom/null product. The by-system prefill route (`GET /v1/systems/{id}/prefill`) is retained and delegates to the same shared resolver (`get_prefill_by_product`).
↳ origin: DM-S2 (sprint-local DF) · refs: D-65

**DF-D2-3** · Four use-distinguishing context controls relocated to use-case step (sprint-local)
`usage_context_id`, `human_oversight_type_id`, `data_category_ids`, `affected_party_ids` are now captured at the use-case-create step (not the intake-capture step). The four vocab hooks and their form controls move from `IntakeCaptureStep` to `UseCaseCreateStep`. The transition arrangement from DF-D1-2 is resolved and closed. `IntakeCaptureFacts` type carries no context fields; `UseCaseCreateStep` holds local state for all four and includes them in the `RegistrationCreate` body.
↳ origin: DM-S2 (sprint-local DF) · refs: DF-D1-2 (closed), D-65
