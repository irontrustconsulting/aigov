# INVARIANTS.md — IronTrust AI Governance Platform

**Location:** `docs/INVARIANTS.md` — single source, mirrored to project knowledge. Updated once.
**Purpose:** The reviewer's checklist and the hard design constraints. Cited by `INV-n` across all canonicals; never restated elsewhere — other files reference these by ID.

**Enforcement legend** (a reviewer agent concentrates attention on `CONVENTION`):
- `DB` — schema / trigger / constraint. Structurally unviolable.
- `CODE` — one routed locus (a predicate, function, or single-statement shape) all paths go through. Violable only by adding a path that bypasses it.
- `CONVENTION` — discipline only. Nothing structural prevents a violation; review must catch it.

**Format:** `INV-n · ENFORCEMENT · locus` / statement / `↳ origin · refs`.
**Note:** DB *uniqueness* objects (partial indexes `uq_one_aiia_per_use_case`, `uq_current_classification`, `uq_one_primary_eu_mapping`; plain constraint `uq_feeder_type_per_aiia`) are catalogued in `DATA-MODEL.md`. Behavioural invariants here reference them by name rather than restating them.

---

**INV-1** · CODE · `verify_cognito_token` / `verify_operator_token`
Tenant and operator tokens must never satisfy each other's verifiers; never share an auth dependency across planes. Structural backstop: the two Cognito pools have different `iss`/`aud`.
↳ origin: foundations

**INV-2** · CONVENTION · membership join (never bare `app_user`)
Any user listing in a tenant context joins from `membership`; `app_user` is never queried bare. It is global and non-RLS — the join is the only thing scoping the read to the caller's tenant.
↳ origin: foundations · refs: INV-34

**INV-3** · CONVENTION · handler dependency (`ctx.tenant_id`)
On every tenant-mutating endpoint, `tenant_id` is `ctx.tenant_id`, never a request-body field.
↳ origin: foundations

**INV-4** · DB · `irontrustai_app` grant (NOBYPASSRLS)
Tenant-scoped work runs on `irontrustai_app` (NOBYPASSRLS). No BYPASSRLS role for tenant work; isolation is RLS, not table grants.
↳ origin: foundations

**INV-5** · DB · `AuditEvent` immutability trigger + grant
`AuditEvent` is append-only. No UPDATE/DELETE at the application layer; the Postgres trigger is the backstop.
↳ origin: foundations

**INV-6** · CONVENTION · evidence model (pointer-only)
Evidence bytes live in S3; Postgres holds only the pointer (`s3_bucket`, `s3_key`, `s3_version_id`) + `sha256`. Never store file bytes in the DB.
↳ origin: S3–4

**INV-7** · CODE · `assert_governance_assignable` / `assert_distinct_workflow_actor` (governance.py)
SoD goes through exactly two sanctioned loci, never a third inline check. Assignment-time (may this membership hold this role, given what it already holds) → `assert_governance_assignable`. Act-time (did one user perform two distinct workflow roles on one object) → `assert_distinct_workflow_actor`, keyed on `user_id`, not `membership_id`. No inline conflict logic in handlers or services.
↳ origin: S6a (revised) · refs: INV-28

**INV-8** · CONVENTION · operator → role → permission only
Operator permissions reach operators only through roles; no direct operator→permission grants. If a one-off is needed, make a role.
↳ origin: foundations

**INV-9** · CONVENTION · no unique constraint on `app_user.email`
Cognito is the email-uniqueness authority; `app_user.email` is deliberately not DB-unique. Do not add a unique constraint without understanding what Cognito's enforcement implies.
↳ origin: foundations

**INV-10** · CODE · classification resolvers (bridge / context-gate)
Tier is never asserted from catalogue facts alone — it comes from deployment context (bridge or context-question gate). The catalogue informs; it never decides.
↳ origin: classification · refs: D-8

