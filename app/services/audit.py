"""
Platform audit helper.

record_platform_event() adds a PlatformAuditEvent row to the given session.
The caller is responsible for committing — this keeps transaction control in
the calling service, not the audit helper, so a failed commit never leaves a
phantom audit row.
"""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.auth.operator_authz import CurrentOperator
from app.models.platform_audit import PlatformAuditEvent


def record_platform_event(
    session: Session,
    *,
    actor: CurrentOperator | None,
    action: str,
    target_type: str,
    target_id: uuid.UUID | None,
    target_ref: str,
    source: str,
    detail: dict | None = None,
) -> None:
    """Stage a platform audit row on `session`. Caller must commit.

    actor=None is valid only for the genesis bootstrap (first create-operator),
    where no prior operator exists to attribute the action to.
    """
    session.add(PlatformAuditEvent(
        id=uuid.uuid4(),
        actor_sub=actor.cognito_sub if actor else None,
        actor_email=actor.email if actor else None,
        action=action,
        target_type=target_type,
        target_id=target_id,
        target_ref=target_ref,
        detail=detail or {},
        source=source,
    ))
