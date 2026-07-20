"""LangGraph orchestration for the RAG pipeline: retrieve -> generate -> cite.

The graph is compiled once at import. Per-request state carries the RLS-bound
session, so retrieval and prompt resolution are automatically tenant-scoped.

Tokens are streamed out of the ``generate`` node via LangGraph's custom stream
writer, so callers can consume ``stream_mode=["custom", "values"]`` to get live
tokens *and* the final state (answer + resolved citations) from one run.
"""

from collections.abc import AsyncIterator
from typing import Any, TypedDict

from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import get_settings
from core.providers.llm import get_llm_provider
from core.rag.prompts import (
    Citation,
    build_system_prompt,
    extract_citations,
    resolve_prompt_template,
)
from core.retrieval import SearchHit, SearchMode, hybrid_search


class RAGState(TypedDict, total=False):
    # Inputs
    session: AsyncSession
    query: str
    history: list[dict[str, str]]
    # Derived
    hits: list[SearchHit]
    system_prompt: str
    answer: str
    citations: list[Citation]


async def retrieve_node(state: RAGState) -> dict[str, Any]:
    settings = get_settings()
    hits = await hybrid_search(
        state["session"],
        state["query"],
        mode=SearchMode.HYBRID,
        limit=settings.generation_context_chunks,
    )
    system_prompt = build_system_prompt(await resolve_prompt_template(state["session"]), hits)
    return {"hits": hits, "system_prompt": system_prompt}


async def generate_node(state: RAGState) -> dict[str, Any]:
    writer = get_stream_writer()
    provider = get_llm_provider()
    messages = [*state.get("history", []), {"role": "user", "content": state["query"]}]

    parts: list[str] = []
    async for token in provider.astream(system=state["system_prompt"], messages=messages):
        parts.append(token)
        writer({"token": token})
    return {"answer": "".join(parts)}


async def cite_node(state: RAGState) -> dict[str, Any]:
    return {"citations": extract_citations(state["answer"], state.get("hits", []))}


def _build() -> Any:
    graph = StateGraph(RAGState)
    graph.add_node("retrieve", retrieve_node)
    graph.add_node("generate", generate_node)
    graph.add_node("cite", cite_node)
    graph.add_edge(START, "retrieve")
    graph.add_edge("retrieve", "generate")
    graph.add_edge("generate", "cite")
    graph.add_edge("cite", END)
    return graph.compile()


rag_graph = _build()


async def stream_answer(
    session: AsyncSession, query: str, history: list[dict[str, str]] | None = None
) -> AsyncIterator[tuple[str, Any]]:
    """Run the pipeline, yielding ("token", str) then a final ("done", state).

    Consumers (the SSE endpoint) forward tokens as they arrive and emit the
    citations once the graph completes.
    """
    initial: RAGState = {
        "session": session,
        "query": query,
        "history": history or [],
    }
    final: dict[str, Any] = {}
    async for mode, chunk in rag_graph.astream(initial, stream_mode=["custom", "values"]):
        if mode == "custom":
            yield "token", chunk["token"]
        elif mode == "values":
            final = chunk
    yield "done", final
