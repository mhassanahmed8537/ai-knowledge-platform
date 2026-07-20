"""Pluggable embedding providers.

The fake provider is the zero-cost dev default: deterministic (same text always
maps to the same unit vector), so retrieval is reproducible in tests. The OpenAI
provider implements the identical interface and activates via config once a key
is present — no schema or call-site change needed.
"""

import hashlib
import math
import random
from functools import lru_cache
from typing import Protocol, runtime_checkable

from core.config import get_settings


@runtime_checkable
class EmbeddingProvider(Protocol):
    dim: int

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class FakeEmbeddingProvider:
    def __init__(self, dim: int) -> None:
        self.dim = dim

    def _vector(self, text: str) -> list[float]:
        seed = int.from_bytes(hashlib.sha256(text.encode()).digest(), "big")
        rng = random.Random(seed)
        values = [rng.gauss(0.0, 1.0) for _ in range(self.dim)]
        norm = math.sqrt(sum(v * v for v in values)) or 1.0
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
