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
| `API-ROUTES.md` | FastAPI route map: every method/path, auth gate, request/response schema, file:line; confirmed-absent routes | **occasional** — update whenever a route is added/removed/re-gated |
| `STATE.md` | Implemented capabilities + deferred register | **every sprint** |

**Stable tier** (`DOMAIN`, `REQUIREMENTS`, `ARCHITECTURE`, `UX`, `PLATFORM-UX`, `PATTERNS`, `FRONTEND`, `INDEX`) rarely moves — `PATTERNS`/`FRONTEND` occasionally, as a new shape or convention is established. **Volatile tier** (`STATE`, `DATA-MODEL`, `API-ROUTES`, `INVARIANTS`, `DECISIONS`) is what a sprint-end update touches — nothing else.

---

## Reading order

**Designing a backend feature / sprint:** `DOMAIN` (what the product is) → `REQUIREMENTS` (what must be built) → `STATE` (what already exists — don't reinvent) → `DATA-MODEL` + `API-ROUTES` + `ARCHITECTURE` + `PATTERNS` (the seams to build on) → `INVARIANTS` (constraints the design must not break) → `DECISIONS` (what's settled, what's open).

**Designing a UI surface:** `UX` (tenant) or `PLATFORM-UX` (operator) — the experience intent → `DOMAIN` (what the surface represents) → `REQUIREMENTS` (what it must do) → `STATE` (the backend capability it wires to) → **`API-ROUTES`** (the exact contract: method, gate, request/response schema, and what does *not* exist — verify here before assuming a route, never re-grep the routers from scratch) → the `INVARIANTS`/`PATTERNS` the surface must honour (SoD must be *visible*; the client↔API contract) → `FRONTEND` (build conventions). Cite `UX-n`/`FE-n` alongside `INV-n`/`D-n`.

**Reviewing an implementation:** `INVARIANTS` (the checklist — concentrate on `CONVENTION`-tagged ones, where nothing structural enforces the rule) + `STATE` (does this duplicate or contradict what exists?) + `PATTERNS` (is the shape right?) + `DATA-MODEL` (schema facts). Cite every finding by `INV-n` / `D-n` / requirement id. For a UI surface, add `UX`/`PLATFORM-UX` (intent) and `FRONTEND` (the client↔API contract), citing `UX-n`/`FE-n` too.

---

## Task → file

| If you need… | Go to |
|---|---|
| What a feature must do, with priority | `REQUIREMENTS` (requirement id) |
| Why a choice was made / whether it's settled | `DECISIONS` (`D-n` / `OPEN-n`) |
| A rule the design mustn't break | `INVARIANTS` (`INV-n`) |
| Whether a table is tenant-scoped; enum labels | `DATA-MODEL` |
| A route's method/path, auth gate, request/response schema — or whether a route exists at all | `API-ROUTES` |
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
- **Invariants:** `INV-1..53`, each tagged `DB` (structurally unviolable) / `CODE` (one routed locus) / `CONVENTION` (discipline only — review must catch).
- **Decisions:** `D-1..40` (+ sprint-local `DF1-3..9`, `DF3-1..7`, `DF4-1..6`, `DF5-1..11`, `DF6-1..10`, `DF7-1..3`, `DF8-1..3`); open questions `OPEN-1..3`.
- **Patterns:** `PAT-1..10`.
- **UX principles:** `UX-1..6` (`UX.md`).
- **Frontend conventions:** `FE-1..13` (`FRONTEND.md`).
- **Entities, enums, tables:** by name (`DATA-MODEL`).

Cross-references between canonicals always use these IDs, never section numbers (section numbers drift; IDs don't).

---

## Working discipline

- **Single home per truth.** A rule lives in `INVARIANTS`; its rationale in `DECISIONS`; its physical object in `DATA-MODEL`; its conceptual statement in `DOMAIN`; experience intent in `UX`/`PLATFORM-UX`; render/build convention in `FRONTEND`. Each cites the others — none restates them.
- **Sprint-end update touches the volatile tier only:** append to `INVARIANTS`/`DECISIONS`, update `DATA-MODEL`/`STATE`. Invariant ids are append-only — never renumber a live id.
- **DB is the source of truth (D-21).** Verify live DDL / `pg_enum` / `pg_policies` before encoding a schema assumption; flag "needs verification" rather than assume.

---

## Current scope

Backend MVP complete **through Sprint 7b** (export / audit pack); **UI build phase** — tenant UI plane complete (`UI-F0..F6`); operator UI plane in progress (`UI-F7-PROVISION` + `UI-F8-OPERATOR-RBAC` shipped). `UI-F0-FOUNDATION` shipped (BFF auth plane, shared contract, smoke surfaces), `UI-F1-INTAKE` shipped (the intake/registration wizard, `apps/tenant/app/systems/new`; one additive backend addition, `DF1-9`), `UI-F2-PORTFOLIO` shipped (portfolio landing + system drill-in, `apps/tenant/app/dashboard` + `apps/tenant/app/systems/[id]`; read-only, zero backend/schema delta), `UI-F3-ASSESS` shipped (the use-case work surface / AIIA authoring, `apps/tenant/app/use-cases/[id]`; one additive backend schema delta, `DF3-7`; first surface to send `If-Match` live, FE-6), `UI-F4-ASSURE` shipped (the assurance / act-SoD surface — reviewer queue, AIIA review, classification sign-off, authorise + ATO terminal, reopen; one additive backend schema delta, `DF4-6`; `apps/tenant/app/review-queue` new, `apps/tenant/app/use-cases/[id]` extended), `UI-F5-EVIDENCE` shipped (evidence repository home + per-item evidence linking; one additive backend schema delta `DF5-8`; `apps/tenant/app/evidence` new, `apps/tenant/app/use-cases/[id]` extended; dedicated BFF upload handler FE-12; closes DF3-1), `UI-F6-AUDITPACK` shipped (audit/coverage capstone — control-coverage view, export/audit pack, ATO document; `apps/tenant/app/audit` new, `systems/[id]`/`use-cases/[id]`/`dashboard` extended; zero backend/schema delta; closes EXP-1 render-half — **tenant UI plane complete**), `UI-F7-PROVISION` shipped (operator provisioning console — `apps/operator/app/(console)/provisioning` + nav shell; `GET /platform/me` durable backend; `whoami` struck; FE-13 `RequirePermission` primitive; brings provisioning into `INV-49` compliance; durable route delta +1; schema delta 0), `UI-F8-OPERATOR-RBAC` shipped (operator RBAC management console — `apps/operator/app/(console)/operators`; three new platform routes `POST`/`GET /platform/operators`, `GET /platform/roles`; `platform_admin` role + `operator:create` permission seeded; RBAC Management nav entry lit; durable route delta +3; schema delta 0 DDL). Ceilings: `INV-53` (1–37 base · 38–45 sprints 7a/7b · 46–48 schema promotions · 49 platform-UI rule · 50 no-token-in-browser · 51–53 UI-F6-AUDITPACK), `D-40` (+ sprint-local `DF1-3..9` · `DF3-1..7` · `DF4-1..6` · `DF5-1..11` · `DF6-1..10` · `DF7-1..3` · `DF8-1..3`, see `DECISIONS.md`), `OPEN-3`, `PAT-10`, `UX-6`, `FE-13`.

**Frontend canonicals** (`UX`, `PLATFORM-UX`, `FRONTEND`) are the frontend half of the KB. `FRONTEND.md` has `FE-1..11` populated. Token palette/type-scale specifics remain `[TBD — per-surface]`.

**Open / verify items to be aware of:**
- `OPEN-1` worked-state void · `OPEN-2` AIIA versioning · `OPEN-3` applicability layer (deferred design intent).
- `DATA-MODEL §5`: register-fact provenance mechanism — `ProvenanceConfidence` is 5-value (includes `USER_PROVIDED` for section answers / from-scratch items / snapshotted register facts); the `DATA-MODEL §5` note that says "4-value, no USER_PROVIDED" is stale and should be corrected when that section is next touched.
- `DF3-6`: feeder authoring (A7) is a confirmed scope hole for feeder-gated tiers; must re-enter scope before any such tier enters full-flow testing.
- `UX.md §3`: the cross-tenant-baseline prefill line is flagged `[VERIFY against INV-4 / RLS]` — confirm before a feature surface wires that prefill source.