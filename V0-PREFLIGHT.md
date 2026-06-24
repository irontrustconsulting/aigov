# V0-PREFLIGHT.md — UI-V0-VISUAL-FOUNDATION

Run date: 2026-06-24. All checks executed against HEAD and live dev DB before any WI-1+ code.

---

## V-1 · Built surface set at HEAD

```
apps/tenant/app/
  api/            dashboard/        evidence/
  review-queue/   systems/          use-cases/
  audit/          globals.css       layout.tsx
  page.tsx        providers.tsx

apps/operator/app/(console)/
  dashboard/      operators/        provisioning/

packages/  api-client/  eslint-plugin-irontrust/  tokens/  ui/
```

**Result: PASS.** 9 tenant surfaces (systems/new, dashboard, systems/[id], use-cases/[id], review-queue, evidence, audit are present as dirs; systems contains `new` and `[id]`), 2 operator console routes (operators, provisioning), nav shell (layout.tsx), packages/ui and packages/tokens present. Matches design doc §0 / SV-2.

---

## V-2 · Provenance enum (`provenance_confidence`)

```sql
SELECT enumlabel FROM pg_enum
WHERE enumtypid = 'provenance_confidence'::regtype
ORDER BY enumsortorder;
```

```
AI_SUGGESTED
CATALOGUE_CURATED
USER_CONFIRMED
USER_AMENDED
(4 rows)
```

**Result: PASS. Exactly 4 members. No `USER_PROVIDED`.** Confirms PAT-8; the stale `DATA-MODEL §5` note (which mentioned `USER_PROVIDED`) must be corrected in WI-6 — see canonical-update item.

---

## V-3 · `packages/tokens` scaffold

`packages/tokens/src/primitives.css` contains an `@theme { }` block wiring CSS custom properties into Tailwind v4. `package.json` exports: `./primitives.css`, `./skin-tenant.css`, `./skin-operator.css`. WI-1 layers additively on this structure (rename + extend, not a second wiring system).

**Result: PASS.**

---

## V-4 · `eslint-plugin-irontrust` no-literal-token-value rule

```
pnpm --filter @irontrust/eslint-plugin-irontrust test
9 tests pass, 0 fail
```

`no-literal-token-value` rule is active and flags raw hex/px values used as className or inline style. `no-raw-live-state-query` also passes. WI-4 component edits must produce zero new violations.

**Result: PASS.**

---

## V-5 · Status enum live members → verdict-tone mapping

### Live members (34 total)

| Enum | Members |
|---|---|
| `assessment_status` | APPROVED, DRAFT, IN_REVIEW, NEEDS_REFRESH |
| `lifecycle_state` | AUTHORISED, DEPLOYED, HALTED_PROHIBITED, HELD, INTAKE, PENDING_AUTHORISATION, PRODUCT_CHECK, REQUESTED, RETIRED, TREATMENT_PENDING, UNDER_ASSESSMENT, VENDOR_CHECK |
| `eu_ai_act_tier` | HIGH, LIMITED, MINIMAL, PROHIBITED, REQUIRES_CONTEXT, UNCLASSIFIED |
| `approval_status` | APPROVED, EXPIRED, NOT_STARTED, REJECTED, UNDER_REVIEW |
| `coverage_status` | OPEN, PARTIAL, SATISFIED |
| `classification_status` | APPROVED, CHANGES_REQUESTED, NEEDS_REFRESH, PENDING_REVIEW |

### Verdict-tone mapping (design doc §2.2 + implementation extensions)

| Tone | Members |
|---|---|
| neutral | `DRAFT`, `REQUESTED`, `INTAKE`, coverage `OPEN`, approval `NOT_STARTED`, tier `UNCLASSIFIED`, tier `LIMITED` *, tier `MINIMAL` * |
| progress | `IN_REVIEW`, `UNDER_ASSESSMENT`, `VENDOR_CHECK`, `PRODUCT_CHECK`, `PENDING_AUTHORISATION`, `TREATMENT_PENDING`, classification `PENDING_REVIEW`, approval `UNDER_REVIEW` |
| positive | assessment `APPROVED`, `AUTHORISED`, `DEPLOYED`, coverage `SATISFIED`, approval `APPROVED`, classification `APPROVED` |
| attention | `NEEDS_REFRESH`, `CHANGES_REQUESTED`, `HELD`, coverage `PARTIAL`, tier `REQUIRES_CONTEXT`, tier `HIGH` * |
| halt | `HALTED_PROHIBITED`, tier `PROHIBITED`, approval `REJECTED` |
| terminal | `RETIRED`, approval `EXPIRED` |

> \* **ESCALATION NOTE — eu_ai_act_tier gap:** The design doc §2.2 mapping explicitly covers `UNCLASSIFIED` (neutral), `REQUIRES_CONTEXT` (attention), and `PROHIBITED` (halt) but does not name `HIGH`, `LIMITED`, or `MINIMAL`. These 3 members exist in the live DB.
>
> Applied implementation tones: `HIGH` → attention (heightened regulatory scrutiny), `LIMITED` → neutral (limited-risk systems, exemptions apply), `MINIMAL` → neutral (below-threshold risk). Rationale matches the EU AI Act risk hierarchy. **Herbert to review and confirm or redirect before V1 ships.**

**Result: PASS with escalation note for eu_ai_act_tier HIGH/LIMITED/MINIMAL.** Mapping is exhaustive (34/34 covered); no member falls through; no invented member.

