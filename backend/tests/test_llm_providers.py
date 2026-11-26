"""Pluggable LLM layer: request shapes, parsing, error mapping, provider selection via config."""
import json

import httpx
import pytest

from app.core.errors import LLMError, ValidationFailure
from app.llm import base as llm_base
from app.llm.providers import DEFAULT_MODELS, get_llm, list_providers

MSGS = [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "yo"}, {"role": "user", "content": "q?"}]


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr(llm_base.time, "sleep", lambda s: None)


def client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_openai_compatible_request_and_parse(monkeypatch, settings):
    monkeypatch.setattr(settings, "openai_api_key", "sk-test")
    seen = {}

    def handler(req: httpx.Request):
        seen["url"], seen["auth"], seen["body"] = str(req.url), req.headers["authorization"], json.loads(req.content)
        return httpx.Response(200, json={"choices": [{"message": {"content": " answer "}}]})

    llm = get_llm("openai", client=client(handler))
    assert llm.generate("SYS", MSGS, temperature=0.2, max_tokens=50) == "answer"
    assert seen["url"] == "https://api.openai.com/v1/chat/completions"
    assert seen["auth"] == "Bearer sk-test"
    body = seen["body"]
    assert body["model"] == DEFAULT_MODELS["openai"] and body["max_completion_tokens"] == 50
    assert body["messages"][0] == {"role": "system", "content": "SYS"} and len(body["messages"]) == 4


def test_groq_uses_openai_protocol_with_max_tokens(settings):
    seen = {}

    def handler(req):
        seen["url"], seen["body"] = str(req.url), json.loads(req.content)
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

    llm = get_llm("groq", model="llama-x", client=client(handler))  # groq key set in conftest
    assert llm.generate("S", MSGS) == "ok"
    assert seen["url"] == "https://api.groq.com/openai/v1/chat/completions"
    assert seen["body"]["model"] == "llama-x" and "max_tokens" in seen["body"]


def test_gemini_request_and_parse(monkeypatch, settings):
    monkeypatch.setattr(settings, "gemini_api_key", "g-key")
    seen = {}

    def handler(req):
        seen["url"], seen["key"], seen["body"] = str(req.url), req.headers["x-goog-api-key"], json.loads(req.content)
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": "he"}, {"text": "llo"}]}}]})

    llm = get_llm("gemini", client=client(handler))
    assert llm.generate("SYS", MSGS) == "hello"
    assert seen["url"].endswith(f"/models/{DEFAULT_MODELS['gemini']}:generateContent") and seen["key"] == "g-key"
    body = seen["body"]
    assert body["systemInstruction"]["parts"][0]["text"] == "SYS"
    assert [c["role"] for c in body["contents"]] == ["user", "model", "user"]


def test_gemini_blocked_prompt(monkeypatch, settings):
    monkeypatch.setattr(settings, "gemini_api_key", "g")
    llm = get_llm("gemini", client=client(lambda r: httpx.Response(200, json={"promptFeedback": {"blockReason": "SAFETY"}})))
    with pytest.raises(LLMError, match="SAFETY"):
        llm.generate("S", MSGS)


def test_ollama_request_and_parse(monkeypatch, settings):
    monkeypatch.setattr(settings, "ollama_base_url", "http://ollama.internal:11434/")
    seen = {}

    def handler(req):
        seen["url"], seen["body"] = str(req.url), json.loads(req.content)
        return httpx.Response(200, json={"message": {"role": "assistant", "content": "local"}})

    llm = get_llm("ollama", client=client(handler))
    assert llm.generate("S", MSGS, max_tokens=77) == "local"
    assert seen["url"] == "http://ollama.internal:11434/api/chat"
    assert seen["body"]["stream"] is False and seen["body"]["options"]["num_predict"] == 77


def test_error_mapping_and_retry(monkeypatch):
    calls = {"n": 0}

    def flaky(req):
        calls["n"] += 1
        return httpx.Response(429 if calls["n"] < 3 else 200, json={"choices": [{"message": {"content": "finally"}}]})

    assert get_llm("groq", client=client(flaky)).generate("S", MSGS) == "finally" and calls["n"] == 3

    with pytest.raises(LLMError) as e:
        get_llm("groq", client=client(lambda r: httpx.Response(401, json={"error": {"message": "bad key sk-SECRET"}}))).generate("S", MSGS)
    assert e.value.code == "llm_auth_error" and "SECRET" not in e.value.message

    with pytest.raises(LLMError) as e:
        get_llm("groq", client=client(lambda r: httpx.Response(404, json={"error": {"message": "no model"}}))).generate("S", MSGS)
    assert e.value.code == "llm_model_error"

    def boom(req):
        raise httpx.ConnectError("down")

    with pytest.raises(LLMError, match="Could not reach"):
        get_llm("groq", client=client(boom)).generate("S", MSGS)

    def slow(req):
        raise httpx.ReadTimeout("slow")

    with pytest.raises(LLMError, match="timed out"):
        get_llm("groq", client=client(slow)).generate("S", MSGS)


def test_openai_retries_without_temperature_for_reasoning_models(monkeypatch, settings):
    monkeypatch.setattr(settings, "openai_api_key", "k")
    bodies = []

    def handler(req):
        body = json.loads(req.content)
        bodies.append(body)
        if "temperature" in body:
            return httpx.Response(400, json={"error": {"message": "Unsupported value: 'temperature' does not support 0.1"}})
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

    assert get_llm("openai", client=client(handler)).generate("S", MSGS) == "ok"
    assert "temperature" in bodies[0] and "temperature" not in bodies[-1]


def test_provider_selection_via_config(monkeypatch, settings):
    monkeypatch.setattr(settings, "llm_provider", "gemini")
    monkeypatch.setattr(settings, "gemini_api_key", "g")
    monkeypatch.setattr(settings, "llm_model", "gemini-custom")
    llm = get_llm()
    assert llm.name == "gemini" and llm.model == "gemini-custom"
    # LLM_MODEL must not leak onto a different provider selected per request
    assert get_llm("groq").model == DEFAULT_MODELS["groq"]
    info = {p["provider"]: p for p in list_providers()}
    assert info["gemini"]["is_default"] and info["gemini"]["default_model"] == "gemini-custom"
    assert set(info) == {"ollama", "groq", "gemini", "openai"}


def test_unconfigured_and_unknown_providers(monkeypatch, settings):
    monkeypatch.setattr(settings, "openai_api_key", None)
    with pytest.raises(LLMError) as e:
        get_llm("openai")
    assert e.value.code == "llm_not_configured" and e.value.status_code == 503
    with pytest.raises(ValidationFailure):
        get_llm("skynet")
