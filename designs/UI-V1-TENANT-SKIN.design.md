# UI-V1-TENANT-SKIN — Final Design Doc

**Status:** FINAL, review folded in · **Track:** visual layer, tenant skin application across `UI-F1..F6` · **Plane:** tenant only · **Delta:** presentational only, 0 backend / 0 schema / 0 route / 0 enum / 0 contract (carries `INV-54`) · **Builds on:** `UI-V0-VISUAL-FOUNDATION` (`FE-14..19`, `INV-54..63`, `D-41..47`), `D-22` · **Adds:** the `--tier-*` semantic channel, `TierBadge`; amends `FE-16`; resolves the V-5 tier escalation, `OPEN-V2`, `OPEN-V3`, `OPEN-V5`

Supersedes the draft. The three Blocking findings were one knot: the "no new tokens" constraint forced tier onto borrowed channels, `FE-16` forbids exactly that (its orthogonality rule is about the visual slot, the ramp, not the wrapping component), and `SV-1` showed there is no categorical severity chip to disambiguate against, so the `--sev-*` reuse was pure colonisation. Resolved by tier-channel option (a): a dedicated `--tier-*` channel and a recorded `FE-16` amendment. Disposition table at §6.

## §0 · Pre-flight verify checklist (binding)

| ID | Check | Why |
|---|---|---|
| VV-1 | Confirm the V0 atoms exist in `packages/ui` at HEAD: `ProvenanceBadge`, `VerdictChip`, `WhoseCourtIndicator`, `StaleLockBanner`, `BadFromStateBanner`, `SodAction`, `PrefillWithBasis`, `Button` (ghost), `Table`/`QueueRow` (density), and F6's `CoverageMatrix`, `NotAnObligationSetBanner`, `AuditGradeDivider`, `AuditPackView`, `EvidenceManifestTable`, `AtoDocumentView` | V1 composes these; it must not re-implement them |
| VV-2 | Confirm `skin-tenant.css` comfortable-density values (16 to 24 rhythm, 15px body) as the base both density modes compose | Adoption and assurance are composition over one skin (`D-45`, `FE-18`, `OPEN-V3`) |
| VV-3 | Read the live `verdict-chip.tsx` `eu_ai_act_tier` branch (`D-21`, `SV-2`). STATE asserts the V0 fold (HIGH→attention, LIMITED→neutral, MINIMAL→neutral); make the removed branch and the 34→28 member-count delta exact | Migrate tier out of `VerdictChip` cleanly, no dead tone branch |
| VV-4 | Read the live coverage response key set (`D-21`, `SV-3`). `coverage_status` enum is `{OPEN, PARTIAL, SATISFIED}`; `UNADDRESSED` and `downgraded_unsubstantiated` are computed verdicts, not enum members. `verdict` stays plain `str`, no enum bind | F6 tone mapping freezes on the computed string set |
| VV-5 | Confirm every surface's route consumption is unchanged; no V1 work item touches a non-CSS/TSX file outside `packages/{tokens,ui}` and the app view layers | `INV-54` boundary holds at the surface-application track |
| VV-6 | Confirm IBM Plex Serif installed for the document face, and `lucide-react` for icons | F6 document face (`D-43`/`FE-17`); icon assignments (`OPEN-V2`) |
| VV-7 | `OPEN-V5` usability gate: compute `--brand` (`#1E4651`) vs `--verdict-positive` (`#2F5D4A`) luminance on a real yours-and-approved row; eyeball `--brand`-token co-occurrence on F2 and F4 | Record outcome; split or nudge only on observed confusion |
| VV-8 | Extend the contrast gate (`INV-62`/`D-47`/`contrast.test.ts`) to the new `--tier-*` pairings; freeze blocked until all pass | The `--tier-*` ramp is new; it must clear AA the same way the V0 tokens did |

## §1 · Resolved decisions

| ID | Decision |
|---|---|
| V1DD-1 | One comprehensive V1: skin-level resolution first (`--tier-*` channel, density modes, `TierBadge`, icons, `OPEN-V5` gate), then per-surface application F1 to F6, dependency-ordered. Fallback split at the adoption/assurance seam only if the handoff proves unwieldy |
| V1DD-2 | Withdrawn and replaced. Tier does **not** reuse `--sev-*` |
| V1DD-3 | Adoption vs assurance is composition and spacing within the one shipped tenant skin; no named adoption sub-tokens (`OPEN-V3` resolved) |
| V1DD-4 | Tier-channel option (a): a dedicated `--tier-*` semantic channel for the four magnitude tiers; the two resolution states render on `--verdict-*` (verdict-class, not magnitudes). `FE-16` amended to add the channel and remove `eu_ai_act_tier` from the `VerdictChip` channel list, recorded as `D-48` with rejected alternatives |

