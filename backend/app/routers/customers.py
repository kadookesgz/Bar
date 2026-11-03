from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import TenantContext, get_tenant_context
from app.db import get_db
from app.models.hospitality import Customer

router = APIRouter(prefix="/api/v1/customers", tags=["customers and loyalty"])


class CustomerCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    email: EmailStr | None = None
    phone: str | None = None
    notes: str | None = None


class LoyaltyAdjustment(BaseModel):
    points: int = Field(ne=0, ge=-100000, le=100000)
    reason: str = Field(min_length=2, max_length=240)


@router.get("")
async def list_customers(ctx: TenantContext = Depends(get_tenant_context), db: AsyncSession = Depends(get_db)):
    rows = await db.scalars(select(Customer).where(
        Customer.tenant_id == ctx.tenant_id, Customer.venue_id == ctx.venue_id
    ).order_by(Customer.name).limit(500))
    return [{"id": str(x.id), "name": x.name, "email": x.email, "phone": x.phone, "loyalty_points": x.loyalty_points} for x in rows]


@router.post("", status_code=201)
async def create_customer(payload: CustomerCreate, ctx: TenantContext = Depends(get_tenant_context), db: AsyncSession = Depends(get_db)):
    item = Customer(tenant_id=ctx.tenant_id, venue_id=ctx.venue_id, **payload.model_dump())
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return {"id": str(item.id), "name": item.name, "loyalty_points": item.loyalty_points}


@router.post("/{customer_id}/points")
async def adjust_points(customer_id: UUID, payload: LoyaltyAdjustment, ctx: TenantContext = Depends(get_tenant_context), db: AsyncSession = Depends(get_db)):
    item = await db.scalar(select(Customer).where(
        Customer.id == customer_id, Customer.tenant_id == ctx.tenant_id, Customer.venue_id == ctx.venue_id
    ))
    if item is None:
        raise HTTPException(status_code=404, detail="Cliente no encontrado.")
    if item.loyalty_points + payload.points < 0:
        raise HTTPException(status_code=409, detail="El saldo de puntos no puede ser negativo.")
    item.loyalty_points += payload.points
    await db.commit()
    return {"customer_id": str(item.id), "loyalty_points": item.loyalty_points, "reason": payload.reason}
