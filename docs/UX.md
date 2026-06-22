# UX.md — IronTrust Design Principles

**Location:** `docs/UX.md` — single source, mirrored to project knowledge. Updated rarely (stable spec — the frontend counterpart to `ARCHITECTURE.md`).
**Purpose:** The experience intent for the **tenant product** — the principles every tenant-facing screen is held against, the two faces it serves, and how input and prefill behave. Intent, not implementation.
**Lanes:** *what* to build and why → `REQUIREMENTS.md` / `DOMAIN.md`; *how the experience should behave and feel* → this file; *how it is rendered* (components, design tokens, accessibility, framework) → `FRONTEND.md` (the build-conventions canonical, when it lands). The operator/platform-plane console has its own intent doc → `PLATFORM-UX.md`. **This file is tenant-plane only.**

---

## 1. Principles

Six yardsticks (`UX-1..6`). Any screen can be checked against them; a screen that fails one is wrong, however polished.

**UX-1 · Capture once, orchestrate behind the scenes.** The user provides context in one uninterrupted pass; the system drives the lifecycle from it. A gate surfaces *only* when the user's own action is required, phrased in business terms. *Test: the user never manages the lifecycle, and never meets a gate that doesn't need them.*
↳ refs: D-16; IXN-1..5

**UX-2 · Opinionated, never a blank form.** Every step leads with a confident, prefilled answer and its basis — not an empty field. *Test: no blank where the system could have proposed something.*
↳ refs: D-1; XCUT-1

**UX-3 · Speak business, reveal compliance on demand.** The surface speaks the owner's vocabulary; the EU AI Act / ISO mapping sits one layer down, reachable by reviewers and the audit trail. *Test: a non-expert never has to read regulation to proceed; an expert can always reach it.*
↳ refs: D-1; CLS-2

**UX-4 · Reasoning is first-class.** Because the product sells defensibility, the *why* — why this tier, why this control — is a primary element, not a tooltip afterthought. *Test: every answer the system asserts shows its basis.*
↳ refs: D-1; XCUT-1; CLS-2, CLS-3

**UX-5 · Role-aware surfaces.** The UI reflects the three lines of defence: an owner sees provide/confirm work, a reviewer a queue, an auditor read-only evidence. Separation of duties shows up visually — the visual correlate of the act-SoD rule. *Test: what you see and can do matches your role — no approve button for something you authored.*
↳ refs: DOMAIN §7; D-4; INV-28; WKF-1, WKF-5

**UX-6 · Judgement, not data entry.** The system does the lookup, mapping and drafting; the human is left only with the decisions that need a human. *Test: the user's effort goes on deciding, not transcribing.*
↳ refs: D-3; INV-30; automation boundary (REQUIREMENTS §5)

---

## 2. Audiences & modes — two faces, one spine (tenant plane)

IronTrust serves two tenant audiences with opposite needs, and most platforms fail by forcing both through one compliance UX. We run **two faces on one engine.**

**The adoption face** — for the non-governance user (a product or business owner). They are doing a *familiar action* — adopt this AI tool, onboard this vendor, start this project — not "completing a compliance assessment." Plain language, opinionated prefills, the fewest questions possible, governance invisible. They meet a gate only when their decision is genuinely needed.

**The assurance face** — for the governance roles (reviewer, authoriser, auditor, governance lead). Full assessment depth, shown reasoning, evidence, queues, SoD, audit trail, dashboards. These users *want* the governance surface.

**One capture-once spine** feeds both. The friendly inputs the owner gives *become* the structured assessment the reviewer sees, translated by the background orchestration. Same data, two surfaces.

**Govern through the workflows people already do.** The non-governance user's familiar action silently triggers the governance lifecycle (VDD, classification, gates). We don't make them come to a governance tool; governance is wrapped inside the thing they were already doing.

**Friendliness is coverage.** This is strategic, not cosmetic: if the front door is easy, people use it; if governance is friction, they route around it — that is shadow AI. Coverage is a UX outcome.

**Beyond the two faces: the operator (platform plane) — not a third face.** The two faces above are both tenant-plane: the same capture-once spine rendered for owner and for governance. IronTrust's own staff (operators) are a third audience, but they are **not** a third face — they live on the separate platform plane (INV-1), do not sit on the tenant spine, and have opposite design drivers (expert users, efficiency over friendliness, operational vocabulary, no adoption dynamic). The spine *feeds* them (a tenant-side taxonomy miss becomes an operator curation task, §3) but never shares a surface with them. Their experience intent has its own home, `PLATFORM-UX.md`, governed by the rule that platform functionality is UI-operated (INV-49, D-36). **Plane separation is itself a UX rule:** operator and tenant surfaces never bleed — the visual/interaction correlate of INV-1.

---

## 3. Input model — structured first, prefilled wherever possible

Free text is minimised by design. This is not a stylistic choice — it is the substrate the product stands on: the orchestration engine can only reason over structured values, prefill is only possible against known values, and a structured answer is auditable where a paragraph is not. It is also the friendliness mechanism — choosing from curated options is recognition, not recall.

**Input preference order** (always reach for the highest that fits):

1. **Prefilled and confirmed** — existing knowledge fills it; the user confirms.
2. **Single-select** from a taxonomy.
3. **Multi-select** from a taxonomy.
4. **Constrained structured** — date, number, bounded enum.
5. **Free text** — last resort, and contained.

**Prefill sources, in order of authority:** the catalogue (known vendor/product facts) → the bridge/taxonomy (category → tier) → this tenant's prior assessments → cross-tenant baselines (the moat) **[VERIFY: reconcile against INV-4 / RLS before this stands as a source — must be anonymised/curated baselines, not raw cross-tenant reads]** → AI-suggested, with reasoning shown. Prefills **cascade**: each structured answer narrows and pre-populates the next — capture-once in action.

