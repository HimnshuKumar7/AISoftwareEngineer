"""
Test suite verifying:
1. Memory monitoring utility
2. PyTorch single-thread and low-overhead embedder configuration
3. Chunk streaming without full repository RAM accumulation
4. Incremental FAISS index building in small batches
5. FAISS index memory unloading and bounded LRU cache
6. Concurrency lock protecting against simultaneous indexing jobs
7. End-to-end query workflow
"""
import os
import shutil
import tempfile
import threading
from pathlib import Path

# Ensure test runs with memory-safe env variables and test sqlite db
os.environ["DATABASE_URL"] = "sqlite:///./test_memory_db.sqlite"
os.environ["WEB_CONCURRENCY"] = "1"
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["TORCH_NUM_THREADS"] = "1"
os.environ["INDEXING_BATCH_SIZE"] = "4"
os.environ["FAISS_CACHE_MAX_SIZE"] = "1"

from app.config import settings
from app.embeddings.embedder import get_embedder
from app.ingestion.parser import CodeChunk, stream_chunk_batches
from app.utils.memory import get_memory_info, log_memory, force_garbage_collection
from app.vectorstore.faiss_store import (
    build_index,
    load_index,
    search,
    unload_index,
    get_loaded_index_ids,
    index_exists,
)


def test_memory_utils():
    mem = get_memory_info()
    assert "rss_mb" in mem
    assert isinstance(mem["rss_mb"], (int, float))
    assert mem["rss_mb"] > 0

    logged = log_memory("Unit test memory check")
    assert "rss_mb" in logged
    assert logged["rss_mb"] > 0

    after_gc = force_garbage_collection("Unit test GC")
    assert "rss_mb" in after_gc


def test_embedder_configuration():
    import torch
    embedder = get_embedder()
    assert embedder is not None
    # PyTorch threads should be set to 1
    assert torch.get_num_threads() == 1


def test_streaming_and_batch_faiss():
    # Create a temporary directory with simulated code files
    temp_dir = tempfile.mkdtemp()
    try:
        repo_path = Path(temp_dir)
        # Create 10 sample python files with functions
        for i in range(10):
            p = repo_path / f"module_{i}.py"
            p.write_text(f"""
def function_{i}(x, y):
    '''Function {i} documentation.'''
    return x + y + {i}

class Class_{i}:
    def method_{i}(self):
        return {i}
""", encoding="utf-8")

        # Stream chunk batches with batch_size=4
        batches = list(stream_chunk_batches(repo_path, batch_size=4))
        assert len(batches) >= 2
        total_chunks = sum(len(b) for b in batches)
        assert total_chunks >= 20

        # Build index with streaming batches
        test_repo_id = "test_repo_mem_123"
        indexed_count = build_index(test_repo_id, stream_chunk_batches(repo_path, batch_size=4))
        assert indexed_count == total_chunks
        assert index_exists(test_repo_id)

        # Build_index must have unloaded the index from cache to save RAM!
        assert test_repo_id not in get_loaded_index_ids()

        # Query the index: load_index should load it on demand
        results = search(test_repo_id, "function_3", k=3)
        assert len(results) > 0
        assert test_repo_id in get_loaded_index_ids()

        # Unload explicitly
        unload_index(test_repo_id)
        assert test_repo_id not in get_loaded_index_ids()

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
        # Clean up test index
        test_index_dir = Path(settings.DATA_DIR) / "indexes" / "test_repo_mem_123"
        if test_index_dir.exists():
            shutil.rmtree(test_index_dir, ignore_errors=True)


def test_faiss_lru_cache_eviction():
    # Verify that FAISS cache honors max capacity = 1
    test_repo_1 = "test_lru_repo_1"
    test_repo_2 = "test_lru_repo_2"

    dummy_chunks_1 = [
        CodeChunk(
            file_path="a.py",
            start_line=1,
            end_line=5,
            symbol="func_a",
            node_type="function_definition",
            text="def func_a(): pass",
        )
    ]
    dummy_chunks_2 = [
        CodeChunk(
            file_path="b.py",
            start_line=1,
            end_line=5,
            symbol="func_b",
            node_type="function_definition",
            text="def func_b(): pass",
        )
    ]

    try:
        build_index(test_repo_1, dummy_chunks_1)
        build_index(test_repo_2, dummy_chunks_2)

        # Load repo 1
        load_index(test_repo_1)
        assert test_repo_1 in get_loaded_index_ids()

        # Load repo 2: since maxsize=1, repo 1 should be evicted!
        load_index(test_repo_2)
        assert test_repo_2 in get_loaded_index_ids()
        assert test_repo_1 not in get_loaded_index_ids()
        assert len(get_loaded_index_ids()) <= 1

    finally:
        unload_index(None)
        for rid in [test_repo_1, test_repo_2]:
            p = Path(settings.DATA_DIR) / "indexes" / rid
            if p.exists():
                shutil.rmtree(p, ignore_errors=True)


def test_concurrency_lock():
    from app.main import _INDEXING_LOCK

    # Test lock behavior
    assert not _INDEXING_LOCK.locked()
    acquired = _INDEXING_LOCK.acquire(blocking=False)
    assert acquired is True

    # Second concurrent acquire should fail immediately (non-blocking)
    second_acquire = _INDEXING_LOCK.acquire(blocking=False)
    assert second_acquire is False

    _INDEXING_LOCK.release()
    assert not _INDEXING_LOCK.locked()


if __name__ == "__main__":
    try:
        print("--> Running test_memory_utils...")
        test_memory_utils()
        print("✓ test_memory_utils passed!")

        print("--> Running test_embedder_configuration...")
        test_embedder_configuration()
        print("✓ test_embedder_configuration passed!")

        print("--> Running test_streaming_and_batch_faiss...")
        test_streaming_and_batch_faiss()
        print("✓ test_streaming_and_batch_faiss passed!")

        print("--> Running test_faiss_lru_cache_eviction...")
        test_faiss_lru_cache_eviction()
        print("✓ test_faiss_lru_cache_eviction passed!")

        print("--> Running test_concurrency_lock...")
        test_concurrency_lock()
        print("✓ test_concurrency_lock passed!")

        print("\n==========================================")
        print("ALL MEMORY AND WORKFLOW TESTS PASSED!")
        print("==========================================")
    finally:
        db_file = Path("test_memory_db.sqlite")
        if db_file.exists():
            db_file.unlink(missing_ok=True)
