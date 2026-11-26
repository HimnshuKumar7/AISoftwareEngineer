"""SQLAlchemy models (Neon PostgreSQL in production, SQLite only for local tests)."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


# Repository lifecycle. `queued -> cloning -> parsing -> embedding -> indexing -> ready` or `failed`.
REPO_ACTIVE_STATUSES = ("queued", "cloning", "parsing", "embedding", "indexing")
REPO_STATUSES = REPO_ACTIVE_STATUSES + ("ready", "failed")


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    name: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    password_hash: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    repositories: Mapped[List["Repository"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )


class Repository(Base):
    __tablename__ = "repositories"
    __table_args__ = (
        UniqueConstraint("user_id", "owner", "name", name="uq_repo_per_user"),
        Index("ix_repositories_user_created", "user_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    url: Mapped[str] = mapped_column(String(500))
    owner: Mapped[str] = mapped_column(String(100))
    name: Mapped[str] = mapped_column(String(100))
    branch: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    commit_sha: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="queued", index=True)
    status_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    file_count: Mapped[int] = mapped_column(Integer, default=0)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    languages: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    indexed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[User] = relationship(back_populates="repositories")
    queries: Mapped[List["QueryHistory"]] = relationship(
        back_populates="repository", cascade="all, delete-orphan", passive_deletes=True
    )
    index: Mapped[Optional["RepoIndex"]] = relationship(
        back_populates="repository", cascade="all, delete-orphan", passive_deletes=True, uselist=False
    )


class RepoIndex(Base):
    """Remote persistence for a repository's FAISS index + chunk metadata.

    Render's disk is ephemeral, so the serialized index lives here (one row per repository) and is
    re-hydrated to local disk/RAM on demand. Rows are strictly keyed by repository id, which keeps
    every repository's index isolated from every other repository's.
    """

    __tablename__ = "repo_indexes"

    repo_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("repositories.id", ondelete="CASCADE"), primary_key=True
    )
    faiss_blob: Mapped[bytes] = mapped_column(LargeBinary)
    chunks_blob: Mapped[bytes] = mapped_column(LargeBinary)  # gzip-compressed JSON
    chunk_count: Mapped[int] = mapped_column(Integer)
    embedding_model: Mapped[str] = mapped_column(String(120))
    dim: Mapped[int] = mapped_column(Integer)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    repository: Mapped[Repository] = relationship(back_populates="index")


class QueryHistory(Base):
    __tablename__ = "query_history"
    __table_args__ = (Index("ix_query_history_repo_conv", "repo_id", "conversation_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    repo_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("repositories.id", ondelete="CASCADE"))
    conversation_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True)
    mode: Mapped[str] = mapped_column(String(20), default="qa")
    question: Mapped[str] = mapped_column(Text)
    answer: Mapped[str] = mapped_column(Text, default="")
    sub_queries: Mapped[List[str]] = mapped_column(JSON, default=list)
    sources: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, default=list)
    citations: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, default=list)
    llm_provider: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    llm_model: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    repository: Mapped[Repository] = relationship(back_populates="queries")
