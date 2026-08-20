"""Outbound webhook signing — shared by the worker's delivery task and its tests.

Kept dependency-free (no Celery, no httpx) so it can live in ``core`` and be
imported by both services without pulling in the worker's task-queue plumbing.
"""

import hashlib
import hmac


def sign_payload(secret: str, body: bytes) -> str:
    """HMAC-SHA256 of the raw request body, hex-encoded.

    Sent as ``X-Webhook-Signature`` so receivers can verify a delivery
    actually came from us (compare with ``hmac.compare_digest``, never ``==``).
    """
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
