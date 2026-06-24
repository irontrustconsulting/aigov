# UI-V0-VISUAL-FOUNDATION — Sprint Handoff (execution-only)

**Status:** READY · **Delta:** presentational only, 0 backend / 0 schema / 0 route / 0 enum / 0 contract · **Scope:** `packages/tokens`, `packages/ui`, the two app theme skins · **Rationale:** see the design doc; this file is execution-only.

Work items are dependency-ordered. Each has a done-check tied to a concrete test. Do not start WI-1 before WI-0 passes.

---

## §0 · Pre-flight verification register (binding)

Run all of these and record the results in a `V0-PREFLIGHT.md` note before any code. A WI is blocked until its inputs here are confirmed.

| ID | Action | Pass condition |
|---|---|---|
| V-1 | List built surfaces and shared packages at HEAD | The 9 tenant/operator surfaces, the nav shell, `packages/ui`, and `packages/tokens` all exist as named in the design doc §0 |
| V-2 | `SELECT enumlabel FROM pg_enum` for the provenance type against the dev DB (`docker compose up -d`, `alembic upgrade head`) | Exactly `{AI_SUGGESTED, CATALOGUE_CURATED, USER_CONFIRMED, USER_AMENDED}`. If a 5th label or `USER_PROVIDED` appears, STOP and escalate: the design doc §2.2 mapping changes |
| V-3 | Inspect `packages/tokens` build | It already emits CSS custom properties mapped into the Tailwind theme; new tokens layer on, no rewrite |
| V-4 | Inspect `eslint-plugin-irontrust` | The no-literal-token-value rule is active and will catch a raw hex/px in `packages/ui` |
| V-5 | `pg_enum` for `assessment_status`, `lifecycle_state`, `classification_status`, `coverage_status`, `approval_status`, `eu_ai_act_tier` | Every label maps to exactly one verdict tone in design doc §2.2; record any label with no mapping and escalate |
| V-6 | Confirm IBM Plex (Sans/Mono/Serif) and the chosen outline icon set | All permissive (MIT / ISC / Apache-2.0 / OFL), self-hostable, no runtime third-party CDN |
| V-7 | Compute WCAG ratios for every foreground/background pairing in design doc §4 from the §2 token values | All text pairings clear 4.5:1 (large 3:1); all meaningful-graphical pairings clear 3:1. Any failure blocks freeze |

---

## WI-0 · Pre-flight (blocking)

Execute the §0 register. Produce `V0-PREFLIGHT.md` recording every pass condition with its observed value, including the two raw `pg_enum` dumps and the §4 contrast table.

**Done-check:** `V0-PREFLIGHT.md` exists; every §0 row is green; the provenance dump equals the 4-member set; no §4 contrast pairing is under threshold.

## WI-1 · Token layers in `packages/tokens`

Populate three layers as CSS custom properties mapped into the Tailwind theme (additive to the existing wiring confirmed at V-3): primitive (§2.1), semantic (§2.2 `--prov-*`, `--verdict-*`, `--court-*`, `--sev-*`), component aliases consumed by `packages/ui`. Reserve empty dark slots per token (`VDD-4`). Use the contrast-cleared hex values from WI-0, not the provisional design-doc values if V-7 moved any.

**Done-check:** `packages/tokens` builds; a snapshot test (`packages/tokens/__tests__/tokens.test.ts`) asserts the full token set and values; `eslint-plugin-irontrust` passes with zero literal-value violations introduced.

## WI-2 · Contrast gate test

Add an automated test that reads the token values and computes WCAG ratios for every design-doc §4 intended pairing, failing under threshold. This is the executable form of invariant 9 / SV-7.

**Done-check:** `packages/tokens/__tests__/contrast.test.ts` runs in CI, asserts every text pairing at 4.5:1 (large 3:1) and every meaningful-graphical pairing at 3:1, and fails the build if a future token edit regresses any pairing.

## WI-3 · Two skin themes

Define the tenant and operator theme skins over the one token core (§3): density defaults, card padding, and the operator `--brand-strong` rail. No second token system.

