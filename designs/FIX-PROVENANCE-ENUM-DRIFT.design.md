# DESIGN (FINAL) · FIX-PROVENANCE-ENUM-DRIFT

**Sprint (provisional):** `FIX-PROVENANCE-ENUM-DRIFT` · backend defect + canon reconcile
**Status:** DESIGN FINAL · review folded (B1–B3, N1–N4, SV1–SV2) · handoff ready
**Problem:** three sites emit `ProvenanceConfidence.USER_PROVIDED`, a phantom ORM member absent from the live four-value `pg_enum`, so any path that inserts it 500s (`InvalidTextRepresentation`).
**Blast radius (ALTER):** `app/models/base.py`, `app/services/assessment_service.py` (`_add_snapshot_item`, `amend_item`, `create_item_from_section`, `_is_pristine`), tests, canon reconcile (DATA-MODEL §5, PAT-8, V-5).
**Backend delta:** code + tests only. **Migrations:** 0 (label never in `pg_enum`; zero rows structurally). **Routes:** 0. **Tables:** 0. **Enums:** ORM member removed; `pg_enum` unchanged.
**New IDs (provisional, re-base at build, SV-6):** `D-82`, `INV-93`, `INV-94`.
**Cross-refs:** PAT-8, PAT-9, INV-13, INV-14, INV-17, INV-23, INV-36, INV-83, D-1, D-21, FE-15, DATA-MODEL §2/§5, V-2, V-5.

---

## 1. Diagnosis (grounded, corrected from review)

Three sites in `assessment_service.py` emit `USER_PROVIDED`, all confirmed against HEAD:

1. `_add_snapshot_item` (create_aiia Pre-fill 2 and MODEL_RISK feeder): register-fact snapshots. `source_ref` set.
2. `amend_item`: the `CATALOGUE_CURATED → authored` provenance flip when a user authors a blank curated section prompt (`new_provenance = USER_PROVIDED if item.provenance == CATALOGUE_CURATED`). `source_ref` null. Documented in the `AssessmentItemAmend` docstring.
3. `create_item_from_section`: create-with-response path (`provenance = USER_PROVIDED if response is not None else CATALOGUE_CURATED`). `source_ref` null.

The live `provenance_confidence` `pg_enum` has four labels only (`AI_SUGGESTED`, `CATALOGUE_CURATED`, `USER_CONFIRMED`, `USER_AMENDED`; DATA-MODEL §2, §5; PAT-8; confirmed V-2). The ORM enum still declares a fifth, `USER_PROVIDED`. Site 1 is the reported 500. Sites 2 and 3 are the same 500 latent on the authoring path, masked only because bootstrap 500s first. Green in the suite because the test DB builds the type from the five-member ORM (PAT-9, verbatim).

**Provenance of the drift.** The fifth value was designed in the original AIIA sprint for user-origin content with no system default (`base.py` member comment: section answer, from-scratch item, snapshotted register fact). The provenance model was later consolidated to the four-value confirm/amend ladder; the fifth was rejected at the DB (DATA-MODEL §5) and PAT-8 restated the rule, leaving the flag "confirm against `create_aiia`." The DB side landed; the ORM member and the three call sites were not cleaned up. F3 pre-flight V-5 recorded the survivor as intended ("5-value mirror") rather than debt. This fix retires all three call sites, deletes the member, and corrects V-5.

**Zero-row guarantee.** No real row can carry `USER_PROVIDED` (every insert 500s), so member removal needs no data migration.

## 2. Resolved decisions

