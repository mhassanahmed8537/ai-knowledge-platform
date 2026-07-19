import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from pwdlib import PasswordHash

from core.config import get_settings
from core.enums import UserRole

_password_hash = PasswordHash.recommended()


# --- Passwords (Argon2) ---
def hash_password(password: str) -> str:
    return _password_hash.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return _password_hash.verify(password, hashed)


# --- Opaque token hashing (refresh tokens, API key secrets) ---
def hash_secret(raw: str) -> str:
    """SHA-256 for high-entropy opaque tokens (fast per-request verification)."""
    return hashlib.sha256(raw.encode()).hexdigest()


# --- JWT access tokens ---
def create_access_token(user_id: uuid.UUID, org_id: uuid.UUID, role: UserRole) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "org": str(org_id),
        "role": role.value,
        "type": "access",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=settings.access_token_ttl_seconds)).timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and validate an access token. Raises ``jwt.PyJWTError`` on failure."""
    settings = get_settings()
    claims: dict[str, Any] = jwt.decode(
        token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
    )
    if claims.get("type") != "access":
        raise jwt.InvalidTokenError("not an access token")
    return claims


# --- Refresh tokens (opaque, stored hashed for revocation) ---
def generate_refresh_token() -> tuple[str, str]:
    """Return (raw_token, token_hash). Only the hash is persisted."""
    raw = secrets.token_urlsafe(32)
    return raw, hash_secret(raw)


# --- API keys ---
def generate_api_key() -> tuple[str, str, str]:
    """Return (full_key, prefix, hashed_secret).

    Layout: ``{api_key_prefix}{prefix}_{secret}`` — the prefix is a public,
    unique lookup handle; only the SHA-256 of the secret is persisted.
    """
    settings = get_settings()
    prefix = secrets.token_hex(4)  # 8 chars, fits the prefix(16) column
    secret = secrets.token_urlsafe(32)
    full_key = f"{settings.api_key_prefix}{prefix}_{secret}"
    return full_key, prefix, hash_secret(secret)


def parse_api_key(full_key: str) -> tuple[str, str] | None:
    """Split a presented API key into (prefix, secret); None if malformed."""
    settings = get_settings()
    if not full_key.startswith(settings.api_key_prefix):
        return None
    body = full_key[len(settings.api_key_prefix) :]
    prefix, sep, secret = body.partition("_")
    if not sep or not prefix or not secret:
        return None
    return prefix, secret
