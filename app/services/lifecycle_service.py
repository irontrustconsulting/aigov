"""
Lifecycle state machine — the sole mutator of UseCase.state (Sprint 5, WI-2).

apply_transition() is the single locus every other piece of lifecycle code
(advance_use_case, re_evaluate, the approval fan-out — WI-5/6/7) goes through
to move a use case. It never re-derives legality from scratch; legality is a
small table-driven check (STATE_MACHINE.md §4.1/§4.2).

Concurrency: the transition is one conditional UPDATE guarded by the
from-state in the WHERE clause (STATE.md inv 14) — never read-then-write.
Zero rows affected means the use case has already moved (a stale read), and
is reported as 409, distinguishable from the 412 a stale lock_version would
report elsewhere in this codebase.

Enum binding: LifecycleState is stored by Postgres enum *member name*, not
`.value` (STATE.md inv 23, confirmed off the live DDL). Binding through the
typed SQLAlchemy column (as below) does this correctly; never compare against
`LifecycleState.X.value` in a raw clause.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import func, select, text, update
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.base import ApprovalStatus, EUAIActTier, LifecycleState
from app.models.domain import (
    CatalogueProduct,
    CatalogueVendor,
    ProductApproval,
    System,
    UseCase,
    VendorApproval,
)
from app.models.identity import Membership, User
from app.models.lifecycle import AuditEvent, LifecycleTransition
from app.schemas.lifecycle import (
    ClearanceQueueRead,
    GateResultRead,
    ProductClearanceEntry,
    SystemRollupRead,
    UseCaseRollupEntry,
    VendorClearanceEntry,
)
from app.services.lifecycle_gates import (
    GateResult,
    assessment_gate,
    authorisation_gate,
    classification_readiness,
    product_gate,
    treatment_gate,
    vendor_gate,
)

# ---------------------------------------------------------------------------
# Legality table (STATE_MACHINE.md §2 / handoff §2) — data, not branching code.
# ---------------------------------------------------------------------------

# event="advance": the single-hop forward edge a passing gate drives.
_ADVANCE_TABLE: dict[LifecycleState, LifecycleState] = {
    LifecycleState.REQUESTED: LifecycleState.VENDOR_CHECK,
    LifecycleState.VENDOR_CHECK: LifecycleState.PRODUCT_CHECK,
    LifecycleState.PRODUCT_CHECK: LifecycleState.INTAKE,
    LifecycleState.INTAKE: LifecycleState.UNDER_ASSESSMENT,
    LifecycleState.UNDER_ASSESSMENT: LifecycleState.TREATMENT_PENDING,
    LifecycleState.TREATMENT_PENDING: LifecycleState.PENDING_AUTHORISATION,
}

# States a use case can have been auto-advanced through — "already passed an
# upstream gate" is only meaningful from one of these (handoff §2: "any
# advanced" -> held). REQUESTED never holds: nothing has passed yet.
# AUTHORISED is added explicitly (Sprint 6b) — it is never an
# _ADVANCE_TABLE value (entry is by human act only, see authorisation_gate
# wiring in full_vector), but "hold" must still be legal from it so
# re_evaluate can regress an authorised use case (design doc §6.3, inv 33).
_ADVANCED_STATES = frozenset(_ADVANCE_TABLE.values()) | {LifecycleState.AUTHORISED}

# event="halt": the prohibited rule fires from any non-terminal state
# (STATE_MACHINE.md §5.5). HALTED_PROHIBITED itself is terminal — re-halting
# a halted use case is undefined, not idempotent.
_TERMINAL_STATES = frozenset({LifecycleState.HALTED_PROHIBITED})

_AUDIT_ACTION_BY_EVENT = {
    "created": "lifecycle.advanced",
    "advance": "lifecycle.advanced",
    "restore": "lifecycle.advanced",
    "hold": "lifecycle.held",
    "halt": "lifecycle.halted_prohibited",
    "authorise": "lifecycle.authorised",
}


def _is_legal(from_state: LifecycleState, event: str, to_state: LifecycleState) -> bool:
    if event in ("created", "advance"):
        return _ADVANCE_TABLE.get(from_state) == to_state
    if event == "halt":
        return (
            to_state == LifecycleState.HALTED_PROHIBITED
            and from_state not in _TERMINAL_STATES
        )
    if event == "hold":
        return to_state == LifecycleState.HELD and from_state in _ADVANCED_STATES
    if event == "restore":
        # Un-hold target is whatever gate the full vector lands on — always
        # one of the canonical forward states by construction (STATE_MACHINE
        # §4.1, #13). Only legal starting from HELD.
        return from_state == LifecycleState.HELD and to_state in _ADVANCED_STATES
    if event == "authorise":
        # The sole entry point into AUTHORISED (Sprint 6b, D10/inv 35) — never
        # derived by advance/restore. authorise_use_case is the only caller.
        return (
            from_state == LifecycleState.PENDING_AUTHORISATION
            and to_state == LifecycleState.AUTHORISED
        )
    return False


def apply_transition(
    db: Session,
    use_case: UseCase,
    event: str,
    to_state: LifecycleState,
    actor_user_id: uuid.UUID,
    reason: str | None,
    *,
    held_reason: str | None = None,
) -> UseCase:
    """The sole writer of use_case.state / LifecycleTransition (STATE.md
    invariant: apply_transition is the only mutator — no other code path may
    write use_case.state).

    Raises ValueError for an undefined (from_state, event) -> to_state combo
    (a caller bug — legality is computed by the gate engine, never user
    input, so this is never a 4xx). Raises HTTPException(409) when the
    conditional UPDATE affects zero rows (the use case moved since it was
    read — a concurrency conflict, not a caller bug).
    """
    from_state = use_case.state
    if not _is_legal(from_state, event, to_state):
        raise ValueError(
            f"Illegal lifecycle transition: ({from_state.name}, {event!r}) "
            f"-> {to_state.name}"
        )

    values: dict[str, object] = {"state": to_state}
    if event == "hold":
        values["held_from_state"] = from_state
        values["held_reason"] = held_reason
    elif from_state == LifecycleState.HELD:
        # Leaving HELD (restore or a halt fired while held) clears the hint —
        # it was never the restore target, only UX context (STATE_MACHINE §4.4).
        values["held_from_state"] = None
        values["held_reason"] = None

    result = db.execute(
        update(UseCase)
        .where(
            UseCase.id == use_case.id,
            UseCase.tenant_id == use_case.tenant_id,
            UseCase.state == from_state,
        )
        .values(**values)
    )
    if result.rowcount == 0:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="Use case lifecycle state changed concurrently; reload and retry",
        )

    for key, value in values.items():
        setattr(use_case, key, value)

    db.add(
        LifecycleTransition(
            id=uuid.uuid4(),
            tenant_id=use_case.tenant_id,
            use_case_id=use_case.id,
            from_state=from_state,
            to_state=to_state,
            actor_user_id=actor_user_id,
            reason=reason,
        )
    )
    db.add(
        AuditEvent(
            id=uuid.uuid4(),
            tenant_id=use_case.tenant_id,
            actor_user_id=actor_user_id,
            action=_AUDIT_ACTION_BY_EVENT[event],
            entity_type="use_case",
            entity_id=use_case.id,
            detail={
                "from_state": from_state.name,
                "to_state": to_state.name,
                "event": event,
            },
        )
    )
    db.flush()
    return use_case


# ---------------------------------------------------------------------------
# advance_use_case (Sprint 5, WI-5) — the auto-advance driver.
# ---------------------------------------------------------------------------


_GATE_FNS = {
    LifecycleState.VENDOR_CHECK: vendor_gate,
    LifecycleState.PRODUCT_CHECK: product_gate,
    LifecycleState.INTAKE: classification_readiness,
    LifecycleState.UNDER_ASSESSMENT: assessment_gate,
    LifecycleState.TREATMENT_PENDING: treatment_gate,
}

# The ordered positional sequence full_vector reports on — every state a
# gate guards, REQUESTED excluded (its "gate" is unconditional, §4.1 row 1).
_VECTOR_STATES = (
    LifecycleState.VENDOR_CHECK,
    LifecycleState.PRODUCT_CHECK,
    LifecycleState.INTAKE,
    LifecycleState.UNDER_ASSESSMENT,
    LifecycleState.TREATMENT_PENDING,
)


def _gate_for_state(
    state: LifecycleState, use_case: UseCase, db: Session
) -> GateResult | None:
    """The gate guarding the current resting state, or None if no gate is
    wired for it (the pending_authorisation ceiling, or a terminal/
    regression state). None always stops the advance loop, the same as a
    park."""
    if state == LifecycleState.REQUESTED:
        # The creation pass always carries a use case past REQUESTED
        # (design doc §4.1) — no condition to check, table row 1 is "—".
        return GateResult("advance", "use_case_created", "Use case created", "system")
    fn = _GATE_FNS.get(state)
    return fn(use_case, db) if fn else None


def advance_use_case(
    db: Session, use_case: UseCase, actor_user_id: uuid.UUID
) -> UseCase:
    """The auto-advance driver (design doc §4.3). MUST be called within the
    triggering write's transaction — get_tenant_db commits once at request
    end, so as long as this runs in-session before the handler returns, the
    trigger and every transition it produces commit atomically (STATE.md
    inv 4 equivalent for this sprint).

    Step 0: a current classification snapshot resolving PROHIBITED forces
    halted_prohibited from any non-terminal state — including HELD — before
    anything else runs (design doc §5.5). Then: advance one gate at a time
    until the first non-advance verdict, the pending_authorisation ceiling,
    or a state with no gate wired yet.
    """
    if use_case.state not in _TERMINAL_STATES:
        readiness = classification_readiness(use_case, db)
        if readiness.verdict == "halt":
            apply_transition(
                db,
                use_case,
                "halt",
                LifecycleState.HALTED_PROHIBITED,
                actor_user_id,
                readiness.reason,
            )
            return use_case

    while True:
        gate = _gate_for_state(use_case.state, use_case, db)
        if gate is None or gate.verdict != "advance":
            break
        event = "created" if use_case.state == LifecycleState.REQUESTED else "advance"
        apply_transition(
            db,
            use_case,
            event,
            _ADVANCE_TABLE[use_case.state],
            actor_user_id,
            gate.reason,
        )
    return use_case


# ---------------------------------------------------------------------------
# full_vector / re_evaluate (Sprint 5, WI-6).
# ---------------------------------------------------------------------------

# Position of each state in the canonical forward sequence — used to compare
# a re_evaluate target against the use case's current resting state. HELD
# and HALTED_PROHIBITED have no rank: they're never compared positionally,
# only entered/exited via their own dedicated events. AUTHORISED has a rank
# only so the lookup at the top of re_evaluate doesn't KeyError — it is
# never reached by the generic rank-comparison branch below, since
# _target_from_vector can never return AUTHORISED (not a gate-guarded
# position); re_evaluate special-cases AUTHORISED explicitly instead
# (Sprint 6b, design doc §6.2/§6.3).
_RANK: dict[LifecycleState, int] = {
    LifecycleState.REQUESTED: 0,
    LifecycleState.VENDOR_CHECK: 1,
    LifecycleState.PRODUCT_CHECK: 2,
    LifecycleState.INTAKE: 3,
    LifecycleState.UNDER_ASSESSMENT: 4,
    LifecycleState.TREATMENT_PENDING: 5,
    LifecycleState.PENDING_AUTHORISATION: 6,
    LifecycleState.AUTHORISED: 7,
}


def full_vector(
    use_case: UseCase, db: Session
) -> list[tuple[LifecycleState, GateResult]]:
    """Every positional gate, evaluated independently and in canonical order
    (design doc §7) — the source of truth for "where, why, whose court".
    Persisted state is a cursor; this is recomputed on every consequential
    read or write, never cached. Pure read: no mutation, no flush.

    authorisation_gate (Sprint 6b) is appended after the 5-state loop
    rather than folded into _GATE_FNS — deliberately. _GATE_FNS also drives
    advance_use_case's auto-advance walk; if authorisation_gate were keyed
    into it at PENDING_AUTHORISATION, a cycle-matching ATO would make that
    walk auto-transition into `authorised` with no human act (exactly the
    bug D10/inv 35 forbid — see docs/AUTORIZATION.md §6.2). Appending it
    here, outside _GATE_FNS, means full_vector reports on it for every
    consumer (status reads, re_evaluate, the rollup) while advance_use_case
    — which never reads past its 5-entry table — stays structurally unable
    to reach it.
    """
    vector: list[tuple[LifecycleState, GateResult]] = []
    for state in _VECTOR_STATES:
        vector.append((state, _GATE_FNS[state](use_case, db)))
    vector.append(
        (LifecycleState.PENDING_AUTHORISATION, authorisation_gate(use_case, db))
    )
    return vector


def _target_from_vector(
    vector: list[tuple[LifecycleState, GateResult]],
) -> tuple[LifecycleState, GateResult | None]:
    """The earliest unsatisfied gate's state (STATE_MACHINE.md §4.4) — first
    non-advance entry in the vector. All-advance -> the ceiling, no blocker."""
    for state, result in vector:
        if result.verdict != "advance":
            return state, result
    return LifecycleState.PENDING_AUTHORISATION, None


def re_evaluate(db: Session, use_case: UseCase, actor_user_id: uuid.UUID) -> UseCase:
    """The manual lever (design doc §8, POST .../lifecycle/re-evaluate) and
    the approval fan-out's per-use-case worker (WI-7). Recomputes the full
    vector and moves the use case to its correct resting gate — advancing,
    un-holding, or regressing an already-advanced use case to held when an
    upstream gate has since lapsed (e.g. an approval's valid_until passed
    with no event to catch it). A consequential write: persists, unlike the
    status read's recompute-and-show.
    """
    if use_case.state in _TERMINAL_STATES:
        # Already terminal — nothing advances, restores, or holds it further.
        return use_case

    readiness = classification_readiness(use_case, db)
    if readiness.verdict == "halt":
        apply_transition(
            db,
            use_case,
            "halt",
            LifecycleState.HALTED_PROHIBITED,
            actor_user_id,
            readiness.reason,
        )
        return use_case

    vector = full_vector(use_case, db)
    target_state, blocking = _target_from_vector(vector)

    if use_case.state == LifecycleState.HELD:
        reason = blocking.reason if blocking else "All upstream gates satisfied"
        apply_transition(db, use_case, "restore", target_state, actor_user_id, reason)
        return use_case

    if use_case.state == LifecycleState.AUTHORISED:
        # Sprint 6b (design doc §6.2/§6.3, D10, inv 35): special-cased
        # rather than falling through the generic rank comparison below —
        # AUTHORISED outranks every _RANK entry the vector can target, so
        # the generic branch would regress it to held unconditionally, even
        # when nothing has lapsed. blocking is None iff every vector entry,
        # INCLUDING authorisation_gate, currently advances (the ATO still
        # cycle-matches and assessment_approved() still holds) — a no-op in
        # that case. Otherwise: one direct regression to held, same shape as
        # the generic regress branch. Never restored back to AUTHORISED by
        # this function — only authorise_use_case can re-enter it.
        if blocking is None:
            return use_case
        apply_transition(
            db,
            use_case,
            "hold",
            LifecycleState.HELD,
            actor_user_id,
            blocking.reason,
            held_reason=blocking.reason,
        )
        return use_case

    current_rank = _RANK[use_case.state]
    target_rank = _RANK[target_state]

    if target_rank > current_rank:
        # Forward movement is always hop-by-hop, one audited transition per
        # gate crossed (design doc §1.1 "Auto-advance audit: per-hop") —
        # advance_use_case already does exactly this.
        advance_use_case(db, use_case, actor_user_id)
        return use_case

    if target_rank < current_rank:
        # An already-passed upstream gate now fails (e.g. expiry) — regress
        # to held in one direct transition, not hop-by-hop backward.
        reason = (
            blocking.reason if blocking else "An upstream gate is no longer satisfied"
        )
        apply_transition(
            db,
            use_case,
            "hold",
            LifecycleState.HELD,
            actor_user_id,
            reason,
            held_reason=reason,
        )
        return use_case

    return use_case


# ---------------------------------------------------------------------------
# Vendor / product approvals + fan-out (Sprint 5, WI-7).
# ---------------------------------------------------------------------------


def _set_tenant_context(db: Session, tenant_id: uuid.UUID) -> None:
    """SET LOCAL app.current_tenant for the session's current transaction.
    is_local=true (the 3rd set_config arg) means this lasts only until the
    next commit/rollback on this connection — get_tenant_db sets it once per
    request because it never commits mid-request. set_vendor_approval/
    set_product_approval below DO commit mid-request (deliberately, so the
    fan-out's independent sessions read a durable row), which silently wipes
    this setting for any further RLS-scoped query on the same `db` for the
    rest of that request (e.g. the router's subsequent fan_out_* call,
    enumerating affected use cases through the same session) — caught live
    against the real RLS-enabled dev DB; the no-RLS test DB can't surface
    this, since it never enforces app.current_tenant at all. Re-set it
    immediately after every mid-request commit in this module.
    """
    db.execute(
        text("SELECT set_config('app.current_tenant', :tid, true)"),
        {"tid": str(tenant_id)},
    )


def set_vendor_approval(
    db: Session,
    tenant_id: uuid.UUID,
    catalogue_vendor_id: uuid.UUID,
    *,
    approval_status: ApprovalStatus,
    valid_until: datetime | None,
    note: str | None,
    actor_user_id: uuid.UUID,
) -> VendorApproval:
    """Set/update the tenant's vendor clearance (design doc §6) — write +
    its own AuditEvent, atomic (one transaction, explicitly committed here
    so the fan-out's independent sessions read a durable, visible row —
    never the eventually-consistent diligence fan-out's uncommitted write).
    No delete: withdrawal is a status change, preserving history.
    """
    approval = db.scalar(
        select(VendorApproval).where(
            VendorApproval.tenant_id == tenant_id,
            VendorApproval.catalogue_vendor_id == catalogue_vendor_id,
        )
    )
    is_update = approval is not None
    if approval is None:
        approval = VendorApproval(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            catalogue_vendor_id=catalogue_vendor_id,
            diligence_blob={},
        )
        db.add(approval)

    approval.status = approval_status
    approval.valid_until = valid_until
    approval.note = note
    approval.decided_by_user_id = actor_user_id
    approval.decided_at = datetime.now(UTC)
    db.flush()

    db.add(
        AuditEvent(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            action="vendor_approval.updated" if is_update else "vendor_approval.set",
            entity_type="vendor_approval",
            entity_id=approval.id,
            detail={
                "status": approval_status.value,
                "valid_until": valid_until.isoformat() if valid_until else None,
            },
        )
    )
    db.commit()
    _set_tenant_context(db, tenant_id)
    return approval


def set_product_approval(
    db: Session,
    tenant_id: uuid.UUID,
    catalogue_product_id: uuid.UUID,
    *,
    approval_status: ApprovalStatus,
    valid_until: datetime | None,
    note: str | None,
    actor_user_id: uuid.UUID,
) -> ProductApproval:
    """Product clearance — same shape as set_vendor_approval."""
    approval = db.scalar(
        select(ProductApproval).where(
            ProductApproval.tenant_id == tenant_id,
            ProductApproval.catalogue_product_id == catalogue_product_id,
        )
    )
    is_update = approval is not None
    if approval is None:
        approval = ProductApproval(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            catalogue_product_id=catalogue_product_id,
            diligence_blob={},
        )
        db.add(approval)

    approval.status = approval_status
    approval.valid_until = valid_until
    approval.note = note
    approval.decided_by_user_id = actor_user_id
    approval.decided_at = datetime.now(UTC)
    db.flush()

    db.add(
        AuditEvent(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            action="product_approval.updated" if is_update else "product_approval.set",
            entity_type="product_approval",
            entity_id=approval.id,
            detail={
                "status": approval_status.value,
                "valid_until": valid_until.isoformat() if valid_until else None,
            },
        )
    )
    db.commit()
    _set_tenant_context(db, tenant_id)
    return approval


def _fan_out(
    tenant_id: uuid.UUID, use_case_ids: list[uuid.UUID], actor_user_id: uuid.UUID
) -> None:
    """Re-evaluate each affected use case in its own short-lived session —
    one idempotent transaction per use case (design doc §6, #7), the
    deferred-SQS-worker shape inline-looped for MVP. A crash mid-fan-out
    leaves some use cases un-advanced; caught on the next consequential
    read/operation or a re-run of this same fan-out (idempotent: re_evaluate
    is a no-op when the target already matches the current state).

    Each session opens on the RLS-bound app role (the same role get_tenant_db
    uses) and must set app.current_tenant itself — there is no FastAPI
    dependency chain here to do it.
    """
    for use_case_id in use_case_ids:
        session = SessionLocal()
        try:
            _set_tenant_context(session, tenant_id)
            use_case = session.get(UseCase, use_case_id)
            if use_case is not None:
                re_evaluate(session, use_case, actor_user_id)
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()


def fan_out_vendor_approval(
    db: Session,
    tenant_id: uuid.UUID,
    catalogue_vendor_id: uuid.UUID,
    actor_user_id: uuid.UUID,
) -> None:
    """Affected = use cases on systems linked to this vendor, RLS-bounded to
    the tenant (the `db` parameter here is the caller's RLS-scoped session,
    used only to enumerate the affected ids; each re-evaluation runs in its
    own session — see _fan_out)."""
    use_case_ids = list(
        db.scalars(
            select(UseCase.id)
            .join(System, System.id == UseCase.system_id)
            .where(
                System.tenant_id == tenant_id,
                System.catalogue_vendor_id == catalogue_vendor_id,
            )
        )
    )
    _fan_out(tenant_id, use_case_ids, actor_user_id)


def fan_out_product_approval(
    db: Session,
    tenant_id: uuid.UUID,
    catalogue_product_id: uuid.UUID,
    actor_user_id: uuid.UUID,
) -> None:
    use_case_ids = list(
        db.scalars(
            select(UseCase.id)
            .join(System, System.id == UseCase.system_id)
            .where(
                System.tenant_id == tenant_id,
                System.catalogue_product_id == catalogue_product_id,
            )
        )
    )
    _fan_out(tenant_id, use_case_ids, actor_user_id)


# ---------------------------------------------------------------------------
# System / portfolio rollup (Sprint 5, WI-8, REG-3).
# ---------------------------------------------------------------------------

# Highest-tier precedence, most severe first — mirrors classification.py's
# _TIER_ORDER. Computed in Python; never compare/sort the enum in SQL
# (STATE.md §2.8 footgun: REQUIRES_CONTEXT/UNCLASSIFIED don't have a
# meaningful lexical or declared-order position).
_TIER_PRECEDENCE: list[EUAIActTier] = [
    EUAIActTier.PROHIBITED,
    EUAIActTier.HIGH,
    EUAIActTier.LIMITED,
    EUAIActTier.MINIMAL,
]


def _tier_rank(tier: EUAIActTier) -> int:
    try:
        return _TIER_PRECEDENCE.index(tier)
    except ValueError:
        # REQUIRES_CONTEXT / UNCLASSIFIED — not yet a determined tier, ranks
        # below every real one.
        return len(_TIER_PRECEDENCE)


def _highest_tier(tiers: list[EUAIActTier]) -> EUAIActTier | None:
    if not tiers:
        return None
    return min(tiers, key=_tier_rank)


def _use_case_rollup_entry(use_case: UseCase, db: Session) -> UseCaseRollupEntry:
    vector = full_vector(use_case, db)
    blocking = next(
        (result for _, result in vector if result.verdict != "advance"), None
    )
    return UseCaseRollupEntry(
        use_case_id=use_case.id,
        title=use_case.title,
        state=use_case.state,
        eu_tier=use_case.eu_tier,
        blocking=(
            GateResultRead(
                state=use_case.state,
                verdict=blocking.verdict,
                reason_code=blocking.reason_code,
                reason=blocking.reason,
                responsible_party=blocking.responsible_party,
            )
            if blocking
            else None
        ),
    )


def system_rollup(
    db: Session, tenant_id: uuid.UUID, system: System
) -> SystemRollupRead:
    """Use cases + states + highest tier + outstanding obligations for one
    system (design doc §7). Pure read, recomputed live off the full vector —
    never a cached/stored rollup."""
    use_cases = list(
        db.scalars(
            select(UseCase).where(
                UseCase.system_id == system.id,
                UseCase.tenant_id == tenant_id,
            )
        )
    )
    return SystemRollupRead(
        system_id=system.id,
        system_name=system.name,
        use_case_count=len(use_cases),
        highest_tier=_highest_tier([uc.eu_tier for uc in use_cases]),
        use_cases=[_use_case_rollup_entry(uc, db) for uc in use_cases],
    )


def portfolio_rollup(db: Session, tenant_id: uuid.UUID) -> list[SystemRollupRead]:
    """Tenant-wide rollup — one SystemRollupRead per system with at least
    one use case (a system with none has nothing to roll up)."""
    systems = list(
        db.scalars(
            select(System)
            .join(UseCase, UseCase.system_id == System.id)
            .where(System.tenant_id == tenant_id)
            .distinct()
        )
    )
    return [system_rollup(db, tenant_id, s) for s in systems]


# ---------------------------------------------------------------------------
# Clearance queue (UI-F10-CLEARANCE, WI-1) — vendor-grouped read of the
# clearance act's blocking state, the single home GET /clearance-queue
# serves.
# ---------------------------------------------------------------------------


def _resolve_decider_names(
    db: Session, tenant_id: uuid.UUID, user_ids: set[uuid.UUID]
) -> dict[uuid.UUID, str]:
    """Batch INV-34 membership-join name resolution (D-25-guarded): a
    decider whose membership/user row is gone is simply absent from the
    result — never a fabricated placeholder (same posture as
    authorisation_service._resolve_actor_identity, batched here for a
    queue read)."""
    if not user_ids:
        return {}
    rows = db.execute(
        select(User.id, User.display_name)
        .join(Membership, Membership.user_id == User.id)
        .where(Membership.tenant_id == tenant_id, User.id.in_(user_ids))
    ).all()
    return {row.id: row.display_name for row in rows}


def clearance_queue(db: Session, tenant_id: uuid.UUID) -> ClearanceQueueRead:
    """Vendor-grouped read of every vendor/product currently awaiting
    clearance (design doc §4, DF-CLR-5): a vendor entry is shown if it has
    its own awaiting use case or hosts a product that does; a product entry
    is shown if its vendor is shown-for-being-in-queue (inert until
    vendor_cleared, INV-88) or it has its own awaiting use case. Both
    awaiting and affected counts derive from the same
    System.catalogue_vendor_id/catalogue_product_id join
    fan_out_vendor_approval/fan_out_product_approval use, so preview and
    actual fan-out cannot diverge (V-c)."""
    vendor_ids = set(
        db.scalars(
            select(System.catalogue_vendor_id)
            .where(
                System.tenant_id == tenant_id,
                System.catalogue_vendor_id.is_not(None),
            )
            .distinct()
        )
    )
    product_ids = set(
        db.scalars(
            select(System.catalogue_product_id)
            .where(
                System.tenant_id == tenant_id,
                System.catalogue_product_id.is_not(None),
            )
            .distinct()
        )
    )
    if not vendor_ids and not product_ids:
        return ClearanceQueueRead(vendors=[])

    products = (
        list(db.scalars(select(CatalogueProduct).where(CatalogueProduct.id.in_(product_ids))))
        if product_ids
        else []
    )
    all_vendor_ids = vendor_ids | {p.vendor_id for p in products}
    vendors = (
        list(db.scalars(select(CatalogueVendor).where(CatalogueVendor.id.in_(all_vendor_ids))))
        if all_vendor_ids
        else []
    )
    vendors_by_id = {v.id: v for v in vendors}
    products_by_vendor: dict[uuid.UUID, list[CatalogueProduct]] = {}
    for p in products:
        products_by_vendor.setdefault(p.vendor_id, []).append(p)

    vendor_approvals = {
        a.catalogue_vendor_id: a
        for a in db.scalars(
            select(VendorApproval).where(
                VendorApproval.tenant_id == tenant_id,
                VendorApproval.catalogue_vendor_id.in_(all_vendor_ids),
            )
        )
    } if all_vendor_ids else {}
    product_approvals = {
        a.catalogue_product_id: a
        for a in db.scalars(
            select(ProductApproval).where(
                ProductApproval.tenant_id == tenant_id,
                ProductApproval.catalogue_product_id.in_(product_ids),
            )
        )
    } if product_ids else {}

    decider_ids = {a.decided_by_user_id for a in vendor_approvals.values() if a.decided_by_user_id}
    decider_ids |= {
        a.decided_by_user_id for a in product_approvals.values() if a.decided_by_user_id
    }
    names_by_user_id = _resolve_decider_names(db, tenant_id, decider_ids)

    def _counts(
        catalogue_id_column, ids: set[uuid.UUID], awaiting_state: LifecycleState
    ) -> tuple[dict[uuid.UUID, int], dict[uuid.UUID, int], dict[uuid.UUID, int]]:
        """(awaiting, affected_use_cases, affected_systems) keyed by
        catalogue id — affected_* is the full fan-out set (any state), not
        merely those parked at the gate."""
        if not ids:
            return {}, {}, {}
        awaiting = dict(
            db.execute(
                select(catalogue_id_column, func.count(UseCase.id))
                .join(UseCase, UseCase.system_id == System.id)
                .where(
                    System.tenant_id == tenant_id,
                    catalogue_id_column.in_(ids),
                    UseCase.state == awaiting_state,
                )
                .group_by(catalogue_id_column)
            ).all()
        )
        affected_rows = db.execute(
            select(
                catalogue_id_column,
                func.count(func.distinct(UseCase.id)),
                func.count(func.distinct(System.id)),
            )
            .join(UseCase, UseCase.system_id == System.id)
            .where(System.tenant_id == tenant_id, catalogue_id_column.in_(ids))
            .group_by(catalogue_id_column)
        ).all()
        affected_use_cases = {row[0]: row[1] for row in affected_rows}
        affected_systems = {row[0]: row[2] for row in affected_rows}
        return awaiting, affected_use_cases, affected_systems

    vendor_awaiting, vendor_affected_uc, vendor_affected_sys = _counts(
        System.catalogue_vendor_id, vendor_ids, LifecycleState.VENDOR_CHECK
    )
    product_awaiting, product_affected_uc, product_affected_sys = _counts(
        System.catalogue_product_id, product_ids, LifecycleState.PRODUCT_CHECK
    )

    in_queue_vendor_ids = {vid for vid, cnt in vendor_awaiting.items() if cnt > 0}
    in_queue_product_ids = {pid for pid, cnt in product_awaiting.items() if cnt > 0}
    vendor_ids_to_show = in_queue_vendor_ids | {
        product.vendor_id for product in products if product.id in in_queue_product_ids
    }

    entries: list[VendorClearanceEntry] = []
    for vendor_id in vendor_ids_to_show:
        vendor = vendors_by_id.get(vendor_id)
        if vendor is None:
            continue
        v_approval = vendor_approvals.get(vendor_id)
        vendor_status = v_approval.status if v_approval else ApprovalStatus.NOT_STARTED
        vendor_cleared = vendor_status == ApprovalStatus.APPROVED

        product_entries: list[ProductClearanceEntry] = []
        for product in products_by_vendor.get(vendor_id, []):
            if not (vendor_id in in_queue_vendor_ids or product.id in in_queue_product_ids):
                continue
            p_approval = product_approvals.get(product.id)
            p_status = p_approval.status if p_approval else ApprovalStatus.NOT_STARTED
            product_entries.append(
                ProductClearanceEntry(
                    catalogue_product_id=product.id,
                    product_name=product.name,
                    status=p_status,
                    valid_until=p_approval.valid_until if p_approval else None,
                    decided_by_name=(
                        names_by_user_id.get(p_approval.decided_by_user_id)
                        if p_approval and p_approval.decided_by_user_id
                        else None
                    ),
                    decided_at=p_approval.decided_at if p_approval else None,
                    note=p_approval.note if p_approval else None,
                    vendor_cleared=vendor_cleared,
                    awaiting_use_case_count=product_awaiting.get(product.id, 0),
                    affected_use_case_count=product_affected_uc.get(product.id, 0),
                    affected_system_count=product_affected_sys.get(product.id, 0),
                )
            )

        entries.append(
            VendorClearanceEntry(
                catalogue_vendor_id=vendor.id,
                vendor_name=vendor.name,
                status=vendor_status,
                valid_until=v_approval.valid_until if v_approval else None,
                decided_by_name=(
                    names_by_user_id.get(v_approval.decided_by_user_id)
                    if v_approval and v_approval.decided_by_user_id
                    else None
                ),
                decided_at=v_approval.decided_at if v_approval else None,
                note=v_approval.note if v_approval else None,
                awaiting_use_case_count=vendor_awaiting.get(vendor_id, 0),
                affected_use_case_count=vendor_affected_uc.get(vendor_id, 0),
                affected_system_count=vendor_affected_sys.get(vendor_id, 0),
                products=product_entries,
            )
        )

    return ClearanceQueueRead(vendors=entries)
