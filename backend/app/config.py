"""
Central configuration for the AI Software Engineer backend.
All values can be overridden via environment variables / .env file.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path


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
    GROQ_MODEL: str = "llama-3.3-70b-versatile"

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
    TOP_K: int = 8

    # ---- Server ----
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
    JWT_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days


settings = Settings()
Path(settings.DATA_DIR).mkdir(parents=True, exist_ok=True)
Path(settings.DATA_DIR, "repos").mkdir(parents=True, exist_ok=True)
Path(settings.DATA_DIR, "indexes").mkdir(parents=True, exist_ok=True)
