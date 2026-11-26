"""Test configuration.

TEST DOUBLES (tests only, never imported by app code):
  * HashingEmbedder - deterministic lexical-hash vectors with the same shape/normalisation contract as the
    MiniLM embedder. Needed because the CI sandbox cannot download the real model. The real
    Sentence-Transformers path is exercised by tests/test_real_embedder.py when weights are available.
  * ScriptedLLM    - a fake LLM provider that returns canned planning/answer text.
"""
import json
import math
import os
import re
import tempfile
from hashlib import md5
from typing import Dict, List

import numpy as np
import pytest

_TMP = tempfile.mkdtemp(prefix="ase-tests-")
os.environ.update(
    DATABASE_URL=f"sqlite:///{_TMP}/test.db",
    JWT_SECRET="test-secret-" + "x" * 40,
    ENVIRONMENT="test",
    DATA_DIR=f"{_TMP}/data",
    CORS_ORIGINS="http://localhost:5173,https://app.example.com",
    CORS_ORIGIN_REGEX=r"https://app-.*\.vercel\.app",
    LOG_LEVEL="WARNING",
    LLM_PROVIDER="groq",
    GROQ_API_KEY="test-key",
)

from app.core.config import EMBEDDING_DIM, get_settings  # noqa: E402
from app.ingestion import embedder as embedder_module  # noqa: E402
from app.llm.base import LLMProvider  # noqa: E402

_WORD = re.compile(r"[A-Z]+(?![a-z])|[A-Z]?[a-z]+|\d+")


class HashingEmbedder:
    """TEST DOUBLE: signed feature hashing of identifier sub-words -> 384-d L2-normalised vectors."""

    dim = EMBEDDING_DIM

    def encode(self, texts, batch_size: int = 16) -> np.ndarray:
        out = np.zeros((len(texts), EMBEDDING_DIM), dtype=np.float32)
        for r, text in enumerate(texts):
            counts: Dict[str, int] = {}
            for w in _WORD.findall(text):
                counts[w.lower()] = counts.get(w.lower(), 0) + 1
            for w, c in counts.items():
                h = int(md5(w.encode()).hexdigest(), 16)
                out[r, h % EMBEDDING_DIM] += (1.0 if (h >> 100) & 1 else -1.0) * (1 + math.log(c))
            n = np.linalg.norm(out[r])
            if n:
                out[r] /= n
        return out

    def encode_query(self, text: str) -> np.ndarray:
        return self.encode([text])[0]


class ScriptedLLM(LLMProvider):
    """TEST DOUBLE: records calls; plans 3 sub-queries; answers citing Source 1 plus one fabricated citation."""

    name = "scripted"

    def __init__(self):
        super().__init__("scripted-1")
        self.calls: List[Dict] = []

    def _build_request(self, *a, **k):  # pragma: no cover - not used
        raise NotImplementedError

    def _parse_response(self, data):  # pragma: no cover - not used
        raise NotImplementedError

    def generate(self, system, messages, *, temperature=0.1, max_tokens=1800):
        self.calls.append({"system": system, "messages": messages, "max_tokens": max_tokens})
        last = messages[-1]["content"]
        if system.startswith("You are the query-planning stage"):
            q = last.strip()
            return json.dumps([q, f"{q} implementation details", "helper functions and utilities"])
        m = re.search(r"### Source 1: (\S+) lines (\d+)-(\d+)", last)
        if not m:
            return "No sources."
        path, a, b = m.group(1), int(m.group(2)), int(m.group(3))
        return (f"The relevant logic is in [{path}:{a}-{b}]. It is also touched at [{path}:{a}] and, "
                f"wrongly, [does/not/exist.py:1-9]. Mentioned list [1, 2] stays as is.")


@pytest.fixture(autouse=True)
def fake_embedder(monkeypatch):
    emb = HashingEmbedder()
    monkeypatch.setattr(embedder_module, "_embedder", emb)
    return emb


@pytest.fixture
def scripted_llm():
    return ScriptedLLM()


@pytest.fixture
def settings():
    return get_settings()
