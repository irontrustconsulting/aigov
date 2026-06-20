# SPRINT_LIFECYCLE — Product Lifecycle, Gates & Approvals (Sprint 5)

Design + rationale: `LIFECYCLE_DESIGN.md` (v2). This doc is execution-only. Build in plan mode; propose before executing.

**Goal:** Wire the use-case lifecycle state machine, deterministic gates, vendor/product approvals, and the status/rollup surface. Forward path ceilings at `pending_authorisation` (authorisation gate = Sprint 6).

**Out of scope:** authorisation gate / AIIA sign-off (Sprint 6); APR-4/APR-6; scheduler/notifications; per-object scope; refresh-on-drift; AI-assist.

---

## 0. Verify before migrating (STATE §22)

- [ ] `\d vendor_approval` / `\d product_approval` — do they carry `status`, validity, `decided_by`/`decided_at`? (decides M3)
- [ ] `\d lifecycle_transition` — does it carry `from_state`, `to_state`, `event`, `actor_user_id`, `reason`? (add if absent)
- [ ] **BLOCKING:** confirm context PROHIBITED reaches persistence — `compute_and_record_classification` writes an `is_current` `Classification` with `tier=PROHIBITED` (status `PENDING_REVIEW`) for a `PROHIBITED_HALT` outcome, and does **not** short-circuit before the row write. §5.5 reads `snapshot.tier`; if no row is written there is nothing to read.
- [ ] `ClassificationStatus` column default inherited by bridge `snapshot_classification` (informational; gate unaffected).

---

## 1. Canonical state

**States** (`LifecycleState`, stored by-name; create in `requested`):
`requested → vendor_check → product_check → intake → under_assessment → treatment_pending → pending_authorisation` (ceiling) · `halted_prohibited` (terminal) · `held` (regression) · `authorised → deployed → retired` (unwired this sprint).

**`GateResult`** = `{verdict: advance|park|halt, reason_code, reason, responsible_party: user|reviewer|authoriser|vendor|system}`.

---

## 2. Transition table

| from | trigger | gate / condition | to |
|---|---|---|---|
| `requested` | created | — | `vendor_check` |
| `vendor_check` | advance | `vendor_gate` PASS | `product_check` |
| `product_check` | advance | `product_gate` PASS | `intake` |
| `intake` | advance | `classification_readiness` = READY | `under_assessment` |
| `under_assessment` | advance | `assessment_gate` PASS | `treatment_pending` |
| `treatment_pending` | advance | `treatment_gate` PASS | `pending_authorisation` |
| *any non-terminal* | step-0 | `snapshot.tier == PROHIBITED` | `halted_prohibited` |
| *any advanced* | full-vector re-eval | an already-passed upstream gate now fails | `held` (set `held_from_state`,`held_reason`) |
| `held` | re-evaluate | full vector | earliest unsatisfied gate's state |

`park` = current gate not satisfied → stay (no transition, no audit). `halt`/`held` = audited `apply_transition`. Legality is table-driven; undefined `(state,event)` → reject.

---

## 3. Gate predicates (pure reads)

```
vendor_gate(uc):
  if uc.system.catalogue_vendor_id is None: PASS (N/A)
  va = VendorApproval(tenant, vendor_id)
  PASS if va and va.status==APPROVED and (va.valid_until is None or va.valid_until >= now)
  else PARK(court=authoriser/vendor)

product_gate(uc): same vs ProductApproval / catalogue_product_id

classification_readiness(uc):              # read set = current snapshot + eu_tier; compare in Python
  snap = current Classification(uc, is_current=True)
  if snap is None: PARK (fail-closed)
  if snap.tier == PROHIBITED: HALT
  if uc.eu_tier in {REQUIRES_CONTEXT, UNCLASSIFIED}: PARK
      (court=reviewer if a current PENDING_REVIEW snapshot exists, else user)
  if uc.eu_tier in {HIGH, LIMITED, MINIMAL}: READY

assessment_gate(uc):
  aiia = current AIIA(uc); if None: PARK
  recs = get_feeder_recommendations(aiia)
  PARK if any rec.applicability==REQUIRED and not rec.exists
  PARK if any AssessmentItem(aiia).provenance == AI_SUGGESTED
  else PASS

treatment_gate(uc):
  aiia = current AIIA(uc)
  for item in items(aiia) where item.risk_id and provenance in {USER_CONFIRMED, USER_AMENDED}:
    PARK if item.treatment_decision is None
    if MITIGATE: PARK unless (control_link exists) or (mitigation_plan non-empty)
    if ACCEPT:   PARK unless treatment_rationale non-empty
  else PASS
```

