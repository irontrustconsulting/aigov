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

**INV-72** · CONVENTION · `DrillDownStep` single-vendor auto-skip: when `vendors.data.length === 1` in the expanded sub-category, the vendor rung is skipped automatically via a `useEffect` watching `[expandedSubcategoryId, expandedVendorId, vendors.data]` that sets `expandedVendorId = vendors.data[0].id`. The effect is gated on `expandedSubcategoryId !== null && expandedVendorId === null && vendors.data !== undefined && vendors.data.length === 1`. A `vendorAutoSkipPrevented` ref guards against re-trigger: it is reset to `false` in `toggleSubcategory` and `toggleCategory` so the auto-skip fires normally on each fresh sub-category. In the accordion design, back-navigation from the confirm stage returns `selectedProductId` to `null` without changing `expandedVendorId`, so the re-trigger condition (`expandedVendorId === null`) is never met on back. The single-vendor product list is rendered only after `expandedVendorId` is confirmed (`expandedVendorId === null || subCategoryProducts.isLoading → Skeleton`) to prevent a transient flash before the auto-skip effect fires.
↳ origin: UI-C2-INTAKE-CATALOGUE · locus: `apps/tenant/app/systems/new/_steps/drill-down-step.tsx` · refs: D-56, FE-25

**INV-73** · CONVENTION · Form-control selection and active affordances use neutral or brand-selection tokens only — never semantic-channel tokens.
Multi-select toggle-chip clusters: selected = `bg-ink text-surface border-ink`; unselected = `bg-surface text-ink border-hairline hover:bg-surface-sunken`. `ListSelectRow` branch-mode expansion (chevron rotation) uses the `transition-transform` utility only — no colour change. The `--verdict-*` and `--prov-*` channel tokens are reserved for their named semantic purpose (verdict outcomes, provenance signal) and must not be borrowed for form-control affordance states.
↳ origin: UI-C2-INTAKE-CATALOGUE · locus: `packages/ui/src/structured-input/multi-select-input.tsx`, `packages/ui/src/kit/list-select-row.tsx` · refs: FE-4, FE-23, INV-56, INV-63

**INV-74** · CONVENTION · Empty and first-run states retain the surface chrome (forward-scoped)
A data surface's empty and first-run states retain the surface chrome (nav, header with primary action, stat row, table/section frames); the empty or get-started content renders **within** the retained data region, not as a full-surface replacement. `FirstRunPanel` (FE-22) remains valid and may be rendered within retained chrome. This invariant binds a surface only when that surface's composition pass explicitly adopts it (per-surface, like INV-69/INV-70); existing surfaces are not retroactively non-compliant. **Applied:** F2 dashboard (D-61 zero-systems scaffolded-empty — first surface under INV-74).
↳ origin: UI-V2-DEPTH-LAYOUT · locus: `apps/tenant/app/dashboard/page.tsx` (first binding) · refs: INV-70, FE-22, FE-27, D-61

**INV-75** · CONVENTION · No raw enum member faces the user
The five verdict-family enums (`approval_status`, `assessment_status`, `classification_status`, `coverage_status`, `lifecycle_state`) render exclusively via the `VerdictChip` `value`→label map (FE-16 ALTER, D-60). `eu_ai_act_tier` renders via `toTierMember()` (D-48). Vocabulary fields render via `VocabItemOut.label`. A bare snake_case enum member never reaches the DOM as user-facing text. Scope is these three families only; `provenance_confidence` (rendered via `ProvenanceBadge`, FE-15) is explicitly excluded — its ORM-vs-doc member count is an unreconciled HEAD question owned elsewhere. Enforcement: `verdict-chip.test.tsx` asserts all 25 unique wire values produce their mapped label; any future member without a map entry triggers `console.warn` at runtime (defensive fallback to raw value, not a throw).
↳ origin: UI-V2-DEPTH-LAYOUT · locus: `packages/ui/src/status/verdict-label-map.ts`, `packages/ui/src/status/verdict-chip.tsx` · refs: FE-16, D-60, INV-68

