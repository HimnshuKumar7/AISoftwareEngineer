from pydantic import BaseModel
from typing import Optional


class IndexRepoRequest(BaseModel):
    repo_url: str
    branch: Optional[str] = None


class IndexRepoResponse(BaseModel):
    repo_id: str
    num_files: int
    num_chunks: int
    status: str


class RepoStatus(BaseModel):
    repo_id: str
    indexed: bool
    num_files: int = 0
    num_chunks: int = 0


class AskRequest(BaseModel):
    repo_id: str
    question: str


class SourceChunk(BaseModel):
    file_path: str
    start_line: int
    end_line: int
    symbol: Optional[str] = None
    snippet: str


class AskResponse(BaseModel):
    answer: str
    plan: list[str]
    sources: list[SourceChunk]


class FileActionRequest(BaseModel):
    repo_id: str
    file_path: str
