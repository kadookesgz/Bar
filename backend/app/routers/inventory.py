from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import TenantContext, get_tenant_context
from app.core.sync import record_sync_event
from app.db import get_db
from app.models.hospitality import StockItem, StockMovement, Supplier

router = APIRouter(prefix="/api/v1/inventory", tags=["inventory and suppliers"])


class StockItemCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    unit: str = Field(default="ud", max_length=20)
    minimum_stock: Decimal = Field(default=0, ge=0)
    cost_per_unit: Decimal = Field(default=0, ge=0)


class StockAdjustment(BaseModel):
    quantity: Decimal
    movement_type: str = Field(pattern="^(purchase|sale|waste|adjustment|transfer_in|transfer_out)$")
    unit_cost: Decimal | None = Field(default=None, ge=0)
    reference: str | None = None
    note: str | None = None


class SupplierCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    tax_id: str | None = None
    email: str | None = None
    phone: str | None = None


@router.get("/items")
async def list_items(ctx: TenantContext = Depends(get_tenant_context), db: AsyncSession = Depends(get_db)):
    rows = await db.scalars(select(StockItem).where(
        StockItem.tenant_id == ctx.tenant_id,
        StockItem.venue_id == ctx.venue_id,
    ).order_by(StockItem.name))
    return [{
        "id": str(x.id), "name": x.name, "unit": x.unit,
        "current_stock": str(x.current_stock), "minimum_stock": str(x.minimum_stock),
        "cost_per_unit": str(x.cost_per_unit),
        "low_stock": x.current_stock <= x.minimum_stock,
    } for x in rows]


@router.post("/items", status_code=201)
async def create_item(payload: StockItemCreate, ctx: TenantContext = Depends(get_tenant_context), db: AsyncSession = Depends(get_db)):
    item = StockItem(tenant_id=ctx.tenant_id, venue_id=ctx.venue_id, **payload.model_dump())
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return {"id": str(item.id), "name": item.name}


@router.post("/items/{item_id}/movements", status_code=201)
async def add_movement(item_id: UUID, payload: StockAdjustment, ctx: TenantContext = Depends(get_tenant_context), db: AsyncSession = Depends(get_db)):
    item = await db.scalar(select(StockItem).where(
        StockItem.id == item_id,
        StockItem.tenant_id == ctx.tenant_id,
        StockItem.venue_id == ctx.venue_id,
    ))
    if item is None:
        raise HTTPException(status_code=404, detail="Artículo de almacén no encontrado.")
    delta = payload.quantity
    if payload.movement_type in {"sale", "waste", "transfer_out"}:
        delta = -abs(delta)
    else:
        delta = abs(delta)
    if item.current_stock + delta < 0:
        raise HTTPException(status_code=409, detail="El movimiento dejaría el stock en negativo.")
    item.current_stock += delta
    if payload.unit_cost is not None:
        item.cost_per_unit = payload.unit_cost
    movement = StockMovement(
        tenant_id=ctx.tenant_id, venue_id=ctx.venue_id, stock_item_id=item.id,
        movement_type=payload.movement_type, quantity=delta, unit_cost=payload.unit_cost,
        reference=payload.reference, note=payload.note,
    )
    db.add(movement)
    record_sync_event(db, ctx, aggregate_type="stock_item", aggregate_id=item.id, event_type="stock.movement", payload={"movement_type":payload.movement_type,"quantity":str(delta),"current_stock":str(item.current_stock)})
    await db.commit()
    return {"item_id": str(item.id), "current_stock": str(item.current_stock)}


@router.get("/suppliers")
async def list_suppliers(ctx: TenantContext = Depends(get_tenant_context), db: AsyncSession = Depends(get_db)):
    rows = await db.scalars(select(Supplier).where(
        Supplier.tenant_id == ctx.tenant_id, Supplier.venue_id == ctx.venue_id
    ).order_by(Supplier.name))
    return [{"id": str(x.id), "name": x.name, "tax_id": x.tax_id, "email": x.email, "phone": x.phone} for x in rows]


@router.post("/suppliers", status_code=201)
async def create_supplier(payload: SupplierCreate, ctx: TenantContext = Depends(get_tenant_context), db: AsyncSession = Depends(get_db)):
    item = Supplier(tenant_id=ctx.tenant_id, venue_id=ctx.venue_id, **payload.model_dump())
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return {"id": str(item.id), "name": item.name}
