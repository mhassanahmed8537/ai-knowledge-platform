import secrets
import uuid
from collections.abc import AsyncIterator, Callable, Coroutine
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import jwt
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.security import decode_access_token, hash_secret, parse_api_key
from core.db import (
    get_auth_sessionmaker,
    get_sessionmaker,
    set_org_context,
)
from core.enums import UserRole
from core.models import ApiKey, User

bearer_scheme = HTTPBearer(auto_error=False)

_UNAUTHORIZED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Not authenticated",
    headers={"WWW-Authenticate": "Bearer"},
)


@dataclass
class Principal:
    """The authenticated caller for a request.

    ``session`` is bound (via RLS) to ``org_id`` so all queries are automatically
    tenant-scoped. ``role`` drives RBAC. ``user`` is the acting human (for API
    keys this is the key's still-active creator); ``via_api_key`` distinguishes
    programmatic callers.
    """

    session: AsyncSession
    org_id: uuid.UUID
    role: UserRole
    user: User
    via_api_key: bool = False


async def get_auth_session() -> AsyncIterator[AsyncSession]:
    """A session on the BYPASSRLS auth role, for cross-tenant auth-bootstrap only."""
    sessionmaker = get_auth_sessionmaker()
    async with sessionmaker() as session:
        yield session


async def _resolve_api_key(raw_key: str) -> tuple[uuid.UUID, User]:
    """Verify an API key on the auth role; return (org_id, active creator user)."""
    parsed = parse_api_key(raw_key)
    if parsed is None:
        raise _UNAUTHORIZED
    prefix, secret = parsed

    auth_sessionmaker = get_auth_sessionmaker()
    async with auth_sessionmaker() as session, session.begin():
        key = await session.scalar(select(ApiKey).where(ApiKey.prefix == prefix))
        now = datetime.now(UTC)
        if (
            key is None
            or key.revoked_at is not None
            or (key.expires_at is not None and key.expires_at <= now)
            or not secrets.compare_digest(key.hashed_key, hash_secret(secret))
        ):
            raise _UNAUTHORIZED

        creator = (
            await session.get(User, key.created_by_user_id) if key.created_by_user_id else None
        )
        if creator is None or not creator.is_active:
            raise _UNAUTHORIZED

        key.last_used_at = now
        return key.org_id, creator


async def get_principal(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> AsyncIterator[Principal]:
    via_api_key = bool(x_api_key)

    if x_api_key:
        org_id, creator = await _resolve_api_key(x_api_key)
        user_id = creator.id
    elif credentials and credentials.credentials:
        try:
            claims = decode_access_token(credentials.credentials)
            user_id = uuid.UUID(claims["sub"])
            org_id = uuid.UUID(claims["org"])
        except (jwt.PyJWTError, KeyError, ValueError) as exc:
            raise _UNAUTHORIZED from exc
    else:
        raise _UNAUTHORIZED

    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session, session.begin():
        # Bind RLS to the caller's org before any tenant query.
        await set_org_context(session, org_id)
        user = await session.get(User, user_id)
        if user is None or not user.is_active or user.org_id != org_id:
            raise _UNAUTHORIZED
        yield Principal(
            session=session,
            org_id=org_id,
            role=user.role,
            user=user,
            via_api_key=via_api_key,
        )


async def get_current_user(principal: Principal = Depends(get_principal)) -> User:
    return principal.user


async def get_session(principal: Principal = Depends(get_principal)) -> AsyncSession:
    return principal.session


def require_role(
    *roles: UserRole,
) -> Callable[[Principal], Coroutine[Any, Any, Principal]]:
    """Dependency factory guarding an endpoint to the given roles."""

    async def _guard(principal: Principal = Depends(get_principal)) -> Principal:
        if principal.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient role",
            )
        return principal

    return _guard