**INV-11** · CODE · `resolve_*` (read) vs `snapshot_`/`compute_`/`sign_off_` (write)
Classification resolution and persistence stay separate on both gates. `resolve_classification`/`resolve_context_classification` never write; `snapshot_classification`/`compute_and_record_classification`/`sign_off_classification` own the transaction. AIIA/feeder creation reads only the current persisted snapshot and never re-enters a resolver.
↳ origin: classification

**INV-12** · CODE · `resolve_context_classification` (fail-closed ladder)
Context-gate resolution is fail-closed: unanswered questions → `UNRESOLVED`, no snapshot. `MINIMAL` is reached only affirmatively (all answered, nothing higher asserted), never as a default or fallback. `PROHIBITED` short-circuits.
↳ origin: classification

**INV-13** · CODE · provenance server-derived + disposition-before-authoring
AIIA/feeder provenance is always server-derived; no request schema accepts a `provenance` field. A still-`AI_SUGGESTED` item blocks authoring-field writes until confirmed or amended.
↳ origin: S3–4

**INV-14** · CODE · single conditional UPDATE (from-state in WHERE)
Provenance transitions are single conditional UPDATEs — never read-then-write; the from-state guard lives in the WHERE clause so a stale read can't corrupt the audit diff. `412` (lock mismatch) and `409` (bad from-state) are deliberately distinguishable.
↳ origin: S3–4

**INV-15** · CODE · feeder scope copy-at-creation
A feeder's scope (`tier_snapshot`/`classification_version`) is copied from its parent AIIA at creation and never re-resolved. Parent and feeder must always agree.
↳ origin: S3–4

**INV-16** · CODE · `assemble_aiia_items` (read-time only)
Feeder propagation into the AIIA is read-time reference only — never copy a feeder item into the AIIA, never write back. `assemble_aiia_items` is the single assembly locus.
↳ origin: S3–4 · refs: D-18

**INV-17** · CODE · `_is_pristine` (assessment_service.py)
Pristine-delete only, AIIA + feeders: a hard DELETE is permitted only with no confirmed/amended items, no control links, no evidence links, and (for an AIIA) no feeders. A worked assessment must be voided instead — not yet built (see STATE deferred).
↳ origin: S3–4 · refs: INV-36

**INV-18** · CODE · upload route (no `get_tenant_db` dependency)
No DB transaction or connection is held across a slow external call that doesn't need one. Evidence upload's S3 put runs with nothing open; the route depends on `get_tenant_context`, not `get_tenant_db`. Contrast Cognito provisioning, which deliberately holds a transaction to compensate on failure — know which shape a new external-call path needs before writing it.
↳ origin: S3–4

**INV-19** · CODE · single guarded DELETE (`NOT EXISTS` inline)
Evidence pristine-delete is a single guarded statement, never check-then-delete. The `assessment_item_evidence` `ON DELETE CASCADE` makes a separate `SELECT count` then `DELETE` racy; the `NOT EXISTS` guard must live in the same statement as the `DELETE`.
↳ origin: S3–4

**INV-20** · CODE · evidence-link vs control-link gating (deliberate asymmetry)
Evidence-linking is disposition-gated (a still-`AI_SUGGESTED` item rejects an evidence link); control-linking is not. Documented asymmetry — do not "fix" one to match the other without re-reading why.
↳ origin: S3–4 · refs: D-20

**INV-21** · CONVENTION · no direct evidence↔control table
Evidence → control is transitive via items only; never add a direct evidence↔control table. Framework satisfaction derives from the control-library cross-map through whichever item the evidence is linked to.
↳ origin: S3–4 · refs: D-19

**INV-22** · CODE · presigned download hardening
Presigned evidence downloads are always hardened: forced `Content-Disposition: attachment`, content-type neutralised off a safe allow-list, signed against the public (not internal) S3 endpoint. Never serve evidence inline.
↳ origin: S3–4

