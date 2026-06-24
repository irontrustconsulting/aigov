# UI-V0-VISUAL-FOUNDATION — Final Design Doc

**Status:** FINAL, review folded in · **Track:** visual layer (the `FE-3` `[TBD]` gap) · **Plane:** both, via one shared core · **Delta:** presentational only, 0 backend / 0 schema / 0 route / 0 enum / 0 contract · **Builds on:** `FE-1`, `FE-3`, `D-22` (additive) · **Feeds:** UI-V1-TENANT-SKIN, UI-V2-OPERATOR-SKIN

This is the final design doc. It supersedes the draft and resolves every review finding (disposition table at the end). Behaviour is fixed by the existing `FE-*` contracts; this track gives them visual form and nothing else.

---

## §0 · Pre-flight verify checklist (binding at implementation)

| ID | Check | Why |
|---|---|---|
| V-1 | Confirm built surface set and shared packages at HEAD: `apps/tenant/{systems/new,dashboard,systems/[id],use-cases/[id],review-queue,evidence,audit}`, `apps/operator/(console)/{provisioning,operators}` + nav shell, `packages/ui`, `packages/tokens` | SV-2; STATE headers "through F6" while F7/F8 shipped |
| V-2 | Read live `pg_enum` for the provenance type. Confirm 4-value `{AI_SUGGESTED, CATALOGUE_CURATED, USER_CONFIRMED, USER_AMENDED}` per `PAT-8` and `app/schemas/assessment.py`. Reconcile against the stale `INDEX` / `DATA-MODEL §5` 5-value `USER_PROVIDED` note. If confirmed 4-value, the canonical-update item flags that note for correction | SV-1; `PAT-8` vs the open-note contradict; `D-21` code wins, but the live read settles it |
| V-3 | Confirm `packages/tokens` already surfaces CSS custom properties mapped into the Tailwind theme (`FE-3`) | New tokens must layer additively, never replace the wiring |
| V-4 | Confirm `eslint-plugin-irontrust` no-literal-token-value rule scope | Restyle must stay token-only; no magic values reintroduced |
| V-5 | Read live `pg_enum` for `assessment_status`, `lifecycle_state`, `classification_status`, `coverage_status`, `approval_status`, `eu_ai_act_tier`. Confirm the §2.2 member-to-tone mapping is exhaustive; no member falls through, no invented member | SV-5; `assessment_status` (4) is distinct from `lifecycle_state` (12); one token set cannot serve both |
| V-6 | Confirm IBM Plex (OFL) and the chosen outline icon set are self-hostable, CSP-clean, and **permissively licensed (MIT / ISC / Apache-2.0 / OFL)** | No runtime third-party font/icon CDN (enterprise + EU buyers, CSP); broadened gate per S-3 |
| V-7 | Compute every intended foreground/background pairing in §4 against a WCAG 2.1 contrast formula. Freeze is blocked until all text pairings clear 4.5:1 (large 3:1) and all meaningful-graphical pairings clear 3:1 | SV-7; operationalises §5 invariant 9, the doc's strongest claim |

## §1 · Resolved decisions

| ID | Decision |
|---|---|
| VDD-1 | Foundation-first: V0 core → V1 tenant skin → V2 operator skin |
| VDD-2 | Neutral-evidentiary; chromatic colour reserved for semantic channels only |
| VDD-3 | Open-source type: IBM Plex Sans (UI), Mono (identifiers), Serif (exported document face) |
| VDD-4 | Light-first; token layer structured so dark lands later as a skin, not a rework |
| VDD-5 | Two skins = tenant vs operator; adoption/assurance is density within the tenant skin |
| VDD-6 | Brand accent: deep petrol-slate `#1E4651` |

## §2 · Token architecture (proposed FE-14)

Three layers, no magic values, extends `FE-3`: **primitive** (raw ramps) then **semantic** (named by meaning: `--prov-*`, `--verdict-*`, `--court-*`, `--sev-*`) then **component** (consumed by `packages/ui`). Components reference semantic tokens, never primitives or literals (lint, `V-4`). Light-first; every token has a reserved dark slot left empty this track (`VDD-4`). Every hex below is provisional until cleared by `V-7`.

