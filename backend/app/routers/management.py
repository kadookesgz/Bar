from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import TenantContext, get_tenant_context
from app.db import get_db
from app.models.hospitality import Order, Product, DiningTable

router = APIRouter(prefix="/api/v1/management", tags=["management"])


@router.get("/dashboard")
async def dashboard(ctx: TenantContext = Depends(get_tenant_context), db: AsyncSession = Depends(get_db)):
    open_orders = await db.scalar(select(func.count(Order.id)).where(
        Order.tenant_id == ctx.tenant_id,
        Order.venue_id == ctx.venue_id,
        Order.status.in_(["open", "sent", "preparing", "ready"]),
    ))
    active_products = await db.scalar(select(func.count(Product.id)).where(
        Product.tenant_id == ctx.tenant_id,
        Product.venue_id == ctx.venue_id,
        Product.active.is_(True),
    ))
    active_tables = await db.scalar(select(func.count(DiningTable.id)).where(
        DiningTable.tenant_id == ctx.tenant_id,
        DiningTable.venue_id == ctx.venue_id,
        DiningTable.active.is_(True),
    ))
    return {
        "open_orders": open_orders or 0,
        "active_products": active_products or 0,
        "active_tables": active_tables or 0,
        "sales_today": "0.00",
        "note": "Las ventas se habilitarán al completar caja y pagos.",
    }
