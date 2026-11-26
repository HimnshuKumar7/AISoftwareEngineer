"""Embedding generation: Sentence-Transformers MiniLM only, independent of the LLM provider.

The model is loaded lazily (so the API boots fast and idle memory stays low) and shared process-wide.
Vectors are L2-normalised, so inner product in FAISS equals cosine similarity.
"""
from __future__ import annotations

import logging
import os
import threading
from pathlib import Path
from typing import List, Optional, Sequence

import numpy as np

from app.core.config import EMBEDDING_DIM, EMBEDDING_MODEL_NAME, get_settings

log = logging.getLogger(__name__)


class Embedder:
    def __init__(self, model_name: str = EMBEDDING_MODEL_NAME, cache_dir: Optional[str] = None):
        self.model_name = model_name
        self.cache_dir = cache_dir
        self._model = None
        self._lock = threading.Lock()

    @property
    def dim(self) -> int:
        return EMBEDDING_DIM

    def _load(self):
        if self._model is None:
            with self._lock:
                if self._model is None:
                    import torch
                    from sentence_transformers import SentenceTransformer

                    torch.set_num_threads(max(1, min(2, os.cpu_count() or 1)))
                    cache = str(Path(self.cache_dir).resolve()) if self.cache_dir else None
                    log.info("Loading embedding model %s (cache=%s)", self.model_name, cache)
                    # The Docker image downloads MiniLM at build time.  Runtime instances
                    # must use that cache instead of making Hugging Face network requests:
                    # free Render services can lose outbound connectivity or restart while
                    # an index job is waiting for the Hub.
                    self._model = SentenceTransformer(
                        self.model_name,
                        device="cpu",
                        cache_folder=cache,
                        local_files_only=True,
                    )
                    self._model.max_seq_length = 256  # MiniLM's trained maximum
                    got = self._model.get_embedding_dimension()
                    if got != EMBEDDING_DIM:
                        raise RuntimeError(f"Unexpected embedding dim {got}, expected {EMBEDDING_DIM}")
        return self._model

    def encode(self, texts: Sequence[str], batch_size: int = 16) -> np.ndarray:
        """Return a float32 array of shape (len(texts), 384), L2-normalised."""
        if not texts:
            return np.zeros((0, EMBEDDING_DIM), dtype=np.float32)
        model = self._load()
        with self._lock:  # one encode at a time keeps peak memory predictable on small instances
            vecs = model.encode(
                list(texts), batch_size=batch_size, convert_to_numpy=True,
                normalize_embeddings=True, show_progress_bar=False,
            )
        return np.ascontiguousarray(vecs, dtype=np.float32)

    def encode_query(self, text: str) -> np.ndarray:
        return self.encode([text], batch_size=1)[0]


_embedder: Optional[Embedder] = None
_embedder_lock = threading.Lock()


def get_embedder() -> Embedder:
    global _embedder
    if _embedder is None:
        with _embedder_lock:
            if _embedder is None:
                _embedder = Embedder(cache_dir=get_settings().model_cache_dir)
    return _embedder
