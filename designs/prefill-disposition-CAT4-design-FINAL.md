# Prefill Disposition (CAT-4 extension) — FINAL

**Status:** FINAL · review folded (B1, B2, N1-N6, SV-A/B/C) · handoff cut as paired file. **Framing (N1):** this **extends** `CAT-4`'s confirm/amend model from catalogue facts to intake defaults and **amends** `D-68`'s deliberate labels-only choice on `N4(b)` grounds. It is a policy tightening, not repair of a shipped defect: DM-S4a satisfied `CAT-4` as then scoped. Sequenced **before S4b** (DD).
**Floors at entry:** `D-70` · `INV-81` · `FE-30`. **Target ceilings (proposed):** `D-71`, `D-72` · `INV-82` · `FE-31`. S4b's provisional IDs bump when it is next re-grounded (unminted).
**Delta envelope:** schema **+1 table** (`prefill_disposition`, tenant-scoped RLS) · `RegistrationCreate` **+`confirmed_fields`** (transient action signal, not in `draft_blob`) · registration handler **+provenance derivation + derived-field 422 gate** · `PATCH /systems` **+re-disposition of changed fields** · `provenance_confidence` extended to intake fields · intake UI `FE-30` → `FE-31` · migration **1** · FE-31 specimen.
**Grounded against:** `CAT-4`, `D-1`, `PAT-4`, `PAT-6`, `PAT-8`, `D-65`, `D-66`, `D-68`, `D-69`, `D-70`, `INV-4`, `INV-13`, `INV-14`, `INV-27`, `INV-55`, `INV-79`, `FE-5`, `FE-15`, `FE-30`/`INV-81`; `registrations.py`, `system_service.py`, `prefill_service.py`, `assessment_service.py`, `base.py`, `schemas/registration.py` @ the synced mirror (§0 binds HEAD).

---

## §0 Pre-flight verify checklist (live DDL / HEAD, D-21)

1. **`provenance_confidence` enum (canonical hygiene, not gating — SV-A).** `base.py` @ HEAD declares five members including `USER_PROVIDED` and `assessment_service.py` writes it, contradicting `DATA-MODEL` §5 and `PAT-8` (4-value). Resolve against live pg_enum. This sprint writes only `USER_CONFIRMED`/`USER_AMENDED` (present in every source), so it is **not** blocked; flag the `USER_PROVIDED` contradiction to the agent as a pre-existing latent issue, orthogonal to this sprint.
2. **Registration handler (SV-2 confirmed).** `registrations.py` creates the system via `system_service.create_system` (Step 1, flushes; `system.id` exists) before the derivation point, single transaction (`INV-27`), `get_tenant_db` commits at request end.
3. **`CatalogueProduct.name` reachable in the handler (B2).** Confirm `create_system`/`_derive_vendor_id` already loads the product when `catalogue_product_id` is set, so `product.name` is the `name` seed with no resolver change. `get_prefill_by_product` supplies the `operator_role_id`/`lifecycle_stage`/`hosting_model_id`/`purpose` seeds (`_build_field_prefills`, `D-70`).
4. **`PATCH /systems/{id}` shape (N3).** Confirm which provenance-bearing fields it can change (`operator_role_id`, `hosting_model_id`, `lifecycle_stage`, `purpose`, `name`) and its concurrency shape (If-Match / `PAT-6`), so the re-disposition write rides its transaction.
5. **`SystemDetail` read + audit-pack consumer (SV-B).** Confirm `SystemDetail` schema and that the register and audit pack read from it, before adding a per-field provenance projection (WI-5). Additive; verify no contract break.
6. **`FE-5`/`PrefillWithBasis`, `FE-15`/`INV-55`** provenance channel reusable for the intake affordance.
7. **Mirror ceilings (SV-C).** Bind live `D`/`INV`/`FE` ceilings and pg_catalog before mint; the mirror can lag HEAD even though floors match.

---

## Resolved decisions