## §2 · The `--tier-*` channel and TierBadge (escalation resolution)

`eu_ai_act_tier` becomes a fifth semantic channel (`FE-16` amended, `D-48`), distinct from `--sev-*` and `--verdict-*`. The ramp encodes regulatory-classification magnitude by depth and fill, deliberately in a cool navy-slate family so it never reads as the warm severity family (and so a future categorical severity chip, `AIIA-8` heat view, stays unmistakable). Provisional values, bound to the extended contrast gate (`VV-8`):

| `eu_ai_act_tier` | Channel · token | Treatment |
|---|---|---|
| `PROHIBITED` | `--tier-prohibited` | white on solid `#1C2A4F`, deepest; the only tier with an icon (`ban`); supreme (`D-7`) |
| `HIGH` | `--tier-high` | white on solid `#2E4A78`, filled |
| `LIMITED` | `--tier-limited` | label `#36507D` on tint `#E7ECF5`, outline |
| `MINIMAL` | `--tier-minimal` | label `#4A5878` on tint `#EDEFF4`, lightest outline; affirmative only, never a fallback (`INV-12`) |
| `UNCLASSIFIED` | `--verdict-neutral` | resolution state, verdict-class, not a magnitude |
| `REQUIRES_CONTEXT` | `--verdict-attention` | resolution state, owner decision pending |

The fill transition (HIGH and above filled, LIMITED and below outline) gives pre-attentive separation in scan contexts (F2 portfolio, F4 queue), which is the gap (b) verdict-only could not close.

`TierBadge` (`packages/ui/status/tier-badge.tsx`, NEW) renders all six members: the four magnitudes on `--tier-*`, the two resolution states on `--verdict-*` (tone follows meaning-class, not enum-membership). No `VerdictChip` renders any tier member; no `TierBadge` renders any non-tier member.

- **Compact variant** (surface headers, queue rows, lists): label plus tone.
- **Card variant** (F1 resolved-tier and context-outcome screens): the reasoning-first treatment (`UX-4`), tier as hero, the basis shown (Annex / criteria, `CLS-2`), the override ladder beneath (`SodAction`-barred to `system_owner`).

**Present vs ALTER:** `--tier-*` tokens NEW; `TierBadge` NEW; `VerdictChip` ALTER (remove the tier branch, 34→28 members; keeps `assessment_status`, `lifecycle_state`, `classification_status`, `coverage_status`, `approval_status`).

## §3 · Two density modes (composition, not new skins)

Both modes consume `skin-tenant.css`; the difference is layout, spacing-step selection, and component density props, not tokens (`V1DD-3`, `D-45`).

| | Adoption-comfortable | Assurance-dense |
|---|---|---|
| Where | F1, owner-led F2 | F3 to F6, governance-led F2 |
| Flow | single-column, one decision per view, 24 rhythm | multi-region panels, tables, queues |
| Cards | large reasoning-first cards | compact rows, scan-optimised |
| Density prop | `Table`/`QueueRow` comfortable | `Table`/`QueueRow` `density="compact"` |
| Driver | recognition over recall, governance invisible (`UX-1`/`UX-3`) | information density, the governance surface users want (`UX.md §2`) |

## §4 · Per-surface visual spec (present → ALTER)

**F1 intake — `systems/new` — adoption, comfortable.** Single-column wizard. Drill-down via the structured-input set (`FE-4`), select-first. Prefill-confirm panel: `PrefillWithBasis` cards, a `ProvenanceBadge` per fact, basis shown, Confirm/Amend display-only (`DF1-8`). **Signature:** the `TierBadge` card variant at the resolved-tier and context-outcome screens, tier as hero with basis and the `system_owner`-only override ladder (`SodAction`-absent for others). Whose-court close via `WhoseCourtIndicator` off the lifecycle blocking vector (`FE-11`). Role empty-states calm, not dead controls. Icon: `clipboard-plus`.

**F2 portfolio — `dashboard`, `systems/[id]` — both, role-led.** `PortfolioHub` two sections ordered by line of defence: 1st-line leads with the whose-court section (comfortable, `WhoseCourtIndicator` cards); 2nd/3rd-line leads with portfolio posture (dense, `VerdictChip` per use-case `lifecycle_state`). No compliance-% headline (`INV-52`); posture links to `/audit` and never restates coverage (`DF6-9`). "Register a use case" nudge (non-interactive, `A2`); "Register a system" `SodAction`-absent for non-`system_owner`. System drill-in: system-coverage panel (F6 ALTER) plus a use-case list carrying `VerdictChip` (state) and compact `TierBadge`. Icons: `layout-dashboard`, `box`.

