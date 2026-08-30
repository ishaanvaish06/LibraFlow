"""
Smart Book Allocation Engine using Max-Heap / Priority Queue
Implements dynamic priority scoring based on exam urgency, academic seniority, and past library usage.
"""
from typing import List, Optional, Any, Dict
import heapq
from datetime import date, datetime
from dataclasses import dataclass, field

from libflow.core.user import User, Student


@dataclass(order=True)
class BorrowRequest:
    priority: float
    request_id: str = field(compare=False)
    user_id: str = field(compare=False)
    user_name: str = field(compare=False)
    isbn: str = field(compare=False)
    branch_id: str = field(compare=False)
    timestamp: datetime = field(default_factory=datetime.now, compare=False)
    metadata: Dict[str, Any] = field(default_factory=dict, compare=False)


class SmartAllocationQueue:
    """
    Max-Heap powered Priority Queue for allocating high-demand books to students.
    """

    def __init__(self, isbn: str):
        self.isbn = isbn
        # Internal min-heap storing (-priority, BorrowRequest) for max-heap behavior
        self._heap: List[BorrowRequest] = []
        self._entry_counter = 0

    @staticmethod
    def calculate_priority(user: User, book_category: str = "") -> float:
        """
        Computes the priority score:
        Priority = 0.4 * Exam Urgency + 0.3 * Academic Year + 0.3 * Historical Usage
        """
        # 1. Exam Urgency (0.0 to 1.0)
        exam_urgency = 0.2  # Default baseline
        academic_score = 0.25
        history_score = 0.1

        if isinstance(user, Student):
            # Academic year scaling (1st yr: 0.25, 2nd yr: 0.50, 3rd yr: 0.75, 4th yr: 1.0)
            academic_score = min(1.0, max(0.25, user.academic_year / 4.0))

            # Exam urgency: closer exam = higher urgency
            if user.exam_date:
                today = date.today()
                days_until_exam = (user.exam_date - today).days
                if days_until_exam <= 1:
                    exam_urgency = 1.0
                elif days_until_exam <= 3:
                    exam_urgency = 0.9
                elif days_until_exam <= 7:
                    exam_urgency = 0.75
                elif days_until_exam <= 14:
                    exam_urgency = 0.5
                elif days_until_exam <= 30:
                    exam_urgency = 0.3
                else:
                    exam_urgency = 0.1
        else:
            # Faculty / Librarian baseline
            academic_score = 0.9
            exam_urgency = 0.5

        # 3. Previous usage score (more active on-time readers get reward)
        completed_borrows = len([b for b in user.borrow_history if b.get("returned_at") is not None])
        history_score = min(1.0, completed_borrows / 10.0)

        # Multi-factor weighting formula
        priority = (0.4 * exam_urgency) + (0.3 * academic_score) + (0.3 * history_score)
        return round(priority, 4)

    def enqueue(
        self,
        request_id: str,
        user: User,
        branch_id: str = "BRANCH-CENTRAL",
        book_category: str = "",
        custom_priority: Optional[float] = None,
    ) -> BorrowRequest:
        """
        Pushes a new request into the priority queue.
        """
        priority = custom_priority if custom_priority is not None else self.calculate_priority(user, book_category)
        
        # We store negative priority in python's min-heap to simulate max-heap
        req = BorrowRequest(
            priority=-priority,  # Negative for max-heap
            request_id=request_id,
            user_id=user.user_id,
            user_name=user.name,
            isbn=self.isbn,
            branch_id=branch_id,
            metadata={
                "actual_priority": priority,
                "role": user.get_role().value,
            },
        )
        heapq.heappush(self._heap, req)
        return req

    def pop_highest_priority(self) -> Optional[BorrowRequest]:
        """
        Pops and returns the highest priority request.
        """
        if not self._heap:
            return None
        req = heapq.heappop(self._heap)
        # Restore positive priority in metadata representation
        return req

    def peek(self) -> Optional[BorrowRequest]:
        return self._heap[0] if self._heap else None

    def size(self) -> int:
        return len(self._heap)

    def to_list(self) -> List[Dict[str, Any]]:
        # Return sorted by priority without consuming heap
        sorted_copy = sorted(self._heap)
        return [
            {
                "request_id": r.request_id,
                "user_id": r.user_id,
                "user_name": r.user_name,
                "priority": round(-r.priority, 4),
                "branch_id": r.branch_id,
                "timestamp": r.timestamp.isoformat(),
            }
            for r in sorted_copy
        ]
