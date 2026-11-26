"""Pre-download the MiniLM embedding model at build time so the runtime never needs Hugging Face.

Usage (Render build step / Docker build):  python -m app.scripts.download_model
"""
from __future__ import annotations

import sys
from pathlib import Path

from app.core.config import EMBEDDING_DIM, EMBEDDING_MODEL_NAME, get_settings


def main() -> int:
    from sentence_transformers import SentenceTransformer

    cache = Path(get_settings().model_cache_dir).resolve()
    cache.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {EMBEDDING_MODEL_NAME} into {cache} ...")
    model = SentenceTransformer(EMBEDDING_MODEL_NAME, device="cpu", cache_folder=str(cache))
    dim = model.get_sentence_embedding_dimension()
    vec = model.encode(["def hello(): pass"], normalize_embeddings=True)
    assert dim == EMBEDDING_DIM and vec.shape == (1, EMBEDDING_DIM), f"unexpected model output {vec.shape}"
    print(f"OK: dim={dim}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
