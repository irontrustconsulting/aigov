# PATTERNS.md — IronTrust AI Governance Platform

**Location:** `docs/PATTERNS.md` — single source, mirrored to project knowledge. Updated occasionally (a new pattern is appended when a sprint establishes one).
**Purpose:** The established implementation shapes a new feature reuses, and the reference a reviewer checks an implementation's shape against. Each `PAT-n` realises an invariant and is justified by a decision.
**Lanes:** endpoint *structure* (router location, gating, schemas) → `ARCHITECTURE.md §9`; the constraint each shape enforces → `INVARIANTS.md`; the rationale → `DECISIONS.md`.

---

## Service-shape selector

A new service picks exactly one shape by two questions:

| Does it call an external system? | Must a commit failure undo the external side-effect? | Shape |
|---|---|---|
| No | — | **PAT-2** (no external call) |
| Yes — fast (Cognito) | Yes | **PAT-1** (hold the transaction, compensate) |
| Yes — slow (S3 put) | n/a — no connection may be held | **PAT-3** (hold no transaction) |

Know which shape a path needs *before* writing it — PAT-1 and PAT-3 are opposites and must not be blended (INV-18).

---

## PAT-1 · External call, transaction held to compensate

**When:** a tenant service calls an external system (Cognito) where a commit failure must be able to undo the external side-effect. The service owns its own DB session.

**Shape:**
```
1. Pre-check in DB            (fail fast before any external call)
2. Optional DB inserts + flush (uncommitted)
3. External call             → failure → rollback; nothing persisted
4. DB inserts that depend on the external result
5. Stage AuditEvent
6. Commit                    → failure → best-effort compensate external; re-raise
```
The transaction is deliberately held across the external call so step 6 can compensate. Implemented in `provision_tenant`, `provision_member`. Shared Cognito helpers (`create_cognito_user`, `delete_cognito_user`, `get_cognito_user_status`) live in `app/services/cognito_helpers.py` — reuse, do not duplicate.
↳ refs: INV-18 (contrast with PAT-3)

## PAT-2 · Tenant-plane, no external call

**When:** tenant-plane work with no external call (`assessment_service` AIIA/feeder creation and mutation; the context-classification service).

**Shape:** pre-check in DB → stage the business-row writes and the `AuditEvent` in the same session → `db.flush()`. No ordering choreography — `get_tenant_db` commits the whole request atomically.
↳ refs: PAT-4 (auditing)

## PAT-3 · Slow external call, no transaction held

**When:** an external call that may run long (an S3 put up to the upload cap), so no DB connection may be held idle.

**Shape:** the route depends on `get_tenant_context` (no session), **not** `get_tenant_db` (which holds a connection for the whole request). The service opens two independent short sessions of its own (`SessionLocal`, not `Depends`): one **before** the put (role pre-check), one **after** (row + audit insert); the put runs in between holding neither. On commit failure of the second session, compensate the S3 object (delete by version-or-key) before re-raising. Implemented in `evidence_service.upload_evidence`.
↳ refs: INV-18 · use this for any future upload/slow-external path; do not bolt it onto PAT-1

---

## PAT-4 · Auditing

- **Tenant plane:** add an `AuditEvent` to the session and commit it atomically with the business rows — never commit audit separately. `AuditEvent` is append-only (INV-5).
- **Platform plane:** use `record_platform_event()` from `app/services/audit.py`.
- Action strings follow an `entity.verb` convention. The current set in use is listed in `STATE.md` (audit trail).
↳ refs: INV-5

## PAT-5 · Classification read / write separation

`resolve_classification` (bridge) and `resolve_context_classification` (decision tree) are **pure reads**, safe to call repeatedly. `snapshot_classification` and `compute_and_record_classification` **write**; the caller owns the transaction. `sign_off_classification` is the only thing that stamps `use_case.eu_tier` (context path). Keep resolution and persistence separate, and never re-enter either resolver from AIIA/feeder code — that code reads only the persisted current snapshot.
↳ refs: INV-11 · D-9

## PAT-6 · Optimistic concurrency (`lock_version` / `If-Match`)

