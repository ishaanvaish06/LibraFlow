"""
Circuit Breaker Pattern for External Dependencies (Redis Cache, ML Risk Inference).
States:
- CLOSED: Normal operation. Successes reset failure count.
- OPEN: Tripped after failure_threshold. Requests fail fast or execute fallback.
- HALF_OPEN: Probe state after recovery_timeout. Single success resets to CLOSED; failure trips back to OPEN.
"""
from __future__ import annotations

from enum import Enum
import logging
import threading
import time
from typing import Callable, Generic, Optional, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class CircuitState(str, Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class CircuitBreakerOpenError(Exception):
    """Raised when an operation is attempted while circuit is open and no fallback is provided."""
    pass


class CircuitBreaker(Generic[T]):
    def __init__(
        self,
        name: str,
        failure_threshold: int = 3,
        recovery_timeout: float = 5.0,
        expected_exceptions: tuple = (Exception,),
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exceptions = expected_exceptions

        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_state_change = time.time()
        self._lock = threading.Lock()

    def call(
        self,
        operation: Callable[[], T],
        fallback: Optional[Callable[[], T]] = None,
    ) -> T:
        with self._lock:
            now = time.time()
            if self.state == CircuitState.OPEN:
                if now - self.last_state_change >= self.recovery_timeout:
                    self.state = CircuitState.HALF_OPEN
                    logger.info(f"[CircuitBreaker:{self.name}] Transitioned OPEN -> HALF_OPEN (probing)")
                else:
                    if fallback is not None:
                        return fallback()
                    raise CircuitBreakerOpenError(f"Circuit '{self.name}' is OPEN")

        try:
            result = operation()
            self._on_success()
            return result
        except self.expected_exceptions as exc:
            self._on_failure(exc)
            if fallback is not None:
                return fallback()
            raise

    def _on_success(self) -> None:
        with self._lock:
            if self.state != CircuitState.CLOSED:
                logger.info(f"[CircuitBreaker:{self.name}] Recovered to CLOSED state")
            self.state = CircuitState.CLOSED
            self.failure_count = 0

    def _on_failure(self, exc: Exception) -> None:
        with self._lock:
            self.failure_count += 1
            logger.warning(
                f"[CircuitBreaker:{self.name}] Failure #{self.failure_count}: {exc}"
            )
            if self.failure_count >= self.failure_threshold or self.state == CircuitState.HALF_OPEN:
                self.state = CircuitState.OPEN
                self.last_state_change = time.time()
                logger.error(f"[CircuitBreaker:{self.name}] TRIPPED TO OPEN")
