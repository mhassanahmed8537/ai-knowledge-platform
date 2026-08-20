import uuid
from decimal import Decimal

from fpdf import FPDF
from httpx import AsyncClient

from core.db import get_sessionmaker, set_org_context
from core.enums import UsageKind
from core.ingestion import run_ingestion
from core.usage import record_usage
from tests.integration._helpers import bearer, signup


def _make_pdf(text: str) -> bytes:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("helvetica", size=12)
    pdf.multi_cell(0, 10, text)
    return bytes(pdf.output())


async def _org_id(client: AsyncClient, token: str) -> uuid.UUID:
    me = await client.get("/auth/me", headers=bearer(token))
    return uuid.UUID(me.json()["org_id"])


async def _chat_once(client: AsyncClient, token: str, message: str = "hi") -> str:
    conv = await client.post("/conversations", headers=bearer(token), json={})
    conv_id = conv.json()["id"]
    resp = await client.post(
        f"/conversations/{conv_id}/messages", headers=bearer(token), json={"message": message}
    )
    assert resp.status_code == 200
    return str(conv_id)


async def test_chat_turn_records_a_generation_usage_event(client: AsyncClient) -> None:
    tokens = await signup(client)
    token = tokens["access_token"]
    conv_id = await _chat_once(client, token)

    events = (await client.get("/usage/events", headers=bearer(token))).json()
    assert len(events) == 1
    event = events[0]
    assert event["kind"] == "generation"
    assert event["provider"] == "stub"
    assert event["conversation_id"] == conv_id
    assert event["input_tokens"] > 0
    assert event["output_tokens"] > 0
    assert Decimal(event["cost_usd"]) == 0  # the stub provider has no pricing entry


async def test_ingestion_records_an_embedding_usage_event(client: AsyncClient) -> None:
    tokens = await signup(client)
    token = tokens["access_token"]
    org_id = await _org_id(client, token)

    resp = await client.post(
        "/documents/upload",
        headers=bearer(token),
        files={"file": ("doc.pdf", _make_pdf("Some content. " * 100), "application/pdf")},
    )
    doc_id = uuid.UUID(resp.json()["id"])
    await run_ingestion(doc_id, org_id)

    events = (await client.get("/usage/events", headers=bearer(token))).json()
    embedding_events = [e for e in events if e["kind"] == "embedding"]
    assert len(embedding_events) == 1
    assert embedding_events[0]["document_id"] == str(doc_id)
    assert embedding_events[0]["provider"] == "fake"
    assert embedding_events[0]["input_tokens"] > 0


async def test_usage_summary_aggregates_by_kind(client: AsyncClient) -> None:
    tokens = await signup(client)
    token = tokens["access_token"]
    await _chat_once(client, token)

    summary = (await client.get("/usage/summary", headers=bearer(token))).json()
    assert "generation" in summary["by_kind"]
    assert summary["by_kind"]["generation"]["output_tokens"] > 0
    assert summary["monthly_budget_usd"] is None
    assert summary["budget_used_pct"] is None
    assert summary["over_budget"] is False


async def test_usage_events_are_tenant_isolated(client: AsyncClient) -> None:
    owner = await signup(client)
    await _chat_once(client, owner["access_token"])

    other = await signup(client)
    other_events = (await client.get("/usage/events", headers=bearer(other["access_token"]))).json()
    assert other_events == []
    other_summary = (
        await client.get("/usage/summary", headers=bearer(other["access_token"]))
    ).json()
    assert Decimal(other_summary["month_to_date_cost_usd"]) == 0


async def test_budget_crossing_fires_only_on_the_crossing_event(client: AsyncClient) -> None:
    tokens = await signup(client)
    token = tokens["access_token"]
    org_id = await _org_id(client, token)

    patch = await client.patch(
        "/organizations/me", headers=bearer(token), json={"monthly_budget_usd": "1.00"}
    )
    assert patch.status_code == 200
    assert Decimal(patch.json()["monthly_budget_usd"]) == Decimal("1.00")

    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session, session.begin():
        await set_org_context(session, org_id)

        async def _spend(cost: str) -> bool:
            _, crossed = await record_usage(
                session,
                org_id=org_id,
                user_id=None,
                kind=UsageKind.GENERATION,
                provider="anthropic",
                model="claude-opus-4-8",
                input_tokens=1000,
                output_tokens=1000,
                cost_usd=Decimal(cost),
            )
            return crossed

        assert await _spend("0.60") is False  # still under the $1 budget
        assert await _spend("0.60") is True  # this one pushes month-to-date over budget
        assert await _spend("0.10") is False  # already over budget; no repeat alert

    summary = (await client.get("/usage/summary", headers=bearer(token))).json()
    assert summary["over_budget"] is True
    assert Decimal(str(summary["budget_used_pct"])) > 100


async def test_only_admin_can_set_budget(client: AsyncClient) -> None:
    admin = await signup(client)
    admin_h = bearer(admin["access_token"])

    created = await client.post(
        "/users",
        headers=admin_h,
        json={"email": f"member-{uuid.uuid4().hex}@itest.dev", "password": "memberpass123"},
    )
    assert created.status_code == 201
    member = await client.post(
        "/auth/login",
        json={"email": created.json()["email"], "password": "memberpass123"},
    )
    member_h = bearer(member.json()["access_token"])

    assert (
        await client.patch(
            "/organizations/me", headers=member_h, json={"monthly_budget_usd": "5.00"}
        )
    ).status_code == 403
    assert (await client.get("/organizations/me", headers=member_h)).status_code == 200