| # | Settled | Authority |
|---|---|---|
| DA | Force disposition on **derived** fields only (`operator_role_id`, `lifecycle_stage`): Continue gated until each is confirmed or amended. **Catalogue-seeded** fields (`hosting_model_id`, `purpose`, `name`) take submit-as-confirmation. Rests on the obligation-load argument (`N4(b)`) and a proportionate-friction judgement, **not** a `PAT-8` base-mapping (N2: both intake bases are system-proposed defaults). | `N4(b)`, `CAT-4` |
| DB | Provenance in a dedicated tenant-scoped table `prefill_disposition`; actor + timestamp for ISO 42005 defensibility. | `CAT-4`, `INV-4` |
| DC | Both panels: intake fields (WI-1..5, WI-PATCH) and the catalogue-facts panel (WI-6, splittable). | `CAT-4`, `DF1-8` |
| DD | Ships **before S4b**. | this thread |
| B1 | `confirmed_fields` is **transient** wizard state, not in `draft_blob`; on resume, an unchanged-confirmed derived default re-gates (re-confirm), while an amended value is self-dispositioned by the value diff. WI-3/WI-6 do **not** touch the DM-S3 persist path. | `D-66`, `INV-79`, `N4(b)` |

---

## Mechanism

Provenance is **server-derived** (`PAT-8`, `INV-13`), never request input. At registration, after `create_system`, the handler derives a `ProvenanceConfidence` per system-supplied field by diffing the submitted value against its seed:

- **Catalogue-seeded** (`hosting_model_id`, `purpose` from `get_prefill_by_product`; **`name` from `CatalogueProduct.name`**, B2): submitted == seed → `USER_CONFIRMED`; else → `USER_AMENDED`. Submission is the confirmation act.
- **Derived** (`operator_role_id = deployer`, `lifecycle_stage = production`): submitted != seed → `USER_AMENDED`; submitted == seed and key in `confirmed_fields` → `USER_CONFIRMED`; submitted == seed and **not** in `confirmed_fields` → **422** (undispositioned derived default). Server-enforced, not merely client-gated.
- **No seed** (custom system, or a typed field): outside the ladder, no `prefill_disposition` row (`D-70`, `PAT-8` register-derived exemption).

The client sends the **action** (`confirmed_fields: list[str]`), never the enum; the server sets the enum, as `confirm_item` does. This does **not** reverse `D-68` rejected-(a) (re-computing the seed to diff writes no value the user did not submit) or rejected-(b) (`confirmed_fields` is an action, not a `basis`/`provenance` field; `INV-55` respected). Only `D-68`'s "server does not store which fields were seeded vs user-entered" clause is superseded (N6, WI-5).

---

## Scope (dependency-ordered)

### WI-1 · Schema: `prefill_disposition` table
Tenant-scoped, RLS (`INV-4`): `id`, `tenant_id`, `system_id` (FK `ON DELETE CASCADE`), `field_key varchar(120)`, `provenance provenance_confidence`, `actor_user_id`, `created_at`. `UNIQUE(system_id, field_key)`. **Namespace (N4):** intake fields use bare names (`operator_role_id`, `name`, ...); catalogue facts (WI-6) use a `fact:<key>` prefix, so a fact keyed `purpose` never collides with the intake `purpose`. One migration.

### WI-2 · Handler: derivation, derived-field 422 gate, disposition rows + audit
`RegistrationCreate` gains `confirmed_fields: list[str] = []` (transient; B1). In the handler after `create_system`: re-compute seeds (`get_prefill_by_product` + `CatalogueProduct.name` for `name`); derive provenance per the mechanism; **422** on any undispositioned derived default; write a `prefill_disposition` row per disposed field and stage an `AuditEvent` per field. **Action strings (N5, PAT-4):** `system.field_confirmed` / `system.field_amended`, value in `detail`. All inside the single `POST /registrations` transaction (`INV-27`); no If-Match (registration is a create).

### WI-3 · Intake confirm/amend affordance (FE-31)
Replace the `FE-30` label caption with a real affordance on `FE-5`/`PrefillWithBasis` + the `FE-15` provenance channel:
- **Derived** (operator role, lifecycle): explicit confirm control; dispositioned when confirmed or edited; **Continue disabled until every derived field is dispositioned**; confirmed keys accumulate into `confirmed_fields`; editing removes the key (value differs → server derives `USER_AMENDED`).
- **Catalogue-seeded** (hosting model, purpose, **name** — provenance now shown, closing the name gap): `FE-15` tone, editable, submit-confirmed.
- **Resume (B1):** `confirmed_fields` is not persisted; on `RESUME_FROM_DRAFT` an unchanged-confirmed derived field is un-dispositioned and re-gates. Values restore from `draft_blob` as before. No change to the DM-S3 persist path.
- Custom path (no seeds, `D-70`): no captions, no gate.