**INV-23** · CONVENTION · typed-column bind (never raw `.value`)
Every by-name enum is stored by Postgres **member name**, not `.value` — a raw `.value` bind silently matches zero rows wherever an enum's `.value` differs in case from its member name. Bind through the typed column; never hand-write a `.value` comparison. All enum labels are uniformly UPPERCASE member names in live DDL (verified `pg_enum`) after fix `3a5b36bdd37a`, which renamed the labels that had shipped lowercase (`classification_status`; `eu_ai_act_tier.REQUIRES_CONTEXT`; `system_lifecycle_stage`). The hazard is structural, not historical: the no-RLS test DB generates enums fresh from the ORM and can never catch a label-case mismatch — only checking real `pg_enum` can. Verify before encoding any raw label comparison.
↳ origin: S5 · fix `3a5b36bdd37a`

**INV-24** · CONVENTION · `apply_transition` sole writer
`apply_transition` is the sole writer of `use_case.state`. No other path may construct `UPDATE … SET state`, directly or via the ORM instance attribute. Nothing structural enforces this — review must catch violations.
↳ origin: S5 · refs: INV-25

**INV-25** · CONVENTION · recompute `full_vector` at every consequential read/write
The full gate vector is source of truth; persisted `use_case.state` is a cursor. No gating decision (advance, regress, an authorisation attempt) reads persisted `state` alone — recompute via `full_vector`/`re_evaluate`. A status `GET` shows the computed verdict and never persists it.
↳ origin: S5

**INV-26** · CODE · `advance_use_case` step-0 (snapshot tier)
Prohibited is terminal, supreme, and read off the current classification snapshot's `tier`, never `eu_tier`. Fires from any non-terminal state including `held` — `eu_tier` is never stamped `PROHIBITED` on the context path, so reading it would silently let a prohibited practice sit un-halted.
↳ origin: S5 · refs: INV-33

**INV-27** · CONVENTION · re-`set_config` after mid-request commit
A mid-request `db.commit()` resets `SET LOCAL`-scoped settings, including `app.current_tenant`. Any code that commits mid-request on an RLS-bound session must immediately re-`set_config` (`_set_tenant_context`), or every later RLS-scoped query on that session silently returns zero rows. Caught only by live-smoke-testing against real RLS-enabled Postgres.
↳ origin: S5

**INV-28** · CODE · `assert_distinct_workflow_actor` (act-level SoD)
Act-level SoD is distinct from assignment SoD and lives only in `assert_distinct_workflow_actor`: `reviewer ≠ submitted_by` (6a); `authoriser ∉ {approved_by, submitted_by}` (6b).
↳ origin: S6a · refs: INV-7

**INV-29** · CODE · `residual_risk_statement` authored on ATO
Residual-risk acceptance is the authoriser's act — `residual_risk_statement` is authored on the ATO at `authorise_use_case` time, never derived from or assignable to the reviewer's AIIA approval.
↳ origin: S6b · refs: D-10

**INV-30** · CODE · human-act gate terms (no auto-derive)
Reviewer/authoriser gates are human-act gates, never auto-advanced. `assessment_approved()` is satisfied only by `record_review(APPROVED)`; `authorisation_gate`'s human-act term only by `authorise_use_case`. `advance_use_case`/`re_evaluate` never derive either.
↳ origin: S6a/6b

**INV-31** · CODE · `_assert_authoring_unlocked`
AIIA authoring is status-locked: item and feeder-item writes are rejected (`409`) while the parent AIIA is `IN_REVIEW` or `APPROVED`; a feeder item's lock resolves through `parent_aiia_id`, since the feeder's own `status` never moves.
↳ origin: S6a

**INV-32** · CONVENTION · read `live_state`, never row-existence
The ATO is a point-in-time fact; deployment authority is the live vector. A `DeploymentAuthorisation` row is never mutated; re-authorisation always writes a new row. Consumers read the computed `live_state` (`GET …/authorisation`), never infer "currently authorised" from a row's mere existence.
↳ origin: S6b

**INV-33** · CODE · state-agnostic halt legality + step-0
`authorised` is not a safe harbour from prohibition: `apply_transition`'s `halt` legality is state-agnostic (`from_state not in _TERMINAL_STATES`) and `advance_use_case`'s step-0 PROHIBITED check runs regardless of starting state — reclassification to `PROHIBITED` forces `halted_prohibited` directly from `authorised`, with no special-casing required.
↳ origin: S6b · refs: INV-26

