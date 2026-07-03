# Prefill Disposition (CAT-4 extension) — Sprint Handoff (EXECUTION ONLY)

Rationale lives in `prefill-disposition-CAT4-design-FINAL.md`. Execution-only; dependency-ordered. Do not originate visual/UX decisions (`INV-68`/`D-51`): build the intake affordance to the FE-31 specimen; flag and stop if a visual choice is unspecified.

**Entry floors:** `D-70` · `INV-81` · `FE-30`. **Mint at close:** `D-71`, `D-72`, `INV-82`, `FE-31`; amend `D-68`.

---

## §0 — Pre-flight (block on these before writing)

- [ ] **0.1** Live pg_enum `provenance_confidence` membership. If it has `USER_PROVIDED` and DATA-MODEL/`PAT-8` say 4-value, record the contradiction and flag the `assessment_service.py::USER_PROVIDED` writes as a **pre-existing** issue (do not fix here). This sprint writes only `USER_CONFIRMED`/`USER_AMENDED`.
- [ ] **0.2** `registrations.py`: `create_system` (Step 1) precedes the derivation point and flushes, so `system.id` exists; single transaction, no mid-request commit (`INV-27`).
- [ ] **0.3** `system_service.create_system`/`_derive_vendor_id` loads `CatalogueProduct` when `catalogue_product_id` is set → `product.name` available for the `name` diff. `get_prefill_by_product` returns `operator_role_id`/`lifecycle_stage`/`hosting_model_id`/`purpose` seeds.
- [ ] **0.4** `PATCH /systems/{id}`: which provenance-bearing fields it changes and its If-Match/`PAT-6` shape.
- [ ] **0.5** `SystemDetail` schema; register and audit pack read from it (additive projection, no break).
- [ ] **0.6** Live `D`/`INV`/`FE` ceilings before mint (mirror may lag).

---

## WI-1 — Schema: `prefill_disposition`
Tenant-scoped RLS table (`INV-4`): `id`, `tenant_id`, `system_id` (FK `ON DELETE CASCADE`), `field_key varchar(120)`, `provenance provenance_confidence`, `actor_user_id`, `created_at`; `UNIQUE(system_id, field_key)`. Intake fields use bare keys; catalogue facts use `fact:<key>`.
**Done:** migration up/down; RLS policy present and tenant-isolating (verify live, `PAT-9`); unique constraint holds; FK cascade on system delete.

## WI-2 — Handler: derivation, 422 gate, disposition rows + audit
`RegistrationCreate` gains `confirmed_fields: list[str] = []`. After `create_system`: re-compute seeds (`get_prefill_by_product` + `product.name`); per field derive `USER_CONFIRMED`/`USER_AMENDED`; **422** on any derived default where `submitted == seed` and key not in `confirmed_fields`; write one `prefill_disposition` row per disposed field; stage `system.field_confirmed`/`system.field_amended` `AuditEvent` (value in `detail`). Inside the single `POST /registrations` transaction.
**Done:** unchanged derived default without confirm → 422; with confirm → row `USER_CONFIRMED` + `system.field_confirmed` audit; amended derived → `USER_AMENDED`; catalogue-seeded unchanged → `USER_CONFIRMED` with no confirm signal; renamed `name` → `USER_AMENDED`; custom system → no rows; rollback on forced mid-handler failure leaves no rows.

## WI-3 — Intake confirm/amend affordance (FE-31)
Rework `intake-capture-step.tsx` to the FE-31 specimen: derived fields carry an explicit confirm control and gate Continue until confirmed or edited; confirmed keys accumulate into `confirmed_fields`; editing a derived field removes its key. Catalogue-seeded fields (incl. `name`) show provenance via `FE-15` and submit-confirm. `confirmed_fields` is **not** added to `draft_blob`; `RESUME_FROM_DRAFT` leaves unchanged-confirmed derived fields un-dispositioned so they re-gate.
**Done:** Continue disabled until both derived fields dispositioned; confirming enables it and populates `confirmed_fields`; editing a derived field disposition without confirm; resume re-gates an unchanged-confirmed derived field; custom path shows no gate; `draft_blob` shape unchanged (DM-S3 tests green).

## WI-4 — FE-31 specimen conformance
Match the delivered specimen: derived confirm state, catalogue provenance, name provenance, gated/enabled Continue, resume re-gate.
**Done:** visual review against specimen; no undesigned states.

## WI-5 — `D-68` amendment + `SystemDetail` provenance
Add a per-field provenance projection to `SystemDetail` sourced from `prefill_disposition`; register and audit pack read it.
**Done:** `SystemDetail` carries per-field provenance; export/audit-pack snapshot includes it; no contract break on existing consumers.

## WI-PATCH — `PATCH /systems` re-disposition
On `update_system`, for each changed provenance-bearing field upsert its `prefill_disposition` to `USER_AMENDED` and stage `system.field_amended`, inside the PATCH transaction.
**Done:** PATCH changing `operator_role_id` upserts the row to `USER_AMENDED` + audit; unchanged fields untouched; rides the PATCH If-Match transaction (per §0.4).

## WI-6 — Catalogue-facts panel disposition (splittable, EA)
Carry `PrefillStep` fact dispositions transiently through pre-boundary steps (not in `draft_blob`), submit with `RegistrationCreate`, write `prefill_disposition` rows keyed `fact:<key>`.
**Done:** confirming/marking-not-applicable a fact writes a `fact:<key>` row; resume re-requires fact disposition; no `draft_blob` change. (If split to fast-follow, record the split and defer this WI.)

## WI-7 — Canonical update (last)
`STATE` (intake prefill disposition, provenance store, `system.field_confirmed`/`system.field_amended` audit strings). `DATA-MODEL` (`+prefill_disposition`; `provenance_confidence` on intake). Append `D-71`, `D-72`, `INV-82`, `FE-31`; amend `D-68` (only the "does not store" clause; preserve rejected-a/b). Record the S4b provisional-ID bump. Never renumber a live `INV-n`; leave the stable tier untouched. Record any `DF-n`.
**Done:** STATE/DATA-MODEL/DECISIONS/INVARIANTS/FRONTEND reflect HEAD; appended IDs next-free; no stable-tier edit; audit set updated.

---

## Global done-check
Backend suite, `pnpm --filter tenant test`, `@irontrust/api-client` typecheck green. Diff touches: 1 migration; `prefill_disposition` model; `registrations.py`; `system_service.py` (`update_system` re-disposition); `schemas/registration.py` (`+confirmed_fields`); `schemas/system.py` (`SystemDetail` provenance); `intake-capture-step.tsx` + `wizard-state.ts`; `packages/api-client`; canon files. `draft_blob` schema and DM-S3 draft tests unchanged. `POST /use-cases` and the classifier untouched (that is S4b).