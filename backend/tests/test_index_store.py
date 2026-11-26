"""FAISS index persistence (remote, DB-backed) and per-repository isolation."""
import uuid

import numpy as np
import pytest

from app.db.models import RepoIndex, Repository, User
from app.db.session import init_db, session_scope
from app.ingestion.chunker import chunk_source
from app.ingestion.index_store import IndexStore, RepoVectorIndex
from tests.sample_repo import build_index


@pytest.fixture
def db():
    init_db()
    with session_scope() as s:
        yield s


def _make_repo(db, name):
    user = User(email=f"{uuid.uuid4().hex[:8]}@t.dev", password_hash="x")
    db.add(user)
    db.flush()
    repo = Repository(user_id=user.id, url=f"https://github.com/o/{name}", owner="o", name=name)
    db.add(repo)
    db.flush()
    return repo


def test_roundtrip_and_restart_survival(db, fake_embedder):
    idx, chunks = build_index(fake_embedder)
    repo = _make_repo(db, "a")
    store = IndexStore()
    store.save(db, repo.id, idx)
    db.commit()

    # Simulate a Render restart/redeploy: brand-new process => empty in-memory cache, only the DB remains.
    fresh = IndexStore()
    loaded = fresh.get(db, repo.id)
    assert loaded is not None and len(loaded) == len(chunks)
    assert [c.to_dict() for c in loaded.chunks] == [c.to_dict() for c in chunks]

    q = fake_embedder.encode_query("verify the jwt token signature")
    assert loaded.search(q, 3) == idx.search(q, 3)
    row = db.get(RepoIndex, repo.id)
    assert row.dim == 384 and row.embedding_model == "sentence-transformers/all-MiniLM-L6-v2"


def test_repositories_are_isolated(db, fake_embedder):
    idx_a, _ = build_index(fake_embedder)
    only_b = [c for c in idx_a.chunks if c.path.startswith("db/")]
    idx_b = RepoVectorIndex.build(fake_embedder.encode([c.embedding_text() for c in only_b]), only_b)

    ra, rb, rc = _make_repo(db, "a2"), _make_repo(db, "b2"), _make_repo(db, "c2")
    store = IndexStore()
    store.save(db, ra.id, idx_a)
    store.save(db, rb.id, idx_b)
    db.commit()

    got_b = store.get(db, rb.id)
    q = fake_embedder.encode_query("verify jwt token")           # best answer lives only in repo A
    paths_b = {got_b.chunks[i].path for i, _ in got_b.search(q, 50)}
    assert paths_b <= {"db/session.py"}                          # B can never surface A's files
    assert len(got_b) == len(only_b) < len(store.get(db, ra.id))
    assert store.get(db, rc.id) is None                          # repo without an index => None, not someone else's


def test_reindex_replaces_and_invalidates_cache(db, fake_embedder):
    idx, _ = build_index(fake_embedder)
    repo = _make_repo(db, "r")
    store = IndexStore()
    store.save(db, repo.id, idx)
    db.commit()
    first = store.get(db, repo.id)
    assert store.get(db, repo.id) is first                       # served from RAM

    small = chunk_source("x.py", b"def only():\n    value = 1\n    value += 2\n    value += 3\n    return value * 10\n")
    store.save(db, repo.id, RepoVectorIndex.build(fake_embedder.encode([c.embedding_text() for c in small]), small))
    db.commit()
    assert len(store.get(db, repo.id)) == len(small)


def test_lru_eviction(db, fake_embedder):
    idx, _ = build_index(fake_embedder)
    store = IndexStore(cache_size=2)
    repos = [_make_repo(db, f"lru{i}") for i in range(3)]
    for r in repos:
        store.save(db, r.id, idx)
    db.commit()
    for r in repos:
        store.get(db, r.id)
    assert len(store._cache) == 2 and repos[0].id not in store._cache


def test_dimension_and_count_validation(fake_embedder):
    idx, chunks = build_index(fake_embedder)
    with pytest.raises(ValueError):
        RepoVectorIndex.build(np.zeros((len(chunks) - 1, 384), dtype=np.float32), chunks)
    with pytest.raises(ValueError):
        RepoVectorIndex.build(np.zeros((len(chunks), 128), dtype=np.float32), chunks)
