"""
FastAPI application entry point.

For the foundation phase this holds only a health check. Routers get included
here as you build them (e.g. app.include_router(systems.router)).
"""

from fastapi import Depends, FastAPI
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db

app = FastAPI(
    title="AI Governance API",
    debug=settings.debug,
)


@app.get("/health")
def health() -> dict:
    """Liveness: the app is up."""
    return {"status": "ok", "env": settings.app_env}


@app.get("/health/db")
def health_db(db: Session = Depends(get_db)) -> dict:
    """Readiness: the app can reach the database."""
    db.execute(text("SELECT 1"))
    return {"status": "ok", "db": "reachable"}