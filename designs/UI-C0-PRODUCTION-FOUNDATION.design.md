# UI-C0-PRODUCTION-FOUNDATION — Final Design Doc

**Status:** FINAL, review folded in, handoff-ready · **Track:** production-UI composition layer (the craft layer beneath the token system) · **Plane:** both · **Delta:** presentational, with one standing-process guardrail · **Builds on:** `UI-V0`/`UI-V1` tokens (`FE-14..19`), the legitimate 2026-06-25 fixes (`INV-66`, `INV-67`/`D-49`, `D-50`), `D-22` · **Adds:** app shell, page-scaffold system, first-class UI state patterns, a shared primitive kit; reconciles the reactive 2026-06-25 design work; introduces the no-undesigned-UI guardrail (`INV-68`/`D-51`) · **Feeds:** member management (first surface), then per-surface composition passes F1 to F8

Supersedes the review-ready draft. Disposition of every finding at §7.

## §0 · Pre-flight verify checklist (binding)

| ID | Check | Why |
|---|---|---|
| C-1 | **Audit the actual diffs**, not STATE's self-report, for the three reactive 2026-06-25 items: `AppNav`, the 26-page layout pass, and the `DrillDownStep` rewrite. Record what each truly touched | The reactive work is agent-authored and STATE is its own account of it. Governing discipline: the project-knowledge-lag rule (canonicals can trail repo HEAD; verify against HEAD), not `D-21`, which is DB-specific (N4) |
| C-2 | Confirm `@source "../../../packages/ui/src"` is present in both `apps/*/app/globals.css` (`INV-67`) | Without it the entire `packages/ui` kit renders unstyled; the foundation's new primitives depend on it |
| C-3 | Confirm the `packages/ui` inventory at HEAD and the current ceilings: `INV-67`, `FE-19`, `D-50`, `OPEN-V7`, `DF-V1-2` | New primitives layer on; new ids assign above the live ceilings |
| C-4 | Confirm, per `OPEN-4` and a live grant check, that `provision_tenant` grants the owner the administrative `ADMIN` role with zero governance roles | Re-anchored on `OPEN-4` (V1). The owner **is** `ADMIN`, so member management is reachable. The single-owner genesis gap is `OPEN-4` (self-assignment block, `INV-7`/`D-5`), not an admin grant, and member management does not resolve it; see §5 |

## §1 · Resolved decisions

| ID | Decision |
|---|---|
| C0-1 | The production-UI layer is a real track, foundation-first: shell, scaffold, state patterns, and the primitive kit first, since every surface inherits them; per-surface composition and the member-management build follow |
| C0-2 | The foundation reconciles the reactive 2026-06-25 design work by **superseding**, not adjudicating |
| C0-3 | A standing guardrail (the no-undesigned-UI rule) ships with this foundation, as `INV-68` (operative rule) with rationale in `D-51` (N1), and in `CLAUDE.md` (operative rule only) |
| C0-4 | Shell topology is a left sidebar, both planes. Tenant: brand, vertical nav, pinned account-and-tenant block. Operator: the same sidebar carrying the `--chrome-rail-bg` brand-strong rail as its accent, folding the plane marker (`INV-60`) and nav into one element. **Rejected:** top-bar (the reactive `AppNav`) — already crowding at five items, lighter-weight, no headroom for Members and Settings |
| C0-5 | `INV-69` and `INV-70` are **forward-scoped**: they bind a surface only once it has completed its UI-C0 composition pass, plus all surfaces built after UI-C0. Surfaces predating their pass are tracked in the composition-debt register (Appendix C) until lifted, not standing violations (B1) |

## §2 · The 2026-06-25 reconcile (audit-confirmed at C-1)

Two buckets. The bug fixes are legitimate and stay, including the invariants they minted. The reactive design work becomes provisional pending this foundation. **"Provisional" here means the code stays live and rendering; it is pending re-grounding against the foundation design, not reverted and not unbuilt (N5).** One bug fix reframes the whole impression of the UI.

| Change | Bucket | Canon appended | Disposition |
|---|---|---|---|
| Tailwind v4 `@source` fix | bug fix | `INV-67`, `D-49` | **Keep.** The one that matters most: before this fix every `packages/ui` utility class was silently never generated, so the V0/V1 design system rendered as good as nothing. Much of "toyish" was the design system not emitting. It began rendering only days ago |
| `TableBody` hydration fix | bug fix | `INV-66` | Keep |
| Stale Tailwind class replacement | bug fix | — | Keep |
| Global 401 to login redirect | bug fix | `D-50` | Keep |
| Layout/typography pass (26 pages) | reactive design | STATE only | **Provisional (live).** Superseded by the foundation scaffold (`FE-21`); ratify what the designed scaffold adopts, replace the rest |
| `AppNav` persistent header | reactive design | STATE only | **Provisional (live).** Superseded by the foundation sidebar shell (`FE-20`, C0-4) |
| `DrillDownStep` UX rewrite | reactive UX design | STATE only | **Provisional (live).** Re-grounded against the F1 design at its per-surface pass (`OPEN-C1`), not trusted from the self-report |

