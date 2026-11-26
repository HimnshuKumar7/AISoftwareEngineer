"""Application configuration, loaded from environment variables (or a local .env file)."""
from __future__ import annotations

import tempfile
from functools import lru_cache
from pathlib import Path
from typing import List, Optional

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# The embedding model is a hard architectural requirement and is intentionally NOT configurable.
EMBEDDING_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_DIM = 384

SUPPORTED_LLM_PROVIDERS = ("ollama", "groq", "gemini", "openai")

_INSECURE_JWT_DEFAULT = "change-me-in-production-change-me-in-production"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", case_sensitive=False
    )

    # --- General -----------------------------------------------------------
    environment: str = "development"  # "production" enables strict startup checks
    log_level: str = "INFO"
    api_prefix: str = "/api"

    # --- Database (Neon PostgreSQL) ----------------------------------------
    database_url: str = "sqlite:///./local-dev.db"  # override with the Neon connection string
    auto_create_tables: bool = True
    db_pool_size: int = 5
    db_max_overflow: int = 5

    # --- Auth ---------------------------------------------------------------
    jwt_secret: str = _INSECURE_JWT_DEFAULT
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 12

    # --- CORS ---------------------------------------------------------------
    # Comma-separated exact origins, e.g. "https://my-app.vercel.app,http://localhost:5173"
    cors_origins: str = "http://localhost:5173"
    # Optional regex, e.g. r"https://my-app-.*\.vercel\.app" to allow Vercel preview deployments
    cors_origin_regex: Optional[str] = None

    # --- LLM provider (pluggable) -------------------------------------------
    llm_provider: str = "groq"
    llm_model: Optional[str] = None  # falls back to the provider default
    llm_temperature: float = 0.1
    llm_max_tokens: int = 1800
    llm_timeout_seconds: float = 90.0
    ollama_base_url: str = ""  # e.g. http://localhost:11434 (must be reachable from the backend host)
    groq_api_key: Optional[str] = None
    gemini_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    openai_base_url: str = "https://api.openai.com/v1"
    groq_base_url: str = "https://api.groq.com/openai/v1"
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta"

    # --- Storage ------------------------------------------------------------
    # Scratch space for clones and the local index cache. Render's filesystem is ephemeral,
    # so the source of truth for FAISS indexes is the database (see index_store.py).
    data_dir: str = str(Path(tempfile.gettempdir()) / "ai-software-engineer")
    model_cache_dir: str = "./models"  # pre-downloaded at build time

    # --- Ingestion limits (tuned for Render free tier: 512 MB RAM) ----------
    max_repos_per_user: int = 5
    clone_timeout_seconds: int = 180
    max_repo_size_mb: int = 150
    max_files_per_repo: int = 1500
    max_file_size_kb: int = 256
    max_chunks_per_repo: int = 6000
    max_chunk_lines: int = 60  # long definitions are split into windows of this size
    embedding_batch_size: int = 16
    index_cache_size: int = 2  # number of repo indexes kept in RAM

    # --- RAG ----------------------------------------------------------------
    retrieval_top_k: int = 6  # per sub-query
    max_context_chunks: int = 12
    max_context_chars: int = 20000
    near_duplicate_threshold: float = 0.85  # cosine pre-filter; confirmed lexically
    history_turns: int = 3

    @field_validator("llm_provider")
    @classmethod
    def _check_provider(cls, v: str) -> str:
        v = v.strip().lower()
        if v not in SUPPORTED_LLM_PROVIDERS:
            raise ValueError(f"LLM_PROVIDER must be one of {SUPPORTED_LLM_PROVIDERS}")
        return v

    @model_validator(mode="after")
    def _production_checks(self) -> "Settings":
        if self.environment.lower() == "production":
            if self.jwt_secret == _INSECURE_JWT_DEFAULT or len(self.jwt_secret) < 32:
                raise ValueError("JWT_SECRET must be set to a random string of >= 32 chars in production")
            if self.database_url.startswith("sqlite"):
                raise ValueError("DATABASE_URL must point at Neon PostgreSQL in production")
        return self

    @property
    def cors_origin_list(self) -> List[str]:
        return [o.strip().rstrip("/") for o in self.cors_origins.split(",") if o.strip()]

    @property
    def sqlalchemy_url(self) -> str:
        """Normalise Neon/Heroku style URLs to the psycopg (v3) SQLAlchemy driver."""
        url = self.database_url.strip()
        if url.startswith("postgres://"):
            url = "postgresql://" + url[len("postgres://"):]
        if url.startswith("postgresql://"):
            url = "postgresql+psycopg://" + url[len("postgresql://"):]
        return url

    @property
    def is_sqlite(self) -> bool:
        return self.sqlalchemy_url.startswith("sqlite")

    @property
    def data_path(self) -> Path:
        p = Path(self.data_dir)
        p.mkdir(parents=True, exist_ok=True)
        return p


@lru_cache
def get_settings() -> Settings:
    return Settings()
