from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import TenantContext, get_tenant_context
from app.core.sync import record_sync_event
from app.db import get_db
from app.models.hospitality import AuditLog, CashMovement, CashRegister, CashShift, Order, Payment, Refund

router = APIRouter(prefix="/api/v1/cash", tags=["cash and payments"])


class OpenShiftRequest(BaseModel):
    register_id: UUID
    opening_float: Decimal = Field(ge=0, max_digits=12, decimal_places=2)


class CloseShiftRequest(BaseModel):
    counted_cash: Decimal = Field(ge=0, max_digits=12, decimal_places=2)


class PaymentRequest(BaseModel):
    order_id: UUID
    method: str = Field(pattern="^(cash|card|transfer|other)$")
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    reference: str | None = Field(default=None, max_length=120)


@router.get("/registers")
async def list_registers(ctx: TenantContext = Depends(get_tenant_context), db: AsyncSession = Depends(get_db)):
    rows = await db.scalars(select(CashRegister).where(
        CashRegister.tenant_id == ctx.tenant_id,
        CashRegister.venue_id == ctx.venue_id,
        CashRegister.active.is_(True),
    ))
    return [{"id": str(x.id), "name": x.name} for x in rows]


@router.get("/shifts/current")
async def current_shift(ctx: TenantContext = Depends(get_tenant_context), db: AsyncSession = Depends(get_db)):
    shift = await db.scalar(select(CashShift).where(
        CashShift.tenant_id == ctx.tenant_id,
        CashShift.venue_id == ctx.venue_id,
        CashShift.status == "open",
    ).order_by(CashShift.opened_at.desc()))
    if not shift:
        return None
    return {
        "id": str(shift.id),
        "register_id": str(shift.register_id),
        "opening_float": str(shift.opening_float),
        "expected_cash": str(shift.expected_cash),
        "opened_at": shift.opened_at.isoformat(),
    }


@router.post("/shifts/open", status_code=201)
async def open_shift(payload: OpenShiftRequest, ctx: TenantContext = Depends(get_tenant_context), db: AsyncSession = Depends(get_db)):
    existing = await db.scalar(select(CashShift.id).where(
        CashShift.tenant_id == ctx.tenant_id,
        CashShift.venue_id == ctx.venue_id,
        CashShift.status == "open",
    ))
    if existing:
        raise HTTPException(status_code=409, detail="Ya hay un turno de caja abierto.")
    register = await db.scalar(select(CashRegister).where(
        CashRegister.id == payload.register_id,
        CashRegister.tenant_id == ctx.tenant_id,
        CashRegister.venue_id == ctx.venue_id,
        CashRegister.active.is_(True),
    ))
    if not register:
        raise HTTPException(status_code=404, detail="Caja no encontrada.")
    shift = CashShift(
        tenant_id=ctx.tenant_id,
        venue_id=ctx.venue_id,
        register_id=register.id,
        opened_by=ctx.user_id,
        opening_float=payload.opening_float,
        expected_cash=payload.opening_float,
        status="open",
    )
    db.add(shift)
    await db.commit()
    await db.refresh(shift)
    return {"id": str(shift.id), "status": shift.status, "expected_cash": str(shift.expected_cash)}


@router.post("/shifts/{shift_id}/close")
async def close_shift(shift_id: UUID, payload: CloseShiftRequest, ctx: TenantContext = Depends(get_tenant_context), db: AsyncSession = Depends(get_db)):
    shift = await db.scalar(select(CashShift).where(
        CashShift.id == shift_id,
        CashShift.tenant_id == ctx.tenant_id,
        CashShift.venue_id == ctx.venue_id,
        CashShift.status == "open",
    ))
    if not shift:
        raise HTTPException(status_code=404, detail="Turno abierto no encontrado.")
    shift.counted_cash = payload.counted_cash
    shift.closed_by = ctx.user_id
    shift.closed_at = datetime.now(timezone.utc)
    shift.status = "closed"
    difference = payload.counted_cash - shift.expected_cash
    db.add(CashMovement(
        tenant_id=ctx.tenant_id, venue_id=ctx.venue_id, cash_shift_id=shift.id,
        movement_type="closing_difference", amount=difference,
        reason="Diferencia de arqueo al cierre", created_by=ctx.user_id,
    ))
    await db.commit()
    return {
        "status": "closed",
        "expected_cash": str(shift.expected_cash),
        "counted_cash": str(shift.counted_cash),
        "difference": str(difference),
    }


