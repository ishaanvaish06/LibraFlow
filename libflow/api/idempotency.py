"""
API Idempotency Manager.
Prevents duplicate side-effects (double checkout, double fine payment, duplicate returns)
on retried HTTP requests by tracking Idempotency-Key headers with TTL.
"""
from __future__ import annotations

import json
import logging
import threading
import time
from typing import Any, Callable, Dict, Optional
from fastapi import HTTPException

logger = logging.getLogger(__name__)


class IdempotencyStore:
    """In-memory or Redis-backed idempotency cache."""

    def __init__(self, redis_client: Optional[Any] = None, ttl_seconds: int = 86400):
        self.redis_client = redis_client
        self.ttl_seconds = ttl_seconds
        self._memory_store: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()

    def _make_key(self, key: str, user_id: Optional[str] = None) -> str:
        if user_id:
            return f"idemp:{user_id}:{key}"
        return f"idemp:global:{key}"

    def get(self, key: str, user_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        full_key = self._make_key(key, user_id)
        if self.redis_client is not None:
            try:
                raw = self.redis_client.get(full_key)
                if raw:
                    return json.loads(raw.decode() if isinstance(raw, bytes) else raw)
            except Exception as e:
                logger.warning(f"Error reading idempotency key from Redis: {e}")
        with self._lock:
            entry = self._memory_store.get(full_key)
            if entry:
                if entry.get("expires_at", 0) < time.time():
                    del self._memory_store[full_key]
                    return None
                return entry.get("data")
        return None

    def set_in_progress(self, key: str, timeout_seconds: int = 60, user_id: Optional[str] = None) -> bool:
        full_key = self._make_key(key, user_id)
        if self.redis_client is not None:
            try:
                return bool(self.redis_client.set(full_key, json.dumps({"status": "IN_PROGRESS"}), nx=True, ex=timeout_seconds))
            except Exception as e:
                logger.warning(f"Error acquiring idempotency key from Redis: {e}")
        with self._lock:
            entry = self._memory_store.get(full_key)
            if entry and entry.get("expires_at", 0) >= time.time():
                return False
            self._memory_store[full_key] = {
                "data": {"status": "IN_PROGRESS"},
                "expires_at": time.time() + timeout_seconds,
            }
            return True

    def set_completed(self, key: str, status_code: int, response_body: Dict[str, Any], user_id: Optional[str] = None) -> None:
        full_key = self._make_key(key, user_id)
        record = {
            "status": "COMPLETED",
            "status_code": status_code,
            "response_body": response_body,
        }
        if self.redis_client is not None:
            try:
                self.redis_client.set(full_key, json.dumps(record, default=str), ex=self.ttl_seconds)
                return
            except Exception as e:
                logger.warning(f"Error saving completed idempotency key to Redis: {e}")
        with self._lock:
            self._memory_store[full_key] = {
                "data": record,
                "expires_at": time.time() + self.ttl_seconds,
            }

    def clear(self, key: str, user_id: Optional[str] = None) -> None:
        full_key = self._make_key(key, user_id)
        if self.redis_client is not None:
            try:
                self.redis_client.delete(full_key)
            except Exception:
                pass
        with self._lock:
            self._memory_store.pop(full_key, None)


# Global default store
default_idempotency_store = IdempotencyStore()


def handle_idempotent_operation(
    idempotency_key: Optional[str],
    store: IdempotencyStore,
    operation_fn: Callable[[], Dict[str, Any]],
    status_code: int = 200,
    user_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Executes operation_fn with idempotency protection if idempotency_key is provided.
    Scoped per user_id to prevent cross-user key collisions.
    If key was already completed, returns stored response.
    If in progress, raises HTTP 409 Conflict.
    """
    if not idempotency_key:
        return operation_fn()

    cached = store.get(idempotency_key, user_id=user_id)
    if cached is not None:
        if cached.get("status") == "COMPLETED":
            return cached.get("response_body", {})
        elif cached.get("status") == "IN_PROGRESS":
            raise HTTPException(
                status_code=409,
                detail=f"Concurrent operation with Idempotency-Key '{idempotency_key}' is currently in progress."
            )

    acquired = store.set_in_progress(idempotency_key, user_id=user_id)
    if not acquired:
        raise HTTPException(
            status_code=409,
            detail=f"Concurrent operation with Idempotency-Key '{idempotency_key}' is currently in progress."
        )

    try:
        result = operation_fn()
        store.set_completed(idempotency_key, status_code, result, user_id=user_id)
        return result
    except Exception:
        store.clear(idempotency_key, user_id=user_id)
        raise

