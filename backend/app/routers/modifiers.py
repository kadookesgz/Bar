from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import TenantContext, get_tenant_context
from app.db import get_db
from app.models.hospitality import Modifier, ModifierGroup, Product, ProductModifierGroup

router = APIRouter(prefix="/api/v1/modifiers", tags=["product modifiers and formats"])


class ModifierInput(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    price_delta: Decimal = Field(default=0, max_digits=12, decimal_places=2)


class GroupCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    min_select: int = Field(default=0, ge=0, le=20)
    max_select: int = Field(default=1, ge=1, le=20)
    required: bool = False
    product_ids: list[UUID] = Field(min_length=1)
    modifiers: list[ModifierInput] = Field(min_length=1)


@router.get("/groups")
async def list_groups(ctx: TenantContext = Depends(get_tenant_context), db: AsyncSession = Depends(get_db)):
    groups = await db.scalars(select(ModifierGroup).where(
        ModifierGroup.tenant_id == ctx.tenant_id, ModifierGroup.venue_id == ctx.venue_id
    ).order_by(ModifierGroup.name))
    output = []
    for group in groups:
        product_links = await db.scalars(select(ProductModifierGroup).where(
            ProductModifierGroup.group_id == group.id, ProductModifierGroup.tenant_id == ctx.tenant_id,
            ProductModifierGroup.venue_id == ctx.venue_id,
        ))
        modifiers = await db.scalars(select(Modifier).where(
            Modifier.group_id == group.id, Modifier.tenant_id == ctx.tenant_id,
            Modifier.venue_id == ctx.venue_id, Modifier.active.is_(True),
        ))
        output.append({
            "id": str(group.id), "name": group.name, "min_select": group.min_select,
            "max_select": group.max_select, "required": group.required,
            "product_ids": [str(link.product_id) for link in product_links],
            "modifiers": [{"id": str(m.id), "name": m.name, "price_delta": str(m.price_delta)} for m in modifiers],
        })
    return output


@router.post("/groups", status_code=201)
async def create_group(payload: GroupCreate, ctx: TenantContext = Depends(get_tenant_context), db: AsyncSession = Depends(get_db)):
    if ctx.role not in {"owner", "admin", "manager"}:
        raise HTTPException(status_code=403, detail="No tienes permiso para configurar modificadores.")
    if payload.min_select > payload.max_select:
        raise HTTPException(status_code=422, detail="La selección mínima no puede superar la máxima.")
    for product_id in payload.product_ids:
        product = await db.scalar(select(Product.id).where(
            Product.id == product_id, Product.tenant_id == ctx.tenant_id,
            Product.venue_id == ctx.venue_id,
        ))
        if not product:
            raise HTTPException(status_code=404, detail="Producto no encontrado.")
    group = ModifierGroup(
        tenant_id=ctx.tenant_id, venue_id=ctx.venue_id, name=payload.name,
        min_select=payload.min_select, max_select=payload.max_select, required=payload.required,
    )
    db.add(group)
    await db.flush()
    for product_id in payload.product_ids:
        db.add(ProductModifierGroup(
            tenant_id=ctx.tenant_id, venue_id=ctx.venue_id,
            product_id=product_id, group_id=group.id,
        ))
    for modifier in payload.modifiers:
        db.add(Modifier(
            tenant_id=ctx.tenant_id, venue_id=ctx.venue_id, group_id=group.id,
            name=modifier.name, price_delta=modifier.price_delta,
        ))
    await db.commit()
    return {"id": str(group.id), "name": group.name}
