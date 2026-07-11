# DM-S1 — Context Relocation — Final Design Doc

**Status:** FINAL (review folded) · backend-led + transitional frontend thread · **handoff held for one nod on the N1 isolation call (below), then issues** · ids from live floors → D-63, D-64, INV-76, INV-77, DF-D1-1..4 · delta: 1 migration, reader cutover (corrected set), write retarget, feeder retarget, **0 classifier change**.

**Review disposition:** B1 (feeder consumers) and B2 (wizard thread) accepted, folded into the reader set and cutover with done-checks. N2/N3 folded. A1/N4 closed. **N1 (isolation) resolved as a call flagged for the founder** (DB-enforced RLS on the new tables) — the one item worth your eye before handoff.

**Scope (one thing):** relocate `usage_context_id`, `human_oversight_type_id`, and the data-category / affected-party links from `system` to `use_case`; `operator_role_id`, `hosting_model_id`, `lifecycle_stage`, and the catalogue link stay. **Not in scope:** atomic registration / orphan closure (DM-S2), draft staging (DM-S2), recognition / uniqueness (DM-S3), the wizard restructure, the F2/F6 detail record, the prefill rework.

**Fidelity, not a classifier change (P-2, confirmed):** the tier resolves per use case from `resolve_classification` (product bridge) plus the context gate (`answers_blob`); none of the four feed it. **The agent must not wire these into `resolve_classification`.**

---

## §0 — Pre-flight verify checklist (binding; grep-first, then plan; D-21)

| id | Verify (live) | Gates |
|---|---|---|
| P-0 (canary) | HEAD; floors D ≥ 62, INV ≥ 75, FE ≥ 27. | ID baseline. |
| **P-1 (run FIRST, drives the cutover)** | Grep `usage_context_id`, `human_oversight_type_id`, `SystemDataCategory`, `SystemAffectedParty`, `data_categories`, `affected_parties`, `system_data_category`, `system_affected_party` across `app/` and `apps/tenant/`. **Confirm the corrected reader set below is complete** — it now includes `assessment_service` (DPIA/FRIA feeder snapshots + DPIA applicability) and the wizard (`wizard-state.ts`, `use-case-create-step.tsx`), the two B1/B2 readers the first draft missed. Any hit not in the cutover stops the sprint. | "nothing stranded" (now true). |
| P-2 | `resolve_classification` + context gate read none of the four. | 0 classifier change. |
| P-3 | `prefill_service` catalogue-only. | reader closure. |
| P-4 | `SystemRead` lean (no four). | reader closure. |
| P-5 | Existing-data shape: rows in the system join tables; systems carrying the two FKs; use-case count per such system. | backfill. |
| P-6 | Code-confirm the access path for the new join tables and the live RLS posture of the system ones (DATA-MODEL §5 open item, N1). | INV-77 / isolation. |
| P-7 | Confirm MODEL_RISK feeder reads `system.catalogue_product_id` (stays on system), so only DPIA/FRIA are affected. | B1 blast radius. |

---

## Resolved decisions

| # | Decision | Rationale / rejected |
|---|---|---|
| D-63 | **Use-distinguishing context relocates to the use case.** `usage_context`, `human_oversight`, data categories, affected parties → use case; `operator_role`, `hosting_model`, `lifecycle_stage`, catalogue link stay. | Per-use-case context fidelity (OPEN-INTAKE-D). **Rejected:** duplicate-at-use-case; keep-on-system. |
| D-64 | **`[NEW]` Isolation on the new join tables is DB-enforced (N1).** `use_case_data_category` / `use_case_affected_party` carry `tenant_id` + an RLS policy, rather than replicating the parent-key, no-`tenant_id` convention of `system_data_category` / `assessment_item_control` whose isolation DATA-MODEL §5 flags as unresolved and MODELS.md §2.1 calls "not defensible" for app-code-only enforcement. **Founder call flagged (below).** **Rejected:** parent-key convention + code-confirm + mint an access-path invariant (consistent with the codebase, but keeps isolation in app code, which is the weaker posture for a compliance product). Out of scope: retrofitting the existing link tables; DATA-MODEL §5 stays open for those. |
| INV-76 | **`[NEW]` CONVENTION** — use-distinguishing context (`usage_context`, `human_oversight`, data categories, affected parties) lives and is read/written at use-case level; deployment-stable facts (`operator_role`, `hosting_model`, `lifecycle_stage`) at system level. The classifier reads neither set for tiering. | Single-home; the spine. |
| INV-77 | **`[NEW]` CONVENTION** — `use_case_data_category` / `use_case_affected_party` are tenant-scoped with DB-enforced RLS (`tenant_id` + policy). | DB-enforced isolation (D-64). |
| DF-D1-1 | **Clean cut.** No production data; move data and drop the system columns/tables in-sprint with the reader cutover. | Dual-home avoided. |
| DF-D1-2 | **Transitional capture location.** The four stay captured in `intake-capture-step`, threaded via `wizard-state.ts` to the `use-case-create-step` write; DM-S2 moves capture to the use-case step. | Keeps intake working; clearly temporary. |
| DF-D1-3 | **Backfill copies system → each use case** (lossless by construction; A1 closed, N4). | Use case inherits its system's recorded context until edited. |
| DF-D1-4 | **`[NEW]` Feeder applicability becomes per-use-case (N3).** DPIA/FRIA pre-fill and DPIA applicability derive from the use case's own categories, not the system union. | The correct, intended behaviour of the relocation; recorded, not silent. |

