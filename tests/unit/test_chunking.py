import pytest

from core.chunking import chunk_text, estimate_tokens


def test_empty_text_yields_no_chunks() -> None:
    assert chunk_text("", size=100, overlap=10) == []
    assert chunk_text("   \n  ", size=100, overlap=10) == []


def test_short_text_is_single_chunk() -> None:
    chunks = chunk_text("hello world", size=100, overlap=10)
    assert chunks == ["hello world"]


def test_long_text_splits_with_overlap() -> None:
    words = " ".join(f"word{i}" for i in range(200))
    chunks = chunk_text(words, size=100, overlap=20)

    assert len(chunks) > 1
    assert all(len(c) <= 100 for c in chunks)
    # Overlap: the tail of one chunk reappears at the head of the next.
    first_tail = chunks[0].split(" ")[-1]
    assert first_tail in chunks[1]


def test_invalid_params() -> None:
    with pytest.raises(ValueError):
        chunk_text("x", size=0, overlap=0)
    with pytest.raises(ValueError):
        chunk_text("x", size=10, overlap=10)


def test_estimate_tokens_monotonic() -> None:
    assert estimate_tokens("a") >= 1
    assert estimate_tokens("a" * 400) > estimate_tokens("a" * 40)