### WI-4 · Binding FE-31 specimen
Rendered specimen: derived confirm state, catalogue-seeded provenance, name provenance, Continue-gated and Continue-enabled states, resume re-gate. Agent builds to it (`INV-68`/`D-51`).

### WI-5 · `D-68` amendment + `SystemDetail` provenance surface
Amend `D-68`: supersede only the "server does not store seeded vs entered" clause; explicitly preserve rejected-(a) and rejected-(b) (N6). The rest of `D-68` (seed is the submission, `field_prefills` orthogonal to `facts`) stands. Add a per-field provenance projection to `SystemDetail` (SV-B) so the register and audit pack surface it (`CAT-4` accountability).

### WI-PATCH · `PATCH /systems` re-disposition (N3)
Drop the vague "re-written on later change." Precise rule: disposition rows are **written at registration**; a subsequent `PATCH /systems/{id}` that changes a provenance-bearing field **upserts that field's `prefill_disposition` to `USER_AMENDED`** with a `system.field_amended` audit event, riding the existing `update_system` transaction (a PATCH is an explicit act, so the change is itself the disposition; no re-gating). §0.4 confirms the PATCH concurrency shape (`PAT-6`/`INV-14`).

### WI-6 · Catalogue-facts panel disposition (DC; splittable — EA)
Make the `PrefillStep` confirm/amend **record** (reversing the recording half of `DF1-8`): fact dispositions are carried transiently through pre-boundary steps (not in `draft_blob`, B1), submitted with `RegistrationCreate`, written as `prefill_disposition` rows with `fact:<key>` keys (N4). May split to a fast-follow; `INV-82` binds it either way.

### WI-7 · Canonical update (last)
`STATE` (intake prefill disposition; provenance store; `system.field_confirmed`/`system.field_amended` audit strings, N5). `DATA-MODEL` (`+prefill_disposition`; `provenance_confidence` now on intake). Append `D-71`, `D-72`, `INV-82`, `FE-31`; amend `D-68` (WI-5). Record the S4b ID bump. Never renumber a live `INV-n`; leave the stable tier untouched.

---

## Invariants and decisions to mint (proposed)

1. **INV-82 · CONVENTION · Every system-supplied prefill or default is dispositioned before commit; provenance server-derived.** Extends `CAT-4`'s confirm/amend model from catalogue facts to intake defaults: no catalogue-seeded or system-derived intake value is silently accepted; the disposition is a server-derived `ProvenanceConfidence` in `prefill_disposition`. A user-typed field with no system default is outside the ladder. Refs: `CAT-4`, `D-1`, `PAT-8`, `INV-55`, `INV-13`.
2. **D-71 · Intake disposition model: derived forced, catalogue-seeded submit-confirmed.** Derived defaults (`deployer`, `production`) require explicit disposition (422 if an unchanged derived default is submitted without a confirm signal); catalogue-seeded values (`hosting_model_id`, `purpose`, `name`) take submit-as-confirmation. Rests on the obligation-load of the operator role (`N4(b)`) and a proportionate-friction judgement, **not** a `PAT-8` base-class mapping (N2: both intake bases are system-proposed defaults). The client sends `confirmed_fields` (action); the server derives the enum. *Rejected:* submit-as-confirmation for derived fields (thin record for an obligation-load-bearing value); forced disposition on all seeds (unwarranted friction). Refs: `N4(b)`, `CAT-4`, `PAT-8`.
3. **D-72 · Prefill provenance in `prefill_disposition`, written at registration, amended by PATCH.** Tenant-scoped table keyed `(system_id, field_key)`; value stays single-homed on the `system` row; point-in-time history is the `AuditEvent` trail. Written at registration; `PATCH /systems` re-dispositions a changed provenance-bearing field to `USER_AMENDED` (N3). *Rejected:* per-field provenance columns on `system` (N columns, no fact coverage); a `metadata_blob` map (no actor/timestamp). Refs: `CAT-4`, `INV-4`, `PAT-6`, single-home.
4. **D-68 AMENDED.** Only the "server does not store which fields were seeded vs user-entered" clause is superseded; rejected-(a) (no server-side apply) and rejected-(b) (no basis sent to server; `INV-55`) still stand (N6). Seed-is-the-submission and `field_prefills`/`facts` orthogonality stand.
5. **FE-31 · Intake confirm/amend affordance** replaces the `FE-30` caption: derived gated-confirm, catalogue-seeded submit-confirm with provenance shown, `name` in the ladder, resume re-gates. Built on `FE-5`/`INV-55`. Refs: `FE-5`, `FE-15`, `INV-81`, `INV-82`.

