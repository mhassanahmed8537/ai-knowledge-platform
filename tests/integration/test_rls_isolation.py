from httpx import AsyncClient

from tests.integration._helpers import bearer, signup


async def test_documents_are_isolated_between_tenants(client: AsyncClient) -> None:
    acme = await signup(client)
    globex = await signup(client)
    acme_h = bearer(acme["access_token"])
    globex_h = bearer(globex["access_token"])

    r1 = await client.post("/documents", headers=acme_h, json={"title": "Acme Only"})
    assert r1.status_code == 201
    r2 = await client.post("/documents", headers=globex_h, json={"title": "Globex Only"})
    assert r2.status_code == 201
    globex_doc_id = r2.json()["id"]

    acme_docs = await client.get("/documents", headers=acme_h)
    titles = {d["title"] for d in acme_docs.json()}
    assert titles == {"Acme Only"}

    globex_docs = await client.get("/documents", headers=globex_h)
    assert {d["title"] for d in globex_docs.json()} == {"Globex Only"}

    # Acme cannot fetch Globex's document by id — RLS makes it a 404.
    cross = await client.get(f"/documents/{globex_doc_id}", headers=acme_h)
    assert cross.status_code == 404


async def test_cross_tenant_update_and_delete_are_404(client: AsyncClient) -> None:
    owner = await signup(client)
    other = await signup(client)
    owner_h = bearer(owner["access_token"])
    other_h = bearer(other["access_token"])

    created = await client.post("/documents", headers=owner_h, json={"title": "secret"})
    doc_id = created.json()["id"]

    patched = await client.patch(
        f"/documents/{doc_id}", headers=other_h, json={"title": "hijacked"}
    )
    assert patched.status_code == 404

    deleted = await client.delete(f"/documents/{doc_id}", headers=other_h)
    assert deleted.status_code == 404
