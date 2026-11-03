from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from html import escape as html_escape
from secrets import randbelow
from uuid import UUID
from pydantic import BaseModel, Field

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import TenantContext, get_tenant_context
from app.core.sync import record_sync_event
from app.db import get_db
from app.models.hospitality import AuditLog, DiningTable, Modifier, ModifierGroup, Order, OrderLine, Payment, Product, ProductModifierGroup
from app.schemas import OrderCreate, OrderLineCreate, OrderOut

router = APIRouter(prefix="/api/v1/orders", tags=["orders"])


def money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)



async def _resolve_modifiers(db: AsyncSession, ctx: TenantContext, product: Product, modifier_ids: list[UUID]):
    associations = list(await db.scalars(select(ProductModifierGroup).where(
        ProductModifierGroup.product_id == product.id,
        ProductModifierGroup.tenant_id == ctx.tenant_id,
        ProductModifierGroup.venue_id == ctx.venue_id,
    )))
    group_ids = {x.group_id for x in associations}
    groups = list(await db.scalars(select(ModifierGroup).where(
        ModifierGroup.id.in_(group_ids) if group_ids else ModifierGroup.id.is_(None),
        ModifierGroup.tenant_id == ctx.tenant_id,
        ModifierGroup.venue_id == ctx.venue_id,
    )))
    selected = []
    if modifier_ids:
        selected = list(await db.scalars(select(Modifier).where(
            Modifier.id.in_(modifier_ids),
            Modifier.group_id.in_(group_ids) if group_ids else Modifier.group_id.is_(None),
            Modifier.tenant_id == ctx.tenant_id,
            Modifier.venue_id == ctx.venue_id,
            Modifier.active.is_(True),
        )))
        if len(selected) != len(set(modifier_ids)):
            raise HTTPException(status_code=422, detail="Hay modificadores no válidos para este producto.")
    for group in groups:
        count = sum(1 for item in selected if item.group_id == group.id)
        minimum = max(group.min_select, 1 if group.required else 0)
        if count < minimum or count > group.max_select:
            raise HTTPException(status_code=422, detail=f"Selecciona entre {minimum} y {group.max_select} opciones en {group.name}.")
    extra = sum((item.price_delta for item in selected), Decimal("0.00"))
    details = [{"id": str(item.id), "name": item.name, "price_delta": str(item.price_delta)} for item in selected]
    return money(product.price + extra), details


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
        unit_price, modifier_details = await _resolve_modifiers(db, ctx, product, line.modifier_ids)
        line_total = money(unit_price * line.quantity)
        tax = money(line_total * product.tax_rate / (Decimal("100") + product.tax_rate))
        subtotal += line_total
        tax_total += tax
        order_lines.append(OrderLine(
            tenant_id=ctx.tenant_id,
            venue_id=ctx.venue_id,
            product_id=product.id,
            product_name=product.name,
            quantity=line.quantity,
            unit_price=unit_price,
            line_total=line_total,
            tax_rate=product.tax_rate,
            modifiers=modifier_details,
            notes=line.notes,
        ))

    if payload.table_id:
        existing_order = await db.scalar(select(Order).where(
            Order.table_id == payload.table_id,
            Order.tenant_id == ctx.tenant_id,
            Order.venue_id == ctx.venue_id,
            Order.status.in_(["open", "sent", "preparing", "ready"]),
        ).order_by(Order.opened_at.desc()).with_for_update())
        if existing_order:
            for line in order_lines:
                line.order_id = existing_order.id
                db.add(line)
            existing_order.subtotal = money(existing_order.subtotal + subtotal)
            existing_order.tax_total = money(existing_order.tax_total + tax_total)
            existing_order.total = money(existing_order.subtotal - existing_order.discount_total)
            existing_order.status = "sent"
            db.add(AuditLog(
                tenant_id=ctx.tenant_id, venue_id=ctx.venue_id, actor_user_id=ctx.user_id,
                action="order.lines_added_from_pos", entity_type="order", entity_id=existing_order.id,
                details={"count": len(order_lines)},
            ))
            record_sync_event(db, ctx, aggregate_type="order", aggregate_id=existing_order.id, event_type="order.lines_added", payload={"line_count": len(order_lines), "total": str(existing_order.total)})
            await db.commit()
            await db.refresh(existing_order)
            return existing_order

    order = Order(
        tenant_id=ctx.tenant_id,
        venue_id=ctx.venue_id,
        order_number=randbelow(900000) + 100000,
        table_id=payload.table_id,
        channel=payload.channel,
        customer_name=payload.customer_name,
        customer_phone=payload.customer_phone,
        delivery_address=payload.delivery_address,
        scheduled_for=payload.scheduled_for,
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
    record_sync_event(db, ctx, aggregate_type="order", aggregate_id=order.id, event_type="order.created", payload={"order_number": order.order_number, "channel": order.channel, "total": str(order.total), "table_id": str(order.table_id) if order.table_id else None})
    await db.commit()
    await db.refresh(order)
    return order


@router.post("/{order_id}/send-to-kitchen", response_model=OrderOut)
async def send_to_kitchen(order_id: str, ctx: TenantContext = Depends(get_tenant_context), db: AsyncSession = Depends(get_db)):
    order = await db.scalar(select(Order).where(
        Order.id == order_id,
        Order.tenant_id == ctx.tenant_id,
        Order.venue_id == ctx.venue_id,
        Order.status.in_(["open", "sent", "preparing"]),
    ))
    if order is None:
        raise HTTPException(status_code=404, detail="Comanda no encontrada o no modificable.")
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
            OrderLine.kitchen_status.in_(["pending", "preparing"]),
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


class DiscountRequest(BaseModel):
    kind: str = Field(pattern="^(amount|percent)$")
    value: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    reason: str = Field(min_length=2, max_length=240)


class MoveTableRequest(BaseModel):
    table_id: UUID | None = None


class SplitLineRequest(BaseModel):
    line_id: UUID
    quantity: Decimal = Field(gt=0, max_digits=10, decimal_places=3)


class SplitOrderRequest(BaseModel):
    lines: list[SplitLineRequest] = Field(min_length=1)


async def _recalculate_order(db: AsyncSession, order: Order, ctx: TenantContext):
    lines = list(await db.scalars(select(OrderLine).where(
        OrderLine.order_id == order.id,
        OrderLine.tenant_id == ctx.tenant_id,
        OrderLine.venue_id == ctx.venue_id,
    )))
    subtotal = sum((line.line_total for line in lines), Decimal("0.00"))
    order.subtotal = money(subtotal)
    order.total = money(max(Decimal("0.00"), subtotal - order.discount_total))
    order.tax_total = money(sum(
        (line.line_total * line.tax_rate / (Decimal("100") + line.tax_rate) for line in lines),
        Decimal("0.00"),
    ) * (order.total / subtotal if subtotal else Decimal("0.00")))


@router.post("/{order_id}/lines", status_code=201)
async def add_order_lines(order_id: str, payload: list[OrderLineCreate], ctx: TenantContext = Depends(get_tenant_context), db: AsyncSession = Depends(get_db)):
    order = await db.scalar(select(Order).where(
        Order.id == order_id, Order.tenant_id == ctx.tenant_id,
        Order.venue_id == ctx.venue_id, Order.status.in_(["open", "sent", "preparing"]),
    ))
    if order is None:
        raise HTTPException(status_code=404, detail="Comanda abierta no encontrada.")
    for requested in payload:
        product = await db.scalar(select(Product).where(
            Product.id == requested.product_id, Product.tenant_id == ctx.tenant_id,
            Product.venue_id == ctx.venue_id, Product.active.is_(True),
        ))
        if product is None:
            raise HTTPException(status_code=404, detail="Producto no disponible.")
        unit_price, modifier_details = await _resolve_modifiers(db, ctx, product, requested.modifier_ids)
        line_total = money(unit_price * requested.quantity)
        db.add(OrderLine(
            tenant_id=ctx.tenant_id, venue_id=ctx.venue_id, order_id=order.id,
            product_id=product.id, product_name=product.name, quantity=requested.quantity,
            unit_price=unit_price, line_total=line_total, tax_rate=product.tax_rate,
            modifiers=modifier_details, notes=requested.notes,
        ))
    await db.flush()
    await _recalculate_order(db, order, ctx)
    db.add(AuditLog(
        tenant_id=ctx.tenant_id, venue_id=ctx.venue_id, actor_user_id=ctx.user_id,
        action="order.lines_added", entity_type="order", entity_id=order.id,
        details={"count": len(payload)},
    ))
    record_sync_event(db, ctx, aggregate_type="order", aggregate_id=order.id, event_type="order.lines_added", payload={"line_count": len(payload), "total": str(order.total)})
    await db.commit()
    await db.refresh(order)
    return {"order_id": str(order.id), "total": str(order.total), "status": order.status}


@router.patch("/{order_id}/table")
async def move_order_table(order_id: str, payload: MoveTableRequest, ctx: TenantContext = Depends(get_tenant_context), db: AsyncSession = Depends(get_db)):
    order = await db.scalar(select(Order).where(
        Order.id == order_id, Order.tenant_id == ctx.tenant_id,
        Order.venue_id == ctx.venue_id, Order.status != "paid",
    ))
    if order is None:
        raise HTTPException(status_code=404, detail="Cuenta abierta no encontrada.")
    if payload.table_id:
        table = await db.scalar(select(DiningTable).where(
            DiningTable.id == payload.table_id, DiningTable.tenant_id == ctx.tenant_id,
            DiningTable.venue_id == ctx.venue_id, DiningTable.active.is_(True),
        ))
        if table is None:
            raise HTTPException(status_code=404, detail="Mesa destino no encontrada.")
    order.table_id = payload.table_id
    db.add(AuditLog(
        tenant_id=ctx.tenant_id, venue_id=ctx.venue_id, actor_user_id=ctx.user_id,
        action="order.table_changed", entity_type="order", entity_id=order.id,
        details={"table_id": str(payload.table_id) if payload.table_id else None},
    ))
    await db.commit()
    return {"order_id": str(order.id), "table_id": str(order.table_id) if order.table_id else None}


@router.post("/{order_id}/discount")
async def apply_discount(order_id: str, payload: DiscountRequest, ctx: TenantContext = Depends(get_tenant_context), db: AsyncSession = Depends(get_db)):
    order = await db.scalar(select(Order).where(
        Order.id == order_id, Order.tenant_id == ctx.tenant_id,
        Order.venue_id == ctx.venue_id, Order.status != "paid",
    ))
    if order is None:
        raise HTTPException(status_code=404, detail="Cuenta abierta no encontrada.")
    from sqlalchemy import func
    paid_total = await db.scalar(select(func.coalesce(func.sum(Payment.amount), 0)).where(
        Payment.order_id == order.id, Payment.tenant_id == ctx.tenant_id,
        Payment.venue_id == ctx.venue_id, Payment.status == "captured",
    ))
    discount = order.subtotal * payload.value / Decimal("100") if payload.kind == "percent" else payload.value
    if discount > order.subtotal:
        raise HTTPException(status_code=409, detail="El descuento no puede superar el importe de la cuenta.")
    if order.subtotal - discount < Decimal(paid_total or 0):
        raise HTTPException(status_code=409, detail="El descuento no puede dejar el total por debajo de lo ya cobrado.")
    order.discount_total = money(discount)
    order.total = money(order.subtotal - order.discount_total)
    if order.subtotal:
        order.tax_total = money(order.tax_total * order.total / order.subtotal)
    db.add(AuditLog(
        tenant_id=ctx.tenant_id, venue_id=ctx.venue_id, actor_user_id=ctx.user_id,
        action="order.discount_applied", entity_type="order", entity_id=order.id,
        details={"kind": payload.kind, "value": str(payload.value), "reason": payload.reason},
    ))
    record_sync_event(db, ctx, aggregate_type="order", aggregate_id=order.id, event_type="order.discounted", payload={"discount_total": str(order.discount_total), "total": str(order.total)})
    await db.commit()
    return {"order_id": str(order.id), "discount_total": str(order.discount_total), "total": str(order.total)}


@router.post("/{order_id}/split", status_code=201)
async def split_order(order_id: str, payload: SplitOrderRequest, ctx: TenantContext = Depends(get_tenant_context), db: AsyncSession = Depends(get_db)):
    source = await db.scalar(select(Order).where(
        Order.id == order_id, Order.tenant_id == ctx.tenant_id,
        Order.venue_id == ctx.venue_id, Order.status.in_(["open", "sent", "preparing", "ready"]),
    ))
    if source is None:
        raise HTTPException(status_code=404, detail="Cuenta abierta no encontrada.")
    if order.discount_total > 0:
        raise HTTPException(status_code=409, detail="Retira el descuento antes de dividir la cuenta.")
    from sqlalchemy import func
    paid_total = await db.scalar(select(func.coalesce(func.sum(Payment.amount), 0)).where(
        Payment.order_id == source.id, Payment.tenant_id == ctx.tenant_id,
        Payment.venue_id == ctx.venue_id, Payment.status == "captured",
    ))
    if Decimal(paid_total or 0) > 0:
        raise HTTPException(status_code=409, detail="No se puede dividir una cuenta que ya tiene cobros registrados.")
    new_order = Order(
        tenant_id=ctx.tenant_id, venue_id=ctx.venue_id,
        order_number=randbelow(900000)+100000, table_id=source.table_id,
        customer_id=source.customer_id, channel=source.channel, status="open",
        notes="Cuenta dividida desde #" + str(source.order_number),
    )
    db.add(new_order)
    await db.flush()
    for requested in payload.lines:
        line = await db.scalar(select(OrderLine).where(
            OrderLine.id == requested.line_id, OrderLine.order_id == source.id,
            OrderLine.tenant_id == ctx.tenant_id, OrderLine.venue_id == ctx.venue_id,
        ))
        if line is None or requested.quantity > line.quantity:
            raise HTTPException(status_code=409, detail="Cantidad o línea no válida para dividir.")
        moved_total = money(line.unit_price * requested.quantity)
        db.add(OrderLine(
            tenant_id=ctx.tenant_id, venue_id=ctx.venue_id, order_id=new_order.id,
            product_id=line.product_id, product_name=line.product_name, quantity=requested.quantity,
            unit_price=line.unit_price, line_total=moved_total, tax_rate=line.tax_rate,
            modifiers=line.modifiers, notes=line.notes,
        ))
        remaining = line.quantity - requested.quantity
        if remaining == 0:
            await db.delete(line)
        else:
            line.quantity = remaining
            line.line_total = money(line.unit_price * remaining)
    await db.flush()
    await _recalculate_order(db, source, ctx)
    await _recalculate_order(db, new_order, ctx)
    db.add(AuditLog(
        tenant_id=ctx.tenant_id, venue_id=ctx.venue_id, actor_user_id=ctx.user_id,
        action="order.split", entity_type="order", entity_id=source.id,
        details={"new_order_id": str(new_order.id)},
    ))
    await db.commit()
    await db.refresh(new_order)
    return {"new_order_id": str(new_order.id), "new_order_number": new_order.order_number, "total": str(new_order.total)}



@router.get("/{order_id}/receipt", response_class=HTMLResponse)
async def print_receipt(order_id: UUID, ctx: TenantContext = Depends(get_tenant_context), db: AsyncSession = Depends(get_db)):
    order = await db.scalar(select(Order).where(
        Order.id == order_id, Order.tenant_id == ctx.tenant_id,
        Order.venue_id == ctx.venue_id,
    ))
    if order is None:
        raise HTTPException(status_code=404, detail="Cuenta no encontrada.")
    lines = await db.scalars(select(OrderLine).where(
        OrderLine.order_id == order.id, OrderLine.tenant_id == ctx.tenant_id,
        OrderLine.venue_id == ctx.venue_id,
    ))
    rows = "".join(
        "<tr><td>" + html_escape(line.product_name) + "</td><td>" + html_escape(str(line.quantity)) +
        "</td><td>" + html_escape(str(line.line_total)) + " €</td></tr>"
        for line in lines
    )
    html = """<!doctype html><html lang="es"><meta charset="utf-8"><title>Ticket</title>
    <style>body{font:14px monospace;max-width:340px;margin:20px auto;color:#111}
    h2,p{text-align:center;margin:6px 0}table{width:100%;border-collapse:collapse;margin:18px 0}
    td{padding:5px 0;border-bottom:1px dashed #aaa}td:last-child{text-align:right}
    .total{font-size:20px;font-weight:bold;text-align:right}@media print{button{display:none}body{margin:0 auto}}</style>
    <h2>TPV HOSTELERÍA</h2><p>Comanda #""" + str(order.order_number) + """</p>
    <p>""" + order.opened_at.strftime("%d/%m/%Y %H:%M") + """</p>
    <table>""" + rows + """</table>
    <p class="total">TOTAL: """ + str(order.total) + """ €</p>
    <p>Gracias por su visita</p><p><button onclick="window.print()">Imprimir</button></p>
    </html>"""
    return HTMLResponse(html)
