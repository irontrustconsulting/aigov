# sprints/UI-F1-INTAKE.md — Tenant Intake / Registration Wizard

**Execution-only.** Rationale lives in the UI-F1-INTAKE design doc (v0.2). Plan-mode: propose edits before applying. **Zero backend / zero migrations / no `DATA-MODEL` change** — pure wire-up over landed S1/S2/S5 routes + `UI-F0` shared packages. Tenant app only. No new `FE-n` (FE-11/12 candidates dropped as F1-local / FE-7 duplicates — design doc N-2). Honour `INV-3`, `INV-13`, `INV-50`, `INV-25`, `INV-26`, `D-1`, `D-7`, `UX-1..6`, `FE-3..9`.

Route contracts verified against live routers/schemas in project knowledge (`use_cases.py`, `classification_context.py`, `systems.py`, `reference.py`, `lifecycle.py`, `schemas/{system,use_cases,classification}.py`); §0 confirms against repo HEAD per `D-21`.

---

## §0 — pre-flight verify (run first; do not build past a failure)

- [ ] **0.1** Repo HEAD matches the pasted routers/schemas (no drift in path, gate, request/response since paste). Confirm `app/main.py` registers `reference, systems, use_cases, classification_context, lifecycle, me` under `/v1`.
- [ ] **0.2** `schemas/reference.py` field shapes for `ProductCategoryRead`, `VendorRead`, `ProductRead` (the only consumed schemas not yet inspected) — type the contract off these, not assumptions.
- [ ] **0.3** Confirm **no** `POST /v1/use-cases/{id}/advance` and **no** `GET /v1/systems/{id}/approval-status` route exists (C-1/C-3). If either appears at HEAD, stop and re-cut — the wizard's lifecycle model assumes their absence.
- [ ] **0.4** Confirm `UI-F0` packages present and importable: `@irontrust/tokens` (`@theme`, `[data-theme]`), `@irontrust/ui` (`SodAction`, prefill-with-basis, 412/409 banners, whose-court scaffold), `@irontrust/api-client` (`useLiveState`, BFF-only fetch, client-`tenant_id`/`provenance` guard), `apps/tenant` BFF proxy + session middleware.
- [ ] **0.5** Live DB: `eu_ai_act_tier` and `classification_status` enum labels are uppercase-by-name (`MODELS.md §2.8` footgun); the client renders enum **values** returned by the API, never reconstructs labels.

---

## Consumed routes (canonical contract)

| Step | Method · Path | Gate | Request | Response | Branch key |
|---|---|---|---|---|---|
| Drill-down | `GET /v1/reference/product-categories[?parent_id]` | anon | — | `ProductCategoryRead[]` | tree depth |
| Drill-down | `GET /v1/reference/product-categories/{cat}/vendors` | anon | — | `VendorRead[]` | — |
| Drill-down | `GET /v1/reference/product-categories/{cat}/products[?vendor_id]` | anon | — | `ProductRead[]` | — |
| Drill-down | `GET /v1/reference/products/{id}` | anon | — | `ProductDetailOut` | — |
| Intake | `POST /v1/systems` | system_owner | `SystemCreate` | `SystemDetail` (201) | — |
| Prefill | `GET /v1/systems/{id}/prefill` | member | — | `PrefillResponse` | `facts` empty ⇒ no panel |
| UC create | `POST /v1/use-cases` | system_owner | `UseCaseCreate` | `UseCaseWithClassification` (201) | `classification.requires_context`, `classification.tier`, `use_case.state` |
| Override (gate-1) | `POST /v1/use-cases/{id}/classify/override` | system_owner | `OverrideRequest` | `UseCaseWithClassification` | — |
| Context Qs | `GET /v1/use-cases/{id}/classification/context` | any gov role | — | `ClassificationContextRead` | `residual_questions` |
| Context preview | `POST /v1/use-cases/{id}/classification/context/preview` | any gov role | `PreviewRequest` | `ContextOutcomeRead` | `kind` |
| Context submit | `POST /v1/use-cases/{id}/classification/context` | system_owner, contributor | `ComputeRequest` | `ComputeResultRead` (201) | `outcome.kind`, `classification.status` |
| Whose-court | `GET /v1/use-cases/{id}/lifecycle` | any gov role | — | `UseCaseLifecycleRead` | `blocking.{responsible_party,reason_code,reason}` |

**Not consumed in F1:** `POST .../classification/sign-off` (reviewer, assurance face); `POST /lifecycle/re-evaluate` (manual lever, off happy path); any assessment/evidence/coverage/export route.

**`SystemCreate` server guards to mirror client-side (structural, pre-submit — not caught as 422):** `is_custom` ⊕ (`catalogue_product_id` | `catalogue_vendor_id`); vocab FK ids must be `active`; `owner_user_id` must be a tenant member. Vendor is derived from product server-side — client never sends `catalogue_vendor_id` when a product is chosen.

