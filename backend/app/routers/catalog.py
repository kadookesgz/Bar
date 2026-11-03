from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import TenantContext, get_tenant_context
from app.db import get_db
from app.models.hospitality import Product, ProductCategory
from app.schemas import CategoryCreate, CategoryOut, ProductCreate, ProductOut

router = APIRouter(prefix="/api/v1", tags=["catalog"])


@router.get("/categories", response_model=list[CategoryOut])
async def list_categories(ctx: TenantContext = Depends(get_tenant_context), db: AsyncSession = Depends(get_db)):
    result = await db.scalars(
        select(ProductCategory).where(
            ProductCategory.tenant_id == ctx.tenant_id,
            ProductCategory.venue_id == ctx.venue_id,
            ProductCategory.active.is_(True),
        ).order_by(ProductCategory.sort_order, ProductCategory.name)
    )
    return list(result)


@router.post("/categories", response_model=CategoryOut, status_code=201)
async def create_category(payload: CategoryCreate, ctx: TenantContext = Depends(get_tenant_context), db: AsyncSession = Depends(get_db)):
    if ctx.role not in {"owner", "admin", "manager"}:
        raise HTTPException(status_code=403, detail="No tienes permiso para editar la carta.")
    item = ProductCategory(tenant_id=ctx.tenant_id, venue_id=ctx.venue_id, **payload.model_dump())
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return item


@router.get("/products", response_model=list[ProductOut])
async def list_products(ctx: TenantContext = Depends(get_tenant_context), db: AsyncSession = Depends(get_db)):
    result = await db.scalars(
        select(Product).where(
            Product.tenant_id == ctx.tenant_id,
            Product.venue_id == ctx.venue_id,
            Product.active.is_(True),
        ).order_by(Product.name)
    )
    return list(result)


@router.post("/products", response_model=ProductOut, status_code=201)
async def create_product(payload: ProductCreate, ctx: TenantContext = Depends(get_tenant_context), db: AsyncSession = Depends(get_db)):
    if ctx.role not in {"owner", "admin", "manager"}:
        raise HTTPException(status_code=403, detail="No tienes permiso para editar la carta.")
    if payload.category_id:
        category = await db.scalar(select(ProductCategory).where(
            ProductCategory.id == payload.category_id,
            ProductCategory.tenant_id == ctx.tenant_id,
            ProductCategory.venue_id == ctx.venue_id,
        ))
        if category is None:
            raise HTTPException(status_code=404, detail="Familia no encontrada.")
    item = Product(tenant_id=ctx.tenant_id, venue_id=ctx.venue_id, **payload.model_dump())
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return item
