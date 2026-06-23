from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.auth.operator_authz import CurrentOperator, require_permission
from app.db.session import get_platform_ro_db
from app.models.platform_rbac import Operator, OperatorRole, Role
from app.schemas.platform import OperatorCreate, OperatorCreated, OperatorListItem, RoleListItem
from app.services.operator_provisioning import (
    OperatorAlreadyExists,
    OperatorProvisioningError,
    RoleNotFound,
    provision_operator,
)

router = APIRouter(tags=["platform"])


@router.post("/operators", response_model=OperatorCreated, status_code=201)
def create_operator(
    body: OperatorCreate,
    operator: CurrentOperator = Depends(require_permission("operator:create")),
) -> OperatorCreated:
    try:
        operator_id, cognito_sub = provision_operator(
            email=body.email,
            display_name=body.display_name,
            role_key=body.role_key,
            actor=operator,
            source="http",
        )
    except OperatorAlreadyExists as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except RoleNotFound as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except OperatorProvisioningError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    return OperatorCreated(operator_id=operator_id, cognito_sub=cognito_sub)


@router.get("/operators", response_model=list[OperatorListItem])
def list_operators(
    operator: CurrentOperator = Depends(require_permission("operator:create")),
    db: Session = Depends(get_platform_ro_db),
) -> list[OperatorListItem]:
    ops = db.scalars(
        select(Operator)
        .options(selectinload(Operator.role_links).selectinload(OperatorRole.role))
        .order_by(Operator.created_at)
    ).all()
    return [
        OperatorListItem(
            id=op.id,
            email=op.email,
            display_name=op.display_name,
            status=op.status.value,
            roles=[link.role.key for link in op.role_links],
        )
        for op in ops
    ]


@router.get("/roles", response_model=list[RoleListItem])
def list_roles(
    operator: CurrentOperator = Depends(require_permission("operator:create")),
    db: Session = Depends(get_platform_ro_db),
) -> list[RoleListItem]:
    roles = db.scalars(select(Role).order_by(Role.key)).all()
    return [RoleListItem(key=r.key, description=r.description) for r in roles]
