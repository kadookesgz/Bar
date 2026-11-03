from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from secrets import randbelow

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import TenantContext, get_tenant_context
from app.db import get_db
from app.models.hospitality import DiningTable, Order, OrderLine, Product
from app.schemas import OrderCreate, OrderOut

router = APIRouter(prefix="/api/v1/orders", tags=["orders"])


def money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


@router.get("", response_model=list[OrderOut])
async def list_open_orders(ctx: TenantContext = Depends(get_tenant_context), db: AsyncSession = Depends(get_db)):
    result = await db.scalars(select(Order).where(
        Order.tenant_id == ctx.tenant_id,
        Order.venue_id == ctx.venue_id,
        Order.status.in_(["open", "sent", "preparing", "ready"]),
    ).order_by(Order.opened_at))
    return list(result)


@router.post("", response_model=OrderOut, status_code=201)
async def create_order(payload: OrderCreate, ctx: TenantContext = Depends(get_tenant_context), db: AsyncSession = Depends(get_db)):
    if payload.table_id:
        table = await db.scalar(select(DiningTable).where(
            DiningTable.id == payload.table_id,
            DiningTable.tenant_id == ctx.tenant_id,
            DiningTable.venue_id == ctx.venue_id,
            DiningTable.active.is_(True),
        ))
        if table is None:
            raise HTTPException(status_code=404, detail="Mesa no encontrada.")

    products = {}
    for line in payload.lines:
        product = await db.scalar(select(Product).where(
            Product.id == line.product_id,
            Product.tenant_id == ctx.tenant_id,
            Product.venue_id == ctx.venue_id,
            Product.active.is_(True),
        ))
        if product is None:
            raise HTTPException(status_code=404, detail=f"Producto no disponible: {line.product_id}")
        products[line.product_id] = product

    subtotal = Decimal("0.00")
    tax_total = Decimal("0.00")
    order_lines = []
    for line in payload.lines:
        product = products[line.product_id]
        line_total = money(product.price * line.quantity)
        tax = money(line_total * product.tax_rate / Decimal("100"))
        subtotal += line_total
        tax_total += tax
        order_lines.append(OrderLine(
            tenant_id=ctx.tenant_id,
            venue_id=ctx.venue_id,
            product_id=product.id,
            product_name=product.name,
            quantity=line.quantity,
            unit_price=product.price,
            line_total=line_total,
            tax_rate=product.tax_rate,
            notes=line.notes,
        ))

    order = Order(
        tenant_id=ctx.tenant_id,
        venue_id=ctx.venue_id,
        order_number=randbelow(900000) + 100000,
        table_id=payload.table_id,
        channel=payload.channel,
        status="open",
        subtotal=money(subtotal),
        tax_total=money(tax_total),
        total=money(subtotal),
        notes=payload.notes,
    )
    db.add(order)
    await db.flush()
    for line in order_lines:
        line.order_id = order.id
        db.add(line)
    await db.commit()
    await db.refresh(order)
    return order


@router.post("/{order_id}/send-to-kitchen", response_model=OrderOut)
async def send_to_kitchen(order_id: str, ctx: TenantContext = Depends(get_tenant_context), db: AsyncSession = Depends(get_db)):
    order = await db.scalar(select(Order).where(
        Order.id == order_id,
        Order.tenant_id == ctx.tenant_id,
        Order.venue_id == ctx.venue_id,
        Order.status == "open",
    ))
    if order is None:
        raise HTTPException(status_code=404, detail="Comanda no encontrada o ya enviada.")
    order.status = "sent"
    await db.commit()
    await db.refresh(order)
    return order


@router.get("/kitchen/queue")
async def kitchen_queue(ctx: TenantContext = Depends(get_tenant_context), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Order, OrderLine).join(OrderLine, OrderLine.order_id == Order.id).where(
            Order.tenant_id == ctx.tenant_id,
            Order.venue_id == ctx.venue_id,
            Order.status.in_(["sent", "preparing", "ready"]),
            OrderLine.tenant_id == ctx.tenant_id,
            OrderLine.venue_id == ctx.venue_id,
        ).order_by(Order.opened_at)
    )
    rows = result.all()
    return [{
        "order_id": str(order.id),
        "order_number": order.order_number,
        "table_id": str(order.table_id) if order.table_id else None,
        "channel": order.channel,
        "order_status": order.status,
        "opened_at": order.opened_at.isoformat(),
        "line_id": str(line.id),
        "product_name": line.product_name,
        "quantity": str(line.quantity),
        "notes": line.notes,
        "kitchen_status": line.kitchen_status,
    } for order, line in rows]
