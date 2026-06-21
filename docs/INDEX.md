# INDEX.md — IronTrust AI Governance Platform · Knowledge Base

**Location:** `docs/INDEX.md` — the entry point. Read this first.
**What this is:** the canonical knowledge base for design and review. It is the single source of truth — the former `PRD.md` / `CLAUDE.md` / `STATE.md` / `app/models/MODELS.md` are superseded and removed. Each fact has exactly one home; everything else cites it by stable ID. The KB now spans both the **backend canon** and the **frontend canon** (`UX`, `PLATFORM-UX`, `FRONTEND`).

**Repo layout:** all canonicals live in `repo/docs/` and mirror into project knowledge. `repo/CLAUDE.md` is a thin pointer into `docs/` (the Claude Code entry point). Models live in `app/models/`; their map is `DATA-MODEL.md`, not a file in the models dir.

---

## The files

| File | Holds | Change freq |
|---|---|---|
| `INDEX.md` (this) | Router, ID scheme, reading order | rare |
| `DOMAIN.md` | Conceptual model, glossary, lifecycle/scopes/roles as concepts, scope boundary | rare |
| `REQUIREMENTS.md` | MoSCoW requirement registers (the spec), automation boundary, NFRs | rare |
| `ARCHITECTURE.md` | Stack, planes, DB-role set, session/RLS mechanics, conventions, dev env | rare |
| `UX.md` | Tenant-product experience intent — principles (`UX-n`), two faces, input/prefill model | rare |
| `PLATFORM-UX.md` | Operator-console (platform-plane) experience intent | rare |
| `FRONTEND.md` | Frontend build conventions (`FE-n`) — rendering + the client↔API contract | occasional |
| `PATTERNS.md` | Established implementation shapes (`PAT-n`) | occasional |
| `INVARIANTS.md` | The constraint register (`INV-n`) — the reviewer's checklist | **append each sprint** |
| `DECISIONS.md` | Locked decisions + rationale (`D-n`), open questions (`OPEN-n`) | **append each sprint** |
| `DATA-MODEL.md` | Physical schema map: tables, plane/RLS, enums, indexes, guarantees | **append each sprint** |
| `STATE.md` | Implemented capabilities + deferred register | **every sprint** |

**Stable tier** (`DOMAIN`, `REQUIREMENTS`, `ARCHITECTURE`, `UX`, `PLATFORM-UX`, `PATTERNS`, `FRONTEND`, `INDEX`) rarely moves — `PATTERNS`/`FRONTEND` occasionally, as a new shape or convention is established. **Volatile tier** (`STATE`, `DATA-MODEL`, `INVARIANTS`, `DECISIONS`) is what a sprint-end update touches — nothing else.

---

## Reading order

**Designing a backend feature / sprint:** `DOMAIN` (what the product is) → `REQUIREMENTS` (what must be built) → `STATE` (what already exists — don't reinvent) → `DATA-MODEL` + `ARCHITECTURE` + `PATTERNS` (the seams to build on) → `INVARIANTS` (constraints the design must not break) → `DECISIONS` (what's settled, what's open).

**Designing a UI surface:** `UX` (tenant) or `PLATFORM-UX` (operator) — the experience intent → `DOMAIN` (what the surface represents) → `REQUIREMENTS` (what it must do) → `STATE` (the backend capability it wires to) → the `INVARIANTS`/`PATTERNS` the surface must honour (SoD must be *visible*; the client↔API contract) → `FRONTEND` (build conventions). Cite `UX-n`/`FE-n` alongside `INV-n`/`D-n`.

**Reviewing an implementation:** `INVARIANTS` (the checklist — concentrate on `CONVENTION`-tagged ones, where nothing structural enforces the rule) + `STATE` (does this duplicate or contradict what exists?) + `PATTERNS` (is the shape right?) + `DATA-MODEL` (schema facts). Cite every finding by `INV-n` / `D-n` / requirement id. For a UI surface, add `UX`/`PLATFORM-UX` (intent) and `FRONTEND` (the client↔API contract), citing `UX-n`/`FE-n` too.

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
| How a tenant UI surface should behave / feel | `UX` (`UX-n`) |
| How the operator console should behave | `PLATFORM-UX` |
| How a surface is rendered / the client↔API contract | `FRONTEND` (`FE-n`) |

---

## ID scheme

- **Requirements:** `LFC` `IXN` `APR` `REG` `CAT` `CLS` `AIIA` `CTL` `RSK` `EVD` `WKF` `EXP` · cross-cutting `XCUT-1` · non-functional `NFR-1..7`.
- **Invariants:** `INV-1..49`, each tagged `DB` (structurally unviolable) / `CODE` (one routed locus) / `CONVENTION` (discipline only — review must catch).
- **Decisions:** `D-1..36`; open questions `OPEN-1..3`.
- **Patterns:** `PAT-1..10`.
- **UX principles:** `UX-1..6` (`UX.md`).
- **Frontend conventions:** `FE-n` (`FRONTEND.md`) — reserved, populated as conventions stabilise.
- **Entities, enums, tables:** by name (`DATA-MODEL`).

Cross-references between canonicals always use these IDs, never section numbers (section numbers drift; IDs don't).

---

## Working discipline

- **Single home per truth.** A rule lives in `INVARIANTS`; its rationale in `DECISIONS`; its physical object in `DATA-MODEL`; its conceptual statement in `DOMAIN`; experience intent in `UX`/`PLATFORM-UX`; render/build convention in `FRONTEND`. Each cites the others — none restates them.
- **Sprint-end update touches the volatile tier only:** append to `INVARIANTS`/`DECISIONS`, update `DATA-MODEL`/`STATE`. Invariant ids are append-only — never renumber a live id.
- **DB is the source of truth (D-21).** Verify live DDL / `pg_enum` / `pg_policies` before encoding a schema assumption; flag "needs verification" rather than assume.

---

## Current scope

Backend MVP complete **through Sprint 7b** (export / audit pack); **UI build phase** under way — `UI-F0-FOUNDATION` shipped (BFF auth plane, shared contract, smoke surfaces; not a feature surface). Ceilings: `INV-50` (1–37 base · 38–45 sprints 7a/7b · 46–48 schema promotions · 49 platform-UI rule · 50 no-token-in-browser), `D-37`, `OPEN-3`, `PAT-10`, `UX-6`, `FE-10`.

**Frontend canonicals** (`UX`, `PLATFORM-UX`, `FRONTEND`) are the frontend half of the KB. `FRONTEND.md` is no longer a stub: the client↔API topology is resolved (BFF, bearer-forward — `D-37`) and `FE-1..10` are populated. Token palette/type-scale specifics and per-surface fetch splits remain `[TBD — first feature surface]`.

**Open / verify items to be aware of:**
- `OPEN-1` worked-state void · `OPEN-2` AIIA versioning · `OPEN-3` applicability layer (deferred design intent).
- `DATA-MODEL §5`: two thin code-confirmations outstanding — `system_*` link-table parent-join isolation (confirm the access path joins via `system`; candidate invariant), and the register-fact provenance mechanism (confirm against `create_aiia`; the enum is 4-value, no `USER_PROVIDED`).
- `UX.md §3`: the cross-tenant-baseline prefill line is flagged `[VERIFY against INV-4 / RLS]` — confirm it means anonymised/curated baselines, not raw cross-tenant reads, before it stands as a documented prefill source (out of scope for `UI-F0-FOUNDATION`; must resolve before a feature surface wires a prefill source).