### 2.1 Primitive: neutral ramp + single brand accent

| Token | Value | Use |
|---|---|---|
| `--paper` | `#F4F4F1` | page |
| `--surface` | `#FFFFFF` | cards |
| `--surface-sunken` | `#FAFAF8` | table header strips |
| `--hairline` | `#E5E5E0` | default 0.5px border |
| `--hairline-strong` | `#D3D4CE` | emphasis border |
| `--ink-muted` | `#696E75` | captions, hints, neutral verdict (darkened from `#787E85`, B-1: clears 4.66 / 5.14 / 4.92 on surface / paper / sunken) |
| `--ink-secondary` | `#4A4F55` | secondary text |
| `--ink` | `#1B1D1E` | primary text |
| `--brand` | `#1E4651` | primary action, focus, brand mark, your-court |
| `--brand-strong` | `#123338` | text on brand-tint, operator rail |
| `--brand-tint` | `#E7F0F0` | brand fills, progress verdict |

### 2.2 Semantic channels (proposed FE-15, FE-16)

Four channels, each a fixed AA treatment. **Orthogonality rule (FE-16):** a channel never borrows another channel's visual slot. Where the restrained palette forces a shared hue (`--brand` in both your-court and progress; `#8A6A2E` in both medium-severity and attention-verdict), the **component form** disambiguates, not the hue. If V1 usability testing shows confusion, split the hue then (a one-token edit), not speculatively.

**Provenance** (the `ProvenanceConfidence` disposition of an asserted value; `FE-5`, `INV-13`, `PAT-8`). The hue lives on the dot or the badge border only; the **label is always `--ink`**, so a provenance hue needs only the 3:1 graphical floor, never 4.5:1 text. 4-value, mapped 1:1 to the live enum (`V-2`):

| Enum member | Token | Treatment |
|---|---|---|
| `AI_SUGGESTED` | `--prov-ai-suggested` `#6E5A8E` | **dashed** badge border; the only member carrying an action (confirm-or-amend gate before authoring opens, `PAT-8`) |
| `CATALOGUE_CURATED` | `--prov-catalogue-curated` `#2E4257` | solid dot; curated catalogue source, exempt from the ladder |
| `USER_CONFIRMED` | `--prov-user-confirmed` `#5A6068` | solid dot; a system default the user accepted |
| `USER_AMENDED` | `--prov-user-amended` `#9A5A48` | solid dot; a system default the user changed (the tracked deviation, `D-1`); distinct hue so an auditor spots overrides at a glance |

There is no fifth provenance value and no `USER_PROVIDED` (`PAT-8`, settled at `V-2`). Register-derived facts carry one of the four; exact member is confirmed against `create_aiia` at `V-2`.

**Verdict tones** (`FE-7`; the LiveStateChip family). Colour is rationed to **six meaning-class tones**, not one colour per enum member; the chip label carries the specific member, the tone carries its meaning-class. One tone family serves `assessment_status`, `lifecycle_state`, `classification_status`, `coverage_status`, and `approval_status`. Mapping confirmed exhaustive at `V-5`:

| Tone | Token | Treatment | Members (provisional, exhaustive-checked at V-5) |
|---|---|---|---|
| neutral | `--verdict-neutral` `#696E75` | grey outline | `DRAFT`, `REQUESTED`, `INTAKE`, coverage `OPEN`, approval `NOT_STARTED`, tier `UNCLASSIFIED` |
| progress | `--verdict-progress` (fill `#E7F0F0`, **text `#123338` = 11.6:1**, N-3) | brand-tint, in motion | `IN_REVIEW`, `UNDER_ASSESSMENT`, `VENDOR_CHECK`, `PRODUCT_CHECK`, `PENDING_AUTHORISATION`, `TREATMENT_PENDING`, classification `PENDING_REVIEW`, approval `UNDER_REVIEW` |
| positive | `--verdict-positive` (text `#2F5D4A` on `#E7F0EC`) | the one earned green | assessment `APPROVED`, `AUTHORISED`, coverage `SATISFIED`, approval `APPROVED`, classification `APPROVED`, `DEPLOYED` |
| attention | `--verdict-attention` `#8A6A2E` | amber outline | `NEEDS_REFRESH`, `CHANGES_REQUESTED`, `HELD`, coverage `PARTIAL`, tier `REQUIRES_CONTEXT` |
| halt | `--verdict-halt` (white on `#872B22`) | oxblood solid | `HALTED_PROHIBITED`, tier `PROHIBITED`, approval `REJECTED` (prohibition is supreme, `D-7`) |
| terminal | `--verdict-terminal` `#696E75` struck | muted, struck-through | `RETIRED`, `EXPIRED` |