**Done-check:** both skins resolve at build; a visual snapshot per skin (`apps/tenant` and `apps/operator` theme harness) renders the primitive and semantic tokens; the operator rail is present and the tenant chrome is not, in their respective harnesses.

## WI-4 · `packages/ui` component visual treatments

Apply the §4 treatments to each component. Behaviour is unchanged; only presentation moves. Per-component done-checks:

- **ProvenanceBadge** — renders the 4 live enum members; AI-suggested carries the dashed border, label is `--ink`. Done-check: `provenance-badge.test.tsx` asserts a case per member and asserts no branch exists for a 5th/`USER_PROVIDED` value.
- **VerdictChip (LiveStateChip)** — every member of the six §0/V-5 enums resolves to exactly one tone. Done-check: `verdict-chip.test.tsx` iterates the live member lists and asserts no member falls through to a default; label equals the member, tone equals the mapping.
- **SodAction** — structural bar renders nothing; transient renders disabled plus reason. Done-check: `sod-action.test.tsx` asserts `queryByRole('button')` is null for the structural case and asserts a disabled control with a reason string for the transient case.
- **PrefillWithBasis** — value, badge, basis, Confirm, Amend; no `provenance` ever sent. Done-check: `prefill.test.tsx` asserts the request payload on Amend carries no `provenance` field.
- **WhoseCourt** — yours edge-bar plus pill, theirs neutral, off `blocking.responsible_party`. Done-check: `whose-court.test.tsx` asserts the yours treatment only when the mapped role matches a caller role.
- **StaleLock 412 / BadFromState 409** — distinct surfaces; 412 offers Reload, 409 offers no retry. Done-check: `concurrency-surfaces.test.tsx` asserts the two render distinct components with distinct affordances.
- **RequirePermission** — absent when permission absent. Done-check: `require-permission.test.tsx` asserts the child is not in the DOM when the permission key is missing from `GET /platform/me`.
- **Tables / QueueRow / CoverageCell / ExportView** — tenant-comfortable and operator-compact variants. Done-check: snapshot per variant.

**Done-check (WI-4 overall):** every component test above passes; `axe` reports zero violations on each component story.

## WI-5 · Accessibility pass

Automated `axe` plus a manual keyboard pass per primitive: visible focus ring, full keyboard operability, `prefers-reduced-motion` honoured.

**Done-check:** `axe` zero violations across the component suite; a recorded keyboard pass note covering ProvenanceBadge, VerdictChip, SodAction, WhoseCourt, the two concurrency surfaces, RequirePermission, and StructuredInputSet; reduced-motion verified to disable transitions.

## WI-6 · Canonical update (always last)

Volatile-tier and the `FE-n` register only. Append, never renumber a live id, leave the rest of the stable tier untouched.

- **`FRONTEND.md`** (its `FE-n` home, append sanctioned): add `FE-14` (token architecture), `FE-15`/`FE-16` (semantic channels and the orthogonality rule), `FE-17` (type), `FE-18` (two-skin model), `FE-19` (motion). Assign ids above the live `FE-13` ceiling.
- **`INVARIANTS.md`**: append the §5 presentational-boundary invariants above the live `INV-53` ceiling.
- **`DECISIONS.md`**: append a durable decision recording `VDD-1..6` with rationale and the rejected alternatives (combined restyle sprint; branded-chromatic identity; licensed type; 5-value provenance assumption); append the sprint-local `DF-V0-*` for OPEN-V1..V5 and the contrast-gate test.
- **`STATE.md`**: mark `UI-V0-VISUAL-FOUNDATION` shipped (token core, two skins, `packages/ui` treatments); record V1 tenant skin and V2 operator skin as the next visual tracks; update the "Current through" line.
- **`DATA-MODEL.md`**: only if V-2 confirmed the provenance enum at 4-value, correct the stale `DATA-MODEL §5` note (4-value, no `USER_PROVIDED`) and flag the matching `INDEX` open-note for correction. No schema change.

**Done-check:** the five canonicals updated as above; a grep confirms no live `INV-n`/`FE-n`/`D-n` id was renumbered; the stable tier is untouched except the sanctioned `FE-14+` append to `FRONTEND.md`; if V-2 confirmed 4-value, the `DATA-MODEL §5` provenance note now reads 4-value.