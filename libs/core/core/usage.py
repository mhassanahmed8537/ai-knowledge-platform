"""Usage-event recording and per-tenant budget tracking (Phase 5).

Written as plain async functions (same philosophy as ``core.ingestion``) so
both the chat endpoint and the ingestion pipeline can call them directly, and
integration tests can drive them without a Celery worker.
"""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.enums import UsageKind
from core.models import Organization, UsageEvent


def _month_start(now: datetime | None = None) -> datetime:
    now = now or datetime.now(UTC)
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


async def month_to_date_cost_usd(session: AsyncSession, org_id: uuid.UUID) -> Decimal:
    total = await session.scalar(
        select(func.sum(UsageEvent.cost_usd)).where(
            UsageEvent.org_id == org_id,
            UsageEvent.created_at >= _month_start(),
        )
    )
    return total if total is not None else Decimal("0")


async def record_usage(
    session: AsyncSession,
    *,
    org_id: uuid.UUID,
    user_id: uuid.UUID | None,
    kind: UsageKind,
    provider: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    cost_usd: Decimal,
    conversation_id: uuid.UUID | None = None,
    document_id: uuid.UUID | None = None,
) -> tuple[UsageEvent, bool]:
    """Insert a usage event; returns ``(event, budget_just_crossed)``.

    ``budget_just_crossed`` is true only on the one event that pushes
    month-to-date spend from under the org's budget to at-or-over it, so a
    caller that fires a webhook on it sends at most one alert per monthly
    cycle rather than one per request thereafter.
    """
    prior_cost = await month_to_date_cost_usd(session, org_id)

    event = UsageEvent(
        org_id=org_id,
        user_id=user_id,
        kind=kind,
        provider=provider,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=cost_usd,
        conversation_id=conversation_id,
        document_id=document_id,
    )
    session.add(event)
    await session.flush()
    await session.refresh(event)

    org = await session.get(Organization, org_id)
    budget = org.monthly_budget_usd if org is not None else None
    crossed = budget is not None and prior_cost < budget <= (prior_cost + cost_usd)
    return event, crossed