**INV-76** · CODE · `resolve_classification` reads no use-distinguishing context fields
`resolve_classification` (and the context gate) must not read `usage_context_id`, `human_oversight_type_id`, `use_case_data_category`, or `use_case_affected_party`. The classifier's only inputs are the product/taxonomy bridge (`system.catalogue_product_id → product_category_eu_mapping → eu_ai_act_subcategory`). Context fields are use-distinguishing facts captured for DPIA/FRIA and export, not tiering inputs. This is asserted by `tests/test_use_case_classification.py::TestClassifierContextIsolation`.
↳ origin: DM-S1 · locus: `app/services/classification.py` · refs: D-63, INV-77

**INV-77** · DB · `use_case_data_category` and `use_case_affected_party` carry `tenant_id` and are RLS-isolated
Both DM-S1 junction tables include a `tenant_id uuid FK tenant NOT NULL` column and an RLS policy `tenant_id = current_setting('app.current_tenant', true)::uuid`. Rows for tenant A are never returned in a session scoped to tenant B. This closes the unresolved isolation question that applied to the former `system_data_category`/`system_affected_party` tables (see DATA-MODEL §5). Cross-tenant isolation is asserted by `tests/test_use_case_classification.py::TestContextLinkIsolation`.
↳ origin: DM-S1 · locus: `alembic/versions/d82c389d1f07_context_relocation_use_case.py`, `app/models/intake.py` · refs: D-63, INV-76


**INV-78** · CODE · No route may construct a `System` outside `POST /v1/registrations`
`POST /v1/systems` is removed (DM-S2). The only route that instantiates a `System` model is `POST /v1/registrations`. This closes the orphan-system seam (REG-2): a `System` cannot exist without a first `UseCase` and a `Classification` snapshot, because all three are created atomically in one transaction. Any other route (test fixtures excluded) that calls `System(...)` or `system_service.create_system(...)` is a violation. Asserted by `tests/test_systems.py::TestPostSystemsAbsent` (404/405) and `tests/test_registrations.py::TestRegistrationAtomicity` (rollback leaves no orphan row).
↳ origin: DM-S2 · locus: `app/routers/v1/registrations.py`, `app/routers/v1/systems.py` · refs: D-65, INV-27

**INV-79** · DB · At most one `draft_registration` row per `(tenant_id, owner_user_id)`
`UniqueConstraint('tenant_id', 'owner_user_id', name='uq_draft_one_per_user')` is enforced at the DB level. The application enforces this via SELECT-first get-or-create (DF-D3-5); the constraint is a backstop for concurrent races. A user has at most one active draft at any time; the draft is discarded atomically when `POST /v1/registrations` succeeds (D-66, SV-3). RLS provides tenant isolation; application-level `owner_user_id` filtering provides user isolation within the tenant (DF-D3-4).
↳ origin: DM-S3 · locus: `alembic/versions/84d535834a0d_draft_registration.py`, `app/models/domain.py::DraftRegistration` · refs: D-66, DF-D3-4, DF-D3-5, INV-4

**INV-80** · CODE · No use-case-removal path exists
No router exposes a route that deletes a `use_case` row (no `DELETE /v1/use-cases/{id}`, no system `DELETE` cascading into `use_case`). Enforced by `tests/test_systems.py::TestDeleteRoutesAbsent` (404/405 assertions for both paths), mirroring `TestPostSystemsAbsent` (INV-78). This is the single novel guarantee; system-construction atomicity is INV-78's home and is cited, not re-asserted. Together with INV-78 they entail that any zero-use-case system is legacy pre-DM-S2 data.
**Seam:** a future void/withdraw path (OPEN-1) that removes a use case reopens bare-system reachability and must re-evaluate the dashboard's bare-system handling, which after D-67 (if Branch A is ever executed) would retain no `GET /v1/systems` read to surface it (NB-4). The OPEN-1 entry carries a back-reference to this invariant and to D-67.
↳ origin: DM-S3b · locus: `tests/test_systems.py::TestDeleteRoutesAbsent`, `app/routers/v1/use_cases.py`, `app/routers/v1/systems.py` · refs: INV-78, OPEN-1, D-67