---

## 4. Services

```
apply_transition(uc, event, to_state, actor, reason, *, held_from=None, held_reason=None):
  UPDATE use_case SET state=:to[, held_from_state, held_reason] WHERE id=:id AND state=:from
    -> rowcount==0: 409                       # from-state guard = concurrency control (STATE inv 14)
  bind enum by NAME via typed column (never .value)
  stage LifecycleTransition(from,to,event,actor,reason) + AuditEvent   # atomic
  clear held_from_state/held_reason on any forward transition out of `held`

advance_use_case(uc, db, actor):              # MUST run in the triggering write's txn
  if uc.state non-terminal and classification_readiness(uc)==HALT: apply_transition(.., halted_prohibited); return
  loop: g = gate_for(uc.state); if g==advance: apply_transition(..next..); continue; else stop  # park/halt/ceiling

full_vector(uc) -> [GateResult per gate in order]   # first non-PASS = blocking

re_evaluate(uc, db, actor):                   # consequential write
  recompute full_vector; target = earliest unsatisfied gate's state
  if target > uc.state: advance via apply_transition(s)
  if target < uc.state (a passed gate now fails): apply_transition(.., held, held_from=uc.state, reason)

set_vendor_approval/set_product_approval(...):
  write approval + AuditEvent (atomic, one txn)
  fan_out: for uc in affected_use_cases(vendor/product, RLS-scoped):
             re_evaluate(uc) in its OWN txn (idempotent, re-runnable)
```

**Trigger wiring (advance in the same txn):** use-case create → `advance_use_case`; `snapshot_classification` / `compute_and_record_classification` / `sign_off_classification` → `advance_use_case` (drives intake + prohibited); item disposition/treatment write → `advance_use_case`. Approval set/update → `fan_out` (per-uc txns).

---

## 5. Schema / migrations

- **M1 `use_case`:** `held_from_state` (`Enum(lifecycle_state)`, null), `held_reason` (text, null).
- **M2 `assessment_item`:** new enum type `treatment_decision` (`MITIGATE`, `ACCEPT`; reserve `TRANSFER`, `AVOID`); columns `treatment_decision` (null), `treatment_rationale` (text, null). By-name.
- **M3 `vendor_approval`/`product_approval`** *(only if §0 shows absent):* `status` (`ApprovalStatus`), `valid_until` (timestamptz, null), `decided_by_user_id` (uuid FK `app_user` ON DELETE SET NULL), `decided_at` (timestamptz, null), `note` (text, null).
- Add `LifecycleTransition` columns if §0 shows absent.
- Hand-edit grants/RLS in the migration (CLAUDE §4). **No new partial index, no new DB role.**
- Doc: add §2.8 note — `LifecycleState`, `treatment_decision` stored by-name, `.value`s decorative.

---

## 6. Endpoints

| Method · path | Behaviour | Gate |
|---|---|---|
| GET `/v1/use-cases/{id}/lifecycle` | state + `full_vector` GateResult; **recompute, do not persist** | any gov role |
| POST `/v1/use-cases/{id}/lifecycle/re-evaluate` | `re_evaluate` (advance or regress to `held`) | `system_owner` |
| GET `/v1/systems/{id}/rollup` *(or extend SystemDetail)* | use cases + states + highest tier (Python max) + blocking obligations | any gov role |
| GET `/v1/portfolio` | tenant-wide rollup | any gov role |
| PUT `/v1/vendors/{vendor_id}/approval` | `set_vendor_approval` + fan-out | `authoriser` |
| PUT `/v1/products/{product_id}/approval` | `set_product_approval` + fan-out | `authoriser` |
| PATCH `/v1/assessments/{aid}/items/{item_id}` *(extend)* | set `treatment_decision`/`treatment_rationale`, **provenance-neutral**, disposition-gated, `If-Match` | `{system_owner, contributor}` |

**Schemas:** `GateResult`; `UseCaseLifecycleRead{state, gates[], blocking}`; `SystemRollupRead`/`PortfolioRead` (view models, not ORM); `VendorApprovalCreate/Read`, `ProductApprovalCreate/Read`; extend `AssessmentItemAmend` with `treatment_decision`, `treatment_rationale`.

**Audit actions:** `lifecycle.advanced`, `lifecycle.held`, `lifecycle.halted_prohibited`, `vendor_approval.set`/`.updated`, `product_approval.set`/`.updated`, `assessment_item.treatment_set`.

---

## 7. Invariants