---

## Present-vs-ALTER summary

| Surface | Present | ALTER |
|---|---|---|
| `prefill_disposition` | none | new tenant-scoped RLS table, `UNIQUE(system_id, field_key)`, `fact:` namespace for facts |
| `RegistrationCreate` | no disposition signal | `+ confirmed_fields: list[str]` (transient, not in `draft_blob`) |
| registration handler | creates system, no provenance | `+` server-derived provenance (name diffed vs `CatalogueProduct.name`), derived 422 gate, disposition rows + `system.field_confirmed`/`_amended` audit |
| `PATCH /systems` | changes fields, no provenance | `+` re-disposition changed field → `USER_AMENDED` + audit |
| `provenance_confidence` usage | `assessment_item` | extended to intake fields |
| intake UI | `FE-30` label caption | `FE-31` confirm/amend affordance; Continue gated on derived disposition; resume re-gates |
| `name` field | seeded client-side, no provenance | in the ladder, diffed vs `CatalogueProduct.name`, provenance shown and recorded |
| `PrefillStep` (facts) | amend presentational (`DF1-8`) | dispositions recorded, `fact:` keys (WI-6, splittable) |
| `SystemDetail` | no provenance | `+` per-field provenance projection (WI-5) |
| `D-68` clause | "server does not store seeded vs entered" | superseded (only that clause) |
| `draft_blob` | pre-boundary wizard fields | **unchanged** (dispositions deliberately excluded, B1) |

---

## Appendix A — Open decisions

| ID | Decision | Recommendation |
|---|---|---|
| EA | WI-6 (catalogue-facts panel) in-sprint vs fast-follow. | Keep in-sprint if the scope stays manageable; else split. `INV-82` binds it either way; intake is the founder-observed surface. |
| EB | `SystemDetail` provenance projection: full per-field map now, or register/audit-pack surface only. | Per-field map on `SystemDetail`; register and audit pack read from it. Pending SV-B. |

Recorded forward: `N4(b)` is discharged for the derived operator role (its confirmation is now recorded); the `eu_operator_role` new-role check stays an `OPEN-3` concern. The `USER_PROVIDED` enum contradiction (SV-A) is flagged to the agent as pre-existing, orthogonal to this sprint.

---

## Appendix B — Source-verification register

| SV | Claim | Verify against | Blocks |
|---|---|---|---|
| SV-A | `provenance_confidence` membership (`base.py` declares 5 incl. `USER_PROVIDED`; DATA-MODEL/`PAT-8` say 4). Canonical hygiene, not gating. | live pg_enum, `base.py`, `assessment_service.py` @ HEAD | none (design uses only `USER_CONFIRMED`/`USER_AMENDED`) |
| SV-B | `SystemDetail` schema and register/audit-pack read from it. | `schemas/system.py`, export/audit-pack service @ HEAD | WI-5/EB |
| SV-C | Live `D`/`INV`/`FE` ceilings and pg_catalog before mint (mirror may lag). | HEAD DECISIONS/INVARIANTS/FRONTEND, live DB | WI-7 mint |
| SV-D | `CatalogueProduct.name` loaded in the handler for the `name` diff (B2). | `system_service.py` @ HEAD | WI-2 name provenance |
| SV-E | `PATCH /systems` provenance-bearing fields and concurrency shape (N3). | `systems.py` router, `update_system` @ HEAD | WI-PATCH |

---

*Handoff cut as the paired file; FE-31 specimen delivered alongside.*