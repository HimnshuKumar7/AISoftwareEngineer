"""Runs the RAG graph for one question and persists the result."""
from __future__ import annotations

import logging
import time
import uuid
from typing import Dict, List

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.schemas import QueryRequest
from app.core.config import get_settings
from app.core.errors import RepoNotReadyError
from app.db.models import QueryHistory, Repository, User
from app.ingestion.embedder import get_embedder
from app.ingestion.index_store import get_index_store
from app.llm.providers import get_llm
from app.rag.graph import run_rag

log = logging.getLogger(__name__)


def _load_history(db: Session, user_id: uuid.UUID, repo_id: uuid.UUID, conversation_id: uuid.UUID, turns: int) -> List[Dict[str, str]]:
    rows = db.execute(
        select(QueryHistory.question, QueryHistory.answer)
        .where(QueryHistory.user_id == user_id, QueryHistory.repo_id == repo_id,
               QueryHistory.conversation_id == conversation_id)
        .order_by(QueryHistory.created_at.desc()).limit(turns)
    ).all()
    msgs: List[Dict[str, str]] = []
    for q, a in reversed(rows):
        msgs.append({"role": "user", "content": q})
        msgs.append({"role": "assistant", "content": a})
    return msgs


def answer_question(db: Session, user: User, repo: Repository, req: QueryRequest) -> QueryHistory:
    settings = get_settings()
    if repo.status != "ready":
        raise RepoNotReadyError(f"Repository is not ready (status: {repo.status}). Wait for indexing to finish.")
    rvi = get_index_store().get(db, repo.id)
    if rvi is None:
        raise RepoNotReadyError("The repository's search index is missing. Please re-index the repository.")

    llm = get_llm(req.provider, req.model)  # validates provider configuration before any work
    conversation_id = req.conversation_id or uuid.uuid4()
    history = _load_history(db, user.id, repo.id, conversation_id, settings.history_turns)

    t0 = time.monotonic()
    state = run_rag(rvi, get_embedder(), llm, settings, question=req.question, mode=req.mode,
                    repo_name=f"{repo.owner}/{repo.name}", history=history)
    latency_ms = int((time.monotonic() - t0) * 1000)

    cited = {(c["path"], c["start_line"], c["end_line"]) for c in state.get("citations", [])}
    cited_ids = {c["chunk_id"] for c in state.get("citations", [])}
    sources = [
        {**{k: c[k] for k in ("chunk_id", "path", "start_line", "end_line", "kind", "name", "language", "score", "code")},
         "cited": c["chunk_id"] in cited_ids, "also_at": c.get("also_at", [])}
        for c in state.get("contexts", [])
    ]
    row = QueryHistory(
        user_id=user.id, repo_id=repo.id, conversation_id=conversation_id, mode=req.mode, question=req.question,
        answer=state["answer"], sub_queries=state.get("sub_queries", []), sources=sources,
        citations=state.get("citations", []), llm_provider=llm.name, llm_model=llm.model, latency_ms=latency_ms,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    # Attach transient fields for the response (not persisted).
    row._extra = {  # type: ignore[attr-defined]
        "dedupe_stats": state.get("dedupe_stats", {}), "removed_citations": state.get("removed_citations", 0),
        "timings_ms": state.get("timings", {}),
    }
    log.info("query repo=%s mode=%s subq=%d ctx=%d cites=%d removed=%d latency=%dms", repo.id, req.mode,
             len(state.get("sub_queries", [])), len(sources), len(state.get("citations", [])),
             state.get("removed_citations", 0), latency_ms)
    return row