@router.post("/payments", status_code=201)
async def create_payment(payload: PaymentRequest, ctx: TenantContext = Depends(get_tenant_context), db: AsyncSession = Depends(get_db)):
    order = await db.scalar(select(Order).where(
        Order.id == payload.order_id,
        Order.tenant_id == ctx.tenant_id,
        Order.venue_id == ctx.venue_id,
        Order.status != "paid",
        Order.status != "cancelled",
    ))
    if not order:
        raise HTTPException(status_code=404, detail="Cuenta abierta no encontrada.")

    # Sum all captured payments without loading payment rows into memory.
    from sqlalchemy import func
    paid_total = await db.scalar(select(func.coalesce(func.sum(Payment.amount), 0)).where(
        Payment.order_id == order.id,
        Payment.tenant_id == ctx.tenant_id,
        Payment.venue_id == ctx.venue_id,
        Payment.status == "captured",
    ))
    outstanding = order.total - Decimal(paid_total or 0)
    if payload.amount > outstanding:
        raise HTTPException(status_code=409, detail=f"El importe supera el pendiente ({outstanding:.2f} €).")

    shift = None
    if payload.method == "cash":
        shift = await db.scalar(select(CashShift).where(
            CashShift.tenant_id == ctx.tenant_id,
            CashShift.venue_id == ctx.venue_id,
            CashShift.status == "open",
        ).order_by(CashShift.opened_at.desc()))
        if shift is None:
            raise HTTPException(status_code=409, detail="Abre un turno de caja antes de cobrar en efectivo.")

    payment = Payment(
        tenant_id=ctx.tenant_id,
        venue_id=ctx.venue_id,
        order_id=order.id,
        cash_shift_id=shift.id if shift else None,
        method=payload.method,
        amount=payload.amount,
        reference=payload.reference,
        status="captured",
    )
    db.add(payment)
    record_sync_event(db, ctx, aggregate_type="payment", aggregate_id=payment.id, event_type="payment.captured", payload={"order_id": str(order.id), "method":payload.method, "amount":str(payload.amount)})
    if shift:
        shift.expected_cash += payload.amount

    if payload.amount == outstanding:
        order.status = "paid"
        order.closed_at = datetime.now(timezone.utc)

    await db.commit()
    return {
        "payment_id": str(payment.id),
        "order_id": str(order.id),
        "paid": str(Decimal(paid_total or 0) + payload.amount),
        "remaining": str(outstanding - payload.amount),
        "order_status": order.status,
    }


@router.get("/orders/{order_id}/balance")
async def order_balance(order_id: UUID, ctx: TenantContext = Depends(get_tenant_context), db: AsyncSession = Depends(get_db)):
    from sqlalchemy import func
    order = await db.scalar(select(Order).where(
        Order.id == order_id, Order.tenant_id == ctx.tenant_id,
        Order.venue_id == ctx.venue_id,
    ))
    if order is None:
        raise HTTPException(status_code=404, detail="Cuenta no encontrada.")
    paid = await db.scalar(select(func.coalesce(func.sum(Payment.amount), 0)).where(
        Payment.order_id == order.id, Payment.tenant_id == ctx.tenant_id,
        Payment.venue_id == ctx.venue_id, Payment.status == "captured",
    ))
    paid_total = Decimal(paid or 0)
    return {
        "order_id": str(order.id), "order_number": order.order_number,
        "total": str(order.total), "paid": str(paid_total),
        "remaining": str(max(Decimal("0.00"), order.total - paid_total)),
        "status": order.status,
    }


