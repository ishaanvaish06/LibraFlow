"""Cross-branch inventory rebalancing engine routes."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, Request

from libflow.api.auth import require_permission

router = APIRouter(prefix="/api/v1/rebalance", tags=["Inventory Rebalancing"])


def get_rebalancer(request: Request):
    return request.app.state.container.rebalancer


@router.get("/plan")
def get_rebalancing_plan(
    rebalancer=Depends(get_rebalancer),
    claims: Dict[str, Any] = Depends(require_permission("BRANCH_MANAGE")),
) -> Dict[str, Any]:
    """Preview proposed inventory transfers calculated by the optimization loop."""
    plan = rebalancer.calculate_rebalancing_plan()
    return {"status": "SUCCESS", "proposed_transfers_count": len(plan), "plan": plan}


@router.post("/run")
def run_rebalancing(
    rebalancer=Depends(get_rebalancer),
    claims: Dict[str, Any] = Depends(require_permission("BRANCH_MANAGE")),
) -> Dict[str, Any]:
    """Execute autonomous rebalancing pass and dispatch events."""
    plan = rebalancer.calculate_rebalancing_plan()
    executed = rebalancer.execute_rebalancing_plan(plan)
    return {"status": "SUCCESS", "transfers_initiated_count": len(executed), "transfers": executed}


@router.post("/complete/{transfer_id}")
def complete_transfer(
    transfer_id: str,
    rebalancer=Depends(get_rebalancer),
    claims: Dict[str, Any] = Depends(require_permission("BRANCH_MANAGE")),
) -> Dict[str, Any]:
    """Mark an autonomous transfer arrived and ready for borrower checkout."""
    result = rebalancer.complete_transfer(transfer_id)
    if not result:
        return {"status": "NOT_FOUND", "transfer_id": transfer_id}
    return {"status": "SUCCESS", "transfer": result}


@router.get("/metrics")
def get_rebalancing_metrics(
    rebalancer=Depends(get_rebalancer),
    claims: Dict[str, Any] = Depends(require_permission("BRANCH_VIEW")),
) -> Dict[str, Any]:
    """Retrieve closed-loop precision metrics (% of autonomous transfers borrowed within 7 days)."""
    return {"status": "SUCCESS", "metrics": rebalancer.get_outcome_metrics()}
