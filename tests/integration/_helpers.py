import uuid
from typing import Any

from httpx import AsyncClient


def unique_email(prefix: str = "user") -> str:
    return f"itest-{prefix}-{uuid.uuid4().hex}@itest.dev"


def unique_org() -> str:
    # _slugify turns this into "itest-<hex>", which the test teardown cleans up.
    return f"itest {uuid.uuid4().hex}"


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def signup(
    client: AsyncClient,
    *,
    email: str | None = None,
    password: str = "supersecret123",
    org_name: str | None = None,
) -> dict[str, Any]:
    resp = await client.post(
        "/auth/signup",
        json={
            "org_name": org_name or unique_org(),
            "email": email or unique_email("admin"),
            "password": password,
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()
