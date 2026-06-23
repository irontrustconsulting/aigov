from fastapi import APIRouter, Depends

from app.auth.operator_authz import CurrentOperator, get_current_operator

router = APIRouter(tags=["platform"])


@router.get("/me")
def platform_me(
    operator: CurrentOperator = Depends(get_current_operator),
) -> dict:
    return {
        "id": str(operator.id),
        "email": operator.email,
        "display_name": operator.display_name,
        "permissions": sorted(operator.permissions),
    }
