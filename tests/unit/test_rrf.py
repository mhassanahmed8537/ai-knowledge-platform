import uuid

from core.retrieval import reciprocal_rank_fusion

A = uuid.UUID("00000000-0000-0000-0000-0000000000a1")
B = uuid.UUID("00000000-0000-0000-0000-0000000000b2")
C = uuid.UUID("00000000-0000-0000-0000-0000000000c3")


def test_item_ranked_high_in_both_lists_wins() -> None:
    vector = [A, B, C]
    lexical = [A, C, B]
    fused = reciprocal_rank_fusion([vector, lexical], rrf_k=60)
    assert fused[0][0] == A  # top of both lists


def test_agreement_beats_single_list_top() -> None:
    # B is #1 in one list only; A is #2 in both -> A's combined score wins.
    vector = [A, B]
    lexical = [A, C]
    fused = reciprocal_rank_fusion([vector, lexical], rrf_k=60)
    order = [item for item, _ in fused]
    assert order[0] == A


def test_single_ranking_preserves_order() -> None:
    fused = reciprocal_rank_fusion([[C, B, A]], rrf_k=60)
    assert [item for item, _ in fused] == [C, B, A]


def test_empty_input() -> None:
    assert reciprocal_rank_fusion([], rrf_k=60) == []
    assert reciprocal_rank_fusion([[]], rrf_k=60) == []
