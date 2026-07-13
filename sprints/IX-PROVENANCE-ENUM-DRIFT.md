# HANDOFF · FIX-PROVENANCE-ENUM-DRIFT (execution-only)

**Class:** backend defect + canon reconcile. **Migrations:** 0. **Routes:** 0. **Tables/enums:** ORM member removed; `pg_enum` unchanged.
**Rationale lives in `FIX-PROVENANCE-ENUM-DRIFT.design.md`; do not re-derive it here.**
**Guardrail (INV-68/D-51):** implement only. Provenance targets are fixed below; do not choose or re-derive them. If a fourth `USER_PROVIDED` emit site appears at §0 P2, STOP and report rather than tag it yourself.

---

## §0 Pre-flight (do first; do not edit until all pass)

- [ ] **P1.** `\dT+ provenance_confidence` returns exactly `AI_SUGGESTED, CATALOGUE_CURATED, USER_CONFIRMED, USER_AMENDED`. A fifth label present → STOP, report.
- [ ] **P2.** `grep -rn USER_PROVIDED app/ apps/ tests/ docs/`. Expected emit sites exactly: `_add_snapshot_item`, `amend_item`, `create_item_from_section` (all in `assessment_service.py`). If any other **emit** site exists, STOP and report before editing. Read/switch/comment sites are in scope for removal.
- [ ] **P3.** `SELECT count(*) FROM assessment_item WHERE provenance::text = 'USER_PROVIDED'` returns 0. (Cast `::text`; the bare comparison errors, which is not a STOP.)
- [ ] **P4.** Read `_is_pristine` in full. Confirm its worked-detection is a positive `or_` of `provenance IN (USER_CONFIRMED, USER_AMENDED)` and `and_(provenance == USER_PROVIDED, source_ref IS NULL)`, and that register snapshots are the only create-time items with non-null `source_ref`.
- [ ] **P5.** Confirm no `user_provided` case in `ProvenanceBadge`, `item-card.tsx`, or FE-15 tokens. Expect none.
- [ ] **P6 (id re-base).** Live ceilings: re-base `D-82`/`INV-93`/`INV-94` against the volatile canonicals (routing sprint minted `D-81`/`INV-92`; verify at HEAD). Take the next free ids; never renumber a live id.
- [ ] **P7 (live-DB lane).** Determine whether an automated live-DB test lane exists (migrated Postgres, real `SessionLocal`/role, PAT-9). WI-4's parity guard and WI-5's smoke run there; if none exists, WI-4 documents the manual PAT-9 smoke instead of asserting a CI guard.

---

## Work items (dependency-ordered)

### WI-1 · Retag the three emit sites (must precede member deletion)
- `app/services/assessment_service.py`:
  - `_add_snapshot_item`: `provenance=ProvenanceConfidence.USER_CONFIRMED`; update docstring (drop "USER_PROVIDED").
  - `amend_item`: change the flip so `item.provenance == CATALOGUE_CURATED` maps to `ProvenanceConfidence.USER_AMENDED`.
  - `create_item_from_section`: `ProvenanceConfidence.USER_AMENDED if response is not None else ProvenanceConfidence.CATALOGUE_CURATED`.
- **Done-check:** `grep -rn USER_PROVIDED app/` returns only the `base.py` member (removed in WI-2) and any comment; no emit site remains.

### WI-2 · Delete the ORM member (depends on WI-1)
- `app/models/base.py`: delete `ProvenanceConfidence.USER_PROVIDED` and its comment.
- **Done-check:** `python -c "from app.models.base import ProvenanceConfidence; assert not hasattr(ProvenanceConfidence, 'USER_PROVIDED')"`; app imports clean.

### WI-3 · Correct `_is_pristine` (depends on WI-1)
- `app/services/assessment_service.py` `_is_pristine`: replace the worked-detection so it is `provenance IN (USER_CONFIRMED, USER_AMENDED) AND source_ref IS NULL`. Remove the `USER_PROVIDED` clause entirely. Update the inline comment.
- **Done-check:** new tests in WI-4 (pristine + non-pristine) green.

### WI-4 · Tests (depends on WI-1, WI-2, WI-3)
- Retag existing assertions: snapshot items → `USER_CONFIRMED`; the two authoring flips → `USER_AMENDED`.
- Add: (a) a freshly bootstrapped AIIA (snapshots + curated prompts + AI risks, no human act) is pristine-deletable; (b) an AIIA with one authored section item (`USER_AMENDED`, `source_ref` null) is NOT pristine; (c) INV-94 discriminator: a snapshot carries non-null `source_ref`, an authored/confirmed item carries null.
- INV-93 parity guard: assert `{m.value for m in ProvenanceConfidence}` equals the live `pg_enum provenance_confidence` labels. Mark it for the live-DB lane (P7); exclude it from the `create_all` no-RLS harness (false green there). If no automated lane exists, land it as a documented PAT-9 smoke step and note the gap.
- **Done-check:** full suite green in the default harness; the parity guard green against migrated dev Postgres (or the manual smoke recorded).

### WI-5 · Live-DB smoke + regression (depends on WI-1..4)
- Run `POST /v1/use-cases/{id}/assessments` bootstrap against migrated dev Postgres (PAT-9) for a `limited_risk` catalogue-linked use case: expect 201 and snapshot items at `USER_CONFIRMED`. Author a curated section item via PATCH: expect `USER_AMENDED`, no 500.
- **Done-check:** both live-DB calls succeed; `apps/tenant` + `app/` suites green; typecheck/lint clean.

### WI-6 · Canonical update (last; volatile tier only)
- **STATE.md:** add a `FIX-PROVENANCE-ENUM-DRIFT` entry: three emit sites retagged (snapshot → `USER_CONFIRMED`; two authoring flips → `USER_AMENDED`), phantom ORM member removed, `_is_pristine` predicate corrected, 0 migration/route/table/enum-DDL delta.
- **DATA-MODEL.md §5:** ORM member removed; ORM/`pg_enum` parity restored; note INV-93 guards it.
- **PATTERNS.md PAT-8:** resolve the "confirm against `create_aiia`" flag; record snapshots = `USER_CONFIRMED`, authored-section flips = `USER_AMENDED`; register facts sit outside the confirm/amend ladder and carry no fifth tag.
- **V-5 record** (`assessment-page-client.tsx` pre-flight note): correct "ProvenanceConfidence is 5-value" to four-value; the prior member was debt, not intent.
- **INVARIANTS.md:** append `INV-93` (SAEnum/`pg_enum` parity, live-DB lane) and `INV-94` (`source_ref` snapshot discriminator) per design §4.
- **DECISIONS.md:** append `D-82` per design §2 (hold four-value, delete member, three retag targets, corrected pristine predicate; supersedes the V-5 "5-value mirror" record).
- Do not renumber any live id; leave the stable tier untouched.
- **Done-check:** ceilings advanced; INDEX ceiling line updated; `docs/` "Sync now" reminder noted for the founder.