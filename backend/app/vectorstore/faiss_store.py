"""Per-repo FAISS index: build once at index-time, load + search at query-time."""
from pathlib import Path

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document

from app.config import settings
from app.embeddings.embedder import get_embedder
from app.ingestion.parser import CodeChunk

_LOADED_CACHE: dict[str, FAISS] = {}


def _index_path(repo_id: str) -> Path:
    return Path(settings.DATA_DIR) / "indexes" / repo_id


def build_index(repo_id: str, chunks: list[CodeChunk]) -> int:
    docs = [
        Document(
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
        for c in chunks
    ]
    store = FAISS.from_documents(docs, get_embedder())
    path = _index_path(repo_id)
    path.mkdir(parents=True, exist_ok=True)
    store.save_local(str(path))
    _LOADED_CACHE[repo_id] = store
    return len(docs)


def load_index(repo_id: str) -> FAISS | None:
    if repo_id in _LOADED_CACHE:
        return _LOADED_CACHE[repo_id]
    path = _index_path(repo_id)
    if not path.exists():
        return None
    store = FAISS.load_local(
        str(path), get_embedder(), allow_dangerous_deserialization=True
    )
    _LOADED_CACHE[repo_id] = store
    return store


def index_exists(repo_id: str) -> bool:
    return _index_path(repo_id).exists()


def search(repo_id: str, query: str, k: int | None = None) -> list[Document]:
    store = load_index(repo_id)
    if store is None:
        return []
    return store.similarity_search(query, k=k or settings.TOP_K)