**F3 assess — `use-cases/[id]` — both, density by role.** Tier-scoped section template; compact `TierBadge` in the surface header linking to the basis. Items each carry a `ProvenanceBadge`; `AI_SUGGESTED` dashed with the confirm-or-amend gate before authoring fields open (`PAT-8`); `USER_AMENDED` carries the deviation hue. Author controls `SodAction`-visible (`FE-8`). Four `assessment_status` states via `VerdictChip` (DRAFT/NEEDS_REFRESH author-open, IN_REVIEW/APPROVED locked). Feeder-surfaced items read-only (`INV-16`); evidence refs manifest-only (`INV-22`); 412/409 via the two banners (`FE-6`). Reviewer/authoriser/auditor read-only; admin empty-state. Icon: `clipboard-check`.

**F4 assure — `use-cases/[id]` ext, `review-queue` — assurance, dense.** `review-queue`: compact `QueueRow`, each with `WhoseCourtIndicator`, submitter attribution, `VerdictChip` state, compact `TierBadge`; scan-optimised. Assurance acts (review, classification sign-off, authorise/ATO, reopen) all `SodAction`-visible: barred act absent, transient disabled-with-reason. ATO terminal reads `live_state`, never row-existence (`INV-32`). **Classification sign-off (`D-9`)** flips `classification_status` `PENDING_REVIEW → APPROVED`, shown on `VerdictChip` (its own channel), and stamps `use_case.eu_tier`; at that point `TierBadge` transitions from the pre-stamp resolution state (`UNCLASSIFIED`/`REQUIRES_CONTEXT`, `--verdict-*` tone) to the authoritative magnitude tier (`--tier-*`). No `classification_status` member is ever rendered by `TierBadge`; no tier member by `VerdictChip` (B-3 fix). Icons: `inbox`, `list-checks`.

**F5 evidence — `evidence`, `use-cases/[id]` ext — assurance, auditor-read, dense.** Two distinct shapes, never conflated (N-2):
- **Repository list / detail** (`EvidenceTable`): columns `title`, `sha256` (mono), `content_type`, `size`, `link_count`, `uploaded_by_user_id` (bare UUID in mono, no name resolution, `DF5-11`). Download via callback to the hardened `GET /evidence/{id}` (`INV-40`/`INV-22`); no inline bytes, no URL in the DOM.
- **Per-item manifest** (`ItemEvidenceRead` on the assess surface): `{evidence_id, title, sha256, content_type, size_bytes}` only, no `link_count`, no uploader (`DF5-8`).

Per-item linking is disposition-gated: linking to an `AI_SUGGESTED` item is blocked, and the link control renders **disabled-with-reason, not absent**, because it is a transient disposition block that confirm/amend clears, not an `FE-8` structural SoD bar (`DF5-5`/`INV-20`/`D-20`) (N-1 fix). Mono face carries digests and ids. Icon: `paperclip`.

**F6 auditpack — `audit`, ext — assurance, auditor read-only, export, the document face.** `/audit` home: tenant-wide `CoverageMatrix`; `include_unapproved` toggle default off, wrapping the non-audit-grade matrix in `AuditGradeDivider` when on (`INV-51`/`INV-52`); framework picker plus a deliberate "Generate framework audit pack" action (`INV-53`). **Coverage verdicts** (computed string set, `VV-4`) via `VerdictChip`: `SATISFIED`→positive, `PARTIAL`→attention, `OPEN`→neutral, `UNADDRESSED`→neutral. **`downgraded_unsubstantiated`** carries the attention tone plus a distinct marker (hatched fill or "downgraded" tag, `OPEN-V6`) so it never reads as a native `PARTIAL` (`INV-51`, never merged). `NotAnObligationSetBanner` prominent, gaps-shown-not-failures, no compliance-% (`INV-52`). **Signature:** `AuditPackView` and `AtoDocumentView` render in the reserved serif document face (IBM Plex Serif, `D-43`), the regulator-read take-away; `AtoDocumentView` shows the drift caveat first, unconditionally (`DF6-5`/`INV-44`); `content_hash` and `generated_at` footer in mono. Export hooks deliberate-action only (`INV-53`). Icons: `file-text` (pack), `file-check` (ATO).

## §5 · Design invariants for this track (proposed INV-64+, presentational)