1. `apply_transition` is the sole writer of `use_case.state` / `LifecycleTransition`.
2. Transition = single conditional `UPDATE … WHERE state=:from`; 0 rows → 409. Bind enum by-name, never `.value`.
3. Single-use-case trigger + its `advance_use_case` commit in one txn.
4. Full vector is source of truth; persisted `state` is a cursor. No gate decision (advance/regress/Sprint-6 auth) reads persisted `state` alone. Status read recomputes + shows (no write); consequential write recomputes + persists.
5. Prohibition read off `snapshot.tier` (not `eu_tier`), step-0, from any non-terminal state → terminal `halted_prohibited`.
6. `park` (verdict, no transition/audit) ≠ `held` (regression state, audited).
7. Un-hold restores via full vector (earliest unsatisfied gate); `held_from_state` is a hint, not the target.
8. Approval write atomic with own audit; fan-out = one idempotent txn per use case.
9. `treatment_decision`/`treatment_rationale` write does **not** alter `ProvenanceConfidence`.
10. `classification_readiness` is the single readiness definition (shared by `create_aiia` + intake gate). Behaviour change: `create_aiia` adopts it (assessable off `eu_tier`, prohibition off snapshot; freeze `tier_snapshot` from `eu_tier`).
11. `tenant_id` from ctx; no new DB role; highest tier in Python (never SQL on the enum).

---

## 8. Tests

**apply_transition / state machine**
- stale from-state → 409 (0 rows); legal transition persists + writes `LifecycleTransition`+`AuditEvent` atomically.
- enum round-trips by-name; raw `.value` bind would miss (assert the helper binds by name).
- undefined `(state,event)` rejected.

**auto-advance**
- create, cleared vendor+product, signed-off HIGH → advances `requested→…→under_assessment`, parks (no AIIA); per-hop transitions audited.
- no catalogue link → vendor/product N/A pass.
- 2nd use case of cleared product → passes vendor/product for free (inheritance).
- atomicity: sign-off stamping `eu_tier` + the advance are both visible only post-commit (same txn).

