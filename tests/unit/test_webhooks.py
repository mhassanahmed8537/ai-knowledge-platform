import hmac

from core.webhooks import sign_payload


def test_sign_payload_is_deterministic() -> None:
    body = b'{"event": "document.ready"}'
    assert sign_payload("secret", body) == sign_payload("secret", body)


def test_sign_payload_differs_by_secret() -> None:
    body = b'{"event": "document.ready"}'
    assert sign_payload("secret-a", body) != sign_payload("secret-b", body)


def test_sign_payload_differs_by_body() -> None:
    secret = "secret"
    assert sign_payload(secret, b"one") != sign_payload(secret, b"two")


def test_sign_payload_is_hex_sha256() -> None:
    sig = sign_payload("secret", b"body")
    assert len(sig) == 64
    int(sig, 16)  # raises if not valid hex


def test_sign_payload_verifiable_with_compare_digest() -> None:
    secret, body = "secret", b"payload"
    sig = sign_payload(secret, body)
    assert hmac.compare_digest(sig, sign_payload(secret, body))
