from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import TenantContext, get_tenant_context
from app.db import get_db
from app.models.hospitality import Product, Recipe, RecipeLine, StockItem

router = APIRouter(prefix="/api/v1/recipes", tags=["recipes and food costing"])


class RecipeComponent(BaseModel):
    stock_item_id: UUID
    quantity: Decimal = Field(gt=0, max_digits=12, decimal_places=3)


class RecipeCreate(BaseModel):
    product_id: UUID
    yield_quantity: Decimal = Field(gt=0, max_digits=10, decimal_places=3, default=1)
    instructions: str | None = None
    components: list[RecipeComponent] = Field(min_length=1)


@router.get("")
async def list_recipes(ctx: TenantContext = Depends(get_tenant_context), db: AsyncSession = Depends(get_db)):
    rows = await db.scalars(select(Recipe).where(
        Recipe.tenant_id == ctx.tenant_id, Recipe.venue_id == ctx.venue_id
    ))
    output = []
    for recipe in rows:
        product = await db.scalar(select(Product).where(
            Product.id == recipe.product_id, Product.tenant_id == ctx.tenant_id,
            Product.venue_id == ctx.venue_id,
        ))
        components = await db.scalars(select(RecipeLine).where(
            RecipeLine.recipe_id == recipe.id, RecipeLine.tenant_id == ctx.tenant_id,
            RecipeLine.venue_id == ctx.venue_id,
        ))
        cost = Decimal("0")
        items = []
        for component in components:
            stock = await db.scalar(select(StockItem).where(
                StockItem.id == component.stock_item_id, StockItem.tenant_id == ctx.tenant_id,
                StockItem.venue_id == ctx.venue_id,
            ))
            if stock:
                component_cost = component.quantity * stock.cost_per_unit
                cost += component_cost
                items.append({"stock_item": stock.name, "quantity": str(component.quantity), "unit": stock.unit})
        output.append({
            "id": str(recipe.id), "product_id": str(recipe.product_id),
            "product_name": product.name if product else "Producto eliminado",
            "yield_quantity": str(recipe.yield_quantity), "cost_per_yield": str(cost),
            "components": items, "instructions": recipe.instructions,
        })
    return output


@router.post("", status_code=201)
async def create_recipe(payload: RecipeCreate, ctx: TenantContext = Depends(get_tenant_context), db: AsyncSession = Depends(get_db)):
    if ctx.role not in {"owner", "admin", "manager"}:
        raise HTTPException(status_code=403, detail="No tienes permiso para editar escandallos.")
    product = await db.scalar(select(Product).where(
        Product.id == payload.product_id, Product.tenant_id == ctx.tenant_id,
        Product.venue_id == ctx.venue_id,
    ))
    if product is None:
        raise HTTPException(status_code=404, detail="Producto no encontrado.")
    for component in payload.components:
        stock = await db.scalar(select(StockItem.id).where(
            StockItem.id == component.stock_item_id, StockItem.tenant_id == ctx.tenant_id,
            StockItem.venue_id == ctx.venue_id,
        ))
        if not stock:
            raise HTTPException(status_code=404, detail="Artículo de almacén no encontrado.")
    recipe = Recipe(
        tenant_id=ctx.tenant_id, venue_id=ctx.venue_id, product_id=product.id,
        yield_quantity=payload.yield_quantity, instructions=payload.instructions,
    )
    db.add(recipe)
    await db.flush()
    for component in payload.components:
        db.add(RecipeLine(
            tenant_id=ctx.tenant_id, venue_id=ctx.venue_id, recipe_id=recipe.id,
            stock_item_id=component.stock_item_id, quantity=component.quantity,
        ))
    await db.commit()
    return {"id": str(recipe.id), "product_name": product.name}
