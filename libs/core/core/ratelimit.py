"""Redis-backed fixed-window rate limiting.

A defense-in-depth backstop behind ``core.config.Settings.rate_limit_enabled``
(default on). It's Redis-backed rather than in-process because the API runs
as multiple replicas in k8s (see infra/k8s) — an in-process counter would let
each pod enforce an independent budget, silently multiplying the effective
limit by replica count.

The primary throttle is expected to be the ingress (see the
``nginx.ingress.kubernetes.io/limit-rps`` annotation in infra/k8s), so the
default here is deliberately generous rather than a tight per-attempt limit.
"""

import time

import redis.asyncio as redis
from fastapi import HTTPException, Request, status

from core.config import get_settings


def _client_ip(request: Request) -> str:
    # Trust X-Forwarded-For only because the app is only ever reachable
    # through the k8s ingress in front of it (see infra/k8s/base/ingress.yaml),
    # which overwrites any client-supplied value rather than appending to it.
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def enforce_rate_limit(
    request: Request, *, key: str, limit: int, window_seconds: int
) -> None:
    """Raise 429 once more than ``limit`` calls land in the current window.

    Fixed-window (not sliding): simple, O(1) per request, and precise enough
    for a backstop — the worst case lets through at most 2x the limit across
    a window boundary, which is an acceptable trade for the added complexity
    a sliding-window/token-bucket implementation would need.
    """
    settings = get_settings()
    if not settings.rate_limit_enabled:
        return

    bucket = int(time.time() // window_seconds)
    redis_key = f"ratelimit:{key}:{_client_ip(request)}:{bucket}"

    client = redis.from_url(settings.redis_url)  # type: ignore[no-untyped-call]
    try:
        count = await client.incr(redis_key)
        if count == 1:
            await client.expire(redis_key, window_seconds)
    finally:
        await client.aclose()

    if count > limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests, please try again later",
        )
