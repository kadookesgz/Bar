from dataclasses import dataclass
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import InvalidTokenError

from app.core.config import get_settings

bearer = HTTPBearer(auto_error=False)
settings = get_settings()


@dataclass(frozen=True)
class TenantContext:
    user_id: UUID
    tenant_id: UUID
    venue_id: UUID
    role: str


async def get_tenant_context(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> TenantContext:
    if credentials is None:
        raise HTTPException(status_code=401, detail="Inicia sesión para continuar.")
    try:
        payload = jwt.decode(credentials.credentials, settings.jwt_secret, algorithms=["HS256"])
        return TenantContext(
            user_id=UUID(payload["sub"]),
            tenant_id=UUID(payload["tenant_id"]),
            venue_id=UUID(payload["venue_id"]),
            role=str(payload.get("role", "staff")),
        )
    except (InvalidTokenError, KeyError, ValueError) as exc:
        raise HTTPException(status_code=401, detail="Sesión inválida o caducada.") from exc
