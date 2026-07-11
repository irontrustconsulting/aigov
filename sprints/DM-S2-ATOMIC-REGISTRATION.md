# DM-S2 — Atomic Use-Bound Registration — Execution Handoff

**Execution-only.** Rationale and review history live in `DM-S2-atomic-registration-design.md`. Do not originate design (INV-68): if a work item seems to need an unspecified choice, stop and flag. Build defects (compile break, failing migration) are exempt.

**Mint floors:** D ≥ 64, INV ≥ 77, FE ≥ 27. New ids: D-65, INV-78, DF-D2-1..3. Never renumber a live id. **0 schema migration, 0 classifier change.**

---

## §0 — Pre-flight (binding; grep-first across ALL THREE layers; halt on divergence)

- **P-0:** HEAD; floors D ≥ 64 / INV ≥ 77 / FE ≥ 27.
- **P-1 (run FIRST — `app/`, `apps/`, AND `packages/`):** grep every caller of `POST /v1/systems` and the typed systems-create contract method: the FastAPI route, the `@irontrust/api-client` method (`packages/`), the `useCreateSystem` hook (`apps/tenant/lib/intake`). Confirm only the wizard chain (hook → step) and tests reference it. **Any other caller → stop and escalate.**
- **P-2:** confirm `create_system`, `snapshot_classification`, and `advance_use_case` all defer the commit / run in-session (one handler + one request-end commit is atomic; no mid-request commit).
- **P-3:** confirm the prefill resolver is keyed by `catalogue_product_id` underneath (so by-product and by-system share one core).
- **P-4:** confirm no route or service other than the new endpoint constructs a `System` (fixtures/seed scripts excluded).
- **P-5:** confirm `SYSTEM_CREATED` / `system: SystemDetail` (reducer) and `useCreateSystem` / the systems-create contract method are referenced only within the wizard chain.
- **V1:** confirm the catalogue router prefix the by-product prefill route attaches to; reuse the existing `PrefillResponse` schema (do not mint a new one).
- **V2:** confirm `UseCaseWithClassification` = `{use_case: UseCaseRead, classification: ClassificationRead}` and `ClassificationRead` carries `requires_context`.

---

## Work items (dependency-ordered: backend → contract → hooks → components → canon)

### WI-1 — `POST /v1/registrations` endpoint
- Schemas: `RegistrationCreate` (system-stable: `name`, `is_custom`, `catalogue_product_id`, `operator_role_id`, `hosting_model_id`, `lifecycle_stage`, `owner_user_id`, `purpose`; first use case: `title`, `purpose`, `context_blob`, `usage_context_id`, `human_oversight_type_id`, `data_category_ids`, `affected_party_ids`). `RegistrationRead` = `{system: SystemDetail, use_case: UseCaseRead, classification: ClassificationRead}`.
- Handler (`gov:system_owner`), one transaction: `create_system(...)` → `system`; create `use_case` (`system_id=system.id`) + DM-S1 link helpers; `resolve_classification(system.id)` → `snapshot_classification(...)`; return `RegistrationRead`. No commit inside the handler.
- **Done:** registration creates system + use_case + classification; a forced exception after the system insert leaves no system (rollback asserted); custom/no-product → `requires_context`; tier still off the bridge (INV-10/76).

### WI-2 — By-product prefill route
- Add `GET /v1/catalogue/products/{product_id}/prefill` → existing `PrefillResponse`, **member-gated** (same as the existing prefill). Extract one core resolver keyed by `catalogue_product_id`; the existing `GET /systems/{id}/prefill` resolves system → product then **delegates** to it (no duplicate query logic).
- **Done:** by-product read returns the product's facts; custom/no-product → empty 200; by-system read still returns identical facts via the shared resolver.

### WI-3 — Remove `POST /v1/systems`
- Remove the route from `systems.py`. Keep `GET /systems`, `GET /systems/{id}`, `PATCH /systems/{id}`, `GET /systems/{id}/prefill`. `create_system` stays as an internal service.
- **Done:** `POST /systems` → 405/404; no route or service constructs a `System` except `POST /registrations` (route-absence test + handler unit test = INV-78).

### WI-4 — `packages/api-client` (contract layer)
- Add `RegistrationCreate` / `RegistrationRead` types and the `POST /registrations` method; add the by-product prefill method. **Retire** the systems-create method and its `SystemCreate` request type usage.
- **Done:** package builds; no export references the removed systems-create method.

### WI-5 — `apps/tenant/lib/intake` (hooks)
- Replace `useCreateSystem` with `useRegister` (calls the new contract method). Re-key the prefill hook to the by-product method.
- **Done:** hooks compile; no import of the retired contract method remains.

### WI-6 — `wizard-state.ts`
- Hold system-stable facts (`name`, `operatorRoleId`, `hostingModelId`, `lifecycleStage`, `isCustom`, `catalogueProductId`) and the four context facts in state. Replace the `system: SystemDetail` field and the `SYSTEM_CREATED` action with a `REGISTERED` action carrying `system` + `use_case` + `classification`.
- **Done:** reducer typechecks; the `REGISTERED` action branches on `classification.requires_context` / `tier === "prohibited"` / resolved exactly as `USE_CASE_CREATED` did.

### WI-7 — `intake-capture-step.tsx`
- Remove the four context controls and the create call; capture system-stable facts into wizard state and advance (no network).
- **Done:** the step renders only system-stable controls; advancing carries the facts into state.

### WI-8 — `prefill-step.tsx`
- Re-key to the by-product hook using `catalogueProductId` from state; display-only behaviour unchanged.
- **Done:** prefill shows the product's facts during capture; custom → empty; no system id required.

### WI-9 — `use-case-create-step.tsx`
- Add the four context controls + `title`/`purpose`; on submit call `useRegister` with state facts + use facts; pass the result up for the reducer's `REGISTERED` branch.
- **Done:** a full intake run lands the four context fields on the created use case; the branch routes to the correct post-create surface.

### WI-10 — `page.tsx`
- Update reducer wiring for the new state/actions; the post-create surfaces (`ResolvedTierStep`, `ContextGateStep`, `TerminalProhibited`, `WhoseCourtStep`) and role-gating unchanged.
- **Done:** the wizard runs end to end via the single atomic call; a11y pass on every screen retained.

### WI-11 — Canon update (mandatory; last)
- **STATE:** registration atomic via `POST /v1/registrations` (system + first use case + classification, one transaction); `POST /v1/systems` removed; REG-2 by construction (INV-78); prefill by product with a shared resolver; four context controls captured at the use-case step (DF-D1-2 closed).
- **API-ROUTES:** remove `POST /systems`; add `POST /registrations` and `GET /catalogue/products/{id}/prefill` (member-gated).
- **FRONTEND:** systems-create contract method retired; `useCreateSystem` → `useRegister`; prefill hook re-keyed.
- **Append:** D-65, INV-78, DF-D2-1..3. Never renumber a live id; stable tier untouched.
- **Done:** canonicals updated; ids appended above floors; STATE "Current through" advanced to DM-S2.

---

**Full suite green before done.** Intake tests retargeted from the two-call flow to the single atomic call; the retired contract method and hook removed without dangling imports; new tests cover WI-1 (atomicity rollback), WI-3 (INV-78 route-absence + handler unit), WI-2 (shared resolver), and WI-9 (end-to-end context persist).