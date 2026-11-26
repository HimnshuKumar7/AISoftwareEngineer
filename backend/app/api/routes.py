"""All HTTP routes, grouped by resource."""
from __future__ import annotations

import logging
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_owned_repo
from app.api.schemas import (
    ConversationSummary, HistoryItem, LoginRequest, ProviderInfo, QueryRequest, QueryResponse, RegisterRequest,
    RepoCreate, RepoOut, TokenResponse, UserOut,
)
from app.core.config import get_settings
from app.core.errors import AuthError, ConflictError, NotFoundError, RepoNotReadyError
from app.core.security import create_access_token, hash_password, verify_password
from app.db.models import REPO_ACTIVE_STATUSES, QueryHistory, Repository, User
from app.db.session import get_db
from app.ingestion.github import parse_github_url
from app.ingestion.index_store import get_index_store
from app.llm.providers import list_providers
from app.rag.duplicates import scan_repository
from app.services.indexer import submit_index_job
from app.services.query_service import answer_question

log = logging.getLogger(__name__)

# A real bcrypt hash, verified against when the email is unknown so response time doesn't reveal accounts.
_DUMMY_HASH = hash_password("dummy-password-for-timing")

auth_router = APIRouter(prefix="/auth", tags=["auth"])
repo_router = APIRouter(prefix="/repos", tags=["repositories"])
meta_router = APIRouter(tags=["meta"])


# ------------------------------------------------------------------ auth
@auth_router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(body: RegisterRequest, db: Session = Depends(get_db)):
    if db.execute(select(User.id).where(User.email == body.email)).first():
        raise ConflictError("An account with this email already exists", code="email_taken")
    user = User(email=body.email, name=body.name, password_hash=hash_password(body.password))
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ConflictError("An account with this email already exists", code="email_taken")
    log.info("user registered id=%s", user.id)
    return TokenResponse(access_token=create_access_token(user.id), user=UserOut.model_validate(user))


@auth_router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = db.execute(select(User).where(User.email == body.email)).scalar_one_or_none()
    ok = verify_password(body.password, user.password_hash if user else _DUMMY_HASH)
    if user is None or not ok:
        raise AuthError("Incorrect email or password", code="invalid_credentials")
    return TokenResponse(access_token=create_access_token(user.id), user=UserOut.model_validate(user))


@auth_router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user


