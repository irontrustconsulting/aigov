"""
TODO: remove after acceptance testing — verification aid only.

GET /platform/whoami lets you confirm the full operator-authZ contract end-to-end
once a genesis operator exists and can mint a token:
  valid + permitted  → identity echoed
  disabled/unknown   → 403
  missing permission → 403
  no token           → 401
"""

from fastapi import APIRouter, Depends

from app.auth.operator_authz import CurrentOperator, require_permission

router = APIRouter(tags=["platform"])


@router.get("/whoami")
def platform_whoami(
    operator: CurrentOperator = Depends(require_permission("tenant:provision")),
) -> dict:
    return {
        "id": str(operator.id),
        "cognito_sub": operator.cognito_sub,
        "email": operator.email,
        "display_name": operator.display_name,
        "permissions": sorted(operator.permissions),
    }
