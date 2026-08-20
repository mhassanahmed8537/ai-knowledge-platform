"""USD pricing for usage-based cost tracking.

Prices are static snapshots (per 1M tokens) baked in at release time — keep
them in sync with vendor pricing pages as models change. An unrecognised
(provider, model) pair — including the zero-cost "stub"/"fake" dev defaults —
prices at $0 rather than raising, so cost tracking degrades gracefully instead
of blocking generation or ingestion.
"""

from decimal import Decimal

_PER_MILLION = Decimal(1_000_000)

# (provider, model) -> (input $ / 1M tokens, output $ / 1M tokens)
_GENERATION_PRICING: dict[tuple[str, str], tuple[Decimal, Decimal]] = {
    ("anthropic", "claude-opus-4-8"): (Decimal("15.00"), Decimal("75.00")),
    ("openai", "gpt-4o-mini"): (Decimal("0.15"), Decimal("0.60")),
    ("gemini", "gemini-2.5-flash"): (Decimal("0.30"), Decimal("2.50")),
}

# (provider, model) -> $ / 1M tokens (embeddings have no separate output price)
_EMBEDDING_PRICING: dict[tuple[str, str], Decimal] = {
    ("openai", "text-embedding-3-small"): Decimal("0.02"),
    ("gemini", "gemini-embedding-001"): Decimal("0.15"),
}


def generation_cost_usd(
    provider: str, model: str, input_tokens: int, output_tokens: int
) -> Decimal:
    prices = _GENERATION_PRICING.get((provider, model))
    if prices is None:
        return Decimal("0")
    input_price, output_price = prices
    return (Decimal(input_tokens) * input_price + Decimal(output_tokens) * output_price) / (
        _PER_MILLION
    )


def embedding_cost_usd(provider: str, model: str, tokens: int) -> Decimal:
    price = _EMBEDDING_PRICING.get((provider, model))
    if price is None:
        return Decimal("0")
    return Decimal(tokens) * price / _PER_MILLION
