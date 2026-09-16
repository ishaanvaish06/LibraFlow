"""Intelligence, recommendation and graph routes."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends

from libflow.api.auth import require_permission
from libflow.api.dependencies import get_intelligence_service
from libflow.services.intelligence_service import IntelligenceService

router = APIRouter(prefix="/api/v1/intelligence", tags=["Intelligence"])


@router.get("/recommendations/{user_id}")
def get_recommendations(
    user_id: str,
    top_k: int = 5,
    intelligence_svc: IntelligenceService = Depends(get_intelligence_service),
    claims: Dict[str, Any] = Depends(require_permission("INTEL_RECOMMENDATIONS")),
) -> Dict[str, Any]:
    recs = intelligence_svc.get_recommendations_for_user(user_id, top_k=top_k)
    return {"status": "SUCCESS", "user_id": user_id, "total": len(recs), "recommendations": recs}


@router.get("/risk-assessment/{user_id}")
def assess_late_risk(
    user_id: str,
    intelligence_svc: IntelligenceService = Depends(get_intelligence_service),
    claims: Dict[str, Any] = Depends(require_permission("INTEL_RISK_ASSESSMENT")),
) -> Dict[str, Any]:
    result = intelligence_svc.assess_user_theft_risk(user_id)
    return {"status": "SUCCESS", **result}


@router.get("/learning-path/{isbn}")
def get_learning_path(
    isbn: str,
    depth: int = 5,
    intelligence_svc: IntelligenceService = Depends(get_intelligence_service),
    claims: Dict[str, Any] = Depends(require_permission("INTEL_LEARNING_PATH")),
) -> Dict[str, Any]:
    path = intelligence_svc.get_subject_learning_path(isbn, max_depth=depth)
    return {"status": "SUCCESS", "start_isbn": isbn, "path": path}


@router.get("/shortest-path")
def find_shortest_path(
    from_isbn: str,
    to_isbn: str,
    intelligence_svc: IntelligenceService = Depends(get_intelligence_service),
    claims: Dict[str, Any] = Depends(require_permission("INTEL_GRAPH_TRAVERSE")),
) -> Dict[str, Any]:
    path = intelligence_svc.get_shortest_connection_path(from_isbn, to_isbn)
    return {"status": "SUCCESS", "path": path}
