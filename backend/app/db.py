"""
Database session setup for Neon (serverless Postgres).

Neon connection strings already include `sslmode=require`, which is all
SQLAlchemy needs - no extra config beyond the URL itself.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from app.config import settings

if not settings.DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL is not set. Copy your Neon connection string into "
        "backend/.env as DATABASE_URL=postgresql://... (see .env.example)."
    )

# pool_pre_ping avoids "server closed the connection" errors that happen
# when Neon's serverless compute auto-suspends an idle connection.
engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create tables if they don't exist yet. Called once on app startup."""
    from app.auth import models  # noqa: F401  (registers models on Base)
    Base.metadata.create_all(bind=engine)
