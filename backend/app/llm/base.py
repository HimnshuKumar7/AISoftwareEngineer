"""Provider-agnostic LLM interface. Embeddings never go through this layer."""
from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from typing import Dict, List, Optional

import httpx

from app.core.errors import LLMError

log = logging.getLogger(__name__)

Message = Dict[str, str]  # {"role": "user" | "assistant", "content": "..."}


class LLMProvider(ABC):
    name: str = "base"

    def __init__(self, model: str, timeout: float = 90.0, client: Optional[httpx.Client] = None):
        self.model = model
        self.timeout = timeout
        self._client = client  # injectable for tests

    @abstractmethod
    def _build_request(self, system: str, messages: List[Message], temperature: float, max_tokens: int) -> Dict:
        """Return kwargs for httpx.Client.request: method, url, headers, json."""

    @abstractmethod
    def _parse_response(self, data: Dict) -> str:
        """Extract the assistant text from the provider's JSON response."""

    def generate(self, system: str, messages: List[Message], *, temperature: float = 0.1, max_tokens: int = 1800) -> str:
        req = self._build_request(system, messages, temperature, max_tokens)
        data = self._send(req)
        text = self._parse_response(data).strip()
        if not text:
            raise LLMError(f"{self.name} returned an empty response")
        return text

    # ------------------------------------------------------------------
    def _send(self, req: Dict) -> Dict:
        client = self._client or httpx.Client(timeout=self.timeout)
        last: Optional[Exception] = None
        try:
            for attempt in range(3):
                try:
                    resp = client.request(**req)
                except httpx.TimeoutException as e:
                    last = e
                    log.warning("%s timeout (attempt %d)", self.name, attempt + 1)
                except httpx.HTTPError as e:
                    last = e
                    log.warning("%s connection error (attempt %d): %s", self.name, attempt + 1, type(e).__name__)
                else:
                    if resp.status_code < 400:
                        try:
                            return resp.json()
                        except ValueError:
                            raise LLMError(f"{self.name} returned a non-JSON response")
                    if resp.status_code in (429, 500, 502, 503, 504) and attempt < 2:
                        log.warning("%s HTTP %d (attempt %d)", self.name, resp.status_code, attempt + 1)
                        last = None
                    else:
                        self._raise_for_status(resp)
                time.sleep(1.5 * (attempt + 1))
            if isinstance(last, httpx.TimeoutException):
                raise LLMError(f"{self.name} timed out. Try again or choose a faster model.")
            raise LLMError(f"Could not reach {self.name}. Check the provider configuration and try again.")
        finally:
            if self._client is None:
                client.close()

    def _raise_for_status(self, resp: httpx.Response) -> None:
        code = resp.status_code
        detail = ""
        try:
            body = resp.json()
            err = body.get("error", body) if isinstance(body, dict) else {}
            detail = (err.get("message") if isinstance(err, dict) else str(err)) or ""
        except ValueError:
            detail = resp.text[:200]
        detail = detail.replace("\n", " ")[:300]
        if code in (401, 403):
            raise LLMError(f"{self.name} rejected the API credentials (HTTP {code}). Check the server's API key.",
                           code="llm_auth_error")
        if code == 404:
            raise LLMError(f"{self.name} model '{self.model}' was not found. Check LLM_MODEL. {detail}", code="llm_model_error")
        if code == 429:
            raise LLMError(f"{self.name} rate limit reached. Please retry in a moment.", code="llm_rate_limited")
        raise LLMError(f"{self.name} request failed (HTTP {code}). {detail}")
