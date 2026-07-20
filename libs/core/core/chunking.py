"""Dependency-free text chunking for ingestion.

A word-boundary sliding window: greedily packs words up to ``size`` characters,
then starts the next chunk with a trailing overlap so context spans boundaries.
Good enough for RAG retrieval and swappable for a semantic splitter later.
"""

import re


def estimate_tokens(text: str) -> int:
    # Rough heuristic (~4 chars/token) — avoids a tokenizer dependency.
    return max(1, len(text) // 4)


def _normalize(text: str) -> str:
    # Collapse runs of whitespace but keep single spaces between words.
    return re.sub(r"\s+", " ", text).strip()


def chunk_text(text: str, *, size: int, overlap: int) -> list[str]:
    if size <= 0:
        raise ValueError("size must be positive")
    if not 0 <= overlap < size:
        raise ValueError("overlap must satisfy 0 <= overlap < size")

    normalized = _normalize(text)
    if not normalized:
        return []

    words = normalized.split(" ")
    chunks: list[str] = []
    current: list[str] = []
    length = 0

    for word in words:
        added = len(word) + (1 if current else 0)
        if length + added > size and current:
            chunk = " ".join(current)
            chunks.append(chunk)
            # Carry an overlap tail (by characters) into the next chunk.
            tail: list[str] = []
            tail_len = 0
            for w in reversed(current):
                if tail_len + len(w) + 1 > overlap:
                    break
                tail.insert(0, w)
                tail_len += len(w) + 1
            current = tail
            length = sum(len(w) + 1 for w in current)
        current.append(word)
        length += added

    if current:
        chunks.append(" ".join(current))
    return chunks