| # | Decision | Rationale | Rejected |
|---|---|---|---|
| R1 | Hold `provenance_confidence` at four labels; delete the `ProvenanceConfidence.USER_PROVIDED` ORM member | Upholds the locked four-value decision (DATA-MODEL §5, D-1, V-2); restores ORM/`pg_enum` parity so the PAT-9 drift class closes. | `ALTER TYPE ADD VALUE 'user_provided'`: reverses a locked decision, needs a migration, and re-widens the provenance vocabulary for a distinction with no read-time governance weight. |
| R2 | `_add_snapshot_item` (site 1) → `USER_CONFIRMED` | Register snapshots are user-origin facts the user stood behind at registration (INV-83 recorded them `USER_CONFIRMED`/`USER_AMENDED` in `prefill_disposition`); passively inherited, not authored in the AIIA. **Founder-confirmed.** | Per-field inherit from `prefill_disposition`: a second home for a single-homed truth; partial (some snapshot fields have no disposition row). |
| R3 | `amend_item` `CATALOGUE_CURATED → authored` flip (site 2) → `USER_AMENDED` | Authoring a blank curated prompt is active user content: amended-from-blank-framing. Outside the override-rate population (that axis reads AI_SUGGESTED-origin risk items, PRD §7.1), so this is a defect-class retag, not a metric change. FE-15 renders `--prov-user-amended`; zero frontend delta. | `USER_CONFIRMED`: reads as passive acceptance of a default that never existed; loses the active-authoring signal. |
| R4 | `create_item_from_section` create-with-response (site 3) → `USER_AMENDED` | Same act as R3 (user authors a section answer); keep the two authoring paths on one tag. `source_ref` null → counts as worked. | `USER_CONFIRMED`: inconsistent with site 2 for the identical act. |
| R5 | `_is_pristine` worked-detection: `provenance IN (USER_CONFIRMED, USER_AMENDED) AND source_ref IS NULL`; drop the `USER_PROVIDED` clause | The live predicate is a positive `or_` of `IN (USER_CONFIRMED, USER_AMENDED)` and `and_(== USER_PROVIDED, source_ref IS NULL)`. After R2, snapshots (`USER_CONFIRMED`, `source_ref` set) would match the first clause and mark a fresh bootstrap non-pristine. Gating on `source_ref IS NULL` excludes exactly the snapshots. | Keep the tag-keyed clause: post-retag it either dead-branches or wrongly blocks pristine bootstrap delete. |
| R6 | Mint INV-93 (ORM/`pg_enum` parity guard) and INV-94 (`source_ref` snapshot discriminator) | R1 closes this instance; INV-93 makes the class fail a test. Post-R2, `source_ref` is the sole snapshot-vs-worked discriminator (previously the distinct tag carried it), so it must be pinned (INV-94). | Leave both as prose: the drift recurs silently on the next enum change or emit site. |

## 3. Present vs ALTER

| File | State | Change |
|---|---|---|
| `app/models/base.py` | ALTER | Delete `ProvenanceConfidence.USER_PROVIDED` and its comment. Model default stays `USER_CONFIRMED` (`assessment.py`), unaffected. |
| `app/services/assessment_service.py` | ALTER | Site 1 `_add_snapshot_item`: `provenance=USER_CONFIRMED`; update docstring. Site 2 `amend_item`: flip target `CATALOGUE_CURATED → USER_AMENDED`; update the `AssessmentItemAmend` docstring reference. Site 3 `create_item_from_section`: `USER_AMENDED if response is not None else CATALOGUE_CURATED`. `_is_pristine`: predicate per R5; update inline comment. Confirm no fourth `USER_PROVIDED` reference in the module (P2). |
| `app/schemas/assessment.py` | Present | No change: `provenance: ProvenanceConfidence` narrows only; confirm no default/validator names the removed member (SV-E). |
| Frontend provenance display | Clean (verify, expect no-op) | Review confirmed FE-15 is four-value; `item-card.tsx` branches only `ai_suggested`/`catalogue_curated`; `ProvenanceBadge` maps the four live values. P2 grep of `apps/` expected to return nothing; remove any dead `user_provided` case if found. Reclassified from ALTER to Clean. |
| tests | ALTER | Retag snapshot-provenance assertions to `USER_CONFIRMED`; retag the two authoring-flip assertions to `USER_AMENDED`; add a pristine-delete test on a freshly bootstrapped AIIA and a non-pristine test on an authored-section AIIA; add the INV-94 discriminator test; add the INV-93 parity guard (live-DB lane, R-N3); add a PAT-9 live-DB bootstrap smoke. |
| `docs/DATA-MODEL.md` §5, `docs/PATTERNS.md` PAT-8, V-5 record | ALTER (canonical-update WI) | §5: ORM member removed, parity restored. PAT-8: resolve the "confirm against `create_aiia`" flag; state snapshots = `USER_CONFIRMED`, authored-section flips = `USER_AMENDED`. Correct the V-5 note: ORM is four-value; "5-value mirror" was debt, not intent. |

**Non-regressions to confirm (not ALTER):** (a) authoring gate: `USER_CONFIRMED`/`USER_AMENDED` are not in the `AI_SUGGESTED` block set, so disposition-before-authoring (PAT-8) is unchanged. (b) `lock_version` (INV-14) and the amend audit `field_detail["provenance"]` before/after (now `catalogue_curated → user_amended`) unchanged in shape. (c) `confirm_item` (AI_SUGGESTED → USER_CONFIRMED) untouched.

## 4. Invariants

