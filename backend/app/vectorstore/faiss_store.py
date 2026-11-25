"""
Per-repo FAISS index with memory-safe batch building, bounded caching, and explicit cleanup.
Designed to prevent Out-Of-Memory (OOM) on memory-constrained platforms like Render (512MB RAM).
"""
import collections
import logging
from collections.abc import Iterable
from pathlib import Path

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document

from app.config import settings
from app.embeddings.embedder import get_embedder
from app.ingestion.parser import CodeChunk
from app.utils.memory import (
    force_garbage_collection,
    log_memory,
    check_and_enforce_memory_limit,
    MemoryLimitExceeded,
)

logger = logging.getLogger(__name__)

# Bounded LRU cache: maps repo_id -> FAISS index
# Keeps at most settings.FAISS_CACHE_MAX_SIZE (default: 1) index in RAM at any given time.
_LOADED_CACHE: collections.OrderedDict[str, FAISS] = collections.OrderedDict()


def _index_path(repo_id: str) -> Path:
    return Path(settings.DATA_DIR) / "indexes" / repo_id


def chunk_to_document(c: CodeChunk) -> Document:
    return Document(
        page_content=f"# {c.file_path} :: {c.symbol or c.node_type} "
                      f"(lines {c.start_line}-{c.end_line})\n{c.text}",
        metadata={
            "file_path": c.file_path,
            "start_line": c.start_line,
            "end_line": c.end_line,
            "symbol": c.symbol or "",
            "node_type": c.node_type,
        },
    )


def _batch_items(iterable: Iterable, batch_size: int):
    """Yield items grouped in chunks of batch_size without loading all into memory."""
    batch = []
    for item in iterable:
        batch.append(item)
        if len(batch) >= batch_size:
            yield batch
            batch = []
    if batch:
        yield batch


def build_index(repo_id: str, chunks: Iterable[CodeChunk] | Iterable[list[CodeChunk]]) -> int:
    """
    Builds a FAISS index incrementally in small batches, saving to disk and immediately
    releasing memory to avoid full-repository accumulation and OOM crashes.
    """
    log_memory(f"Starting build_index for {repo_id}")
    embedder = get_embedder()
    store: FAISS | None = None
    total_chunks = 0
    batch_size = max(1, settings.INDEXING_BATCH_SIZE)

    # Determine whether chunks are already batched or raw individual chunks
    chunk_iter = iter(chunks)
    first_item = None
    try:
        first_item = next(chunk_iter)
    except StopIteration:
        return 0

    if isinstance(first_item, list):
        # Already batched
        def _chain_batches():
            yield first_item
            for b in chunk_iter:
                yield b
        batches_iterable = _chain_batches()
    else:
        # Stream of individual chunks: batch them on the fly
        def _chain_first():
            yield first_item
            for item in chunk_iter:
                yield item

        batches_iterable = _batch_items(_chain_first(), batch_size)

    for batch_num, batch in enumerate(batches_iterable, start=1):
        if not batch:
            continue

        # Active Memory Guard: protect against Render 512MB RAM ceiling
        try:
            check_and_enforce_memory_limit(
                threshold_mb=settings.MAX_PROCESS_MEMORY_MB,
                action=f"batch {batch_num} for {repo_id}",
            )
        except MemoryLimitExceeded as e:
            logger.warning(f"Memory threshold safety limit triggered: {e}")
            if store is not None and total_chunks > 0:
                logger.info(f"Safely finalizing {total_chunks} indexed chunks to disk before halting.")
                break
            raise

        # Safety Cap on total chunks: prevent giant repos from exhausting memory
        if total_chunks >= settings.MAX_REPO_CHUNKS:
            logger.warning(
                f"Repository reached maximum safety chunk limit ({settings.MAX_REPO_CHUNKS} chunks). "
                f"Finalizing index to protect container memory."
            )
            break

        batch_docs = [chunk_to_document(c) for c in batch]
        count = len(batch_docs)
        total_chunks += count

        if store is None:
            # Initialize FAISS with the first batch of documents
            store = FAISS.from_documents(batch_docs, embedder)
        else:
            # Add subsequent batches incrementally
            store.add_documents(batch_docs)

        # Free batch documents immediately and run garbage collection
        del batch_docs
        del batch

        if batch_num % 3 == 0:
            force_garbage_collection(f"Batch {batch_num} indexed ({total_chunks} chunks)")

    if store is None or total_chunks == 0:
        return 0

    # Save index to disk
    path = _index_path(repo_id)
    path.mkdir(parents=True, exist_ok=True)
    store.save_local(str(path))
    log_memory(f"FAISS index saved to disk for {repo_id} ({total_chunks} chunks)")

    # Crucial: Unload store from memory immediately after saving to disk
    # This prevents keeping both the C++ index and Python docstore in RAM after indexing
    del store
    unload_index(repo_id)
    force_garbage_collection(f"Post build_index cleanup for {repo_id}")

    return total_chunks


def load_index(repo_id: str) -> FAISS | None:
    """
    Loads a FAISS index with bounded LRU memory management.
    Ensures at most settings.FAISS_CACHE_MAX_SIZE (default 1) indexes stay in RAM.
    """
    global _LOADED_CACHE
    if repo_id in _LOADED_CACHE:
        # Move to end (most recently used)
        _LOADED_CACHE.move_to_end(repo_id)
        return _LOADED_CACHE[repo_id]

    path = _index_path(repo_id)
    if not path.exists():
        return None

    # Enforce cache capacity limit before loading new index
    max_size = max(1, settings.FAISS_CACHE_MAX_SIZE)
    while len(_LOADED_CACHE) >= max_size:
        oldest_repo, oldest_store = _LOADED_CACHE.popitem(last=False)
        logger.info(f"Evicting FAISS index '{oldest_repo}' from cache to protect RAM.")
        del oldest_store
        force_garbage_collection(f"Evicted index {oldest_repo}")

    log_memory(f"Loading FAISS index from disk for {repo_id}")
    store = FAISS.load_local(
        str(path), get_embedder(), allow_dangerous_deserialization=True
    )
    _LOADED_CACHE[repo_id] = store
    log_memory(f"FAISS index loaded for {repo_id}")
    return store


def unload_index(repo_id: str | None = None) -> None:
    """
    Explicitly removes an index (or all indexes if repo_id is None) from RAM and runs GC.
    """
    global _LOADED_CACHE
    if repo_id is not None:
        if repo_id in _LOADED_CACHE:
            store = _LOADED_CACHE.pop(repo_id)
            del store
            force_garbage_collection(f"Unloaded index {repo_id}")
    else:
        while _LOADED_CACHE:
            _, store = _LOADED_CACHE.popitem()
            del store
        force_garbage_collection("Cleared all loaded FAISS indexes")


def get_loaded_index_ids() -> list[str]:
    """Returns the list of repo IDs currently loaded in memory."""
    return list(_LOADED_CACHE.keys())


def index_exists(repo_id: str) -> bool:
    return _index_path(repo_id).exists()


def search(repo_id: str, query: str, k: int | None = None) -> list[Document]:
    """
    Searches the FAISS index for relevant documents using Max Marginal Relevance (MMR).
    """
    check_and_enforce_memory_limit(
        threshold_mb=settings.MAX_PROCESS_MEMORY_MB,
        action=f"search in {repo_id}",
    )
    store = load_index(repo_id)
    if store is None:
        return []
    results = store.max_marginal_relevance_search(
        query,
        k=k or settings.TOP_K,
        fetch_k=min(30, (k or settings.TOP_K) * 4),  # Bounded candidate fetch
        lambda_mult=0.7,
    )
    return results
