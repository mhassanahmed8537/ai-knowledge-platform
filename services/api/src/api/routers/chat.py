"""Conversations and the streaming RAG chat endpoint.

Streaming note: a StreamingResponse body is produced *after* the endpoint
returns, by which point the request-scoped session from ``get_principal`` has
already committed and closed. The generator therefore opens its own session and
re-binds the org context in every transaction — ``set_config(..., is_local)`` is
transaction-scoped, so it must be set again after each commit.
"""

import json
import uuid
from collections.abc import AsyncIterator
from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import Principal, get_principal
from api.schemas import ChatRequest, ConversationCreate, ConversationOut, MessageOut
from api.tasks import enqueue_webhook_event
from core.config import get_settings
from core.db import get_sessionmaker, set_org_context
from core.enums import MessageRole, UsageKind, WebhookEvent
from core.models import Conversation, Message
from core.providers.llm import UsageAccumulator
from core.providers.pricing import generation_cost_usd
from core.rag.graph import stream_answer
from core.usage import record_usage

router = APIRouter(prefix="/conversations", tags=["chat"])


def _sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


async def _get_conversation(session: AsyncSession, conversation_id: uuid.UUID) -> Conversation:
    # RLS scopes this to the caller's org, so a cross-tenant id yields 404.
    conv = await session.scalar(select(Conversation).where(Conversation.id == conversation_id))
    if conv is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    return conv


@router.post("", response_model=ConversationOut, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    body: ConversationCreate,
    principal: Principal = Depends(get_principal),
) -> Conversation:
    conv = Conversation(org_id=principal.org_id, user_id=principal.user.id, title=body.title)
    principal.session.add(conv)
    await principal.session.flush()
    await principal.session.refresh(conv)
    return conv


@router.get("", response_model=list[ConversationOut])
async def list_conversations(
    principal: Principal = Depends(get_principal),
) -> list[Conversation]:
    result = await principal.session.scalars(
        select(Conversation).order_by(Conversation.created_at.desc())
    )
    return list(result.all())


@router.get("/{conversation_id}/messages", response_model=list[MessageOut])
async def list_messages(
    conversation_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
) -> list[Message]:
    await _get_conversation(principal.session, conversation_id)
    result = await principal.session.scalars(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at)
    )
    return list(result.all())


@router.post("/{conversation_id}/messages")
async def chat(
    conversation_id: uuid.UUID,
    body: ChatRequest,
    principal: Principal = Depends(get_principal),
) -> StreamingResponse:
    """Stream a grounded answer as SSE: `token`* then `citations` then `done`."""
    settings = get_settings()
    await _get_conversation(principal.session, conversation_id)

    # Load prior turns while the request-scoped session is still open.
    prior = await principal.session.scalars(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at)
    )
    history = [{"role": m.role.value, "content": m.content} for m in prior.all()][
        -settings.max_history_messages :
    ]
    org_id = principal.org_id
    user_id = principal.user.id
    question = body.message

    async def event_stream() -> AsyncIterator[str]:
        sessionmaker = get_sessionmaker()
        async with sessionmaker() as session:
            # Persist the user turn in its own transaction so it survives a
            # client disconnect mid-generation.
            async with session.begin():
                await set_org_context(session, org_id)
                session.add(
                    Message(
                        org_id=org_id,
                        conversation_id=conversation_id,
                        role=MessageRole.USER,
                        content=question,
                    )
                )

            parts: list[str] = []
            citations: list[dict[str, Any]] = []
            final_state: dict[str, Any] = {}
            budget_crossed = False
            async with session.begin():
                await set_org_context(session, org_id)  # SET LOCAL is per-transaction
                async for kind, payload in stream_answer(session, question, history):
                    if kind == "token":
                        parts.append(payload)
                        yield _sse("token", {"text": payload})
                    else:
                        final_state = payload
                        citations = [asdict(c) for c in final_state.get("citations", [])]

                answer = "".join(parts)
                session.add(
                    Message(
                        org_id=org_id,
                        conversation_id=conversation_id,
                        role=MessageRole.ASSISTANT,
                        content=answer,
                        citations=citations or None,
                    )
                )

                usage: UsageAccumulator = final_state.get("usage") or UsageAccumulator()
                cost = generation_cost_usd(
                    final_state.get("llm_provider", ""),
                    final_state.get("llm_model", ""),
                    usage.input_tokens,
                    usage.output_tokens,
                )
                _, budget_crossed = await record_usage(
                    session,
                    org_id=org_id,
                    user_id=user_id,
                    kind=UsageKind.GENERATION,
                    provider=final_state.get("llm_provider", ""),
                    model=final_state.get("llm_model", ""),
                    input_tokens=usage.input_tokens,
                    output_tokens=usage.output_tokens,
                    cost_usd=cost,
                    conversation_id=conversation_id,
                )

            if budget_crossed:
                enqueue_webhook_event(
                    org_id,
                    WebhookEvent.BUDGET_ALERT.value,
                    {"conversation_id": str(conversation_id)},
                )

            yield _sse("citations", {"citations": citations})
            yield _sse("done", {"length": len(answer)})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
