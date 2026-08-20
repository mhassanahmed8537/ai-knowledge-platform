import uuid

from httpx import AsyncClient

from tests.integration._helpers import bearer, signup


async def test_webhook_lifecycle(client: AsyncClient) -> None:
    admin = await signup(client)
    admin_h = bearer(admin["access_token"])

    created = await client.post(
        "/webhooks",
        headers=admin_h,
        json={"url": "https://example.com/hook", "event_types": ["document.ready"]},
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["secret"]  # plaintext signing secret returned exactly once
    assert body["event_types"] == ["document.ready"]
    webhook_id = body["id"]

    listed = await client.get("/webhooks", headers=admin_h)
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert "secret" not in listed.json()[0]  # never returned again

    assert (await client.delete(f"/webhooks/{webhook_id}", headers=admin_h)).status_code == 204
    assert (await client.get("/webhooks", headers=admin_h)).json() == []


async def test_webhook_delete_missing_is_404(client: AsyncClient) -> None:
    admin = await signup(client)
    admin_h = bearer(admin["access_token"])
    resp = await client.delete(f"/webhooks/{uuid.uuid4()}", headers=admin_h)
    assert resp.status_code == 404


async def test_webhook_requires_at_least_one_event_type(client: AsyncClient) -> None:
    admin = await signup(client)
    resp = await client.post(
        "/webhooks",
        headers=bearer(admin["access_token"]),
        json={"url": "https://example.com/hook", "event_types": []},
    )
    assert resp.status_code == 422


async def test_only_admin_can_manage_webhooks(client: AsyncClient) -> None:
    admin = await signup(client)
    admin_h = bearer(admin["access_token"])

    created = await client.post(
        "/users",
        headers=admin_h,
        json={"email": f"member-{uuid.uuid4().hex}@itest.dev", "password": "memberpass123"},
    )
    member = await client.post(
        "/auth/login",
        json={"email": created.json()["email"], "password": "memberpass123"},
    )
    member_h = bearer(member.json()["access_token"])

    assert (
        await client.post(
            "/webhooks",
            headers=member_h,
            json={"url": "https://example.com/hook", "event_types": ["document.ready"]},
        )
    ).status_code == 403
    assert (await client.get("/webhooks", headers=member_h)).status_code == 403


async def test_webhooks_are_tenant_isolated(client: AsyncClient) -> None:
    owner = await signup(client)
    await client.post(
        "/webhooks",
        headers=bearer(owner["access_token"]),
        json={"url": "https://example.com/hook", "event_types": ["budget.alert"]},
    )

    other = await signup(client)
    other_webhooks = await client.get("/webhooks", headers=bearer(other["access_token"]))
    assert other_webhooks.json() == []
