"""
FastAPI application entry point.

Routers are included here under the /v1 prefix. Health checks stay at the root
(unversioned) so liveness/readiness probes have a stable path.
"""

from fastapi import Depends, FastAPI
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.routers.v1 import tenants, reference, systems

from app.auth.cognito import verify_cognito_token, CognitoClaims

app = FastAPI(
    title="AI Governance API",
    debug=settings.debug,
)

# Versioned API surface.

@app.get("/v1/whoami")
def whoami(claims: CognitoClaims = Depends(verify_cognito_token)) -> dict:
    return {"sub": claims.sub, "email": claims.email,
            "name": claims.name, "tenant_id": claims.tenant_id, "role": claims.role}

app.include_router(tenants.router, prefix="/v1")
app.include_router(reference.router, prefix="/v1")
app.include_router(systems.router, prefix="/v1")


@app.get("/health")
def health() -> dict:
    """Liveness: the app is up."""
    return {"status": "ok", "env": settings.app_env}


@app.get("/health/db")
def health_db(db: Session = Depends(get_db)) -> dict:
    """Readiness: the app can reach the database."""
    db.execute(text("SELECT 1"))
    return {"status": "ok", "db": "reachable"}