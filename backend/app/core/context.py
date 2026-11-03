from dataclasses import dataclass
from uuid import UUID

from fastapi import Header, HTTPException


@dataclass(frozen=True)
class TenantContext:
    tenant_id: UUID
    venue_id: UUID


async def get_tenant_context(
    x_tenant_id: str | None = Header(default=None),
    x_venue_id: str | None = Header(default=None),
) -> TenantContext:
    """
    Development-only tenant scope resolver.

    Replace with authenticated membership/session claims before public or production use.
    """
    if not x_tenant_id or not x_venue_id:
        raise HTTPException(status_code=401, detail="Falta contexto de empresa y establecimiento.")
    try:
        return TenantContext(UUID(x_tenant_id), UUID(x_venue_id))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Identificador de empresa/local inválido.") from exc
