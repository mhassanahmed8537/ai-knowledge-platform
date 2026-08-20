import secrets
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from api.deps import Principal, require_role
from api.schemas import WebhookCreate, WebhookCreated, WebhookOut
from core.enums import UserRole
from core.models import OrgWebhook

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

_ADMIN = require_role(UserRole.ADMIN)


@router.get("", response_model=list[WebhookOut])
async def list_webhooks(principal: Principal = Depends(_ADMIN)) -> list[OrgWebhook]:
    result = await principal.session.scalars(
        select(OrgWebhook).order_by(OrgWebhook.created_at.desc())
    )
    return list(result.all())


@router.post("", response_model=WebhookCreated, status_code=status.HTTP_201_CREATED)
async def create_webhook(
    body: WebhookCreate,
    principal: Principal = Depends(_ADMIN),
) -> WebhookCreated:
    secret = secrets.token_urlsafe(32)
    webhook = OrgWebhook(
        org_id=principal.org_id,
        url=str(body.url),
        secret=secret,
        event_types=[e.value for e in body.event_types],
    )
    principal.session.add(webhook)
    await principal.session.flush()
    await principal.session.refresh(webhook)

    return WebhookCreated(
        id=webhook.id,
        url=webhook.url,
        event_types=list(body.event_types),
        is_active=webhook.is_active,
        created_at=webhook.created_at,
        secret=secret,
    )


@router.delete("/{webhook_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_webhook(webhook_id: uuid.UUID, principal: Principal = Depends(_ADMIN)) -> None:
    webhook = await principal.session.scalar(select(OrgWebhook).where(OrgWebhook.id == webhook_id))
    if webhook is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Webhook not found")
    await principal.session.delete(webhook)