Every mutating endpoint that changes a provenance-bearing row takes an `If-Match` header carrying the expected `lock_version`; the mutation is a **single conditional** `UPDATE … WHERE id = :id AND lock_version = :expected [AND <from-state guard>]`. A stale lock → `412`; a wrong from-state → `409` — deliberately distinguishable. Never read-then-write; the from-state check lives in the `WHERE` clause, not in application code after a separate `SELECT`.
↳ refs: INV-14

## PAT-7 · Read-time reference propagation (not copy)

Feeders surface into their parent AIIA by assembling a view at read time (`assemble_aiia_items`) — never by writing a copy into the AIIA or syncing on edit. If a future feature needs one entity's content to appear inside another's read response, prefer this shape (join at read time, tag the source) over duplicating rows.
↳ refs: INV-16 · D-18

## PAT-8 · Provenance machine (§1.5)

Every system-proposed or system-derived value carries a `ProvenanceConfidence` tag. The live enum is **4-value**: `AI_SUGGESTED`, `CATALOGUE_CURATED`, `USER_CONFIRMED`, `USER_AMENDED` (`USER_CONFIRMED`/`USER_AMENDED` mean a system default was accepted or changed). Provenance is **always server-derived, never accepted as request input**. A still-`AI_SUGGESTED` item must be confirmed or amended before its authoring fields can be written (disposition-before-authoring); section-prompt items (`CATALOGUE_CURATED`) are exempt, since answering them isn't overriding a default. **Register-derived facts** (system/use-case facts pulled into an AIIA at creation, `create_aiia`'s `_add_snapshot_item`) carry no system default behind them and sit outside this confirm/amend ladder — they get `USER_CONFIRMED` (a human stood behind them at registration, INV-83) plus a non-null `source_ref`; they do **not** get a `USER_PROVIDED` tag (that label does not exist; a fifth state was considered and rejected — DATA-MODEL §5). The two authored-content flips (`amend_item`'s `CATALOGUE_CURATED →` transition, `create_item_from_section`'s create-with-response) get `USER_AMENDED`. Post-collapse, `source_ref` (non-null only on snapshots) is the sole discriminator between a `USER_CONFIRMED` snapshot and a worked item under the same tag — INV-94 pins this; INV-93 guards ORM/`pg_enum` parity (FIX-PROVENANCE-ENUM-DRIFT).
↳ refs: INV-13, INV-93, INV-94 · D-1, D-82

## PAT-9 · Live-smoke-test RLS-sensitive code against the real dev DB

The test DB (`irontrustai_test`) is built via `Base.metadata.create_all()` — no RLS, no triggers, no grants, and its enum types are generated fresh from the ORM declaration, so they are always self-consistent. None of that is true of a real migrated database. A green test suite proves business logic; it proves **nothing** about RLS-scoped queries, `SET LOCAL`/`app.current_tenant` handling, or enum label case against the real schema. Before trusting new code that touches any of those — a new fan-out/background-session pattern, a new enum, a new RLS-scoped query path — run it once against the actual dev Postgres (`docker compose up -d`, `alembic upgrade head`) using the real `SessionLocal`/role, not just the test harness.
↳ refs: INV-23, INV-27 · D-21 — both bugs caught this way were live while the full suite stayed green

## PAT-10 · Consistent-read self-owned session (export pack)

**When:** a multi-entity read-assembly that must be internally consistent (an export pack spanning many use cases) and stages exactly one disclosure-audit write.

**Shape:** the route depends on `get_tenant_context` (no session), not `get_tenant_db`. The service opens its own session, sets `isolation_level="REPEATABLE READ"` via `execution_options` **at acquisition — before the first query** (Postgres requires the isolation level before the transaction's first statement, and `SET LOCAL` is a statement), then `SET LOCAL app.current_tenant` from `ctx`, then assembles, then **owns the `export.generated` commit itself**. Never raw `SET TRANSACTION` after `SET LOCAL`. Reusing `get_tenant_db` is wrong here — it would own the commit and run READ COMMITTED.

Distinct from PAT-3: both are self-owned sessions, for opposite reasons. PAT-3 holds *no* transaction across a slow S3 put; PAT-10 deliberately holds one long-lived `REPEATABLE READ` transaction for snapshot consistency. The `content_hash` is computed over a canonical serialization (sorted keys, ISO-8601 UTC, no insignificant whitespace) *before* staging the audit, so it lands in `detail`.
↳ refs: INV-27 (ordering cousin), INV-42, INV-43 · D-30, D-35