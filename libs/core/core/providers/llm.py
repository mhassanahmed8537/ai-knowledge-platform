"""Pluggable LLM providers for grounded answer generation.

The stub provider is the zero-cost dev default: it reads the numbered sources
out of the system prompt and emits a deterministic answer with inline citation
markers, so the whole generation path (streaming, citation parsing, session
memory) is exercisable offline and in CI. The Anthropic (Claude), OpenAI (GPT),
and Google (Gemini) providers implement the identical streaming interface and
activate via config — nothing outside this module knows which vendor is in use.
"""

import re
from collections.abc import AsyncIterator
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Protocol, runtime_checkable

from core.config import get_settings

# Matches the "[n]" source markers the prompt builder emits.
_SOURCE_RE = re.compile(r"^\[(\d+)\]", re.MULTILINE)


@dataclass
class UsageAccumulator:
    """Filled in by a provider as it streams, for cost tracking.

    Callers create one fresh instance per request (providers are cached
    singletons — see ``get_llm_provider`` — so state can't be held on the
    provider itself without leaking across concurrent requests).
    """

    input_tokens: int = 0
    output_tokens: int = 0


@runtime_checkable
class LLMProvider(Protocol):
    name: str
    model: str

    def astream(
        self,
        *,
        system: str,
        messages: list[dict[str, str]],
        usage: UsageAccumulator | None = None,
    ) -> AsyncIterator[str]: ...


class StubLLMProvider:
    """Deterministic, offline answer generator.

    Cites every source it was given so citation extraction has something real
    to parse, and echoes the question so multi-turn memory is observable.
    """

    name = "stub"
    model = "stub"

    def astream(
        self,
        *,
        system: str,
        messages: list[dict[str, str]],
        usage: UsageAccumulator | None = None,
    ) -> AsyncIterator[str]:
        question = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
        sources = _SOURCE_RE.findall(system)
        citations = "".join(f"[{n}]" for n in sources) or "(no sources retrieved)"
        text = (
            f"Based on the retrieved context, here is the answer to "
            f"{question.strip()!r}. {citations}"
        )
        if usage is not None:
            # Word-count heuristic: cheap, deterministic, and costs $0 anyway
            # (the stub has no pricing entry), so precision doesn't matter here.
            prompt_words = len(system.split()) + sum(len(m["content"].split()) for m in messages)
            usage.input_tokens = prompt_words
            usage.output_tokens = len(text.split())

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
        self.model = model
        self._max_tokens = max_tokens
        self._effort = effort

    def astream(
        self,
        *,
        system: str,
        messages: list[dict[str, str]],
        usage: UsageAccumulator | None = None,
    ) -> AsyncIterator[str]:
        async def _gen() -> AsyncIterator[str]:
            kwargs: dict[str, Any] = {
                "model": self.model,
                "max_tokens": self._max_tokens,
                "system": system,
                "messages": messages,
                "thinking": {"type": "adaptive"},
                "output_config": {"effort": self._effort},
            }
            async with self._client.messages.stream(**kwargs) as stream:
                async for text in stream.text_stream:
                    yield text
                if usage is not None:
                    final = await stream.get_final_message()
                    usage.input_tokens = final.usage.input_tokens
                    usage.output_tokens = final.usage.output_tokens

        return _gen()


class OpenAILLMProvider:
    """OpenAI chat-completions streaming (kept behind the same interface)."""

    name = "openai"

    def __init__(self, *, api_key: str, model: str, max_tokens: int, base_url: str) -> None:
        self._api_key = api_key
        self.model = model
        self._max_tokens = max_tokens
        self._base_url = base_url.rstrip("/")

    def astream(
        self,
        *,
        system: str,
        messages: list[dict[str, str]],
        usage: UsageAccumulator | None = None,
    ) -> AsyncIterator[str]:
        async def _gen() -> AsyncIterator[str]:
            import json

            import httpx

            payload = {
                "model": self.model,
                "max_tokens": self._max_tokens,
                "stream": True,
                # Without this, the final SSE chunk carries no usage data.
                "stream_options": {"include_usage": True},
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
                    chunk = json.loads(data)
                    if usage is not None and (chunk_usage := chunk.get("usage")):
                        usage.input_tokens = chunk_usage.get("prompt_tokens", 0)
                        usage.output_tokens = chunk_usage.get("completion_tokens", 0)
                    for choice in chunk.get("choices", []):
                        if content := choice.get("delta", {}).get("content"):
                            yield content

        return _gen()


def to_gemini_contents(messages: list[dict[str, str]]) -> list[dict[str, Any]]:
    """Map our {user,assistant} turns onto Gemini's {user,model} `contents`."""
    return [
        {
            "role": "model" if m["role"] == "assistant" else "user",
            "parts": [{"text": m["content"]}],
        }
        for m in messages
    ]


class GeminiLLMProvider:
    """Google Gemini generation via the Generative Language REST API.

    Gemini names the assistant role "model" and carries the system prompt in a
    separate `systemInstruction` field rather than as a message.
    """

    name = "gemini"

    def __init__(self, *, api_key: str, model: str, max_tokens: int, base_url: str) -> None:
        self._api_key = api_key
        self.model = model
        self._max_tokens = max_tokens
        self._base_url = base_url.rstrip("/")

    def astream(
        self,
        *,
        system: str,
        messages: list[dict[str, str]],
        usage: UsageAccumulator | None = None,
    ) -> AsyncIterator[str]:
        async def _gen() -> AsyncIterator[str]:
            import json

            import httpx

            payload = {
                "contents": to_gemini_contents(messages),
                "systemInstruction": {"parts": [{"text": system}]},
                "generationConfig": {"maxOutputTokens": self._max_tokens},
            }
            url = f"{self._base_url}/models/{self.model}:streamGenerateContent"
            async with (
                httpx.AsyncClient(timeout=120.0) as client,
                client.stream(
                    "POST",
                    url,
                    params={"alt": "sse", "key": self._api_key},
                    json=payload,
                ) as response,
            ):
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    chunk = json.loads(line[len("data: ") :])
                    # Gemini reports a running total on every chunk, so the last
                    # one seen holds the final counts.
                    if usage is not None and (meta := chunk.get("usageMetadata")):
                        usage.input_tokens = meta.get("promptTokenCount", 0)
                        usage.output_tokens = meta.get("candidatesTokenCount", 0)
                    for candidate in chunk.get("candidates", []):
                        for part in candidate.get("content", {}).get("parts", []):
                            if text := part.get("text"):
                                yield text

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
    if settings.llm_provider == "gemini":
        if not settings.gemini_api_key:
            raise RuntimeError("gemini_api_key is required when llm_provider='gemini'")
        return GeminiLLMProvider(
            api_key=settings.gemini_api_key,
            model=settings.gemini_chat_model,
            max_tokens=settings.llm_max_tokens,
            base_url=settings.gemini_base_url,
        )
    return StubLLMProvider()
