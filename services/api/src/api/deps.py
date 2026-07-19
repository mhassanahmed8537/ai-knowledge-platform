import uuid
from collections.abc import AsyncIterator, Callable, Coroutine
from dataclasses import dataclass
from typing import Any

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from api.security import decode_access_token
from core.db import get_auth_sessionmaker, get_sessionmaker, set_org_context
from core.enums import UserRole
from core.models import User

bearer_scheme = HTTPBearer(auto_error=False)

_UNAUTHORIZED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Not authenticated",
    headers={"WWW-Authenticate": "Bearer"},
)


@dataclass
class AuthContext:
    """Request-scoped authenticated context: an RLS-bound session + the caller."""

    session: AsyncSession
    user: User


async def get_auth_session() -> AsyncIterator[AsyncSession]:
    """A session on the BYPASSRLS auth role, for cross-tenant auth-bootstrap only."""
    sessionmaker = get_auth_sessionmaker()
    async with sessionmaker() as session:
        yield session


async def get_auth_context(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> AsyncIterator[AuthContext]:
    if credentials is None or not credentials.credentials:
        raise _UNAUTHORIZED

    try:
        claims = decode_access_token(credentials.credentials)
        user_id = uuid.UUID(claims["sub"])
        org_id = uuid.UUID(claims["org"])
    except (jwt.PyJWTError, KeyError, ValueError) as exc:
        raise _UNAUTHORIZED from exc

    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session, session.begin():
        # Bind RLS to the caller's org before any tenant query.
        await set_org_context(session, org_id)
        user = await session.get(User, user_id)
        if user is None or not user.is_active or user.org_id != org_id:
            raise _UNAUTHORIZED
        yield AuthContext(session=session, user=user)


async def get_current_user(ctx: AuthContext = Depends(get_auth_context)) -> User:
    return ctx.user


async def get_session(ctx: AuthContext = Depends(get_auth_context)) -> AsyncSession:
    return ctx.session


def require_role(
    *roles: UserRole,
) -> Callable[[AuthContext], Coroutine[Any, Any, AuthContext]]:
    """Dependency factory guarding an endpoint to the given roles."""

    async def _guard(ctx: AuthContext = Depends(get_auth_context)) -> AuthContext:
        if ctx.user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient role",
            )
        return ctx

    return _guard
