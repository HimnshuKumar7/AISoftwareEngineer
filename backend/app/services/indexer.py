"""Background indexing pipeline: clone -> parse (Tree-sitter) -> embed (MiniLM) -> FAISS -> persist.

Jobs run on a single worker thread so that at most one clone/embedding job holds memory at a time
(important on Render's 512 MB free tier). Status is written to the repositories row after every
stage so the frontend can poll it.
"""
from __future__ import annotations

import logging
import shutil
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import List

from sqlalchemy import select, update

from app.core.config import get_settings
from app.core.errors import IngestionError
from app.db.models import REPO_ACTIVE_STATUSES, Repository
from app.db.session import session_scope
from app.ingestion.chunker import CodeChunk, chunk_files
from app.ingestion.embedder import get_embedder
from app.ingestion.github import clone_repo, parse_github_url
from app.ingestion.index_store import RepoVectorIndex, get_index_store
from app.ingestion.walker import WalkStats, walk_repo

log = logging.getLogger(__name__)

_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="indexer")
_inflight: set[uuid.UUID] = set()
_inflight_lock = threading.Lock()


def _set_status(repo_id: uuid.UUID, status: str, message: str | None = None, progress: int | None = None, **extra) -> None:
    values = {"status": status, "status_message": message, **extra}
    if progress is not None:
        values["progress"] = progress
    with session_scope() as s:
        s.execute(update(Repository).where(Repository.id == repo_id).values(**values))


def submit_index_job(repo_id: uuid.UUID) -> bool:
    """Queue an indexing job. Returns False if one is already queued/running for this repo."""
    with _inflight_lock:
        if repo_id in _inflight:
            return False
        _inflight.add(repo_id)
    _executor.submit(_run_job, repo_id)
    return True


def recover_interrupted_jobs() -> int:
    """On boot, any repo left in an active state was interrupted by a restart/redeploy."""
    with session_scope() as s:
        res = s.execute(
            update(Repository)
            .where(Repository.status.in_(REPO_ACTIVE_STATUSES))
            .values(status="failed", status_message="Indexing was interrupted by a server restart. Click re-index to retry.")
        )
        return res.rowcount or 0


def _run_job(repo_id: uuid.UUID) -> None:
    settings = get_settings()
    workdir = settings.data_path / "clones" / str(repo_id)
    t0 = time.monotonic()
    try:
        with session_scope() as s:
            repo = s.get(Repository, repo_id)
            if repo is None:
                return
            owner, name, branch = repo.owner, repo.name, repo.branch
        ref = parse_github_url(f"https://github.com/{owner}/{name}", branch)

        _set_status(repo_id, "cloning", "Cloning repository from GitHub", 5)
        sha = clone_repo(ref, workdir, settings.clone_timeout_seconds, settings.max_repo_size_mb)

        _set_status(repo_id, "parsing", "Parsing source files with Tree-sitter", 20, commit_sha=sha)
        stats = WalkStats()
        files = walk_repo(workdir, settings.max_files_per_repo, settings.max_file_size_kb, stats)
        chunks: List[CodeChunk] = []
        for chunk in chunk_files(files, max_lines=settings.max_chunk_lines):
            chunks.append(chunk)
            if len(chunks) >= settings.max_chunks_per_repo:
                stats.truncated = True
                break
        shutil.rmtree(workdir, ignore_errors=True)  # free disk/RAM before embedding
        if not chunks:
            raise IngestionError("No supported source files were found in this repository.")
        log.info("repo=%s parsed files=%d chunks=%d truncated=%s", repo_id, stats.files_indexed, len(chunks), stats.truncated)

        _set_status(repo_id, "embedding", f"Embedding {len(chunks)} code chunks", 35,
                    file_count=stats.files_indexed, chunk_count=len(chunks), languages=stats.languages)
        embedder = get_embedder()
        texts = [c.embedding_text() for c in chunks]
        batch = settings.embedding_batch_size
        parts = []
        for i in range(0, len(texts), batch * 8):
            parts.append(embedder.encode(texts[i:i + batch * 8], batch_size=batch))
            pct = 35 + int(50 * min(i + batch * 8, len(texts)) / len(texts))
            _set_status(repo_id, "embedding", f"Embedding {len(chunks)} code chunks", pct)
        import numpy as np

        vectors = np.vstack(parts)

        _set_status(repo_id, "indexing", "Building and persisting FAISS index", 90)
        idx = RepoVectorIndex.build(vectors, chunks)
        with session_scope() as s:
            get_index_store().save(s, repo_id, idx)

        note = "Index truncated at the configured file/chunk limits." if stats.truncated else None
        _set_status(repo_id, "ready", note, 100, indexed_at=datetime.now(timezone.utc))
        log.info("repo=%s indexed in %.1fs", repo_id, time.monotonic() - t0)
    except IngestionError as e:
        log.warning("repo=%s ingestion failed: %s", repo_id, e.message)
        _set_status(repo_id, "failed", e.message)
    except Exception as e:  # noqa: BLE001 - surface unexpected failures on the row, log full trace
        log.exception("repo=%s unexpected indexing failure", repo_id)
        _set_status(repo_id, "failed", f"Unexpected error while indexing: {type(e).__name__}")
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
        with _inflight_lock:
            _inflight.discard(repo_id)
