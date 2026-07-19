import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from api.deps import Principal, require_role
from api.schemas import ApiKeyCreate, ApiKeyCreated, ApiKeyOut
from api.security import generate_api_key
from core.enums import UserRole
from core.models import ApiKey

router = APIRouter(prefix="/api-keys", tags=["api-keys"])

_ADMIN = require_role(UserRole.ADMIN)


@router.get("", response_model=list[ApiKeyOut])
async def list_api_keys(principal: Principal = Depends(_ADMIN)) -> list[ApiKey]:
    result = await principal.session.scalars(select(ApiKey).order_by(ApiKey.created_at.desc()))
    return list(result.all())


@router.post("", response_model=ApiKeyCreated, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    body: ApiKeyCreate,
    principal: Principal = Depends(_ADMIN),
) -> ApiKeyCreated:
    full_key, prefix, hashed = generate_api_key()
    expires_at = (
        datetime.now(UTC) + timedelta(days=body.expires_in_days)
        if body.expires_in_days is not None
        else None
    )
    api_key = ApiKey(
        org_id=principal.org_id,
        created_by_user_id=principal.user.id,
        name=body.name,
        prefix=prefix,
        hashed_key=hashed,
        expires_at=expires_at,
    )
    principal.session.add(api_key)
    await principal.session.flush()
    await principal.session.refresh(api_key)

    return ApiKeyCreated(
        id=api_key.id,
        name=api_key.name,
        prefix=api_key.prefix,
        last_used_at=api_key.last_used_at,
        expires_at=api_key.expires_at,
        revoked_at=api_key.revoked_at,
        created_at=api_key.created_at,
        key=full_key,
    )


@router.delete("/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_api_key(key_id: uuid.UUID, principal: Principal = Depends(_ADMIN)) -> None:
    api_key = await principal.session.scalar(select(ApiKey).where(ApiKey.id == key_id))
    if api_key is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")
    if api_key.revoked_at is None:
        api_key.revoked_at = datetime.now(UTC)
        await principal.session.flush()
