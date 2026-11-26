"""Pydantic request/response models (validation lives here)."""
from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

Mode = Literal["qa", "explain", "optimize", "duplicates"]
_MODEL_RE = re.compile(r"^[A-Za-z0-9._:/@-]{1,100}$")


# --- auth -------------------------------------------------------------------------
class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)
    name: Optional[str] = Field(default=None, max_length=120)

    @field_validator("password")
    @classmethod
    def _bytes(cls, v: str) -> str:
        if len(v.encode("utf-8")) > 72:
            raise ValueError("password must be at most 72 bytes")
        return v

    @field_validator("email")
    @classmethod
    def _lower(cls, v: str) -> str:
        return v.lower()


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=72)

    @field_validator("email")
    @classmethod
    def _lower(cls, v: str) -> str:
        return v.lower()


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    email: str
    name: Optional[str] = None
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# --- repositories -----------------------------------------------------------------
class RepoCreate(BaseModel):
    url: str = Field(min_length=10, max_length=300)
    branch: Optional[str] = Field(default=None, max_length=100)


class RepoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    url: str
    owner: str
    name: str
    branch: Optional[str] = None
    commit_sha: Optional[str] = None
    status: str
    status_message: Optional[str] = None
    progress: int = 0
    file_count: int = 0
    chunk_count: int = 0
    languages: Dict[str, Any] = {}
    created_at: datetime
    indexed_at: Optional[datetime] = None


# --- querying ---------------------------------------------------------------------
class QueryRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)
    mode: Mode = "qa"
    conversation_id: Optional[uuid.UUID] = None
    provider: Optional[Literal["ollama", "groq", "gemini", "openai"]] = None
    model: Optional[str] = Field(default=None, max_length=100)

    @field_validator("question")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 3:
            raise ValueError("question is too short")
        return v

    @field_validator("model")
    @classmethod
    def _model(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not _MODEL_RE.match(v):
            raise ValueError("invalid model name")
        return v


class Citation(BaseModel):
    path: str
    start_line: int
    end_line: int
    chunk_id: int
    kind: str
    name: str


class Source(BaseModel):
    chunk_id: int
    path: str
    start_line: int
    end_line: int
    kind: str
    name: str
    language: str
    score: float
    code: str
    cited: bool = False
    also_at: List[str] = []


class QueryResponse(BaseModel):
    id: uuid.UUID
    conversation_id: uuid.UUID
    repo_id: uuid.UUID
    mode: str
    question: str
    answer: str
    sub_queries: List[str]
    citations: List[Citation]
    sources: List[Source]
    dedupe_stats: Dict[str, int] = {}
    removed_citations: int = 0
    timings_ms: Dict[str, int] = {}
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None
    latency_ms: int
    created_at: datetime


class HistoryItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    conversation_id: uuid.UUID
    mode: str
    question: str
    answer: str
    sub_queries: List[str]
    citations: List[Dict[str, Any]]
    sources: List[Dict[str, Any]]
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None
    latency_ms: int
    created_at: datetime


class ConversationSummary(BaseModel):
    conversation_id: uuid.UUID
    title: str
    last_activity: datetime
    messages: int


class ProviderInfo(BaseModel):
    provider: str
    default_model: str
    configured: bool
    is_default: bool
