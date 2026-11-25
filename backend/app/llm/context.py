"""Small, provider-independent guards for bounded LLM requests."""
from collections.abc import Sequence

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage

from app.config import settings


def truncate_text(text: str, max_chars: int) -> str:
    """Trim display/context text without splitting a Python character."""
    if len(text) <= max_chars:
        return text
    suffix = "\n[truncated]"
    if max_chars <= len(suffix):
        return text[:max_chars]
    return text[:max_chars - len(suffix)].rstrip() + suffix


def _clip_to_bytes(text: str, max_bytes: int) -> str:
    """Use UTF-8 bytes as a conservative upper bound for BPE token counts."""
    encoded = text.encode("utf-8")
    if len(encoded) <= max_bytes:
        return text
    suffix = "\n[truncated]"
    if max_bytes <= len(suffix.encode("utf-8")):
        return encoded[:max_bytes].decode("utf-8", errors="ignore")
    room = max(0, max_bytes - len(suffix.encode("utf-8")))
    return encoded[:room].decode("utf-8", errors="ignore").rstrip() + suffix


def _copy_message(message: BaseMessage, content: str) -> BaseMessage:
    if isinstance(message, SystemMessage):
        return SystemMessage(content=content)
    if isinstance(message, HumanMessage):
        return HumanMessage(content=content)
    return message.model_copy(update={"content": content})


def truncate_conversation(messages: Sequence[BaseMessage]) -> list[BaseMessage]:
    """Keep instructions and the newest conversation turns within Groq's input cap.

    UTF-8 byte length is intentionally a strict BPE-token upper bound. The
    safety margin covers role and message framing added by the provider.
    """
    budget = max(1, settings.LLM_MAX_INPUT_TOKENS - settings.LLM_INPUT_TOKEN_SAFETY_MARGIN)
    system_messages = [m for m in messages if isinstance(m, SystemMessage)]
    other_messages = [m for m in messages if not isinstance(m, SystemMessage)]
    selected: list[tuple[BaseMessage, str]] = []
    remaining = budget
    system_remaining = min(remaining, settings.LLM_MAX_SYSTEM_PROMPT_TOKENS)

    for message in system_messages:
        if system_remaining <= 0:
            break
        content = _clip_to_bytes(str(message.content), system_remaining)
        selected.append((message, content))
        remaining -= len(content.encode("utf-8"))
        system_remaining -= len(content.encode("utf-8"))
        if remaining <= 0:
            break

    # When callers include prior turns, retain the newest relevant messages.
    recent: list[tuple[BaseMessage, str]] = []
    for message in reversed(other_messages):
        if remaining <= 0:
            break
        content = _clip_to_bytes(str(message.content), remaining)
        recent.append((message, content))
        remaining -= len(content.encode("utf-8"))

    selected.extend(reversed(recent))
    return [_copy_message(message, content) for message, content in selected]


def invoke_bounded(llm, messages: Sequence[BaseMessage]):
    """Invoke an LLM only after applying the shared input-token guard."""
    return llm.invoke(truncate_conversation(messages))
