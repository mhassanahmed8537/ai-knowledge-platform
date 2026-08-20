"""Per-tenant usage analytics and cost tracking (Phase 5).

All queries run on the RLS-bound principal session, so — as with every other
router — no explicit ``org_id`` filter is needed: Postgres enforces the tenant
boundary.
"""

from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select

from api.deps import Principal, get_principal
from api.schemas import UsageEventOut, UsageKindTotals, UsageSummaryOut
from core.models import Organization, UsageEvent
from core.usage import month_to_date_cost_usd

router = APIRouter(prefix="/usage", tags=["usage"])


@router.get("/summary", response_model=UsageSummaryOut)
async def get_usage_summary(principal: Principal = Depends(get_principal)) -> UsageSummaryOut:
    session = principal.session
    org = await session.get(Organization, principal.org_id)
    budget = org.monthly_budget_usd if org is not None else None
    mtd_cost = await month_to_date_cost_usd(session, principal.org_id)

    rows = (
        await session.execute(
            select(
                UsageEvent.kind,
                func.coalesce(func.sum(UsageEvent.input_tokens), 0),
                func.coalesce(func.sum(UsageEvent.output_tokens), 0),
                func.coalesce(func.sum(UsageEvent.cost_usd), 0),
            ).group_by(UsageEvent.kind)
        )
    ).all()
    by_kind = {
        kind: UsageKindTotals(
            input_tokens=int(input_tokens),
            output_tokens=int(output_tokens),
            cost_usd=Decimal(cost),
        )
        for kind, input_tokens, output_tokens, cost in rows
    }

    return UsageSummaryOut(
        month_to_date_cost_usd=mtd_cost,
        monthly_budget_usd=budget,
        budget_used_pct=float(mtd_cost / budget * 100) if budget and budget > 0 else None,
        over_budget=budget is not None and mtd_cost >= budget,
        by_kind=by_kind,
    )


@router.get("/events", response_model=list[UsageEventOut])
async def list_usage_events(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    principal: Principal = Depends(get_principal),
) -> list[UsageEvent]:
    result = await principal.session.scalars(
        select(UsageEvent).order_by(UsageEvent.created_at.desc()).limit(limit).offset(offset)
    )
    return list(result.all())
