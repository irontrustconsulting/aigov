"""
Tests for the Classification Gate (gate 2) sprint.

Acceptance criteria covered:
  § Resolver unit tests (pure, no DB):
    - Precedence: PROHIBITED > HIGH > LIMITED > MINIMAL for each adjacent pair,
      irrespective of answer order.
    - Determinism: same (answers, tree) → same outcome repeatedly.
    - Fail-closed: incomplete answers → UNRESOLVED, never MINIMAL.
    - PROHIBITED answer → PROHIBITED_HALT.
    - Subcategory code populated when option asserts it; None otherwise.
    - MINIMAL affirmative: all answered, no rung asserted → MINIMAL.

  § Seed loader:
    - Idempotent on unchanged content.
    - Fails loud on content mutation under same version.

  § Compute integration (WI-6):
    - Resolvable answers → PENDING_REVIEW snapshot; eu_tier still UNCLASSIFIED.
    - UNRESOLVED → no snapshot written.
    - classification.tier is never UNCLASSIFIED.
    - Override (system_owner) → overridden=True, proposed_tier recorded.
    - Override attempted by contributor-only → 403.

  § Sign-off integration (WI-7):
    - Reviewer sign-off → APPROVED, eu_tier stamped.
    - PROHIBITED classification signed off → eu_tier=PROHIBITED.
    - Non-reviewer → 403.

  § Auth sweep:
    - GET /context and POST /context/preview → 200 for all five roles.
    - POST /context → 403 for reviewer, authoriser, auditor.
    - POST /sign-off → 403 for system_owner, contributor, auditor, authoriser.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any
from unittest.mock import patch

import pytest
from fastapi import status as http_status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.context import TenantContext, get_tenant_context, get_tenant_db
from app.main import app
from app.models.assessment import Classification
from app.models.base import (
    ClassificationStatus,
    EUAIActTier,
    ProvenanceConfidence,
    UserRole,
)
from app.models.decision_tree import DecisionTree, DecisionTreeOption, DecisionTreeQuestion
from app.models.domain import System, UseCase
from app.models.governance import GovernanceRole, GovernanceRoleAssignment
from app.models.identity import Membership, Tenant, User
from app.services.context_classification import (
    AnswerIn,
    ContextOutcome,
    compute_and_record_classification,
    get_context_questions,
    resolve_context_classification,
    sign_off_classification,
)


# ─────────────────────────────────────────────────────────────────────────────
# Reference data / tree fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def minimal_tree(db_session: Session) -> DecisionTree:
    """A minimal three-question tree: one PROHIBITED, one HIGH, one LIMITED."""
    tree = DecisionTree(
        id=uuid.uuid4(),
        version="test-1.0",
        name="Test Tree",
        content_hash="deadbeef" * 8,  # 64-char placeholder
    )
    db_session.add(tree)
    db_session.flush()

    # Q1 — probes PROHIBITED
    q_prohibited = DecisionTreeQuestion(
        id=uuid.uuid4(),
        tree_id=tree.id,
        question_code="Q_PROHIBITED",
        text="Is this a prohibited practice?",
        probes_rung=EUAIActTier.PROHIBITED,
        legal_ref="Art. 5",
        sort_order=10,
    )
    db_session.add(q_prohibited)
    db_session.flush()
    db_session.add_all([
        DecisionTreeOption(
            id=uuid.uuid4(), question_id=q_prohibited.id,
            option_code="YES", label="Yes",
            asserts_rung=EUAIActTier.PROHIBITED,
            asserts_subcategory_code="ART5_TEST",
        ),
        DecisionTreeOption(
            id=uuid.uuid4(), question_id=q_prohibited.id,
            option_code="NO", label="No",
            asserts_rung=None, asserts_subcategory_code=None,
        ),
    ])

    # Q2 — probes HIGH
    q_high = DecisionTreeQuestion(
        id=uuid.uuid4(),
        tree_id=tree.id,
        question_code="Q_HIGH",
        text="Is this a high-risk use?",
        probes_rung=EUAIActTier.HIGH,
        legal_ref="Annex III",
        sort_order=20,
    )
    db_session.add(q_high)
    db_session.flush()
    db_session.add_all([
        DecisionTreeOption(
            id=uuid.uuid4(), question_id=q_high.id,
            option_code="YES", label="Yes",
            asserts_rung=EUAIActTier.HIGH,
            asserts_subcategory_code="ANNEX3_TEST",
        ),
        DecisionTreeOption(
            id=uuid.uuid4(), question_id=q_high.id,
            option_code="NO", label="No",
            asserts_rung=None, asserts_subcategory_code=None,
        ),
    ])

    # Q3 — probes LIMITED
    q_limited = DecisionTreeQuestion(
        id=uuid.uuid4(),
        tree_id=tree.id,
        question_code="Q_LIMITED",
        text="Does it interact with users in a chatbot-like way?",
        probes_rung=EUAIActTier.LIMITED,
        legal_ref="Art. 50",
        sort_order=30,
    )
    db_session.add(q_limited)
    db_session.flush()
    db_session.add_all([
        DecisionTreeOption(
            id=uuid.uuid4(), question_id=q_limited.id,
            option_code="YES", label="Yes",
            asserts_rung=EUAIActTier.LIMITED,
            asserts_subcategory_code="ART50_TEST",
        ),
        DecisionTreeOption(
            id=uuid.uuid4(), question_id=q_limited.id,
            option_code="NO", label="No",
            asserts_rung=None, asserts_subcategory_code=None,
        ),
    ])

    db_session.flush()
    return tree


# ─────────────────────────────────────────────────────────────────────────────
# Tenant + member fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def tenant(db_session: Session) -> Tenant:
    t = Tenant(id=uuid.uuid4(), name="Gate Corp", slug="gate-corp")
    db_session.add(t)
    db_session.flush()
    return t


def _make_member(db: Session, tenant: Tenant) -> tuple[User, Membership]:
    u = User(id=uuid.uuid4(), cognito_sub=f"sub-{uuid.uuid4()}", email=f"{uuid.uuid4()}@test.local")
    m = Membership(id=uuid.uuid4(), user_id=u.id, tenant_id=tenant.id, role=UserRole.MEMBER)
    db.add_all([u, m])
    db.flush()
    return u, m


@pytest.fixture
def member(db_session: Session, tenant: Tenant) -> tuple[User, Membership]:
    return _make_member(db_session, tenant)


@pytest.fixture
def gov_roles(db_session: Session) -> dict[str, GovernanceRole]:
    roles = {}
    for key, name, line in [
        ("system_owner", "System Owner", 1),
        ("contributor", "Contributor", 1),
        ("reviewer", "Reviewer", 2),
        ("authoriser", "Authoriser", 2),
        ("auditor", "Auditor", 3),
    ]:
        r = GovernanceRole(id=uuid.uuid4(), key=key, name=name, line_of_defence=line)
        db_session.add(r)
        roles[key] = r
    db_session.flush()
    return roles


def _grant(db: Session, tenant: Tenant, m: Membership, role: GovernanceRole) -> None:
    db.add(GovernanceRoleAssignment(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        membership_id=m.id,
        governance_role_id=role.id,
    ))
    db.flush()


def _make_system(db: Session, tenant: Tenant) -> System:
    s = System(id=uuid.uuid4(), tenant_id=tenant.id, name="TestSys", metadata_blob={})
    db.add(s)
    db.flush()
    return s


def _make_use_case(db: Session, tenant: Tenant, system: System) -> UseCase:
    uc = UseCase(id=uuid.uuid4(), tenant_id=tenant.id, system_id=system.id, title="Gate UC", context_blob={})
    db.add(uc)
    db.flush()
    return uc


def _make_ctx(user: User, membership: Membership, tenant: Tenant) -> TenantContext:
    return TenantContext(
        user_id=user.id, membership_id=membership.id,
        tenant_id=tenant.id, role=membership.role.value,
    )


def _ctx_override(ctx: TenantContext):
    def _dep():
        return ctx
    return _dep


def _db_override(session: Session):
    def _dep():
        yield session
        session.flush()
    return _dep


# ─────────────────────────────────────────────────────────────────────────────
# 1. Resolver unit tests (pure, use DB only to load tree)
# ─────────────────────────────────────────────────────────────────────────────

class TestResolver:
    def _all_no(self, tree: DecisionTree) -> list[AnswerIn]:
        return [
            AnswerIn(question_code="Q_PROHIBITED", option_code="NO"),
            AnswerIn(question_code="Q_HIGH", option_code="NO"),
            AnswerIn(question_code="Q_LIMITED", option_code="NO"),
        ]

    def test_prohibited_yields_prohibited_halt(self, db_session, minimal_tree):
        answers = [
            AnswerIn(question_code="Q_PROHIBITED", option_code="YES"),
            AnswerIn(question_code="Q_HIGH", option_code="NO"),
            AnswerIn(question_code="Q_LIMITED", option_code="NO"),
        ]
        outcome = resolve_context_classification(answers, minimal_tree.version, db_session)
        assert outcome.kind == "PROHIBITED_HALT"
        assert outcome.tier == EUAIActTier.PROHIBITED
        assert outcome.subcategory_code == "ART5_TEST"
        assert outcome.missing == []

    def test_high_yields_resolved_high(self, db_session, minimal_tree):
        answers = [
            AnswerIn(question_code="Q_PROHIBITED", option_code="NO"),
            AnswerIn(question_code="Q_HIGH", option_code="YES"),
            AnswerIn(question_code="Q_LIMITED", option_code="NO"),
        ]
        outcome = resolve_context_classification(answers, minimal_tree.version, db_session)
        assert outcome.kind == "RESOLVED"
        assert outcome.tier == EUAIActTier.HIGH

    def test_limited_yields_resolved_limited(self, db_session, minimal_tree):
        answers = [
            AnswerIn(question_code="Q_PROHIBITED", option_code="NO"),
            AnswerIn(question_code="Q_HIGH", option_code="NO"),
            AnswerIn(question_code="Q_LIMITED", option_code="YES"),
        ]
        outcome = resolve_context_classification(answers, minimal_tree.version, db_session)
        assert outcome.kind == "RESOLVED"
        assert outcome.tier == EUAIActTier.LIMITED

    def test_all_no_yields_minimal(self, db_session, minimal_tree):
        """All questions answered with 'no' assertions → MINIMAL."""
        outcome = resolve_context_classification(
            self._all_no(minimal_tree), minimal_tree.version, db_session
        )
        assert outcome.kind == "RESOLVED"
        assert outcome.tier == EUAIActTier.MINIMAL
        assert outcome.missing == []

    def test_precedence_prohibited_over_high(self, db_session, minimal_tree):
        """PROHIBITED beats HIGH regardless of answer order."""
        answers_ph = [
            AnswerIn(question_code="Q_PROHIBITED", option_code="YES"),
            AnswerIn(question_code="Q_HIGH", option_code="YES"),
            AnswerIn(question_code="Q_LIMITED", option_code="NO"),
        ]
        answers_hp = [
            AnswerIn(question_code="Q_HIGH", option_code="YES"),
            AnswerIn(question_code="Q_PROHIBITED", option_code="YES"),
            AnswerIn(question_code="Q_LIMITED", option_code="NO"),
        ]
        for answers in [answers_ph, answers_hp]:
            outcome = resolve_context_classification(answers, minimal_tree.version, db_session)
            assert outcome.kind == "PROHIBITED_HALT"
            assert outcome.tier == EUAIActTier.PROHIBITED

    def test_precedence_high_over_limited(self, db_session, minimal_tree):
        """HIGH beats LIMITED regardless of answer order."""
        for answers in [
            [AnswerIn("Q_PROHIBITED", "NO"), AnswerIn("Q_HIGH", "YES"), AnswerIn("Q_LIMITED", "YES")],
            [AnswerIn("Q_PROHIBITED", "NO"), AnswerIn("Q_LIMITED", "YES"), AnswerIn("Q_HIGH", "YES")],
        ]:
            outcome = resolve_context_classification(answers, minimal_tree.version, db_session)
            assert outcome.kind == "RESOLVED"
            assert outcome.tier == EUAIActTier.HIGH

    def test_incomplete_answers_are_unresolved(self, db_session, minimal_tree):
        """Only one of three questions answered → UNRESOLVED, never MINIMAL."""
        answers = [AnswerIn(question_code="Q_PROHIBITED", option_code="NO")]
        outcome = resolve_context_classification(answers, minimal_tree.version, db_session)
        assert outcome.kind == "UNRESOLVED"
        assert outcome.tier is None
        assert "Q_HIGH" in outcome.missing
        assert "Q_LIMITED" in outcome.missing

    def test_no_answers_unresolved(self, db_session, minimal_tree):
        outcome = resolve_context_classification([], minimal_tree.version, db_session)
        assert outcome.kind == "UNRESOLVED"
        assert set(outcome.missing) == {"Q_PROHIBITED", "Q_HIGH", "Q_LIMITED"}

    def test_determinism(self, db_session, minimal_tree):
        """Same (answers, tree_version) yields identical outcome on repeated calls."""
        answers = [AnswerIn("Q_PROHIBITED", "NO"), AnswerIn("Q_HIGH", "YES"), AnswerIn("Q_LIMITED", "NO")]
        o1 = resolve_context_classification(answers, minimal_tree.version, db_session)
        o2 = resolve_context_classification(answers, minimal_tree.version, db_session)
        assert o1.kind == o2.kind
        assert o1.tier == o2.tier
        assert o1.subcategory_code == o2.subcategory_code

    def test_subcategory_populated_for_prohibited(self, db_session, minimal_tree):
        answers = [
            AnswerIn("Q_PROHIBITED", "YES"),
            AnswerIn("Q_HIGH", "NO"),
            AnswerIn("Q_LIMITED", "NO"),
        ]
        outcome = resolve_context_classification(answers, minimal_tree.version, db_session)
        assert outcome.subcategory_code == "ART5_TEST"

    def test_subcategory_none_for_minimal(self, db_session, minimal_tree):
        outcome = resolve_context_classification(
            self._all_no(minimal_tree), minimal_tree.version, db_session
        )
        assert outcome.subcategory_code is None

    def test_unknown_tree_version_raises_422(self, db_session, minimal_tree):
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc:
            resolve_context_classification([], "version-does-not-exist", db_session)
        assert exc.value.status_code == 422

    def test_unknown_question_code_raises_422(self, db_session, minimal_tree):
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc:
            resolve_context_classification(
                [AnswerIn("Q_UNKNOWN", "NO")], minimal_tree.version, db_session
            )
        assert exc.value.status_code == 422

    def test_prohibited_short_circuits_missing(self, db_session, minimal_tree):
        """Answering only the PROHIBITED question YES resolves immediately."""
        answers = [AnswerIn("Q_PROHIBITED", "YES")]
        outcome = resolve_context_classification(answers, minimal_tree.version, db_session)
        assert outcome.kind == "PROHIBITED_HALT"
        assert outcome.missing == []


# ─────────────────────────────────────────────────────────────────────────────
# 2. Seed loader
# ─────────────────────────────────────────────────────────────────────────────

class TestSeedLoader:
    def test_idempotent_on_same_content(self, db_session, minimal_tree):
        """Reloading the same tree version is a no-op (content hash matches)."""
        from scripts.seed.seed_decision_tree import _load_tree as load_fn, _compute_hash

        raw_questions = [
            {
                "code": "Q_PROHIBITED",
                "text": "Is this a prohibited practice?",
                "probes_rung": "PROHIBITED",
                "legal_ref": "Art. 5",
                "order": 10,
                "options": [
                    {"code": "YES", "label": "Yes", "asserts_rung": "PROHIBITED", "asserts_subcategory_code": "ART5_TEST"},
                    {"code": "NO", "label": "No", "asserts_rung": None, "asserts_subcategory_code": None},
                ],
            }
        ]
        # Patch the tree's content_hash to match what _compute_hash would produce
        # for a tree with just Q_PROHIBITED (our minimal_tree has 3 questions).
        # Instead, test with a fresh tree insert + re-load scenario.

        # Build a data dict matching the minimal_tree's content.
        # Since minimal_tree has a static content_hash placeholder, we just
        # verify that _load_tree skips when version exists and hash matches.
        # We'll create a synthetic tree directly.
        hash_val = _compute_hash(raw_questions)
        tree2 = DecisionTree(
            id=uuid.uuid4(), version="loader-test-1.0",
            name="Loader Test", content_hash=hash_val,
        )
        db_session.add(tree2)
        db_session.flush()

        data = {"version": "loader-test-1.0", "name": "Loader Test", "questions": raw_questions}
        # Should be a no-op (same hash → skip).
        load_fn(db_session, data)  # no exception

    def test_fails_loud_on_content_mutation(self, db_session, minimal_tree):
        """Changing content under an existing version raises RuntimeError."""
        from scripts.seed.seed_decision_tree import _load_tree as load_fn

        data = {
            "version": minimal_tree.version,
            "name": minimal_tree.name,
            "questions": [
                {
                    "code": "Q_NEW",
                    "text": "New question that mutates the frozen version",
                    "probes_rung": "HIGH",
                    "legal_ref": None,
                    "order": 1,
                    "options": [
                        {"code": "YES", "label": "Yes", "asserts_rung": "HIGH", "asserts_subcategory_code": None},
                    ],
                }
            ],
        }
        with pytest.raises(RuntimeError, match="Frozen versions cannot be mutated"):
            load_fn(db_session, data)


# ─────────────────────────────────────────────────────────────────────────────
# 3. Compute-and-record integration (WI-6)
# ─────────────────────────────────────────────────────────────────────────────

class TestComputeAndRecord:
    def _all_no(self) -> list[AnswerIn]:
        return [
            AnswerIn("Q_PROHIBITED", "NO"),
            AnswerIn("Q_HIGH", "NO"),
            AnswerIn("Q_LIMITED", "NO"),
        ]

    def _high_answers(self) -> list[AnswerIn]:
        return [
            AnswerIn("Q_PROHIBITED", "NO"),
            AnswerIn("Q_HIGH", "YES"),
            AnswerIn("Q_LIMITED", "NO"),
        ]

    def _prohibited_answers(self) -> list[AnswerIn]:
        return [AnswerIn("Q_PROHIBITED", "YES")]

    def test_resolvable_answers_write_pending_review_snapshot(
        self, db_session, tenant, member, minimal_tree
    ):
        user, m = member
        system = _make_system(db_session, tenant)
        uc = _make_use_case(db_session, tenant, system)

        outcome, snapshot = compute_and_record_classification(
            use_case=uc,
            answers=self._high_answers(),
            tree_version=minimal_tree.version,
            db=db_session,
            actor_user_id=user.id,
        )
        db_session.flush()

        assert outcome.kind == "RESOLVED"
        assert snapshot is not None
        assert snapshot.status == ClassificationStatus.PENDING_REVIEW
        assert snapshot.tier == EUAIActTier.HIGH
        assert snapshot.is_current is True

    def test_eu_tier_not_stamped_on_compute(
        self, db_session, tenant, member, minimal_tree
    ):
        user, m = member
        system = _make_system(db_session, tenant)
        uc = _make_use_case(db_session, tenant, system)

        compute_and_record_classification(
            use_case=uc, answers=self._high_answers(),
            tree_version=minimal_tree.version, db=db_session,
            actor_user_id=user.id,
        )
        db_session.flush()
        db_session.refresh(uc)

        # eu_tier must remain UNCLASSIFIED until Reviewer sign-off.
        assert uc.eu_tier == EUAIActTier.UNCLASSIFIED

    def test_unresolved_writes_nothing(
        self, db_session, tenant, member, minimal_tree
    ):
        user, m = member
        system = _make_system(db_session, tenant)
        uc = _make_use_case(db_session, tenant, system)

        outcome, snapshot = compute_and_record_classification(
            use_case=uc, answers=[AnswerIn("Q_PROHIBITED", "NO")],
            tree_version=minimal_tree.version, db=db_session,
            actor_user_id=user.id,
        )
        db_session.flush()

        assert outcome.kind == "UNRESOLVED"
        assert snapshot is None
        count = db_session.scalar(
            select(Classification).where(Classification.use_case_id == uc.id)
        )
        assert count is None

    def test_classification_tier_never_unclassified(
        self, db_session, tenant, member, minimal_tree
    ):
        user, m = member
        system = _make_system(db_session, tenant)
        uc = _make_use_case(db_session, tenant, system)

        _, snapshot = compute_and_record_classification(
            use_case=uc, answers=self._all_no(),
            tree_version=minimal_tree.version, db=db_session,
            actor_user_id=user.id,
        )
        db_session.flush()

        assert snapshot is not None
        assert snapshot.tier != EUAIActTier.UNCLASSIFIED
        assert snapshot.tier not in (EUAIActTier.REQUIRES_CONTEXT, EUAIActTier.UNCLASSIFIED)

    def test_override_by_system_owner_records_metadata(
        self, db_session, tenant, member, minimal_tree
    ):
        user, m = member
        system = _make_system(db_session, tenant)
        uc = _make_use_case(db_session, tenant, system)

        _, snapshot = compute_and_record_classification(
            use_case=uc, answers=self._high_answers(),
            tree_version=minimal_tree.version, db=db_session,
            actor_user_id=user.id,
            override_tier=EUAIActTier.LIMITED,
            justification="Deployment context shows limited risk",
        )
        db_session.flush()

        assert snapshot is not None
        assert snapshot.overridden is True
        assert snapshot.tier == EUAIActTier.LIMITED
        assert snapshot.proposed_tier == EUAIActTier.HIGH
        assert "Deployment context" in snapshot.rationale

    def test_concurrent_compute_only_one_is_current(
        self, db_session, tenant, member, minimal_tree
    ):
        """Two sequential computes → second flips first; only one is_current."""
        user, m = member
        system = _make_system(db_session, tenant)
        uc = _make_use_case(db_session, tenant, system)

        _, first = compute_and_record_classification(
            use_case=uc, answers=self._high_answers(),
            tree_version=minimal_tree.version, db=db_session,
            actor_user_id=user.id,
        )
        db_session.flush()

        _, second = compute_and_record_classification(
            use_case=uc, answers=self._all_no(),
            tree_version=minimal_tree.version, db=db_session,
            actor_user_id=user.id,
        )
        db_session.flush()

        db_session.refresh(first)
        assert first.is_current is False
        assert second.is_current is True

        current_count = db_session.scalar(
            select(Classification.id).where(
                Classification.use_case_id == uc.id,
                Classification.is_current.is_(True),
            )
        )
        assert current_count is not None

    def test_prohibited_compute_creates_prohibited_halt_snapshot(
        self, db_session, tenant, member, minimal_tree
    ):
        user, m = member
        system = _make_system(db_session, tenant)
        uc = _make_use_case(db_session, tenant, system)

        outcome, snapshot = compute_and_record_classification(
            use_case=uc, answers=self._prohibited_answers(),
            tree_version=minimal_tree.version, db=db_session,
            actor_user_id=user.id,
        )
        db_session.flush()

        assert outcome.kind == "PROHIBITED_HALT"
        assert snapshot is not None
        assert snapshot.tier == EUAIActTier.PROHIBITED
        assert snapshot.status == ClassificationStatus.PENDING_REVIEW


# ─────────────────────────────────────────────────────────────────────────────
# 4. Reviewer sign-off (WI-7)
# ─────────────────────────────────────────────────────────────────────────────

class TestSignOff:
    def _compute(self, db, tenant, user, uc, tree, answers):
        compute_and_record_classification(
            use_case=uc, answers=answers,
            tree_version=tree.version, db=db,
            actor_user_id=user.id,
        )
        db.flush()

    def test_sign_off_flips_status_and_stamps_eu_tier(
        self, db_session, tenant, member, minimal_tree
    ):
        user, m = member
        system = _make_system(db_session, tenant)
        uc = _make_use_case(db_session, tenant, system)
        answers = [AnswerIn("Q_PROHIBITED", "NO"), AnswerIn("Q_HIGH", "YES"), AnswerIn("Q_LIMITED", "NO")]
        self._compute(db_session, tenant, user, uc, minimal_tree, answers)

        snapshot = sign_off_classification(uc, db_session, reviewer_user_id=user.id)
        db_session.flush()
        db_session.refresh(uc)

        assert snapshot.status == ClassificationStatus.APPROVED
        assert uc.eu_tier == EUAIActTier.HIGH

    def test_prohibited_sign_off_stamps_eu_tier_prohibited(
        self, db_session, tenant, member, minimal_tree
    ):
        user, m = member
        system = _make_system(db_session, tenant)
        uc = _make_use_case(db_session, tenant, system)
        self._compute(db_session, tenant, user, uc, minimal_tree,
                      [AnswerIn("Q_PROHIBITED", "YES")])

        sign_off_classification(uc, db_session, reviewer_user_id=user.id)
        db_session.flush()
        db_session.refresh(uc)

        assert uc.eu_tier == EUAIActTier.PROHIBITED

    def test_double_sign_off_raises_409(
        self, db_session, tenant, member, minimal_tree
    ):
        from fastapi import HTTPException
        user, m = member
        system = _make_system(db_session, tenant)
        uc = _make_use_case(db_session, tenant, system)
        answers = [AnswerIn("Q_PROHIBITED", "NO"), AnswerIn("Q_HIGH", "NO"), AnswerIn("Q_LIMITED", "YES")]
        self._compute(db_session, tenant, user, uc, minimal_tree, answers)
        sign_off_classification(uc, db_session, reviewer_user_id=user.id)
        db_session.flush()

        with pytest.raises(HTTPException) as exc:
            sign_off_classification(uc, db_session, reviewer_user_id=user.id)
        assert exc.value.status_code == 409

    def test_sign_off_without_pending_raises_404(
        self, db_session, tenant, member, minimal_tree
    ):
        from fastapi import HTTPException
        user, m = member
        system = _make_system(db_session, tenant)
        uc = _make_use_case(db_session, tenant, system)

        with pytest.raises(HTTPException) as exc:
            sign_off_classification(uc, db_session, reviewer_user_id=user.id)
        assert exc.value.status_code == 404


# ─────────────────────────────────────────────────────────────────────────────
# 5. HTTP integration — auth and endpoint behaviour
# ─────────────────────────────────────────────────────────────────────────────

class TestHTTPEndpoints:
    def _setup(self, db_session, tenant, gov_roles, minimal_tree):
        system = _make_system(db_session, tenant)
        uc = _make_use_case(db_session, tenant, system)
        return system, uc

    def _override(self, client, db_session, ctx):
        app.dependency_overrides[get_tenant_context] = _ctx_override(ctx)
        app.dependency_overrides[get_tenant_db] = _db_override(db_session)

    def _clear(self):
        app.dependency_overrides.pop(get_tenant_context, None)
        app.dependency_overrides.pop(get_tenant_db, None)

    # ── GET /context ─────────────────────────────────────────────────────────

    @pytest.mark.parametrize("role_key", [
        "system_owner", "contributor", "reviewer", "authoriser", "auditor"
    ])
    def test_get_context_allowed_for_all_roles(
        self, client, db_session, tenant, member, gov_roles, minimal_tree, role_key
    ):
        user, m = member
        _grant(db_session, tenant, m, gov_roles[role_key])
        _, uc = self._setup(db_session, tenant, gov_roles, minimal_tree)
        ctx = _make_ctx(user, m, tenant)
        self._override(client, db_session, ctx)
        try:
            r = client.get(f"/v1/use-cases/{uc.id}/classification/context")
        finally:
            self._clear()
        assert r.status_code == 200
        body = r.json()
        assert "residual_questions" in body
        assert body["residual_questions"]["tree_version"] == minimal_tree.version

    # ── POST /context/preview ─────────────────────────────────────────────────

    @pytest.mark.parametrize("role_key", [
        "system_owner", "contributor", "reviewer", "authoriser", "auditor"
    ])
    def test_preview_allowed_for_all_roles(
        self, client, db_session, tenant, member, gov_roles, minimal_tree, role_key
    ):
        user, m = member
        _grant(db_session, tenant, m, gov_roles[role_key])
        _, uc = self._setup(db_session, tenant, gov_roles, minimal_tree)
        ctx = _make_ctx(user, m, tenant)
        self._override(client, db_session, ctx)
        try:
            r = client.post(
                f"/v1/use-cases/{uc.id}/classification/context/preview",
                json={
                    "answers": [
                        {"question_code": "Q_PROHIBITED", "option_code": "NO", "provenance": "user_confirmed"},
                        {"question_code": "Q_HIGH", "option_code": "YES", "provenance": "user_confirmed"},
                        {"question_code": "Q_LIMITED", "option_code": "NO", "provenance": "user_confirmed"},
                    ],
                    "tree_version": minimal_tree.version,
                },
            )
        finally:
            self._clear()
        assert r.status_code == 200
        assert r.json()["kind"] == "RESOLVED"
        assert r.json()["tier"] == "high_risk"

    # ── POST /context — gating ────────────────────────────────────────────────

    @pytest.mark.parametrize("role_key", ["reviewer", "authoriser", "auditor"])
    def test_compute_forbidden_for_non_first_line(
        self, client, db_session, tenant, member, gov_roles, minimal_tree, role_key
    ):
        user, m = member
        _grant(db_session, tenant, m, gov_roles[role_key])
        _, uc = self._setup(db_session, tenant, gov_roles, minimal_tree)
        ctx = _make_ctx(user, m, tenant)
        self._override(client, db_session, ctx)
        try:
            r = client.post(
                f"/v1/use-cases/{uc.id}/classification/context",
                json={
                    "answers": [
                        {"question_code": "Q_PROHIBITED", "option_code": "NO", "provenance": "user_confirmed"},
                        {"question_code": "Q_HIGH", "option_code": "NO", "provenance": "user_confirmed"},
                        {"question_code": "Q_LIMITED", "option_code": "NO", "provenance": "user_confirmed"},
                    ],
                    "tree_version": minimal_tree.version,
                },
            )
        finally:
            self._clear()
        assert r.status_code == 403

    def test_compute_allowed_for_system_owner(
        self, client, db_session, tenant, member, gov_roles, minimal_tree
    ):
        user, m = member
        _grant(db_session, tenant, m, gov_roles["system_owner"])
        _, uc = self._setup(db_session, tenant, gov_roles, minimal_tree)
        ctx = _make_ctx(user, m, tenant)
        self._override(client, db_session, ctx)
        try:
            r = client.post(
                f"/v1/use-cases/{uc.id}/classification/context",
                json={
                    "answers": [
                        {"question_code": "Q_PROHIBITED", "option_code": "NO", "provenance": "user_confirmed"},
                        {"question_code": "Q_HIGH", "option_code": "YES", "provenance": "user_confirmed"},
                        {"question_code": "Q_LIMITED", "option_code": "NO", "provenance": "user_confirmed"},
                    ],
                    "tree_version": minimal_tree.version,
                },
            )
        finally:
            self._clear()
        assert r.status_code == 201
        body = r.json()
        assert body["classification"]["status"] == "pending_review"
        assert body["classification"]["tier"] == "high_risk"

    def test_override_by_contributor_only_is_403(
        self, client, db_session, tenant, member, gov_roles, minimal_tree
    ):
        """contributor can compute but cannot override the tier."""
        user, m = member
        _grant(db_session, tenant, m, gov_roles["contributor"])
        _, uc = self._setup(db_session, tenant, gov_roles, minimal_tree)
        ctx = _make_ctx(user, m, tenant)
        self._override(client, db_session, ctx)
        try:
            r = client.post(
                f"/v1/use-cases/{uc.id}/classification/context",
                json={
                    "answers": [
                        {"question_code": "Q_PROHIBITED", "option_code": "NO", "provenance": "user_confirmed"},
                        {"question_code": "Q_HIGH", "option_code": "YES", "provenance": "user_confirmed"},
                        {"question_code": "Q_LIMITED", "option_code": "NO", "provenance": "user_confirmed"},
                    ],
                    "tree_version": minimal_tree.version,
                    "override_tier": "limited_risk",
                    "justification": "We think it's limited",
                },
            )
        finally:
            self._clear()
        assert r.status_code == 403

    # ── POST /sign-off — gating ──────────────────────────────────────────────

    @pytest.mark.parametrize("role_key", ["system_owner", "contributor", "authoriser", "auditor"])
    def test_sign_off_forbidden_for_non_reviewer(
        self, client, db_session, tenant, member, gov_roles, minimal_tree, role_key
    ):
        user, m = member
        _grant(db_session, tenant, m, gov_roles[role_key])
        _, uc = self._setup(db_session, tenant, gov_roles, minimal_tree)
        ctx = _make_ctx(user, m, tenant)
        self._override(client, db_session, ctx)
        try:
            r = client.post(f"/v1/use-cases/{uc.id}/classification/sign-off")
        finally:
            self._clear()
        assert r.status_code == 403

    def test_sign_off_allowed_for_reviewer(
        self, client, db_session, tenant, member, gov_roles, minimal_tree
    ):
        user, m = member
        _grant(db_session, tenant, m, gov_roles["system_owner"])
        system = _make_system(db_session, tenant)
        uc = _make_use_case(db_session, tenant, system)

        # First compute a classification via service layer.
        compute_and_record_classification(
            use_case=uc,
            answers=[
                AnswerIn("Q_PROHIBITED", "NO"),
                AnswerIn("Q_HIGH", "YES"),
                AnswerIn("Q_LIMITED", "NO"),
            ],
            tree_version=minimal_tree.version,
            db=db_session,
            actor_user_id=user.id,
        )
        db_session.flush()

        # Now sign off as reviewer.
        reviewer_user, reviewer_m = _make_member(db_session, tenant)
        _grant(db_session, tenant, reviewer_m, gov_roles["reviewer"])
        ctx = _make_ctx(reviewer_user, reviewer_m, tenant)
        self._override(client, db_session, ctx)
        try:
            r = client.post(f"/v1/use-cases/{uc.id}/classification/sign-off")
        finally:
            self._clear()

        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "approved"
        assert body["tier"] == "high_risk"

        db_session.refresh(uc)
        assert uc.eu_tier == EUAIActTier.HIGH
