"""
Classification Gate (gate 2) — context-based EU AI Act classification.

Four public functions:

  get_latest_tree_version(db)
      Returns the highest-loaded version string. Pure read.

  get_context_questions(use_case, supplied_answers, db, tree_version)
      Returns the residual question set: all tree questions minus those
      already answered. Pure read; no writes.

  resolve_context_classification(answers, tree_version, db)
      Pure resolver. Loads the pinned decision tree, applies the precedence
      ladder, and returns an Outcome. NEVER writes. Deterministic: same
      (answers, tree_version) always yields the same Outcome.

  compute_and_record_classification(use_case, answers, tree_version, db,
                                     actor_user_id, override_tier, justification)
      Writes exactly one Classification snapshot (status=PENDING_REVIEW) when
      the outcome is RESOLVED or PROHIBITED_HALT. Stages one AuditEvent in the
      same transaction. Does NOT stamp use_case.eu_tier — that is reserved for
      Reviewer sign-off.

  sign_off_classification(use_case, db, reviewer_user_id)
      Reviewer approves the current PENDING_REVIEW snapshot: flips status to
      APPROVED, stamps use_case.eu_tier, and stages classification.signed_off
      AuditEvent. All in one transaction.

Fail-closed rules (enforced everywhere):
  - UNRESOLVED → no snapshot, eu_tier stays UNCLASSIFIED.
  - MINIMAL is an affirmative determination only — never a fallback.
  - classification.tier is never UNCLASSIFIED or REQUIRES_CONTEXT.
  - PROHIBITED → PROHIBITED_HALT outcome (not an error, but distinct).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Literal

from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models.assessment import Classification
from app.models.base import (
    ClassificationStatus,
    EUAIActTier,
    ProvenanceConfidence,
)
from app.models.decision_tree import (
    DecisionTree,
    DecisionTreeOption,
    DecisionTreeQuestion,
)
from app.models.domain import UseCase
from app.models.lifecycle import AuditEvent
from app.services.lifecycle_service import advance_use_case

# ── Precedence ladder ───────────────────────────────────────────────────────

_TIER_PRECEDENCE: list[EUAIActTier] = [
    EUAIActTier.PROHIBITED,
    EUAIActTier.HIGH,
    EUAIActTier.LIMITED,
    EUAIActTier.MINIMAL,
]

# Tiers that are valid to store in classification.tier
_STORABLE_TIERS: frozenset[EUAIActTier] = frozenset(_TIER_PRECEDENCE)


def _tier_rank(tier: EUAIActTier) -> int:
    try:
        return _TIER_PRECEDENCE.index(tier)
    except ValueError:
        return len(_TIER_PRECEDENCE)  # sentinel / unknown → lowest priority


def _higher_tier(a: EUAIActTier | None, b: EUAIActTier | None) -> EUAIActTier | None:
    if a is None:
        return b
    if b is None:
        return a
    return a if _tier_rank(a) <= _tier_rank(b) else b


# ── Data structures ─────────────────────────────────────────────────────────

@dataclass
class AnswerIn:
    question_code: str
    option_code: str
    provenance: ProvenanceConfidence = ProvenanceConfidence.USER_CONFIRMED


@dataclass
class OptionRead:
    code: str
    label: str
    asserts_rung: EUAIActTier | None
    asserts_subcategory_code: str | None


@dataclass
class QuestionRead:
    code: str
    text: str
    legal_ref: str | None
    sort_order: int
    options: list[OptionRead]


@dataclass
class QuestionSet:
    tree_version: str
    questions: list[QuestionRead]


OutcomeKind = Literal["UNRESOLVED", "RESOLVED", "PROHIBITED_HALT"]


@dataclass
class ContextOutcome:
    kind: OutcomeKind
    tier: EUAIActTier | None           # None when UNRESOLVED
    subcategory_code: str | None       # set when a single subcategory is identified
    rationale: str
    missing: list[str] = field(default_factory=list)  # question_codes still needed


# ── Pure reads ──────────────────────────────────────────────────────────────

def get_latest_tree_version(db: Session) -> str | None:
    """Return the most recently loaded tree version, or None if none exists."""
    return db.scalar(
        select(DecisionTree.version).order_by(DecisionTree.created_at.desc()).limit(1)
    )


def _load_tree(tree_version: str, db: Session) -> DecisionTree:
    tree = db.scalar(
        select(DecisionTree)
        .where(DecisionTree.version == tree_version)
    )
    if tree is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Decision tree version '{tree_version}' not found. "
                   "Seed the tree before submitting answers.",
        )
    return tree


def get_context_questions(
    supplied_answers: list[AnswerIn],
    db: Session,
    tree_version: str | None = None,
) -> QuestionSet:
    """Return the residual question set: all tree questions minus supplied answers.

    If tree_version is None, uses the latest loaded version. Pure read.
    WI-9 extension point: catalogue prefill subtracts additional answered
    questions before returning the residual.
    """
    if tree_version is None:
        tree_version = get_latest_tree_version(db)
        if tree_version is None:
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="No decision tree has been loaded. Run the seed script.",
            )

    tree = _load_tree(tree_version, db)

    answered_codes: set[str] = {a.question_code for a in supplied_answers}

    residual: list[QuestionRead] = []
    for q in tree.questions:
        if q.question_code in answered_codes:
            continue
        residual.append(QuestionRead(
            code=q.question_code,
            text=q.text,
            legal_ref=q.legal_ref,
            sort_order=q.sort_order,
            options=[
                OptionRead(
                    code=o.option_code,
                    label=o.label,
                    asserts_rung=o.asserts_rung,
                    asserts_subcategory_code=o.asserts_subcategory_code,
                )
                for o in q.options
            ],
        ))

    return QuestionSet(tree_version=tree_version, questions=residual)


def resolve_context_classification(
    answers: list[AnswerIn],
    tree_version: str,
    db: Session,
) -> ContextOutcome:
    """Deterministic, pure resolver.

    Loads the pinned tree, maps answers to options, collects assertions, and
    applies the precedence ladder. Never writes to the DB.

    Fail-closed rules:
      - Unanswered questions → UNRESOLVED, no tier, missing = unanswered codes.
      - PROHIBITED asserted → PROHIBITED_HALT immediately (short-circuit).
      - MINIMAL only when ALL questions answered and no rung asserted.
      - All answered, no rung asserted, MINIMAL not reachable → RuntimeError
        (indicates a seed/logic defect).
    """
    tree = _load_tree(tree_version, db)

    # Index supplied answers: question_code → option_code
    answer_map: dict[str, str] = {a.question_code: a.option_code for a in answers}

    # Index tree: question_code → DecisionTreeQuestion
    question_map: dict[str, DecisionTreeQuestion] = {
        q.question_code: q for q in tree.questions
    }
    all_question_codes: set[str] = set(question_map)

    # Validate: supplied answer codes must all exist in the tree.
    unknown = set(answer_map) - all_question_codes
    if unknown:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Answers reference unknown question codes: {sorted(unknown)}",
        )

    # Resolve each answered question's option.
    # option_map: question_code → DecisionTreeOption for the chosen option
    option_lookup: dict[str, dict[str, DecisionTreeOption]] = {}
    for q in tree.questions:
        option_lookup[q.question_code] = {o.option_code: o for o in q.options}

    highest_rung: EUAIActTier | None = None
    resolved_subcategory_code: str | None = None
    assertion_rationale_parts: list[str] = []

    for q_code, o_code in answer_map.items():
        opts = option_lookup.get(q_code, {})
        opt = opts.get(o_code)
        if opt is None:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Option '{o_code}' not found for question '{q_code}'",
            )

        if opt.asserts_rung is not None:
            prev = highest_rung
            highest_rung = _higher_tier(highest_rung, opt.asserts_rung)
            if highest_rung != prev:
                sub = (
                    f" ({opt.asserts_subcategory_code})"
                    if opt.asserts_subcategory_code else ""
                )
                assertion_rationale_parts.append(
                    f"{q_code}/{o_code} → {opt.asserts_rung.value}{sub}"
                )
                if opt.asserts_subcategory_code:
                    resolved_subcategory_code = opt.asserts_subcategory_code

            # Short-circuit: PROHIBITED is the maximum; no further questions can
            # override it. Return immediately with PROHIBITED_HALT.
            if highest_rung == EUAIActTier.PROHIBITED:
                rationale = (
                    f"PROHIBITED practice identified. "
                    f"Assertions: {'; '.join(assertion_rationale_parts)}."
                )
                return ContextOutcome(
                    kind="PROHIBITED_HALT",
                    tier=EUAIActTier.PROHIBITED,
                    subcategory_code=resolved_subcategory_code,
                    rationale=rationale,
                    missing=[],
                )

    # Determine missing questions.
    missing_codes: list[str] = sorted(all_question_codes - set(answer_map))

    if missing_codes:
        return ContextOutcome(
            kind="UNRESOLVED",
            tier=None,
            subcategory_code=None,
            rationale=(
                f"{len(missing_codes)} question(s) still required to complete "
                f"the EU AI Act classification."
            ),
            missing=missing_codes,
        )

    # All questions answered, no PROHIBITED. Resolve final tier.
    if highest_rung is not None:
        rationale = (
            f"Resolved via decision tree v{tree_version}. "
            f"Highest asserted rung: {highest_rung.value}. "
            f"Assertions: {'; '.join(assertion_rationale_parts)}."
        )
        return ContextOutcome(
            kind="RESOLVED",
            tier=highest_rung,
            subcategory_code=resolved_subcategory_code,
            rationale=rationale,
            missing=[],
        )

    # All answered, no rung asserted → MINIMAL (affirmative determination).
    # If the tree has no question that can assert MINIMAL explicitly, this is
    # the correct terminal: all higher-rung practices were negated.
    if not tree.questions:
        raise RuntimeError(
            f"Decision tree v{tree_version} has no questions — seed defect."
        )

    return ContextOutcome(
        kind="RESOLVED",
        tier=EUAIActTier.MINIMAL,
        subcategory_code=None,
        rationale=(
            f"All {len(tree.questions)} classification questions answered; "
            f"no prohibited, high-risk, or limited-risk practices identified. "
            f"Tier: MINIMAL (affirmative determination)."
        ),
        missing=[],
    )


# ── Compute-and-record (WI-6) ───────────────────────────────────────────────

def compute_and_record_classification(
    use_case: UseCase,
    answers: list[AnswerIn],
    tree_version: str,
    db: Session,
    actor_user_id: uuid.UUID,
    override_tier: EUAIActTier | None = None,
    justification: str | None = None,
) -> tuple[ContextOutcome, Classification | None]:
    """Resolve and, if resolved, persist a PENDING_REVIEW classification snapshot.

    Fail-closed: UNRESOLVED returns immediately with no writes.
    Override: if override_tier is set and differs from outcome.tier, the caller
    must already have been gated to system_owner (enforced in the route layer).

    Returns (outcome, snapshot_or_None).
    The caller (get_tenant_db session) owns the transaction and commits.
    use_case.eu_tier is NOT updated here — that happens only at sign-off (WI-7).
    """
    outcome = resolve_context_classification(answers, tree_version, db)

    if outcome.kind == "UNRESOLVED":
        return outcome, None

    # Determine the stored tier (override or computed).
    overridden = False
    proposed_tier: EUAIActTier | None = None
    stored_tier: EUAIActTier = outcome.tier  # type: ignore[assignment]

    if override_tier is not None and override_tier != outcome.tier:
        if override_tier not in _STORABLE_TIERS:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Cannot override to tier '{override_tier.value}':"
                    " not a valid tier."
                ),
            )
        overridden = True
        proposed_tier = outcome.tier
        stored_tier = override_tier

    if stored_tier not in _STORABLE_TIERS:
        # Defensive guard: should never fire, but if it does, fail loud.
        raise RuntimeError(
            f"Invariant violation: attempted to write '{stored_tier.value}' to "
            f"classification.tier — only real tiers are permitted."
        )

    # Build the answers_blob (self-contained, tree-version pinned, §11).
    provenance_map: dict[str, ProvenanceConfidence] = {
        a.question_code: a.provenance for a in answers
    }
    # Eagerly load question/option details for the blob.
    tree = _load_tree(tree_version, db)
    question_index: dict[str, DecisionTreeQuestion] = {
        q.question_code: q for q in tree.questions
    }
    option_index: dict[str, dict[str, DecisionTreeOption]] = {
        q.question_code: {o.option_code: o for o in q.options}
        for q in tree.questions
    }

    answer_blobs: list[dict] = []
    for a in answers:
        q = question_index.get(a.question_code)
        opt = option_index.get(a.question_code, {}).get(a.option_code)
        if opt and opt.asserts_rung:
            asserts_str = f"rung:{opt.asserts_rung.value}"
        elif opt and opt.asserts_subcategory_code:
            asserts_str = f"subcategory:{opt.asserts_subcategory_code}"
        else:
            asserts_str = "none"
        answer_blobs.append({
            "question_code": a.question_code,
            "question_text": q.text if q else "",
            "option_code": a.option_code,
            "option_label": opt.label if opt else "",
            "legal_ref": q.legal_ref if q else None,
            "asserts": asserts_str,
            "provenance": (
                provenance_map.get(a.question_code)
                or ProvenanceConfidence.USER_CONFIRMED
            ).value,
        })

    answers_blob: dict = {
        "tree_version": tree_version,
        "resolution": "FROM_SCRATCH",
        "outcome": outcome.kind,
        "resolved_rung": stored_tier.value,
        "resolved_subcategory_code": outcome.subcategory_code,
        "answers": answer_blobs,
    }

    # Rationale — append override justification if applicable.
    rationale = outcome.rationale
    if overridden and justification:
        rationale = f"{rationale}\n\nOverride justification: {justification}"
    elif overridden:
        rationale = f"{rationale}\n\nTier overridden to {stored_tier.value}."

    # Flip prior is_current snapshot.
    db.execute(
        update(Classification)
        .where(
            Classification.use_case_id == use_case.id,
            Classification.is_current.is_(True),
        )
        .values(is_current=False)
    )

    prior_version = db.scalar(
        select(Classification.version)
        .where(Classification.use_case_id == use_case.id)
        .order_by(Classification.version.desc())
        .limit(1)
    )
    new_version = (prior_version or 0) + 1

    snapshot = Classification(
        id=uuid.uuid4(),
        tenant_id=use_case.tenant_id,
        use_case_id=use_case.id,
        tier=stored_tier,
        rationale=rationale,
        answers_blob=answers_blob,
        version=new_version,
        is_current=True,
        overridden=overridden,
        proposed_tier=proposed_tier,
        basis_subcategory_code=outcome.subcategory_code,
        basis_legal_ref=None,    # populated via WI-9 subcategory lookup
        status=ClassificationStatus.PENDING_REVIEW,
    )
    db.add(snapshot)
    db.flush()

    audit_action = (
        "classification.overridden" if overridden else "classification.created"
    )
    detail: dict = {
        "tier": stored_tier.value,
        "outcome_kind": outcome.kind,
        "tree_version": tree_version,
        "version": new_version,
        "basis_subcategory_code": outcome.subcategory_code,
    }
    if overridden:
        detail["proposed_tier"] = proposed_tier.value if proposed_tier else None
        detail["justification"] = justification

    db.add(AuditEvent(
        id=uuid.uuid4(),
        tenant_id=use_case.tenant_id,
        actor_user_id=actor_user_id,
        action=audit_action,
        entity_type="classification",
        entity_id=snapshot.id,
        detail=detail,
    ))

    # NOTE: use_case.eu_tier is NOT stamped here. That happens at sign-off (WI-7).

    # Sprint 5 WI-5: drives the prohibited halt off this snapshot becoming
    # current — load-bearing here specifically, since the context path never
    # stamps eu_tier=PROHIBITED; advance_use_case's step 0 reads the
    # snapshot's tier, not eu_tier, so a PROHIBITED_HALT outcome halts the
    # use case atomically with this write even though eu_tier is untouched
    # (design doc §5.5, the v1 hole #1 this rule exists to close).
    advance_use_case(db, use_case, actor_user_id)

    return outcome, snapshot


# ── Reviewer sign-off (WI-7) ────────────────────────────────────────────────

def sign_off_classification(
    use_case: UseCase,
    db: Session,
    reviewer_user_id: uuid.UUID,
) -> Classification:
    """Reviewer approves the current PENDING_REVIEW snapshot.

    Single transaction (the caller's get_tenant_db session):
      1. Load current PENDING_REVIEW snapshot.
      2. Flip status → APPROVED.
      3. Stamp use_case.eu_tier with the approved tier.
      4. Stage AuditEvent(classification.signed_off).

    Raises 404 if there is no pending snapshot to approve.
    Raises 409 if the current snapshot is already APPROVED.
    """
    snapshot = db.scalar(
        select(Classification)
        .where(
            Classification.use_case_id == use_case.id,
            Classification.is_current.is_(True),
        )
    )

    if snapshot is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail="No current classification snapshot found for this use case.",
        )

    if snapshot.status == ClassificationStatus.APPROVED:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="Classification is already approved.",
        )

    if snapshot.status != ClassificationStatus.PENDING_REVIEW:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail=(
                "Cannot sign off a classification with status"
                f" '{snapshot.status.value}'."
            ),
        )

    snapshot.status = ClassificationStatus.APPROVED
    db.add(snapshot)

    # Stamp the use case's denormalised tier — the authoritative ratification.
    use_case.eu_tier = snapshot.tier
    db.add(use_case)

    db.flush()

    db.add(AuditEvent(
        id=uuid.uuid4(),
        tenant_id=use_case.tenant_id,
        actor_user_id=reviewer_user_id,
        action="classification.signed_off",
        entity_type="classification",
        entity_id=snapshot.id,
        detail={
            "tier": snapshot.tier.value,
            "version": snapshot.version,
            "tree_version": (
                snapshot.answers_blob.get("tree_version")
                if snapshot.answers_blob else None
            ),
        },
    ))

    # Sprint 5 WI-5: eu_tier just became ratified — drives the intake gate.
    advance_use_case(db, use_case, reviewer_user_id)

    return snapshot
