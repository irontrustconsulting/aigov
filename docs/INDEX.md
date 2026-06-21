# INDEX.md — IronTrust AI Governance Platform · Knowledge Base

**Location:** `docs/INDEX.md` — the entry point. Read this first.
**What this is:** the canonical knowledge base for design and review. It is the single source of truth — the former `PRD.md` / `CLAUDE.md` / `STATE.md` / `app/models/MODELS.md` are superseded and removed. Each fact has exactly one home; everything else cites it by stable ID.

**Repo layout:** all canonicals live in `repo/docs/` and mirror into project knowledge. `repo/CLAUDE.md` is a thin pointer into `docs/` (the Claude Code entry point). Models live in `app/models/`; their map is `DATA-MODEL.md`, not a file in the models dir.

---

## The files

| File | Holds | Change freq |
|---|---|---|
| `INDEX.md` (this) | Router, ID scheme, reading order | rare |
| `DOMAIN.md` | Conceptual model, glossary, lifecycle/scopes/roles as concepts, scope boundary | rare |
| `REQUIREMENTS.md` | MoSCoW requirement registers (the spec), automation boundary, NFRs | rare |
| `ARCHITECTURE.md` | Stack, planes, DB-role set, session/RLS mechanics, conventions, dev env | rare |
| `PATTERNS.md` | Established implementation shapes (`PAT-n`) | occasional |
| `INVARIANTS.md` | The constraint register (`INV-n`) — the reviewer's checklist | **append each sprint** |
| `DECISIONS.md` | Locked decisions + rationale (`D-n`), open questions (`OPEN-n`) | **append each sprint** |
| `DATA-MODEL.md` | Physical schema map: tables, plane/RLS, enums, indexes, guarantees | **append each sprint** |
| `STATE.md` | Implemented capabilities + deferred register | **every sprint** |

**Stable tier** (`DOMAIN`, `REQUIREMENTS`, `ARCHITECTURE`, `PATTERNS`, `INDEX`) rarely moves. **Volatile tier** (`STATE`, `DATA-MODEL`, `INVARIANTS`, `DECISIONS`) is what a sprint-end update touches — nothing else.

---

## Reading order

**Designing a feature / sprint:** `DOMAIN` (what the product is) → `REQUIREMENTS` (what must be built) → `STATE` (what already exists — don't reinvent) → `DATA-MODEL` + `ARCHITECTURE` + `PATTERNS` (the seams to build on) → `INVARIANTS` (constraints the design must not break) → `DECISIONS` (what's settled, what's open).

**Reviewing an implementation:** `INVARIANTS` (the checklist — concentrate on `CONVENTION`-tagged ones, where nothing structural enforces the rule) + `STATE` (does this duplicate or contradict what exists?) + `PATTERNS` (is the shape right?) + `DATA-MODEL` (schema facts). Cite every finding by `INV-n` / `D-n` / requirement id.

---

## Task → file

| If you need… | Go to |
|---|---|
| What a feature must do, with priority | `REQUIREMENTS` (requirement id) |
| Why a choice was made / whether it's settled | `DECISIONS` (`D-n` / `OPEN-n`) |
| A rule the design mustn't break | `INVARIANTS` (`INV-n`) |
| Whether a table is tenant-scoped; enum labels | `DATA-MODEL` |
| The correct service/concurrency shape | `PATTERNS` (`PAT-n`) |
| Stack, DB roles, auth chain, RLS mechanics | `ARCHITECTURE` |
| What's already built / deliberately deferred | `STATE` |
| A term, the lifecycle states, the role model | `DOMAIN` |

---

## ID scheme

- **Requirements:** `LFC` `IXN` `APR` `REG` `CAT` `CLS` `AIIA` `CTL` `RSK` `EVD` `WKF` `EXP` · cross-cutting `XCUT-1` · non-functional `NFR-1..7`.
- **Invariants:** `INV-1..48`, each tagged `DB` (structurally unviolable) / `CODE` (one routed locus) / `CONVENTION` (discipline only — review must catch).
- **Decisions:** `D-1..35`; open questions `OPEN-1..3`.
- **Patterns:** `PAT-1..10`.
- **Entities, enums, tables:** by name (`DATA-MODEL`).

Cross-references between canonicals always use these IDs, never section numbers (section numbers drift; IDs don't).

---

## Working discipline

- **Single home per truth.** A rule lives in `INVARIANTS`; its rationale in `DECISIONS`; its physical object in `DATA-MODEL`; its conceptual statement in `DOMAIN`. Each cites the others — none restates them.
- **Sprint-end update touches the volatile tier only:** append to `INVARIANTS`/`DECISIONS`, update `DATA-MODEL`/`STATE`. Invariant ids are append-only — never renumber a live id.
- **DB is the source of truth (D-21).** Verify live DDL / `pg_enum` / `pg_policies` before encoding a schema assumption; flag "needs verification" rather than assume.

---

## Current scope

Built **through Sprint 7b** (export / audit pack). Ceilings: `INV-48` (1–37 base · 38–45 sprints 7a/7b · 46–48 schema promotions), `D-35`, `OPEN-3`, `PAT-10`.

**Open / verify items to be aware of:**
- `OPEN-1` worked-state void · `OPEN-2` AIIA versioning · `OPEN-3` applicability layer (deferred design intent).
- `DATA-MODEL §5`: two thin code-confirmations outstanding — `system_*` link-table parent-join isolation (confirm the access path joins via `system`; candidate invariant), and the register-fact provenance mechanism (confirm against `create_aiia`; the enum is 4-value, no `USER_PROVIDED`).