from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import TenantContext, get_tenant_context
from app.db import get_db
from app.models.hospitality import Order, OrderLine, Payment

router = APIRouter(prefix="/api/v1/reports", tags=["reports and analytics"])


@router.get("/daily")
async def daily_report(report_date: date | None = None, ctx: TenantContext = Depends(get_tenant_context), db: AsyncSession = Depends(get_db)):
    day = report_date or datetime.now(timezone.utc).date()
    start = datetime.combine(day, time.min, tzinfo=timezone.utc)
    end = start + timedelta(days=1)
    sales = await db.scalar(select(func.coalesce(func.sum(Order.total), 0)).where(
        Order.tenant_id == ctx.tenant_id, Order.venue_id == ctx.venue_id,
        Order.status == "paid", Order.closed_at >= start, Order.closed_at < end,
    ))
    paid_orders = await db.scalar(select(func.count(Order.id)).where(
        Order.tenant_id == ctx.tenant_id, Order.venue_id == ctx.venue_id,
        Order.status == "paid", Order.closed_at >= start, Order.closed_at < end,
    ))
    payments = await db.execute(select(Payment.method, func.sum(Payment.amount)).where(
        Payment.tenant_id == ctx.tenant_id, Payment.venue_id == ctx.venue_id,
        Payment.status == "captured", Payment.paid_at >= start, Payment.paid_at < end,
    ).group_by(Payment.method))
    best_sellers = await db.execute(
        select(OrderLine.product_name, func.sum(OrderLine.quantity), func.sum(OrderLine.line_total))
        .join(Order, Order.id == OrderLine.order_id)
        .where(
            OrderLine.tenant_id == ctx.tenant_id, OrderLine.venue_id == ctx.venue_id,
            Order.tenant_id == ctx.tenant_id, Order.venue_id == ctx.venue_id,
            Order.status == "paid", Order.closed_at >= start, Order.closed_at < end,
        ).group_by(OrderLine.product_name).order_by(func.sum(OrderLine.quantity).desc()).limit(10)
    )
    return {
        "date": day.isoformat(),
        "sales_total": str(Decimal(sales or 0)),
        "paid_orders": paid_orders or 0,
        "average_ticket": str((Decimal(sales or 0) / paid_orders).quantize(Decimal("0.01")) if paid_orders else Decimal("0.00")),
        "payments_by_method": [{"method": method, "amount": str(amount)} for method, amount in payments.all()],
        "top_products": [{"name": name, "quantity": str(quantity), "sales": str(amount)} for name, quantity, amount in best_sellers.all()],
    }
