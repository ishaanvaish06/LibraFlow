"""Operational routes: notifications, audit logs, and cache observability."""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Query

from libflow.api.auth import require_permission
from libflow.api.dependencies import (
    get_audit_logger,
    get_cache,
    get_inapp_notifications,
)
from libflow.patterns.observer_notification import InAppNotificationService
from libflow.patterns.singleton_logger import AuditLogger
from libflow.storage.cache import Cache

router = APIRouter(prefix="/api/v1/system", tags=["System"])


@router.get("/notifications/{user_id}")
def get_user_notifications(
    user_id: str,
    inapp_svc: InAppNotificationService = Depends(get_inapp_notifications),
    claims: Dict[str, Any] = Depends(require_permission("SYSTEM_NOTIFICATIONS")),
) -> Dict[str, Any]:
    notifications = inapp_svc.get_user_notifications(user_id)
    return {"user_id": user_id, "total": len(notifications), "notifications": notifications}


@router.get("/audit-logs")
def get_audit_logs(
    limit: int = Query(100),
    action: Optional[str] = Query(None),
    audit_logger: AuditLogger = Depends(get_audit_logger),
    claims: Dict[str, Any] = Depends(require_permission("SYSTEM_AUDIT")),
) -> Dict[str, Any]:
    logs = audit_logger.get_logs(limit=limit, action_filter=action)
    return {"total": len(logs), "logs": logs}


@router.get("/cache-stats")
def get_cache_stats(
    cache: Cache = Depends(get_cache),
    claims: Dict[str, Any] = Depends(require_permission("SYSTEM_CACHE")),
) -> Dict[str, Any]:
    stats = cache.get_stats()
    return {"backend": cache.__class__.__name__, **stats}