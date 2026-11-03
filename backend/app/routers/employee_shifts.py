from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import TenantContext, get_tenant_context
from app.db import get_db
from app.models.hospitality import EmployeeShift
from app.models.tenancy import User, UserVenue

router = APIRouter(prefix="/api/v1/employee-shifts", tags=["employee scheduling"])


class ShiftCreate(BaseModel):
    user_id: UUID
    starts_at: datetime
    ends_at: datetime
    notes: str | None = None


@router.get("")
async def list_shifts(ctx: TenantContext = Depends(get_tenant_context), db: AsyncSession = Depends(get_db)):
    rows = await db.scalars(select(EmployeeShift).where(
        EmployeeShift.tenant_id == ctx.tenant_id,
        EmployeeShift.venue_id == ctx.venue_id,
    ).order_by(EmployeeShift.starts_at).limit(500))
    return [{"id": str(x.id), "user_id": str(x.user_id), "starts_at": x.starts_at.isoformat(),
             "ends_at": x.ends_at.isoformat(), "status": x.status, "notes": x.notes} for x in rows]


@router.post("", status_code=201)
async def create_shift(payload: ShiftCreate, ctx: TenantContext = Depends(get_tenant_context), db: AsyncSession = Depends(get_db)):
    if ctx.role not in {"owner", "admin", "manager"}:
        raise HTTPException(status_code=403, detail="No tienes permiso para planificar turnos.")
    if payload.ends_at <= payload.starts_at:
        raise HTTPException(status_code=422, detail="La hora de fin debe ser posterior a la de inicio.")
    member = await db.scalar(select(UserVenue.user_id).join(User, User.id == UserVenue.user_id).where(
        UserVenue.user_id == payload.user_id, UserVenue.venue_id == ctx.venue_id,
        User.tenant_id == ctx.tenant_id, User.is_active.is_(True),
    ))
    if not member:
        raise HTTPException(status_code=404, detail="Empleado no asignado a este establecimiento.")
    item = EmployeeShift(tenant_id=ctx.tenant_id, venue_id=ctx.venue_id, **payload.model_dump())
    db.add(item)
    await db.commit()
    return {"id": str(item.id), "status": item.status}
