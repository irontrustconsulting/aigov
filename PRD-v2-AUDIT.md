# PRD-v2 Canon & Codebase Audit

Source of authority: `docs/PRD-v2.md` (v2.0, supersedes all prior PRDs). Every finding below traces a place where a canon doc or the shipped code has not yet caught up to PRD-v2 — mostly concentrated in Appendix A "Change record," Appendix B "Open items," and Appendix C "Source verification."

Method: seven parallel research passes, one per canon area, each reading PRD-v2 in full, reading its assigned canon doc(s) in full, then spot-verifying the highest-stakes claims against the live code (models, services, routers, migrations, frontend components). Findings are marked **doc-only drift** (the code already matches PRD-v2 or the gap is purely descriptive) or **real code/schema gap** (the thing PRD-v2 now requires does not exist or actively contradicts it). Severity: **blocking** (M-priority MVP requirement, actively contradicted or absent) / **major** / **minor**.

---

## 0. Cross-cutting findings (surfaced independently across most canons)

These are the load-bearing issues — each was found by multiple audit passes working from different docs, which is itself the strongest evidence they're real rather than an artifact of one doc's phrasing.

### 0.1 Clearance order is still vendor-outermost, not use-case-outermost — **blocking, real code gap**
PRD-v2 APR-1..7 / Appendix A.3 / **Appendix C SV-5** (which explicitly flags this as needing verification) require the use-case gate to be outermost, with vendor vetting demoted to a step inside product approval, never a standalone gate. The audit confirms SV-5 is true: the shipped state machine is still vendor → product → intake.

- `app/services/lifecycle_service.py` `_ADVANCE_TABLE`: `REQUESTED → VENDOR_CHECK → PRODUCT_CHECK → INTAKE → ...`
- `app/services/lifecycle_gates.py::vendor_gate` (~L59-74) and `::product_gate` (~L77-92): two independent, sequential gates, vendor strictly before product.
- No use-case-level clearance object exists anywhere in `app/models/domain.py` — matches PRD-v2's own **Appendix B O-6** ("use-case gate object has no home in the current clearance model").
- Shipped UI (`UI-F10-CLEARANCE`, `apps/tenant/app/clearances/_components/clearance-queue-list.tsx:63-76`) renders `vendors.map(vendor => <VendorSection>)` with products nested under vendors — no use-case dimension anywhere in the surface.
- Documented as correct-and-current in `DOMAIN.md` §5, `REQUIREMENTS.md` APR-1..3, `INV-86`–`INV-92` (esp. `INV-88`, which codifies "product's clearance disabled until parent vendor is APPROVED"), `DECISIONS.md` D-15/D-17, `STATE.md:41`, `API-ROUTES.md:110-124`.

This is a foundational reversal that touches the state machine, the `VendorApproval`/`ProductApproval` model shape, six-plus invariants, two decisions, and a shipped UI surface — not a find-and-replace doc fix.

### 0.2 Risk scoring methodology (SCR-1..13) is essentially unbuilt — **blocking, real code/schema gap**
PRD-v2 raised this to MVP-core in Appendix A.2 ("Recovered"). **Appendix C SV-3** ("no scoring, banding, or criticality logic exists at HEAD") is confirmed true:

- `AssessmentItem` (`app/models/assessment.py:225-241`) has only free, nullable `likelihood`/`severity`/`residual_likelihood`/`residual_severity` integers, hand-authored via `amend_item` — no `exposure` axis, no `Inherent = L×I×E`, no `Residual = Inherent × (1−CE)`, no 0.90 effectiveness cap, no persisted score or band enum (Low/Moderate/High/Critical).
- No risk-domain field (technical/data/operational/legal/ethical — RSK-5), no scope field (system-relevant vs org-level — RSK-7), no protected-harm tag (RSK-8), no seeded default L/I/E (RSK-6) on `Risk` (`app/models/knowledge.py:87-106`). The existing `RiskLayer` enum (`TECHNICAL_SECURITY`/`GOVERNANCE_RIGHTS`/`ADVERSARIAL_THREAT`) is a different taxonomy that doesn't map onto PRD-v2's 5-value domain set.
- No `PATTERNS.md` shape exists for "methodology as data" (SCR-11) either — nothing to misdescribe, it's a genuine gap at every layer (schema, service, pattern, doc).

