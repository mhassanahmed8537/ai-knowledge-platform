import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from api.deps import Principal, require_role
from api.schemas import UserCreate, UserOut, UserUpdate
from api.security import hash_password
from core.enums import UserRole
from core.models import User

router = APIRouter(prefix="/users", tags=["users"])

_ADMIN = require_role(UserRole.ADMIN)


async def _get_org_user(principal: Principal, user_id: uuid.UUID) -> User:
    user = await principal.session.scalar(select(User).where(User.id == user_id))
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


@router.get("", response_model=list[UserOut])
async def list_users(principal: Principal = Depends(_ADMIN)) -> list[User]:
    result = await principal.session.scalars(select(User).order_by(User.created_at))
    return list(result.all())


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def create_user(
    body: UserCreate,
    principal: Principal = Depends(_ADMIN),
) -> User:
    user = User(
        org_id=principal.org_id,
        email=body.email,
        hashed_password=hash_password(body.password),
        full_name=body.full_name,
        role=body.role,
    )
    principal.session.add(user)
    try:
        await principal.session.flush()
    except IntegrityError as exc:
        # Email is globally unique; the conflicting row may live in another org
        # (and be invisible to this admin under RLS), so report a generic 409.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Email already registered"
        ) from exc
    await principal.session.refresh(user)
    return user


@router.get("/{user_id}", response_model=UserOut)
async def get_user(user_id: uuid.UUID, principal: Principal = Depends(_ADMIN)) -> User:
    return await _get_org_user(principal, user_id)


@router.patch("/{user_id}", response_model=UserOut)
async def update_user(
    user_id: uuid.UUID,
    body: UserUpdate,
    principal: Principal = Depends(_ADMIN),
) -> User:
    user = await _get_org_user(principal, user_id)

    if user.id == principal.user.id and body.role is not None and body.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Admins cannot demote themselves"
        )
    if user.id == principal.user.id and body.is_active is False:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Admins cannot deactivate themselves"
        )

    if body.full_name is not None:
        user.full_name = body.full_name
    if body.role is not None:
        user.role = body.role
    if body.is_active is not None:
        user.is_active = body.is_active
    await principal.session.flush()
    return user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(user_id: uuid.UUID, principal: Principal = Depends(_ADMIN)) -> None:
    user = await _get_org_user(principal, user_id)
    if user.id == principal.user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Admins cannot delete themselves"
        )
    await principal.session.delete(user)