> **N1 founder call (the one thing to confirm before handoff):** D-64 makes the new join tables DB-enforced (`tenant_id` + RLS) rather than copying the existing parent-key convention. This is the compliance-defensible answer and the moment to set it, at the cost of being inconsistent with the older link tables (whose isolation is itself flagged open). If you would rather keep convention-consistency and instead code-confirm + mint an access-path invariant, say so and I will swap D-64/INV-77. Recommendation: DB-enforced.

---

## The migration (schema)

Add to `use_case`: `usage_context_id`, `human_oversight_type_id` (FK, nullable, SET NULL). New `use_case_data_category` / `use_case_affected_party` — **with `tenant_id` + RLS (D-64/INV-77)**, unique pair per use case. Backfill system → each use case (DF-D1-3). Drop `system.usage_context_id`, `system.human_oversight_type_id`, and `system_data_category` / `system_affected_party` (DF-D1-1). Alembic; the down-path is a **best-effort dev reversal, not a true inverse** (N2: per-use-case rows cannot losslessly re-aggregate to one system row once use cases diverge).

## Reader and writer cutover (corrected set; dependency-ordered)

1. **Models** — `UseCase` gains the two FKs + `data_categories` / `affected_parties` relationships (new `UseCaseDataCategory` / `UseCaseAffectedParty`, tenant-scoped); `System` loses all four.
2. **Schemas** — `SystemCreate` / `SystemUpdate` drop the four; `SystemDetail` drops the four (now use-case-level); the use-case create/update/read schemas gain them (resolved `VocabItemOut` / `DataCategoryOut` / `AffectedPartyOut` on read). `SystemRead` unchanged (P-4).
3. **`system_service`** — `create_system` / `update_system` stop writing the four; `_load_system_full` drops the two `selectinload`s; `_build_detail` / `get_system_detail` stop assembling them; `_replace_data_categories` / `_replace_affected_parties` move to the use-case service, rekeyed on `use_case_id`, setting `tenant_id`.
4. **Use-case service** — create/update writes the two FKs and replaces link rows on the use case (with `tenant_id`).
5. **`assessment_service` (B1) — the designed retarget.** The DPIA feeder snapshot reads `UseCaseDataCategory` (was `SystemDataCategory where system_id`); the FRIA snapshot reads `UseCaseAffectedParty`; `source_ref` strings change to `use_case_data_category:{id}` / `use_case_affected_party:{id}`; **DPIA applicability recomputes from the use case's own categories** (`has_special_category` / `has_data_category` / else NOT_APPLICABLE) per DF-D1-4. MODEL_RISK reads `system.catalogue_product_id` (stays), so it is untouched (P-7).
6. **`export_service`** — `_use_case_record` sources the four from the use case; `build_system_export` / `get_system_detail` no longer carry them at system level.
7. **Frontend (transitional, B2/DF-D1-2)** — `intake-capture-step` drops the four from the `SystemCreate` body and writes them into wizard state; **`wizard-state.ts` carries the four; `use-case-create-step.tsx` adds them to the `POST /v1/use-cases` body**; `SystemDetailClient` moves the four to per-use-case display.
8. **Classifier** — untouched (P-2).

## Done-checks (tied to the two blockers)

- **Feeder (B1/DF-D1-4):** a use case with a special-category data category → its DPIA feeder pre-fills items from `use_case_data_category` and DPIA applicability resolves to required-with-special-category-basis; a use case with no data categories → DPIA NOT_APPLICABLE. FRIA pre-fills from `use_case_affected_party`. `source_ref` uses the new strings. Existing feeder tests retargeted.
- **Wizard (B2):** a full intake run (system step → use-case step) lands the four on the **created use case**, asserted end-to-end; the stripped `SystemCreate` rejects the four (or omits them) without breaking the run.
- **Isolation (D-64):** a cross-tenant read of `use_case_data_category` under the wrong tenant context returns nothing (RLS), asserted like the parent tables.

## What does NOT change

`resolve_classification`, the context gate, `prefill_service`, `SystemRead`, MODEL_RISK feeder, the catalogue, the lifecycle/gates. Per-use-case classification already works.

---

## Appendix A — Open decisions

- **A1 — CLOSED (N4):** backfill is lossless by construction (no per-use-case divergence can exist pre-migration; the fields only live at system level today).
- **A2:** the four write on use-case **create** in DM-S1; an explicit use-case **edit** path rides DM-S2 / the prefill rework. Confirmed: create-only now.

## Appendix B — Source-verification register

P-0 canary, **P-1 grep-first (now the cutover's driver, corrected set incl. `assessment_service` + wizard)**, P-2 classifier non-read, P-3 prefill, P-4 `SystemRead`, P-5 existing-data, P-6 isolation/access-path (resolves DATA-MODEL §5 for the new tables), P-7 MODEL_RISK blast radius.

## Appendix C — Canon-update note (for the handoff)

STATE: intake writes deployment-stable facts only; use-distinguishing context on the use case; `SystemDetail` drops the four; **DPIA/FRIA feeder pre-fill and DPIA applicability now per-use-case (DF-D1-4), a recorded behavioural change**; classifier unchanged. DATA-MODEL: drop the four from `system` + the two system join tables; add the two FKs to `use_case` + `use_case_data_category` / `use_case_affected_party` **with `tenant_id` + RLS**; **note the existing link-table isolation question (§5) remains open for the older tables, resolved here only for the new ones**. Append D-63, D-64, INV-76, INV-77, DF-D1-1..4. Never renumber a live id; stable tier untouched.

**Handoff issues once the N1 call is confirmed.**