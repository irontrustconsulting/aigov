"""
Database wiring: engine, session factory, and the request-scoped session
dependency used by FastAPI route handlers.

Sync SQLAlchemy 2.0 for now (simplest to reason about). The async seam for the
lifecycle worker comes later and doesn't require async here — keep this sync.
"""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings

engine = create_engine(
    settings.database_url,
    echo=settings.debug,          # log SQL in dev; quiet in prod
    pool_pre_ping=True,           # transparently recover dropped connections
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency. Yields a session, always closes it.

    Usage:
        @router.get("/things")
        def list_things(db: Session = Depends(get_db)):
            ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()