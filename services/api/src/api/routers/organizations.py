from fastapi import APIRouter, Depends

from api.deps import Principal, get_principal, require_role
from api.schemas import OrganizationOut, OrganizationUpdate
from core.enums import UserRole
from core.models import Organization

router = APIRouter(prefix="/organizations", tags=["organizations"])

_ADMIN = require_role(UserRole.ADMIN)


@router.get("/me", response_model=OrganizationOut)
async def get_my_organization(principal: Principal = Depends(get_principal)) -> Organization:
    org = await principal.session.get(Organization, principal.org_id)
    assert org is not None  # the principal's own org always exists
    return org


@router.patch("/me", response_model=OrganizationOut)
async def update_my_organization(
    body: OrganizationUpdate,
    principal: Principal = Depends(_ADMIN),
) -> Organization:
    org = await principal.session.get(Organization, principal.org_id)
    assert org is not None
    org.monthly_budget_usd = body.monthly_budget_usd
    await principal.session.flush()
    return org
