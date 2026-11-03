from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import TenantContext, get_tenant_context
from app.db import get_db
from app.models.hospitality import DiningArea, DiningTable
from app.schemas import AreaCreate, TableCreate, TableOut

router = APIRouter(prefix="/api/v1/floor", tags=["floor"])


@router.get("/areas")
async def list_areas(ctx: TenantContext = Depends(get_tenant_context), db: AsyncSession = Depends(get_db)):
    result = await db.scalars(select(DiningArea).where(
        DiningArea.tenant_id == ctx.tenant_id, DiningArea.venue_id == ctx.venue_id
    ).order_by(DiningArea.sort_order, DiningArea.name))
    return [{"id": str(x.id), "name": x.name, "sort_order": x.sort_order} for x in result]


@router.post("/areas", status_code=201)
async def create_area(payload: AreaCreate, ctx: TenantContext = Depends(get_tenant_context), db: AsyncSession = Depends(get_db)):
    if ctx.role not in {"owner", "admin", "manager"}:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="No tienes permiso para configurar la sala.")
    item = DiningArea(tenant_id=ctx.tenant_id, venue_id=ctx.venue_id, name=payload.name)
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return {"id": str(item.id), "name": item.name}


@router.get("/tables", response_model=list[TableOut])
async def list_tables(ctx: TenantContext = Depends(get_tenant_context), db: AsyncSession = Depends(get_db)):
    result = await db.scalars(select(DiningTable).where(
        DiningTable.tenant_id == ctx.tenant_id,
        DiningTable.venue_id == ctx.venue_id,
        DiningTable.active.is_(True),
    ).order_by(DiningTable.code))
    return list(result)


@router.post("/tables", response_model=TableOut, status_code=201)
async def create_table(payload: TableCreate, ctx: TenantContext = Depends(get_tenant_context), db: AsyncSession = Depends(get_db)):
    if ctx.role not in {"owner", "admin", "manager"}:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="No tienes permiso para configurar la sala.")
    if payload.area_id:
        area = await db.scalar(select(DiningArea).where(
            DiningArea.id == payload.area_id,
            DiningArea.tenant_id == ctx.tenant_id,
            DiningArea.venue_id == ctx.venue_id,
        ))
        if area is None:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Zona no encontrada.")
    item = DiningTable(tenant_id=ctx.tenant_id, venue_id=ctx.venue_id, **payload.model_dump())
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return item
