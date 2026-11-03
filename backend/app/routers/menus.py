from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import TenantContext, get_tenant_context
from app.db import get_db
from app.models.hospitality import Menu, MenuItem, Product

router = APIRouter(prefix="/api/v1/menus", tags=["menus and combos"])


class MenuItemInput(BaseModel):
    product_id: UUID
    group_name: str | None = None
    selection_type: str = Field(default="included", pattern="^(included|choice|optional)$")
    supplement: Decimal = Field(default=0, ge=0)


class MenuCreate(BaseModel):
    name: str = Field(min_length=2, max_length=140)
    description: str | None = None
    fixed_price: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    available_days: list[int] = Field(default_factory=list)
    available_from: str | None = None
    available_until: str | None = None
    items: list[MenuItemInput] = Field(min_length=1)


@router.get("")
async def list_menus(ctx: TenantContext = Depends(get_tenant_context), db: AsyncSession = Depends(get_db)):
    rows = await db.scalars(select(Menu).where(
        Menu.tenant_id == ctx.tenant_id, Menu.venue_id == ctx.venue_id
    ).order_by(Menu.name))
    output = []
    for menu in rows:
        items = await db.scalars(select(MenuItem).where(
            MenuItem.menu_id == menu.id, MenuItem.tenant_id == ctx.tenant_id,
            MenuItem.venue_id == ctx.venue_id,
        ))
        output.append({
            "id": str(menu.id), "name": menu.name, "description": menu.description,
            "fixed_price": str(menu.fixed_price), "active": menu.active,
            "available_days": menu.available_days,
            "items": [{"product_id": str(i.product_id), "group_name": i.group_name,
                       "selection_type": i.selection_type, "supplement": str(i.supplement)} for i in items],
        })
    return output


@router.post("", status_code=201)
async def create_menu(payload: MenuCreate, ctx: TenantContext = Depends(get_tenant_context), db: AsyncSession = Depends(get_db)):
    if ctx.role not in {"owner", "admin", "manager"}:
        raise HTTPException(status_code=403, detail="No tienes permiso para gestionar menús.")
    for item in payload.items:
        product = await db.scalar(select(Product.id).where(
            Product.id == item.product_id, Product.tenant_id == ctx.tenant_id,
            Product.venue_id == ctx.venue_id, Product.active.is_(True),
        ))
        if not product:
            raise HTTPException(status_code=404, detail="Producto de menú no encontrado.")
    menu = Menu(
        tenant_id=ctx.tenant_id, venue_id=ctx.venue_id, name=payload.name,
        description=payload.description, fixed_price=payload.fixed_price,
        available_days=payload.available_days, available_from=payload.available_from,
        available_until=payload.available_until,
    )
    db.add(menu)
    await db.flush()
    for item in payload.items:
        db.add(MenuItem(
            tenant_id=ctx.tenant_id, venue_id=ctx.venue_id, menu_id=menu.id,
            product_id=item.product_id, group_name=item.group_name,
            selection_type=item.selection_type, supplement=item.supplement,
        ))
    await db.commit()
    return {"id": str(menu.id), "name": menu.name, "fixed_price": str(menu.fixed_price)}