**prohibited (#1)**
- bridge prohibited at creation → `halted_prohibited` on creation pass.
- **context prohibited** (`PENDING_REVIEW` snapshot `tier=PROHIBITED`, `eu_tier` unstamped) → step-0 reads `snapshot.tier` → `halted_prohibited`.
- re-classify to prohibited at `under_assessment` → forced `halted_prohibited`.
- `halted_prohibited` terminal — no event advances.

**intake / readiness**
- `eu_tier=REQUIRES_CONTEXT`, no PENDING_REVIEW → park, court=user; with PENDING_REVIEW snapshot → court=reviewer.
- unsigned context (PENDING_REVIEW, `eu_tier` still REQUIRES_CONTEXT) → intake parks; `create_aiia` → 409.
- signed-off HIGH → intake advances; `create_aiia` proceeds, `tier_snapshot=HIGH`.

**vendor/product gates**
- PENDING/absent → park; expired `valid_until` → park; APPROVED & valid → advance.

**assessment gate**
- AIIA missing → park; REQUIRED feeder (HIGH+deployer FRIA) missing → park; still-`AI_SUGGESTED` item → park; all dispositioned + required feeders present → advance.

**treatment gate**
- dispositioned risk, no `treatment_decision` → park.
- `MITIGATE` w/o control-link & empty `mitigation_plan` → park; w/ control-link → pass.
- `ACCEPT` w/o `treatment_rationale` → park; w/ rationale → pass.
- set `treatment_decision` on `USER_CONFIRMED` risk → provenance **unchanged** (#9).
- set treatment on `AI_SUGGESTED` item → 409 (disposition-gated).

**full-vector / cursor / expiry**
- status GET recomputes, does **not** mutate `state`.
- approval expires post-advance → GET shows `held` verdict; `re-evaluate` → `state` becomes `held`.
- **un-hold w/ second lapse:** held at `under_assessment` (vendor revoked); product expires; vendor re-cleared; `re-evaluate` rests at `product_check`, not `under_assessment`.

**approvals / fan-out**
- set vendor approval → held/waiting use cases at `vendor_check` advance (each own txn).
- revoke vendor approval → advanced downstream use cases regress to `held`.
- fan-out idempotent (re-run → same state); approval write + own audit atomic.

**authz / tenancy**
- approval set: non-`authoriser` → 403; treatment write: outside `{system_owner,contributor}` → 403; status/rollup: all five roles allowed.
- cross-tenant `vendor_id` in approval request → fail-closed; `tenant_id` always from ctx.

---

## 9. Work items

Each WI is one plan-mode unit: propose → execute → land with its tests green. Order is dependency order. `dep` = blocking predecessors. Tests cited by §8 area.

### Phase A — spine to `under_assessment`

**WI-0 · Pre-flight verify** — dep: none
Run §0 checklist. Resolve the **blocking** context-PROHIBITED persistence question against `compute_and_record_classification` before any migration. Record findings + the M3 / LifecycleTransition decisions in `STATE.md`. *Done:* §0 boxes checked; downstream WIs know which columns exist.

**WI-1 · Migrations & enum** — dep: WI-0
M1 (`use_case.held_from_state`, `held_reason`); M3 if §0 showed absent; add `LifecycleTransition` columns if absent. Hand-edit grants/RLS in the migration. Add §2.8 by-name note. *Done:* upgrade/downgrade run clean on a seeded DB; no new DB role; `\d` confirms columns.

**WI-2 · `apply_transition` + legality** — dep: WI-1
Legality table (§2) as data; `apply_transition` sole mutator — conditional `UPDATE … WHERE state=:from`, enum bound by-name, stages `LifecycleTransition` + `AuditEvent`, clears held fields on forward exit from `held`. *Done:* §8 "apply_transition / state machine" green. No other code path writes `use_case.state`.

**WI-3 · Gate predicates** — dep: WI-1
Pure-read module: `vendor_gate`, `product_gate`, `assessment_gate`, and `classification_readiness` **extracted** as the shared primitive (READY/PARK/HALT). No state writes here. *Done:* §8 vendor/product/assessment/intake-readiness predicate cases green against fixtures.

**WI-4 · `create_aiia` adopts `classification_readiness`** — dep: WI-3
Refactor `create_aiia` to consume the shared primitive; freeze `tier_snapshot` from `eu_tier`; prohibition off snapshot. Behaviour-change WI — keep its existing tests + add the unsigned-context 409 case. *Done:* §8 intake/readiness cases green; no regression in existing AIIA tests.

**WI-5 · `advance_use_case` + trigger wiring** — dep: WI-2, WI-3
Step-0 prohibited check off `snapshot.tier` → `halted_prohibited`; advance loop. Wire `advance_use_case(uc)` into the same txn as: use-case create, `snapshot_classification`, `compute_and_record_classification`, `sign_off_classification`, item disposition. *Done:* §8 auto-advance + prohibited(both paths) green; atomicity test proves trigger+advance commit together.

**WI-6 · `full_vector`, `re_evaluate`, status + lever endpoints** — dep: WI-5
`full_vector` (ordered GateResults, first non-PASS = blocking); `re_evaluate` (advance or regress to `held`). `GET …/lifecycle` recompute-no-persist; `POST …/lifecycle/re-evaluate` (`system_owner`). *Done:* §8 full-vector/cursor cases green; status GET never mutates `state`.

**WI-7 · Approvals + fan-out** — dep: WI-1, WI-6
Approval model fields; `PUT /vendors|products/{id}/approval` (`authoriser`) → `set_*_approval` (write+audit atomic); `fan_out` = one idempotent `re_evaluate` txn per affected use case. *Done:* §8 approvals/fan-out + the un-hold-with-second-lapse case green; fan-out re-run idempotent.

**WI-8 · Rollup + portfolio reads** — dep: WI-6
`GET /systems/{id}/rollup`, `GET /portfolio` (view models; highest tier via Python `max`). All gov roles read. *Done:* rollup reflects live full vector; tier never computed in SQL.

### Phase B — treatment gate to `pending_authorisation`

**WI-9 · Treatment migration** — dep: WI-1
M2: `treatment_decision` enum (by-name) + `treatment_decision`, `treatment_rationale` columns. *Done:* migration clean; enum round-trips by-name.

**WI-10 · Treatment gate + amend path** — dep: WI-9, WI-5
Extend item PATCH (`{system_owner, contributor}`, `If-Match`, **provenance-neutral**) to set treatment fields; `treatment_gate`; advance `treatment_pending → pending_authorisation`. *Done:* §8 treatment-gate cases green; provenance-unchanged + AI_SUGGESTED-409 proven.

---

## 10. Sequencing & acceptance

**Phase A** = WI-0…WI-8 (demoable). **Phase B** = WI-9…WI-10.

**Acceptance — Phase A:** a use case registered against a cleared/uncleared vendor+product auto-advances or parks correctly; status surface + rollup reflect the full vector; approval changes fan out; prohibited (both bridge and context paths) halts.
**Acceptance — Phase B:** treatment decisions gate `treatment_pending → pending_authorisation`; provenance untouched by treatment writes.