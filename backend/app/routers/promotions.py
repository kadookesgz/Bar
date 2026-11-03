from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import TenantContext, get_tenant_context
from app.db import get_db
from app.models.hospitality import AuditLog, Order, Promotion

router = APIRouter(prefix="/api/v1/promotions", tags=["promotions and discounts"])


class PromotionCreate(BaseModel):
    name: str = Field(min_length=2, max_length=140)
    code: str | None = Field(default=None, max_length=40)
    discount_type: str = Field(pattern="^(amount|percent)$")
    discount_value: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    minimum_amount: Decimal = Field(default=0, ge=0)
    starts_at: datetime | None = None
    ends_at: datetime | None = None


class ApplyPromotion(BaseModel):
    order_id: UUID
    code: str = Field(min_length=1, max_length=40)


@router.get("")
async def list_promotions(ctx: TenantContext = Depends(get_tenant_context), db: AsyncSession = Depends(get_db)):
    rows = await db.scalars(select(Promotion).where(
        Promotion.tenant_id == ctx.tenant_id, Promotion.venue_id == ctx.venue_id
    ).order_by(Promotion.name))
    return [{"id": str(x.id), "name": x.name, "code": x.code, "discount_type": x.discount_type,
             "discount_value": str(x.discount_value), "minimum_amount": str(x.minimum_amount),
             "active": x.active} for x in rows]


@router.post("", status_code=201)
async def create_promotion(payload: PromotionCreate, ctx: TenantContext = Depends(get_tenant_context), db: AsyncSession = Depends(get_db)):
    if ctx.role not in {"owner", "admin", "manager"}:
        raise HTTPException(status_code=403, detail="No tienes permiso para gestionar promociones.")
    item = Promotion(tenant_id=ctx.tenant_id, venue_id=ctx.venue_id, **payload.model_dump())
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return {"id": str(item.id), "name": item.name, "code": item.code}


@router.post("/apply")
async def apply_promotion(payload: ApplyPromotion, ctx: TenantContext = Depends(get_tenant_context), db: AsyncSession = Depends(get_db)):
    now = datetime.now(timezone.utc)
    promo = await db.scalar(select(Promotion).where(
        Promotion.tenant_id == ctx.tenant_id, Promotion.venue_id == ctx.venue_id,
        Promotion.code == payload.code, Promotion.active.is_(True),
    ))
    if promo is None or (promo.starts_at and promo.starts_at > now) or (promo.ends_at and promo.ends_at < now):
        raise HTTPException(status_code=404, detail="Código promocional no válido o caducado.")
    order = await db.scalar(select(Order).where(
        Order.id == payload.order_id, Order.tenant_id == ctx.tenant_id,
        Order.venue_id == ctx.venue_id, Order.status != "paid",
    ))
    if order is None:
        raise HTTPException(status_code=404, detail="Cuenta abierta no encontrada.")
    if order.subtotal < promo.minimum_amount:
        raise HTTPException(status_code=409, detail="La cuenta no alcanza el mínimo de la promoción.")
    discount = order.subtotal * promo.discount_value / Decimal("100") if promo.discount_type == "percent" else promo.discount_value
    if discount > order.subtotal:
        discount = order.subtotal
    order.discount_total = discount.quantize(Decimal("0.01"))
    order.total = order.subtotal - order.discount_total
    if order.subtotal:
        order.tax_total = (order.tax_total * order.total / order.subtotal).quantize(Decimal("0.01"))
    db.add(AuditLog(
        tenant_id=ctx.tenant_id, venue_id=ctx.venue_id, actor_user_id=ctx.user_id,
        action="promotion.applied", entity_type="order", entity_id=order.id,
        details={"promotion_id": str(promo.id), "code": promo.code},
    ))
    await db.commit()
    return {"order_id": str(order.id), "promotion": promo.name,
            "discount_total": str(order.discount_total), "total": str(order.total)}
