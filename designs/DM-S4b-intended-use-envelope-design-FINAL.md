# DM-S4b — Intended-Use Category, Envelope Triage, and Gate-1 Governing-Subcategory Refinement (FINAL)

**Status:** FINAL · review folded (B1-B5, N1-N4, SV-a/c carried) · handoff cut as paired file. Touches the classifier and the shared classification writer (stable-tier service): a second review pass on this final is advisable before execution given the surface grew past the proposal envelope.
**Floors at entry:** `D-70` · `INV-81` · `FE-30`. **Target ceilings (proposed, append-only):** `D-71`, `D-72`, `D-73` · `INV-82` · `FE-31`.
**Delta envelope (revised by review):** schema **+2 columns** (`use_case.product_category_id`, `classification.off_label`) **−1 column** (`use_case.purpose`, dropped) · `snapshot_classification` **+2 defaulted params** (`status`, `stamp_eu_tier`) · `resolve_classification` **declared-category-aware, backward-compatible** · `ClassificationProposal` **+`disposition`** (defaulted) · `ClassificationRead` **+`status`** (crosses the gate-1-projection convention) · `RegistrationCreate` **+`intended_use_category_id`, −`use_case_purpose`** · **1 read** (product→categories) · migration **1** (2 adds, 1 drop) · export `ClassificationHistoryEntryRead` **+`off_label`** (additive).
**Grounded against:** `classification.py::{resolve_classification,snapshot_classification,ClassificationProposal}`, `context_classification.py`, `assessment.py::Classification`, `domain.py::UseCase`, `schemas/use_cases.py`, `schemas/registration.py`, `schemas/export.py`, `use_cases.py`, API-ROUTES @ the synced mirror (§0 binds HEAD).
**Out of scope:** applicability/obligation layer (`OPEN-3`), `N4(b)`, ISO SoA. `D-64` untouched.

---

## §0 Pre-flight verify checklist (live DDL / HEAD, D-21)

1. **Writer behaviour (GATING, B1/B2).** Confirm `Classification.status` ORM default is `PENDING_REVIEW` (`assessment.py`), that `snapshot_classification` passes no `status` and unconditionally stamps `use_case.eu_tier` and `eu_ai_act_subcategory_id` (`classification.py`), and that `sign_off_classification` gates solely on `status == PENDING_REVIEW`. WI-4 parametrizes the writer against exactly this.
2. **Column name (GATING, B3).** Confirm `domain.py::UseCase` declares `purpose: Mapped[str | None]` (the column is `use_case.purpose`), and that `use_case_purpose` appears only as the `RegistrationCreate` input field; `UseCaseCreate`/`UseCaseRead` expose it as `purpose`.
3. **`purpose` consumer sweep (GATING, B3/N4).** Grep `purpose` on use-case reads/writes, not `use_case_purpose`: `RegistrationCreate` (input), `UseCaseCreate`, `UseCaseRead`, `packages/api-client` `UseCaseRead`, F3/F4 page-test fixtures (`purpose: "Automated screening"`), and the AIIA register-fact snapshot (PAT-8, SV-b). Export pack confirmed clear (`UseCaseExportSectionsRead` has no purpose field; `SystemDetail.purpose` is system-level, untouched). Data check: existing non-null `use_case.purpose` rows acceptable to lose (drop is irreversible).
4. **Second call site (GATING, B5).** Confirm `POST /use-cases` (`use_cases.py`) auto-derives via `resolve_classification`→`snapshot_classification`, and that `UseCaseCreate` has no category field. WI-2's backward-compatible null path preserves it.
5. **Wire projection (B4).** Confirm `ClassificationRead` (gate-1 projection in `RegistrationRead`) carries `requires_context`, never `status`, and that `UseCaseWithClassification.classification` already carries `status` (fixture-confirmed). WI-6b adds `status` to `ClassificationRead`.
6. **`classification` columns.** Confirm the snapshot column set for the `off_label` add; confirm `use_case.eu_ai_act_subcategory_id` already exists (stamped by `snapshot_classification`).
7. **`product_category` / bridge.** Confirm `product_category_membership`, `product_category_eu_mapping.is_primary`, and `_TIER_ORDER` (`PROHIBITED > HIGH > LIMITED > MINIMAL`) for the down-selection comparison.
8. **Wizard steps.** Confirm `use-case-resolved`, `context-gate`, `whose-court` steps for the disposition branch (`wizard-state.ts`).

