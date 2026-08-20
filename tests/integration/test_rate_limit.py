"""Rate limiting is disabled by default in tests (see conftest.py) because
every request shares one apparent client IP under httpx's ASGITransport, so
this test re-enables it for its own assertions only, with a short window to
avoid colliding with itself across repeated local test runs.
"""

import pytest
from httpx import AsyncClient

from core.config import get_settings
from tests.integration._helpers import unique_email, unique_org


@pytest.fixture
def _enabled_rate_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "true")
    monkeypatch.setenv("AUTH_RATE_LIMIT_PER_MINUTE", "3")
    monkeypatch.setenv("AUTH_RATE_LIMIT_WINDOW_SECONDS", "5")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


async def test_login_is_rate_limited_per_ip(client: AsyncClient, _enabled_rate_limit: None) -> None:
    statuses = [
        (
            await client.post(
                "/auth/login", json={"email": "nobody@example.com", "password": "wrong"}
            )
        ).status_code
        for _ in range(5)
    ]
    # Under the limit: real auth failures, not throttled.
    assert statuses[:3] == [401, 401, 401]
    # Over the limit: throttled before auth logic even runs.
    assert 429 in statuses[3:]


async def test_signup_and_login_have_independent_budgets(
    client: AsyncClient, _enabled_rate_limit: None
) -> None:
    # Exhaust the login budget...
    for _ in range(3):
        await client.post("/auth/login", json={"email": "nobody@example.com", "password": "wrong"})
    assert (
        await client.post("/auth/login", json={"email": "nobody@example.com", "password": "wrong"})
    ).status_code == 429

    # ...signup is keyed separately, so it isn't affected.
    resp = await client.post(
        "/auth/signup",
        json={
            "org_name": unique_org(),
            "email": unique_email("rl-signup"),
            "password": "supersecret123",
        },
    )
    assert resp.status_code == 201
