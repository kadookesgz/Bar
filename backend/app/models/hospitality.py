import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    Boolean, DateTime, ForeignKey, Index, Integer, JSON, Numeric, String, Text,
    UniqueConstraint
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKey


class ScopedRecord(UUIDPrimaryKey, TimestampMixin):
    """Common tenant and venue ownership for business records."""
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    venue_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("venues.id", ondelete="RESTRICT"), nullable=False, index=True
    )


class ProductCategory(ScopedRecord, Base):
    __tablename__ = "product_categories"
    __table_args__ = (UniqueConstraint("tenant_id", "venue_id", "name", name="uq_category_name"),)

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Product(ScopedRecord, Base):
    __tablename__ = "products"
    __table_args__ = (
        UniqueConstraint("tenant_id", "venue_id", "sku", name="uq_product_sku"),
        Index("ix_products_scope_active", "tenant_id", "venue_id", "active"),
    )

    category_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("product_categories.id", ondelete="SET NULL")
    )
    sku: Mapped[str | None] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    tax_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=10, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    track_stock: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    image_url: Mapped[str | None] = mapped_column(String(500))
    allergens: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    prep_station_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))


class ModifierGroup(ScopedRecord, Base):
    __tablename__ = "modifier_groups"

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    min_select: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_select: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class Modifier(ScopedRecord, Base):
    __tablename__ = "modifiers"

    group_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("modifier_groups.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    price_delta: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class DiningArea(ScopedRecord, Base):
    __tablename__ = "dining_areas"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class DiningTable(ScopedRecord, Base):
    __tablename__ = "dining_tables"
    __table_args__ = (UniqueConstraint("tenant_id", "venue_id", "code", name="uq_table_code"),)

    area_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("dining_areas.id", ondelete="SET NULL")
    )
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    label: Mapped[str] = mapped_column(String(80), nullable=False)
    capacity: Mapped[int] = mapped_column(Integer, default=2, nullable=False)
    pos_x: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    pos_y: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    shape: Mapped[str] = mapped_column(String(20), default="square", nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Reservation(ScopedRecord, Base):
    __tablename__ = "reservations"
    __table_args__ = (Index("ix_reservations_scope_start", "tenant_id", "venue_id", "starts_at"),)

    customer_name: Mapped[str] = mapped_column(String(160), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(40))
    party_size: Mapped[int] = mapped_column(Integer, nullable=False)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, default=120, nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="booked", nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    table_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("dining_tables.id"))


class Customer(ScopedRecord, Base):
    __tablename__ = "customers"

    name: Mapped[str] = mapped_column(String(160), nullable=False)
    email: Mapped[str | None] = mapped_column(String(254))
    phone: Mapped[str | None] = mapped_column(String(40))
    loyalty_points: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)


class Order(ScopedRecord, Base):
    __tablename__ = "orders"
    __table_args__ = (Index("ix_orders_scope_status", "tenant_id", "venue_id", "status"),)

    order_number: Mapped[int] = mapped_column(Integer, nullable=False)
    table_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("dining_tables.id"))
    customer_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("customers.id"))
    waiter_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    channel: Mapped[str] = mapped_column(String(24), default="dine_in", nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="open", nullable=False)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    discount_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    tax_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    total: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class OrderLine(ScopedRecord, Base):
    __tablename__ = "order_lines"

    order_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("products.id", ondelete="SET NULL"))
    product_name: Mapped[str] = mapped_column(String(160), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    line_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    tax_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    modifiers: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    kitchen_status: Mapped[str] = mapped_column(String(24), default="pending", nullable=False)


class KitchenStation(ScopedRecord, Base):
    __tablename__ = "kitchen_stations"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class KitchenEvent(ScopedRecord, Base):
    __tablename__ = "kitchen_events"

    order_line_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("order_lines.id", ondelete="CASCADE"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    note: Mapped[str | None] = mapped_column(Text)


class CashRegister(ScopedRecord, Base):
    __tablename__ = "cash_registers"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class CashShift(ScopedRecord, Base):
    __tablename__ = "cash_shifts"

    register_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("cash_registers.id"), nullable=False)
    opened_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    closed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    opening_float: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    expected_cash: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    counted_cash: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    status: Mapped[str] = mapped_column(String(20), default="open", nullable=False)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Payment(ScopedRecord, Base):
    __tablename__ = "payments"

    order_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("orders.id"), nullable=False, index=True)
    cash_shift_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("cash_shifts.id"))
    method: Mapped[str] = mapped_column(String(24), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    reference: Mapped[str | None] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(20), default="captured", nullable=False)
    paid_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)


class CashMovement(ScopedRecord, Base):
    __tablename__ = "cash_movements"

    cash_shift_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("cash_shifts.id"), nullable=False, index=True)
    movement_type: Mapped[str] = mapped_column(String(24), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    reason: Mapped[str] = mapped_column(String(240), nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))


class Supplier(ScopedRecord, Base):
    __tablename__ = "suppliers"

    name: Mapped[str] = mapped_column(String(160), nullable=False)
    tax_id: Mapped[str | None] = mapped_column(String(24))
    email: Mapped[str | None] = mapped_column(String(254))
    phone: Mapped[str | None] = mapped_column(String(40))


class StockItem(ScopedRecord, Base):
    __tablename__ = "stock_items"

    name: Mapped[str] = mapped_column(String(160), nullable=False)
    unit: Mapped[str] = mapped_column(String(20), default="ud", nullable=False)
    current_stock: Mapped[Decimal] = mapped_column(Numeric(12, 3), default=0, nullable=False)
    minimum_stock: Mapped[Decimal] = mapped_column(Numeric(12, 3), default=0, nullable=False)
    cost_per_unit: Mapped[Decimal] = mapped_column(Numeric(12, 4), default=0, nullable=False)


class Recipe(ScopedRecord, Base):
    __tablename__ = "recipes"

    product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False, index=True)
    yield_quantity: Mapped[Decimal] = mapped_column(Numeric(10, 3), default=1, nullable=False)
    instructions: Mapped[str | None] = mapped_column(Text)


class RecipeLine(ScopedRecord, Base):
    __tablename__ = "recipe_lines"

    recipe_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("recipes.id", ondelete="CASCADE"), nullable=False)
    stock_item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("stock_items.id"), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)


class StockMovement(ScopedRecord, Base):
    __tablename__ = "stock_movements"

    stock_item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("stock_items.id"), nullable=False, index=True)
    movement_type: Mapped[str] = mapped_column(String(24), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    unit_cost: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    reference: Mapped[str | None] = mapped_column(String(120))
    note: Mapped[str | None] = mapped_column(Text)


class AuditLog(ScopedRecord, Base):
    __tablename__ = "audit_logs"

    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    details: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)


class SyncEvent(ScopedRecord, Base):
    __tablename__ = "sync_events"
    __table_args__ = (UniqueConstraint("tenant_id", "event_uuid", name="uq_sync_event_uuid"),)

    event_uuid: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), default=uuid.uuid4, nullable=False)
    aggregate_type: Mapped[str] = mapped_column(String(80), nullable=False)
    aggregate_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