**Whose-court** (`FE-11`): `--court-yours` = `--brand` 3px left edge-bar (radius 0) plus `--brand-tint` pill; `--court-theirs` = neutral pill. Read off `blocking.responsible_party`, presentational highlight only.

**Severity** (rationed; saturation only at the top): `--sev-low` = `--ink-muted`; `--sev-medium-ink` `#8A6A2E`; `--sev-high-ink` **`#A84B36`** on `--sev-high-bg` `#F8ECE8` (darkened from `#B0503A`, N-1: the High label renders as text on tint, so 4.5:1 applies; `#A84B36` clears 4.87:1); `--sev-critical-ink` white on `--sev-critical-bg` `#872B22`. `--sev-medium-ink` shares the exact value of `--verdict-attention`; two tokens, disambiguated by component form (severity tag vs verdict chip), kept separate so the later split stays a one-token edit.

### 2.3 Type (proposed FE-17)

`--font-sans` IBM Plex Sans, `--font-mono` IBM Plex Mono, `--font-serif` IBM Plex Serif; self-hosted OFL, subset, no runtime CDN (`V-6`). Mono carries identifiers, `lock_version`, and SHA-256 digests. Serif is reserved for the exported document face (ATO basis, audit pack). Weights 400 / 500 / 600 only. Sizes are integers (N-6: half-pixel sizes subpixel-render unevenly on 1x):

| Role | px / weight / line-height |
|---|---|
| display | 26 / 600 / 1.2 |
| h1 | 22 / 600 / 1.25 |
| h2 | 20 / 600 / 1.3 |
| h3 | 16 / 600 / 1.4 |
| body (tenant) | 15 / 400 / 1.55 |
| body (operator) | 14 / 400 / 1.5 |
| body-strong | as body, 500 |
| caption | 13 / 400 / 1.45 |
| micro / mono-id | 12 / 400 |

No text token below 12px.

### 2.4 Spacing, radius, elevation, motion

- **Spacing** (4px base): 2, 4, 8, 12, 16, 20, 24, 32, 40, 48. Tenant comfortable: 16 to 24 rhythm. Operator compact: 6 to 12.
- **Radius:** `--r-sm` 4 (badges, chips, inputs), `--r-md` 6 (buttons), `--r-lg` 8 (cards), `0` mandatory on single-sided border accents. No pills except the deliberate your-court pill at `--r-sm`.
- **Elevation:** hairline borders do the work. `e1` = border only; `e2` (menus/overlays) subtle `0 1px 2px rgba(0,0,0,.06)` plus hairline; focus ring `0 0 0 2px --brand-tint, 0 0 0 .5px --brand`. No decorative shadow, glow, or gradient.
- **Motion (proposed FE-19):** 120 / 180 / 240ms, standard easing; honours `prefers-reduced-motion`; no celebratory or completion motion (anti-cliché).

### 2.5 Iconography

Single outline icon set, permissively licensed (MIT / ISC / Apache-2.0 / OFL), self-hosted (`V-6`). Outline only, no filled variants, no emoji.

## §3 · Two-skin model (proposed FE-18)

Both skins consume the same primitive and semantic tokens (`FE-3`, `VDD-5`); they differ only in density defaults and chrome.

| | Tenant skin | Operator skin |
|---|---|---|
| Body | 15 | 14 |
| Spacing rhythm | 16 to 24 | 6 to 12 |
| Card padding | 13 to 15px | tabular rows, 6 to 8px |
| Posture | comfortable; adoption and assurance are density modes within it | compact, tabular-first, mono identifiers prominent |
| Chrome | tenant | plane-distinct rail in `--brand-strong` so an operator never mistakes the plane (`INV-1`) |
| Warmth | adoption face: reasoning-first cards, generous leading | none; operational vocabulary (`PLATFORM-UX §2`) |

