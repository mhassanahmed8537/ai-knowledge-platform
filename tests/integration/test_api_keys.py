from httpx import AsyncClient

from tests.integration._helpers import bearer, signup


async def test_api_key_lifecycle(client: AsyncClient) -> None:
    admin = await signup(client)
    admin_h = bearer(admin["access_token"])

    created = await client.post("/api-keys", headers=admin_h, json={"name": "ci"})
    assert created.status_code == 201
    body = created.json()
    key = body["key"]
    key_id = body["id"]
    assert key  # plaintext returned exactly once

    key_h = {"X-API-Key": key}

    # The key inherits its admin creator's role.
    assert (await client.get("/documents", headers=key_h)).status_code == 200
    assert (
        await client.post("/documents", headers=key_h, json={"title": "via key"})
    ).status_code == 201

    listed = await client.get("/api-keys", headers=admin_h)
    assert listed.json()[0]["last_used_at"] is not None

    # Malformed key is rejected.
    assert (await client.get("/documents", headers={"X-API-Key": "garbage"})).status_code == 401

    # Revoked key stops working.
    assert (await client.delete(f"/api-keys/{key_id}", headers=admin_h)).status_code == 204
    assert (await client.get("/documents", headers=key_h)).status_code == 401
