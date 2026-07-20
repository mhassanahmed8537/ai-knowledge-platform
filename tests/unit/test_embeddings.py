import math

from core.providers.embeddings import FakeEmbeddingProvider


def test_fake_embeddings_have_correct_dim() -> None:
    provider = FakeEmbeddingProvider(dim=1536)
    vectors = provider.embed(["hello", "world"])
    assert len(vectors) == 2
    assert all(len(v) == 1536 for v in vectors)


def test_fake_embeddings_are_deterministic() -> None:
    a = FakeEmbeddingProvider(dim=64).embed(["same text"])[0]
    b = FakeEmbeddingProvider(dim=64).embed(["same text"])[0]
    assert a == b


def test_fake_embeddings_are_unit_normalized() -> None:
    v = FakeEmbeddingProvider(dim=128).embed(["something"])[0]
    norm = math.sqrt(sum(x * x for x in v))
    assert abs(norm - 1.0) < 1e-9


def test_different_texts_differ() -> None:
    provider = FakeEmbeddingProvider(dim=64)
    assert provider.embed(["a"])[0] != provider.embed(["b"])[0]
