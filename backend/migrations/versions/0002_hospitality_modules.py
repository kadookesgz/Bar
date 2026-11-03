"""Extend the initial schema with newer V2 modules and order fields.

Revision ID: 0002_hospitality_modules
Revises: 0001_initial
"""
from alembic import op
import sqlalchemy as sa

from app.models import Base

revision = "0002_hospitality_modules"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    # Creates tables added since 0001 without touching tables that already exist.
    Base.metadata.create_all(bind=bind)

    inspector = sa.inspect(bind)
    table_columns = {name: {column["name"] for column in inspector.get_columns(name)}
                     for name in inspector.get_table_names()}

    dining_columns = table_columns.get("dining_tables", set())
    if "qr_token_hash" not in dining_columns:
        op.add_column("dining_tables", sa.Column("qr_token_hash", sa.String(length=64), nullable=True))
    indexes = {index["name"] for index in sa.inspect(bind).get_indexes("dining_tables")}
    if "ix_dining_tables_qr_token_hash" not in indexes:
        op.create_index("ix_dining_tables_qr_token_hash", "dining_tables", ["qr_token_hash"], unique=True)

    order_columns = table_columns.get("orders", set())
    additions = [
        ("customer_name", sa.String(length=160)),
        ("customer_phone", sa.String(length=40)),
        ("delivery_address", sa.Text()),
        ("scheduled_for", sa.DateTime(timezone=True)),
        ("external_source", sa.String(length=80)),
        ("external_reference", sa.String(length=120)),
    ]
    for name, column_type in additions:
        if name not in order_columns:
            op.add_column("orders", sa.Column(name, column_type, nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "orders" in inspector.get_table_names():
        columns = {column["name"] for column in inspector.get_columns("orders")}
        for name in ("external_reference", "external_source", "scheduled_for", "delivery_address", "customer_phone", "customer_name"):
            if name in columns:
                op.drop_column("orders", name)
    if "dining_tables" in inspector.get_table_names():
        indexes = {index["name"] for index in inspector.get_indexes("dining_tables")}
        if "ix_dining_tables_qr_token_hash" in indexes:
            op.drop_index("ix_dining_tables_qr_token_hash", table_name="dining_tables")
        columns = {column["name"] for column in inspector.get_columns("dining_tables")}
        if "qr_token_hash" in columns:
            op.drop_column("dining_tables", "qr_token_hash")