None of the reactive design work was elevated to an `INV-n`/`D-n`, so canon pollution is contained to STATE narrative. Hygiene action in the handoff: STATE marks the three reactive items provisional-pending-`UI-C0` with the explicit live-not-reverted note above.

## §3 · The no-undesigned-UI guardrail (proposed INV-68, rationale D-51, plus CLAUDE.md)

`INV-68` (`CONVENTION`) carries the operative rule; `D-51` carries the rationale and rejected alternative (single-home, per `INV-67`→`D-49`, `INV-64`→`D-48`, N1); `CLAUDE.md` carries the operative rule only.

> **Operative rule (INV-68 / CLAUDE.md):** The coding agent does not originate visual, layout, UX, or composition design. It implements only what an execution-only handoff specifies. If it judges a visual or UX change is needed, it flags it and stops; it does not improvise one. It never records an undesigned visual or UX decision in STATE, INDEX, or any canonical as shipped work. Genuine defects (build breaks, hydration errors, broken redirects, classes referencing absent tokens) are exempt and may be fixed and recorded as fixes.

> **D-51 rationale:** Aesthetic debate with the agent has no design authority to draw on, so the agent improvises and then logs the improvisation into canon as shipped work (observed at the 2026-06-25 reactive pass). The rule routes design back to the design plane and keeps the agent in its lane. **Rejected:** letting the agent iterate UI reactively against user complaints (origin of the erosion); a purely advisory CLAUDE.md note with no `CONVENTION` invariant (no review hook to catch recurrence). The exemption boundary is drawn at defects-versus-design: a defect is a behaviour the surface was specified to have and does not; design is any unspecified visual or UX choice. `INV-68` does not collide with `INV-49` (operation locus, not design origination).

## §4 · Foundation deliverables (present vs ALTER)

**(a) App shell (`FE-20`).** A shared `AppShell`/`Sidebar` primitive (NEW) consumed by both planes.
- Tenant shell: `AppNav` (reactive, provisional) → **ALTER-replace** with the sidebar; brand, vertical nav, account-and-tenant block pinned at the foot (the affordance the current bar lacks).
- Operator shell: `apps/operator/app/(console)/layout.tsx` (shipped `UI-F7`) → **ALTER-rework** to the conforming sidebar carrying the `--chrome-rail-bg` plane rail (`INV-60`). The F7 nav-shell logic (`RequirePermission` gating, `FE-13`) is preserved; only its chrome is reworked.

**(b) Page scaffold (`FE-21`).** The 26-page layout pass → **ALTER-supersede**. `PageHeader` primitive (NEW): title, optional subtitle, primary-action slot, breadcrumb/step slot. Defines content width, section rhythm, and the shell-to-content relationship so margins read as intentional.

**(c) UI state patterns (`FE-22`).** All **NEW** (today these are bare sentences): `EmptyState` (icon, line, optional action), `FirstRunPanel` (the get-started path), skeleton loaders, standard error state.

**(d) The shared primitive kit (`FE-23`).** `FE-23` covers only the new composition primitives and **cites, does not restate,** the existing primitive conventions `FE-4` (structured-input set), `FE-5` (prefill-with-basis), `FE-8` (SoD controls), which already own their components (N3).
- `StatCard` — NEW.
- `DataTable` scaffold — **ALTER-extend** the existing `Table`/`TableBody`/`TableRow` (`UI-V0`, `INV-66`): add the scaffold wrapper, header row, and empty body; do not re-implement the table primitive.
- `SectionHeader` — NEW.
- `ListSelectRow` — NEW (the drill-down currently uses inline `<button>`s).
- `PageHeader` — NEW (shared with `FE-21`).
- `Button` — **ALTER** (the `ghost` variant landed at `UI-V0`); refine the hierarchy only.
- `EmptyState` — NEW (shared with `FE-22`).

**Proposed invariants:** `INV-68` (guardrail, refs `D-51`); `INV-69` (compose-from-kit, no bespoke layout or one-off component) and `INV-70` (every data surface defines empty/first-run/loading/error), **both forward-scoped per C0-5**. **Proposed conventions:** `FE-20` (shell), `FE-21` (scaffold), `FE-22` (state patterns), `FE-23` (primitive kit). **Proposed decision:** `D-51` (guardrail rationale). Agent assigns above the live ceilings.

## §5 · Member management and the SoD loop (re-anchored on OPEN-4)

