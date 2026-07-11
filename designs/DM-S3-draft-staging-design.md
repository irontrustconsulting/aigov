# DM-S3 — Draft Staging & Resume (core) — Final Design Doc

**Status:** FINAL (review folded) · scope narrowed: the **dashboard half (FE-29 indicator + nudge) peels to DM-S3b** per the reviewer's recommendation · core = backend + api-client + hooks + wizard + `ResumePrompt` · **handoff ready** · ids from live floors → D-66, INV-79, FE-28, DF-D3-1..6 · delta: 1 table (+RLS), 4 draft endpoints, 1 optional field on `POST /registrations`, 1 FE primitive, wizard persist + resume · **0 classifier change.**

**Review disposition:** B1 and B2 both sit in the dashboard groups and **move to DM-S3b** (B1 nudge gated on SV-1 portfolio-totality; B2 FE-29 in both render paths + system_owner-gated query). Non-blockers N-1..N-6 folded into the core. SV-3 added. Core groups (backend, api-client, hooks, wizard, `ResumePrompt`) were found clean.

**Scope (core):** progressive server-side draft staging plus the **front-door resume** (`ResumePrompt` on re-entering Register). The draft accumulates pre-boundary capture, persists on transition, feeds forward, and is discarded atomically when registration commits. **Peeled to DM-S3b:** the dashboard `DraftResumeIndicator` (FE-29) and the zero-use-case nudge decision. **Not in scope:** recognition/uniqueness (DM-S4), the prefill rework, the F2/F6 detail record.

**Resume coverage without the dashboard:** the front-door `ResumePrompt` fully covers resume — a user who abandons mid-registration resumes by clicking **Register a system** again. The dashboard indicator (DM-S3b) is an additional cue, not the only path; nothing is lost by peeling it.

---

## §0 — Pre-flight verify checklist (binding; grep-first across ALL layers; D-21)

| id | Verify (live) | Gates |
|---|---|---|
| P-0 (canary) | HEAD; floors D ≥ 65, INV ≥ 78, FE ≥ 27 (STATE "Current through: DM-S2" is the floor; INDEX lags at UI-V2 — SV-2). | ID baseline. |
| **P-1 (full-stack enumeration)** | Confirm the work items cover every core layer: FastAPI router + service + model + migration; `@irontrust/api-client` draft contracts; `lib/intake` hooks; the wizard reducer/steps. (Dashboard layer deferred to DM-S3b.) | nothing stranded. |
| P-2 | `WizardState` holds the pre-boundary fields + `step`; `step` is a UI cursor. | draft_blob shape. |
| P-4 | The tenant-RLS table pattern (INV-77: `tenant_id` FK NOT NULL + policy `tenant_id = current_setting('app.current_tenant', true)::uuid`); `gov:system_owner` gate. | isolation + gate. |
| P-5 / SV-3 | `RegistrationCreate` takes an additive optional `draft_id`; an in-handler delete after the flushes leaves `TestRegistrationAtomicity` green (delete inside the same transaction). | atomic discard (D-66). |

---

## Resolved decisions

| # | Decision | Rationale / rejected |
|---|---|---|
| D-66 | **Progressive server-side draft staging, atomic discard.** A `draft_registration` row accumulates pre-boundary capture, written on each transition (`PATCH`), fed forward on resume. The draft is **staging, never an inventory entity** (not a `System`; never in the register). `POST /v1/registrations` takes an optional `draft_id` and **discards the draft in the same transaction** as the create. | OPEN-INTAKE-C. **Rejected:** client-side discard (non-atomic, stale-draft prompt); a `/promote` endpoint (forks the create). |
| INV-79 | **`[NEW]` CONVENTION — one active `draft_registration` per (tenant, user); a draft is never a system.** Enforced by a **plain `UniqueConstraint(tenant_id, owner_user_id)`** (N-1: no partial predicate exists — the table holds at most one row per user, hard-deleted on discard/promote, no status discriminator) and by structural distinctness from `system` (no register FK). | one-active-draft; staging-not-entity. |
| FE-28 | **`[NEW]` `ResumePrompt`** — the resume-or-start-over panel (product, progress, last-edited; primary Resume, secondary Start over). Shown on re-entering Register with an active draft. | Front-door resume. |
| DF-D3-1 | `draft_blob` is **JSONB** holding the pre-boundary `WizardState` fields + `step`; never the post-registration fields. | Transient staging. |
| DF-D3-2 | **Persist points are the pre-boundary transitions** (drill-down → intake, intake → prefill, prefill → use-case); the use-case screen stays in-memory until submit (the boundary). | The direction's completed-screen rule. |
| DF-D3-3 | **`step` is clamped to the pre-boundary set** (`drill-down`/`intake`/`prefill`/`use-case`) on both persist and resume (N-3). A stored or restored post-boundary `step` is invalid — its `system`/`classification` are not in `draft_blob`. No `PATCH` fires on or after `REGISTERED`. | resume never lands past `use-case`. |
| DF-D3-4 | **Per-user scoping is explicit application-level filtering, not RLS** (N-2). RLS isolates by tenant only; `GET /active`, `PATCH`, `DELETE` each add `WHERE owner_user_id = ctx.user_id`. This is the one per-user-within-tenant scope in the codebase. | correctness; RLS does not supply it. |
| DF-D3-5 | **`POST /draft-registrations` is SELECT-first get-or-create** (N-4): return the caller's active draft if one exists, else create; the unique constraint is the backstop, not the control path. | idempotent, no error-driven flow. |
| DF-D3-6 | **`draft_blob` `PATCH` is last-write-wins** (N-5): no `lock_version` (contrast INV-14); acceptable for a single-user transient draft (two tabs → LWW, intentionally). No optimistic concurrency. | scope discipline; do not improvise. |