class RefundRequest(BaseModel):
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    method: str = Field(pattern="^(cash|card|transfer|other)$")
    reason: str = Field(min_length=3, max_length=240)


@router.post("/payments/{payment_id}/refund", status_code=201)
async def refund_payment(payment_id: UUID, payload: RefundRequest, ctx: TenantContext = Depends(get_tenant_context), db: AsyncSession = Depends(get_db)):
    from sqlalchemy import func
    payment = await db.scalar(select(Payment).where(
        Payment.id == payment_id, Payment.tenant_id == ctx.tenant_id,
        Payment.venue_id == ctx.venue_id, Payment.status == "captured",
    ))
    if payment is None:
        raise HTTPException(status_code=404, detail="Cobro no encontrado.")
    refunded = await db.scalar(select(func.coalesce(func.sum(Refund.amount), 0)).where(
        Refund.payment_id == payment.id, Refund.tenant_id == ctx.tenant_id,
        Refund.venue_id == ctx.venue_id, Refund.status == "completed",
    ))
    remaining = payment.amount - Decimal(refunded or 0)
    if payload.amount > remaining:
        raise HTTPException(status_code=409, detail=f"El reembolso supera el importe reembolsable ({remaining:.2f} €).")
    shift = None
    if payload.method == "cash":
        shift = await db.scalar(select(CashShift).where(
            CashShift.tenant_id == ctx.tenant_id, CashShift.venue_id == ctx.venue_id,
            CashShift.status == "open",
        ).order_by(CashShift.opened_at.desc()))
        if shift is None:
            raise HTTPException(status_code=409, detail="Abre caja para registrar un reembolso en efectivo.")
        shift.expected_cash -= payload.amount
    refund = Refund(
        tenant_id=ctx.tenant_id, venue_id=ctx.venue_id, payment_id=payment.id,
        amount=payload.amount, method=payload.method, reason=payload.reason,
        refunded_by=ctx.user_id, status="completed",
    )
    db.add(refund)
    db.add(AuditLog(
        tenant_id=ctx.tenant_id, venue_id=ctx.venue_id, actor_user_id=ctx.user_id,
        action="payment.refunded", entity_type="payment", entity_id=payment.id,
        details={"amount": str(payload.amount), "method": payload.method, "reason": payload.reason},
    ))
    record_sync_event(db, ctx, aggregate_type="refund", aggregate_id=refund.id, event_type="payment.refunded", payload={"payment_id":str(payment.id),"amount":str(payload.amount),"method":payload.method})
    await db.commit()
    return {"refund_id": str(refund.id), "payment_id": str(payment.id), "refunded": str(payload.amount), "remaining_refundable": str(remaining-payload.amount)}


@router.get("/payments")
async def recent_payments(limit: int = 50, ctx: TenantContext = Depends(get_tenant_context), db: AsyncSession = Depends(get_db)):
    from sqlalchemy import func
    safe_limit = max(1, min(limit, 200))
    rows = await db.scalars(select(Payment).where(
        Payment.tenant_id == ctx.tenant_id, Payment.venue_id == ctx.venue_id,
        Payment.status == "captured",
    ).order_by(Payment.paid_at.desc()).limit(safe_limit))
    output = []
    for payment in rows:
        order = await db.scalar(select(Order).where(
            Order.id == payment.order_id, Order.tenant_id == ctx.tenant_id,
            Order.venue_id == ctx.venue_id,
        ))
        refunded = await db.scalar(select(func.coalesce(func.sum(Refund.amount), 0)).where(
            Refund.payment_id == payment.id, Refund.tenant_id == ctx.tenant_id,
            Refund.venue_id == ctx.venue_id, Refund.status == "completed",
        ))
        output.append({
            "id": str(payment.id), "order_number": order.order_number if order else None,
            "amount": str(payment.amount), "method": payment.method,
            "refunded": str(refunded or 0),
            "refundable": str(payment.amount - Decimal(refunded or 0)),
            "paid_at": payment.paid_at.isoformat(),
        })
    return output
