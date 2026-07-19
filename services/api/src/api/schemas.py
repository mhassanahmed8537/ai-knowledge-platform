import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from core.enums import DocumentStatus, UserRole


class SignupRequest(BaseModel):
    org_name: str = Field(min_length=1, max_length=255)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=255)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class OrganizationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    created_at: datetime


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    org_id: uuid.UUID
    email: EmailStr
    full_name: str | None
    role: UserRole
    is_active: bool
    created_at: datetime


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=255)
    role: UserRole = UserRole.MEMBER


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, max_length=255)
    role: UserRole | None = None
    is_active: bool | None = None


class DocumentCreate(BaseModel):
    title: str = Field(min_length=1, max_length=512)
    filename: str | None = Field(default=None, max_length=512)
    content_type: str | None = Field(default=None, max_length=255)


class DocumentUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=512)


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    org_id: uuid.UUID
    title: str
    filename: str | None
    content_type: str | None
    status: DocumentStatus
    created_at: datetime


class ApiKeyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    expires_in_days: int | None = Field(default=None, ge=1, le=3650)


class ApiKeyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    prefix: str
    last_used_at: datetime | None
    expires_at: datetime | None
    revoked_at: datetime | None
    created_at: datetime


class ApiKeyCreated(ApiKeyOut):
    """Returned only once at creation — includes the plaintext key."""

    key: str
