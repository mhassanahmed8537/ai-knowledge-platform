import uuid

from fpdf import FPDF
from httpx import AsyncClient

from core.ingestion import run_ingestion
from tests.integration._helpers import bearer, signup


def _make_pdf(text: str) -> bytes:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("helvetica", size=12)
    pdf.multi_cell(0, 10, text)
    return bytes(pdf.output())


async def _upload_and_ingest(client: AsyncClient, token: str, text: str) -> uuid.UUID:
    me = await client.get("/auth/me", headers=bearer(token))
    org_id = uuid.UUID(me.json()["org_id"])
    resp = await client.post(
        "/documents/upload",
        headers=bearer(token),
        files={"file": ("doc.pdf", _make_pdf(text), "application/pdf")},
    )
    doc_id = uuid.UUID(resp.json()["id"])
    await run_ingestion(doc_id, org_id)
    return doc_id


async def test_lexical_search_finds_matching_document(client: AsyncClient) -> None:
    tokens = await signup(client)
    token = tokens["access_token"]
    foxes = await _upload_and_ingest(
        client, token, "The quick brown fox leaps over hedgerows in the meadow. " * 20
    )
    await _upload_and_ingest(
        client, token, "Relational databases store rows and columns with indexes. " * 20
    )

    resp = await client.post(
        "/search",
        headers=bearer(token),
        json={"query": "brown fox meadow", "mode": "lexical", "limit": 5},
    )
    assert resp.status_code == 200
    hits = resp.json()
    assert hits, "expected at least one lexical hit"
    assert all(h["document_id"] == str(foxes) for h in hits)
    assert hits == sorted(hits, key=lambda h: h["score"], reverse=True)


async def test_hybrid_and_vector_modes_return_results(client: AsyncClient) -> None:
    tokens = await signup(client)
    token = tokens["access_token"]
    await _upload_and_ingest(
        client, token, "Photosynthesis converts sunlight into chemical energy in plants. " * 20
    )

    for mode in ("hybrid", "vector"):
        resp = await client.post(
            "/search",
            headers=bearer(token),
            json={"query": "sunlight energy plants", "mode": mode},
        )
        assert resp.status_code == 200, mode
        assert resp.json(), f"expected results for mode={mode}"


async def test_search_is_tenant_isolated(client: AsyncClient) -> None:
    owner = await signup(client)
    other = await signup(client)
    await _upload_and_ingest(
        client, owner["access_token"], "Confidential zebra logistics roadmap. " * 20
    )

    resp = await client.post(
        "/search",
        headers=bearer(other["access_token"]),
        json={"query": "zebra logistics roadmap", "mode": "hybrid"},
    )
    assert resp.status_code == 200
    assert resp.json() == []


async def test_empty_query_rejected(client: AsyncClient) -> None:
    tokens = await signup(client)
    resp = await client.post("/search", headers=bearer(tokens["access_token"]), json={"query": ""})
    assert resp.status_code == 422