### 0.3 Treatment is not yet a distinct propose-and-ratify phase — **blocking/major, real code gap**
PRD-v2 Appendix A.3 moved treatment from "a gate inside the AIIA flow, pre-review" to "a distinct phase after AIIA approval, propose-and-ratify" (LFC-8, TRT-1..13).

- `treatment_gate` (`app/services/lifecycle_gates.py:283-341`) only checks that `treatment_decision` is set plus a control-link or rationale string. No risk-owner confirmation step (TRT-2), no round trip to a Compliance Officer/authoriser (TRT-4), no band check — **a Critical or protected-harm risk can be ACCEPTed today with just a rationale string**, directly contradicting TRT-8/TRT-9's hard stops.
- `TreatmentDecision` enum (`app/models/base.py:191-198`) has `AVOID`/`TRANSFER` present but commented "reserved for post-MVP" — stale relative to PRD-v2 now making all four `M`.
- No `INV-n` covers this gate's missing band/protected-harm check — a genuine invariant hole, not just a stale one.
- `UX.md` §5's per-surface list has no Treatment entry at all, not even a placeholder — `grep -i treatment` across UX/PLATFORM-UX/FRONTEND returns nothing.

### 0.4 Residual risk is authored prose, not computed — **blocking, real code gap**
PRD-v2 ATO-3/ATO-4 ("computed, never authored... no narrative basis... comment field never required, never gating") reverses the old model. The old model is still live:

- `DECISIONS.md` **D-10** locks in "`residual_risk_statement` is authored on the ATO by the authoriser."
- `INVARIANTS.md` **INV-29** states this as the current, correct rule.
- The shipped UI enforces it: `apps/tenant/app/use-cases/[id]/_regions/authorise-panel.tsx:20-44` — a `<textarea>` labelled "Residual risk statement," `aria-required="true"`, gating the "Grant authorisation" button on non-empty text. This is the literal shape ATO-3/4 now forbid, already in production.

### 0.5 Three MVP-must objects don't exist at all: Exceptions, Applicability layer, Statement of Applicability
- **EXC-1..6** (exceptions): no model/route/service anywhere (`grep` for "exception" outside Python `except` keywords returns nothing). Missing from `STATE.md`'s deferred register — not even flagged as pending. **Blocking build gap; minor doc-completeness gap** (should at least be named as absent).
- **CTL-4** (applicability layer): absent, but `STATE.md:404` already lists it honestly under §3 deferred, referencing `OPEN-3`. Priority under PRD-v2 changed (deferred → MVP) but the doc is self-aware. **Major build gap; no doc fix needed beyond re-flagging priority.**
- **SOA-1..6** (Statement of Applicability): no model/route anywhere; not even in `STATE.md`'s deferred register (silent omission, not flagged). **Blocking build gap; minor doc-completeness gap.**
- **RRG-2/3** (organisation-level risk register, raised to MVP-core): absent; not in `API-ROUTES.md` §4 "confirmed absent" either. **Blocking build gap; minor doc-completeness gap.**

### 0.6 INDEX.md is internally inconsistent about its own ID ceiling
PRD-v2's own **Appendix C SV-6** warns "the index lags the repository." The audit found this is concretely true today: `INDEX.md`'s "Current scope" narrative tail correctly states the ceiling as `INV-94`/`D-82`/`FE-37` (matching the real last-appended `D-82` in `DECISIONS.md`), but `INDEX.md`'s separate, earlier **"## ID scheme"** block still reads `INV-1..83`, `D-1..75`, `FE-1..32`, `OPEN-1..4` — 11 INV ids, 7 D ids, 5 FE ids, and `OPEN-5` behind the narrative tail, in the same file. **Major, doc-only, and directly actionable** (a single bump pass fixes it).

---

## 1. `DOMAIN.md` + `REQUIREMENTS.md`

