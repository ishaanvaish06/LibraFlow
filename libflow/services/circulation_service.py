"""
Circulation Service: Checkouts, Returns, Smart Allocation, Reservation Queues, and Concurrency Locks
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import uuid

from libflow.core.enums import BookStatus, ReservationStatus
from libflow.core.book import PhysicalBook, EBook, BookCopy
from libflow.core.user import User, Student
from libflow.storage.database import LibraryDatabase
from libflow.storage.lock_manager import ConcurrencyLockManager
from libflow.storage.cache import DistributedCache
from libflow.dsa.priority_queue import SmartAllocationQueue
from libflow.patterns.reservation_queue import BookReservationQueueManager
from libflow.patterns.observer_notification import NotificationDispatcher, NotificationEvent
from libflow.patterns.singleton_logger import AuditLogger
from libflow.ai.demand_forecaster import DemandForecaster


class CirculationService:
    def __init__(
        self,
        db: LibraryDatabase,
        lock_mgr: ConcurrencyLockManager,
        cache: DistributedCache,
        reservation_mgr: BookReservationQueueManager,
        dispatcher: NotificationDispatcher,
        demand_forecaster: DemandForecaster,
    ):
        self.db = db
        self.lock_mgr = lock_mgr
        self.cache = cache
        self.reservation_mgr = reservation_mgr
        self.dispatcher = dispatcher
        self.demand_forecaster = demand_forecaster
        self.audit_logger = AuditLogger()
        # isbn -> SmartAllocationQueue
        self.allocation_queues: Dict[str, SmartAllocationQueue] = {}

    def issue_physical_book(
        self,
        copy_id: str,
        user_id: str,
        actor_id: str = "LIBRARIAN",
        loan_days: int = 14,
    ) -> Dict[str, Any]:
        """
        Issues a physical copy to a user under a pessimistic lock to guarantee zero race conditions.
        """
        user = self.db.get_user(user_id)
        if not user:
            raise ValueError(f"User '{user_id}' not found.")
        if not user.can_borrow():
            raise ValueError(f"User '{user_id}' is not eligible to borrow (limit reached or unpaid fines).")

        copy = self.db.get_copy(copy_id)
        if not copy:
            raise ValueError(f"Book copy '{copy_id}' not found.")

        # Pessimistic concurrency lock on specific copy ID
        with self.lock_mgr.acquire_pessimistic_lock(copy_id):
            if copy.status != BookStatus.AVAILABLE:
                # Check if reserved specifically for this user
                if not (copy.status == BookStatus.RESERVED and copy.current_reserver_id == user_id):
                    raise ValueError(f"Copy '{copy_id}' is not available (Current status: {copy.status.value}).")

            # Check out copy
            copy.check_out(user_id)
            user.add_borrow(copy_id, copy.book_isbn)

            due_date = datetime.now() + timedelta(days=loan_days)
            tx_record = {
                "transaction_id": f"TX-{uuid.uuid4().hex[:8].upper()}",
                "type": "BORROW",
                "copy_id": copy_id,
                "isbn": copy.book_isbn,
                "user_id": user_id,
                "borrowed_at": datetime.now().isoformat(),
                "due_date": due_date.isoformat(),
                "returned_at": None,
            }
            self.db.record_circulation_log(tx_record)
            self.demand_forecaster.record_checkout(copy.book_isbn, datetime.now().date())

            # Invalidate caches
            self.cache.invalidate(f"book:{copy.book_isbn}")

            # Notify borrower
            self.dispatcher.dispatch(NotificationEvent(
                event_type="BOOK_ISSUED",
                recipient_id=user_id,
                message=f"Book copy '{copy_id}' issued successfully. Due on {due_date.strftime('%Y-%m-%d')}.",
                payload={"copy_id": copy_id, "isbn": copy.book_isbn, "due_date": due_date.isoformat()},
            ))

            self.audit_logger.log_event(
                actor_id=actor_id,
                action="ISSUE_BOOK",
                resource_id=copy_id,
                details={"user_id": user_id, "isbn": copy.book_isbn},
            )

            return tx_record

    def return_physical_book(
        self,
        copy_id: str,
        actor_id: str = "LIBRARIAN",
        is_late: bool = False,
        is_damaged: bool = False,
    ) -> Dict[str, Any]:
        """
        Returns a physical copy, triggers reservation auto-assignment, and updates audit records.
        """
        copy = self.db.get_copy(copy_id)
        if not copy:
            raise ValueError(f"Book copy '{copy_id}' not found.")

        with self.lock_mgr.acquire_pessimistic_lock(copy_id):
            borrower_id = copy.current_borrower_id
            if not borrower_id:
                raise ValueError(f"Copy '{copy_id}' is not currently issued to any user.")

            user = self.db.get_user(borrower_id)
            if user:
                user.record_return(copy_id, is_late=is_late, is_damaged=is_damaged)

            copy.return_book()

            # Trigger auto-assignment from reservation queue if users are waiting
            assigned_res = self.reservation_mgr.handle_copy_returned(copy.book_isbn, copy_id)
            if assigned_res:
                copy.reserve(assigned_res.user_id)

            self.cache.invalidate(f"book:{copy.book_isbn}")

            self.audit_logger.log_event(
                actor_id=actor_id,
                action="RETURN_BOOK",
                resource_id=copy_id,
                details={
                    "previous_borrower": borrower_id,
                    "is_late": is_late,
                    "is_damaged": is_damaged,
                    "assigned_reservation": assigned_res.reservation_id if assigned_res else None,
                },
            )

            return {
                "copy_id": copy_id,
                "status": copy.status.value,
                "previous_borrower": borrower_id,
                "auto_assigned_to_reservation": assigned_res.to_dict() if assigned_res else None,
            }

    def request_smart_allocation(self, isbn: str, user_id: str) -> Dict[str, Any]:
        """
        Enqueues student request into the Priority Queue for smart allocation.
        """
        user = self.db.get_user(user_id)
        if not user:
            raise ValueError(f"User '{user_id}' not found.")

        if isbn not in self.allocation_queues:
            self.allocation_queues[isbn] = SmartAllocationQueue(isbn=isbn)

        req_id = f"ALLOC-{uuid.uuid4().hex[:8].upper()}"
        req = self.allocation_queues[isbn].enqueue(request_id=req_id, user=user)

        return {
            "request_id": req.request_id,
            "isbn": isbn,
            "user_id": user_id,
            "calculated_priority": req.metadata.get("actual_priority", 0.0),
            "queue_position": self.allocation_queues[isbn].size(),
        }

    def process_smart_allocation_drop(self, isbn: str) -> Optional[Dict[str, Any]]:
        """
        Pops the highest-priority student from the max-heap and matches with an available copy.
        """
        queue = self.allocation_queues.get(isbn)
        if not queue or queue.size() == 0:
            return None

        book = self.db.get_book(isbn)
        if not isinstance(book, PhysicalBook):
            return None

        avail = book.get_available_copies()
        if not avail:
            return None

        copy = avail[0]
        top_req = queue.pop_highest_priority()
        if not top_req:
            return None

        # Issue copy to top request
        tx = self.issue_physical_book(copy.copy_id, top_req.user_id, actor_id="SMART_ALLOCATOR")
        return {
            "assigned_user_id": top_req.user_id,
            "user_name": top_req.user_name,
            "copy_id": copy.copy_id,
            "priority": top_req.metadata.get("actual_priority", 0.0),
            "transaction": tx,
        }