---

## Resolved decisions

| # | Settled | Authority |
|---|---|---|
| R-1 | Intended-use category is a use-case-level field, anchored on `product_category` (DD), constrained to the product's memberships, plus explicit "Other / not listed". | this thread; `taxonomy.py` |
| R-2 | The governing subcategory follows the declared category's primary mapping, not product-wide highest, when a category is declared. | `D-8`, `INV-10` |
| R-3 | `D-64` stands: the intended-use category is the `product_category` axis, not a context field. | `D-64` |
| R-4 | Envelope is triage, not gate; off-label recorded via typed `classification.off_label` (DC), never blocked. Rationale stands on `D-72`, not `D-59` (N3). | `D-72` |
| R-5 | `use_case.purpose` (column) is dropped (B3), replaced by the structured category. | this thread |
| R-6 | Down-selection is review-routed (DA): `PENDING_REVIEW`, no `eu_tier` stamp, reviewer sign-off. | `D-4`, `D-9` |
| R-7 | Ship whole (DE). | this thread |
| R-8 | `POST /use-cases` is preserved unchanged (B5): no declared category → today's product-wide-highest, auto-stamp, `off_label=false`. `UseCaseCreate` is **not** extended this sprint. | `D-71`, B5 |
| R-9 | `N4(b)` not consumed by S4b (guards `OPEN-3`). | `D-68`, `OPEN-3` |

---

## Scope (dependency-ordered; whole, DE)

### WI-1 · Schema: use-case intended-use category
Add `use_case.product_category_id uuid NULL` (FK `product_category.id`, `ON DELETE SET NULL`, indexed).

