"""
GoF Singleton Pattern for Thread-Safe Audit Logging System
Tracks every mutation, borrow, return, fine charge, and transfer in the system.
"""
from typing import List, Dict, Any, Optional
import threading
from datetime import datetime


class AuditLogger:
    """
    Thread-safe Singleton Audit Logger.
    """
    _instance: Optional["AuditLogger"] = None
    _lock: threading.Lock = threading.Lock()

    def __new__(cls) -> "AuditLogger":
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(AuditLogger, cls).__new__(cls)
                cls._instance._logs = []
                cls._instance._buffer_lock = threading.Lock()
        return cls._instance

    def log_event(
        self,
        actor_id: str,
        action: str,
        resource_id: str,
        details: Optional[Dict[str, Any]] = None,
        ip_address: str = "127.0.0.1",
    ) -> Dict[str, Any]:
        """
        Appends an immutable audit log entry.
        """
        entry = {
            "timestamp": datetime.now().isoformat(),
            "actor_id": actor_id,
            "action": action,
            "resource_id": resource_id,
            "details": details or {},
            "ip_address": ip_address,
        }
        with self._buffer_lock:
            self._logs.append(entry)
        return entry

    def get_logs(self, limit: int = 100, action_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        with self._buffer_lock:
            logs_copy = list(self._logs)
        if action_filter:
            logs_copy = [entry for entry in logs_copy if entry["action"] == action_filter]
        return logs_copy[-limit:]

    def clear(self) -> None:
        """For testing isolation."""
        with self._buffer_lock:
            self._logs.clear()
