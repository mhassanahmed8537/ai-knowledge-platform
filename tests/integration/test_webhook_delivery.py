"""Exercises the actual outbound POST, not just the CRUD API.

Spins up a throwaway HTTP receiver on localhost and drives
``dispatch_webhooks_for_event`` directly — the same function the worker's
Celery task and ``worker.tasks.ingest`` call — so this covers signing,
event-type filtering, and the is_active flag end to end without needing a
running Celery worker.
"""

import json
import threading
import uuid
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from httpx import AsyncClient

from core.webhooks import sign_payload
from tests.integration._helpers import bearer, signup
from worker.tasks.webhooks import dispatch_webhooks_for_event


class _Received:
    def __init__(self) -> None:
        self.requests: list[tuple[bytes, dict[str, str]]] = []


class _CapturingHandler(BaseHTTPRequestHandler):
    received: _Received

    def do_POST(self) -> None:  # noqa: N802 (stdlib naming convention)
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        self.received.requests.append((body, dict(self.headers)))
        self.send_response(200)
        self.end_headers()

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        pass  # keep test output quiet


@pytest.fixture
def webhook_receiver() -> Iterator[tuple[str, _Received]]:
    received = _Received()
    _CapturingHandler.received = received
    server = ThreadingHTTPServer(("127.0.0.1", 0), _CapturingHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]
    try:
        yield f"http://127.0.0.1:{port}/hook", received
    finally:
        server.shutdown()
        thread.join()


async def test_dispatch_delivers_signed_payload_to_subscribed_webhook(
    client: AsyncClient, webhook_receiver: tuple[str, _Received]
) -> None:
    url, received = webhook_receiver
    tokens = await signup(client)
    token = tokens["access_token"]
    me = await client.get("/auth/me", headers=bearer(token))
    org_id = uuid.UUID(me.json()["org_id"])

    created = await client.post(
        "/webhooks",
        headers=bearer(token),
        json={"url": url, "event_types": ["document.ready"]},
    )
    secret = created.json()["secret"]

    delivered = await dispatch_webhooks_for_event(
        org_id, "document.ready", {"document_id": "abc123"}
    )
    assert delivered == 1
    assert len(received.requests) == 1

    body, headers = received.requests[0]
    payload = json.loads(body)
    assert payload["event"] == "document.ready"
    assert payload["data"] == {"document_id": "abc123"}
    assert headers["X-Webhook-Event"] == "document.ready"
    assert headers["X-Webhook-Signature"] == sign_payload(secret, body)


async def test_dispatch_skips_webhooks_not_subscribed_to_the_event(
    client: AsyncClient, webhook_receiver: tuple[str, _Received]
) -> None:
    url, received = webhook_receiver
    tokens = await signup(client)
    token = tokens["access_token"]
    me = await client.get("/auth/me", headers=bearer(token))
    org_id = uuid.UUID(me.json()["org_id"])

    await client.post(
        "/webhooks",
        headers=bearer(token),
        json={"url": url, "event_types": ["budget.alert"]},
    )

    delivered = await dispatch_webhooks_for_event(
        org_id, "document.ready", {"document_id": "abc123"}
    )
    assert delivered == 0
    assert received.requests == []


async def test_dispatch_is_scoped_to_the_target_org(
    client: AsyncClient, webhook_receiver: tuple[str, _Received]
) -> None:
    url, received = webhook_receiver
    owner = await signup(client)
    await client.post(
        "/webhooks",
        headers=bearer(owner["access_token"]),
        json={"url": url, "event_types": ["document.ready"]},
    )

    other = await signup(client)
    me = await client.get("/auth/me", headers=bearer(other["access_token"]))
    other_org_id = uuid.UUID(me.json()["org_id"])

    delivered = await dispatch_webhooks_for_event(
        other_org_id, "document.ready", {"document_id": "abc123"}
    )
    assert delivered == 0
    assert received.requests == []
