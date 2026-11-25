"""
Returns a LangChain chat model based on LLM_PROVIDER in config/.env.

Supported options:
  - "gemini": Free hosted tier from Google AI Studio.
  - "groq":   Free hosted tier from Groq.
  - "ollama": 100% local & free.
  - "openai": Paid API.
"""
from functools import lru_cache

from app.config import settings


@lru_cache(maxsize=8)
def _create_llm(provider: str, model: str, api_key: str, base_url: str):
    if provider == "ollama":
        from langchain_ollama import ChatOllama
        return ChatOllama(
            base_url=base_url,
            model=model,
            temperature=0.1,
            num_predict=settings.LLM_MAX_RESPONSE_TOKENS,
        )

    if provider == "groq":
        from langchain_groq import ChatGroq
        return ChatGroq(
            api_key=api_key,
            model=model,
            temperature=0.1,
            max_tokens=settings.LLM_MAX_RESPONSE_TOKENS,
        )

    if provider == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            google_api_key=api_key,
            model=model,
            temperature=0.1,
            max_output_tokens=settings.LLM_MAX_RESPONSE_TOKENS,
        )

    if provider == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            api_key=api_key,
            model=model,
            temperature=0.1,
            max_tokens=settings.LLM_MAX_RESPONSE_TOKENS,
        )

    raise ValueError(f"Unknown LLM_PROVIDER: {provider}")


def get_llm():
    provider = settings.LLM_PROVIDER.lower()
    if provider == "ollama":
        return _create_llm("ollama", settings.OLLAMA_MODEL, "", settings.OLLAMA_BASE_URL)
    elif provider == "groq":
        return _create_llm("groq", settings.GROQ_MODEL, settings.GROQ_API_KEY, "")
    elif provider == "gemini":
        return _create_llm("gemini", settings.GEMINI_MODEL, settings.GEMINI_API_KEY, "")
    elif provider == "openai":
        return _create_llm("openai", settings.OPENAI_MODEL, settings.OPENAI_API_KEY, "")
    else:
        raise ValueError(f"Unknown LLM_PROVIDER: {provider}")
