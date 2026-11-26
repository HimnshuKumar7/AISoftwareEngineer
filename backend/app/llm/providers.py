"""Concrete providers: Ollama, Groq, Gemini, OpenAI (all via plain HTTPS to keep memory low)."""
from __future__ import annotations

from typing import Dict, List, Optional

import httpx

from app.core.config import SUPPORTED_LLM_PROVIDERS, Settings, get_settings
from app.core.errors import LLMError, ValidationFailure
from app.llm.base import LLMProvider, Message

DEFAULT_MODELS: Dict[str, str] = {
    "ollama": "llama3.1:8b",
    "groq": "llama-3.3-70b-versatile",
    "gemini": "gemini-2.5-flash",
    "openai": "gpt-4o-mini",
}


class OpenAICompatibleProvider(LLMProvider):
    """OpenAI and Groq both speak the OpenAI Chat Completions protocol."""

    def __init__(self, name: str, base_url: str, api_key: str, model: str, token_param: str, **kw):
        super().__init__(model, **kw)
        self.name = name
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.token_param = token_param
        self._send_temperature = True

    def _build_request(self, system, messages, temperature, max_tokens):
        payload: Dict = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, *messages],
            self.token_param: max_tokens,
        }
        if self._send_temperature:
            payload["temperature"] = temperature
        return {
            "method": "POST",
            "url": f"{self.base_url}/chat/completions",
            "headers": {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            "json": payload,
        }

    def _parse_response(self, data):
        try:
            return data["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError):
            raise LLMError(f"{self.name} returned an unexpected response shape")

    def generate(self, system, messages, *, temperature=0.1, max_tokens=1800):
        try:
            return super().generate(system, messages, temperature=temperature, max_tokens=max_tokens)
        except LLMError as e:
            # Some newer reasoning models only accept the default temperature.
            if self._send_temperature and "temperature" in str(e).lower():
                self._send_temperature = False
                return super().generate(system, messages, temperature=temperature, max_tokens=max_tokens)
            raise


class GeminiProvider(LLMProvider):
    name = "gemini"

    def __init__(self, base_url: str, api_key: str, model: str, **kw):
        super().__init__(model, **kw)
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    def _build_request(self, system, messages, temperature, max_tokens):
        contents = [
            {"role": "model" if m["role"] == "assistant" else "user", "parts": [{"text": m["content"]}]}
            for m in messages
        ]
        return {
            "method": "POST",
            "url": f"{self.base_url}/models/{self.model}:generateContent",
            "headers": {"x-goog-api-key": self.api_key, "Content-Type": "application/json"},
            "json": {
                "systemInstruction": {"parts": [{"text": system}]},
                "contents": contents,
                "generationConfig": {"temperature": temperature, "maxOutputTokens": max_tokens},
            },
        }

    def _parse_response(self, data):
        cands = data.get("candidates") or []
        if not cands:
            reason = (data.get("promptFeedback") or {}).get("blockReason", "no candidates")
            raise LLMError(f"gemini returned no answer ({reason})")
        parts = (cands[0].get("content") or {}).get("parts") or []
        return "".join(p.get("text", "") for p in parts)


class OllamaProvider(LLMProvider):
    name = "ollama"

    def __init__(self, base_url: str, model: str, **kw):
        super().__init__(model, **kw)
        self.base_url = base_url.rstrip("/")

    def _build_request(self, system, messages, temperature, max_tokens):
        return {
            "method": "POST",
            "url": f"{self.base_url}/api/chat",
            "headers": {"Content-Type": "application/json"},
            "json": {
                "model": self.model,
                "stream": False,
                "messages": [{"role": "system", "content": system}, *messages],
                "options": {"temperature": temperature, "num_predict": max_tokens},
            },
        }

    def _parse_response(self, data):
        try:
            return data["message"]["content"] or ""
        except (KeyError, TypeError):
            raise LLMError("ollama returned an unexpected response shape")


def provider_is_configured(provider: str, s: Settings) -> bool:
    if provider == "ollama":
        return bool(s.ollama_base_url)
    return bool({"groq": s.groq_api_key, "gemini": s.gemini_api_key, "openai": s.openai_api_key}[provider])


def default_model_for(provider: str, s: Settings) -> str:
    # LLM_MODEL only applies to the provider selected via LLM_PROVIDER.
    if s.llm_model and provider == s.llm_provider:
        return s.llm_model
    return DEFAULT_MODELS[provider]


def get_llm(provider: Optional[str] = None, model: Optional[str] = None,
            client: Optional[httpx.Client] = None) -> LLMProvider:
    s = get_settings()
    provider = (provider or s.llm_provider).lower()
    if provider not in SUPPORTED_LLM_PROVIDERS:
        raise ValidationFailure(f"Unknown LLM provider '{provider}'. Choose one of {', '.join(SUPPORTED_LLM_PROVIDERS)}.")
    if not provider_is_configured(provider, s):
        raise LLMError(f"LLM provider '{provider}' is not configured on this server (missing API key).",
                       code="llm_not_configured", status_code=503)
    model = model or default_model_for(provider, s)
    kw = {"timeout": s.llm_timeout_seconds, "client": client}
    if provider == "openai":
        return OpenAICompatibleProvider("openai", s.openai_base_url, s.openai_api_key, model, "max_completion_tokens", **kw)
    if provider == "groq":
        return OpenAICompatibleProvider("groq", s.groq_base_url, s.groq_api_key, model, "max_tokens", **kw)
    if provider == "gemini":
        return GeminiProvider(s.gemini_base_url, s.gemini_api_key, model, **kw)
    return OllamaProvider(s.ollama_base_url, model, **kw)


def list_providers() -> List[Dict]:
    s = get_settings()
    return [
        {
            "provider": p,
            "default_model": default_model_for(p, s),
            "configured": provider_is_configured(p, s),
            "is_default": p == s.llm_provider,
        }
        for p in SUPPORTED_LLM_PROVIDERS
    ]
