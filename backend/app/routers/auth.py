from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import TenantContext, get_tenant_context
from app.core.security import create_access_token, verify_password
from app.db import get_db
from app.models.tenancy import Tenant, User, UserVenue, Venue

router = APIRouter(prefix="/api/v1/auth", tags=["authentication"])


class LoginRequest(BaseModel):
    tenant_slug: str = Field(min_length=2, max_length=80)
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)


class SwitchVenueRequest(BaseModel):
    venue_id: UUID


@router.post("/login")
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)):
    tenant = await db.scalar(select(Tenant).where(
        Tenant.slug == payload.tenant_slug, Tenant.status.in_(["active", "trial"])
    ))
    if tenant is None:
        raise HTTPException(status_code=401, detail="Empresa, usuario o contraseña incorrectos.")
    user = await db.scalar(select(User).where(
        User.tenant_id == tenant.id, User.email == str(payload.email).lower(), User.is_active.is_(True)
    ))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Empresa, usuario o contraseña incorrectos.")
    membership = await db.scalar(select(UserVenue).where(UserVenue.user_id == user.id).order_by(UserVenue.venue_id))
    if membership is None:
        raise HTTPException(status_code=403, detail="El usuario no tiene establecimientos asignados.")
    venue = await db.scalar(select(Venue).where(Venue.id == membership.venue_id, Venue.tenant_id == tenant.id))
    if venue is None or not venue.is_active:
        raise HTTPException(status_code=403, detail="Establecimiento no disponible.")
    token = create_access_token(user_id=user.id, tenant_id=tenant.id, venue_id=venue.id, role=membership.role)
    return {
        "access_token": token, "token_type": "bearer",
        "user": {"id": str(user.id), "name": user.display_name, "email": user.email, "role": membership.role},
        "tenant": {"id": str(tenant.id), "name": tenant.name, "slug": tenant.slug},
        "venue": {"id": str(venue.id), "name": venue.name},
    }


@router.post("/switch-venue")
async def switch_venue(payload: SwitchVenueRequest, ctx: TenantContext = Depends(get_tenant_context), db: AsyncSession = Depends(get_db)):
    membership = await db.scalar(select(UserVenue).where(
        UserVenue.user_id == ctx.user_id, UserVenue.venue_id == payload.venue_id
    ))
    if membership is None:
        raise HTTPException(status_code=403, detail="No tienes acceso a ese establecimiento.")
    venue = await db.scalar(select(Venue).where(
        Venue.id == payload.venue_id, Venue.tenant_id == ctx.tenant_id, Venue.is_active.is_(True)
    ))
    if venue is None:
        raise HTTPException(status_code=404, detail="Establecimiento no encontrado.")
    token = create_access_token(
        user_id=ctx.user_id, tenant_id=ctx.tenant_id, venue_id=venue.id, role=membership.role
    )
    return {"access_token": token, "token_type": "bearer", "venue": {"id": str(venue.id), "name": venue.name}, "role": membership.role}
