from decimal import Decimal

from core.providers.pricing import embedding_cost_usd, generation_cost_usd


def test_generation_cost_known_model() -> None:
    # gpt-4o-mini: $0.15 / 1M input, $0.60 / 1M output.
    cost = generation_cost_usd("openai", "gpt-4o-mini", 1_000_000, 1_000_000)
    assert cost == Decimal("0.75")


def test_generation_cost_unknown_pair_is_free() -> None:
    assert generation_cost_usd("stub", "stub", 1_000_000, 1_000_000) == Decimal("0")
    assert generation_cost_usd("anthropic", "some-future-model", 100, 100) == Decimal("0")


def test_generation_cost_zero_tokens() -> None:
    assert generation_cost_usd("openai", "gpt-4o-mini", 0, 0) == Decimal("0")


def test_embedding_cost_known_model() -> None:
    # text-embedding-3-small: $0.02 / 1M tokens.
    cost = embedding_cost_usd("openai", "text-embedding-3-small", 1_000_000)
    assert cost == Decimal("0.02")


def test_embedding_cost_unknown_pair_is_free() -> None:
    assert embedding_cost_usd("fake", "fake", 1_000_000) == Decimal("0")
