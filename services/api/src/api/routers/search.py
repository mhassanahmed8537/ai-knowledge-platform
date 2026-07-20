from fastapi import APIRouter, Depends

from api.deps import Principal, get_principal
from api.schemas import SearchHitOut, SearchRequest
from core.retrieval import hybrid_search

router = APIRouter(prefix="/search", tags=["search"])


@router.post("", response_model=list[SearchHitOut])
async def search(
    body: SearchRequest,
    principal: Principal = Depends(get_principal),
) -> list[SearchHitOut]:
    hits = await hybrid_search(principal.session, body.query, mode=body.mode, limit=body.limit)
    return [
        SearchHitOut(
            chunk_id=h.chunk_id,
            document_id=h.document_id,
            document_title=h.document_title,
            chunk_index=h.chunk_index,
            content=h.content,
            score=h.score,
        )
        for h in hits
    ]
