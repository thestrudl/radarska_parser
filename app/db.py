"""SQLAlchemy engine/session setup with connection pooling and connect retries."""
from __future__ import annotations

import logging
import time

from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker

from app.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    future=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


def get_session():
    """FastAPI dependency yielding a DB session."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def wait_for_db(retries: int = 30, delay: float = 2.0) -> None:
    """Block until the database accepts connections (used at worker startup)."""
    from sqlalchemy import text

    for attempt in range(1, retries + 1):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            logger.info("Database is ready.")
            return
        except OperationalError as err:
            logger.info("Waiting for database (%d/%d): %s", attempt, retries, err)
            time.sleep(delay)
    raise RuntimeError("Database did not become available in time")
