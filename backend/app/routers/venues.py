from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import TenantContext, get_tenant_context
from app.core.security import create_access_token
from app.db import get_db
from app.models.hospitality import CashRegister, DiningArea
from app.models.tenancy import UserVenue, Venue

router = APIRouter(prefix="/api/v1/venues", tags=["multi-establishment"])


class VenueCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    code: str = Field(min_length=2, max_length=40)
    timezone: str = "Europe/Madrid"


@router.get("")
async def list_venues(ctx: TenantContext = Depends(get_tenant_context), db: AsyncSession = Depends(get_db)):
    rows = await db.execute(
        select(Venue, UserVenue.role).join(UserVenue, UserVenue.venue_id == Venue.id).where(
            Venue.tenant_id == ctx.tenant_id, UserVenue.user_id == ctx.user_id, Venue.is_active.is_(True)
        ).order_by(Venue.name)
    )
    return [{"id": str(v.id), "name": v.name, "code": v.code, "role": role} for v, role in rows.all()]


@router.post("", status_code=201)
async def create_venue(payload: VenueCreate, ctx: TenantContext = Depends(get_tenant_context), db: AsyncSession = Depends(get_db)):
    if ctx.role not in {"owner", "admin"}:
        raise HTTPException(status_code=403, detail="Solo el propietario o administrador puede crear establecimientos.")
    venue = Venue(tenant_id=ctx.tenant_id, name=payload.name, code=payload.code, timezone=payload.timezone)
    db.add(venue)
    await db.flush()
    db.add(UserVenue(user_id=ctx.user_id, venue_id=venue.id, role=ctx.role))
    db.add(CashRegister(tenant_id=ctx.tenant_id, venue_id=venue.id, name="Caja principal"))
    db.add(DiningArea(tenant_id=ctx.tenant_id, venue_id=venue.id, name="Sala", sort_order=0))
    await db.commit()
    return {"id": str(venue.id), "name": venue.name, "code": venue.code}