### WI-2 · `resolve_classification` declared-category-aware, backward-compatible
Read `use_case.product_category_id`:
- **Non-null** (declared): governing = declared category's `is_primary` mapping; also compute product-wide-highest (retained query) for comparison. `disposition = AUTHORITATIVE` if governing tier **==** product-wide-highest, else `DOWN_SELECTION` (declared tier **<** highest). Declared category with no primary mapping → tier `REQUIRES_CONTEXT`.
- **Null** (no declaration; `POST /use-cases`, legacy): today's product-wide-highest path unchanged; `disposition = AUTHORITATIVE`; `REQUIRES_CONTEXT` when no product / no primary mappings.
`ClassificationProposal` gains `disposition: ClassificationDisposition = AUTHORITATIVE` (defaulted, so `override_classification`'s direct construction is untouched — N1). Resolution stays pure (`INV-11`). `REQUIRES_CONTEXT` continues to be signalled by `tier`, not `disposition`.

### WI-3 · Product-to-categories read
`GET /v1/catalogue/products/{id}/categories` → the product's `product_category` memberships. Gate: any tenant member; no audit. Feeds the membership-constrained select.

### WI-4 · Parametrize the writer; branch persistence in the registration handler (B1/B2/DA)
`snapshot_classification` gains `status: ClassificationStatus = PENDING_REVIEW` and `stamp_eu_tier: bool = True` — **defaults preserve every existing caller byte-for-byte** (`POST /use-cases`, override). The registration handler branches:
- `tier == REQUIRES_CONTEXT` → gate-2 seam (no bridge snapshot); if the cause is "Other" (WI-5), set `off_label`.
- `disposition == AUTHORITATIVE` → `snapshot_classification(..., status=APPROVED, stamp_eu_tier=True)`.
- `disposition == DOWN_SELECTION` → `snapshot_classification(..., status=PENDING_REVIEW, stamp_eu_tier=False)`; reviewer sign-off via the existing `sign_off_classification` stamps `eu_tier` (`D-9`).
This makes `AUTHORITATIVE` (APPROVED, stamped) and `DOWN_SELECTION` (PENDING_REVIEW, unstamped) distinguishable on both `status` and `eu_tier`, closing B1. Resolution/persistence stay separated (`INV-11`). Scoped consequence: the registration-declared-authoritative path writes `APPROVED` while the untouched `POST /use-cases` product-wide path keeps its current `PENDING_REVIEW`; correcting the standalone path is a deliberate non-goal this sprint.

### WI-5 · Typed `off_label` (DC); "Other" is a registration-handler interpretation (B5)
Add `classification.off_label boolean NOT NULL DEFAULT false`. At registration, "Other" = product present (`catalogue_product_id` not null) and no membership category selected (`intended_use_category_id` null); the handler sets `off_label=true` and routes `REQUIRES_CONTEXT` (gate-2). A null `product_category_id` reached via `POST /use-cases`/legacy is **not** off-label (no declaration, `off_label` stays default false) — this is why `resolve` does not itself infer "Other". Surface `off_label` additively on `ClassificationHistoryEntryRead`, which renders in the register, audit pack, **and** `AtoDocumentRead.current_classification_summary` (N2). Full assessment proceeds; nothing blocked (R-4).

### WI-6 · Drop `use_case.purpose`; registration contract and wizard (B3, N4, FE-31)
Drop `use_case.purpose` (destructive; §0.3 sweep + data check first). `RegistrationCreate` gains `intended_use_category_id: uuid | null` and drops `use_case_purpose`; `UseCaseCreate`/`UseCaseRead` (server and `packages/api-client`) drop `purpose`; F3/F4 fixtures swept. Wizard use-case step (`FE-31`) renders a membership-constrained `SingleSelect` (via WI-3) plus explicit "Other / not listed" (maps to null); free-text purpose removed. Custom systems present no membership set → "Other"/context path.

### WI-6b · `ClassificationRead` gains `status` (B4)
Add `status: ClassificationStatus` to `ClassificationRead` (the gate-1 projection embedded in `RegistrationRead`). The wizard post-registration branch: `requires_context` → `context-gate`; else `status == pending_review` → `whose-court`/review (down-selection); else (`approved`) → `use-case-resolved`. This deliberately crosses the documented "gate-1 projection carries `requires_context`, never `status`" convention; recorded in the canonical update (WI-7).

### WI-7 · Canonical update (last)
`STATE` (gate-1 declared-category refinement, review-routed down-selection, off-label, `use_case.purpose` dropped, `POST /use-cases` preserved, writer parametrized). `DATA-MODEL` (`+use_case.product_category_id`, `+classification.off_label`, `−use_case.purpose`). Append `D-71`, `D-72`, `D-73`, `INV-82`, `FE-31`. **Amend the API-ROUTES gate-1-projection note** (`ClassificationRead` now carries `status`). Record the `snapshot_classification` parametrization and the `POST /use-cases` preserved-scope decision. Never renumber a live `INV-n`; leave the stable tier's rules intact.

---

## Invariants and decisions to mint (proposed)

1. **D-71 · Governing subcategory is selected per use case from its declared intended-use category (when declared).** Gate-1 resolves from the declared `product_category`'s primary mapping; a null declaration falls through to today's product-wide-highest (preserving `POST /use-cases`). Aligns gate-1 with `D-8`/`INV-10`; the category is the `product_category` axis, not a `D-64` field. `use_case.purpose` dropped as its redundant predecessor. Refs: `D-8`, `INV-10`, `D-64`, B5.
2. **D-72 · Envelope is triage, not gate; off-label is recorded, not blocked.** "Other" (product present, no membership picked) routes to gate-2 with `classification.off_label=true` recorded and surfaced (register, audit pack, ATO doc). Stands on its own rationale, not `D-59` (N3). *Rejected:* blocking off-envelope registration. Refs: `D-59` (principle only), `R-4`.
3. **D-73 · Down-selection is a reviewable act.** A declared category below the product-wide-highest writes `PENDING_REVIEW` with no `eu_tier` stamp (`snapshot_classification(status=PENDING_REVIEW, stamp_eu_tier=False)`); reviewer sign-off stamps. *Rejected:* auto-stamping a user-lowered tier (inverts `D-4`/`D-9`). Refs: `D-4`, `D-9`, B1/B2.
4. **INV-82 · CONVENTION · Gate-1 governing subcategory derives from the declared intended-use category.** `resolve_classification` selects the governing subcategory from `use_case.product_category_id` when set and returns a `disposition`; null falls through to product-wide-highest; no resolvable mapping → `REQUIRES_CONTEXT`. Locus: `app/services/classification.py`. Refs: `D-71`, `INV-10`, `INV-11`.
5. **FE-31 · Intended-use category select replaces free-text purpose.** Membership-constrained `SingleSelect` (via WI-3) plus explicit "Other / not listed"; free-text purpose removed; wizard branches on `requires_context`/`status`. Refs: `FE-30`, `INV-81`, `R-5`, B4.

---

## Present-vs-ALTER summary

| Surface | Present | ALTER |
|---|---|---|
| `use_case` | no `product_category_id`; `purpose` column | `+ product_category_id uuid NULL`; `− purpose` (B3) |
| `classification` | no off-label | `+ off_label boolean NOT NULL DEFAULT false` |
| `snapshot_classification` | no `status` param; always stamps | `+ status=PENDING_REVIEW`, `+ stamp_eu_tier=True` (defaults preserve callers) |
| `resolve_classification` | `system_id`; product-wide-highest | declared-category-aware; null → product-wide-highest (preserved) |
| `ClassificationProposal` | no disposition | `+ disposition=AUTHORITATIVE` (defaulted, N1) |
| gate-1 persistence (registration only) | always PENDING_REVIEW + stamp | per disposition: APPROVED+stamp / PENDING_REVIEW+no-stamp / gate-2 |
| `POST /use-cases` | product-wide auto-stamp | **unchanged** (B5, R-8) |
| `ClassificationRead` | `requires_context`, no `status` | `+ status` (B4; convention crossing) |
| `RegistrationCreate` | `use_case_purpose` | `+ intended_use_category_id`; `− use_case_purpose` |
| `UseCaseCreate`/`UseCaseRead` (+ api-client) | carry `purpose` | drop `purpose` |
| export `ClassificationHistoryEntryRead` (register, audit, ATO doc) | no `off_label` | `+ off_label` (N2) |

---

## Appendix A — Open decisions

None open. Folded review findings: B1/B2 (writer parametrized), B3 (`use_case.purpose` corrected), B4 (`ClassificationRead.status`), B5 (`POST /use-cases` preserved, `resolve` backward-compatible), N1 (`disposition` defaulted field), N2 (off-label on ATO doc), N3 (`D-72` stands alone), N4 (sweep `purpose`). Recorded forward: `N4(b)` pending for `OPEN-3`.

---

## Appendix B — Source-verification register

| SV | Claim | Verify against | Blocks |
|---|---|---|---|
| SV-1 | `Classification.status` default `PENDING_REVIEW`; `snapshot_classification` no-`status`, unconditional stamp; `sign_off` gates on `PENDING_REVIEW`. | `assessment.py`, `classification.py` @ HEAD | WI-4 (confirmed in review) |
| SV-2 | Column is `use_case.purpose`; `use_case_purpose` is the `RegistrationCreate` field only. | `domain.py`, `schemas/*` @ HEAD | WI-6 (confirmed) |
| SV-3 | Full `purpose` consumer set incl. api-client, F3/F4 fixtures, AIIA register-fact snapshot (PAT-8); export clear. | `schemas/*`, `export_service.py`, `assessment_service.py`, fixtures @ HEAD | WI-6 |
| SV-4 | `POST /use-cases` uses `resolve`→`snapshot`; `UseCaseCreate` has no category field. | `use_cases.py`, `schemas/use_cases.py` @ HEAD | WI-2/WI-4 (confirmed) |
| SV-5 | `ClassificationRead` lacks `status`; `UseCaseWithClassification.classification` carries it. | `schemas/use_cases.py` @ HEAD | WI-6b (confirmed) |
| SV-a | `ClassificationHistoryEntryRead` field set and assembly; `off_label` clean additive from the `Classification` row. | `schemas/export.py`, `export_service.py` @ HEAD | WI-5 |
| SV-b | Every writer of `use_case.purpose` (notably AIIA register-fact snapshot, PAT-8) to size the drop. | `registrations.py`, `assessment_service.py` @ HEAD | WI-6 |
| SV-c | Vocabulary collision: `catalogue_product.intended_use` (D-69, seeds `System.purpose`) vs the use-case `product_category_id` framed as "intended-use category" (FE-30 caption vs FE-31 select). | DATA-MODEL, FRONTEND @ HEAD | FE-31 wording |

---

*Handoff cut as the paired file. Given the review expanded the classifier-touch surface (shared-writer parametrization, `ClassificationRead` contract field), a second review of this final before execution is advisable.*