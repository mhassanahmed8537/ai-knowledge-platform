from httpx import AsyncClient

from tests.integration._helpers import bearer, signup, unique_email


async def test_signup_me_login_refresh_rotation(client: AsyncClient) -> None:
    email = unique_email("admin")
    tokens = await signup(client, email=email)

    me = await client.get("/auth/me", headers=bearer(tokens["access_token"]))
    assert me.status_code == 200
    body = me.json()
    assert body["email"] == email
    assert body["role"] == "admin"

    login = await client.post("/auth/login", json={"email": email, "password": "supersecret123"})
    assert login.status_code == 200

    old_refresh = tokens["refresh_token"]
    rotated = await client.post("/auth/refresh", json={"refresh_token": old_refresh})
    assert rotated.status_code == 200
    assert rotated.json()["refresh_token"] != old_refresh

    # The rotated-away refresh token must no longer work.
    reused = await client.post("/auth/refresh", json={"refresh_token": old_refresh})
    assert reused.status_code == 401


async def test_me_requires_auth(client: AsyncClient) -> None:
    assert (await client.get("/auth/me")).status_code == 401
    bad = await client.get("/auth/me", headers=bearer("not-a-jwt"))
    assert bad.status_code == 401


async def test_duplicate_email_and_bad_password(client: AsyncClient) -> None:
    email = unique_email("admin")
    await signup(client, email=email)

    dup = await client.post(
        "/auth/signup",
        json={"org_name": "itest dup", "email": email, "password": "supersecret123"},
    )
    assert dup.status_code == 409

    wrong = await client.post("/auth/login", json={"email": email, "password": "wrongpassword"})
    assert wrong.status_code == 401
