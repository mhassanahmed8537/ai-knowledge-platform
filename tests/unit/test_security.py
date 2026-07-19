import uuid

import jwt
import pytest

from api.security import (
    create_access_token,
    decode_access_token,
    generate_api_key,
    hash_password,
    parse_api_key,
    verify_password,
)
from core.enums import UserRole


def test_password_hash_roundtrip() -> None:
    hashed = hash_password("supersecret123")
    assert hashed != "supersecret123"
    assert verify_password("supersecret123", hashed)
    assert not verify_password("wrong", hashed)


def test_access_token_roundtrip() -> None:
    user_id = uuid.uuid4()
    org_id = uuid.uuid4()
    token = create_access_token(user_id, org_id, UserRole.ADMIN)
    claims = decode_access_token(token)

    assert claims["sub"] == str(user_id)
    assert claims["org"] == str(org_id)
    assert claims["role"] == "admin"
    assert claims["type"] == "access"


def test_refresh_typed_token_rejected_as_access() -> None:
    from core.config import get_settings

    settings = get_settings()
    token = jwt.encode(
        {"sub": "x", "org": "y", "type": "refresh"},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    with pytest.raises(jwt.InvalidTokenError):
        decode_access_token(token)


def test_api_key_parse_roundtrip() -> None:
    full_key, prefix, hashed = generate_api_key()
    parsed = parse_api_key(full_key)
    assert parsed is not None
    parsed_prefix, parsed_secret = parsed
    assert parsed_prefix == prefix
    from api.security import hash_secret

    assert hash_secret(parsed_secret) == hashed


def test_api_key_parse_rejects_malformed() -> None:
    assert parse_api_key("not-a-key") is None
    assert parse_api_key("akp_only") is None
