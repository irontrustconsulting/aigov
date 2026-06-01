"""
Cognito ID-token verification for FastAPI.

A request arrives with `Authorization: Bearer <id_token>`. We verify the token
is a genuine, unexpired ID token from OUR Cognito user pool, then expose its
claims as a typed object.

What we check (each guards a specific failure mode):
  - signature: signed by our pool's private key (verified against the pool's
    published JWKS public keys) -> proves the token is not forged.
  - iss (issuer): equals our pool's issuer URL -> proves it is OUR pool.
  - aud (audience): equals our app client id -> proves it was minted for our app.
  - token_use == "id": reject access tokens; we want the ID token.
  - exp: not expired (enforced by the library).

The JWKS keys are fetched once and cached by PyJWKClient (they rotate rarely);
we do NOT fetch them per request.
"""

from __future__ import annotations

from functools import lru_cache

import jwt
from jwt import PyJWKClient
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from app.config import settings


class CognitoClaims(BaseModel):
    """The verified identity we trust from a valid ID token."""
    sub: str
    email: str | None = None
    name: str | None = None
    tenant_id: str          # from custom:tenant_id — the tenant's DB id
    role: str | None = None  # from custom:role


@lru_cache(maxsize=1)
def _issuer() -> str:
    return (
        f"https://cognito-idp.{settings.cognito_region}.amazonaws.com/"
        f"{settings.cognito_user_pool_id}"
    )


@lru_cache(maxsize=1)
def _jwk_client() -> PyJWKClient:
    """Cached JWKS client — fetches and caches the pool's public keys."""
    return PyJWKClient(f"{_issuer()}/.well-known/jwks.json")


# Extracts the "Bearer <token>" header. auto_error=False so we can return our
# own 401 rather than FastAPI's default.
_bearer = HTTPBearer(auto_error=False)


def verify_cognito_token(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> CognitoClaims:
    """FastAPI dependency: verify the bearer ID token, return typed claims.

    Raises 401 on any failure (missing/invalid/expired/wrong-audience token).
    """
    if creds is None or not creds.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = creds.credentials
    try:
        signing_key = _jwk_client().get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],          # Cognito signs with RS256
            audience=settings.cognito_app_client_id,   # checks `aud`
            issuer=_issuer(),                            # checks `iss`
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

    tenant_id = claims.get("custom:tenant_id")
    if not tenant_id:
        # A verified user with no tenant claim cannot be scoped — reject.
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Token has no tenant_id claim",
        )

    return CognitoClaims(
        sub=claims["sub"],
        email=claims.get("email"),
        name=claims.get("name"),
        tenant_id=tenant_id,
        role=claims.get("custom:role"),
    )