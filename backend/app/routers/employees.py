from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import TenantContext, get_tenant_context
from app.core.security import hash_password
from app.db import get_db
from app.models.tenancy import User, UserVenue

router = APIRouter(prefix="/api/v1/employees", tags=["employees"])
ALLOWED_ROLES = {"manager", "waiter", "kitchen", "cashier"}


class EmployeeCreate(BaseModel):
    display_name: str = Field(min_length=2, max_length=160)
    email: EmailStr
    password: str = Field(min_length=12, max_length=256)
    role: str = Field(pattern="^(manager|waiter|kitchen|cashier)$")


@router.get("")
async def list_employees(ctx: TenantContext = Depends(get_tenant_context), db: AsyncSession = Depends(get_db)):
    rows = await db.execute(
        select(User, UserVenue).join(UserVenue, UserVenue.user_id == User.id).where(
            User.tenant_id == ctx.tenant_id,
            UserVenue.venue_id == ctx.venue_id,
            User.is_active.is_(True),
        ).order_by(User.display_name)
    )
    return [{
        "id": str(user.id), "display_name": user.display_name,
        "email": user.email, "role": membership.role,
    } for user, membership in rows.all()]


@router.post("", status_code=201)
async def create_employee(payload: EmployeeCreate, ctx: TenantContext = Depends(get_tenant_context), db: AsyncSession = Depends(get_db)):
    if ctx.role not in {"owner", "admin", "manager"}:
        raise HTTPException(status_code=403, detail="No tienes permiso para gestionar empleados.")
    email = str(payload.email).lower()
    existing = await db.scalar(select(User.id).where(User.tenant_id == ctx.tenant_id, User.email == email))
    if existing:
        raise HTTPException(status_code=409, detail="Ya existe un usuario con ese correo en la empresa.")
    user = User(
        tenant_id=ctx.tenant_id, email=email, password_hash=hash_password(payload.password),
        display_name=payload.display_name, is_active=True,
    )
    db.add(user)
    await db.flush()
    db.add(UserVenue(user_id=user.id, venue_id=ctx.venue_id, role=payload.role))
    await db.commit()
    return {"id": str(user.id), "display_name": user.display_name, "email": user.email, "role": payload.role}