**INV-81** · CONVENTION · `SingleSelect` never renders a value its bound state does not hold
When `value=""` (empty) or does not match any `options` entry, `SingleSelect` (`packages/ui/src/structured-input/single-select.tsx`) displays a non-selectable placeholder `<option value="" disabled hidden>` as the first option. The substantive options follow. Corollary: the value submitted from any form containing a `SingleSelect` always equals the value visible in the control — no silent phantom-first-option submission. All consumers that previously bound `value=""` now show the placeholder instead of the first substantive option (cosmetic shift; submit behaviour unchanged for non-empty values). Enforced by the primitive test in `packages/ui/src/structured-input/__tests__/single-select.test.tsx`.
↳ origin: DM-S4a · locus: `packages/ui/src/structured-input/single-select.tsx` · refs: FE-4 (ALTER DM-S4a), D-70

**INV-82** · CODE · `resolve_classification` selects the governing subcategory from `use_case.product_category_id` when set
When `use_case.product_category_id` is non-null, `resolve_classification` governs from that category's primary `product_category_eu_mapping` (the row with `is_primary=True` for that category). This declared path overrides the product-wide-highest path. When `product_category_id` is null (category not declared), the resolver falls back to the product-wide-highest primary mapping across all membership categories. When no mapping exists at all (no product / no primary mapping), the result is `REQUIRES_CONTEXT`. `ClassificationDisposition` (`AUTHORITATIVE` / `DOWN_SELECTION`) is then computed by comparing the declared category's tier to the product-wide-highest tier: equal → `AUTHORITATIVE`; lower → `DOWN_SELECTION`. The null / no-product path always produces `AUTHORITATIVE` when resolvable. Asserted by `tests/test_use_case_classification.py`.

