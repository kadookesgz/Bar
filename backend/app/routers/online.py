import base64
import hashlib
import secrets
from io import BytesIO
from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID

import qrcode
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import TenantContext, get_tenant_context
from app.db import get_db
from app.models.hospitality import DiningTable, Order, OrderLine, Product

router = APIRouter(tags=["QR and online ordering"])


class QROrderLine(BaseModel):
    product_id: UUID
    quantity: Decimal = Field(gt=0, max_digits=10, decimal_places=3)
    notes: str | None = None


class QROrderCreate(BaseModel):
    lines: list[QROrderLine] = Field(min_length=1)
    customer_note: str | None = None


@router.post("/api/v1/floor/tables/{table_id}/qr-token")
async def rotate_qr_token(table_id: UUID, request: Request, ctx: TenantContext = Depends(get_tenant_context), db: AsyncSession = Depends(get_db)):
    table = await db.scalar(select(DiningTable).where(
        DiningTable.id == table_id,
        DiningTable.tenant_id == ctx.tenant_id,
        DiningTable.venue_id == ctx.venue_id,
        DiningTable.active.is_(True),
    ))
    if table is None:
        raise HTTPException(status_code=404, detail="Mesa no encontrada.")
    token = secrets.token_urlsafe(32)
    table.qr_token_hash = hashlib.sha256(token.encode()).hexdigest()
    await db.commit()
    menu_path = "/qr/" + token
    menu_url = str(request.base_url).rstrip("/") + menu_path
    image = qrcode.make(menu_url)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    qr_png_base64 = base64.b64encode(buffer.getvalue()).decode("ascii")
    return {"table_id": str(table.id), "token": token, "menu_path": menu_path, "menu_url": menu_url, "qr_png_base64": qr_png_base64}


@router.get("/api/v1/public/qr/{token}")
async def public_qr_menu(token: str, db: AsyncSession = Depends(get_db)):
    digest = hashlib.sha256(token.encode()).hexdigest()
    table = await db.scalar(select(DiningTable).where(DiningTable.qr_token_hash == digest, DiningTable.active.is_(True)))
    if table is None:
        raise HTTPException(status_code=404, detail="Código QR no válido.")
    products = await db.scalars(select(Product).where(
        Product.tenant_id == table.tenant_id,
        Product.venue_id == table.venue_id,
        Product.active.is_(True),
    ).order_by(Product.name))
    return {
        "venue": str(table.venue_id),
        "table": {"id": str(table.id), "label": table.label},
        "products": [{
            "id": str(p.id), "name": p.name, "description": p.description,
            "price": str(p.price), "tax_rate": str(p.tax_rate), "allergens": p.allergens,
        } for p in products],
    }


@router.post("/api/v1/public/qr/{token}/orders", status_code=201)
async def create_qr_order(token: str, payload: QROrderCreate, db: AsyncSession = Depends(get_db)):
    digest = hashlib.sha256(token.encode()).hexdigest()
    table = await db.scalar(select(DiningTable).where(DiningTable.qr_token_hash == digest, DiningTable.active.is_(True)))
    if table is None:
        raise HTTPException(status_code=404, detail="Código QR no válido.")
    subtotal = Decimal("0.00")
    tax_total = Decimal("0.00")
    lines = []
    for requested in payload.lines:
        product = await db.scalar(select(Product).where(
            Product.id == requested.product_id,
            Product.tenant_id == table.tenant_id,
            Product.venue_id == table.venue_id,
            Product.active.is_(True),
        ))
        if product is None:
            raise HTTPException(status_code=404, detail="Uno de los productos ya no está disponible.")
        line_total = (product.price * requested.quantity).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        tax_total += (line_total * product.tax_rate / (Decimal("100") + product.tax_rate)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        subtotal += line_total
        lines.append(OrderLine(
            tenant_id=table.tenant_id, venue_id=table.venue_id, product_id=product.id,
            product_name=product.name, quantity=requested.quantity, unit_price=product.price,
            line_total=line_total, tax_rate=product.tax_rate, notes=requested.notes,
        ))
    order = Order(
        tenant_id=table.tenant_id, venue_id=table.venue_id, order_number=secrets.randbelow(900000)+100000,
        table_id=table.id, channel="qr", status="sent", subtotal=subtotal,
        tax_total=tax_total, total=subtotal, notes=payload.customer_note,
    )
    db.add(order)
    await db.flush()
    for line in lines:
        line.order_id = order.id
        db.add(line)
    await db.commit()
    return {"order_id": str(order.id), "order_number": order.order_number, "status": order.status, "total": str(order.total)}
