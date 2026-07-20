import uuid

from fpdf import FPDF
from httpx import AsyncClient

from core.ingestion import run_ingestion
from tests.integration._helpers import bearer, signup

MARKER = "ZanzibarQuokka distinctive marker phrase for retrieval."


def _make_pdf(text: str) -> bytes:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("helvetica", size=12)
    pdf.multi_cell(0, 10, text)
    return bytes(pdf.output())


async def _org_id(client: AsyncClient, token: str) -> uuid.UUID:
    me = await client.get("/auth/me", headers=bearer(token))
    return uuid.UUID(me.json()["org_id"])


async def test_pdf_upload_and_ingestion(client: AsyncClient) -> None:
    tokens = await signup(client)
    headers = bearer(tokens["access_token"])
    org_id = await _org_id(client, tokens["access_token"])

    pdf = _make_pdf(f"{MARKER}\n\n" + "Filler sentence. " * 200)
    resp = await client.post(
        "/documents/upload",
        headers=headers,
        files={"file": ("sample.pdf", pdf, "application/pdf")},
    )
    assert resp.status_code == 201, resp.text
    doc = resp.json()
    assert doc["status"] == "pending"
    doc_id = uuid.UUID(doc["id"])

    # Drive ingestion directly (in a running system the Celery worker does this).
    n_chunks = await run_ingestion(doc_id, org_id)
    assert n_chunks >= 1

    ready = await client.get(f"/documents/{doc_id}", headers=headers)
    assert ready.json()["status"] == "ready"

    chunks = await client.get(f"/documents/{doc_id}/chunks", headers=headers)
    assert chunks.status_code == 200
    bodies = [c["content"] for c in chunks.json()]
    assert len(bodies) == n_chunks
    assert any("ZanzibarQuokka" in b for b in bodies)


async def test_non_pdf_upload_rejected(client: AsyncClient) -> None:
    tokens = await signup(client)
    headers = bearer(tokens["access_token"])
    resp = await client.post(
        "/documents/upload",
        headers=headers,
        files={"file": ("notes.txt", b"hello", "text/plain")},
    )
    assert resp.status_code == 415


async def test_chunks_are_tenant_isolated(client: AsyncClient) -> None:
    owner = await signup(client)
    other = await signup(client)
    owner_h = bearer(owner["access_token"])
    org_id = await _org_id(client, owner["access_token"])

    pdf = _make_pdf(MARKER)
    resp = await client.post(
        "/documents/upload",
        headers=owner_h,
        files={"file": ("sample.pdf", pdf, "application/pdf")},
    )
    doc_id = uuid.UUID(resp.json()["id"])
    await run_ingestion(doc_id, org_id)

    # The other tenant cannot even see the document, let alone its chunks.
    cross = await client.get(f"/documents/{doc_id}/chunks", headers=bearer(other["access_token"]))
    assert cross.status_code == 404