**INV-93 (CONVENTION, new).** Every `SAEnum`-mapped ORM enum's member value-set must equal its live `pg_enum` label-set. A parity guard asserts this per Postgres-backed enum against the migrated dev DB. Python-only enums (`ClassificationDisposition`; reserved `TreatmentDecision` members) are out of scope (no `pg_enum`). The guard runs in the live-DB lane only (PAT-9): in the `create_all` no-RLS harness the type is generated from the ORM and is self-consistent by construction, so the guard is a false green there and must be excluded. A member present in one set but not the other is a build-blocking failure. Cross-refs: PAT-9, INV-23, D-21.

**INV-94 (CONVENTION, new).** A register-fact snapshot item carries a non-null `source_ref`; no confirmed or amended worked item carries a `source_ref`. This is the sole discriminator separating a `USER_CONFIRMED` snapshot from a `USER_CONFIRMED`/`USER_AMENDED` worked item after the four-value collapse, and it is load-bearing for `_is_pristine` (R5). Any new snapshot emit site sets `source_ref`; no authoring path sets it. Cross-refs: INV-17, INV-36, PAT-8, single-home.

## 5. §0 pre-flight verify checklist (D-21, run at build before any edit)

- [ ] **P1 (live enum).** `\dT+ provenance_confidence` returns exactly the four labels. A fifth present → STOP (an unrecorded migration exists).
- [ ] **P2 (emit-site enumeration).** `grep -rn USER_PROVIDED app/ apps/ tests/ docs/`. Expected emit sites: `_add_snapshot_item`, `amend_item`, `create_item_from_section`. Any other emit site is in scope and retagged; read/switch sites are dead and removed. This grep is the guard against a further undercount (the miss the review caught).
- [ ] **P3 (zero rows).** `SELECT count(*) FROM assessment_item WHERE provenance::text = 'USER_PROVIDED'` returns 0. Cast to `::text`: the bare `= 'USER_PROVIDED'` raises `invalid input value` (label absent), which is not a STOP condition.
- [ ] **P4 (pristine predicate).** Read `_is_pristine` in full; confirm register snapshots are the only create-time items carrying non-null `source_ref`, so R5 excludes exactly them (INV-94).
- [ ] **P5 (frontend no-op).** Confirm no `user_provided` case in `ProvenanceBadge`/`item-card.tsx`/FE-15 tokens; expect none.
- [ ] **P6 (id re-base).** Re-base `D-82`/`INV-93`/`INV-94` against the live volatile canonicals (the routing sprint minted `D-81`/`INV-92`; those rest on STATE/INDEX, which lag this mirror). Never renumber a live id (SV-6).

## Appendix A — Open decisions

- **A1 (authoring-flip target).** R3/R4 set sites 2 and 3 to `USER_AMENDED`. This is the one judgement folded from review (B2) rather than founder-confirmed. It is defect-class (outside the override-rate population, verified), so it is not gated on founder sign-off, but it is flippable to `USER_CONFIRMED` at §0 without any other change (both are worked under R5). Default: `USER_AMENDED`.
- **A2 (INV-93 live-DB lane).** The parity guard requires a migrated-DB connection. If no automated live-DB CI lane exists, it runs as the PAT-9 manual smoke and the handoff notes the gap rather than asserting a green CI guard. Confirm the lane at §0.
- **A3 (INV-94 vs PAT-8 home).** INV-94 could instead extend PAT-8's text. Default: mint INV-94 (a checkable CONVENTION constraint distinct from PAT-8's provenance-machine shape). Review-adjudicable.

## Appendix B — Source-verification register

| ID | Claim to verify | Target (file:line at HEAD) |
|---|---|---|
| SV-A | The three emit sites are the complete set (`_add_snapshot_item`, `amend_item`, `create_item_from_section`) | `app/services/assessment_service.py` |
| SV-B | `_is_pristine` worked-detection `or_` shape; `source_ref` present only on snapshots at create time | `app/services/assessment_service.py` |
| SV-C | Live `pg_enum` provenance_confidence = four labels | dev DB `\dT+ provenance_confidence` |
| SV-D | No frontend `user_provided` case | `apps/tenant` `ProvenanceBadge`, `item-card.tsx`, FE-15 tokens |
| SV-E | No schema default/validator names the removed member | `app/schemas/assessment.py` |
| SV-F | V-5 note; DATA-MODEL §5 flag; PAT-8 `create_aiia` flag | `assessment-page-client.tsx` V-5 note; `docs/DATA-MODEL.md` §5; `docs/PATTERNS.md` PAT-8 |
| SV-G | Live D-n / INV-n ceiling (routing sprint `D-81`/`INV-92` landed) | volatile canonicals / repo |