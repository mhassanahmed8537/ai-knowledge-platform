"""Pluggable embedding providers.

The fake provider is the zero-cost dev default: a deterministic **signed
feature-hashing** (bag-of-words) embedding. Texts that share vocabulary map to
nearby unit vectors, so both the vector and lexical arms of hybrid retrieval are
genuinely exercisable offline — while staying reproducible and free. It is
lexical, not semantic; true semantic similarity comes from swapping in the
OpenAI provider (identical interface, activated by config, no schema change).
"""

import hashlib
import math
import re
from functools import lru_cache
from typing import Protocol, runtime_checkable

from core.config import get_settings

_TOKEN_RE = re.compile(r"[a-z0-9]+")


@runtime_checkable
class EmbeddingProvider(Protocol):
    dim: int

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class FakeEmbeddingProvider:
    def __init__(self, dim: int) -> None:
        self.dim = dim

    def _vector(self, text: str) -> list[float]:
        values = [0.0] * self.dim
        for token in _TOKEN_RE.findall(text.lower()):
            digest = hashlib.md5(token.encode()).digest()  # noqa: S324 (non-crypto use)
            bucket = int.from_bytes(digest[:8], "big") % self.dim
            values[bucket] += 1.0 if digest[8] & 1 else -1.0
        norm = math.sqrt(sum(v * v for v in values))
        if norm == 0.0:
            # No alphanumeric tokens: fall back to a deterministic unit vector.
            fallback = int.from_bytes(hashlib.md5(text.encode()).digest()[:8], "big") % self.dim
            values[fallback] = 1.0
            return values
        return [v / norm for v in values]

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(t) for t in texts]


class OpenAIEmbeddingProvider:
    def __init__(self, *, api_key: str, model: str, dim: int, base_url: str) -> None:
        self.api_key = api_key
        self.model = model
        self.dim = dim
        self.base_url = base_url.rstrip("/")

    def embed(self, texts: list[str]) -> list[list[float]]:
        import httpx

        resp = httpx.post(
            f"{self.base_url}/embeddings",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={"model": self.model, "input": texts},
            timeout=60.0,
        )
        resp.raise_for_status()
        data = sorted(resp.json()["data"], key=lambda d: d["index"])
        return [d["embedding"] for d in data]


@lru_cache
def get_embedding_provider() -> EmbeddingProvider:
    settings = get_settings()
    if settings.embedding_provider == "openai":
        if not settings.openai_api_key:
            raise RuntimeError("openai_api_key is required when embedding_provider='openai'")
        return OpenAIEmbeddingProvider(
            api_key=settings.openai_api_key,
            model=settings.openai_embedding_model,
            dim=settings.embedding_dim,
            base_url=settings.openai_base_url,
        )
    return FakeEmbeddingProvider(settings.embedding_dim)
