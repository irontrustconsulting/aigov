# DM-S4b — Sprint Handoff (EXECUTION ONLY)

Rationale lives in `DM-S4b-intended-use-envelope-design-FINAL.md`. Execution-only; work items dependency-ordered. Do not originate visual/UX decisions (INV-68/D-51); build the use-case step to the FE-30/FE-31 pattern, flag and stop if a visual choice is unspecified.

**Entry floors:** `D-70` · `INV-81` · `FE-30`. **Mint at close:** `D-71`, `D-72`, `D-73`, `INV-82`, `FE-31`.

---

## §0 — Pre-flight (block on these before writing)

- [ ] **0.1 (GATING)** `assessment.py`: `Classification.status` default is `PENDING_REVIEW`. `classification.py::snapshot_classification` passes no `status` and unconditionally sets `use_case.eu_tier` + `eu_ai_act_subcategory_id`. `sign_off_classification` gates on `status == PENDING_REVIEW`. Record before touching the writer.
- [ ] **0.2 (GATING)** `domain.py::UseCase` declares `purpose: Mapped[str | None]` (column is `use_case.purpose`). `use_case_purpose` appears only as the `RegistrationCreate` field.
- [ ] **0.3 (GATING)** Grep `purpose` (not `use_case_purpose`) across: `RegistrationCreate`, `UseCaseCreate`, `UseCaseRead` (server + `packages/api-client`), F3/F4 page-test fixtures, AIIA register-fact snapshot (PAT-8). Confirm export pack (`UseCaseExportSectionsRead`) has no purpose field. Data check: existing non-null `use_case.purpose` rows acceptable to lose.
- [ ] **0.4 (GATING)** `use_cases.py`: `POST /use-cases` calls `resolve_classification`→`snapshot_classification`; `UseCaseCreate` has no category field. This path stays unchanged.
- [ ] **0.5** `schemas/use_cases.py`: `ClassificationRead` carries `requires_context`, not `status`; `UseCaseWithClassification.classification` carries `status`.
- [ ] **0.6** `classification` column set for the `off_label` add; `use_case.eu_ai_act_subcategory_id` exists.
- [ ] **0.7** `product_category_membership`, `product_category_eu_mapping.is_primary`, `_TIER_ORDER`; wizard steps `use-case-resolved`/`context-gate`/`whose-court`.

---

## WI-1 — Schema: `use_case.product_category_id`
Add `use_case.product_category_id uuid NULL` (FK `product_category.id`, `ON DELETE SET NULL`, indexed).
**Done:** migration up/down; column nullable; FK resolves; existing rows null.

## WI-2 — `resolve_classification` declared-category-aware, backward-compatible
Read `use_case.product_category_id`. Non-null → governing = declared category's `is_primary` mapping, compute product-wide-highest, set `disposition = AUTHORITATIVE` (governing tier == highest) or `DOWN_SELECTION` (< highest); declared category with no primary mapping → tier `REQUIRES_CONTEXT`. Null → today's product-wide-highest, `disposition = AUTHORITATIVE`. Add `disposition: ClassificationDisposition = AUTHORITATIVE` (defaulted) to `ClassificationProposal`. Pure; no writes.
**Done:** service tests — declared==highest → AUTHORITATIVE; declared<highest → DOWN_SELECTION; declared unmapped → REQUIRES_CONTEXT; null → product-wide-highest AUTHORITATIVE (byte-identical to pre-sprint for a null case); `override_classification` construction compiles unchanged (default disposition).

## WI-3 — Product-to-categories read
Add `GET /v1/catalogue/products/{id}/categories` → memberships. Gate: any tenant member; no audit.
**Done:** returns a product's categories; empty list for a product with none; contract in `packages/api-client`.