**Prefill is a default, never a lock.** Every prefill shows its basis and is one click to override; the override is *also* a structured pick (plus an optional justification), and the deviation is tracked. This is the D-1 contract — strong default → shown reasoning → easy override → tracked deviation — applied at the level of a single field.

**The "other / not listed" path is designed, not a dumping ground.** When the taxonomy doesn't cover a case, the user gives the minimum, isn't blocked, and proceeds — and the miss is captured as a flagged signal routed to operators as a curation task. An operator adds it to the catalogue properly, with its mapping, and it becomes a structured option for everyone next time. Misses grow the catalogue — the moat compounds. *(The UX captures the signal now; the operator-side curation tooling is a follow-on build — its intent lives in `PLATFORM-UX.md` §3.)*

**Where free text is irreducible** — an override justification, a truly novel intended purpose — it is allowed, but attached to a structured decision, never floating on its own.

---

## 4. What we mirror, what we fix

**Mirror** — the conventions users now expect, and we adopt: a central AI inventory/registry; a structured intake → classify → assess → review → authorise lifecycle; framework mapping with cross-framework deduplication (one control satisfying several regimes); audit-ready evidence and reporting; portfolio dashboards (risk / readiness); review queues with attribution; and integration into the tools people already use.

**Fix** — the category's well-documented UX failures, which our thesis already attacks:

| The category's weakness | Our answer |
|---|---|
| Steep learning curve; "you need a consultant"; multi-month implementations | Sales-led and baked — no tenant configuration |
| Requires governance maturity; complex for non-experts | Built for the non-governance user first |
| "Checkbox" feel; the customer builds the questionnaires | Opinionated, baked expertise — defaults, not blank forms |
| Resource-heavy, not plug-and-play | Capture-once, orchestrate in the background |

The differentiators *are* the fixes. Measure every surface against both columns: does it adopt the convention, and does it avoid the weakness?

---

## 5. Per-surface intent (fill-as-you-go)

Each surface is designed just-in-time, when it's about to be built, with the object model in front of you. The method is fixed: run the surface through the principles (§1) and the two faces (§2), answering for each — *which audience and face dominate? which principles bite hardest? what is prefilled, and from where? what does each role see?*

The tenant surfaces, as a framework to fill in:

- **Intake / registration wizard** (`UI-F1-INTAKE`) — adoption face dominant, as designed. `UX-1` (capture-once) and `UX-2`/`UX-4` (opinionated default, shown reasoning) bite hardest: one pass — drill-down or "not in catalogue" → structured capture → prefill confirm → use-case create — silently triggers classification; a gate (the context-question sub-surface, the reviewer hand-off) surfaces only when `requires_context` or the answer genuinely needs the owner's decision. Prefilled from the catalogue only (`DF1-4`: the bridge/prior-assessment/cross-tenant rungs of the §3 ladder are not yet wired); every prefilled fact shows its basis and source, override is presentational only pending a write-back path (`DF1-8`). Tier + basis are reasoning-first (`UX-4`) at the resolved-tier and context-outcome screens. Role-aware (`UX-5`): system_owner drives the whole spine; a bare contributor/member meets an empty-state, not a dead control, since capture is system_owner-only; reviewer/authoriser/auditor get an assurance-read message — the wizard has nothing for them to act on. "Whose-court" closes the surface, reading the lifecycle gate vector rather than a dedicated approval-status field.
- **Inventory / dashboard** — both faces; portfolio view; role-aware. *[to design when built]*
- **Review queue** — assurance face; reviewer / authoriser; SoD-aware; attribution. *[to design when built]*
- **Assessment view (AIIA)** (`UI-F3-ASSESS`) — both faces; `UX-5` (SoD-visible: controls absent, not disabled, for barred roles) and `UX-6` (§1.5 spine) bite hardest. Four-way role branch: system_owner (full author mode), contributor (item-author + control-link only; bootstrap/submit/re-evaluate absent), reviewer/authoriser/auditor (assembled AIIA read-only; no author or assure controls), admin (empty-state). Assembled at read time (`assemble_aiia_items`, INV-16) — native and feeder-surfaced items in the tier-scoped section template, each with provenance badge and shown reasoning. `AI_SUGGESTED` items require confirm-or-amend before authoring fields open (PAT-8/D-3). Whose-court from lifecycle only (`FE-11`). Four status states all rendered (INV-31): DRAFT/NEEDS_REFRESH author-open; IN_REVIEW/APPROVED locked with reason. Re-evaluate lever is system_owner-only. Submit sends `If-Match` (FE-6 live — this sprint inverts DF1-5). Evidence refs display as manifest only, no bytes (INV-22). Feeder recs panel read-only (A7 provisional). Evidence linking, coverage panel, and all assurance acts deferred (A2/A3/F4).
- **Evidence / audit pack** — assurance face; auditor read-only; export. *[to design when built]*
- **"Whose-court" status** — both faces; legible state; what is waiting on whom. *[to design when built]*

Operator-console surfaces (provisioning, operator RBAC, catalogue/reference curation, the curation-task inbox) are **not** listed here — they are platform-plane and are framed in `PLATFORM-UX.md`.

---

## 6. Implementation conventions — elsewhere

How these principles are *rendered* — component library, design tokens, typography, spacing, accessibility (WCAG), framework, desktop-first / responsive behaviour — lives in the frontend build-conventions canonical (`FRONTEND.md`, when it lands), **not here**. *(Note: `CLAUDE.md` is now only the thin repo-root pointer into `docs/`; frontend conventions do not live there.)* This file is intent; that is implementation. When a surface is built, it honours this document and follows those conventions.