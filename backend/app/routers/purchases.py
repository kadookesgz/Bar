from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import TenantContext, get_tenant_context
from app.core.sync import record_sync_event
from app.db import get_db
from app.models.hospitality import PurchaseOrder, PurchaseOrderLine, StockItem, StockMovement, Supplier

router = APIRouter(prefix="/api/v1/purchases", tags=["purchasing and suppliers"])


class PurchaseLineInput(BaseModel):
    stock_item_id: UUID
    quantity: Decimal = Field(gt=0, max_digits=12, decimal_places=3)
    unit_cost: Decimal = Field(ge=0, max_digits=12, decimal_places=4)


class PurchaseCreate(BaseModel):
    supplier_id: UUID
    reference: str | None = None
    lines: list[PurchaseLineInput] = Field(min_length=1)


@router.get("")
async def list_purchases(ctx: TenantContext = Depends(get_tenant_context), db: AsyncSession = Depends(get_db)):
    rows = await db.scalars(select(PurchaseOrder).where(
        PurchaseOrder.tenant_id == ctx.tenant_id, PurchaseOrder.venue_id == ctx.venue_id
    ).order_by(PurchaseOrder.ordered_at.desc()).limit(200))
    return [{"id": str(x.id), "supplier_id": str(x.supplier_id), "reference": x.reference,
             "status": x.status, "total": str(x.total), "ordered_at": x.ordered_at.isoformat()} for x in rows]


@router.post("", status_code=201)
async def create_purchase(payload: PurchaseCreate, ctx: TenantContext = Depends(get_tenant_context), db: AsyncSession = Depends(get_db)):
    if ctx.role not in {"owner", "admin", "manager"}:
        raise HTTPException(status_code=403, detail="No tienes permiso para registrar compras.")
    supplier = await db.scalar(select(Supplier).where(
        Supplier.id == payload.supplier_id, Supplier.tenant_id == ctx.tenant_id,
        Supplier.venue_id == ctx.venue_id,
    ))
    if supplier is None:
        raise HTTPException(status_code=404, detail="Proveedor no encontrado.")
    total = Decimal("0")
    for line in payload.lines:
        item = await db.scalar(select(StockItem).where(
            StockItem.id == line.stock_item_id, StockItem.tenant_id == ctx.tenant_id,
            StockItem.venue_id == ctx.venue_id,
        ))
        if item is None:
            raise HTTPException(status_code=404, detail="Artículo de almacén no encontrado.")
        total += line.quantity * line.unit_cost
    purchase = PurchaseOrder(
        tenant_id=ctx.tenant_id, venue_id=ctx.venue_id, supplier_id=supplier.id,
        reference=payload.reference, status="ordered", total=total.quantize(Decimal("0.01")),
    )
    db.add(purchase)
    await db.flush()
    for line in payload.lines:
        db.add(PurchaseOrderLine(
            tenant_id=ctx.tenant_id, venue_id=ctx.venue_id, purchase_order_id=purchase.id,
            stock_item_id=line.stock_item_id, quantity=line.quantity, unit_cost=line.unit_cost,
        ))
    await db.commit()
    return {"id": str(purchase.id), "status": purchase.status, "total": str(purchase.total)}


@router.post("/{purchase_id}/receive")
async def receive_purchase(purchase_id: UUID, ctx: TenantContext = Depends(get_tenant_context), db: AsyncSession = Depends(get_db)):
    if ctx.role not in {"owner", "admin", "manager"}:
        raise HTTPException(status_code=403, detail="No tienes permiso para recepcionar compras.")
    purchase = await db.scalar(select(PurchaseOrder).where(
        PurchaseOrder.id == purchase_id, PurchaseOrder.tenant_id == ctx.tenant_id,
        PurchaseOrder.venue_id == ctx.venue_id, PurchaseOrder.status == "ordered",
    ))
    if purchase is None:
        raise HTTPException(status_code=404, detail="Compra no encontrada o ya recepcionada.")
    lines = list(await db.scalars(select(PurchaseOrderLine).where(
        PurchaseOrderLine.purchase_order_id == purchase.id,
        PurchaseOrderLine.tenant_id == ctx.tenant_id, PurchaseOrderLine.venue_id == ctx.venue_id,
    )))
    for line in lines:
        item = await db.scalar(select(StockItem).where(
            StockItem.id == line.stock_item_id, StockItem.tenant_id == ctx.tenant_id,
            StockItem.venue_id == ctx.venue_id,
        ))
        if item is None:
            raise HTTPException(status_code=409, detail="Artículo de almacén eliminado; no se puede recepcionar.")
        item.current_stock += line.quantity
        item.cost_per_unit = line.unit_cost
        line.received_quantity = line.quantity
        db.add(StockMovement(
            tenant_id=ctx.tenant_id, venue_id=ctx.venue_id, stock_item_id=item.id,
            movement_type="purchase", quantity=line.quantity, unit_cost=line.unit_cost,
            reference=purchase.reference or str(purchase.id), note="Recepción de compra",
        ))
    purchase.status = "received"
    purchase.received_at = datetime.now(timezone.utc)
    record_sync_event(db, ctx, aggregate_type="purchase_order", aggregate_id=purchase.id, event_type="purchase.received", payload={"total":str(purchase.total),"line_count":len(lines)})
    await db.commit()
    return {"id": str(purchase.id), "status": purchase.status, "lines_received": len(lines)}
