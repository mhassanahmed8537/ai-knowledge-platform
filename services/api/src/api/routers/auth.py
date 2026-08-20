import re
import secrets
from datetime import UTC, datetime, timedelta

from authlib.integrations.base_client import OAuthError
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_auth_session, get_current_user
from api.oauth_clients import extract_identity, get_client
from api.schemas import (
    LoginRequest,
    RefreshRequest,
    SignupRequest,
    TokenResponse,
    UserOut,
)
from api.security import (
    create_access_token,
    generate_refresh_token,
    hash_password,
    hash_secret,
    verify_password,
)
from core.config import get_settings
from core.enums import OAuthProvider, UserRole
from core.models import OAuthAccount, Organization, RefreshToken, User
from core.ratelimit import enforce_rate_limit

router = APIRouter(prefix="/auth", tags=["auth"])


async def _rate_limit(request: Request, key: str) -> None:
    settings = get_settings()
    await enforce_rate_limit(
        request,
        key=key,
        limit=settings.auth_rate_limit_per_minute,
        window_seconds=settings.auth_rate_limit_window_seconds,
    )


async def _signup_rate_limit(request: Request) -> None:
    await _rate_limit(request, "auth:signup")


async def _login_rate_limit(request: Request) -> None:
    await _rate_limit(request, "auth:login")


async def _refresh_rate_limit(request: Request) -> None:
    await _rate_limit(request, "auth:refresh")


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "org"


async def _issue_tokens(session: AsyncSession, user: User) -> TokenResponse:
    settings = get_settings()
    access = create_access_token(user.id, user.org_id, user.role)
    raw_refresh, refresh_hash = generate_refresh_token()
    session.add(
        RefreshToken(
            user_id=user.id,
            token_hash=refresh_hash,
            expires_at=datetime.now(UTC) + timedelta(seconds=settings.refresh_token_ttl_seconds),
        )
    )
    return TokenResponse(
        access_token=access,
        refresh_token=raw_refresh,
        expires_in=settings.access_token_ttl_seconds,
    )


@router.post("/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def signup(
    body: SignupRequest,
    session: AsyncSession = Depends(get_auth_session),
    _rl: None = Depends(_signup_rate_limit),
) -> TokenResponse:
    existing = await session.scalar(select(User).where(User.email == body.email))
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    slug = _slugify(body.org_name)
    if await session.scalar(select(Organization).where(Organization.slug == slug)) is not None:
        slug = f"{slug}-{secrets.token_hex(3)}"

    org = Organization(name=body.org_name, slug=slug)
    session.add(org)
    await session.flush()

    user = User(
        org_id=org.id,
        email=body.email,
        hashed_password=hash_password(body.password),
        full_name=body.full_name,
        role=UserRole.ADMIN,
    )
    session.add(user)
    await session.flush()

    tokens = await _issue_tokens(session, user)
    await session.commit()
    return tokens


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    session: AsyncSession = Depends(get_auth_session),
    _rl: None = Depends(_login_rate_limit),
) -> TokenResponse:
    user = await session.scalar(select(User).where(User.email == body.email))
    if (
        user is None
        or user.hashed_password is None
        or not verify_password(body.password, user.hashed_password)
    ):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is inactive")

    tokens = await _issue_tokens(session, user)
    await session.commit()
    return tokens


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    body: RefreshRequest,
    session: AsyncSession = Depends(get_auth_session),
    _rl: None = Depends(_refresh_rate_limit),
) -> TokenResponse:
    token_hash = hash_secret(body.refresh_token)
    stored = await session.scalar(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
    now = datetime.now(UTC)
    if stored is None or stored.revoked_at is not None or stored.expires_at <= now:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
        )

    user = await session.get(User, stored.user_id)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
        )

    # Rotate: revoke the presented token and issue a fresh pair.
    stored.revoked_at = now
    tokens = await _issue_tokens(session, user)
    await session.commit()
    return tokens


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    body: RefreshRequest,
    session: AsyncSession = Depends(get_auth_session),
) -> None:
    token_hash = hash_secret(body.refresh_token)
    stored = await session.scalar(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
    if stored is not None and stored.revoked_at is None:
        stored.revoked_at = datetime.now(UTC)
        await session.commit()


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)) -> User:
    return user


# --- OAuth (Google / GitHub) ---
def _require_provider(provider: OAuthProvider):  # type: ignore[no-untyped-def]
    client = get_client(provider)
    if client is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"OAuth provider '{provider.value}' is not configured",
        )
    return client


@router.get("/oauth/{provider}/authorize")
async def oauth_authorize(provider: OAuthProvider, request: Request) -> RedirectResponse:
    client = _require_provider(provider)
    redirect_uri = f"{get_settings().oauth_redirect_base_url}/auth/oauth/{provider.value}/callback"
    result: RedirectResponse = await client.authorize_redirect(request, redirect_uri)
    return result


@router.get("/oauth/{provider}/callback", response_model=TokenResponse)
async def oauth_callback(
    provider: OAuthProvider,
    request: Request,
    session: AsyncSession = Depends(get_auth_session),
) -> TokenResponse:
    client = _require_provider(provider)
    try:
        token = await client.authorize_access_token(request)
    except OAuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="OAuth exchange failed"
        ) from exc

    identity = await extract_identity(provider, client, token)

    # 1) Already-linked provider account -> log in.
    linked = await session.scalar(
        select(OAuthAccount).where(
            OAuthAccount.provider == provider,
            OAuthAccount.provider_account_id == identity.provider_account_id,
        )
    )
    if linked is not None:
        user = await session.get(User, linked.user_id)
        if user is None or not user.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is inactive")
        tokens = await _issue_tokens(session, user)
        await session.commit()
        return tokens

    if identity.email is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OAuth provider did not return a usable email",
        )

    # 2) Existing local user with that email -> link the provider account.
    user = await session.scalar(select(User).where(User.email == identity.email))
    if user is not None:
        session.add(
            OAuthAccount(
                user_id=user.id,
                provider=provider,
                provider_account_id=identity.provider_account_id,
            )
        )
        tokens = await _issue_tokens(session, user)
        await session.commit()
        return tokens

    # 3) First-time login -> provision a new org + admin (passwordless).
    local_part = identity.email.split("@", 1)[0]
    slug = _slugify(identity.full_name or local_part)
    if await session.scalar(select(Organization).where(Organization.slug == slug)) is not None:
        slug = f"{slug}-{secrets.token_hex(3)}"

    org = Organization(name=identity.full_name or f"{local_part}'s Organization", slug=slug)
    session.add(org)
    await session.flush()

    user = User(
        org_id=org.id,
        email=identity.email,
        hashed_password=None,
        full_name=identity.full_name,
        role=UserRole.ADMIN,
    )
    session.add(user)
    await session.flush()
    session.add(
        OAuthAccount(
            user_id=user.id,
            provider=provider,
            provider_account_id=identity.provider_account_id,
        )
    )

    tokens = await _issue_tokens(session, user)
    await session.commit()
    return tokens
