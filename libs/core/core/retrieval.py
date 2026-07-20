"""Hybrid retrieval: lexical (Postgres FTS / BM25-style) + vector (pgvector),
combined with Reciprocal Rank Fusion.

Everything runs on the caller's RLS-bound session, so results are automatically
scoped to the tenant. RRF is score-scale agnostic: it fuses the two ranked id
lists by rank position, so the very different score ranges of ts_rank_cd and
cosine distance never need to be normalised against each other.
"""

import asyncio
import enum
import uuid
from dataclasses import dataclass

from sqlalchemy import Float, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import get_settings
from core.models import Document, DocumentChunk
from core.providers.embeddings import get_embedding_provider


class SearchMode(enum.StrEnum):
    HYBRID = "hybrid"
    VECTOR = "vector"
    LEXICAL = "lexical"


@dataclass
class SearchHit:
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    document_title: str
    chunk_index: int
    content: str
    score: float


async def _vector_ranked_ids(
    session: AsyncSession, query_vector: list[float], k: int
) -> list[uuid.UUID]:
    distance = DocumentChunk.embedding.cosine_distance(query_vector)
    stmt = select(DocumentChunk.id).order_by(distance.asc()).limit(k)
    return list((await session.scalars(stmt)).all())


async def _lexical_ranked_ids(session: AsyncSession, query: str, k: int) -> list[uuid.UUID]:
    tsquery = func.plainto_tsquery("english", query)
    rank = func.ts_rank_cd(DocumentChunk.content_tsv, tsquery).cast(Float)
    stmt = (
        select(DocumentChunk.id)
        .where(DocumentChunk.content_tsv.op("@@")(tsquery))
        .order_by(rank.desc())
        .limit(k)
    )
    return list((await session.scalars(stmt)).all())


def reciprocal_rank_fusion(
    rankings: list[list[uuid.UUID]], *, rrf_k: int
) -> list[tuple[uuid.UUID, float]]:
    """Fuse ranked id lists. Score = sum over lists of 1 / (rrf_k + rank)."""
    scores: dict[uuid.UUID, float] = {}
    for ranking in rankings:
        for position, item_id in enumerate(ranking):
            scores[item_id] = scores.get(item_id, 0.0) + 1.0 / (rrf_k + position + 1)
    return sorted(scores.items(), key=lambda kv: kv[1], reverse=True)


async def hybrid_search(
    session: AsyncSession,
    query: str,
    *,
    mode: SearchMode = SearchMode.HYBRID,
    limit: int | None = None,
) -> list[SearchHit]:
    settings = get_settings()
    limit = limit or settings.search_default_limit
    k = settings.retrieval_candidate_k

    rankings: list[list[uuid.UUID]] = []
    if mode in (SearchMode.HYBRID, SearchMode.VECTOR):
        provider = get_embedding_provider()
        query_vector = (await asyncio.to_thread(provider.embed, [query]))[0]
        rankings.append(await _vector_ranked_ids(session, query_vector, k))
    if mode in (SearchMode.HYBRID, SearchMode.LEXICAL):
        rankings.append(await _lexical_ranked_ids(session, query, k))

    fused = reciprocal_rank_fusion(rankings, rrf_k=settings.rrf_k)[:limit]
    if not fused:
        return []

    order = {chunk_id: rank for rank, (chunk_id, _) in enumerate(fused)}
    score_by_id = dict(fused)
    ids = [chunk_id for chunk_id, _ in fused]

    rows = (
        await session.execute(
            select(DocumentChunk, Document.title)
            .join(Document, Document.id == DocumentChunk.document_id)
            .where(DocumentChunk.id.in_(ids))
        )
    ).all()

    hits = [
        SearchHit(
            chunk_id=chunk.id,
            document_id=chunk.document_id,
            document_title=title,
            chunk_index=chunk.chunk_index,
            content=chunk.content,
            score=score_by_id[chunk.id],
        )
        for chunk, title in rows
    ]
    hits.sort(key=lambda h: order[h.chunk_id])
    return hits