Adoption vs assurance is spacing and component-default driven inside the tenant skin, not a third theme.

## §4 · Component visual spec (`packages/ui`, behaviour unchanged) — present vs ALTER

Every intended foreground/background pairing named here is the input set to the `V-7` contrast computation.

| Component | State | Visual treatment | Behaviour locus (unchanged) |
|---|---|---|---|
| ProvenanceBadge | present → ALTER | dot (or dashed border for AI-suggested) in the member hue, label in `--ink`; 4 members | server-derived, client never authors (`INV-13`) |
| PrefillWithBasis | present → ALTER | value, badge, basis line, Confirm (ghost), Amend (structured pick) | override structured, deviation tracked server-side (`FE-5`, `D-1`) |
| SodAction | present → ALTER | structural bar renders nothing; transient renders disabled plus reason caption | server is authz authority (`FE-8`, `INV-28`, `D-4`, `D-24`) |
| WhoseCourt | present → ALTER | brand edge-bar plus pill; yours vs theirs | direct `blocking.responsible_party` read (`FE-11`) |
| StaleLock 412 | present → ALTER | amber edge-bar plus Reload action | invalidate, refetch, re-present (`FE-6`) |
| BadFromState 409 | present → ALTER | ink edge-bar, no retry affordance | action void (`FE-6`) |
| LiveStateChip | present → ALTER | verdict-tone chip; tone from the §2.2 mapping, label = enum member | `staleTime: 0`, refetch on mutation (`FE-7`, `INV-25`, `INV-32`) |
| StructuredInputSet | present → ALTER | select-first ladder, prefilled-confirm to contained free-text | `FE-4`, `UX-2`, `UX-3` |
| Tables / QueueRow / CoverageCell / ExportView | present → ALTER | tenant-comfortable and operator-compact variants | read-only shapes unchanged |
| RequirePermission (operator) | present → ALTER | absent when permission absent; nav distinguishes absent from unbuilt-visible-disabled | `require_permission` is authz authority (`FE-13`, `DF7-2`) |

`packages/tokens`: present scaffold (CSS custom properties to Tailwind, `FE-3`) → ALTER to populate primitive, semantic, and component layers. No new package.

## §5 · Design invariants for this track (proposed INV-54+, presentational-only boundary)

1. No backend, schema, route, enum, or contract delta; visual layer only. → `D-22`
2. Provenance stays server-derived; no component authors a `provenance` value. → `INV-13`
3. SoD and permission enforcement stay server-side; UI absence is non-disclosure, never enforcement. → `FE-8`, `FE-13`, `INV-28`, `INV-8`, `D-24`
4. Live-state refetch discipline untouched; no chip renders a cached verdict as settled. → `FE-7`, `INV-25`, `INV-32`
5. No token in the browser; BFF custody preserved. → `INV-50`, `FE-2`
6. `tenant_id` never client-supplied. → `INV-3`
7. Plane chrome never bleeds; the operator rail is the visual correlate of plane separation. → `INV-1`
8. Evidence never inline-rendered; the visual layer introduces no inline byte path. → `INV-22`
9. Every intended **text** pairing meets WCAG 2.1 AA (4.5:1 normal, 3:1 large) and every **meaningful-graphical** pairing meets 3:1; structural separators (hairlines) are exempt as non-1.4.11 UI-component elements. Verified by `SV-7` before freeze, not asserted. → `FE-3`, `SV-7` (reworded per N-4, hooked to verification per B-2)
10. Components carry no literal colour or spacing values (lint-enforced). → `FE-3`, `V-4`

## §6 · Review disposition (every finding accounted for)

