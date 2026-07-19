"""OAuth provider registry and identity extraction (Google + GitHub).

Providers are registered only when their client id/secret are configured, so an
unconfigured provider is cleanly reported as unavailable rather than half-working.
"""

from dataclasses import dataclass
from typing import Any

from authlib.integrations.starlette_client import OAuth, StarletteOAuth2App

from core.config import get_settings
from core.enums import OAuthProvider

_oauth = OAuth()
_settings = get_settings()

if _settings.google_client_id and _settings.google_client_secret:
    _oauth.register(
        name="google",
        client_id=_settings.google_client_id,
        client_secret=_settings.google_client_secret,
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"},
    )

if _settings.github_client_id and _settings.github_client_secret:
    _oauth.register(
        name="github",
        client_id=_settings.github_client_id,
        client_secret=_settings.github_client_secret,
        access_token_url="https://github.com/login/oauth/access_token",
        authorize_url="https://github.com/login/oauth/authorize",
        api_base_url="https://api.github.com/",
        client_kwargs={"scope": "read:user user:email"},
    )


@dataclass
class OAuthIdentity:
    provider: OAuthProvider
    provider_account_id: str
    email: str | None
    full_name: str | None


def get_client(provider: OAuthProvider) -> StarletteOAuth2App | None:
    return _oauth.create_client(provider.value)


async def extract_identity(
    provider: OAuthProvider, client: StarletteOAuth2App, token: dict[str, Any]
) -> OAuthIdentity:
    if provider is OAuthProvider.GOOGLE:
        userinfo = token.get("userinfo") or await client.userinfo(token=token)
        return OAuthIdentity(
            provider=provider,
            provider_account_id=str(userinfo["sub"]),
            email=userinfo.get("email"),
            full_name=userinfo.get("name"),
        )

    # GitHub: profile from /user; email may require the /user/emails endpoint.
    profile = (await client.get("user", token=token)).json()
    email = profile.get("email")
    if not email:
        emails = (await client.get("user/emails", token=token)).json()
        primary = next(
            (e for e in emails if e.get("primary") and e.get("verified")),
            next((e for e in emails if e.get("verified")), None),
        )
        email = primary.get("email") if primary else None
    return OAuthIdentity(
        provider=provider,
        provider_account_id=str(profile["id"]),
        email=email,
        full_name=profile.get("name") or profile.get("login"),
    )