## WI-4 — Parametrize the writer; branch persistence in the registration handler
Add to `snapshot_classification`: `status: ClassificationStatus = PENDING_REVIEW`, `stamp_eu_tier: bool = True` (defaults preserve all callers). Registration handler branches on the WI-2 result: `tier == REQUIRES_CONTEXT` → gate-2 seam (set `off_label` if "Other", WI-5); `AUTHORITATIVE` → `snapshot_classification(status=APPROVED, stamp_eu_tier=True)`; `DOWN_SELECTION` → `snapshot_classification(status=PENDING_REVIEW, stamp_eu_tier=False)`.
**Done:** tests — AUTHORITATIVE snapshot is `APPROVED` with `eu_tier` stamped; DOWN_SELECTION snapshot is `PENDING_REVIEW` with `eu_tier` NOT stamped and `sign_off_classification` then stamps it; `POST /use-cases` and `override` unchanged (default params → prior behaviour, existing tests green).

## WI-5 — Typed `off_label`
Add `classification.off_label boolean NOT NULL DEFAULT false`. Registration handler sets `off_label=true` when the system has `catalogue_product_id` and `intended_use_category_id` is null ("Other"); routes `REQUIRES_CONTEXT`. Add `off_label` to `ClassificationHistoryEntryRead` (renders in register, audit pack, `AtoDocumentRead.current_classification_summary`).
**Done:** migration; existing rows backfill `false`; "Other" registration yields `off_label=true` + REQUIRES_CONTEXT; a declared membership category yields `off_label=false`; `POST /use-cases`/custom yields `off_label=false`; export projection carries it in all three render surfaces.

## WI-6 — Drop `use_case.purpose`; contract and wizard
After §0.3, drop `use_case.purpose` (destructive migration). `RegistrationCreate`: `+ intended_use_category_id: uuid | null`, `− use_case_purpose`. `UseCaseCreate`/`UseCaseRead` (server + `packages/api-client`): drop `purpose`. Sweep F3/F4 fixtures. Wizard use-case step (`FE-31`): membership-constrained `SingleSelect` (via WI-3) + "Other / not listed" (→ null); remove the free-text purpose control.
**Done:** migration up/down; grep shows no live `use_case.purpose` reader; tenant + api-client suites green after fixture sweep; wizard renders the category select and "Other"; custom path shows "Other"/context.

## WI-6b — `ClassificationRead` gains `status`
Add `status: ClassificationStatus` to `ClassificationRead`; regenerate the contract. Wizard post-registration branch: `requires_context` → `context-gate`; else `status == pending_review` → `whose-court`/review; else → `use-case-resolved`.
**Done:** response-schema test asserts `status` present; wizard branches correctly for each of the three dispositions (AUTHORITATIVE, DOWN_SELECTION, Other).

## WI-7 — Canonical update (last)
`STATE` (declared-category gate-1 refinement, review-routed down-selection, off-label, `use_case.purpose` dropped, `POST /use-cases` preserved, writer parametrized). `DATA-MODEL` (`+use_case.product_category_id`, `+classification.off_label`, `−use_case.purpose`). Append `D-71`, `D-72`, `D-73`, `INV-82`, `FE-31`. Amend the API-ROUTES gate-1-projection note (`ClassificationRead` now carries `status`). Record the `snapshot_classification` parametrization and the `POST /use-cases` preserved-scope decision. Never renumber a live `INV-n`; leave the stable tier untouched. Record any `DF-S4b-n`.
**Done:** STATE/DATA-MODEL/API-ROUTES reflect HEAD; appended IDs are next free slots; no stable-tier edit.

---

## Global done-check
Backend suite, `pnpm --filter tenant test`, and `@irontrust/api-client` typecheck green. The diff touches: 1 migration; `classification.py` (`resolve_classification`, `snapshot_classification`, `ClassificationProposal`); the registration handler; `schemas/use_cases.py` (`ClassificationRead +status`, drop `purpose`), `schemas/registration.py`; `catalogue` router (new read); `domain.py` (drop `use_case.purpose`, add `product_category_id`); `assessment.py` (`classification.off_label`); `schemas/export.py` (`ClassificationHistoryEntryRead +off_label`); wizard step + `wizard-state`; `packages/api-client`; canon files. `POST /use-cases` and `override_classification` diffs are limited to signature-compatible call sites, with their existing tests unchanged and green.