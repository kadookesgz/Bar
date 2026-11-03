import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, hash_password
from app.db import get_db
from app.models.tenancy import Tenant, User, UserVenue, Venue

router = APIRouter(prefix="/api/v1/setup", tags=["initial setup"])


class BootstrapRequest(BaseModel):
    company_name: str = Field(min_length=2, max_length=160)
    venue_name: str = Field(min_length=2, max_length=160)
    tenant_slug: str | None = Field(default=None, min_length=2, max_length=80)
    admin_name: str = Field(min_length=2, max_length=160)
    admin_email: EmailStr
    admin_password: str = Field(min_length=12, max_length=256)


@router.get("/status")
async def setup_status(db: AsyncSession = Depends(get_db)):
    count = await db.scalar(select(func.count(Tenant.id)))
    return {"setup_required": (count or 0) == 0}


@router.post("/bootstrap", status_code=201)
async def bootstrap(payload: BootstrapRequest, db: AsyncSession = Depends(get_db)):
    count = await db.scalar(select(func.count(Tenant.id)))
    if count:
        raise HTTPException(status_code=409, detail="La instalación inicial ya está completada.")

    slug = payload.tenant_slug or re.sub(r"[^a-z0-9]+", "-", payload.company_name.lower()).strip("-")
    if len(slug) < 2:
        raise HTTPException(status_code=422, detail="Indica un identificador de empresa válido.")

    tenant = Tenant(name=payload.company_name, slug=slug, status="trial")
    db.add(tenant)
    await db.flush()

    venue = Venue(tenant_id=tenant.id, name=payload.venue_name, code="LOCAL-01", timezone="Europe/Madrid")
    db.add(venue)
    await db.flush()

    user = User(
        tenant_id=tenant.id,
        email=str(payload.admin_email).lower(),
        password_hash=hash_password(payload.admin_password),
        display_name=payload.admin_name,
        is_active=True,
    )
    db.add(user)
    await db.flush()
    db.add(UserVenue(user_id=user.id, venue_id=venue.id, role="owner"))
    await db.commit()

    token = create_access_token(user_id=user.id, tenant_id=tenant.id, venue_id=venue.id, role="owner")
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {"id": str(user.id), "name": user.display_name, "email": user.email, "role": "owner"},
        "tenant": {"id": str(tenant.id), "name": tenant.name, "slug": tenant.slug},
        "venue": {"id": str(venue.id), "name": venue.name},
    }
