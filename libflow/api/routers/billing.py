"""Billing, fines and payment routes."""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Header, Query

from libflow.api.auth import require_permission
from libflow.api.dependencies import get_billing_service
from libflow.api.idempotency import default_idempotency_store, handle_idempotent_operation
from libflow.api.schemas import PayFineRequest
from libflow.services.billing_service import BillingService

router = APIRouter(prefix="/api/v1/billing", tags=["Billing"])


@router.get("/fine-estimate")
def calculate_fine_estimate(
    isbn: str = Query(...),
    user_id: str = Query(...),
    overdue_days: int = Query(...),
    billing_svc: BillingService = Depends(get_billing_service),
) -> Dict[str, Any]:
    fine = billing_svc.calculate_projected_fine(isbn, user_id, overdue_days)
    return {"isbn": isbn, "user_id": user_id, "overdue_days": overdue_days, "projected_fine": fine}


@router.post("/pay")
def pay_fine(
    req: PayFineRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    billing_svc: BillingService = Depends(get_billing_service),
    claims: Dict[str, Any] = Depends(require_permission("BILLING_PAY")),
) -> Dict[str, Any]:
    def _execute():
        result = billing_svc.pay_fine(
            user_id=req.user_id,
            amount=req.amount,
            payment_method=req.payment_method,
            payment_metadata=req.payment_metadata,
        )
        return {"status": "SUCCESS", **result}

    return handle_idempotent_operation(idempotency_key, default_idempotency_store, _execute)