**Two Classification read projections (type both off one canonical view in the contract package):** gate-1 `ClassificationRead` = `{tier, rationale, version, is_current, overridden, proposed_tier, basis_subcategory_code, basis_legal_ref, requires_context}` (no `status`); gate-2 `ClassificationStatusRead` = `{tier, status, overridden, proposed_tier, basis_subcategory_code, basis_legal_ref, rationale, version, is_current, …}` (no `requires_context`).

---

## Lifecycle model the UI must encode (no client mutation of state)

- Every classification write auto-advances server-side, atomic with the write (`C-1`). The wizard reads state; it never drives it.
- Branch precedence after `POST /v1/use-cases`, on the create response:
  1. `classification.requires_context == true` → **context gate** (owner's court — drive the sub-surface; do **not** read lifecycle court here, it mislabels as `reviewer`).
  2. else `classification.tier == "prohibited"` (and `use_case.state == "halted_prohibited"`) → **terminal hard-stop** render; no advance control.
  3. else (concrete tier) → **resolved**; fetch `GET /lifecycle` and render whose-court from `blocking` (often `authoriser`/vendor-product when catalogue-linked, or `user`/create-AIIA).
- Context-gate sub-surface (when 1):
  - `GET .../context` → render `residual_questions` (`FE-4`, `legal_ref` as basis).
  - answer → `POST .../context/preview` → show `ContextOutcomeRead` before commit (`UX-4`/`D-1`); `kind == "UNRESOLVED"` → render `missing`, collect remainder, re-preview (loop).
  - commit → `POST .../context` → `201`; `kind == "PROHIBITED_HALT"` → terminal hard-stop; else `classification.status == "pending_review"` → whose-court **reviewer** (sign-off out of F1).
  - `override_tier` control is **system_owner-only**: render **absent** for a bare `contributor` (`FE-8`, role-capability bar — not act-SoD); a `contributor` `200/no-snapshot` UNRESOLVED is normal, a 403 means an override slipped through and must not be reachable in the UI.
- **Tier/basis display reads the snapshot** (`ClassificationRead.tier` / `ClassificationStatusRead.tier` + `basis_*`), **never** `use_case.eu_tier` (`C-2`/`V-2`: unratified on the context path).
- `FE-6` is dormant: **no** consumed F1 route accepts `If-Match`; do not send it.

---

## Work items (dependency-ordered; done-checks tie to concrete tests)

**WI-1 · FE-3 adoption-skin tokens.** Resolve palette, type-scale, spacing/elevation/radius for the tenant adoption skin in `@irontrust/tokens` as `@theme` custom properties under the tenant `[data-theme]`; AA contrast baked; no literal values (eslint `no-literal-token-value`). Operator skin untouched (sibling theme, same primitives).
*Done:* axe contrast pass on a sample wizard screen; eslint clean; operator app renders unchanged.

**WI-2 · Contract types.** In `@irontrust/api-client`, type every Consumed-routes row off `schemas/*` (incl. `schemas/reference.py` per 0.2). Encode one canonical `Classification` view and derive the gate-1 (`requires_context`) and gate-2 (`status`) projections from it. Runtime+compile guard already forbids client `tenant_id`/`provenance` (`INV-3`/`INV-13`) — assert it covers `SystemCreate`/`UseCaseCreate`/`ComputeRequest`.
*Done:* type-check passes against recorded fixtures of each response; a test asserting a client-supplied `tenant_id`/`provenance` is rejected at the client boundary.

**WI-3 · Query/mutation hooks (BFF only).** TanStack Query hooks through the BFF proxy for all reads; mutations (`POST /systems`, `POST /use-cases`, `classify/override`, `context`, `context/preview`) via BFF (`FE-9`). Lifecycle + classification reads use `useLiveState` (`staleTime:0`, invalidate-and-refetch after each write — `FE-7`). No `If-Match` on any F1 hook.
*Done:* network assertion that no browser→API call bypasses the BFF (`INV-50`); after `POST /use-cases`, the lifecycle query refetches (no cached verdict).

**WI-4 · Drill-down step.** Category tree (`parent_id` drill), vendors, products, product detail. **"Not in catalogue / in-house"** branch → set `is_custom=true`, skip prefill. (Catalogue-miss curation signal is **out of F1** — `CAT-8` deferred, design doc N-3; do not emit and do not imply it is met.)
*Done:* drill renders against seeded taxonomy; empty taxonomy returns `[]` cleanly; custom branch carries `is_custom` into WI-5.

**WI-5 · Intake capture.** `FE-4` structured set: single-selects (operator_role/hosting_model/usage_context/human_oversight_type), multi-selects (data_categories/affected_parties), `lifecycle_stage` (`SystemLifecycleStage`), `purpose` (contained free-text, last resort). Mirror the `is_custom ⊕ catalogue` bar structurally; submit `POST /v1/systems` → hold `SystemDetail`.
*Done:* a `is_custom=true` + product selection is unreachable in the UI; successful create returns `SystemDetail` and routes to WI-6.

**WI-6 · Prefill confirm/amend.** `GET /systems/{id}/prefill`; `FE-5` prefill-with-basis per `CatalogueFactOut` (provenance badge from server, `source_label`/`source_url`/`last_checked_at` as basis). **Display-only / no write-back** (DF1-8): "amend" is presentational and does not persist; the structured WI-5 fields are the capture of record. `facts == []` (custom / no product) → panel absent, never an error.
*Done:* custom system shows no panel and no error; a catalogue system renders facts with provenance badges; no mutation is issued from this step.

**WI-7 · Use-case create + outcome branch.** `POST /v1/use-cases {system_id,title,purpose,context_blob}`; branch per the lifecycle model above. Resolved-tier branch offers the gate-1 **override ladder** (`FE-5`): `classify/override {tier, subcategory_code, justification}` with `tier`/`subcategory` as structured picks (server 422s on unknown subcategory or tier≠subcategory.tier — prevent both client-side). Render tier + basis reasoning-first (`UX-4`) from the snapshot.
*Done:* PROHIBITED create renders terminal hard-stop with `state==halted_prohibited` and no advance control; a HIGH bridge create renders tier+basis and an override control; override to a mismatched tier is unreachable.

**WI-8 · Context-gate sub-surface.** Only when `requires_context`. `GET context` → `FE-4` questions; `preview` confirm-before-commit; UNRESOLVED `missing` loop; `submit` → `PENDING_REVIEW` (or PROHIBITED_HALT terminal). `override_tier` control absent for non-system_owner (`FE-8`).
*Done:* an UNRESOLVED preview re-prompts `missing` and issues no write; a resolved submit lands `PENDING_REVIEW` and routes whose-court to reviewer; a PROHIBITED_HALT submit renders terminal; contributor never sees the override control.

**WI-9 · Whose-court handoff.** `GET /v1/use-cases/{id}/lifecycle`; promote the `UI-F0` scaffold indicator to render `blocking.responsible_party` + `reason` (`UX §5` legible state). Terminal for F1. (This is also where vendor/product clearance surfaces — `responsible_party == authoriser` — replacing the dropped approval-status badge, `C-3`.)
*Done:* a catalogue-linked, unapproved use case shows "with the authoriser (vendor/product clearance)"; a bridge-resolved, no-vendor-link use case shows "with you (start the assessment)"; a context-path PENDING_REVIEW shows "with the reviewer."

**WI-10 · Role-aware render pass (`FE-8`).** Server-authoritative roles via `GET /v1/me` (`D-24`, never token claims). system_owner: full spine. contributor: context preview/submit only — create-system/create-use-case/override **absent** (role-capability bar). reviewer/authoriser/auditor reaching the surface: assurance read, capture controls absent. Bare contributor entry → "needs a system owner" empty-state, not a dead control.
*Done:* per-role snapshot tests match the design-doc matrix; every absent control is also server-rejected if forced (assert one 403/structural rejection per barred control).

**WI-11 · a11y + concurrency assertions + tests.** WCAG 2.1 AA: axe pass + manual keyboard pass per surface; visible focus; semantic structure (`FRONTEND §4`). Assert `FE-6` dormancy: no F1 hook sends `If-Match`. Enumerated tests: the three create branches (prohibited/resolved/requires-context), the UNRESOLVED loop, the override 422-prevention, the empty-prefill custom path, the no-token-in-browser network assertion.
*Done:* axe clean on every wizard surface; keyboard-only completes the full spine; the enumerated tests pass.

**WI-12 · Canonical update (last).** Update `STATE` (add the F1 intake-wizard surface under the UI section; note approval-status endpoint absent / clearance via lifecycle vector; note `POST /advance` does not exist). Append to `DECISIONS`: DF1-3 (sign-off out), DF1-4 (catalogue-fact-only prefill), DF1-5 (`If-Match` dormant in F1), DF1-8 (prefill display-only/no write-back). **No new `FE-n`** (FE-11/12 candidates dropped — F1-local / FE-7 duplicate). **No `INVARIANTS` append** unless WI-10's structural-bar assertions surface a genuinely new convention. Volatile tier only; `FRONTEND.md` and the rest of the stable tier untouched this sprint; never renumber a live id.
*Done:* `STATE`/`DECISIONS` reflect the above; `git diff` touches no stable-tier canonical; no live id renumbered.

---

## Invariants honoured (existing — review checklist)

`INV-50` (BFF-only, no browser token) · `INV-3` (no client tenant_id) · `INV-13` (provenance server-derived; client renders, never authors) · `INV-25` (live state recomputed, never cached as settled) · `INV-26`/`D-7` (prohibition supreme — UI surfaces, never gates) · `D-1`/`UX-2`/`UX-4` (strong default → shown basis → tracked override) · `UX-1` (capture-once; gates only when the owner's act is needed) · `UX-5`/`FE-8` (SoD/role bars visible; backend remains authority) · `D-24` (roles from server context, not token).