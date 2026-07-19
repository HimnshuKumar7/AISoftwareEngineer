from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db, init_db
from app.ingestion.clone import clone_repo, iter_source_files
from app.ingestion.parser import parse_file_to_chunks
from app.ingestion.chunker import split_oversized
from app.vectorstore.faiss_store import build_index, index_exists
from app.graph.graph import get_graph
from app.models import (
    IndexRepoRequest, IndexRepoResponse, RepoStatus,
    AskRequest, AskResponse, SourceChunk, FileActionRequest,
)
from app.auth.router import router as auth_router
from app.auth.deps import get_current_user
from app.auth.models import User, Repo, QueryHistory

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
    return {"status": "ok", "llm_provider": settings.LLM_PROVIDER}


@app.post("/api/repos/index", response_model=IndexRepoResponse)
def index_repo(
    req: IndexRepoRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        repo_id, repo_path = clone_repo(req.repo_url, req.branch)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Clone failed: {e}")

    all_chunks = []
    num_files = 0
    for file_path in iter_source_files(repo_path):
        num_files += 1
        try:
            for chunk in parse_file_to_chunks(file_path, repo_path):
                all_chunks.extend(split_oversized(chunk))
        except Exception:
            continue  # skip unparsable files, never fail the whole index

    if not all_chunks:
        raise HTTPException(status_code=422, detail="No indexable source files found in repo")

    num_chunks = build_index(repo_id, all_chunks)

    # Upsert a Repo record so it shows up on the user's dashboard.
    repo_row = db.query(Repo).filter(Repo.id == repo_id).first()
    if repo_row is None:
        repo_row = Repo(id=repo_id, owner_id=current_user.id, url=req.repo_url)
        db.add(repo_row)
    repo_row.num_files = num_files
    repo_row.num_chunks = num_chunks
    db.commit()

    return IndexRepoResponse(
        repo_id=repo_id, num_files=num_files, num_chunks=num_chunks, status="indexed"
    )


@app.get("/api/repos/{repo_id}/status", response_model=RepoStatus)
def repo_status(repo_id: str, current_user: User = Depends(get_current_user)):
    return RepoStatus(repo_id=repo_id, indexed=index_exists(repo_id))


def _record_history(db: Session, user: User, repo_id: str, action_type: str, question: str, answer: str):
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


@app.post("/api/ask", response_model=AskResponse)
def ask(
    req: AskRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not index_exists(req.repo_id):
        raise HTTPException(status_code=404, detail="Repo not indexed. Call /api/repos/index first.")

    graph = get_graph()
    result = graph.invoke({"repo_id": req.repo_id, "question": req.question})

    sources = [
        SourceChunk(
            file_path=r["file_path"], start_line=r["start_line"],
            end_line=r["end_line"], symbol=r.get("symbol"), snippet=r["snippet"],
        )
        for r in result.get("retrieved", [])
    ]
    answer = result.get("answer", "")

    _record_history(db, current_user, req.repo_id, "ask", req.question, answer)

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