| Finding | Disposition |
|---|---|
| B-1 `--ink-muted` fails AA | Accepted. `#787E85` to `#696E75` (§2.1); cascades to caption, hint, neutral verdict, operator-compact secondary |
| B-2 no verification hook for the contrast claim | Accepted. SV-7 added (Appendix B); V-7 added (§0); invariant 9 now cites SV-7 |
| N-1 `--sev-high` 4.48:1 if text | Accepted, ambiguity resolved: High is a coloured **label** on tint, so it is text; darkened to `#A84B36` (4.87:1) (§2.2) |
| N-2 brand vs approved isoluminant (1.36:1) | Logged, not perturbed: OPEN-V5, V1 usability check; current mitigation is form separation (edge-bar vs chip-on-tint) |
| N-3 progress fill had no foreground | Accepted. `--verdict-progress` text fixed to `#123338` (11.6:1) (§2.2) |
| N-4 invariant 9 "every token pair" false | Accepted. Reworded to intended text and meaningful-graphical pairings; hairlines explicitly exempt (§5.9) |
| N-5 brand-token density | Logged: folded into OPEN-V5 co-occurrence check at V1 |
| N-6 half-pixel type sizes | Accepted. Scale snapped to integers (§2.3) |
| S-1 provenance 4-vs-5 collision | Resolved against canon: 4-value, `USER_PROVIDED` does not exist (`PAT-8` + live schema import); explicit member-to-token mapping (§2.2); stale `INDEX`/`DATA-MODEL §5` note flagged for correction; live read bound at V-2 |
| S-2 `--state-*` vs lifecycle vocabulary | Resolved: `assessment_status` (4) is distinct from `lifecycle_state` (12) per `DATA-MODEL §2`. Replaced the single state set with the `--verdict-*` six-tone family plus an exhaustive member-to-tone mapping; live read bound at V-5 |
| S-3 Lucide is ISC not MIT | Accepted. Licensing gate broadened to permissive (MIT / ISC / Apache-2.0 / OFL) (V-6, §2.5); OPEN-V2 unblocked |
| Clean items | Carried unchanged: SodAction structural-vs-transient; medium/attention shared-hue two-token discipline; 0-radius on single-sided accents; `--prov-ai-suggested` dashed outlier; motion anti-cliché; light-first reserved-dark; BFF/`tenant_id`/plane echoes; present-to-ALTER framing |

## Appendix A · Open decisions

| ID | Decision | Disposition |
|---|---|---|
| OPEN-V1 | Dark skin timing | Deferred (`VDD-4`); token layer reserves dark slots now, skin lands later |
| OPEN-V2 | Outline icon set final pick (Lucide / Phosphor / Tabler-outline) | Unblocked by S-3; agent selects at V0 implementation against the permissive gate unless founder has a preference |
| OPEN-V3 | Whether adoption density mode needs named sub-tokens or is purely spacing-driven | Resolve at V1 against the real adoption surfaces (`systems/new`, `dashboard`) |
| OPEN-V4 | Per-surface visual specifics for F1 to F8 | Just-in-time at V1/V2 per `UX §5` |
| OPEN-V5 | `--brand` vs `--verdict-positive` isoluminance (1.36:1) on a yours-and-approved row, and `--brand`-token co-occurrence (focus ring + primary action + your-court + tint pill) | V1 usability check (N-2, N-5); split or nudge only if testing shows confusion |

## Appendix B · Source-verification register

| ID | Item | Action |
|---|---|---|
| SV-1 | Provenance enum membership and count | Read live `pg_enum`; confirm 4-value, no `USER_PROVIDED`; flag stale note (V-2) |
| SV-2 | Built surface set and shared packages at HEAD | Verify against repo, not STATE (V-1) |
| SV-3 | `packages/tokens` Tailwind / CSS-custom-property wiring | Confirm additive layering (V-3) |
| SV-4 | `eslint-plugin-irontrust` no-literal-token-value scope | Confirm restyle stays token-only (V-4) |
| SV-5 | `assessment_status`, `lifecycle_state`, `classification_status`, `coverage_status`, `approval_status`, `eu_ai_act_tier` membership | Confirm the verdict-tone mapping is exhaustive; no invented member (V-5) |
| SV-6 | IBM Plex and icon-set licensing, self-host, CSP | Confirm permissive (MIT / ISC / Apache-2.0 / OFL), no runtime CDN (V-6) |
| SV-7 | WCAG contrast computation for every §4 intended pairing | Compute before freeze; block on any failure (V-7); the verification hook behind invariant 9 |