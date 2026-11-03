from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import TenantContext, get_tenant_context
from app.db import get_db
from app.models.hospitality import KitchenEvent, Order, OrderLine

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
    line.kitchen_status = payload.status
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
