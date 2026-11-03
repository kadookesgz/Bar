from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class CategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    sort_order: int = 0


class CategoryOut(ORMModel):
    id: UUID
    name: str
    sort_order: int
    active: bool


class ProductCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    category_id: UUID | None = None
    sku: str | None = Field(default=None, max_length=64)
    description: str | None = None
    price: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    tax_rate: Decimal = Field(default=Decimal("10"), ge=0, le=100)
    allergens: list[str] = Field(default_factory=list)
    track_stock: bool = False


class ProductOut(ORMModel):
    id: UUID
    name: str
    category_id: UUID | None
    sku: str | None
    description: str | None
    price: Decimal
    tax_rate: Decimal
    active: bool
    track_stock: bool
    allergens: list


class AreaCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class TableCreate(BaseModel):
    area_id: UUID | None = None
    code: str = Field(min_length=1, max_length=32)
    label: str = Field(min_length=1, max_length=80)
    capacity: int = Field(default=2, ge=1, le=100)
    pos_x: int = 0
    pos_y: int = 0
    shape: str = "square"


class TableOut(ORMModel):
    id: UUID
    area_id: UUID | None
    code: str
    label: str
    capacity: int
    pos_x: int
    pos_y: int
    shape: str
    active: bool


class OrderLineCreate(BaseModel):
    product_id: UUID
    quantity: Decimal = Field(gt=0, max_digits=10, decimal_places=3)
    modifier_ids: list[UUID] = Field(default_factory=list)
    notes: str | None = None


class OrderCreate(BaseModel):
    table_id: UUID | None = None
    channel: str = Field(default="dine_in", pattern="^(dine_in|takeaway|delivery|qr|online|external)$")
    notes: str | None = None
    customer_name: str | None = Field(default=None, max_length=160)
    customer_phone: str | None = Field(default=None, max_length=40)
    delivery_address: str | None = None
    scheduled_for: datetime | None = None
    lines: list[OrderLineCreate] = Field(min_length=1)


class OrderOut(ORMModel):
    id: UUID
    order_number: int
    table_id: UUID | None
    channel: str
    status: str
    subtotal: Decimal
    discount_total: Decimal
    tax_total: Decimal
    total: Decimal
    opened_at: datetime
