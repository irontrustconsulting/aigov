# CLAUDE.md — IronTrust AI Governance Platform

> Entry point for working in this repo. **Read `docs/INDEX.md` before touching code.**
> This file is a pointer plus working process, not a knowledge base — it holds no durable domain facts, so it cannot go stale. Everything substantive lives in `docs/` and is cited by ID.

**Product, in one line:** an AI governance platform for mid-market orgs; the MVP centre of gravity is the ISO/IEC 42005 AI System Impact Assessment, scoped by EU AI Act risk tier. The *why and what* is `docs/DOMAIN.md`.

**Naming:** repo `aigov`; DB / Cognito / role prefix `irontrustai`; company IronTrust.

---

## The knowledge base (`docs/`) is the source of truth

`docs/INDEX.md` is the router. In short:

| For… | Read |
|---|---|
| What the product is; terms; lifecycle/roles | `DOMAIN.md` |
| What must be built, with priority | `REQUIREMENTS.md` |
| How the repo is built — stack, DB roles, auth, RLS, conventions, dev loop | `ARCHITECTURE.md` |
| Tenant UX intent — principles, two faces, prefill model | `UX.md` (`UX-n`) |
| Operator-console (platform-plane) UX intent | `PLATFORM-UX.md` |
| How the UI is rendered + the client↔API contract | `FRONTEND.md` (`FE-n`) |
| The correct implementation shapes | `PATTERNS.md` (`PAT-n`) |
| Rules the change must not break | `INVARIANTS.md` (`INV-n`) |
| Why a choice was made / what's open | `DECISIONS.md` (`D-n` / `OPEN-n`) |
| Schema: tables, plane/RLS, enums, indexes | `DATA-MODEL.md` |
| Every route: method, path, auth gate, request/response schema — or whether one exists at all | `API-ROUTES.md` |
| What's already built / deferred | `STATE.md` |

The current unit of work is `sprints/*.md`. Don't restate any of the above here.

---

## Working discipline (Claude Code)

- **Plan mode:** propose edits before applying.
- **Additive over greenfield** (D-22) — never reinvent identity, tenancy, or auth foundations.
- **DB is the source of truth** (D-21) — verify live DDL / `pg_enum` / `pg_policies` before encoding a schema assumption; flag "needs verification" rather than assume.
- **Follow the established shape** — pick the `PAT-n` the task calls for rather than improvising; live-smoke RLS / `SET LOCAL` / enum paths against the real dev DB (PAT-9), since the no-RLS test DB can't catch them.
- **Provisioning is never self-service** (D-23); **the §1.5 UX contract holds** (D-1). Dev loop, migrations, "adding an endpoint" → `ARCHITECTURE.md §7–10`.

**Cardinal guardrails** (pointers — full set in `INVARIANTS.md`): SoD reviewer ≠ authoriser (INV-7, 28; D-4) · prohibition is supreme from any state (INV-26, 33; D-7) · substantive act → domain row + audit event (D-6) · plane separation (INV-1) · tenant isolation by RLS, no BYPASSRLS for tenant work (INV-4, 48) · `AuditEvent` append-only (INV-5) · `apply_transition` sole writer of `use_case.state` (INV-24) · platform functionality is UI-operated, CLI bootstrap-only (D-36, INV-49).

---

## Sprint closure — definition of done

You are the only agent that edits `docs/`; closure is your job. The **canon statement** of this rule is `INDEX.md` → Working discipline; the **per-sprint instance** is the handoff's final work item, which names the exact edits and the `INV`/`D` text to append. The steps below are the standing expansion — run them every sprint, whether or not a given handoff spells each one out.

1. **Verify before documenting.** Done-checks / tests green. Live-smoke any RLS / `SET LOCAL` / enum-label path against the real dev DB (PAT-9, D-21); confirm new enum-label case against `pg_enum` (INV-23). Document the DB as migrated, never as the design doc assumed it.
2. **Update the volatile tier only:**
   - `STATE.md` — move shipped capability out of *deferred* into *implemented*; update the deferred register; add any new audit-action strings.
   - `DATA-MODEL.md` — new tables / enums / indexes with **plane + RLS** tag; new guarantees; resolve drift notes.
   - `API-ROUTES.md` — add/update/remove the rows for any route the sprint touched (method, gate, request/response schema); add to §4 (confirmed absent) if a sprint's pre-flight rules a plausible-sounding route out.
   - `INVARIANTS.md` — **append** new `INV-n`, tagged `DB`/`CODE`/`CONVENTION` + locus + origin.
   - `DECISIONS.md` — **append** new `D-n` (rationale / rejected alternative); add or resolve `OPEN-n`.
   - `PATTERNS.md` — append a `PAT-n` only if the sprint established a genuinely new reusable shape.
   - `INDEX.md` — bump the ID ceilings and the Current-scope line.
   - *UI sprints also:* fill the built surface's per-surface intent in `UX`/`PLATFORM-UX` §5; add any stabilised `FE-n` to `FRONTEND`; bump the INDEX `UX`/`FE` ids.
3. **Append-only — never renumber** a live `INV`/`D`/`PAT`/`UX`/`FE` id. An id is an identifier, not a chronology.
4. **Leave the stable tier untouched** (`DOMAIN`, `REQUIREMENTS`, `ARCHITECTURE`, the `UX`/`PLATFORM-UX` principles, `INDEX` structure). If a sprint genuinely forces a stable-tier change, **flag and propose — don't silently edit.**
5. **Single home per truth.** Distil the durable fact into its one canonical and cite by ID elsewhere; never duplicate across files. Rationale stays in `DECISIONS`/the design doc — keep it out of `STATE`/`DATA-MODEL`.
6. **Mirror note.** These docs also mirror into project knowledge; Herbert syncs that manually. You own the repo `docs/` — leave the mirror to him.