"""
Cognito ID-token verification for PLATFORM OPERATORS.

This is the operator-plane counterpart of app/cognito.py. The structure is
deliberately PARALLEL rather than shared: keeping the two verifiers as separate,
self-contained units makes the plane separation explicit and auditable. Each one
is hard-wired to exactly one Cognito pool and one app client and cannot be
accidentally pointed at the other. (If the duplication ever grates, the shared
JWKS/decode plumbing can be factored into a helper later — but the two PUBLIC
dependencies should stay distinct.)

A request arrives with `Authorization: Bearer <id_token>`. We verify the token
is a genuine, unexpired ID token from the OPERATOR user pool, then expose its
claims as a typed object.

The cross-plane guarantee (security-critical):
  - iss (issuer)   must equal the OPERATOR pool's issuer URL
  - aud (audience) must equal the OPERATOR app client id
A tenant token carries the tenant pool's `iss` and the tenant app client's `aud`,
so it FAILS both checks here — and an operator token symmetrically fails the
tenant verifier. The two planes cannot bleed into one another, and this falls
out of the iss/aud checks for free: no extra "is this a tenant token?" logic.

What we DON'T do here (unlike the tenant verifier):
  - We do NOT look for custom:tenant_id. Operators are not members of any tenant.
  - We do NOT read a role/permission from the token. What an operator may DO is
    authorization, which lives in the DATABASE (the require_permission seam),
    not in the Cognito token. This verifier answers identity only: "who is this?"
"""

from __future__ import annotations

from functools import lru_cache

import jwt
from jwt import PyJWKClient
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from app.config import settings


class OperatorClaims(BaseModel):
    """The verified identity we trust from a valid operator ID token.

    Identity only — no tenant, no permissions. Authorization is resolved
    separately from the DB once we know the operator's `sub`.
    """
    sub: str
    email: str | None = None
    name: str | None = None


# The issuer is the AUTHORITATIVE value Terraform output (COGNITO_OPERATOR_POOL_ISSUER),
# not something we rebuild from region + pool id. Rebuilding would couple the `iss`
# check to settings.cognito_region — the TENANT pool's region — so if the operator
# pool lives in a different region (it does: eu-west-2), a rebuilt issuer would
# silently fail to match the token and every verification would 401. Consuming the
# value Cognito actually mints removes that whole class of bug.


@lru_cache(maxsize=1)
def _operator_jwk_client() -> PyJWKClient:
    """Cached JWKS client — fetches and caches the OPERATOR pool's public keys."""
    return PyJWKClient(
        f"{settings.cognito_operator_pool_issuer}/.well-known/jwks.json"
    )


# Own HTTPBearer instance. auto_error=False so we can return our own 401 rather
# than FastAPI's default.
_bearer = HTTPBearer(auto_error=False)


def verify_operator_token(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> OperatorClaims:
    """FastAPI dependency: verify the bearer ID token from the OPERATOR pool.

    Raises 401 on any failure (missing/invalid/expired/wrong-audience token).
    This establishes WHO the operator is (authN). It does NOT check what they are
    allowed to do — that is require_permission's job (authZ), layered on top.
    """
    if creds is None or not creds.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = creds.credentials
    try:
        signing_key = _operator_jwk_client().get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],                              # Cognito signs with RS256
            audience=settings.cognito_operator_app_client_id,  # checks `aud`
            issuer=settings.cognito_operator_pool_issuer,      # checks `iss`
            options={"require": ["exp", "iss", "aud", "sub"]},
        )
    except jwt.PyJWTError as e:
        # Any verification failure (bad signature, expired, wrong aud/iss, etc.)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {e}",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Belt-and-braces: ensure this is an ID token, not an access token.
    if claims.get("token_use") != "id":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Expected an ID token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return OperatorClaims(
        sub=claims["sub"],
        email=claims.get("email"),
        name=claims.get("name"),
    )