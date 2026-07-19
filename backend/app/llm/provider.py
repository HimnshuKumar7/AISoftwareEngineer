"""
Returns a LangChain chat model based on LLM_PROVIDER in config/.env.

Free options (recommended):
  - "ollama": 100% local & free. Install Ollama on Windows, then:
        ollama pull qwen2.5-coder:7b
    No API key needed. Best for privacy / zero cost, needs a decent GPU/CPU.
  - "groq":  Free hosted tier, extremely fast, generous rate limits.
        Get a free key at https://console.groq.com
  - "gemini": Free hosted tier from Google.
        Get a free key at https://aistudio.google.com/apikey

Paid option:
  - "openai": requires billing enabled on your OpenAI account.
"""
from functools import lru_cache

from app.config import settings


@lru_cache(maxsize=1)
def get_llm():
    provider = settings.LLM_PROVIDER.lower()

    if provider == "ollama":
        from langchain_ollama import ChatOllama
        return ChatOllama(
            base_url=settings.OLLAMA_BASE_URL,
            model=settings.OLLAMA_MODEL,
            temperature=0.1,
        )

    if provider == "groq":
        from langchain_groq import ChatGroq
        return ChatGroq(
            api_key=settings.GROQ_API_KEY,
            model=settings.GROQ_MODEL,
            temperature=0.1,
        )

    if provider == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            google_api_key=settings.GEMINI_API_KEY,
            model=settings.GEMINI_MODEL,
            temperature=0.1,
        )

    if provider == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            api_key=settings.OPENAI_API_KEY,
            model=settings.OPENAI_MODEL,
            temperature=0.1,
        )

    raise ValueError(f"Unknown LLM_PROVIDER: {provider}")
