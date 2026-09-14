"""Circulation, lending and reservation routes."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends

from libflow.api.auth import require_permission
from libflow.api.dependencies import get_circulation_service, get_reservation_manager
from libflow.api.schemas import (
    IssueBookRequest,
    ReserveBookRequest,
    ReturnBookRequest,
    SmartAllocationRequest,
)
from libflow.patterns.reservation_queue import BookReservationQueueManager
from libflow.services.circulation_service import CirculationService

router = APIRouter(prefix="/api/v1/circulation", tags=["Circulation"])


@router.post("/issue")
def issue_physical_copy(
    req: IssueBookRequest,
    circulation_svc: CirculationService = Depends(get_circulation_service),
    claims: Dict[str, Any] = Depends(require_permission("BOOK_ISSUE")),
) -> Dict[str, Any]:
    tx = circulation_svc.issue_physical_book(
        copy_id=req.copy_id,
        user_id=req.user_id,
        loan_days=req.loan_days,
        actor_id=claims.get("sub", ""),
    )
    return {"status": "SUCCESS", "transaction": tx}


@router.post("/return")
def return_physical_copy(
    req: ReturnBookRequest,
    circulation_svc: CirculationService = Depends(get_circulation_service),
    claims: Dict[str, Any] = Depends(require_permission("BOOK_RETURN")),
) -> Dict[str, Any]:
    result = circulation_svc.return_physical_book(
        copy_id=req.copy_id,
        is_late=req.is_late,
        is_damaged=req.is_damaged,
        actor_id=claims.get("sub", ""),
    )
    return {"status": "SUCCESS", **result}


@router.post("/reserve")
def reserve_book(
    req: ReserveBookRequest,
    reservation_mgr: BookReservationQueueManager = Depends(get_reservation_manager),
    claims: Dict[str, Any] = Depends(require_permission("BOOK_RESERVE")),
) -> Dict[str, Any]:
    entry = reservation_mgr.reserve_book(isbn=req.isbn, user_id=req.user_id)
    return {"status": "SUCCESS", "reservation": entry.to_dict()}


@router.post("/smart-allocation/request")
def request_smart_allocation(
    req: SmartAllocationRequest,
    circulation_svc: CirculationService = Depends(get_circulation_service),
    claims: Dict[str, Any] = Depends(require_permission("BOOK_ALLOCATE")),
) -> Dict[str, Any]:
    result = circulation_svc.request_smart_allocation(isbn=req.isbn, user_id=req.user_id)
    return {"status": "SUCCESS", **result}


@router.post("/smart-allocation/drop/{isbn}")
def process_smart_allocation_drop(
    isbn: str,
    circulation_svc: CirculationService = Depends(get_circulation_service),
    claims: Dict[str, Any] = Depends(require_permission("BOOK_ALLOCATE")),
) -> Dict[str, Any]:
    result = circulation_svc.process_smart_allocation_drop(isbn=isbn)
    if result is None:
        return {"status": "NO_MATCH", "isbn": isbn}
    return {"status": "SUCCESS", **result}