| # | Finding | PRD-v2 | Canon | Type | Severity |
|---|---|---|---|---|---|
| 1 | Vendor-outermost clearance vocabulary (§5 table) | APR-1..4, A.3 | `DOMAIN.md` §5; `app/models/domain.py:348` `VendorApproval` docstring "outer gate" | real code gap | blocking (= §0.1) |
| 2 | No SCR section anywhere in `REQUIREMENTS.md` | §8.11 | — | real code gap (nothing to describe) | blocking (= §0.2) |
| 3 | Vocabulary inversion: `UseCase` is a child row of `System`, not an org-wide "cleared once" object; no distinct `Product`/`AISystem` split | A.3 "Vocabulary"; §7.1 | `app/models/domain.py:154` `System`, `:199` `UseCase`; `DOMAIN.md` §2/§3; `REQUIREMENTS.md` REG-1/2 | real design gap — containment direction is inverted, not just renamed | major |
| 4 | Whole requirement sections missing: TRT, RRG, EXC, CTL-4 (full), SOA (own section), ATO (only a stub), AIA, XCUT-2..5 | §8.12-8.21, Appendix A.2/A.3 | `REQUIREMENTS.md` (absent) | doc-only, layered on real build gaps tracked separately | major |
| 5 | Classification framed as blurred with registration rather than "first step of assessment" | CLS-1, A.3 | `DOMAIN.md` §4/§6; `REQUIREMENTS.md` REG-2 | doc-only wording | major |
| 6 | Glossary says TRANSFER/AVOID "reserved" — code already has all four active | TRT-3 | `DOMAIN.md` §2; `app/models/base.py:194-198` | doc lags in the safe direction | minor |
| 7 | Five-role SoD model already matches PRD-v2 (no Consultant, correct conflict pair) | WKF-1/5, A.4 | `DOMAIN.md` §7, `REQUIREMENTS.md` WKF-1/5 | **no drift** — confirmed aligned | — |

## 2. `ARCHITECTURE.md` + `PATTERNS.md`