# ------------------------------------------------------------------ repositories
@repo_router.post("", response_model=RepoOut, status_code=status.HTTP_202_ACCEPTED)
def create_repo(body: RepoCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    settings = get_settings()
    ref = parse_github_url(body.url, body.branch)
    count = db.execute(select(func.count()).select_from(Repository).where(Repository.user_id == user.id)).scalar_one()
    if count >= settings.max_repos_per_user:
        raise ConflictError(f"Repository limit reached ({settings.max_repos_per_user}). Delete one to add another.",
                            code="repo_limit")
    existing = db.execute(
        select(Repository).where(Repository.user_id == user.id, Repository.owner == ref.owner, Repository.name == ref.name)
    ).scalar_one_or_none()
    if existing:
        raise ConflictError("This repository has already been added. Use re-index to refresh it.", code="repo_exists")
    repo = Repository(user_id=user.id, url=ref.canonical_url, owner=ref.owner, name=ref.name, branch=ref.branch,
                      status="queued", status_message="Waiting for an indexing worker", progress=0)
    db.add(repo)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ConflictError("This repository has already been added.", code="repo_exists")
    db.refresh(repo)
    submit_index_job(repo.id)
    log.info("repo queued id=%s %s/%s", repo.id, repo.owner, repo.name)
    return repo


@repo_router.get("", response_model=List[RepoOut])
def list_repos(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.execute(select(Repository).where(Repository.user_id == user.id).order_by(Repository.created_at.desc())).scalars().all()


@repo_router.get("/{repo_id}", response_model=RepoOut)
def get_repo(repo: Repository = Depends(get_owned_repo)):
    return repo


@repo_router.delete("/{repo_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_repo(repo: Repository = Depends(get_owned_repo), db: Session = Depends(get_db)):
    if repo.status in REPO_ACTIVE_STATUSES:
        raise ConflictError("Indexing is in progress. Wait for it to finish before deleting.", code="repo_busy")
    repo_id = repo.id
    db.delete(repo)  # cascades to repo_indexes and query_history
    db.commit()
    get_index_store().invalidate(repo_id)


@repo_router.post("/{repo_id}/reindex", response_model=RepoOut, status_code=status.HTTP_202_ACCEPTED)
def reindex_repo(repo: Repository = Depends(get_owned_repo), db: Session = Depends(get_db)):
    if repo.status in REPO_ACTIVE_STATUSES:
        raise ConflictError("Indexing is already in progress.", code="repo_busy")
    repo.status, repo.status_message, repo.progress = "queued", "Waiting for an indexing worker", 0
    db.commit()
    db.refresh(repo)
    submit_index_job(repo.id)
    return repo


@repo_router.get("/{repo_id}/duplicates")
def repo_duplicates(
    threshold: Optional[float] = Query(default=None, ge=0.5, le=1.0),
    limit: int = Query(default=30, ge=1, le=200),
    repo: Repository = Depends(get_owned_repo), db: Session = Depends(get_db),
):
    """Static whole-repository duplicate scan (no LLM involved)."""
    if repo.status != "ready":
        raise RepoNotReadyError(f"Repository is not ready (status: {repo.status}).")
    rvi = get_index_store().get(db, repo.id)
    if rvi is None:
        raise RepoNotReadyError("The repository's search index is missing. Please re-index the repository.")
    return scan_repository(rvi, threshold or get_settings().near_duplicate_threshold, limit)


# ------------------------------------------------------------------ querying
@repo_router.post("/{repo_id}/query", response_model=QueryResponse)
def query_repo(body: QueryRequest, repo: Repository = Depends(get_owned_repo),
               user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    row = answer_question(db, user, repo, body)
    extra = getattr(row, "_extra", {})
    return QueryResponse(
        id=row.id, conversation_id=row.conversation_id, repo_id=row.repo_id, mode=row.mode, question=row.question,
        answer=row.answer, sub_queries=row.sub_queries, citations=row.citations, sources=row.sources,
        dedupe_stats=extra.get("dedupe_stats", {}), removed_citations=extra.get("removed_citations", 0),
        timings_ms=extra.get("timings_ms", {}), llm_provider=row.llm_provider, llm_model=row.llm_model,
        latency_ms=row.latency_ms, created_at=row.created_at,
    )


@repo_router.get("/{repo_id}/history", response_model=List[HistoryItem])
def repo_history(
    conversation_id: Optional[uuid.UUID] = None, limit: int = Query(default=50, ge=1, le=200),
    repo: Repository = Depends(get_owned_repo), user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    q = select(QueryHistory).where(QueryHistory.repo_id == repo.id, QueryHistory.user_id == user.id)
    if conversation_id:
        q = q.where(QueryHistory.conversation_id == conversation_id).order_by(QueryHistory.created_at.asc())
    else:
        q = q.order_by(QueryHistory.created_at.desc())
    return db.execute(q.limit(limit)).scalars().all()


@repo_router.get("/{repo_id}/conversations", response_model=List[ConversationSummary])
def repo_conversations(
    limit: int = Query(default=30, ge=1, le=100),
    repo: Repository = Depends(get_owned_repo), user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    rows = db.execute(
        select(QueryHistory.conversation_id, QueryHistory.question, QueryHistory.created_at)
        .where(QueryHistory.repo_id == repo.id, QueryHistory.user_id == user.id)
        .order_by(QueryHistory.created_at.asc())
    ).all()
    convs: dict = {}
    for cid, question, created in rows:
        c = convs.setdefault(cid, {"conversation_id": cid, "title": question[:80], "last_activity": created, "messages": 0})
        c["messages"] += 1
        c["last_activity"] = max(c["last_activity"], created)
    out = sorted(convs.values(), key=lambda c: c["last_activity"], reverse=True)[:limit]
    return [ConversationSummary(**c) for c in out]


# ------------------------------------------------------------------ meta
@meta_router.get("/llm/providers", response_model=List[ProviderInfo])
def llm_providers(_: User = Depends(get_current_user)):
    return list_providers()