**INV-83** · CODE · Every prefill default is dispositioned before the registration transaction commits; provenance is server-derived
When `POST /v1/registrations` is called for a catalogue-linked system, the handler must derive and write a `prefill_disposition` row for every seeded field before the transaction commits (D-74, D-75). The client sends a `confirmed_fields: list[str]` signal; the server derives `ProvenanceConfidence` (`USER_CONFIRMED` / `USER_AMENDED`) and writes the row — the client never asserts provenance directly (PAT-8, INV-13). Derived intake defaults (`operator_role_id`, `lifecycle_stage`; basis = `"derived"`) require an explicit confirm signal: if submitted at the seed value without appearing in `confirmed_fields`, the handler raises HTTP 422 with `undispositioned_fields`. Catalogue-seeded fields (`hosting_model_id`, `purpose`, `name`) take submit-as-confirmation: if the submitted value equals the seed, `USER_CONFIRMED`; if it differs, `USER_AMENDED`. Catalogue-fact dispositions arrive as `"fact:<key>"` (USER_CONFIRMED) or `"fact_amended:<key>"` (USER_AMENDED) entries in `confirmed_fields`. Custom systems and no-product systems: no seeds, no disposition rows, no 422 gate. **Transience rule (B1):** disposition intent is transient — `confirmedIntakeFields`, `confirmedFactKeys`, `amendedFactKeys` are NOT persisted in `draft_blob`; `RESUME_FROM_DRAFT` resets all three to `[]` so derived fields re-gate on resume.
**[ALTER FIX-RESUME-REGATE]** The re-gate on resume is satisfied by re-deriving basis, not just resetting confirm arrays. `SEED_INTAKE` computes each seeded field's basis value-vs-seed (current value equals the seed value → the seed's basis; otherwise `"user-set"`), not value-presence — a resume-restored value still at its derived seed re-reads `"derived"` and genuinely re-gates, closing the client/server basis mismatch OPEN-5 identified (client silently read `"user-set"` while the server, which re-derives basis from the seed map independent of the client, still 422'd). The re-gate is satisfiable wherever the confirm affordance is reachable, not only at the `intake` step: a pre-commit disposition gate (FE-36) at the foot of the use-case step surfaces any still-unconfirmed derived field before Register, so a draft resumed past `intake` is never a dead end. A catalogue fact not re-reviewed on resume (Path B) retains its catalogue-curated provenance; the client never synthesises a `USER_CONFIRMED` for it — no commit-time "confirm everything not explicitly amended" fallback, since `amendedFactKeys` is itself reset on resume and such a fallback would fabricate confirmation for a fact the user had actually amended pre-park. No change to server predicates (`_dispose_intake_prefill` / `_dispose_fact_prefill` are unchanged) or to the "not persisted in `draft_blob`" rule above.
↳ origin: CAT-4 (prefill-disposition sprint) · locus: `app/routers/v1/registrations.py::_dispose_intake_prefill`, `_dispose_fact_prefill`; `alembic/versions/c7e2f1a3b4d5_prefill_disposition.py` · refs: D-74, D-75, PAT-8, INV-13, INV-55, FE-32
↳ origin: DM-S4b · locus: `app/services/classification.py::resolve_classification` · refs: D-71, D-72, D-73, INV-76
↳ origin: FIX-RESUME-REGATE · locus: `apps/tenant/app/systems/new/wizard-state.ts::SEED_INTAKE`, `apps/tenant/lib/intake/pre-commit-disposition-gate.tsx`, `apps/tenant/lib/intake/derived-unconfirmed.ts` · refs: FE-36, DF-RR-1..5, OPEN-5

**INV-84** · CONVENTION · Catalogue-fact values render shape-typed; `JSON.stringify` and array-to-string coercion (`String(array)`) never reach the DOM; boolean facts render judgement-neutral (no `--verdict-*` token); an overridden fact renders its override label as plain text, keeping the visual and the `fact_amended:<key>` disposition in lockstep (R8).
The `FactValue` component (`apps/tenant/lib/intake/fact-value.tsx`) implements five branches in strict priority order: (1) `answer` boolean → neutral Yes/No chip; (2) array-valued key → pill cluster; (3) string-valued key → plain text; (4) `note` only → note text as value; (5) residual → `<dl>` definition list with `String()` for primitives, never `JSON.stringify`. The branch-5 floor guarantees no shape can produce raw JSON in the DOM. Yes/No chip and pill items carry `data-fact-value` (and `data-bool` on the chip) for test isolation; neither carries `--verdict-*` or `data-tone`. Asserted by `lib/intake/__tests__/fact-value.test.tsx` covering all five branches, the branch-5 floor, and the no-verdict-token rule; and by `_steps/__tests__/prefill-step.test.tsx` asserting end-to-end: no raw JSON for `{answer,note}` facts, no comma-join for `{list:[…]}` facts.
**R10 — value type is uniform; prose mass vs token mass is inherent (designed, not a defect).** All value outputs across all five branches render `text-sm text-ink`. `text-ink-muted` is strictly the supporting-note / basis / caption role and never applies to a value node regardless of whether the value is a compact token (chip, pill, short string) or long prose (branch 4 note-only). The perceived visual weight difference between a prose value and a chip value is a function of content mass, not a rendering inconsistency. If long-prose values ever need softening, the correct lever is measure (`max-w-*`) or leading (`leading-*`), never type-size or tone change.
↳ origin: UI-V-PREFILL-FACT · locus: `apps/tenant/lib/intake/fact-value.tsx`, `apps/tenant/app/systems/new/_steps/prefill-step.tsx` · refs: R1, R3, R8, R10, FE-16, FE-33, INV-83, D-21

**INV-85** · CONVENTION · The registration front-door gates on an explicit draft-resolution flag (`resumeResolved`), never on the wizard `step`/`draftId` cursor
While an active-draft fetch succeeds (`activeDraft.data` truthy) and the draft is unresolved (`state.resumeResolved === false`), no wizard step renders: a server-side draft is never reachable-for-overwrite (guards `uq_draft_one_per_user`, INV-79) nor orphaned-from-view behind a first-paint race. `resumeResolved` flips `true` in exactly three reducer transitions — `RESUME_FROM_DRAFT`, `DRAFT_CREATED`, `DRAFT_DISCARDED` — and is client-transient: it is never written into `draft_blob` (`toDraftBlob` in `page.tsx` does not carry it), consistent with the transience rule for other UI-only disposition state (INV-83). On `activeDraft.isError`, `activeDraft.data` is `undefined`, the gate is false, and the wizard renders directly (unchanged fallback behaviour; clobber prevention falls back to `getOrCreate` SELECT-first plus last-write-wins, DF-D3-5/DF-D3-6).
↳ origin: UI-DRAFT-RESUME-GATE · locus: `apps/tenant/app/systems/new/wizard-state.ts`, `apps/tenant/app/systems/new/page.tsx` · refs: INV-79, INV-83, DF-D3-1, DF-D3-5, DF-D3-6, D-66, D-76

**INV-86** · CONVENTION · Setting a vendor/product clearance is an authoriser-only act; reading the clearance queue is not gated by this invariant
The set-clearance control (`apps/tenant/app/clearances`) renders only for a caller holding `authoriser` (`SodAction barred={!isAuthoriser}`), absent otherwise — never merely disabled. `GET /clearance-queue` itself is `gov:ALL` (DF-CLR-17); the server `PUT /vendors|products/{id}/approval` stays `gov:authoriser` regardless of what the UI renders.
↳ origin: UI-F10-CLEARANCE · locus: `apps/tenant/app/clearances/_components/clearance-queue-list.tsx`, `app/routers/v1/lifecycle.py` · refs: FE-8, D-4, DF-CLR-17

**INV-87** · CONVENTION · The clearance surface shows the fan-out blast radius — the full set of use cases re-evaluated on commit, not merely those parked — before the act commits
Each vendor/product entry in `ClearanceQueueRead` carries both `awaiting_use_case_count` (parked at the gate) and `affected_use_case_count`/`affected_system_count` (the full fan-out set). Both derive from the same `System.catalogue_vendor_id`/`catalogue_product_id` join `fan_out_vendor_approval`/`fan_out_product_approval` use, so the confirm-step preview and the actual fan-out cannot diverge. The set-clearance dialog's confirm stage renders the affected counts before the `PUT` fires.
↳ origin: UI-F10-CLEARANCE · locus: `app/services/lifecycle_service.py::clearance_queue`, `apps/tenant/app/clearances/_components/clearance-dialog.tsx` · refs: APR-2

**INV-88** · CONVENTION · A product's clearance control renders disabled-with-reason until its parent vendor is `APPROVED`
`ProductClearanceEntry.vendor_cleared` (`vendor.status == APPROVED`) drives `SodAction blockedReason="Clear the vendor first"` on the product row's set-clearance button, for an authoriser caller. A non-authoriser caller never sees the control at all (`barred`, INV-86) — the disabled-with-reason state is reachable only within an authoriser's own view.
↳ origin: UI-F10-CLEARANCE · locus: `apps/tenant/app/clearances/_components/clearance-queue-list.tsx` · refs: APR-2, FE-8, INV-86

**INV-89** · CONVENTION · The clearance surface is born INV-69/INV-70 compliant
`apps/tenant/app/clearances` composes exclusively from the shipped C0 kit (`PageScaffold`/`PageHeader`, `SectionGroup`, `DataTable`, `Skeleton`/`ErrorState`/`EmptyState`, `VerdictChip`, `SodAction`, `Dialog`) — no bespoke chrome. No composition-debt row is owed for this surface.
↳ origin: UI-F10-CLEARANCE · locus: `apps/tenant/app/clearances/` · refs: INV-68, INV-69, INV-70

**INV-90** · CONVENTION · The portfolio hub remains read-only; whose-court supplies navigation only
The F2 dashboard's your-court re-treatment (raised card, `VerdictChip`, trailing chevron) and `system-detail-client.tsx`'s additive clearance deep-link only add navigation affordances — no clearance action is exposed from either surface. Setting a clearance happens exclusively on `apps/tenant/app/clearances`.
↳ origin: UI-F10-CLEARANCE · locus: `apps/tenant/app/dashboard/page.tsx`, `apps/tenant/app/systems/[id]/system-detail-client.tsx` · refs: A1, D-38, FE-11

**INV-91** · CONVENTION · A tenant sidebar entry is hidden only when the caller is barred from that surface's purpose by separation of duties
Review queue renders iff the caller holds `reviewer` (the reviewer/authoriser hard conflict, D-4/D-10); Clearances renders for every governance role (reading the clearance status list breaches no SoD — the set-clearance action is gated inside the surface itself, INV-86); Evidence, Audit, Portfolio are navigable by any governance role, unconditionally. The server gate and each surface's own empty-state remain the authority — the sidebar gate is presentational (FE-8).
↳ origin: UI-F10-CLEARANCE · locus: `apps/tenant/app/_components/tenant-sidebar.tsx` · refs: FE-8, UX-5, D-4, D-10, FE-24, INV-71, INV-86
