# CLAUDE.md — IronTrust AI Governance Platform

> Entry point for working in this repo. **Read `docs/INDEX.md` before touching code.**
> This file is a pointer, not a knowledge base — it holds nothing durable, so it cannot go stale. Everything substantive lives in `docs/` and is cited by ID.

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
| The correct implementation shapes | `PATTERNS.md` (`PAT-n`) |
| Rules the change must not break | `INVARIANTS.md` (`INV-n`) |
| Why a choice was made / what's open | `DECISIONS.md` (`D-n` / `OPEN-n`) |
| Schema: tables, plane/RLS, enums, indexes | `DATA-MODEL.md` |
| What's already built / deferred | `STATE.md` |

The current unit of work is `sprints/*.md`. Don't restate any of the above here.

---

## Working discipline (Claude Code)

- **Plan mode:** propose edits before applying.
- **Additive over greenfield** (D-22) — never reinvent identity, tenancy, or auth foundations.
- **DB is the source of truth** (D-21) — verify live DDL / `pg_enum` / `pg_policies` before encoding a schema assumption; flag "needs verification" rather than assume.
- **Sprint-end update touches the volatile tier only:** update `STATE.md` + `DATA-MODEL.md`, append to `INVARIANTS.md` + `DECISIONS.md`; leave the stable tier alone. **Never renumber a live `INV-n`** — ids are append-only.
- **Provisioning is never self-service** (D-23). **The §1.5 UX contract holds** (D-1). Dev loop, migrations, and "adding an endpoint" → `ARCHITECTURE.md §7–10`.

**Cardinal guardrails** (pointers — full set in `INVARIANTS.md`): SoD reviewer ≠ authoriser (INV-7, 28; D-4) · prohibition is supreme from any state (INV-26, 33) · plane separation (INV-1) · tenant isolation by RLS, no BYPASSRLS for tenant work (INV-4, 48) · `AuditEvent` append-only (INV-5) · `apply_transition` sole writer of `use_case.state` (INV-24).