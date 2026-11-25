"""
Local, CPU-friendly embeddings via sentence-transformers.
Optimized for low-RAM environments (e.g. Render 512MB RAM free/starter instances).
"""
import os
import threading
from functools import lru_cache

# Restrict multi-threading thread-pools that cause large memory allocations in PyTorch / BLAS
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("VECLIB_MAXIMUM_THREADS", "1")
os.environ.setdefault("NUMEXPR_NUM_THREADS", "1")
os.environ.setdefault("TORCH_NUM_THREADS", "1")

try:
    import torch
    torch.set_num_threads(1)
    if hasattr(torch, "set_num_interop_threads"):
        try:
            torch.set_num_interop_threads(1)
        except RuntimeError:
            pass  # Already set or initialized
    torch.set_grad_enabled(False)
except ImportError:
    pass

from langchain_huggingface import HuggingFaceEmbeddings

from app.config import settings
from app.utils.memory import log_memory

_EMBEDDER_LOCK = threading.Lock()
_EMBEDDER_INSTANCE: HuggingFaceEmbeddings | None = None


def get_embedder() -> HuggingFaceEmbeddings:
    """
    Thread-safe lazy singleton loader for sentence-transformers embedding model.
    Configures low-overhead CPU execution and small batch encoding.
    """
    global _EMBEDDER_INSTANCE
    if _EMBEDDER_INSTANCE is None:
        with _EMBEDDER_LOCK:
            if _EMBEDDER_INSTANCE is None:
                log_memory("Before loading embedding model")
                _EMBEDDER_INSTANCE = HuggingFaceEmbeddings(
                    model_name=settings.EMBEDDING_MODEL,
                    model_kwargs={"device": "cpu"},
                    encode_kwargs={
                        "batch_size": settings.EMBEDDING_BATCH_SIZE,
                        "normalize_embeddings": True,
                    },
                )
                log_memory("After loading embedding model")
    return _EMBEDDER_INSTANCE
