from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import TenantContext
from app.models.hospitality import SyncEvent


def record_sync_event(
    db: AsyncSession,
    ctx: TenantContext,
    *,
    aggregate_type: str,
    aggregate_id: UUID,
    event_type: str,
    payload: dict,
) -> None:
    """Add a durable local outbox event in the same transaction as the business change."""
    db.add(SyncEvent(
        tenant_id=ctx.tenant_id,
        venue_id=ctx.venue_id,
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        event_type=event_type,
        payload=payload,
        status="pending",
    ))
