from decimal import Decimal

from httpx import AsyncClient

from tests.integration._helpers import bearer, signup


async def test_get_my_organization(client: AsyncClient) -> None:
    tokens = await signup(client)
    resp = await client.get("/organizations/me", headers=bearer(tokens["access_token"]))
    assert resp.status_code == 200
    body = resp.json()
    assert body["monthly_budget_usd"] is None


async def test_admin_can_set_and_clear_budget(client: AsyncClient) -> None:
    tokens = await signup(client)
    headers = bearer(tokens["access_token"])

    set_budget = await client.patch(
        "/organizations/me", headers=headers, json={"monthly_budget_usd": "250.50"}
    )
    assert set_budget.status_code == 200
    assert Decimal(set_budget.json()["monthly_budget_usd"]) == Decimal("250.50")

    fetched = await client.get("/organizations/me", headers=headers)
    assert Decimal(fetched.json()["monthly_budget_usd"]) == Decimal("250.50")

    cleared = await client.patch("/organizations/me", headers=headers, json={})
    assert cleared.status_code == 200
    assert cleared.json()["monthly_budget_usd"] is None


async def test_negative_budget_rejected(client: AsyncClient) -> None:
    tokens = await signup(client)
    resp = await client.patch(
        "/organizations/me",
        headers=bearer(tokens["access_token"]),
        json={"monthly_budget_usd": "-1"},
    )
    assert resp.status_code == 422
