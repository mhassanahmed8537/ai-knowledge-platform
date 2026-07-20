import json
import uuid

from fpdf import FPDF
from httpx import AsyncClient

from core.ingestion import run_ingestion
from tests.integration._helpers import bearer, signup

TOPIC = "Photosynthesis converts sunlight into chemical energy stored in glucose. "


def _make_pdf(text: str) -> bytes:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("helvetica", size=12)
    pdf.multi_cell(0, 10, text)
    return bytes(pdf.output())


async def _seeded_org(client: AsyncClient) -> str:
    """Sign up, ingest one document, and return the access token."""
    tokens = await signup(client)
    token = tokens["access_token"]
    me = await client.get("/auth/me", headers=bearer(token))
    org_id = uuid.UUID(me.json()["org_id"])

    resp = await client.post(
        "/documents/upload",
        headers=bearer(token),
        files={"file": ("bio.pdf", _make_pdf(TOPIC * 20), "application/pdf")},
    )
    await run_ingestion(uuid.UUID(resp.json()["id"]), org_id)
    return token


def _parse_sse(body: str) -> list[tuple[str, dict]]:
    events: list[tuple[str, dict]] = []
    for block in body.strip().split("\n\n"):
        if not block.strip():
            continue
        name, payload = None, None
        for line in block.splitlines():
            if line.startswith("event: "):
                name = line[len("event: ") :]
            elif line.startswith("data: "):
                payload = json.loads(line[len("data: ") :])
        if name is not None and payload is not None:
            events.append((name, payload))
    return events


async def test_chat_streams_tokens_and_citations(client: AsyncClient) -> None:
    token = await _seeded_org(client)
    conv = await client.post("/conversations", headers=bearer(token), json={"title": "bio"})
    assert conv.status_code == 201
    conv_id = conv.json()["id"]

    resp = await client.post(
        f"/conversations/{conv_id}/messages",
        headers=bearer(token),
        json={"message": "How does photosynthesis store energy?"},
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")

    events = _parse_sse(resp.text)
    kinds = [name for name, _ in events]
    assert kinds.count("token") > 1, "expected a genuinely streamed answer"
    assert kinds[-2:] == ["citations", "done"]

    citations = next(p["citations"] for name, p in events if name == "citations")
    assert citations, "expected at least one resolved citation"
    first = citations[0]
    assert first["marker"] == 1
    assert first["document_title"] == "bio.pdf"
    assert uuid.UUID(first["chunk_id"])  # resolves to a real chunk


async def test_history_is_persisted_and_replayed(client: AsyncClient) -> None:
    token = await _seeded_org(client)
    conv_id = (await client.post("/conversations", headers=bearer(token), json={})).json()["id"]

    await client.post(
        f"/conversations/{conv_id}/messages",
        headers=bearer(token),
        json={"message": "first question"},
    )
    await client.post(
        f"/conversations/{conv_id}/messages",
        headers=bearer(token),
        json={"message": "second question"},
    )

    messages = (
        await client.get(f"/conversations/{conv_id}/messages", headers=bearer(token))
    ).json()
    roles = [m["role"] for m in messages]
    assert roles == ["user", "assistant", "user", "assistant"]
    assert messages[0]["content"] == "first question"
    # Assistant turns persist their citations for replay.
    assert messages[1]["citations"] is not None


async def test_conversations_are_tenant_isolated(client: AsyncClient) -> None:
    owner_token = await _seeded_org(client)
    other = await signup(client)
    conv_id = (await client.post("/conversations", headers=bearer(owner_token), json={})).json()[
        "id"
    ]

    other_h = bearer(other["access_token"])
    assert (
        await client.get(f"/conversations/{conv_id}/messages", headers=other_h)
    ).status_code == 404
    cross = await client.post(
        f"/conversations/{conv_id}/messages", headers=other_h, json={"message": "leak?"}
    )
    assert cross.status_code == 404
    assert (await client.get("/conversations", headers=other_h)).json() == []


async def test_empty_message_rejected(client: AsyncClient) -> None:
    token = await _seeded_org(client)
    conv_id = (await client.post("/conversations", headers=bearer(token), json={})).json()["id"]
    resp = await client.post(
        f"/conversations/{conv_id}/messages", headers=bearer(token), json={"message": ""}
    )
    assert resp.status_code == 422
