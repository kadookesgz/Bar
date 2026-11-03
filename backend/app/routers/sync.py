from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import TenantContext, get_tenant_context
from app.db import get_db
from app.models.hospitality import SyncEvent

router = APIRouter(prefix="/api/v1/sync", tags=["local-cloud synchronization"])


@router.get("/status")
async def sync_status(ctx: TenantContext = Depends(get_tenant_context), db: AsyncSession = Depends(get_db)):
    pending = await db.scalar(select(func.count(SyncEvent.id)).where(
        SyncEvent.tenant_id == ctx.tenant_id,
        SyncEvent.venue_id == ctx.venue_id,
        SyncEvent.status == "pending",
    ))
    delivered = await db.scalar(select(func.count(SyncEvent.id)).where(
        SyncEvent.tenant_id == ctx.tenant_id,
        SyncEvent.venue_id == ctx.venue_id,
        SyncEvent.status == "delivered",
    ))
    return {
        "mode": "local-first",
        "pending_events": pending or 0,
        "delivered_events": delivered or 0,
        "cloud_sync_configured": False,
        "message": "La cola local está preparada; el conector y el servidor central se implementarán en la fase SaaS.",
    }


@router.get("/outbox")
async def read_outbox(limit: int = 100, ctx: TenantContext = Depends(get_tenant_context), db: AsyncSession = Depends(get_db)):
    if ctx.role not in {"owner", "admin"}:
        raise HTTPException(status_code=403, detail="No tienes permiso para consultar la cola de sincronización.")
    safe_limit = max(1, min(limit, 500))
    rows = await db.scalars(select(SyncEvent).where(
        SyncEvent.tenant_id == ctx.tenant_id,
        SyncEvent.venue_id == ctx.venue_id,
        SyncEvent.status == "pending",
    ).order_by(SyncEvent.created_at).limit(safe_limit))
    return [{
        "event_uuid": str(x.event_uuid), "aggregate_type": x.aggregate_type,
        "aggregate_id": str(x.aggregate_id), "event_type": x.event_type,
        "payload": x.payload, "attempts": x.attempts, "created_at": x.created_at.isoformat(),
    } for x in rows]
