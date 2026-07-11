# DM-S2 — Atomic Use-Bound Registration — Final Design Doc

**Status:** FINAL (review folded) · vertical slice (backend + contract + hooks + wizard) · **handoff ready** · ids from live floors → D-65, INV-78, DF-D2-1..3 · delta: 1 new endpoint, 1 route removed, 1 by-product prefill read, contract + hook + wizard rewire, **0 schema migration, 0 classifier change**.

**Review disposition:** B1 and B2 accepted — the contract layer (`packages/api-client`) and the hook layer (`apps/tenant/lib/intake`) were absent from both the work items and the grep; both folded (the rewire now spans those layers; §0 P-1 now greps `packages/` too). N1 (INV-78 reworded to CONVENTION + tests), N2 (shared prefill resolver), N3 (prefill gate), N4 (P-2 names `advance_use_case`) folded. V1/V2 added as verifies. A2 resolved (return full). A4 resolved (no new audit marker). Atomicity argument survived source check (Clean).

**Scope (one act, three faces):** (1) `POST /v1/registrations` creates `system` + first `use_case` + classification in one transaction. (2) `POST /v1/systems` removed (founder ruled). (3) the four context controls move to the use-case step (closes DF-D1-2). **Not in scope:** draft staging / resume (DM-S3), recognition / uniqueness (DM-S4), the prefill rework (§9.3), the F2/F6 detail record.

**Reuses, does not fork:** `create_system`, the use-case-create path, `resolve_classification`, `snapshot_classification` (which fires `advance_use_case`). One handler, one request-end commit.

---

## §0 — Pre-flight verify checklist (binding; grep-first across ALL layers; D-21)

