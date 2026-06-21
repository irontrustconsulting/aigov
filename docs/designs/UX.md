# UX.md — IronTrust Design Principles

> The experience intent for IronTrust: the principles every screen is held against, the two audiences it serves, and how input and prefill work.
>
> **Lane:** the PRD says *what* to build and why; this file says *how the experience should behave and feel*; `CLAUDE.md` / `docs/FRONTEND.md` say *how it's implemented* (components, design tokens, accessibility). This file carries intent, not implementation.

---

## 1. Principles

Six yardsticks. Any screen can be checked against them; a screen that fails one is wrong, however polished.

**1. Capture once, orchestrate behind the scenes.** The user provides context in one uninterrupted pass; the system drives the lifecycle from it. A gate surfaces *only* when the user's own action is required, phrased in business terms. *Test: the user never manages the lifecycle, and never meets a gate that doesn't need them.* (PRD §4.1.3.)

**2. Opinionated, never a blank form.** Every step leads with a confident, prefilled answer and its basis — not an empty field. *Test: no blank where the system could have proposed something.*

**3. Speak business, reveal compliance on demand.** The surface speaks the owner's vocabulary; the EU AI Act / ISO mapping sits one layer down, reachable by reviewers and the audit trail. *Test: a non-expert never has to read regulation to proceed; an expert can always reach it.*

**4. Reasoning is first-class.** Because the product sells defensibility, the *why* — why this tier, why this control — is a primary element, not a tooltip afterthought. *Test: every answer the system asserts shows its basis.*

**5. Role-aware surfaces.** The UI reflects the three lines of defence (PRD §4.9.1): an owner sees provide/confirm work, a reviewer a queue, an auditor read-only evidence. Separation of duties shows up visually. *Test: what you see and can do matches your role — no approve button for something you authored.*

**6. Judgement, not data entry.** The system does the lookup, mapping and drafting; the human is left only with the decisions that need a human. *Test: the user's effort goes on deciding, not transcribing.*

---

## 2. Audiences & modes — two faces, one spine

IronTrust serves two audiences with opposite needs, and most platforms fail by forcing both through one compliance UX. We run **two faces on one engine.**

**The adoption face** — for the non-governance user (a product or business owner). They are doing a *familiar action* — adopt this AI tool, onboard this vendor, start this project — not "completing a compliance assessment." Plain language, opinionated prefills, the fewest questions possible, governance invisible. They meet a gate only when their decision is genuinely needed.

**The assurance face** — for the governance roles (reviewer, authoriser, auditor, governance lead). Full assessment depth, shown reasoning, evidence, queues, SoD, audit trail, dashboards. These users *want* the governance surface.

**One capture-once spine** feeds both. The friendly inputs the owner gives *become* the structured assessment the reviewer sees, translated by the background orchestration. Same data, two surfaces.

**Govern through the workflows people already do.** The non-governance user's familiar action silently triggers the governance lifecycle (VDD, classification, gates). We don't make them come to a governance tool; governance is wrapped inside the thing they were already doing.

**Friendliness is coverage.** This is strategic, not cosmetic: if the front door is easy, people use it; if governance is friction, they route around it — that is shadow AI. Coverage is a UX outcome.

---

## 3. Input model — structured first, prefilled wherever possible

Free text is minimised by design. This is not a stylistic choice — it is the substrate the product stands on: the orchestration engine can only reason over structured values, prefill is only possible against known values, and a structured answer is auditable where a paragraph is not. It is also the friendliness mechanism — choosing from curated options is recognition, not recall.

**Input preference order** (always reach for the highest that fits):

1. **Prefilled and confirmed** — existing knowledge fills it; the user confirms.
2. **Single-select** from a taxonomy.
3. **Multi-select** from a taxonomy.
4. **Constrained structured** — date, number, bounded enum.
5. **Free text** — last resort, and contained.

**Prefill sources, in order of authority:** the catalogue (known vendor/product facts) → the bridge/taxonomy (category → tier) → this tenant's prior assessments → cross-tenant baselines (the moat) → AI-suggested, with reasoning shown. Prefills **cascade**: each structured answer narrows and pre-populates the next — capture-once in action.

**Prefill is a default, never a lock.** Every prefill shows its basis and is one click to override; the override is *also* a structured pick (plus an optional justification), and the deviation is tracked. This is the PRD §1.5 contract — strong default → shown reasoning → easy override → tracked deviation — applied at the level of a single field.

**The "other / not listed" path is designed, not a dumping ground.** When the taxonomy doesn't cover a case, the user gives the minimum, isn't blocked, and proceeds — and the miss is captured as a flagged signal routed to operators as a curation task. An operator adds it to the catalogue properly, with its mapping, and it becomes a structured option for everyone next time. Misses grow the catalogue — the moat compounds. *(The UX captures the signal now; the operator-side curation tooling is a follow-on build.)*

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

The surfaces, as a framework to fill in:

- **Intake / registration wizard** — adoption face dominant; *the* capture-once spine; structured-first and prefill at their most intense. *[to design when built]*
- **Inventory / dashboard** — both faces; portfolio view; role-aware. *[to design when built]*
- **Review queue** — assurance face; reviewer / authoriser; SoD-aware; attribution. *[to design when built]*
- **Assessment view (AIIA)** — assurance face; full depth, reasoning, evidence; owner-confirms vs reviewer-reviews. *[to design when built]*
- **Evidence / audit pack** — assurance face; auditor read-only; export. *[to design when built]*
- **"Whose-court" status** — both faces; legible state; what is waiting on whom. *[to design when built]*

---

## 6. Implementation conventions — elsewhere

How these principles are *rendered* — component library, design tokens, typography, spacing, accessibility (WCAG), framework, desktop-first / responsive behaviour — lives in `CLAUDE.md` / `docs/FRONTEND.md`, not here. This file is intent; that is implementation. When a surface is built, it honours this document and follows those conventions.