---

## V-6 · IBM Plex + icon set licensing

- `@fontsource/ibm-plex-sans` 5.2.8 — OFL ✓ self-hostable ✓ latin subset ✓
- `@fontsource/ibm-plex-mono` 5.2.7 — OFL ✓
- `@fontsource/ibm-plex-serif` 5.2.7 — OFL ✓
- `lucide-react` 1.21.0 — ISC ✓ outline-only ✓ self-bundled ✓

No runtime CDN dependency for any of the above. All compatible with CSP.

**Result: PASS.**

---

## V-7 · WCAG 2.1 contrast computation (design doc §4 pairings)

Computed via the WCAG relative-luminance formula against the V-7-cleared hex values from design doc §2.1/§2.2 (B-1, N-1, N-3 review fixes already applied).

| Pairing | FG | BG | Type | Ratio | Threshold | Result |
|---|---|---|---|---|---|---|
| `--ink` on `--paper` | #1B1D1E | #F4F4F1 | text | 15.36 | 4.5 | **PASS** |
| `--ink` on `--surface` | #1B1D1E | #FFFFFF | text | 16.92 | 4.5 | **PASS** |
| `--ink` on `--surface-sunken` | #1B1D1E | #FAFAF8 | text | 16.19 | 4.5 | **PASS** |
| `--ink-secondary` on `--paper` | #4A4F55 | #F4F4F1 | text | 7.50 | 4.5 | **PASS** |
| `--ink-secondary` on `--surface` | #4A4F55 | #FFFFFF | text | 8.27 | 4.5 | **PASS** |
| `--ink-muted` on `--paper` | #696E75 | #F4F4F1 | text | 4.66 | 4.5 | **PASS** (B-1 fix: #787E85→#696E75) |
| `--ink-muted` on `--surface` | #696E75 | #FFFFFF | text | 5.14 | 4.5 | **PASS** |
| `--ink-muted` on `--surface-sunken` | #696E75 | #FAFAF8 | text | 4.92 | 4.5 | **PASS** |
| `--brand` on `--paper` | #1E4651 | #F4F4F1 | text | 9.30 | 4.5 | **PASS** |
| `--brand` on `--surface` | #1E4651 | #FFFFFF | text | 10.24 | 4.5 | **PASS** |
| `--brand-strong` on `--brand-tint` (progress verdict) | #123338 | #E7F0F0 | text | 11.64 | 4.5 | **PASS** (N-3 fix) |
| `--verdict-positive-text` on fill | #2F5D4A | #E7F0EC | text | 6.49 | 4.5 | **PASS** |
| `--verdict-halt-text` on fill | #FFFFFF | #872B22 | text | 8.75 | 4.5 | **PASS** |
| `--verdict-attention` on `--surface` | #8A6A2E | #FFFFFF | graphical | 5.02 | 3.0 | **PASS** |
| `--sev-high-ink` on `--sev-high-bg` | #A84B36 | #F8ECE8 | text | 4.87 | 4.5 | **PASS** (N-1 fix: #B0503A→#A84B36) |
| `--sev-critical-ink` on `--sev-critical-bg` | #FFFFFF | #872B22 | text | 8.75 | 4.5 | **PASS** |
| `--prov-ai-suggested` on `--surface` | #6E5A8E | #FFFFFF | graphical | 5.97 | 3.0 | **PASS** |
| `--prov-catalogue-curated` on `--surface` | #2E4257 | #FFFFFF | graphical | 10.33 | 3.0 | **PASS** |
| `--prov-user-confirmed` on `--surface` | #5A6068 | #FFFFFF | graphical | 6.35 | 3.0 | **PASS** |
| `--prov-user-amended` on `--surface` | #9A5A48 | #FFFFFF | graphical | 5.34 | 3.0 | **PASS** |

All 20 pairings clear threshold. **No freeze blocker. Proceed to WI-1.**

---

## Keyboard pass note (WI-5 record)

Completed during WI-5 after component treatments applied.

- **ProvenanceBadge** — non-interactive, no keyboard focus needed ✓
- **VerdictChip** — non-interactive display chip, no keyboard focus needed ✓
- **SodAction** — transient-disabled Button accessible via Tab; `aria-describedby` wired to reason note; `title` set ✓
- **WhoseCourt** — non-interactive pill indicator, no keyboard focus needed ✓
- **StaleLock (412)** — Reload button reachable via Tab, activates on Enter/Space ✓
- **BadFromState (409)** — no interactive affordance, no keyboard focus needed ✓
- **RequirePermission** — non-interactive gate, child reachable when present ✓
- **StructuredInputSet** — full keyboard operability confirmed by existing test suite ✓
- **prefers-reduced-motion** — `@media (prefers-reduced-motion: reduce)` block disables transitions ✓

---

## Summary

| Check | Result |
|---|---|
| V-1 Surface set | PASS |
| V-2 Provenance enum | PASS — 4 members, no USER_PROVIDED |
| V-3 Tokens scaffold | PASS |
| V-4 ESLint rule | PASS |
| V-5 Status enums | PASS with escalation note (eu_ai_act_tier HIGH/LIMITED/MINIMAL) |
| V-6 IBM Plex + Lucide | PASS |
| V-7 WCAG contrast | PASS — all 20 pairings clear threshold |

**Pre-flight complete. WI-1 unblocked.**
