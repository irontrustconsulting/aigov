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
- **Invariants:** `INV-1..79`, each tagged `DB` (structurally unviolable) / `CODE` (one routed locus) / `CONVENTION` (discipline only — review must catch).
- **Decisions:** `D-1..66` (+ sprint-local `DF1-3..9`, `DF3-1..7`, `DF4-1..6`, `DF5-1..11`, `DF6-1..10`, `DF7-1..3`, `DF8-1..3`, `DF-V1-1..2`, `DF-F9-1`, `DF-F9-3`, `DF-C2-1..8`, `DF-D1-1..4`, `DF-D2-1..3`, `DF-D3-1..6`); open questions `OPEN-1..4` + `OPEN-V1..V7` (`OPEN-C1` resolved at UI-C2).
- **Patterns:** `PAT-1..10`.
- **UX principles:** `UX-1..6` (`UX.md`).
- **Frontend conventions:** `FE-1..29` (`FRONTEND.md`).
- **Entities, enums, tables:** by name (`DATA-MODEL`).

Cross-references between canonicals always use these IDs, never section numbers (section numbers drift; IDs don't).

---

## Working discipline

- **Single home per truth.** A rule lives in `INVARIANTS`; its rationale in `DECISIONS`; its physical object in `DATA-MODEL`; its conceptual statement in `DOMAIN`; experience intent in `UX`/`PLATFORM-UX`; render/build convention in `FRONTEND`. Each cites the others — none restates them.
- **Sprint-end update touches the volatile tier only:** append to `INVARIANTS`/`DECISIONS`, update `DATA-MODEL`/`STATE`. Invariant ids are append-only — never renumber a live id.
- **DB is the source of truth (D-21).** Verify live DDL / `pg_enum` / `pg_policies` before encoding a schema assumption; flag "needs verification" rather than assume.

---

## Current scope

Backend MVP complete **through Sprint 7b** (export / audit pack); **UI build phase** — tenant UI plane complete (`UI-F0..F6`); operator UI plane complete (`UI-F7-PROVISION` + `UI-F8-OPERATOR-RBAC` shipped); visual foundation installed (`UI-V0-VISUAL-FOUNDATION` shipped); tenant visual skin applied (`UI-V1-TENANT-SKIN` shipped — presentational-only, 0 backend/schema delta); post-V1 corrections shipped (2026-06-25): Tailwind v4 `@source` fix, `TableBody` hydration fix, stale class names, layout/typography pass on 26 pages, `AppNav` persistent nav header, `DrillDownStep` two-level hierarchy, global 401 → login redirect; production UI composition layer installed (`UI-C0-PRODUCTION-FOUNDATION` shipped — `AppShell`/`Sidebar` both planes, `PageHeader`/`PageScaffold`, `EmptyState`/`FirstRunPanel`, shared primitive kit; no-undesigned-UI guardrail INV-68/D-51; 0 backend/schema delta; per-surface composition passes tracked in composition-debt register); first composition pass + identity fold shipped (`UI-C1-PORTFOLIO-IDENTITY` — F2 dashboard composed with C0 kit; `Skeleton`/`ErrorState` built (FE-22 complete); `MeRead.tenant_name` additive backend field; shell identity fold: user in top utility bar, tenant name in sidebar foot; D-52 minted; F2 dashboard composition-debt row cleared); Cognito tenant pool switched to SES email delivery (D-54; `infra/cognito_tenant.tf`; no code/schema delta); member management surface shipped (`UI-F9-MEMBERS` — `apps/tenant/app/members/`; admin-gated Members sidebar entry; member list + invite + SoD-visible governance-role assign/revoke; roles-held column from tenant-wide assignments fetch; born-compliant INV-69/INV-70; 0 backend/schema/route delta; INV-71, D-53, DF-F9-1/3, FE-24 minted; OPEN-4 still open); catalogue drill-down & F1 composition pass shipped (`UI-C2-INTAKE-CATALOGUE` full delivery — `DrillDownStep` rebuilt as in-place single-open accordion per D-56 (category → sub-category → vendor [>1 only] → product leaf), single-vendor auto-skip INV-72, `LogoTile` FE-25 branding on vendor/product rows, confirm step tiles; Lift A: `TextInput` new, `SingleSelect`/`MultiSelectInput`/`FreeText`/`PrefillWithBasis` visual pass (FE-4/FE-5 ALTER); Lift B: `PageHeader` back affordance (FE-21 ALTER); `ListSelectRow` branch mode (FE-23 ALTER); vocab aggregate gate in `IntakeCaptureStep`; all `systems/new` steps re-grounded under INV-69/INV-70; `logo_url` plumbed to `ProductDetailOut`/`CatalogueVendorRef`; D-55..56, DF-C2-1..8, INV-72..73, FE-25 minted; FE-4/5/21/23 altered; `OPEN-C1` resolved; F1 composition-debt row cleared); depth + layout + semantic fidelity shipped (`UI-V2-DEPTH-LAYOUT` — elevation tokens FE-26 + `SectionGroup` FE-27 + `PageScaffold` width prop FE-21 ALTER + `VerdictChip` label map FE-16 ALTER; dashboard zero-systems scaffolded-empty D-61 + INV-74; INV-75 label-map guard; `UI-V2-OPERATOR-SKIN` formally retired; 0 backend/schema/route delta). `UI-F0-FOUNDATION` shipped (BFF auth plane, shared contract, smoke surfaces), `UI-F1-INTAKE` shipped (the intake/registration wizard, `apps/tenant/app/systems/new`; one additive backend addition, `DF1-9`), `UI-F2-PORTFOLIO` shipped (portfolio landing + system drill-in, `apps/tenant/app/dashboard` + `apps/tenant/app/systems/[id]`; read-only, zero backend/schema delta), `UI-F3-ASSESS` shipped (the use-case work surface / AIIA authoring, `apps/tenant/app/use-cases/[id]`; one additive backend schema delta, `DF3-7`; first surface to send `If-Match` live, FE-6), `UI-F4-ASSURE` shipped (the assurance / act-SoD surface — reviewer queue, AIIA review, classification sign-off, authorise + ATO terminal, reopen; one additive backend schema delta, `DF4-6`; `apps/tenant/app/review-queue` new, `apps/tenant/app/use-cases/[id]` extended), `UI-F5-EVIDENCE` shipped (evidence repository home + per-item evidence linking; one additive backend schema delta `DF5-8`; `apps/tenant/app/evidence` new, `apps/tenant/app/use-cases/[id]` extended; dedicated BFF upload handler FE-12; closes DF3-1), `UI-F6-AUDITPACK` shipped (audit/coverage capstone — control-coverage view, export/audit pack, ATO document; `apps/tenant/app/audit` new, `systems/[id]`/`use-cases/[id]`/`dashboard` extended; zero backend/schema delta; closes EXP-1 render-half — **tenant UI plane complete**), `UI-F7-PROVISION` shipped (operator provisioning console — `apps/operator/app/(console)/provisioning` + nav shell; `GET /platform/me` durable backend; `whoami` struck; FE-13 `RequirePermission` primitive; brings provisioning into `INV-49` compliance; durable route delta +1; schema delta 0), `UI-F8-OPERATOR-RBAC` shipped (operator RBAC management console — `apps/operator/app/(console)/operators`; three new platform routes `POST`/`GET /platform/operators`, `GET /platform/roles`; `platform_admin` role + `operator:create` permission seeded; RBAC Management nav entry lit; durable route delta +3; schema delta 0 DDL), `UI-V0-VISUAL-FOUNDATION` shipped (design-system token core + two skins + `packages/ui` component treatments; IBM Plex + Lucide installed; `VerdictChip` new shared component; 0 backend/schema/route delta; INV-54..INV-63 added; FE-14..FE-19 added; D-41..D-47 + OPEN-V1..V5 added), `UI-V1-TENANT-SKIN` shipped (`--tier-*` magnitude channel + `TierBadge` component; `VerdictChip` trimmed to 5 enums/28 members; F1–F6 surface visual treatments; audit serif face; `downgraded_unsubstantiated` distinct marker; stale Tailwind classes replaced; 0 backend/schema/route delta; INV-64..INV-65 added; D-48 + DF-V1-1..2 + OPEN-V6 closed + OPEN-V7 opened; FE-16 amended), `UI-V2-DEPTH-LAYOUT` shipped (elevation tokens FE-26; `SectionGroup` FE-27; `PageScaffold` width FE-21 ALTER; `VerdictChip` label map FE-16 ALTER; dashboard zero-systems scaffolded-empty D-61; INV-74, INV-75, DF-V2-1..4 minted; `UI-V2-OPERATOR-SKIN` retired). BFF session-loop fix (2026-06-27): proxy 401 now clears the stale session cookie (prevents infinite redirect loop after dev-server restart); proactive refresh failure is non-destructive (D-62). **DM-S1 context relocation shipped (2026-06-27):** `usage_context_id`, `human_oversight_type_id`, data categories, affected parties relocated from `system` to `use_case`; `use_case_data_category`/`use_case_affected_party` with RLS + `tenant_id`; DPIA/FRIA feeders + applicability retargeted; classifier unchanged; D-63, D-64, INV-76, INV-77, DF-D1-1..4 minted. **DM-S2 atomic registration shipped (2026-06-27):** `POST /v1/systems` removed (INV-78); `POST /v1/registrations` atomic (D-65); `GET /v1/catalogue/products/{id}/prefill` added (DF-D2-2); four context controls relocated to use-case step (DF-D1-2 closed, DF-D2-3); `useRegister` replaces two-call pattern; `SystemCreate` contract retired; DF-D2-1..3, INV-78 minted. **DM-S3 draft staging shipped (2026-06-28):** `draft_registration` table (TENANT RLS, `uq_draft_one_per_user`, CASCADE FKs — INV-79); four draft endpoints `POST/GET/PATCH/DELETE /v1/draft-registrations`; `POST /v1/registrations` gains optional `draft_id` for atomic draft discard (SV-3/D-66); wizard persist-on-transition + front-door `ResumePrompt` (FE-28); D-66, DF-D3-1..6, INV-79 minted. **DM-S3b dashboard draft-resume indicator shipped (2026-06-28):** `DraftResumeIndicator` kit component (FE-29); wired to `PortfolioHub` for `system_owner` with active draft (first child of `PageScaffold`, scaffolded-empty + populated returns, excluded from loading/error — DF-S3b-1); INV-80 minted + enforced; D-67 authored Branch B (1 legacy bare system — `useSystems()` retained); DF-S3b-1..3 minted; `useActiveDraft()` gains `enabled` option; 0 schema/route delta. Ceilings: `INV-80` (1–37 base · 38–45 sprints 7a/7b · 46–48 schema promotions · 49 platform-UI rule · 50 no-token-in-browser · 51–53 UI-F6-AUDITPACK · 54–63 UI-V0-VISUAL-FOUNDATION · 64–65 UI-V1-TENANT-SKIN · 66–67 post-V1 corrections · 68–70 UI-C0-PRODUCTION-FOUNDATION · 71 UI-F9-MEMBERS · 72–73 UI-C2-INTAKE-CATALOGUE · 74–75 UI-V2-DEPTH-LAYOUT · 76–77 DM-S1 · 78 DM-S2 · 79 DM-S3 · 80 DM-S3b), `D-67` (+ sprint-local `DF1-3..9` · `DF3-1..7` · `DF4-1..6` · `DF5-1..11` · `DF6-1..10` · `DF7-1..3` · `DF8-1..3` · `DF-V1-1..2` · `DF-F9-1` · `DF-F9-3` · `DF-C2-1..8` · `DF-V2-1..4` · `DF-D1-1..4` · `DF-D2-1..3` · `DF-D3-1..6` · `DF-S3b-1..3`, see `DECISIONS.md`) + OPEN-V7, `OPEN-4`, `PAT-10`, `UX-6`, `FE-29`.

**Frontend canonicals** (`UX`, `PLATFORM-UX`, `FRONTEND`) are the frontend half of the KB. `FRONTEND.md` has `FE-1..29` populated. Per-surface depth/layout adoption (F2 detail, F3–F8) continues in per-surface composition passes.

**Open / verify items to be aware of:**
- `OPEN-1` worked-state void · `OPEN-2` AIIA versioning · `OPEN-3` applicability layer (deferred design intent) · `OPEN-4` genesis governance role bootstrap gap.
- `eu_ai_act_tier` HIGH/LIMITED/MINIMAL verdict-tone mapping: tones (HIGH→attention, LIMITED→neutral, MINIMAL→neutral) applied by implementation; Herbert to confirm at V1 (V-5 escalation, STATE.md V0 section).
- `DF3-6`: feeder authoring (A7) is a confirmed scope hole for feeder-gated tiers; must re-enter scope before any such tier enters full-flow testing.
- `UX.md §3`: the cross-tenant-baseline prefill line is flagged `[VERIFY against INV-4 / RLS]` — confirm before a feature surface wires that prefill source.