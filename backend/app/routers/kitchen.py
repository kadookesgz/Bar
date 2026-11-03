from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import TenantContext, get_tenant_context
from app.db import get_db
from app.models.hospitality import KitchenEvent, Order, OrderLine, Recipe, RecipeLine, StockItem, StockMovement

router = APIRouter(prefix="/api/v1/kitchen", tags=["kitchen display"])


class KitchenStatusRequest(BaseModel):
    status: str = Field(pattern="^(pending|preparing|ready|served|cancelled)$")
    note: str | None = None


@router.patch("/lines/{line_id}/status")
async def update_line_status(line_id: UUID, payload: KitchenStatusRequest, ctx: TenantContext = Depends(get_tenant_context), db: AsyncSession = Depends(get_db)):
    line = await db.scalar(select(OrderLine).where(
        OrderLine.id == line_id,
        OrderLine.tenant_id == ctx.tenant_id,
        OrderLine.venue_id == ctx.venue_id,
    ))
    if line is None:
        raise HTTPException(status_code=404, detail="Línea de comanda no encontrada.")
    previous_status = line.kitchen_status
    line.kitchen_status = payload.status
    if payload.status in {"ready", "served"} and previous_status not in {"ready", "served"} and line.product_id:
        recipe = await db.scalar(select(Recipe).where(
            Recipe.product_id == line.product_id, Recipe.tenant_id == ctx.tenant_id,
            Recipe.venue_id == ctx.venue_id,
        ))
        if recipe:
            components = await db.scalars(select(RecipeLine).where(
                RecipeLine.recipe_id == recipe.id, RecipeLine.tenant_id == ctx.tenant_id,
                RecipeLine.venue_id == ctx.venue_id,
            ))
            for component in components:
                stock = await db.scalar(select(StockItem).where(
                    StockItem.id == component.stock_item_id, StockItem.tenant_id == ctx.tenant_id,
                    StockItem.venue_id == ctx.venue_id,
                ))
                if stock:
                    used = component.quantity * line.quantity / recipe.yield_quantity
                    stock.current_stock -= used
                    db.add(StockMovement(
                        tenant_id=ctx.tenant_id, venue_id=ctx.venue_id, stock_item_id=stock.id,
                        movement_type="sale", quantity=-used, unit_cost=stock.cost_per_unit,
                        reference=str(line.order_id), note="Consumo automático por elaboración de comanda",
                    ))
    db.add(KitchenEvent(
        tenant_id=ctx.tenant_id, venue_id=ctx.venue_id, order_line_id=line.id,
        status=payload.status, actor_user_id=ctx.user_id, note=payload.note,
    ))
    order = await db.scalar(select(Order).where(
        Order.id == line.order_id,
        Order.tenant_id == ctx.tenant_id,
        Order.venue_id == ctx.venue_id,
    ))
    if order:
        lines = list(await db.scalars(select(OrderLine).where(
            OrderLine.order_id == order.id,
            OrderLine.tenant_id == ctx.tenant_id,
            OrderLine.venue_id == ctx.venue_id,
        )))
        if lines and all(x.kitchen_status in {"ready", "served", "cancelled"} for x in lines):
            order.status = "ready"
        elif any(x.kitchen_status == "preparing" for x in lines):
            order.status = "preparing"
    await db.commit()
    return {"line_id": str(line.id), "status": line.kitchen_status, "order_status": order.status if order else None}
