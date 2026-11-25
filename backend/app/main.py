import threading
from concurrent.futures import ThreadPoolExecutor
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db, init_db
from app.ingestion.clone import clone_repo, iter_source_files
from app.ingestion.parser import parse_file_to_chunks, parse_and_split_file, stream_chunk_batches
from app.ingestion.chunker import split_oversized
from app.vectorstore.faiss_store import build_index, index_exists, get_loaded_index_ids, unload_index
from app.graph.graph import get_graph
from app.models import (
    IndexRepoRequest, IndexRepoResponse, RepoStatus,
    AskRequest, AskResponse, SourceChunk, FileActionRequest,
)
from app.auth.router import router as auth_router
from app.auth.deps import get_current_user
from app.auth.models import User, Repo, QueryHistory
from app.utils.memory import (
    get_memory_info,
    log_memory,
    force_garbage_collection,
    MemoryLimitExceeded,
)

# Concurrency lock to restrict indexing to exactly 1 concurrent job
# Protects against Render 512MB RAM OOM crashes caused by concurrent clone/parse/embed tasks
_INDEXING_LOCK = threading.Lock()

app = FastAPI(title="AI Software Engineer API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)


@app.on_event("startup")
def _on_startup():
    init_db()


@app.get("/api/health")
def health():
    mem = get_memory_info()
    return {
        "status": "ok",
        "llm_provider": settings.LLM_PROVIDER,
        "memory": {
            "rss_mb": mem["rss_mb"],
            "vms_mb": mem["vms_mb"],
            "indexing_in_progress": _INDEXING_LOCK.locked(),
            "cached_indexes": get_loaded_index_ids(),
        },
    }


@app.post("/api/system/clear-cache")
def clear_cache(current_user: User = Depends(get_current_user)):
    """Evict all in-memory FAISS indexes and force garbage collection."""
    unload_index(None)
    mem = force_garbage_collection("Manual cache clear")
    return {"status": "cache cleared", "memory": mem}


def _parse_single_file(item):
    """Backwards-compatible helper to parse and chunk a single file."""
    file_path, repo_path = item
    return parse_and_split_file(file_path, repo_path)


@app.post("/api/repos/index", response_model=IndexRepoResponse)
def index_repo(
    req: IndexRepoRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Enforce concurrency limit: only 1 indexing job at a time
    if not _INDEXING_LOCK.acquire(blocking=False):
        raise HTTPException(
            status_code=429,
            detail="Another repository indexing job is currently in progress. "
                   "To prevent Out-Of-Memory (OOM) errors on server instances (e.g. 512MB RAM on Render), "
                   "concurrent indexing is limited to 1 job. Please wait and retry shortly.",
        )

    try:
        log_memory(f"Starting index_repo for '{req.repo_url}'")
        try:
            repo_id, repo_path = clone_repo(req.repo_url, req.branch)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Clone failed: {e}")

        files = list(iter_source_files(repo_path))
        num_files = len(files)
        if num_files == 0:
            raise HTTPException(status_code=422, detail="No indexable source files found in repo")

        log_memory(f"Cloned repo: {num_files} source files detected")

        # Stream chunk batches directly to FAISS to eliminate full-repository RAM accumulation
        chunk_batches = stream_chunk_batches(repo_path, batch_size=settings.INDEXING_BATCH_SIZE)
        num_chunks = build_index(repo_id, chunk_batches)

        if num_chunks == 0:
            raise HTTPException(status_code=422, detail="No indexable code chunks extracted from repo")

        # Upsert a Repo record so it shows up on the user's dashboard.
        repo_row = db.query(Repo).filter(Repo.id == repo_id).first()
        if repo_row is None:
            repo_row = Repo(id=repo_id, owner_id=current_user.id, url=req.repo_url)
            db.add(repo_row)
        repo_row.num_files = num_files
        repo_row.num_chunks = num_chunks
        db.commit()

        log_memory(f"Completed index_repo for {repo_id}: {num_files} files, {num_chunks} chunks")
        return IndexRepoResponse(
            repo_id=repo_id, num_files=num_files, num_chunks=num_chunks, status="indexed"
        )
    except MemoryLimitExceeded as e:
        raise HTTPException(
            status_code=507,
            detail=f"Server memory threshold reached (Render 512MB cap). Indexing safely halted: {e}",
        )
    finally:
        _INDEXING_LOCK.release()
        force_garbage_collection("Post index_repo cleanup")


@app.get("/api/repos/{repo_id}/status", response_model=RepoStatus)
def repo_status(repo_id: str, current_user: User = Depends(get_current_user)):
    return RepoStatus(repo_id=repo_id, indexed=index_exists(repo_id))


def _record_history(db: Session, user: User, repo_id: str, action_type: str, question: str, answer: str):
    try:
        repo_row = db.query(Repo).filter(Repo.id == repo_id).first()
        entry = QueryHistory(
            user_id=user.id,
            repo_id=repo_id,
            repo_url=repo_row.url if repo_row else repo_id,
            action_type=action_type,
            question=question,
            answer=answer,
        )
        db.add(entry)
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"--> [Warning] Failed to record query history to DB: {e}")


@app.post("/api/ask", response_model=AskResponse)
def ask(
    req: AskRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    print(f"\n--> [API /ask] Received question: '{req.question}' for repo {req.repo_id}")
    if not index_exists(req.repo_id):
        raise HTTPException(status_code=404, detail="Repo not indexed. Call /api/repos/index first.")

    graph = get_graph()
    print("--> [API /ask] Invoking LangGraph agent pipeline...")
    result = graph.invoke({"repo_id": req.repo_id, "question": req.question})
    print("--> [API /ask] Graph execution complete! Returning response.")

    sources = [
        SourceChunk(
            file_path=r["file_path"], start_line=r["start_line"],
            end_line=r["end_line"], symbol=r.get("symbol"), snippet=r["snippet"],
        )
        for r in result.get("retrieved", [])
    ]
    answer = result.get("answer", "")

    _record_history(db, current_user, req.repo_id, "ask", req.question, answer)
    force_garbage_collection("Post ask query cleanup")

    return AskResponse(answer=answer, plan=result.get("plan", []), sources=sources)


# ---- Convenience endpoints that just pre-fill a prompt template and reuse the graph ----

def _run_prompt(
    repo_id: str, question: str, action_type: str,
    current_user: User, db: Session,
) -> AskResponse:
    result = ask(AskRequest(repo_id=repo_id, question=question), current_user=current_user, db=db)
    # ask() already recorded this under action_type="ask" - relabel the most recent entry.
    last = (
        db.query(QueryHistory)
        .filter(QueryHistory.user_id == current_user.id, QueryHistory.repo_id == repo_id)
        .order_by(QueryHistory.created_at.desc())
        .first()
    )
    if last:
        last.action_type = action_type
        db.commit()
    return result


@app.post("/api/repos/docs", response_model=AskResponse)
def generate_docs(
    req: FileActionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = (f"Generate clear markdown documentation for the file `{req.file_path}`: "
         f"purpose, public functions/classes with parameters and return values, "
         f"and any important side effects.")
    return _run_prompt(req.repo_id, q, "docs", current_user, db)


@app.post("/api/repos/tests", response_model=AskResponse)
def generate_tests(
    req: FileActionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = (f"Generate unit tests for the file `{req.file_path}`. Infer the testing "
         f"framework from the language/repo conventions. Cover the main logic "
         f"branches and edge cases. Output complete runnable test code.")
    return _run_prompt(req.repo_id, q, "tests", current_user, db)


@app.post("/api/repos/duplicates", response_model=AskResponse)
def find_duplicates(
    req: FileActionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = (f"Analyze `{req.file_path}` and related retrieved code for duplicated or "
         f"near-duplicated logic elsewhere in the repo. List the duplicate "
         f"locations and suggest how to consolidate them.")
    return _run_prompt(req.repo_id, q, "duplicates", current_user, db)


@app.post("/api/repos/optimize", response_model=AskResponse)
def suggest_optimizations(
    req: FileActionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = (f"Review `{req.file_path}` for performance, readability, and "
         f"maintainability issues. Suggest concrete optimizations with brief "
         f"reasoning for each.")
    return _run_prompt(req.repo_id, q, "optimize", current_user, db)
