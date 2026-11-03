from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import TenantContext, get_tenant_context
from app.db import get_db
from app.models.hospitality import DiningArea, PriceList, PriceListItem, Product

router = APIRouter(prefix="/api/v1/price-lists", tags=["price lists and room pricing"])


class PriceEntry(BaseModel):
    product_id: UUID
    price: Decimal = Field(ge=0, max_digits=12, decimal_places=2)


class PriceListCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    area_id: UUID | None = None
    items: list[PriceEntry] = Field(default_factory=list)


@router.get("")
async def list_price_lists(ctx: TenantContext = Depends(get_tenant_context), db: AsyncSession = Depends(get_db)):
    rows = await db.scalars(select(PriceList).where(
        PriceList.tenant_id == ctx.tenant_id, PriceList.venue_id == ctx.venue_id
    ).order_by(PriceList.name))
    return [{"id": str(x.id), "name": x.name, "area_id": str(x.area_id) if x.area_id else None, "active": x.active} for x in rows]


@router.post("", status_code=201)
async def create_price_list(payload: PriceListCreate, ctx: TenantContext = Depends(get_tenant_context), db: AsyncSession = Depends(get_db)):
    if ctx.role not in {"owner", "admin", "manager"}:
        raise HTTPException(status_code=403, detail="No tienes permiso para gestionar tarifas.")
    if payload.area_id:
        area = await db.scalar(select(DiningArea.id).where(
            DiningArea.id == payload.area_id, DiningArea.tenant_id == ctx.tenant_id,
            DiningArea.venue_id == ctx.venue_id,
        ))
        if not area:
            raise HTTPException(status_code=404, detail="Zona no encontrada.")
    for entry in payload.items:
        product = await db.scalar(select(Product.id).where(
            Product.id == entry.product_id, Product.tenant_id == ctx.tenant_id,
            Product.venue_id == ctx.venue_id,
        ))
        if not product:
            raise HTTPException(status_code=404, detail="Producto no encontrado.")
    item = PriceList(tenant_id=ctx.tenant_id, venue_id=ctx.venue_id, name=payload.name, area_id=payload.area_id)
    db.add(item)
    await db.flush()
    for entry in payload.items:
        db.add(PriceListItem(
            tenant_id=ctx.tenant_id, venue_id=ctx.venue_id, price_list_id=item.id,
            product_id=entry.product_id, price=entry.price,
        ))
    await db.commit()
    return {"id": str(item.id), "name": item.name}