---

## The draft table and endpoints

`draft_registration`: `id`, `tenant_id` (FK `tenant`, **`ondelete=CASCADE`**, RLS), `owner_user_id` (FK `app_user`, **`ondelete=CASCADE`**) (N-6: the draft is transient, dies with tenant or user), `draft_blob` (JSONB), `created_at`, `updated_at`. **`UniqueConstraint(tenant_id, owner_user_id)`** (N-1).

Endpoints (`app/routers/v1/draft_registrations.py`, `gov:system_owner`):
- `POST /v1/draft-registrations` → **get-or-create** the caller's active draft (DF-D3-5).
- `PATCH /v1/draft-registrations/{id}` → persist a completed screen; **`WHERE owner_user_id = ctx.user_id`** (DF-D3-4); LWW (DF-D3-6).
- `GET /v1/draft-registrations/active` → the caller's active draft or `204`; **owner-filtered** (DF-D3-4).
- `DELETE /v1/draft-registrations/{id}` → discard; **owner-filtered** (DF-D3-4).
- `POST /v1/registrations` gains optional `draft_id`; when present, the draft is deleted in the same transaction as the create (D-66, SV-3).

## The flow

**Persist-on-transition.** First pre-boundary advance creates the draft (get-or-create); each subsequent advance `PATCH`es `draft_blob` with the clamped `step` (DF-D3-2, DF-D3-3). No `PATCH` on or after `REGISTERED`.

**Front-door resume.** On entering `/systems/new`, the wizard reads `GET /draft-registrations/active`. Present → `ResumePrompt` (FE-28): Resume loads `draft_blob` and lands on the clamped saved `step`; Start over `DELETE`s and begins clean.

**Boundary.** The use-case step submits `POST /registrations` with `draft_id`; on commit, system + use_case are created and the draft discarded atomically (D-66). The register never held the draft.

## Rewire (dependency-ordered; contract and hooks first)

1. **Backend** — migration (table + RLS + plain unique + CASCADE FKs); `draft_registrations` router + service (owner-filtered, get-or-create, LWW); the optional `draft_id` discard on `POST /registrations`.
2. **`packages/api-client`** — draft contracts + the `draft_id` field on `RegistrationCreate`.
3. **`apps/tenant/lib/intake`** — `useDraft` hooks (get-or-create, patch, active, discard); thread `draft_id` into `useRegister`.
4. **`packages/ui`** — `ResumePrompt` (FE-28).
5. **`wizard-state.ts` / steps** — persist-on-transition (clamped); the entry active-draft check + `ResumePrompt`; resume load.

## Done-checks (tied to tests)

- **Persist + resume:** advancing through drill-down and intake writes the draft; re-entering `/systems/new` shows `ResumePrompt`; Resume restores state and lands on the saved (clamped) step; Start over discards and begins clean.
- **Clamp (DF-D3-3):** resume never lands past `use-case`; no `PATCH` fires on/after `REGISTERED` (asserted).
- **One active draft (INV-79):** a second `POST /draft-registrations` returns the existing draft (get-or-create), not a second row; `UniqueConstraint` asserted as the backstop.
- **Owner scoping (DF-D3-4):** a second user in the same tenant cannot read/patch/delete the first user's draft (owner filter asserted, not just RLS).
- **Atomic discard (D-66/SV-3):** a successful `POST /registrations` with `draft_id` leaves no draft row; a forced registration failure leaves the draft intact; `TestRegistrationAtomicity` stays green.
- **Isolation:** cross-tenant read of `draft_registration` returns nothing (RLS).

---

## DM-S3b scope (peeled; built next, not here)

- **FE-29 `DraftResumeIndicator`** rendering in **both** `PortfolioHub` render paths — the D-61 zero-systems scaffolded-empty branch **and** the populated branch (B2; the zero-systems + active-draft case is the highest-frequency resume scenario). The active-draft query is **`enabled: isSystemOwner`** so it never 403s contributor/reviewer/auditor (B2).
- **The zero-use-case nudge decision**, gated on **SV-1** (does `GET /v1/portfolio` return a row for a system whose only use case is `HALTED_PROHIBITED` / `REQUIRES_CONTEXT` / `PENDING_REVIEW`?). If the projection is **non-total**, the nudge or an equivalent "registered but absent from portfolio" affordance **stays**, because it is the only surface listing a prohibited-halted system, which §4 inventory-completeness requires kept visible (B1). **SV-4:** retire only `page.test.tsx::zero-use-case-system`; never the `f2-portfolio.test.tsx` D-61 zero-systems test.

## Appendix B — Source-verification register

P-0 canary (STATE is floor; INDEX lags — SV-2); P-1 full-stack core enumeration; P-2 `WizardState` fields; P-4 RLS + gate; **SV-3** `draft_id` additive + in-txn discard leaves atomicity green. (SV-1 portfolio totality and SV-4 nudge-test blast radius ride DM-S3b.)

## Appendix C — Canon-update note (for the handoff)

STATE: registration wizard draft-staged and resumable via the front door; `draft_registration` (tenant RLS, one active per user via plain unique, owner-filtered access, CASCADE FKs, INV-79); four draft endpoints + atomic `draft_id` discard on `POST /registrations` (D-66); `ResumePrompt` (FE-28). API-ROUTES: add the four draft routes + `draft_id`. DATA-MODEL: add `draft_registration`. FRONTEND: FE-28. Append D-66, INV-79, FE-28, DF-D3-1..6. **Also refresh INDEX.md "Current scope" (it lags at UI-V2 — SV-2)** and treat STATE "Current through" as the floor. Never renumber a live id; stable tier untouched.

**Handoff issues next (dashboard peeled to DM-S3b).**