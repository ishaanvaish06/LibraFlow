"""
Book Reservation Queue System
Handles FIFO waiting queues, automatic assignment upon book return, and reservation expiry.
"""
from typing import Dict, Optional, Deque
from collections import deque
from datetime import datetime, timedelta
import uuid

from libflow.core.enums import ReservationStatus
from libflow.patterns.observer_notification import NotificationDispatcher, NotificationEvent


class ReservationEntry:
    def __init__(self, reservation_id: str, isbn: str, user_id: str, priority_score: float = 0.0):
        self.reservation_id = reservation_id
        self.isbn = isbn
        self.user_id = user_id
        self.priority_score = priority_score
        self.status = ReservationStatus.PENDING
        self.created_at = datetime.now()
        self.assigned_copy_id: Optional[str] = None
        self.ready_pickup_expires_at: Optional[datetime] = None

    def to_dict(self) -> Dict:
        return {
            "reservation_id": self.reservation_id,
            "isbn": self.isbn,
            "user_id": self.user_id,
            "status": self.status.value,
            "assigned_copy_id": self.assigned_copy_id,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.ready_pickup_expires_at.isoformat() if self.ready_pickup_expires_at else None,
        }


class BookReservationQueueManager:
    """
    Manages active reservation queues across titles with auto-assignment.
    """

    def __init__(self, notification_dispatcher: Optional[NotificationDispatcher] = None):
        # isbn -> FIFO queue of ReservationEntry
        self.queues: Dict[str, Deque[ReservationEntry]] = {}
        # reservation_id -> ReservationEntry
        self.reservations: Dict[str, ReservationEntry] = {}
        self.dispatcher = notification_dispatcher

    def reserve_book(self, isbn: str, user_id: str, priority_score: float = 0.0) -> ReservationEntry:
        if isbn not in self.queues:
            self.queues[isbn] = deque()

        # Check if already in queue
        for res in self.queues[isbn]:
            if res.user_id == user_id and res.status in (ReservationStatus.PENDING, ReservationStatus.READY_FOR_PICKUP):
                return res

        res_id = f"RES-{uuid.uuid4().hex[:8].upper()}"
        entry = ReservationEntry(reservation_id=res_id, isbn=isbn, user_id=user_id, priority_score=priority_score)
        self.queues[isbn].append(entry)
        self.reservations[res_id] = entry
        return entry

    def handle_copy_returned(self, isbn: str, copy_id: str, pickup_window_hours: int = 48) -> Optional[ReservationEntry]:
        """
        Called when a physical copy is returned.
        Automatically assigns copy to top waiting user in FIFO queue and dispatches notification.
        """
        if isbn not in self.queues or not self.queues[isbn]:
            return None

        # Pop the next pending reservation
        while self.queues[isbn]:
            entry = self.queues[isbn].popleft()
            if entry.status == ReservationStatus.PENDING:
                entry.status = ReservationStatus.READY_FOR_PICKUP
                entry.assigned_copy_id = copy_id
                entry.ready_pickup_expires_at = datetime.now() + timedelta(hours=pickup_window_hours)

                # Send notification event
                if self.dispatcher:
                    self.dispatcher.dispatch(NotificationEvent(
                        event_type="BOOK_RESERVED_AVAILABLE",
                        recipient_id=entry.user_id,
                        message=f"Good news! Book {isbn} (Copy: {copy_id}) is now ready for pickup until {entry.ready_pickup_expires_at.strftime('%Y-%m-%d %H:%M')}.",
                        payload={"isbn": isbn, "copy_id": copy_id, "reservation_id": entry.reservation_id},
                    ))
                return entry

        return None

    def get_waiting_count(self, isbn: str) -> int:
        return len([r for r in self.queues.get(isbn, []) if r.status == ReservationStatus.PENDING])