| # | Finding | PRD-v2 | Canon | Type | Severity |
|---|---|---|---|---|---|
| 1 | No pattern for "methodology as data" | SCR-11, NFR-6 | `PATTERNS.md` (PAT-1..10, none fit; PAT-5 is the closest analog but covers classification only) | real gap, nothing built to pattern | blocking (= §0.2) |
| 2 | No pattern for the applicability layer; `coverage_service.py` docstring points at a non-existent `docs/APPLICABILITY_DESIGN.md` | CTL-4 | `PATTERNS.md` (absent); `app/services/coverage_service.py:1-11` | real gap + dangling doc pointer | blocking (= §0.5) |
| 3 | GLOBAL-corpus list in `ARCHITECTURE.md` §6 omits "methodology defaults and seeded impacts" (doesn't exist yet) and doesn't explicitly name the bridge/risk-control cross-map as GLOBAL; conversely lists "governance-role catalogue + conflict matrix" as GLOBAL when PRD-v2 §6.3 doesn't include roles in GLOBAL corpus at all (WKF-10: roles are tenant-scoped) | §6.3 | `ARCHITECTURE.md:113` | doc-only plane-model mismatch | major |
| 4 | `TreatmentDecision` enum has AVOID/TRANSFER commented "reserved for post-MVP" | TRT-3 | `app/models/base.py:191-198` | real code gap (= §0.3) | major |
| 5 | `RiskLayer` taxonomy (`TECHNICAL_SECURITY`/`GOVERNANCE_RIGHTS`/`ADVERSARIAL_THREAT`) doesn't match RSK-5's five-domain set; no seeded defaults, no protected-harm tag, no scope field | RSK-5..8 | `app/models/base.py:89-93`, `app/models/knowledge.py:87-110` | real schema gap (= §0.2) | major |
| 6 | `RiskControlMap.strength` correctly implements a strength qualifier, correctly *not* numeric (SCR-13 weighting is out-of-MVP-scope, `S`-priority) | SV-4, SCR-13 | `app/models/knowledge.py:131` | **no drift** — confirmed aligned | — |

## 3. `DATA-MODEL.md`

| # | Finding | PRD-v2 | Canon | Type | Severity |
|---|---|---|---|---|---|
| 1 | No exposure, control_effectiveness, risk_band, or inherent-score columns anywhere; `AssessmentItem` has only raw likelihood/severity ints | SCR-1..12 | `DATA-MODEL.md` §1/§2/§4 (silent); `app/models/assessment.py:225-241` | real schema gap (= §0.2, confirms SV-3 literally) | blocking |
| 2 | `Risk` table missing domain, scope, protected-harm tag, seeded L/I/E defaults; existing `risk_layer` enum is a different, incompatible taxonomy | RSK-5..8 | `DATA-MODEL.md` §1/§2 (silent); `app/models/knowledge.py:87-106` | real schema gap | blocking |
| 3 | Treatment fields bolted onto the identification-phase `assessment_item` row — no decision-maker/ratifier actors, no decision/ratification/target dates, no status, no proposed-vs-final split (TRT-13's full shape) | TRT-4, TRT-13 | `DATA-MODEL.md` (line 76, silent); `app/models/assessment.py:255-258` | real schema gap (= §0.3) | blocking |
| 4 | No Exception, applicability-rule, or SoA-state tables anywhere in the 53-table inventory, and none flagged as absent | EXC / CTL-4 / SOA | `DATA-MODEL.md` §1 (silent) | real schema gap + doc silence (= §0.5) | blocking |
| 5 | `use_case` table implements PRD-v2's "AI System" (carries `state`/`eu_tier`), not PRD-v2's "Use case" (abstract, org-wide, cleared once) — the rename/split in Appendix A.3 and open item O-6 isn't surfaced anywhere in `DATA-MODEL.md` | §7.1, A.3, O-6 | `DATA-MODEL.md:40` | doc silence on a real, PRD-acknowledged-open design question | major |
| 6 | `Evidence` model missing `type`, `description`, `confidentiality` (EVD-3); `AssessmentItemEvidence` and `assessment_review` have no per-item attestation column (EVD-5) | EVD-3, EVD-5 | `app/models/lifecycle.py:35-58`; `app/models/assessment.py:303-323` | real schema gap, undocumented | major |
| 7 | GLOBAL/tenant plane tags for risk/control/catalogue libraries correctly align with §6.3/XCUT-3 | §6.3, XCUT-3 | `DATA-MODEL.md` | **no drift** — confirmed aligned | — |

## 4. `INVARIANTS.md`

| # | Finding | PRD-v2 | Canon | Type | Severity |
|---|---|---|---|---|---|
| 1 | `INV-26`/`INV-33` gate prohibition per-registration off the current use-case's classification snapshot, not organisation-wide once per use-case-type | LFC-3 | `INV-26`, `INV-33` | real gap, tied to O-6 | blocking |
| 2 | `INV-86`–`INV-92` (esp. `INV-88`) codify vendor-before-product as the *correct* shipped model | APR-3/4 | `INV-86..92` | real code gap (= §0.1) | blocking, needs rewrite alongside the reorder |
| 3 | `INV-29` states residual risk is authored on the ATO by the authoriser | ATO-3/4 | `INV-29` | real code gap (= §0.4) | blocking |
| 4 | No invariant covers `treatment_gate`'s missing band/protected-harm check — a Critical or protected-harm risk can be ACCEPTed with just a rationale string today | TRT-8, TRT-9 | missing | real gap, genuinely unenforced hard stop | blocking |
| 5 | Zero invariant coverage for exceptions, including EXC-4 (critical/protected-harm never exception-clearable) | EXC-1..6 | missing | real gap (likely unbuilt, per §0.5) | major |
| 6 | No invariant states the exact WKF-3 conflict-matrix pairs (only that a matrix table exists, and generic reviewer≠submitter/authoriser≠approver checks) | WKF-3 | `INV-48`, `INV-7`, `INV-28`, `INV-71` | doc gap, matrix likely correct as seed data but unpinned | minor |
| 7 | ATO-6 (new AIIA version invalidates ATO) partially covered; `INV-44` admits the referenced assessment state is "never reconstructed until AIIA versioning exists" | ATO-6, AIIA-1 | `INV-37`, `INV-44` | partial, needs AIIA-1 versioning check before closing | minor |
| 8 | No invariant states WKF-8's authoriser triad (risk acceptance, risk-ownership confirmation, SoA confirmation) together | WKF-8 | missing | doc gap | minor |
| 9 | AVOID's missing terminal lifecycle state has no invariant, but PRD-v2 itself flags this as open (O-4) | TRT-10 | missing | self-acknowledged open, no action beyond tracking | minor |

## 5. `DECISIONS.md` (+ `INDEX.md`'s ID-scheme block)

| # | Finding | PRD-v2 | Canon | Type | Severity |
|---|---|---|---|---|---|
| 1 | `D-17`/`D-15` lock in vendor-outermost clearance | APR-1/3, A.3, SV-5 | `D-17`, `D-15` | real code gap (= §0.1) | blocking |
| 2 | `D-10` locks in authored (not computed) residual risk | ATO-3/4, A.3 | `D-10` | real code gap (= §0.4) | major (not yet built per SV-3, but the on-file design intent is wrong) |
| 3 | `D-65` makes registration+classification one atomic transaction — PRD-v2 now separates them (classification is assessment's first step) | CLS-1, A.3 | `D-65` (DM-S2, shipped) | real, shipped schema/transaction shape | blocking |
| 4 | No existing `D-n` ever asserted a nine-role model / Consultant role / questionnaire engine / treatment-as-pre-review-gate — nothing to reverse for those A.4 retirements | A.4 | — | **no drift** | — |
| 5 | Appendix B open items O-1, O-3, O-5, O-7, O-8 have no existing `OPEN-n` counterpart — genuinely new | Appendix B | `DECISIONS.md` OPEN register | doc gap, straightforward to open | major (methodology-blocking, Founder-owned) |
| 6 | O-2 is adjacent to but distinct from `D-28`/`OPEN-3` (coverage-matrix denominator vs SCR-6 partial-state weighting) — flag adjacency, don't treat as duplicate | O-2 | `D-28`, `OPEN-3` | doc gap, needs care not to conflate | minor |
| 7 | O-4 (AVOID's terminal state) overlaps but isn't identical to `OPEN-1` (void/withdraw of a worked assessment) — needs cross-reference, not a blind new entry | O-4 | `OPEN-1` | doc gap | minor |
| 8 | O-6 (use-case gate object) is directly evidenced by finding §0.1 above — should be opened and `D-17`'s reversal drafted together | O-6 | — | real gap, tie to §0.1 | major |
| 9 | `INDEX.md`'s "## ID scheme" block is stale relative to its own "Current scope" narrative tail in the same file (11 INV / 7 D / 5 FE ids behind, missing `OPEN-5`) — a live instance of the exact risk SV-6 warns about | SV-6 | `INDEX.md` | doc-only, directly actionable | major |

## 6. `API-ROUTES.md` + `STATE.md`

| # | Finding | PRD-v2 | Canon | Type | Severity |
|---|---|---|---|---|---|
| 1 | Vendor/product gates confirmed vendor-outermost in both docs, accurately describing the (wrong) shipped shape | APR-1..7, SV-5 | `STATE.md:41`, `API-ROUTES.md:110-124` | real code gap (= §0.1), docs are honest | blocking |
| 2 | Scoring engine absent; `STATE.md` correctly doesn't overclaim it | SCR-1..13 | `STATE.md` (silent, accurate) | real code gap (= §0.2) | blocking |
| 3 | Treatment gate lacks propose-and-ratify; `STATE.md:41` accurately describes current shape ("written via `amend_item`, provenance-neutral") | TRT-1..13 | `STATE.md:41` | real code gap (= §0.3), doc is honest | major |
| 4 | Organisation-level risk register absent from code, `STATE.md`, and **not listed in `API-ROUTES.md` §4 "confirmed absent"** | RRG-2/3 | `API-ROUTES.md` §4 (silent) | real gap + doc completeness gap | blocking (build) / minor (doc) |
| 5 | Exception management absent from code, `STATE.md`, and `API-ROUTES.md` §4 | EXC-1..6 | `API-ROUTES.md` §4 (silent) | real gap + doc completeness gap | blocking (build) / minor (doc) |
| 6 | Applicability layer absent but already honestly flagged in `STATE.md:404` deferred register (OPEN-3) — only the priority label changed | CTL-4 | `STATE.md:404` | real gap, doc already accurate | major (build) / none (doc) |
| 7 | SoA absent from code and from `STATE.md`'s deferred register entirely (silent omission, not even flagged) | SOA-1..6 | `STATE.md` (silent) | real gap + doc completeness gap | blocking (build) / minor (doc) |
| 8 | §10.2 out-of-scope retirements (Consultant role, questionnaire builder, workflow engine, tenant risk-tolerance policy) — no scope creep found, nothing built that needs removing | §10.2 | — | **no drift** — clean | — |
| 9 | Everything else in §10.1's in-scope list spot-checked (multi-tenancy/RLS, 5 roles + SoD, inventory, catalogue + 4 prefill states, taxonomy + bridge, classification, AIIA identification+feeders, evidence + per-item attestation, review/sign-off, ATO, audit pack/trail, versioning, AI-assistance labelling) matches `STATE.md` with no drift | §10.1 | `STATE.md` | **no drift** | — |

## 7. `UX.md` + `PLATFORM-UX.md` + `FRONTEND.md`

| # | Finding | PRD-v2 | Canon | Type | Severity |
|---|---|---|---|---|---|
| 1 | No dual plain/formal label map exists — the one label-map module in the codebase (`FE-16`, `packages/ui/src/status/verdict-label-map.ts`) maps each value to a single register, applied identically regardless of role. `UX.md` UX-3 describes reachability ("one layer down"), not a role-conditioned dual map; `FRONTEND.md` has no FE-n for it | XCUT-2 | `UX.md` UX-3; `FRONTEND.md` (absent) | real gap + doc gap on requirement shape | major |
| 2 | Authoriser role is seeded and rendered as literal "Authoriser," not "Compliance Officer / Manager" — a raw, untranslated backend value reaching the user (also an XCUT-5 violation) | WKF-2, XCUT-5 | `data/seed/governance_roles.yaml:37-43`; `apps/tenant/app/members/_components/role-panel.tsx:92,105,114` | real code gap, undocumented as a requirement anywhere in UX docs | blocking |
| 3 | Treatment-as-distinct-phase has zero presence in `UX.md` §5's per-surface list — not even a placeholder; `grep -i treatment` across all three docs returns nothing | §7.2 step 8, LFC-8 | `UX.md` §5 (silent) | doc-only, but consequential (forthcoming-work tracking gap) (= §0.3) | major |
| 4 | Clearance UI (`UI-F10-CLEARANCE`) renders strictly vendor→product, no use-case dimension — confirms SV-5 at the UI layer too | APR-1/3, SV-5 | `apps/tenant/app/clearances/_components/clearance-queue-list.tsx:63-76` | real code gap (= §0.1) | blocking |
| 5 | Authorise panel has a required, gating free-text "Residual risk statement" textarea — the exact shape ATO-3/4 now forbid, live in production, undocumented anywhere as intentional | ATO-3/4 | `apps/tenant/app/use-cases/[id]/_regions/authorise-panel.tsx:20-44` | real code gap (= §0.4) | blocking |

---

## Suggested next step

Per this repo's own closure discipline (`CLAUDE.md` "Sprint closure"), none of this should be silently patched into `docs/` — it needs to become explicit sprint-scoped work: new `D-n` entries recording each PRD-v2 reversal (never editing `D-10`/`D-15`/`D-17`/`D-65` in place), new `OPEN-n` entries for PRD-v2's O-1/O-3/O-5/O-7/O-8, an `INDEX.md` ID-scheme bump pass, and a design pass on the clearance-order reversal (§0.1) before any code changes — it's the one finding that's both foundational and already reflected in shipped UI, so it carries real migration cost.
