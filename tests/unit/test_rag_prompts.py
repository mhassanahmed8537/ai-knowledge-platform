import uuid

from core.rag.prompts import DEFAULT_RAG_PROMPT, build_system_prompt, extract_citations
from core.retrieval import SearchHit


def _hit(title: str, content: str) -> SearchHit:
    return SearchHit(
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        document_title=title,
        chunk_index=0,
        content=content,
        score=1.0,
    )


def test_sources_are_numbered_and_line_leading() -> None:
    hits = [_hit("A.pdf", "alpha text"), _hit("B.pdf", "beta text")]
    prompt = build_system_prompt(DEFAULT_RAG_PROMPT, hits)

    # Markers must start a line so the model (and the stub) can find them.
    assert "\n[1] (A.pdf) alpha text" in prompt
    assert "\n[2] (B.pdf) beta text" in prompt


def test_no_hits_renders_explicit_none() -> None:
    assert "(none retrieved)" in build_system_prompt(DEFAULT_RAG_PROMPT, [])


def test_extract_citations_maps_markers_to_sources() -> None:
    hits = [_hit("A.pdf", "alpha"), _hit("B.pdf", "beta")]
    citations = extract_citations("Alpha is true [1]. Beta too [2].", hits)

    assert [c.marker for c in citations] == [1, 2]
    assert citations[0].document_title == "A.pdf"
    assert citations[0].chunk_id == str(hits[0].chunk_id)
    assert citations[1].document_title == "B.pdf"


def test_repeated_marker_reported_once() -> None:
    hits = [_hit("A.pdf", "alpha")]
    citations = extract_citations("First [1], again [1], still [1].", hits)
    assert len(citations) == 1


def test_hallucinated_marker_is_dropped() -> None:
    # The model cited [7] but only 2 sources were retrieved.
    hits = [_hit("A.pdf", "alpha"), _hit("B.pdf", "beta")]
    citations = extract_citations("Claim [1] and bogus [7].", hits)
    assert [c.marker for c in citations] == [1]


def test_uncited_answer_yields_no_citations() -> None:
    assert extract_citations("I could not find that.", [_hit("A.pdf", "alpha")]) == []


def test_snippet_is_truncated() -> None:
    hits = [_hit("A.pdf", "x" * 1000)]
    citations = extract_citations("See [1].", hits, snippet_chars=50)
    assert len(citations[0].snippet) == 50
