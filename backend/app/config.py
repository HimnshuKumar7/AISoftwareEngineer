"""
Central configuration for the AI Software Engineer backend.
All values can be overridden via environment variables / .env file.
"""
import sys
from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path

# Platform-aware default: On Windows, PyTorch working set includes mapped system DLLs (~480-520MB).
# On Linux (Render), private cgroup RSS is much lower (~200-300MB) with a hard 512MB ceiling.
DEFAULT_MAX_MEMORY_MB: float = 800.0 if sys.platform == "win32" else 485.0


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # ---- Storage ----
    DATA_DIR: str = str(Path(__file__).resolve().parent.parent / "data")

    # ---- LLM provider: "ollama" | "groq" | "gemini" | "openai" ----
    LLM_PROVIDER: str = "ollama"

    # Ollama (fully local, free, no API key)
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "qwen2.5-coder:7b"

    # Groq (free tier, very fast, hosted) - https://console.groq.com
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama-3.1-8b-instant"

    # Google Gemini (free tier) - https://aistudio.google.com/apikey
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.0-flash"

    # OpenAI (paid, optional)
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"

    # ---- Embeddings: local, free, runs on CPU ----
    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"

    # ---- Chunking ----
    MAX_CHUNK_CHARS: int = 1800
    CHUNK_OVERLAP: int = 200

    # ---- Retrieval ----
    TOP_K: int = 4
    MAX_RETRIEVED_CHUNKS: int = 6
    MAX_RAG_CHUNK_CHARS: int = 900
    MAX_RAG_CONTEXT_CHARS: int = 3600

    # ---- LLM request budgets ----
    # Groq's free-tier TPM limit is 8,000. Keep input below 6,000 tokens and
    # reserve room for a concise response and chat-message overhead.
    LLM_MAX_INPUT_TOKENS: int = 6000
    LLM_INPUT_TOKEN_SAFETY_MARGIN: int = 256
    LLM_MAX_SYSTEM_PROMPT_TOKENS: int = 1600
    LLM_MAX_RESPONSE_TOKENS: int = 1024
    MAX_QUESTION_CHARS: int = 1200
    MAX_REASONING_CHARS: int = 2800

    # ---- Memory & Performance Optimization (Render 512MB RAM safe) ----
    WEB_CONCURRENCY: int = 1
    INDEXING_BATCH_SIZE: int = 32
    EMBEDDING_BATCH_SIZE: int = 16
    PARSER_MAX_WORKERS: int = 1
    FAISS_CACHE_MAX_SIZE: int = 1
    FORCE_GC_AFTER_INDEXING: bool = True
    MAX_PROCESS_MEMORY_MB: float = DEFAULT_MAX_MEMORY_MB  # Guard threshold below Render's 512MB hard limit (Linux) or Windows working set
    MAX_REPO_CHUNKS: int = 2500           # Cap max chunks to prevent multi-GB repo indexes in memory
    MAX_FILE_SIZE_BYTES: int = 500_000    # Skip files > 500KB (e.g. minified bundles, big datasets)

    # ---- Server ----
    # Comma-separated list, e.g. "https://your-app.vercel.app,http://localhost:5173"
    CORS_ORIGINS_RAW: str = "https://ai-software-engineer-omega.vercel.app,http://127.0.0.1:5173"

    @property
    def CORS_ORIGINS(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS_RAW.split(",") if o.strip()]

    # ---- Database (Neon Postgres) ----
    # Get this from your Neon project dashboard -> Connection Details.
    # Example: postgresql://user:password@ep-xxxx.neon.tech/dbname?sslmode=require
    DATABASE_URL: str = ""

    # ---- Auth (JWT) ----
    JWT_SECRET: str = "change-this-to-a-long-random-string"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days users login remains for 7 days, have to log in again after that


settings = Settings()
Path(settings.DATA_DIR).mkdir(parents=True, exist_ok=True)
Path(settings.DATA_DIR, "repos").mkdir(parents=True, exist_ok=True)
Path(settings.DATA_DIR, "indexes").mkdir(parents=True, exist_ok=True)