1. **INV-64 · CONVENTION ·** `eu_ai_act_tier` renders only via `TierBadge`. The four magnitude tiers use the dedicated `--tier-*` channel; the two resolution states use `--verdict-*` (tone follows meaning-class). No tier member renders via `VerdictChip`, and no other channel reuses `--tier-*`. → `D-7`, `INV-12`, `FE-16` (as amended by `D-48`)
2. **INV-65 · CONVENTION ·** the exported document face (`AuditPackView`, `AtoDocumentView`) renders in the reserved serif family; no other tenant surface uses serif. → `D-43`, `FE-17`

INV-66 (adoption/assurance as composition) is dropped: it restated `D-45`/`FE-18` (N-5). `INV-54` (presentational boundary), `INV-51`/`INV-52` (coverage caveats and downgraded-distinct), `INV-22`/`INV-40` (evidence manifest only), `INV-44` (ATO drift), `INV-53` (deliberate export fetch), and `DF6-9` (single-home posture-vs-coverage) govern V1 and are cited, not restated.

## §6 · Review disposition

| Finding | Fold |
|---|---|
| B-1 | Resolved by V1DD-4: dedicated `--tier-*` channel; `--sev-*` reuse withdrawn; `FE-16` amended via `D-48` with rejected alternatives |
| B-2 | Resolved: §2 mapping is now coherent. The four magnitude tiers on `--tier-*`; the two resolution states on `--verdict-*` because they are verdict-class. No patchwork |
| B-3 | Resolved: `VerdictChip` renders `classification_status`; `TierBadge` renders tier (resolution state pre-stamp, authoritative post-stamp). F4 sentence reworked; no cross-channel borrow |
| N-1 | Accepted: F5 link control disabled-with-reason, not absent (`DF5-5`, transient disposition block) |
| N-2 | Accepted: F5 shapes split (per-item `ItemEvidenceRead` vs repository-list `EvidenceTable`) |
| N-3 | Accepted: `VerdictChip` ALTER done-check updates `verdict-chip.test.tsx` 34→28; no dead branch |
| N-4 | Accepted: status reworded to "resolves the deferred per-surface icon assignments under `OPEN-V2`"; the set was closed at V0 |
| N-5 | Accepted: INV-66 dropped; cite `D-45`/`FE-18`. INV-65 retained |
| N-6 | Accepted: cites split, `INV-52` for compliance-%, `DF6-9` for never-restates-coverage |
| SV-1 | Folded: INV-64's severity-disambiguation clause dropped (no referent; severity is integer scores, no categorical chip) |
| SV-2 | Bound to the coding agent (VV-3): read live `verdict-chip.tsx` before migration |
| SV-3 | Folded: coverage tones map on the computed string set, not the 3-member `coverage_status` enum; `verdict` stays plain `str` (VV-4) |
| Clean items | Carried unchanged: tier value list, F3 status treatment, F4 ATO live-state read, F6 coverage/serif/ATO-drift/deliberate-export, §3 density modes, `INV-54` boundary |

## Appendix A · Open decisions

| ID | Decision | Disposition |
|---|---|---|
| OPEN-V2 | Deferred per-surface icon assignments | Proposed inline in §4 (Lucide): `clipboard-plus`, `layout-dashboard`, `box`, `clipboard-check`, `inbox`, `list-checks`, `paperclip`, `file-text`, `file-check`, `ban` (PROHIBITED only). No shield, no emoji. The set itself was closed at V0 |
| OPEN-V5 | `--brand` vs `--verdict-positive` isoluminance, `--brand`-token co-occurrence | Usability-check work item (VV-7); split or nudge only on observed confusion |
| OPEN-V6 | `downgraded_unsubstantiated` distinct marker form (hatched fill vs tag) | Pick at implementation against `axe`/legibility; both satisfy `INV-51` |
| OPEN-V7 (new) | `--tier-*` and a future categorical severity chip (`AIIA-8` heat view) co-occurrence on F3 | The navy `--tier-*` family is chosen to stay distinct from a warm severity scale; confirm at the heat-view track, not now |

## Appendix B · Source-verification register

| ID | Item | Action |
|---|---|---|
| VV-1 | V0 atom inventory at HEAD | Verify components exist before composing |
| VV-3 / SV-2 | `VerdictChip` current `eu_ai_act_tier` branch | Read live; make the removed branch and 34→28 delta exact |
| VV-4 / SV-3 | Coverage computed-verdict key set | Confirm before the F6 tone mapping freezes; `verdict` stays plain `str` |
| VV-6 | IBM Plex Serif + Lucide installed | Confirm before the document face and icons land |
| VV-7 | `OPEN-V5` luminance and co-occurrence | Compute and eyeball on real F2/F4 surfaces; record |
| VV-8 | `--tier-*` contrast | Extend the gate; all new pairings clear AA before freeze |