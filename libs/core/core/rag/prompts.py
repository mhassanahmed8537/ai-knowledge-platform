"""Prompt construction and citation extraction for grounded answers.

Sources are rendered as line-leading ``[n]`` markers so the model can cite them
inline; ``extract_citations`` maps those markers back to the exact chunk and
document they came from, which is what the API returns alongside the answer.
"""

import re
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.models import PromptTemplate
from core.retrieval import SearchHit

DEFAULT_PROMPT_NAME = "rag"

DEFAULT_RAG_PROMPT = """You are a knowledge assistant. Answer the user's question \
using ONLY the numbered sources below.

Rules:
- Cite every claim with the bracketed marker of the source it came from, e.g. [1].
- If several sources support a claim, cite each one, e.g. [1][3].
- If the sources do not contain the answer, say so plainly. Do not invent facts.
- Be concise and answer directly."""

# Markers are emitted line-leading, so anchor to line start when listing sources.
_CITATION_RE = re.compile(r"\[(\d+)\]")


@dataclass
class Citation:
    marker: int
    chunk_id: str
    document_id: str
    document_title: str
    snippet: str


def build_system_prompt(template: str, hits: list[SearchHit]) -> str:
    """Render the system prompt with numbered, citable sources."""
    if not hits:
        return f"{template}\n\nSources:\n(none retrieved)"
    sources = "\n\n".join(
        f"[{i}] ({hit.document_title}) {hit.content}" for i, hit in enumerate(hits, start=1)
    )
    return f"{template}\n\nSources:\n{sources}"


def extract_citations(
    answer: str, hits: list[SearchHit], *, snippet_chars: int = 240
) -> list[Citation]:
    """Map the ``[n]`` markers actually used in the answer back to their sources.

    Markers outside the range of retrieved sources (a hallucinated citation) are
    ignored rather than surfaced, and each source is reported at most once.
    """
    seen: set[int] = set()
    citations: list[Citation] = []
    for raw in _CITATION_RE.findall(answer):
        marker = int(raw)
        if marker in seen or not 1 <= marker <= len(hits):
            continue
        seen.add(marker)
        hit = hits[marker - 1]
        citations.append(
            Citation(
                marker=marker,
                chunk_id=str(hit.chunk_id),
                document_id=str(hit.document_id),
                document_title=hit.document_title,
                snippet=hit.content[:snippet_chars],
            )
        )
    return sorted(citations, key=lambda c: c.marker)


async def resolve_prompt_template(session: AsyncSession, *, name: str = DEFAULT_PROMPT_NAME) -> str:
    """Return the tenant's active prompt version, or the built-in default.

    RLS scopes the lookup to the caller's org, so tenants can override the
    system prompt without seeing each other's.
    """
    row = await session.scalar(
        select(PromptTemplate).where(
            PromptTemplate.name == name,
            PromptTemplate.is_active.is_(True),
        )
    )
    return row.content if row is not None else DEFAULT_RAG_PROMPT