| id | Verify (live) | Gates |
|---|---|---|
| P-0 (canary) | HEAD; floors D ≥ 64, INV ≥ 77, FE ≥ 27. | ID baseline. |
| **P-1 (the removal's safety — greps `app/`, `apps/`, AND `packages/`)** | Grep every caller of `POST /v1/systems` and the typed systems-create method across **all three layers**: the FastAPI route, the `@irontrust/api-client` contract method (`packages/`), and the `useCreateSystem` hook (`apps/tenant/lib/intake`). Confirm only the wizard chain (hook → step component) and tests reference it — no operator surface, no script, no other hook. Any other caller stops the removal. | orphan closure safe (B2). |
| P-2 | Confirm `create_system`, `snapshot_classification`, **and `advance_use_case`** each leave the commit to the caller / run in-session and never commit mid-request (so one handler + one commit is atomic and INV-27 is not tripped). | atomicity (N4). |
| P-3 | Confirm the prefill resolver is keyed by `catalogue_product_id` underneath, so a by-product read and the by-system read can share one core (N2). | prefill single-home. |
| P-4 | Confirm no **route or service** other than the new endpoint constructs a `System` (test factories / seed scripts excluded; they are fixtures, not callers). | INV-78 (N1). |
| P-5 | Confirm `SYSTEM_CREATED` / `system: SystemDetail` in the reducer, and `useCreateSystem` / the systems-create contract method, are referenced only within the wizard chain (safe to restructure/retire). | rewire blast radius (B1). |
| V1 | Confirm the catalogue router prefix the by-product prefill route attaches to (a catalogue router already backs DrillDownStep's browse reads), and **reuse the existing `PrefillResponse` schema** rather than minting a new one. | prefill home + shape. |
| V2 | Confirm `UseCaseWithClassification` is `{use_case: UseCaseRead, classification: ClassificationRead}` and that `ClassificationRead` carries `requires_context` (not `status`) — the wizard branches on `requires_context`. | `RegistrationRead` shape (A2). |

---

## Resolved decisions

| # | Decision | Rationale / rejected |
|---|---|---|
| D-65 | **Registration is one atomic act.** `POST /v1/registrations` (`gov:system_owner`), body `RegistrationCreate` = system-stable + first use-case facts, creates `system` + `use_case` + classification in one transaction; returns `RegistrationRead` = `{system: SystemDetail, use_case: UseCaseRead, classification: ClassificationRead}` (A2: full, no post-create refetch). `POST /v1/systems` removed; `create_system` stays as an internal service. | Closes the orphan seam (REG-2). **Rejected:** keep `POST /systems` with a guard (founder ruled remove); extend `POST /use-cases` to optionally create a system (muddies it). |
| INV-78 | **`[NEW]` CONVENTION — no bare system.** No **route or service** constructs a `System` without a `UseCase` in the same commit. Enforced by CONVENTION plus two tests: a route-absence assertion (`POST /systems` gone) and a handler unit test that registration always creates system + use_case in one transaction. Test factories and seed scripts are fixtures, explicitly outside this claim (N1). | REG-2; the spine. Not a DB constraint (a relational ≥1-child guarantee has no clean DDL — A3). |
| DF-D2-1 | **Capture relocation completed.** The four context controls move from `intake-capture-step` to the use-case step; the intake step keeps system-stable controls. Closes DF-D1-2. | Fields belong with the use they describe. |
| DF-D2-2 | **Prefill re-keyed by product, single resolver (N2).** Add `GET /v1/catalogue/products/{product_id}/prefill` → existing `PrefillResponse` (V1), **member-gated, same as the existing prefill (N3)**. Both routes share one core resolver keyed by product; the by-system route resolves system → product then **delegates** to it (no divergent query logic). | The system does not exist at capture time; single-home. |
| DF-D2-3 | **Wizard promotes at the boundary.** Capture held in wizard state through drill-down → intake → prefill → use-case, then `POST /registrations` once at the use-case step. No early `POST /systems`. | The creation boundary; no orphan. |

**A4 resolved (audit marker):** registration leaves the two existing domain-row events — `system.created` and `classification.created`, both staged in the one transaction — and does **not** add a `registration.created` marker. D-6 is satisfied by the two substantive-act rows; a third marker would duplicate, not document.

---

## The atomic endpoint

`POST /v1/registrations` (`gov:system_owner`), `RegistrationCreate`:
- **System-stable:** `name`, `is_custom`, `catalogue_product_id`, `operator_role_id`, `hosting_model_id`, `lifecycle_stage`, `owner_user_id`, `purpose`.
- **First use case:** `title`, `purpose`, `context_blob`, `usage_context_id`, `human_oversight_type_id`, `data_category_ids`, `affected_party_ids`.

Handler, one transaction:
1. `create_system(...)` → `system` (existing service; vendor-from-product, `is_custom` XOR catalogue, vocab/owner validation unchanged; INV-3 — tenant from `ctx`, never the body).
2. Create `use_case` (`system_id = system.id`) + the DM-S1 link helpers (which stamp `tenant_id`, INV-77).
3. `resolve_classification(system.id)` → proposal; `snapshot_classification(...)` (stamps `eu_tier`, stages audit, fires `advance_use_case`; INV-26/33 prohibited-halt still off the snapshot tier).
4. Return `RegistrationRead`. One commit at request end → atomic; a forced failure after step 1 rolls back with no orphan.

Custom/no-product → `REQUIRES_CONTEXT` → context gate, unchanged.

## Orphan closure

Remove the `POST /v1/systems` route. Retire the systems-create contract method in `packages/api-client` and the `useCreateSystem` hook in `lib/intake` (B1). Keep `GET /systems`, `GET /systems/{id}`, `PATCH /systems/{id}`, `GET /systems/{id}/prefill`. After removal the only `System`-constructing route/service is `POST /registrations` (INV-78, P-4).

## Rewire (dependency-ordered; contract and hooks first — B1)

1. **`packages/api-client` (contract layer, FE-1).** Add `RegistrationCreate` / `RegistrationRead` and the by-product prefill contract; retire the systems-create method.
2. **`apps/tenant/lib/intake` (hook layer, FE-2).** Replace `useCreateSystem` with `useRegister` (calls `POST /registrations`); re-key the prefill hook to the by-product read.
3. **`wizard-state.ts`.** Hold system-stable + the four context facts in state; replace the `system: SystemDetail` field and `SYSTEM_CREATED` action with a `REGISTERED` action carrying `system` + `use_case` + `classification`; the use-case step drives the create.
4. **`intake-capture-step.tsx`.** Drop the four context controls and the create call; capture system-stable facts into state and advance (no network here).
5. **`prefill-step.tsx`.** Re-key to the by-product hook using `catalogueProductId`; display-only behaviour unchanged (custom → empty).
6. **`use-case-create-step.tsx`.** Gain the four context controls + `title`/`purpose`; on submit call `useRegister` with state facts + use facts; branch on the response as the reducer does today.
7. **`page.tsx`.** Reducer wiring updated; the post-create branch surfaces unchanged.

No new FE primitives; relocated controls reuse `SingleSelect` / `MultiSelectInput`.

## Done-checks (tied to tests)

- **Atomicity:** registration creates system + use_case + classification; a forced failure after the system insert leaves no system (rollback asserted).
- **Orphan closure:** `POST /systems` route gone (405/404); the contract method and `useCreateSystem` removed; **the P-1 grep across all three layers confirms no live caller remains** (V3); no `System` built outside `POST /registrations` (INV-78 route-absence + handler unit test).
- **Capture relocation:** a full intake run captures the four at the use-case step and lands them on the use case; the intake step no longer renders them.
- **Prefill by product:** the by-product read returns the product's facts via the shared resolver; custom → empty 200; the by-system route still works (delegation).
- **Branch intact:** resolved / requires_context / prohibited each route correctly from the atomic response; custom → REQUIRES_CONTEXT → context gate.
- **Suite green:** intake tests retargeted from the two-call flow to the single atomic call; the dead contract method and hook removed without dangling imports.

---

## Sprint-local decisions (DF-D2-n)

DF-D2-1 capture relocation completed · DF-D2-2 prefill re-keyed by product (single resolver) · DF-D2-3 wizard promotes at the boundary.

## Appendix A — Open decisions

- **A1:** endpoint name `POST /v1/registrations` (recommended). Resource-noun, not a sub-action of a removed resource.
- **A2 — RESOLVED:** `RegistrationRead` returns full `SystemDetail` + `UseCaseRead` + `ClassificationRead` (no post-create refetch).
- **A3 — accepted:** REG-2 by construction + INV-78 tests, not a DB constraint.
- **A4 — RESOLVED:** no `registration.created` marker; `system.created` + `classification.created` satisfy D-6.

## Appendix B — Source-verification register

P-0 canary; **P-1 the three-layer removal grep (binding — `app/` + `apps/` + `packages/`, B2)**; P-2 caller-commits atomicity incl. `advance_use_case` (N4); P-3 prefill resolver by product (N2); P-4 no other `System`-constructing route/service, fixtures excluded (N1); P-5 rewire blast radius incl. contract method + hook (B1); V1 catalogue router prefix + reuse `PrefillResponse`; V2 `UseCaseWithClassification` shape + `requires_context` (A2); V3 executed P-1 result.

## Appendix C — Canon-update note (for the handoff)

STATE: registration atomic via `POST /v1/registrations`; `POST /v1/systems` removed; REG-2 by construction (INV-78); prefill available by product, shared resolver; four context controls captured at the use-case step (DF-D1-2 closed). API-ROUTES: remove `POST /systems`; add `POST /registrations` and `GET /catalogue/products/{id}/prefill` (member-gated). FRONTEND: contract method retired, `useCreateSystem` → `useRegister`, prefill hook re-keyed. Append D-65, INV-78, DF-D2-1..3. Never renumber a live id; stable tier untouched.

**Handoff issues next (no open founder call).**