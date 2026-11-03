from decimal import Decimal
from uuid import uuid4

import jwt

from app.core.config import get_settings
from app.core.security import create_access_token, hash_password, verify_password
from app.models import Base
from app.routers.orders import money


def test_money_rounds_half_up_to_cents():
    assert money(Decimal("12.345")) == Decimal("12.35")
    assert money(Decimal("12.344")) == Decimal("12.34")


def test_password_is_hashed_and_verifiable():
    raw = "Correct horse battery staple 2026!"
    encoded = hash_password(raw)
    assert encoded != raw
    assert verify_password(raw, encoded)
    assert not verify_password("wrong password", encoded)


def test_access_token_contains_tenant_and_venue_scope():
    user_id, tenant_id, venue_id = uuid4(), uuid4(), uuid4()
    token = create_access_token(
        user_id=user_id, tenant_id=tenant_id, venue_id=venue_id, role="owner"
    )
    payload = jwt.decode(
        token, get_settings().jwt_secret, algorithms=["HS256"]
    )
    assert payload["sub"] == str(user_id)
    assert payload["tenant_id"] == str(tenant_id)
    assert payload["venue_id"] == str(venue_id)
    assert payload["role"] == "owner"


def test_business_tables_have_tenant_and_venue_scope():
    for table_name in (
        "products", "orders", "order_lines", "payments",
        "cash_shifts", "stock_items", "reservations",
    ):
        table = Base.metadata.tables[table_name]
        assert "tenant_id" in table.c
        assert "venue_id" in table.c
