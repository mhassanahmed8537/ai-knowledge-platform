from httpx import AsyncClient

from tests.integration._helpers import bearer, signup, unique_email


async def _login(client: AsyncClient, email: str, password: str = "memberpass123") -> str:
    resp = await client.post("/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


async def test_role_matrix(client: AsyncClient) -> None:
    admin = await signup(client)
    admin_h = bearer(admin["access_token"])

    member_email = unique_email("member")
    viewer_email = unique_email("viewer")
    r = await client.post(
        "/users",
        headers=admin_h,
        json={"email": member_email, "password": "memberpass123", "role": "member"},
    )
    assert r.status_code == 201
    r = await client.post(
        "/users",
        headers=admin_h,
        json={"email": viewer_email, "password": "memberpass123", "role": "read_only"},
    )
    assert r.status_code == 201

    member_h = bearer(await _login(client, member_email))
    viewer_h = bearer(await _login(client, viewer_email))

    # Member can write documents; read_only cannot but can read.
    assert (
        await client.post("/documents", headers=member_h, json={"title": "m"})
    ).status_code == 201
    assert (
        await client.post("/documents", headers=viewer_h, json={"title": "v"})
    ).status_code == 403
    assert (await client.get("/documents", headers=viewer_h)).status_code == 200

    # Only admins may manage users.
    assert (await client.get("/users", headers=member_h)).status_code == 403
    assert (await client.get("/users", headers=admin_h)).status_code == 200


async def test_admin_self_protection(client: AsyncClient) -> None:
    admin = await signup(client)
    admin_h = bearer(admin["access_token"])
    me = await client.get("/auth/me", headers=admin_h)
    admin_id = me.json()["id"]

    demote = await client.patch(f"/users/{admin_id}", headers=admin_h, json={"role": "member"})
    assert demote.status_code == 400

    delete = await client.delete(f"/users/{admin_id}", headers=admin_h)
    assert delete.status_code == 400