Member management (`admin`-gated, the owner is `ADMIN` per C-4) lets the owner invite colleagues and assign **other** members governance roles. Because those assignments are to other members, the self-assignment block (`INV-7`/`D-5`) does not bite, so this unblocks the multi-member SoD loop: owner staffs Alice as `system_owner`, Bob as `reviewer`, Carol as `authoriser`, and the author-review-authorise chain runs.

It does **not** resolve `OPEN-4`. `OPEN-4` is the single-owner genesis gap: a lone owner cannot self-grant any governance role, so a one-person tenant can do no governance at all. That remains `OPEN-4`'s own resolution (path a: `provision_tenant` seeds an initial governance role; path b: a grace exception in `assert_governance_assignable`) and is out of scope here. The demo loop this track enables is the multi-member one; `OPEN-4` is cited, not closed.

## §6 · Explicitly deferred

Per-surface composition passes (lifting the surfaces in Appendix C from consistency-basic to crafted) and the **member-management build** follow the foundation, member management first because it unblocks the multi-member SoD loop (§5). The data-rich confirmation surface (assess detail or coverage matrix) is the first per-surface target so the kit is proven against real content, not only empty states.

## §7 · Review disposition

| Finding | Fold |
|---|---|
| B1 (blocking) `INV-69`/`INV-70` born-violated | Resolved: both forward-scoped (C0-5) to bind only surfaces that have completed their UI-C0 composition pass plus all post-UI-C0 surfaces; the composition-debt register (Appendix C) tracks the existing-surface debt as remediation, not standing violations |
| V1 (needs source verification) C-4 misframes genesis, omits `OPEN-4` | Resolved: C-4 re-anchored on `OPEN-4` (owner is `ADMIN`); §5 corrected to claim only the multi-member loop and to cite `OPEN-4` as the governing canonical for the single-owner gap |
| N1 `INV-68` no rationale home | `D-51` minted for the rationale; `INV-68` refs it; `CLAUDE.md` carries the operative rule only (§3) |
| N2 present-vs-ALTER missing | Added throughout §4: shell is ALTER both planes (replace tenant, rework operator), `Button`/`DataTable` ALTER, the rest NEW |
| N3 `FE-23` restates `FE-4`/`5`/`8` | `FE-23` now cites them and enumerates only the new composition primitives (§4d) |
| N4 C-1 "D-21 analogue" | Re-anchored on the project-knowledge-lag rule; `D-21` is DB-specific (§0 C-1) |
| N5 hygiene "provisional" ambiguity | §2 states explicitly: code stays live and rendering; provisional means pending re-grounding, not reverted or unbuilt |
| Clean items | Carried: ceilings, bucket split, operator-rail/`INV-60` consistency, `INV-68`/`INV-49` non-collision |

## Appendix A · Open decisions

| ID | Decision | Disposition |
|---|---|---|
| OPEN-C1 | Whether the `DrillDownStep` two-level hierarchy is ratified as-is or re-designed | Resolve at the F1 per-surface pass against the F1 design; provisional until then |

## Appendix B · Source-verification register

| ID | Item | Action |
|---|---|---|
| C-1 | The three reactive-item diffs | Read the code, not STATE (KB-lag rule), before the reconcile freezes |
| C-2 | `@source` directive present (`INV-67`) | Confirm; the kit depends on it |
| C-3 | `packages/ui` inventory and ceilings | Confirm before assigning new ids |
| C-4 | Owner granted `ADMIN` + zero governance roles (`OPEN-4`) | Confirm live; gates the member sprint, but does not close `OPEN-4` |

## Appendix C · Composition-debt register (B1 remediation)

The foundation installs the new shell globally, so the shell debt is cleared at foundation landing. The per-surface **internal** composition (scaffold application, state patterns, kit adoption) is the tracked debt below. A surface comes under `INV-69`/`INV-70` only when its pass clears it here. Member management is born compliant (built to the kit, not listed).

| Surface | Owes | Cleared by |
|---|---|---|
| F1 intake (`systems/new` + steps) | scaffold + states + kit; `DrillDownStep` re-ground (`OPEN-C1`) | F1 composition pass |
| F2 portfolio (`dashboard`, `systems/[id]`) | scaffold + states + kit | F2 pass |
| F3 assess (`use-cases/[id]`) | scaffold + states + kit | F3 pass |
| F4 assure (`review-queue`, `use-cases/[id]` ext) | scaffold + states + kit | F4 pass |
| F5 evidence (`evidence`, ext) | scaffold + states + kit | F5 pass |
| F6 audit (`audit`, ext) | scaffold + states + kit | F6 pass |
| F7 provisioning (operator) | states + kit (shell reworked at foundation) | F7 pass |
| F8 operators (operator) | states + kit (shell reworked at foundation) | F8 pass |