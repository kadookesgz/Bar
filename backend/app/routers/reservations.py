from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import TenantContext, get_tenant_context
from app.db import get_db
from app.models.hospitality import DiningTable, Reservation

router = APIRouter(prefix="/api/v1/reservations", tags=["reservations"])


class ReservationCreate(BaseModel):
    customer_name: str = Field(min_length=2, max_length=160)
    phone: str | None = None
    party_size: int = Field(ge=1, le=100)
    starts_at: datetime
    duration_minutes: int = Field(default=120, ge=15, le=600)
    notes: str | None = None
    table_id: UUID | None = None


class ReservationStatus(BaseModel):
    status: str = Field(pattern="^(booked|confirmed|seated|cancelled|no_show|completed)$")


@router.get("")
async def list_reservations(ctx: TenantContext = Depends(get_tenant_context), db: AsyncSession = Depends(get_db)):
    rows = await db.scalars(select(Reservation).where(
        Reservation.tenant_id == ctx.tenant_id,
        Reservation.venue_id == ctx.venue_id,
    ).order_by(Reservation.starts_at.desc()).limit(200))
    return [{
        "id": str(x.id), "customer_name": x.customer_name, "phone": x.phone,
        "party_size": x.party_size, "starts_at": x.starts_at.isoformat(),
        "duration_minutes": x.duration_minutes, "status": x.status,
        "notes": x.notes, "table_id": str(x.table_id) if x.table_id else None,
    } for x in rows]


@router.post("", status_code=201)
async def create_reservation(payload: ReservationCreate, ctx: TenantContext = Depends(get_tenant_context), db: AsyncSession = Depends(get_db)):
    if payload.table_id:
        table = await db.scalar(select(DiningTable).where(
            DiningTable.id == payload.table_id,
            DiningTable.tenant_id == ctx.tenant_id,
            DiningTable.venue_id == ctx.venue_id,
            DiningTable.active.is_(True),
        ))
        if table is None:
            raise HTTPException(status_code=404, detail="Mesa no encontrada.")
    item = Reservation(tenant_id=ctx.tenant_id, venue_id=ctx.venue_id, **payload.model_dump())
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return {"id": str(item.id), "status": item.status}


@router.patch("/{reservation_id}/status")
async def change_reservation_status(reservation_id: UUID, payload: ReservationStatus, ctx: TenantContext = Depends(get_tenant_context), db: AsyncSession = Depends(get_db)):
    item = await db.scalar(select(Reservation).where(
        Reservation.id == reservation_id,
        Reservation.tenant_id == ctx.tenant_id,
        Reservation.venue_id == ctx.venue_id,
    ))
    if item is None:
        raise HTTPException(status_code=404, detail="Reserva no encontrada.")
    item.status = payload.status
    await db.commit()
    return {"id": str(item.id), "status": item.status}
