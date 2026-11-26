"""Per-repository FAISS indexes with remote persistence.

Isolation: one `RepoVectorIndex` per repository id. Nothing ever searches across repositories; the
only way to reach an index is through `IndexStore.get(session, repo_id)`, and API handlers verify
repository ownership before calling it.

Persistence: Render's filesystem is ephemeral, so the serialized FAISS index and chunk metadata are
stored in the `repo_indexes` table (Neon PostgreSQL). A small in-process LRU keeps hot indexes in
RAM; freshness is checked with one tiny `updated_at` query per lookup, which also keeps multiple
instances consistent.
"""
from __future__ import annotations

import gzip
import json
import logging
import threading
import uuid
from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Sequence, Tuple

import faiss
import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import EMBEDDING_DIM, EMBEDDING_MODEL_NAME, get_settings
from app.db.models import RepoIndex
from app.ingestion.chunker import CodeChunk

log = logging.getLogger(__name__)


class RepoVectorIndex:
    """Exact cosine-similarity index (IndexFlatIP over L2-normalised MiniLM vectors)."""

    def __init__(self, index: faiss.Index, chunks: List[CodeChunk]):
        if index.d != EMBEDDING_DIM:
            raise ValueError(f"index dim {index.d} != {EMBEDDING_DIM}")
        if index.ntotal != len(chunks):
            raise ValueError("index/chunk count mismatch")
        self.index = index
        self.chunks = chunks

    @classmethod
    def build(cls, vectors: np.ndarray, chunks: Sequence[CodeChunk]) -> "RepoVectorIndex":
        if vectors.shape != (len(chunks), EMBEDDING_DIM):
            raise ValueError(f"vectors shape {vectors.shape} does not match {len(chunks)} chunks")
        index = faiss.IndexFlatIP(EMBEDDING_DIM)
        index.add(np.ascontiguousarray(vectors, dtype=np.float32))
        return cls(index, list(chunks))

    def __len__(self) -> int:
        return len(self.chunks)

    def search(self, query_vec: np.ndarray, k: int) -> List[Tuple[int, float]]:
        if len(self) == 0:
            return []
        k = max(1, min(k, len(self)))
        q = np.ascontiguousarray(query_vec.reshape(1, -1), dtype=np.float32)
        scores, ids = self.index.search(q, k)
        return [(int(i), float(s)) for i, s in zip(ids[0], scores[0]) if i >= 0]

    def vectors(self) -> np.ndarray:
        return self.index.reconstruct_n(0, self.index.ntotal)

    # --- serialisation ---------------------------------------------------------------
    def to_blobs(self) -> Tuple[bytes, bytes]:
        faiss_blob = faiss.serialize_index(self.index).tobytes()
        payload = json.dumps([c.to_dict() for c in self.chunks], separators=(",", ":")).encode("utf-8")
        return faiss_blob, gzip.compress(payload, compresslevel=6)

    @classmethod
    def from_blobs(cls, faiss_blob: bytes, chunks_blob: bytes) -> "RepoVectorIndex":
        index = faiss.deserialize_index(np.frombuffer(faiss_blob, dtype=np.uint8))
        chunks = [CodeChunk.from_dict(d) for d in json.loads(gzip.decompress(chunks_blob).decode("utf-8"))]
        return cls(index, chunks)


@dataclass
class _CacheEntry:
    version: Optional[datetime]
    value: RepoVectorIndex


class IndexStore:
    def __init__(self, cache_size: int = 2):
        self._cache: "OrderedDict[uuid.UUID, _CacheEntry]" = OrderedDict()
        self._cache_size = max(1, cache_size)
        self._lock = threading.Lock()

    def save(self, session: Session, repo_id: uuid.UUID, idx: RepoVectorIndex) -> None:
        faiss_blob, chunks_blob = idx.to_blobs()
        row = session.get(RepoIndex, repo_id)
        if row is None:
            row = RepoIndex(repo_id=repo_id, faiss_blob=faiss_blob, chunks_blob=chunks_blob,
                            chunk_count=len(idx), embedding_model=EMBEDDING_MODEL_NAME, dim=EMBEDDING_DIM)
            session.add(row)
        else:
            row.faiss_blob = faiss_blob
            row.chunks_blob = chunks_blob
            row.chunk_count = len(idx)
            row.embedding_model = EMBEDDING_MODEL_NAME
            row.dim = EMBEDDING_DIM
        session.flush()
        log.info("Persisted index for repo %s: %d chunks, %.1f KB faiss, %.1f KB chunks",
                 repo_id, len(idx), len(faiss_blob) / 1024, len(chunks_blob) / 1024)
        self.invalidate(repo_id)

    def get(self, session: Session, repo_id: uuid.UUID) -> Optional[RepoVectorIndex]:
        version = session.execute(select(RepoIndex.updated_at).where(RepoIndex.repo_id == repo_id)).scalar_one_or_none()
        if version is None:  # no persisted index (never built, or repository deleted)
            self.invalidate(repo_id)
            return None
        with self._lock:
            hit = self._cache.get(repo_id)
            if hit is not None and hit.version == version:
                self._cache.move_to_end(repo_id)
                return hit.value
        row = session.execute(
            select(RepoIndex.faiss_blob, RepoIndex.chunks_blob, RepoIndex.updated_at).where(RepoIndex.repo_id == repo_id)
        ).one_or_none()
        if row is None:
            return None
        idx = RepoVectorIndex.from_blobs(row.faiss_blob, row.chunks_blob)
        with self._lock:
            self._cache[repo_id] = _CacheEntry(row.updated_at, idx)
            self._cache.move_to_end(repo_id)
            while len(self._cache) > self._cache_size:
                evicted, _ = self._cache.popitem(last=False)
                log.debug("Evicted index %s from memory cache", evicted)
        log.info("Loaded index for repo %s from database (%d chunks)", repo_id, len(idx))
        return idx

    def invalidate(self, repo_id: uuid.UUID) -> None:
        with self._lock:
            self._cache.pop(repo_id, None)


_store: Optional[IndexStore] = None


def get_index_store() -> IndexStore:
    global _store
    if _store is None:
        _store = IndexStore(cache_size=get_settings().index_cache_size)
    return _store
