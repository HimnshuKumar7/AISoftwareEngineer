import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, Integer, Text, ForeignKey, DateTime
from sqlalchemy.orm import relationship

from app.db import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=_uuid)
    name = Column(String(120), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    repos = relationship("Repo", back_populates="owner", cascade="all, delete-orphan")
    history = relationship("QueryHistory", back_populates="user", cascade="all, delete-orphan")


class Repo(Base):
    """A repo a user has indexed. repo_id matches the FAISS index folder name."""
    __tablename__ = "repos"

    id = Column(String, primary_key=True)  # = repo_id (hash of URL)
    owner_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    url = Column(String(500), nullable=False)
    num_files = Column(Integer, default=0)
    num_chunks = Column(Integer, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    owner = relationship("User", back_populates="repos")


class QueryHistory(Base):
    __tablename__ = "query_history"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    repo_id = Column(String, ForeignKey("repos.id"), nullable=False)
    repo_url = Column(String(500), nullable=False)
    action_type = Column(String(30), default="ask")  # ask | docs | tests | duplicates | optimize
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="history")
