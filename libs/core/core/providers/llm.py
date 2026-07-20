"""Pluggable LLM providers for grounded answer generation.

The stub provider is the zero-cost dev default: it reads the numbered sources
out of the system prompt and emits a deterministic answer with inline citation
markers, so the whole generation path (streaming, citation parsing, session
memory) is exercisable offline and in CI. The Anthropic and OpenAI providers
implement the identical streaming interface and activate via config.
"""

import re
from collections.abc import AsyncIterator
from functools import lru_cache
from typing import Any, Protocol, runtime_checkable

from core.config import get_settings

# Matches the "[n]" source markers the prompt builder emits.
_SOURCE_RE = re.compile(r"^\[(\d+)\]", re.MULTILINE)


@runtime_checkable
class LLMProvider(Protocol):
    name: str

    def astream(self, *, system: str, messages: list[dict[str, str]]) -> AsyncIterator[str]: ...


class StubLLMProvider:
    """Deterministic, offline answer generator.

    Cites every source it was given so citation extraction has something real
    to parse, and echoes the question so multi-turn memory is observable.
    """

    name = "stub"

    def astream(self, *, system: str, messages: list[dict[str, str]]) -> AsyncIterator[str]:
        question = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
        sources = _SOURCE_RE.findall(system)
        citations = "".join(f"[{n}]" for n in sources) or "(no sources retrieved)"
        text = (
            f"Based on the retrieved context, here is the answer to "
            f"{question.strip()!r}. {citations}"
        )

        async def _gen() -> AsyncIterator[str]:
            # Emit word-by-word so the SSE streaming path is genuinely exercised.
            for i, word in enumerate(text.split(" ")):
                yield word if i == 0 else f" {word}"

        return _gen()


class AnthropicLLMProvider:
    """Claude generation via the official Anthropic SDK.

    Note: temperature / top_p / top_k are rejected by the Opus 4.8 family, so
    they are never sent; depth is controlled with adaptive thinking + effort.
    """

    name = "anthropic"

    def __init__(self, *, api_key: str, model: str, max_tokens: int, effort: str) -> None:
        import anthropic

        self._client = anthropic.AsyncAnthropic(api_key=api_key)
        self._model = model
        self._max_tokens = max_tokens
        self._effort = effort

    def astream(self, *, system: str, messages: list[dict[str, str]]) -> AsyncIterator[str]:
        async def _gen() -> AsyncIterator[str]:
            kwargs: dict[str, Any] = {
                "model": self._model,
                "max_tokens": self._max_tokens,
                "system": system,
                "messages": messages,
                "thinking": {"type": "adaptive"},
                "output_config": {"effort": self._effort},
            }
            async with self._client.messages.stream(**kwargs) as stream:
                async for text in stream.text_stream:
                    yield text

        return _gen()


class OpenAILLMProvider:
    """OpenAI chat-completions streaming (kept behind the same interface)."""

    name = "openai"

    def __init__(self, *, api_key: str, model: str, max_tokens: int, base_url: str) -> None:
        self._api_key = api_key
        self._model = model
        self._max_tokens = max_tokens
        self._base_url = base_url.rstrip("/")

    def astream(self, *, system: str, messages: list[dict[str, str]]) -> AsyncIterator[str]:
        async def _gen() -> AsyncIterator[str]:
            import json

            import httpx

            payload = {
                "model": self._model,
                "max_tokens": self._max_tokens,
                "stream": True,
                "messages": [{"role": "system", "content": system}, *messages],
            }
            async with (
                httpx.AsyncClient(timeout=120.0) as client,
                client.stream(
                    "POST",
                    f"{self._base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    json=payload,
                ) as response,
            ):
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data = line[len("data: ") :]
                    if data == "[DONE]":
                        break
                    delta = json.loads(data)["choices"][0].get("delta", {})
                    if content := delta.get("content"):
                        yield content

        return _gen()


@lru_cache
def get_llm_provider() -> LLMProvider:
    settings = get_settings()
    if settings.llm_provider == "anthropic":
        if not settings.anthropic_api_key:
            raise RuntimeError("anthropic_api_key is required when llm_provider='anthropic'")
        return AnthropicLLMProvider(
            api_key=settings.anthropic_api_key,
            model=settings.anthropic_model,
            max_tokens=settings.llm_max_tokens,
            effort=settings.llm_effort,
        )
    if settings.llm_provider == "openai":
        if not settings.openai_api_key:
            raise RuntimeError("openai_api_key is required when llm_provider='openai'")
        return OpenAILLMProvider(
            api_key=settings.openai_api_key,
            model=settings.openai_chat_model,
            max_tokens=settings.llm_max_tokens,
            base_url=settings.openai_base_url,
        )
    return StubLLMProvider()
