"""
Circulation Service: checkouts, returns, smart allocation and reservation queues.

Concurrency control for copy mutations lives in the storage layer (see
``BookRepository.locking_section``): a per-copy mutex for the in-memory store,
a ``SELECT ... FOR UPDATE`` transaction for PostgreSQL. The service treats the
lock as a black box — which keeps this module storage-agnostic.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, Optional
import uuid

from libflow.ai.demand_forecaster import DemandForecaster
from libflow.core.book import PhysicalBook
from libflow.core.enums import BookStatus
from libflow.core.exceptions import (
    CopyNotFoundError,
    CopyUnavailableError,
    InvalidStateTransitionError,
    UserNotFoundError,
    UserNotEligibleError,
)
from libflow.dsa.priority_queue import SmartAllocationQueue
from libflow.patterns.observer_notification import NotificationDispatcher, NotificationEvent
from libflow.patterns.reservation_queue import BookReservationQueueManager
from libflow.patterns.singleton_logger import AuditLogger
from libflow.storage.cache import Cache
from libflow.storage.outbox import OutboxRepository
from libflow.storage.repository import (
    BookRepository,
    CirculationRecordRepository,
    UserRepository,
)


class CirculationService:
    def __init__(
        self,
        book_repo: BookRepository,
        user_repo: UserRepository,
        circulation_repo: CirculationRecordRepository,
        cache: Cache,
        reservation_mgr: BookReservationQueueManager,
        dispatcher: NotificationDispatcher,
        demand_forecaster: DemandForecaster,
        outbox_repo: Optional[OutboxRepository] = None,
        rebalancer: Optional[Any] = None,
    ):
        self.book_repo = book_repo
        self.user_repo = user_repo
        self.circulation_repo = circulation_repo
        self.cache = cache
        self.reservation_mgr = reservation_mgr
        self.dispatcher = dispatcher
        self.demand_forecaster = demand_forecaster
        self.outbox_repo = outbox_repo
        self.rebalancer = rebalancer
        self.audit_logger = AuditLogger()
        # isbn -> SmartAllocationQueue (in-memory, DSA showcase)
        self.allocation_queues: Dict[str, SmartAllocationQueue] = {}

    def issue_physical_book(
        self,
        copy_id: str,
        user_id: str,
        actor_id: str = "LIBRARIAN",
        loan_days: int = 14,
    ) -> Dict[str, Any]:
        """Issue a physical copy under an exclusive lock; guarantees exactly one
        concurrent checkout succeeds for a given copy."""
        user = self.user_repo.get_user(user_id)
        if not user:
            raise UserNotFoundError(user_id)
        if not user.can_borrow():
            raise UserNotEligibleError(user_id, "borrow limit reached or unpaid fines")

        with self.book_repo.locking_section(copy_id) as session:
            copy = self.book_repo.get_copy(copy_id, session=session)
            if not copy:
                raise CopyNotFoundError(copy_id)

            if copy.status != BookStatus.AVAILABLE:
                is_reserved_for_user = (
                    copy.status == BookStatus.RESERVED
                    and copy.current_reserver_id == user_id
                )
                if not is_reserved_for_user:
                    raise CopyUnavailableError(copy_id, copy.status.value)

            try:
                copy.check_out(user_id)
            except ValueError as exc:
                raise InvalidStateTransitionError(str(exc))

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
            self.circulation_repo.save_record(tx_record, session=session)
            self.book_repo.save_copy(copy, session=session)
            self.user_repo.save_user(user, session=session)

            if self.outbox_repo is not None:
                self.outbox_repo.save_event(
                    topic="copy.issued",
                    payload={
                        "copy_id": copy_id,
                        "isbn": copy.book_isbn,
                        "user_id": user_id,
                        "due_date": due_date.isoformat(),
                        "transaction_id": tx_record["transaction_id"],
                    },
                    session=session,
                )

            self.demand_forecaster.record_checkout(copy.book_isbn, datetime.now().date(), branch_id=copy.branch_id)
            if self.rebalancer is not None:
                self.rebalancer.record_checkout_hook(copy_id, copy.branch_id)
            self.cache.invalidate(f"book:{copy.book_isbn}")

            self.dispatcher.dispatch(NotificationEvent(
                event_type="BOOK_ISSUED",
                recipient_id=user_id,
                message=(
                    f"Book copy '{copy_id}' issued successfully. "
                    f"Due on {due_date.strftime('%Y-%m-%d')}."
                ),
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
        """Return a copy, auto-assign the next reservation waiter, and audit."""
        with self.book_repo.locking_section(copy_id) as session:
            copy = self.book_repo.get_copy(copy_id, session=session)
            if not copy:
                raise CopyNotFoundError(copy_id)

            borrower_id = copy.current_borrower_id
            if not borrower_id:
                raise InvalidStateTransitionError(
                    f"Copy '{copy_id}' is not currently issued to any user."
                )

            user = self.user_repo.get_user(borrower_id, session=session)
            if user:
                user.record_return(copy_id, is_late=is_late, is_damaged=is_damaged)
                self.user_repo.save_user(user, session=session)

            copy.return_book()
            self.book_repo.save_copy(copy, session=session)

            assigned_res = self.reservation_mgr.handle_copy_returned(copy.book_isbn, copy_id)
            if assigned_res:
                copy.reserve(assigned_res.user_id)
                self.book_repo.save_copy(copy, session=session)

            if self.outbox_repo is not None:
                self.outbox_repo.save_event(
                    topic="copy.returned",
                    payload={
                        "copy_id": copy_id,
                        "isbn": copy.book_isbn,
                        "user_id": borrower_id,
                        "is_late": is_late,
                        "is_damaged": is_damaged,
                        "assigned_reservation": assigned_res.reservation_id if assigned_res else None,
                    },
                    session=session,
                )

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
        user = self.user_repo.get_user(user_id)
        if not user:
            raise UserNotFoundError(user_id)

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
        queue = self.allocation_queues.get(isbn)
        if not queue or queue.size() == 0:
            return None

        book = self.book_repo.get_book(isbn)
        if not isinstance(book, PhysicalBook):
            return None

        available = book.get_available_copies()
        if not available:
            return None

        top_req = queue.pop_highest_priority()
        if not top_req:
            return None

        tx = self.issue_physical_book(
            available[0].copy_id, top_req.user_id, actor_id="SMART_ALLOCATOR"
        )
        return {
            "assigned_user_id": top_req.user_id,
            "user_name": top_req.user_name,
            "copy_id": available[0].copy_id,
            "priority": top_req.metadata.get("actual_priority", 0.0),
            "transaction": tx,
        }
