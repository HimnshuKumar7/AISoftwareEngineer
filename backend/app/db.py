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

# pool_pre_ping & pool_recycle avoid "SSL connection closed unexpectedly" 
# errors when Neon's serverless compute auto-suspends idle connections.
engine_kwargs = {"pool_pre_ping": True}
if "sqlite" not in settings.DATABASE_URL:
    engine_kwargs["pool_recycle"] = 300
    engine_kwargs["pool_timeout"] = 30
else:
    engine_kwargs["connect_args"] = {"check_same_thread": False}

engine = create_engine(settings.DATABASE_URL, **engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


import time


def init_db():
    """Create tables if they don't exist yet. Called once on app startup."""
    from app.auth import models  # noqa: F401  (registers models on Base)
    for attempt in range(1, 4):
        try:
            Base.metadata.create_all(bind=engine)
            print("--> [Database] Connected & tables verified successfully.")
            return
        except Exception as e:
            print(f"--> [Database] Connection attempt {attempt}/3 failed ({e}). Retrying in 1s...")
            time.sleep(1)
    print("--> [Warning] Could not complete init_db on startup. App will proceed.")