**INV-34** · CONVENTION · actor-identity via membership
Actor-identity reads join via `membership`, never bare `app_user` (INV-2 applied to the review queue, review history, and the ATO's authoriser identity).
↳ origin: S6b · refs: INV-2

**INV-35** · CODE · `_GATE_FNS`/`_ADVANCE_TABLE` ceiling
`authorised` is entered only by `authorise_use_case`. `advance_use_case`'s gate-driving structures have no entry past `pending_authorisation`, so a cycle-matching ATO is never sufficient on its own to cross into `authorised`. `re_evaluate` may hold an already-`authorised` use case in place (no-op, full vector still all-advances) or regress it to `held`, but its restore branch can only target a vector-guarded state — never `authorised` — so a regressed-then-restored use case always lands at `pending_authorisation` and waits for re-confirmation.
↳ origin: S6b

**INV-36** · CODE · `_is_pristine` (status + history)
Pristine-delete is status-and-history-aware: a hard DELETE is blocked unless `status == DRAFT` **and** no `AssessmentReview`/`DeploymentAuthorisation` row references the assessment — on top of INV-17's existing conditions.
↳ origin: S6a/6b · refs: INV-17

**INV-37** · CODE · `authorisation_gate` cycle match
`authorisation_gate` matches by cycle: it passes only when a `DeploymentAuthorisation`'s `submission_round` equals the assessment's current `submission_round` — existence alone is insufficient; a re-submitted cycle orphans the prior ATO.
↳ origin: S6b

**INV-38** · CODE · `coverage_service` qualifying-link filter (S7a)
Control coverage counts only links on dispositioned items (item provenance ≠ `AI_SUGGESTED`); `UNADDRESSED` is a first-class response verdict (zero qualifying links), never an omission. Approval is tested against the **governing AIIA** (`parent_aiia_id` for a feeder item) at status `APPROVED` only — `DRAFT`/`NEEDS_REFRESH` are excluded from the headline, never a feeder's own perpetual-`DRAFT` status.
↳ origin: S7a · refs: INV-13, 20, 31

**INV-39** · CODE · cross-framework satisfaction is structural (S7a)
No inter-control coverage propagation exists or is permitted. Cross-framework satisfaction is structural — one multi-homed control projected across its `control_framework_map` rows — never inferred between distinct controls.
↳ origin: S7a · refs: D-19; INV-21

**INV-40** · CODE · export references evidence by manifest only (S7b)
The export references evidence by manifest (`id, sha256, filename, content_type, size, back-refs`) — never bytes, never embedded presigned URLs; retrieval stays on the hardened `GET /v1/evidence/{id}`.
↳ origin: S7b · refs: INV-6, 22

**INV-41** · CODE · export AIIA section is native items only (S7b)
The export's AIIA section is native items only; feeder content appears solely as full feeder sub-records carrying `surfaces_into` cross-refs. The export never calls `assemble_aiia_items` and never re-surfaces or duplicates feeder items — `assemble_aiia_items` stays the single surfacing locus.
↳ origin: S7b · refs: INV-16; D-18

**INV-42** · CODE · export generation stages `export.generated` (S7b)
Export generation is a disclosure/custody act and stages `export.generated` — the only audit-writing read besides `evidence.access`.
↳ origin: S7b · refs: INV-5

**INV-43** · CONVENTION · export is a live cursor + canonical `content_hash` (S7b)
The export is recomputed live per request, plus a canonical `content_hash` (sorted keys, ISO-8601 UTC, no insignificant whitespace — JCS/RFC 8785-style, computed *before* staging the audit so it lands in `detail`). No persisted/frozen export artifact exists in MVP.
↳ origin: S7b · refs: INV-25

**INV-44** · CODE · ATO-basis honesty (S7b)
The `DeploymentAuthorisation` row is the authoritative basis; the referenced assessment is presented as **current state, may have drifted**, never reconstructed (until AIIA versioning exists) — labelled `basis_is_current_state_not_authorisation_snapshot`.
↳ origin: S7b · refs: INV-32; OPEN-2

**INV-45** · CODE · audit-trail closure = entity-id OR detail-back-ref (S7b)
The export's audit-trail section is the durable-entity-id closure **or** a `detail` back-ref match — ephemeral/removal events (`assessment_item_control`/`assessment_item_evidence`, `.created`/`.deleted`) are scoped by `detail->>'item_id' IN (in-scope items)`, since the keyed link row hard-deletes and a current-rows closure would drop add/remove pairs entirely. Never the unscoped tenant log; `source_ip` excluded. Completeness is "resolvable to a surviving in-scope entity," with a bounded documented residual (`assessment.deleted` pristine-only; `evidence.access` on since-unlinked evidence).
↳ origin: S7b · refs: INV-5, 19

---

## Promoted from `CLAUDE.md` §3.2 (numbered above the live ceiling)

> Long-standing schema/code rules promoted from CLAUDE §3.2. They post-date STATE §6's sprint-numbered invariants (1–45), so they take the next free ids — an id is an identifier, not a chronology.

**INV-46** · DB · reference-data FK `ondelete=RESTRICT`
FKs from assessment items into library tables (`AssessmentItem.risk_id`, `AssessmentItemControl.control_id`) are `RESTRICT`, not `CASCADE`/`SET NULL` — deleting a referenced library risk/control is blocked rather than silently orphaning or stripping assessment records. Deprecate library entries via a soft-flag instead.
↳ origin: foundations (promoted from CLAUDE §3.2)

**INV-47** · CODE · `passive_deletes=True` on deferred cascades
Self-referential relationships meant to defer to a DB-level `ON DELETE CASCADE` must carry `passive_deletes=True` (`Assessment.feeders`), or SQLAlchemy nulls a loaded child's FK on parent delete instead of trusting the DB cascade. Apply to any future self-referential relationship of this shape.
↳ origin: S3–4 (promoted from CLAUDE §3.2)

**INV-48** · DB · global reference tables carry no `tenant_id`, no RLS
Catalogue, controls, risks, taxonomy, governance-role catalogue + conflict matrix, decision tree, and assessment section templates are cross-tenant by design: no `tenant_id` column, no RLS policy, readable from any session. Tenant data always carries `tenant_id`.
↳ origin: foundations (promoted from CLAUDE §3.2)

**INV-49** · CONVENTION · platform functionality is UI-operated, CLI bootstrap-only
Every platform-plane capability that requires ongoing operator interaction is operated through the operator console UI; CLI/scripts are reserved for initial bootstrap and break-glass that must precede or underlie the UI (DB-role creation, first-operator seeding, the first tenant before any console exists). A platform feature needing interactive operation is not done until its operator UI is built — the UI ships with the feature, never as a deferred follow-on.
↳ origin: platform-UI rule (retroactively closed at UI-F0-FOUNDATION — cited by `PLATFORM-UX.md`, `UX.md`, `FRONTEND.md`, `INDEX.md` since before this sprint, but never appended until now) · refs: INV-1, D-36

**INV-50** · CONVENTION · browser holds no token; all browser→API via the plane's own BFF
The browser never holds a Cognito token and never calls the API directly. Every browser→API request is mediated by that plane's own Next-server BFF, which holds the token server-side (keyed by an opaque session id in an httpOnly cookie) and forwards the bearer. A tenant-origin session cannot reach the operator origin or vice versa (plane separation is origin-level).
↳ origin: UI-F0-FOUNDATION · refs: INV-1, D-37

**INV-51** · CONVENTION · interactive coverage is never presented as the audit verdict
Interactive coverage (`require_evidence_for_satisfied=false`, internal to the coverage router) is labelled "interactive posture" and is never presented as the audit verdict. The audit-grade verdict is the export-embedded coverage (`require_evidence_for_satisfied=true`, passed by the export service — D-29), which downgrades unsubstantiated `SATISFIED → PARTIAL` and carries `downgraded_unsubstantiated`. The two may legitimately differ for one control and must be visually distinguished. The interactive route exposes no flag for a client to request `true`, so the line is structurally non-bypassable.
↳ origin: UI-F6-AUDITPACK · refs: D-29, DF6-3

**INV-52** · CONVENTION · coverage matrix visibly carries its caveat; no compliance-% headline
The coverage matrix always renders `not_an_obligation_set` prominently and presents `unaddressed_controls` as gaps-shown-not-failures. No "% compliant" headline treats unaddressed controls as fail until applicability (OPEN-3) lands. The `include_unapproved`+interactive combined state (doubly non-audit-grade) is always hard-divided from any adjacent audit-grade coverage view by an `AuditGradeDivider`.
↳ origin: UI-F6-AUDITPACK · refs: D-28, OPEN-3, DF6-4, DF6-8

**INV-53** · CONVENTION · export/ATO-document hooks fire only on explicit user action
The client issues an export/audit-pack or ATO-document fetch only on explicit user action, never as an eager mount/focus fetch. Hooks must carry `enabled: false`, `staleTime: Infinity`, `refetchOnWindowFocus: false`, `refetchOnMount: false`. Coverage reads are exempt (no audit staging). The staging fact for export reads lives in INV-42, not restated here.
↳ origin: UI-F6-AUDITPACK · refs: INV-42, PAT-10, D-35, DF6-2
**INV-54** · CONVENTION · presentational boundary — zero backend/schema/route/enum/contract delta
`UI-V0-VISUAL-FOUNDATION` is visual-layer-only. No backend route, DB schema, enum label, or API contract was added, changed, or removed. Any change to `packages/tokens` or `packages/ui` that also touches a non-CSS/TSX file outside those packages is a boundary violation.
↳ origin: UI-V0-VISUAL-FOUNDATION · refs: D-22, FE-14

**INV-55** · CONVENTION · provenance stays server-derived; no component authors a `provenance` value
No component in `packages/ui`, `apps/tenant`, or `apps/operator` ever constructs or sends a `provenance` field to the API. Provenance is set exclusively by the server on write (PAT-8). The `PrefillWithBasis.onOverride` callback signature carries no provenance parameter — tested by `prefill-with-basis.test.tsx`.
↳ origin: UI-V0-VISUAL-FOUNDATION · refs: INV-13, PAT-8, FE-15

**INV-56** · CONVENTION · SoD and permission enforcement remain server-side; UI absence is non-disclosure
`SodAction` and `RequirePermission` remove controls from the DOM as a usability / non-disclosure choice. Both are presentational only. The backend `apply_transition` / `require_permission` guards reject barred or unauthorised requests regardless of the UI state.
↳ origin: UI-V0-VISUAL-FOUNDATION · refs: FE-8, FE-13, INV-28, INV-8, D-4, D-24

**INV-57** · CONVENTION · live-state refetch discipline untouched by visual layer
No chip in `packages/ui` renders a cached verdict as settled. `VerdictChip` is a pure display component that receives a server-computed value; the `staleTime: 0` / refetch-on-mutation contract (FE-7) is owned by each surface's query hook, not by the chip.
↳ origin: UI-V0-VISUAL-FOUNDATION · refs: FE-7, INV-25, INV-32

**INV-58** · CONVENTION · no token in the browser; BFF custody preserved
The visual-layer tokens are CSS custom properties compiled into the Next.js build. No Cognito token, session token, or other auth secret is exposed to the browser through the token layer. `FE-2` / `INV-50` are unchanged.
↳ origin: UI-V0-VISUAL-FOUNDATION · refs: INV-50, FE-2

**INV-59** · CONVENTION · `tenant_id` never client-supplied
The visual layer introduces no mechanism by which a client could supply `tenant_id`. No CSS variable, data attribute, or component prop carries or exposes tenant identity. INV-3 is unchanged.
↳ origin: UI-V0-VISUAL-FOUNDATION · refs: INV-3

**INV-60** · CONVENTION · plane chrome never bleeds; operator rail is the visual correlate of plane separation
The `[data-theme="operator"] nav` selector carries `--chrome-rail-bg: var(--color-brand-strong)`. The tenant skin carries no rail token. An operator can never be shown the tenant chrome, and a tenant user can never see the operator rail. INV-1 is unchanged.
↳ origin: UI-V0-VISUAL-FOUNDATION · refs: INV-1, FE-18

**INV-61** · CONVENTION · evidence is never inline-rendered; the visual layer introduces no inline byte path
No component in the visual-layer track renders evidence bytes inline. `EvidenceTable` and related components link to download endpoints; no blob URL, base64 embed, or inline `<img src="...">` from evidence bytes is introduced.
↳ origin: UI-V0-VISUAL-FOUNDATION · refs: INV-22

**INV-62** · CODE · every intended text pairing meets WCAG 2.1 AA; enforced by contrast gate test
Every text foreground/background pairing in `packages/tokens/src/primitives.css` must clear 4.5:1 (normal) or 3:1 (large) per WCAG 2.1 §1.4.3. Every meaningful-graphical pairing must clear 3:1 per §1.4.11. Hairlines (structural separators) are exempt. Enforced by `packages/tokens/src/__tests__/contrast.test.ts` which fails the build on any regression.
↳ origin: UI-V0-VISUAL-FOUNDATION · refs: FE-14, SV-7, D-41, V-7

**INV-63** · CONVENTION · components carry no literal colour or spacing values
Every colour and spacing value used in `packages/ui` components must reference a design token via a Tailwind utility class or `var(--token-name)` inline style. Literal hex, pixel, or RGB values in `className` strings are prohibited and enforced by `eslint-plugin-irontrust/no-literal-token-value`.
↳ origin: UI-V0-VISUAL-FOUNDATION · refs: FE-3, FE-14, V-4

**INV-64** · CONVENTION · `eu_ai_act_tier` renders only via `TierBadge`; `VerdictChip` renders no tier member
`eu_ai_act_tier` values (`prohibited`, `high_risk`, `limited_risk`, `minimal_risk`, `unclassified`, `requires_context`) must be converted via `toTierMember()` and displayed exclusively with `<TierBadge>`. `VerdictChip` must not receive any of these values (they no longer appear in its `TONE_MAP`). Violations would merge two orthogonal channels — the tier-magnitude channel (`--tier-*`) and the verdict-tone channel (`--verdict-*`) — breaking the channel-orthogonality rule from FE-16.
↳ origin: UI-V1-TENANT-SKIN · locus: `packages/ui/src/status/` · refs: FE-16, D-48, INV-56

**INV-65** · CONVENTION · IBM Plex Serif confined to `AuditPackView` and `AtoDocumentView` root wrappers
The serif face (`font-serif` / IBM Plex Serif) must only appear on the root `<article>` of `AuditPackView` and `AtoDocumentView`. No other tenant surface uses serif. The font-face signals "exported document / archival artefact", not UI. Using it in interactive surfaces (forms, lists, dashboards) violates the reading-mode distinction.
↳ origin: UI-V1-TENANT-SKIN · locus: `packages/ui/src/audit/` · refs: FE-17, D-44

**INV-66** · CONVENTION · every `<TableRow>` must be wrapped in `<TableBody>`
`<TableRow>` (`<tr>`) must never be a direct child of `<Table>` (`<table>`). Browsers auto-insert a `<tbody>` during HTML parsing; React SSR does not — the DOM mismatch triggers a React hydration error at runtime. Wrap all data rows in `<TableBody>` (the exported `<tbody>` primitive from `packages/ui`). `<TableHeaderRow>` (`<thead>`) is exempt: browsers do not auto-promote `<thead>` the same way.
↳ origin: post-UI-V1 correction (2026-06-25) · locus: `packages/ui/src/primitives/table.tsx` · refs: INV-54

**INV-67** · CONVENTION · Tailwind v4 `@source` directive must cover `packages/ui/src` in every app `globals.css`
Tailwind v4 automatic content detection scans only the app's own directory. Utility classes used exclusively in `packages/ui` components are never generated unless the app explicitly declares `@source "../../../packages/ui/src"` before the `@import "tailwindcss"` line. This directive must appear in `apps/tenant/app/globals.css` and `apps/operator/app/globals.css`. Omitting it causes the design system to silently produce an unstyled UI — all token-derived classes from UI components go missing.
↳ origin: post-UI-V1 correction (2026-06-25) · locus: `apps/*/app/globals.css` · refs: FE-14, D-49

**INV-68** · CONVENTION · No-undesigned-UI guardrail: the coding agent does not originate visual, layout, UX, or composition design
The coding agent implements only what an execution-only handoff specifies. If it judges that a visual or UX change is needed, it flags the need and stops; it does not improvise. It never records an undesigned visual or UX decision in STATE, INDEX, or any canonical as shipped work. Genuine defects (build breaks, hydration errors, broken redirects, classes referencing absent tokens) are exempt and may be fixed and recorded as fixes. The exemption boundary: a defect is a behaviour the surface was specified to have and does not exhibit; design is any unspecified visual or UX choice. This invariant does not collide with INV-49 (operation locus, not design origination).
↳ origin: UI-C0-PRODUCTION-FOUNDATION · locus: `CLAUDE.md` + `packages/ui/src` + `apps/*` · refs: D-51

**INV-69** · CONVENTION · Compose from the kit — no bespoke layout or one-off components (forward-scoped per C0-5)
A surface built after UI-C0 uses `AppShell`/`Sidebar` (FE-20), `PageScaffold`/`PageHeader` (FE-21), `EmptyState`/`FirstRunPanel` (FE-22), and the FE-23 kit primitives rather than inventing bespoke layout or one-off components. A surface built before UI-C0 comes under this invariant only once its UI-C0 per-surface composition pass has cleared it in the composition-debt register (design doc Appendix C). Until cleared, it is tracked as remediation debt, not a standing violation.
↳ origin: UI-C0-PRODUCTION-FOUNDATION · locus: `packages/ui/src` + `apps/*` · refs: FE-20, FE-21, FE-22, FE-23, D-51, INV-68

**INV-70** · CONVENTION · Every data surface defines empty, first-run, loading, and error states (forward-scoped per C0-5)
Any surface that displays server-fetched data must provide all four presentation states: empty (no data), first-run (no data and first visit), loading (skeleton), and error. This uses FE-22 primitives (`EmptyState`, `FirstRunPanel`, `Skeleton`, `ErrorState`). The same forward-scope clause as INV-69 applies: surfaces predating UI-C0 are brought under this invariant at their per-surface composition pass.
↳ origin: UI-C0-PRODUCTION-FOUNDATION · locus: `apps/*` data surfaces · refs: FE-22, INV-69, D-51, INV-68

**INV-71** · CONVENTION · Governance-role assignment UI: resolvable SoD conflicts shown disabled-with-reason before the act; structural self-assignment bar honoured by control absence
In the governance-role assignment panel (FE-24), a **resolvable** SoD conflict (the target member already holds a role that conflicts with the candidate, per `governance_role_conflict`) is surfaced as a disabled assign button accompanied by a reason string of the form `"Conflicts with {held role name}: separation of duties"` (colon, no em dash). The **structural** self-assignment bar (D-5) is honoured by rendering **no** assign or revoke control at all (INV-56); an explanatory note may accompany the absent control. The client computes the affordance from the conflict matrix; the server (`assert_governance_assignable`, INV-7) is the authority and a forged call returns 403. Client-side visibility never substitutes for server enforcement.
↳ origin: UI-F9-MEMBERS · locus: `apps/tenant/app/members/_components/role-panel.tsx` · refs: INV-7, INV-56, D-4, D-5, FE-8, FE-24
