# Product Lifecycle, Gates & Approvals — Backend Design Proposal (v2)

**Feature:** The orchestrating spine (LFC-1..6, APR-1..3/5, IXN-2/4, REG-3) — a determinate state machine over the fixed use-case lifecycle, deterministic gates that read captured facts and advance / park / halt, per-tenant vendor & product approval records, and the status/portfolio surface that tells a user where each use case is, why, and whose court the ball is in.
**Scope:** Additive feature on the existing multi-tenant governance platform — not a greenfield redesign. **Sprint 5**, the lifecycle the AIIA and evidence work (`AIIA_DESIGN.md`, `EVIDENCE_DESIGN.md`) left as model-only seams (`LifecycleState`, `LifecycleTransition`, `VendorApproval`, `ProductApproval` exist; no transition logic, gate reads, or approval service — STATE §5). The forward path **tops out at `pending_authorisation`**; the authorisation gate is Sprint 6.
**Status:** v2 — first review round incorporated (14 findings, Appendix B). Headline changes vs v1: **the full gate vector is authoritative and persisted `state` is a cursor** recomputed on consequential reads — un-hold, expiry regression, and persisted/computed authority are now one coherent rule (#3/#4/#6); the **trigger→advance atomicity invariant is made explicit** (#2), and the approval **fan-out is split into one idempotent transaction per use case** (#7), separating atomic single-use-case safety transitions from the eventually-consistent diligence fan-out; the **prohibited rule reads the current snapshot's `tier`, not just `eu_tier`**, closing a real safety hole on the context path where `eu_tier` may never carry PROHIBITED (#1); `treatment_decision` is **provenance-neutral** with a dedicated `treatment_rationale` (#5/#8); the forward-wait verdict is renamed **`park`** to end the `hold`/`held` collision (#10).
**Out of scope this sprint:** the **authorisation gate** + AIIA reviewed-completeness (Sprint 6, STATE §5; PRD §4.9 WKF-2/3); **APR-4** upward evidence rollup (PRD priority **S** — confirmed not a Must, #14); **APR-6** full diligence workflows; **scheduler-driven expiry / notifications** (IXN-5, WKF-4 — expiry is instead caught **lazily** by full-vector re-evaluation on consequential reads, #4); **AI-assist**; **per-object governance scope** (WKF-7); **refresh-on-material-change** of a worked AIIA (CLS-5).
**Decisions:** all resolved (§1.1, §15, Appendix A v1 self-review, Appendix B v2 review). Migrations: `treatment_decision` enum + `treatment_rationale` column on `assessment_item`; `held_from_state` + `held_reason` on `use_case`; vendor/product approval status/validity/decision columns **(verify live DDL first — §3)**. Behaviour change to existing code: `create_aiia`'s readiness moves to the shared `classification_readiness` primitive (reads `eu_tier` for assessable-tier, the current snapshot's `tier` for prohibition — §5.2, #1).

---

## 1. Overview

This sprint turns the individual features — registration, classification, assessment, evidence — into a single governed flow with a clear outcome (PRD §4.1.1). A use case progresses through a fixed, opinionated set of gates; it cannot advance until the current gate's conditions are met, the system tells the user where it is and what is next (IXN-4), and a prohibited-practice classification halts it permanently (LFC-3). The lifecycle is **determinate** — rules over captured context, not a configurable engine (LFC-6).

Three load-bearing decisions:

**Predicate/mutator separation.** A gate predicate is a pure read returning a verdict + reason + responsible-party; it never mutates. `apply_transition` is the single mutator. Three callers need the same gate logic — advance, status, rollup — and if it lives only in the advance path the surface drifts from what the engine enforces.

**The full gate vector is the source of truth; persisted `state` is a cursor (revised in v2, #3/#4/#6).** Conditions change without an event — an approval crosses `valid_until`, a second upstream approval lapses while a use case is already `held`. So the authoritative answer to "where should this use case be?" is the full gate vector recomputed at every *consequential* moment (a status read, an advance/re-evaluate, a Sprint-6 authorisation attempt), not the persisted `state` column. Persisted `state` is the last-known resting gate, advanced or regressed to match the vector whenever a consequential **write** runs; a status **read** shows the computed verdict without mutating. This is what lets time-based expiry regress an already-advanced use case to `held` with no scheduler, and what stops Sprint 6 from authorising a use case whose upstream clearance silently lapsed.

**Auto-advance is event-driven but atomic with its trigger (revised in v2, #2).** "Events" are in-process `advance_use_case` calls, not durable messages, so durability depends on each trigger running its advance pass **in the same transaction as the triggering write**. This is the engine's backbone and is now explicit (§4.3): creation, classification-write, and per-item triggers advance their *own* use case atomically; the multi-use-case approval fan-out is the one eventually-consistent path (§6, #7). A use case is created in `requested` (STATE §5) and the creation pass — same transaction — carries it to its first resting gate, so it never commits wedged in `requested`.

Inherited clearance (APR-3) needs no inheritance code: a use case of an already-cleared vendor+product blows through `vendor_check`/`product_check` on its creation pass, because those gates read **tenant-scoped** approval rows shared across every use case of that product (§5.1). Work splits into **Phase A** (state machine + deterministic gates + approvals + status — demoable) and **Phase B** (the treatment field + gate, and the rollup).

### 1.1 Resolved design decisions

| Decision | Resolution |
| --- | --- |
| State authority | **Full vector authoritative, `state` is a cursor (#3/#4/#6).** The recomputed gate vector decides where a use case should rest; persisted `state` is advanced/regressed to match on any consequential write, and shown (not mutated) on a read. Resolves un-hold restore, expiry regression, and persisted-vs-computed authority as one rule |
| Trigger atomicity | **Explicit (#2).** A triggering write and the `advance_use_case` pass for *that* use case commit in one transaction — the tenant-plane request shape provides it, but the advance call must be in-session, pre-commit, never after. The prohibited halt and the `requested`-is-transient claim depend on this |
| Fan-out durability | **Split (#7).** An approval write + its own audit are atomic; re-evaluating the *other* affected use cases fans out as **one idempotent transaction per use case** (the deferred SQS shape, inline-looped for MVP) — bounded locks, and the safety/diligence durability classes no longer conflated |
| State model reading | **Waiting-room.** `requested` is the transient creation default; each `*_check`/`intake` state is the gate the use case sits *at*. Forward path ceilings at `pending_authorisation`; `authorised → deployed → retired` out of scope |
| `LifecycleState` storage / binding | **Keep uppercase, bind by name.** The `lifecycle_state` type carries member **names** (DDL-confirmed); `.value`s decorative (no `values_callable`) — the §2.8 footgun. Every state write goes through one `_apply_transition()` binding the member through the typed column (emits the name); §2.8 note added |
| `apply_transition` shape | **Single conditional UPDATE, single locus.** `… WHERE id=:id AND state=:from`; from-state guard in the `WHERE` (STATE inv 14); zero rows → 409. Writes `LifecycleTransition` + `AuditEvent` atomically |
| Verdict vs state vocabulary | **`park` ≠ `held` (revised in v2, #10).** The forward-wait **verdict** is `park` (sit at the current gate; no transition, no audit). The regression **state** is `held` (an audited `apply_transition`). `GateResult.verdict ∈ {advance, park, halt}`; `held` is reserved for regression |
| HELD semantics & restore | **Regression-only; restore via full vector (#3/#4).** `held` marks an already-advanced use case whose *upstream* gate lapsed; carries `held_from_state` + `held_reason` as a **UX/audit hint, not the restore target**. Un-hold re-runs the full vector and rests at the **earliest** still-unsatisfied gate (which may be earlier than `held_from_state`). Reversible, against terminal halt |
| Prohibited halt | **Reads the current snapshot's `tier`, from any non-terminal state (revised in v2, #1).** *If the current classification snapshot resolves PROHIBITED → terminal `halted_prohibited`.* Reads `snapshot.tier` (stamped immediately on both bridge and context paths) **not `eu_tier`** (which the context path may never stamp PROHIBITED). Covers creation-time and mid-lifecycle re-classification; a terminal side-exit, doesn't breach no-skip |
| Intake readiness | **`classification_readiness` primitive — read set is `eu_tier` + the current snapshot (#1/#11).** Assessable-tier off **`eu_tier`** (authoritative-ratification signal; closes the unsigned-assessment / tier-freeze defect); prohibition off **`snapshot.tier`** (immediate, both paths); `REQUIRES_CONTEXT`/`UNCLASSIFIED` → park. Shared by `create_aiia` (→ its 409s) and the intake gate. The §2 "reads `eu_tier` only" claim is corrected accordingly |
| Assessment gate depth | **Structural only.** Required AIIA + required feeders (the existing `get_feeder_recommendations` REQUIRED set) present, all proposed risks dispositioned. Reviewer AIIA sign-off is Sprint 6 — an AND-term added to this gate then |
| Treatment gate basis | **Explicit decision, provenance-neutral, dedicated rationale (#3/#5/#8).** Add nullable `treatment_decision` (`MITIGATE`/`ACCEPT`, reserve `TRANSFER`/`AVOID`) + `treatment_rationale`. Inference can't tell *accepted* from *not-addressed*. The write **must not touch `ProvenanceConfidence`** — treatment is orthogonal to the risk-identity confirm/amend axis the override-rate metric depends on. `treatment_rationale` is dedicated, not an overloaded `mitigation_plan` (incoherent in the audit pack) |
| Vendor/product approval | **Thin per-tenant record (APR-5).** Status + validity + `decided_by`/`decided_at` + note. An **expired** approval is not clearance (§5.1); on the *forward* gate always, and on *regression* lazily via full-vector re-evaluation (#4) |
| Clearance role | **Authoriser (#9 v1).** Clearance is acceptance; SoD keeps it off 1st-line and off the recommends-only reviewer |
| Manual lever | **Re-evaluate, not advance-only (#12).** `POST …/lifecycle/re-evaluate` recomputes the full vector and moves the use case to its correct resting gate — **advancing or regressing to `held`** — so it can also fix a stale-after-expiry state |
| Auto-advance audit | **Per-hop.** Each gate crossed is its own audited transition, even when instant — inherited-clearance passes are compliance facts |
| Highest-tier rollup | **Python max via the precedence ladder**, never SQL on the enum (the §2.8 `REQUIRES_CONTEXT` casing footgun) |

---

## 2. Reused components (existing foundations)

- **`LifecycleState` + `LifecycleTransition` (models live, logic absent).** Use cases created in `requested` (STATE §5). Enum consumed as-shipped.
- **`VendorApproval` / `ProductApproval` (models live, no service/router).** Tenant + `catalogue_vendor` / tenant + `catalogue_product` scoped. This sprint adds status management, gate reads, and the cascade — APR-1's three reserved scopes wired.
- **The classification system.** `use_case.eu_tier` (authoritative-tier signal — bridge `snapshot_classification` stamps it eagerly; gate-2 `sign_off_classification` stamps it on review); the **current snapshot's `tier`** (set on resolution, both paths — the prohibition signal, #1); `compute_and_record_classification` (writes `PENDING_REVIEW`, never stamps `eu_tier`); the precedence ladder; `PROHIBITED_HALT`. Resolution/persistence stay separate, never re-entered (STATE inv 11) — the lifecycle reads `eu_tier` **and the current snapshot**, never re-resolves (§5.2, correcting the v1 "`eu_tier` only" claim, #11).
- **AIIA core (`assessment_service.py`).** `create_aiia` (its readiness precondition becomes the shared primitive, §5.2); `get_feeder_recommendations` (the REQUIRED/RECOMMENDED/N-A logic the assessment gate reuses verbatim, §5.3); `AssessmentItem` + `assessment_item_control` (`CoverageStatus`) + `mitigation_plan`/residual fields (treatment gate, §5.4); the disposition-gated amend path with `lock_version`/`If-Match` — reused for the `treatment_decision` write, **minus its provenance-mutating branch** (#5).
- **`AuditEvent` + immutability trigger (STATE inv 5).** Every transition stages one, atomic with the row.
- **Tenant-endpoint contract (STATE §4).** `app/routers/v1/` under `/v1`; `get_tenant_db` + exactly one role dependency; `tenant_id` from `ctx`; schemas in `app/schemas/`. No external call — the simpler tenant-plane shape.
- **The conditional-UPDATE from-state pattern (STATE inv 14).** The transition is this pattern; the `state` column is its own from-state guard, no `lock_version` on the use case.
- **`System` catalogue links.** `catalogue_vendor_id` / `catalogue_product_id` decide whether the vendor/product gates apply (N/A → auto-pass, §5.1).
- **Governance role model (PRD §4.9).** Consumed for gating; no SoD logic here (§12).

---

## 3. Data model

Additive changes plus one behaviour change. **No new table, no new DB role, no new partial index.**

- **`use_case`: `held_from_state` (`lifecycle_state`, nullable) + `held_reason` (`text`, nullable).** HELD's hint (§4.4) — a UX/audit record of where it fell from and why, *not* the restore target (#3). Null on non-held use cases. Same by-name convention as `state`.
- **`assessment_item`: `treatment_decision` (new enum `treatment_decision`, nullable) + `treatment_rationale` (`text`, nullable, #8).** `MITIGATE`/`ACCEPT` for MVP, reserve `TRANSFER`/`AVOID` (the `Framework` reserve-now pattern). Stored by-name. `treatment_rationale` holds the *why* for `ACCEPT` and any narrative for `MITIGATE` — kept separate from `mitigation_plan` (the *how*), which reads incoherently as an acceptance rationale in the audit pack (#8). Both written **provenance-neutral** (#5).
- **`vendor_approval` / `product_approval`: status + validity + decision columns — VERIFY against live DDL first.** `status` (`ApprovalStatus`), a validity field (`valid_until` — the §4.1.4 "validity period"), `decided_by_user_id` / `decided_at` / note. If the reserved models carry these, service/router-only; else a small additive migration. **Also verify `LifecycleTransition`'s columns** (`from_state`/`to_state`/`event`/`actor_user_id`/`reason`).
- **Behaviour change (not a migration): `create_aiia` adopts `classification_readiness`** — gates assessable-tier on `eu_tier`, prohibition on the current snapshot's `tier`, freezes `tier_snapshot` from `eu_tier` (§5.2, #1). Re-run AIIA-creation tests: this now 409s on an unsigned context classification the current code accepts.

**§2.8 documentation:** record that `LifecycleState` and `treatment_decision` are stored **by-name**, `.value`s decorative.

---

## 4. The lifecycle state machine

### 4.1 States & the waiting-room model

| State | Advances when… | Terminal / notes |
| --- | --- | --- |
| `requested` | created → begin (transient; the same-transaction creation pass carries it on) | — |
| `vendor_check` | vendor approved & not expired, **or** no vendor link | — |
| `product_check` | product approved & not expired, **or** no product link | — |
| `intake` | `classification_readiness` = READY (`eu_tier` a real non-prohibited tier) | **snapshot PROHIBITED → `halted_prohibited`** |
| `under_assessment` | structural assessment complete (§5.3) | — |
| `treatment_pending` | every dispositioned risk has a treatment decision (§5.4) | — |
| `pending_authorisation` | reviewer/authoriser sign-off | **sprint ceiling — Sprint 6** |
| `authorised → deployed → retired` | — | out of scope; legality table reserves the transitions, unwired |
| `halted_prohibited` | — | terminal |
| `held` | full-vector re-evaluation rests it at the earliest unsatisfied gate (#3) | reversible regression target (§4.4) |

Transition legality is a table `(state, event) → state`; an undefined `(state, event)` is rejected (LFC-2). The **one full-vector-driven edge** is the exit from `held`: its target is whatever gate the recomputed vector lands on (always a legal positional state by construction, so no separate `held_from_state` legality check is needed once restore is vector-driven — #13).

### 4.2 `apply_transition` — the single mutator

One choke point for every state change. It (1) runs the conditional `UPDATE … WHERE id=:id AND state=:from` — the from-state guard *is* the concurrency control (STATE inv 14); zero rows → 409; (2) binds states as enum **members** through the typed column (by-name, never `.value`); (3) stages a `LifecycleTransition` (from/to/event/actor/reason) **and** an `AuditEvent`, atomic with the row; (4) on a HELD entry, sets `held_from_state` + `held_reason`; clears them on any forward transition out of `held`.

### 4.3 `advance_use_case` — the auto-advance driver, atomic with its trigger (#2)

The orchestration spine, **invoked within the triggering write's transaction** so the write and its transition(s) commit atomically. On a trigger it: (0) **prohibited pre-check** — if the current snapshot resolves PROHIBITED and the state is non-terminal, `apply_transition` to `halted_prohibited` and stop (§5.5, #1); else (1) evaluate the current state's gate; advance and loop until the first `park`, the terminal halt, or the `pending_authorisation` ceiling.

**Single-use-case triggers (atomic):** `use_case.created` (creation transaction — the use case commits at its first resting gate, never wedged in `requested`); a classification becoming current for *this* use case (bridge resolve; context sign-off stamping `eu_tier`; **any** PROHIBITED resolution — the write paths invoke advance in-session so a mid-lifecycle prohibition halts atomically, never a committed-but-unhalted window, §5.5); an item disposition / treatment change. **Multi-use-case trigger (eventually consistent):** an approval set/update — see §6, #7.

### 4.4 HELD — regression, restored by the full vector (#3)

`held` is entered only by the **full-vector** evaluation finding an *already-passed* upstream gate now unsatisfied — a vendor/product approval revoked or expired after the use case advanced. `apply_transition` records `held_from_state` + `held_reason`. **Un-hold re-runs the full vector and rests at the earliest still-unsatisfied gate** — *not* a forward advance from `held_from_state`, which would skip an upstream gate that lapsed *while* the use case was held (the v1 bug, #3). `held_from_state` is a UX/audit hint only. Reversible — the deliberate counterpart to the prohibited path's terminal halt.

---

## 5. The gates

Six gates, side-effect-free predicates returning a `GateResult` — `verdict ∈ {advance, park, halt}` (#10), a stable `reason_code`, a human reason, and `responsible_party ∈ {user, reviewer, authoriser, vendor, system}` (IXN-4). Advance runs the next gate; status/rollup runs the **full vector** (§7).

### 5.1 Vendor & product gates

- **Vendor:** read `VendorApproval(tenant_id, system.catalogue_vendor_id)` — `APPROVED` and not past `valid_until` → advance; absent/`PENDING`/`REJECTED`/expired → park (court: authoriser/vendor); **no `catalogue_vendor_id` → N/A, auto-pass**.
- **Product:** `ProductApproval(tenant_id, system.catalogue_product_id)`, same shape; no product link → auto-pass.

Use-case-independent reads on tenant-scoped rows — that *is* APR-3 inheritance, no inheritance code (§1). Validity gates forward motion here; **expiry of an already-passed approval regresses via the full vector on the next consequential read** (#4, §7), not a scheduler.

### 5.2 Intake gate — `classification_readiness`

Read set: **`use_case.eu_tier` + the current classification snapshot** (compared in Python, never SQL-filtered on the enum — the §2.8 `REQUIRES_CONTEXT` footgun). Two signals, deliberately:

| Condition | Verdict | Signal |
| --- | --- | --- |
| current snapshot `tier == PROHIBITED` | **halt** → `halted_prohibited` | `snapshot.tier` — set immediately on resolution, **both paths**, pre-sign-off (#1) |
| no current snapshot | park (fail-closed; shouldn't occur post-creation) | — |
| `eu_tier ∈ {REQUIRES_CONTEXT, UNCLASSIFIED}` | park | `eu_tier` |
| `eu_tier ∈ {HIGH, LIMITED, MINIMAL}` | advance | `eu_tier` (authoritative) |

**Why two signals.** Prohibition is a safety halt that must not wait for review — and on the context path `eu_tier` may *never* carry PROHIBITED (the resolution short-circuits and `compute_and_record_classification` does not stamp `eu_tier`; no one signs off a prohibition), so reading `eu_tier` alone would *park*, not *halt* — the v1 hole (#1). Reading the **snapshot's `tier`** for prohibition fires immediately on either path. Assessable-readiness, by contrast, *must* wait for ratification — so it keys on **`eu_tier`**, which stays `REQUIRES_CONTEXT` through the context `PENDING_REVIEW` window and only becomes a real tier on sign-off — closing the unsigned-assessment / tier-freeze defect (Appendix A #1). `create_aiia` consumes the same primitive: halt/park → its 409s, advance → proceed, freezing `tier_snapshot` from `eu_tier`.

**Whose-court** at a park can't come from `eu_tier` alone: `REQUIRES_CONTEXT` covers "user hasn't answered the tree" and "answered, `PENDING_REVIEW`, awaiting sign-off." The status label peeks at whether a current `PENDING_REVIEW` snapshot exists (→ reviewer) vs not (→ user). (This snapshot read is why §2 says the read set is `eu_tier` **plus** the current snapshot, #11.)

### 5.3 Assessment gate — structural

Met when: the current AIIA exists; every feeder `get_feeder_recommendations` marks **REQUIRED** for this use case exists; and no still-`AI_SUGGESTED` proposed-risk items remain. Reviewer sign-off (`AssessmentStatus → approved`) is **not** checked here — Sprint 6; folding it in is an AND-term then. Missing AIIA → park ("no assessment started", user's court); missing required feeder → park, reusing the recommendation verdict.

### 5.4 Treatment gate

Met when every **dispositioned risk item** (`risk_id` set, provenance `USER_CONFIRMED`/`USER_AMENDED`) carries a `treatment_decision`; `MITIGATE` additionally requires a control-link or a non-empty `mitigation_plan`; `ACCEPT` requires a non-empty `treatment_rationale` (#8). The upstream assessment gate guarantees disposition, so this gate only checks the decision.

The `treatment_decision`/`treatment_rationale` write reuses the item amend machinery — disposition-gated (no deciding treatment on a still-`AI_SUGGESTED` item), `lock_version`/`If-Match`, audited (`assessment_item.treatment_set`) — but **must not alter `ProvenanceConfidence` (#5)**: treatment is orthogonal to the risk-identity confirm/amend axis that feeds the override-rate metric (`AIIA_DESIGN.md` §4). It is written through a branch that leaves provenance untouched, not through `amend_item`'s `CATALOGUE_CURATED → USER_PROVIDED` path. This per-risk decision is **1st-line owner work**; it is *not* the Authoriser's aggregate residual-risk acceptance (Sprint 6).

### 5.5 The unified prohibited-halt rule (cross-cutting, #1)

Step 0 of `advance_use_case`, evaluated from **any** non-terminal state: *if the current classification snapshot resolves PROHIBITED → `halted_prohibited`.* Reads **`snapshot.tier`** (not `eu_tier`), so it fires on the context path even though `eu_tier` is never stamped PROHIBITED there (#1). Fires for a bridge prohibited at creation (halts on the creation pass, never entering diligence — IXN-3) and a re-classification to prohibited mid-lifecycle. The classification write paths invoke `advance_use_case` **in-transaction** (#2), so a prohibition halts atomically — STATE §5's missing wire (the classification gate hard-stops via `PROHIBITED_HALT` but nothing yet drives the lifecycle off it) is exactly this, now durable.

---

## 6. Vendor / product approval records

The thin diligence record (APR-5): per-tenant `VendorApproval`/`ProductApproval` with status, validity, decision metadata (§3). Endpoints **set/update** each (no delete — withdrawal is a status change, preserving history), authoriser-gated (§12).

**Re-evaluation fan-out — split for durability (#7).** An approval write affects many use cases (LFC-4). The model:
1. The **approval write + its own `AuditEvent`** commit atomically (one transaction).
2. The affected use cases (those on systems linked to that vendor/product) are then re-evaluated as **one idempotent transaction per use case** — cleared approvals advance held/waiting use cases; downgraded/expired/revoked approvals regress now-unsatisfied use cases to `held` (§4.4). RLS bounds the set to the tenant.

This separates the two durability classes the v1 single transaction conflated: the *safety* halt is single-use-case and atomic with its trigger (§4.3, #2); the *diligence* fan-out is reversible HELD and eventually-consistent — re-runnable, idempotent, lock-bounded. It **is** the deferred SQS worker's shape (IXN-5): inline-looped per-transaction now, queue-driven later, no rewrite.

**Expiry has no event (#4).** `valid_until` gates forward motion always; for an already-advanced use case, expiry is caught **lazily** by the full-vector re-evaluation that runs on any consequential read/operation (§7) — no scheduler. Absent such a read, persisted `state` may briefly overstate clearance, but **no gating decision uses persisted `state` alone** (§7), so nothing unsafe rides on the staleness.

---

## 7. Status surface, the full-vector model & system rollup (REG-3 / IXN-4)

**Persisted `state` is a cursor; the full gate vector is source of truth (#3/#4/#6).** The full vector is recomputed:
- on a **status read** — shown as the `GateResult`, **not** persisted (a GET never mutates);
- on a consequential **write** (`re-evaluate`/advance attempt, §8; Sprint-6 authorisation attempt) — and persisted: the use case is moved to its correct resting gate, advancing or **regressing to `held`** if an upstream gate lapsed.

So a use case whose vendor approval expired shows "held: vendor clearance expired" on the next status read, and is *moved* to `held` on the next consequential write — and Sprint 6 **must** re-run the full vector before authorising, so it cannot admit a use case whose upstream clearance silently lapsed (#6). This is the safety property that makes a cursor-style persisted `state` acceptable.

- **Per use case:** state (cursor) + the **full-vector** `GateResult` — where, why, whose court.
- **Per system / portfolio (REG-3):** each system's use cases with states, **highest tier present** (Python `max` over the precedence ladder — never SQL on the enum), and outstanding obligations (the blocking `GateResult` per use case). A read-model / Pydantic view (`MODELS.md` §6).

---

## 8. API endpoints

| Method + path | Purpose | Gate |
| --- | --- | --- |
| `GET /v1/use-cases/{id}/lifecycle` | State + full-vector `GateResult`; recompute shown, not persisted (§7) | any governance role |
| `POST /v1/use-cases/{id}/lifecycle/re-evaluate` | Recompute the full vector and move to the correct resting gate — **advance or regress to `held`** (#12); the manual fix for stale-after-expiry state | `system_owner` |
| `GET /v1/systems/{id}/rollup` *(or extend `SystemDetail`)* | Per-system use cases, states, highest tier, obligations (REG-3) | any governance role |
| `GET /v1/portfolio` | Tenant-wide rollup | any governance role |
| `PUT /v1/vendors/{vendor_id}/approval` | Set/update vendor clearance (§6) | `authoriser` |
| `PUT /v1/products/{product_id}/approval` | Set/update product clearance | `authoriser` |
| `PATCH /v1/assessments/{aid}/items/{item_id}` *(extended)* | Also sets `treatment_decision` + `treatment_rationale`, provenance-neutral (§5.4) | `{system_owner, contributor}` |

Audit actions: `lifecycle.advanced`, `lifecycle.held`, `lifecycle.halted_prohibited`, `vendor_approval.set`/`.updated`, `product_approval.set`/`.updated`, `assessment_item.treatment_set`.

---

## 9. Tenancy, RLS & isolation

Entirely tenant-plane, `irontrustai_app` / `get_tenant_db`, `NOBYPASSRLS`, **no new DB role** (STATE inv 4). `use_case`, `lifecycle_transition`, `vendor_approval`, `product_approval` all RLS-scoped. `tenant_id` from `ctx` (STATE inv 3) — a cross-tenant `vendor_id`/`product_id` is invisible, fails closed. The approval fan-out (§6) is RLS-bounded to the acting tenant.

---

## 10. Constraints & invariants

1. **One mutator.** Every `use_case.state` change goes through `apply_transition`; it is the only writer and the only stager of `LifecycleTransition`.
2. **From-state guard in the `WHERE` (STATE inv 14).** Single conditional `UPDATE`, never read-then-write; zero rows → 409.
3. **Enum bound by name, never `.value`.** `LifecycleState`/`treatment_decision` stored as names; `.value` in a raw `WHERE` silently matches zero rows.
4. **Trigger atomicity (#2).** A single-use-case triggering write and its `advance_use_case` pass commit in one transaction. The prohibited halt and the `requested`-transient guarantee depend on it.
5. **Full vector is source of truth; persisted `state` is a cursor (#3/#4/#6).** No gating decision (advance, regress, or Sprint-6 authorisation) is made from persisted `state` alone; it is recomputed at every consequential read/operation. Reads show, consequential writes persist.
6. **Prohibited is terminal, supreme, and read off the snapshot (#1, LFC-3).** The current snapshot resolving PROHIBITED forces `halted_prohibited` from any non-terminal state, via `snapshot.tier` (not `eu_tier`), evaluated as step 0 of every advance.
7. **`park` ≠ `held` (#10).** `park` is the forward-wait **verdict** — no transition, no audit. `held` is a **regression state** — an audited `apply_transition`. Forward waiting is never audited; entering `held` always is.
8. **HELD is regression-only and restored by the full vector (#3).** `held_from_state`/`held_reason` are hints; un-hold rests at the earliest unsatisfied gate, not a forward advance from `held_from_state`.
9. **Fan-out is per-use-case and idempotent (#7).** The approval write is atomic with its own audit; other affected use cases re-evaluate as independent transactions. Safety transitions are never in a fan-out (they are single-use-case, classification-driven).
10. **`treatment_decision` is provenance-neutral (#5).** Writing it never alters `ProvenanceConfidence`; treatment is orthogonal to the risk-identity confirm/amend axis.
11. **`classification_readiness` is the single readiness definition.** Consumed by both `create_aiia` and the intake gate; assessable off `eu_tier`, prohibition off the snapshot. They must not diverge.
12. **Catalogue-link conditionality.** Vendor/product gates auto-pass when the relevant `catalogue_*_id` is null — explicit branch.
13. **Inheritance via shared reads (APR-3); `tenant_id` from context; no new DB role.**
14. **Highest-tier in Python**, never SQL on `eu_ai_act_tier` (§2.8 footgun).
15. **Assessment gate structural; treatment an explicit decision.** Neither reads reviewer sign-off — Sprint 6.

---

## 11. Sequencing

**Phase A — state machine + deterministic gates + approvals + status (demoable).** Migrations: `held_from_state`/`held_reason` on `use_case`; vendor/product approval columns (if absent). The legality table; `apply_transition`; `advance_use_case` (atomic-with-trigger, prohibited pre-check off the snapshot); the shared `classification_readiness` extract + the `create_aiia` change (#1); vendor/product gates; the intake gate; approval endpoints + the per-use-case fan-out (#7); per-use-case status + system/portfolio rollup with the **full-vector recompute** (#6); the `re-evaluate` lever (#12); the prohibited-halt wire into the classification write paths (#1/#2).

**Phase B — treatment field + gate.** Migration: `treatment_decision` enum + `treatment_rationale` column. The provenance-neutral amend-path branch to set them (#5); the treatment gate; `treatment_pending → pending_authorisation`.

**Seams preserved:** `advance_use_case` + the per-use-case fan-out as the SQS entry point (IXN-5); the `pending_authorisation` ceiling (Sprint 6); `scope_id` (WKF-7); drift fields (CLS-5); `classification_readiness` as the single point a future bridge-review requirement (§9 PRD) lands.

---

## 12. Role gates

| Action | Gate | Basis |
| --- | --- | --- |
| `treatment_decision`/`treatment_rationale` authoring | `{system_owner, contributor}` | 1st-line; Contributor "drives remediation" |
| Vendor/product approval set/update | `authoriser` | acceptance; off 1st-line and off the recommends-only reviewer (#9 v1) |
| Lifecycle status + rollup reads | all five governance roles | auditor read-only oversight |
| Manual re-evaluate | `system_owner` | "steers the process"; low-stakes (recompute → correct resting gate) |

SoD enforced only at assignment (`assert_governance_assignable`); gates read eligibility, carry no conflict logic.

---

## 13. Edge & failure cases

- No catalogue link → vendor/product gates auto-pass (§5.1).
- Classification `REQUIRES_CONTEXT`/`UNCLASSIFIED` → intake **parks** (court: user or reviewer per a `PENDING_REVIEW` peek), not an error.
- **Context-resolved prohibited** (writes `PENDING_REVIEW` snapshot `tier=PROHIBITED`, never stamps `eu_tier`) → step 0 reads `snapshot.tier` → `halted_prohibited` (#1), the v1 hole closed.
- Bridge prohibited at creation → halts on the creation pass, never enters diligence.
- Re-classified to prohibited mid-lifecycle → forced `halted_prohibited` from any state, via the in-transaction classification trigger (#1/#2).
- Approval **revoked** after its gate passed → full-vector re-eval moves the use case to `held`, reversibly; not auto-reverted to a positional state.
- Approval **expires** (no event) → not caught until the next consequential read/operation re-runs the full vector; persisted `state` may briefly overstate clearance, but no gating decision rides on it (§7, #4).
- **Un-hold with a second lapse** — held at `under_assessment` (vendor revoked), product then expires; on vendor re-clearance the full vector rests it back at `product_check`, not forward at `under_assessment` (#3).
- Approval fan-out across 200 use cases → 200 independent idempotent transactions, not one (#7); a crash mid-fan-out leaves some un-advanced, caught on next consequential read or re-run.
- Concurrent advance vs fan-out re-eval → the conditional from-state UPDATE serialises; the loser sees zero rows / already-moved.
- Required feeder absent → assessment gate parks, reusing `get_feeder_recommendations` (§5.3).
- Risk accepted-as-is → `treatment_decision = ACCEPT` + `treatment_rationale` passes; absence of a control/plan no longer reads as "untreated" (#3 v1).
- Setting `treatment_decision` on a `USER_CONFIRMED` risk → provenance unchanged (#5); the override-rate metric is untouched.
- Sprint-6 authorisation attempt on a use case with a lapsed upstream approval → full-vector re-run blocks it even if persisted `state` is stale (#6).
- `create_aiia` on an unsigned context classification → 409 (readiness off `eu_tier`, Appendix A #1).

---

## 14. Intentionally deferred (post-MVP / later sprints)

- **Authorisation gate + AIIA reviewed-completeness** — reviewer/authoriser sign-off, review queue, `AssessmentStatus` transitions, ATO doc (EXP-1a). The `pending_authorisation` ceiling is its entry, and it **must re-run the full vector** before authorising (#6).
- **APR-4** upward evidence rollup — PRD priority **S** (confirmed not a Must, #14); deferral does not need a Must-flag.
- **APR-6** full diligence workflows.
- **Scheduler-driven expiry + notifications** (IXN-5/WKF-4) — expiry is covered lazily by full-vector re-evaluation (#4); a scheduler only makes regression eager.
- **Per-object governance scope** (WKF-7); **refresh-on-material-change** (CLS-5 — drift fields exist, re-run cycle does not); **AI-assist**.
- **Remediation of pre-existing mis-scoped AIIAs (#14).** The #1 fix prevents *new* AIIAs off unsigned snapshots; any already created off one are not retro-detected (no CLS-5 drift yet) — manual review, likely moot pre-launch.

### Next sprint (not post-MVP)
- **Sprint 6 — review/sign-off + authorisation gate (PRD §8).** The direct consumer of the ceiling: the Reviewer AIIA sign-off (the assessment-gate AND-term, §5.3), the Authoriser residual-risk acceptance, `authorised → deployed → retired`, the full-vector re-run before authorisation (#6), and — if §9 decides bridge classifications need review — the one-line tightening in `classification_readiness`.

---

## 15. Decisions resolved + migration

**Migration set:**
- **Phase A:** `held_from_state` + `held_reason` on `use_case`; vendor/product approval status/validity/decision columns **iff absent**; `LifecycleTransition` columns **iff absent**. `down_revision` = current head; hand-edit grants/RLS per CLAUDE §4 (no new partial index, no new role).
- **Phase B:** `treatment_decision` enum type + nullable column, and `treatment_rationale` text column, on `assessment_item`.
- **Not a migration:** the `create_aiia` readiness change (#1); the §2.8 by-name note.

**Verify-against-code preconditions (STATE §22):**
1. Vendor/product approval column set; `LifecycleTransition` column set (§3).
2. **What the context PROHIBITED short-circuit writes (#1/#9).** Confirmed-by-design that `compute_and_record_classification` writes a current snapshot with `tier=PROHIBITED` (status `PENDING_REVIEW`) and does **not** stamp `eu_tier`; the §5.5 rule reads `snapshot.tier`, so it is robust either way — but confirm the snapshot is in fact written `is_current` for a PROHIBITED_HALT outcome (the resolver returns the outcome before persistence; verify the persistence path is reached, not short-circuited earlier).
3. The `ClassificationStatus` default the bridge `snapshot_classification` inherits (sets no explicit `status`); if `PENDING_REVIEW`, a bridge row is `eu_tier`-authoritative but `status`-pending — a data-honesty smell worth a one-line `status=APPROVED` on the bridge writer; does not affect the gate (Appendix A #6).

---

## Appendix A — Design findings & disposition (v1 self-review)

Issues surfaced reconciling the v1 design against live source.

| # | Sev | Finding | Disposition |
| --- | --- | --- | --- |
| 1 | Blocking | `create_aiia` gates/freezes `tier_snapshot` from the current snapshot's `tier`, real on an `is_current` `PENDING_REVIEW` context snapshot **before** sign-off — assess off an unsigned classification, scoped to a tier review may revise, undetected | **Fixed.** `classification_readiness` gates assessable-tier off `eu_tier`; `create_aiia` + intake share it (§5.2) |
| 2 | Blocking | `lifecycle_state` stores member **names**; `.value`s lowercase, no `values_callable` — a raw `.value` bind silently matches zero rows (§2.8 footgun) | **Resolved.** Keep uppercase, bind by name in `_apply_transition`; §2.8 note (§10.3) |
| 3 | Blocking | No treatment/accept field — inference can't tell *accepted* from *not-addressed* | **Resolved.** Nullable `treatment_decision` (+ `treatment_rationale`, v2 #8) |
| 4 | Should | `HELD` as a catch-all erases which gate | **Resolved.** Regression-only + hints; restore by full vector (v2 #3) |
| 5 | Should | Enum orders vendor/product before `intake` — prohibited-at-creation would run diligence first | **Resolved.** Unified prohibited rule as step 0 from any state (§5.5) |
| 6 | Minor | Bridge `snapshot_classification` stamps `eu_tier` but sets no `status` (column default) — possibly authoritative-by-`eu_tier`, pending-by-`status` | **Noted.** Gate unaffected; optional `status=APPROVED` tidy; verify default (§15) |
| 7 | Should | Intake gate could impose stricter readiness than `create_aiia` | **Resolved.** Shared primitive — one definition (§5.2) |
| 8 | Should | Behaviour on upstream-approval revoke after advance undefined | **Resolved.** Move to `held`, reversible (§4.4) — sharpened in v2 #3 |
| 9 | Decision | Clearance role | **Authoriser** (§12) |
| 10 | Verify | Approval / `LifecycleTransition` column sets assumed | **Open precondition** (§15) |

## Appendix B — Review disposition (v2, round 1)

| # | Sev | Finding | Disposition |
| --- | --- | --- | --- |
| 1 | Blocking | Prohibited rule reads `eu_tier`, but the context path never stamps `eu_tier=PROHIBITED` — a context-prohibited use case would park, not halt | **Fixed.** Step 0 / `classification_readiness` read the **current snapshot's `tier`** for prohibition (immediate, both paths); `eu_tier` retained only for assessable-readiness (§5.2, §5.5). Verify item added (§15.2) |
| 2 | Blocking | "Event-driven" advance has an unstated trigger→advance atomicity invariant; the safety transition can be lost | **Fixed.** Invariant made explicit — single-use-case triggers advance in the triggering transaction (§4.3, inv 4); classification writes invoke advance in-session |
| 3 | Blocking | Un-hold restores forward from `held_from_state`, skipping a gate that lapsed while held | **Fixed.** Un-hold re-runs the full vector, rests at the earliest unsatisfied gate; `held_from_state` demoted to a hint (§4.4, inv 8) |
| 4 | Blocking | Time-based expiry has no trigger — an advanced use case never regresses on expiry | **Fixed via the full-vector model.** Validity gates forward always; expiry regresses lazily on the next consequential read/operation; no scheduler (§6, §7, inv 5). Documented that persisted `state` may briefly overstate, but nothing gates on it alone |
| 5 | Blocking | `treatment_decision` via the amend path may mutate provenance, polluting the override-rate metric | **Fixed.** Written through a **provenance-neutral** branch, never `amend_item`'s `CATALOGUE_CURATED→USER_PROVIDED` path (§5.4, inv 10). (Note: live `amend_item` only flips `CATALOGUE_CURATED`, so a confirmed risk wouldn't flip today — neutrality is now guaranteed regardless) |
| 6 | Should | Persisted `state` vs computed full-vector authority undefined | **Fixed.** Full vector authoritative; `state` a cursor recomputed at consequential reads; Sprint 6 authorisation re-runs it (§7, inv 5) |
| 7 | Should | Fan-out is one transaction scaling with portfolio breadth; conflates two durability classes | **Fixed.** Approval write atomic with its own audit; other use cases re-evaluate as one idempotent transaction each — the SQS shape (§6, inv 9) |
| 8 | Should | `mitigation_plan` as ACCEPT rationale is a semantic smell in audit exports | **Fixed.** Dedicated `treatment_rationale` field (§3, §5.4) |
| 9 | Should | Add the context-prohibited-`eu_tier` check to the verify list | **Added** (§15.2) |
| 10 | Minor | `hold` (verdict) vs `held` (state) collision makes inv 7 self-contradictory | **Fixed.** Forward-wait verdict renamed `park`; `held` reserved for regression (§5, inv 7) |
| 11 | Minor | Intake reads the snapshot, contradicting "reads `eu_tier` only" | **Corrected.** Read set stated as `eu_tier` + current snapshot (§2, §5.2) |
| 12 | Minor | The one manual lever is forward-only | **Fixed.** `re-evaluate` recomputes the full vector and advances **or** regresses (§8) |
| 13 | Minor | `held → held_from_state` restore is the one data-driven transition target | **Resolved by #3.** Restore target is the full-vector result (a legal positional state by construction); `held_from_state` is a hint, no separate legality check (§4.1) |
| 14 | Minor | Confirm APR-4 priority; fix doesn't remediate existing mis-scoped AIIAs | **Confirmed APR-4 = S** (no Must-flag needed); pre-existing-AIIA note added (§14) |