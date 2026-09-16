"""
Core User Domain Model & Role-Based Access Control (RBAC)
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import List, Set, Dict, Any, Optional
from datetime import datetime, date

from libflow.core.enums import UserRole


class User(ABC):
    """
    Abstract Base Class for all library system users.
    Encapsulates identity, borrowing privileges, fines, and security profile.
    """

    def __init__(
        self,
        user_id: str,
        name: str,
        email: str,
        password_hash: str = "hashed_default_pwd",
        max_borrow_limit: int = 3,
        branch_id: str = "BRANCH-CENTRAL",
    ):
        self.user_id = user_id
        self.name = name
        self.email = email
        self.password_hash = password_hash
        self.max_borrow_limit = max_borrow_limit
        self.branch_id = branch_id

        # State tracking
        self.active_borrowed_copy_ids: Set[str] = set()
        self.borrow_history: List[Dict[str, Any]] = []
        self.active_reservations: Set[str] = set()
        self.unpaid_fines_balance: float = 0.0
        self.security_deposit_balance: float = 0.0
        self.is_suspended: bool = False
        self.created_at: datetime = datetime.now()

    @abstractmethod
    def get_role(self) -> UserRole:
        """Returns the primary role enum of the user."""
        pass

    @abstractmethod
    def get_permissions(self) -> Set[str]:
        """Returns the set of permission strings assigned to this user role."""
        pass

    def has_permission(self, permission: str) -> bool:
        return permission in self.get_permissions() or "ALL" in self.get_permissions()

    def can_borrow(self) -> bool:
        if self.is_suspended:
            return False
        if self.unpaid_fines_balance > 100.0:  # Fine threshold
            return False
        if len(self.active_borrowed_copy_ids) >= self.max_borrow_limit:
            return False
        return True

    def add_borrow(self, copy_id: str, isbn: str) -> None:
        self.active_borrowed_copy_ids.add(copy_id)
        self.borrow_history.append({
            "copy_id": copy_id,
            "isbn": isbn,
            "borrowed_at": datetime.now().isoformat(),
            "returned_at": None,
            "is_late": False,
            "is_damaged": False,
        })

    def record_return(self, copy_id: str, is_late: bool = False, is_damaged: bool = False) -> None:
        self.active_borrowed_copy_ids.discard(copy_id)
        for record in reversed(self.borrow_history):
            if record["copy_id"] == copy_id and record["returned_at"] is None:
                record["returned_at"] = datetime.now().isoformat()
                record["is_late"] = is_late
                record["is_damaged"] = is_damaged
                break

    def add_fine(self, amount: float) -> None:
        self.unpaid_fines_balance += max(0.0, amount)

    def pay_fine(self, amount: float) -> float:
        paid = min(self.unpaid_fines_balance, amount)
        self.unpaid_fines_balance -= paid
        return paid

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "name": self.name,
            "email": self.email,
            "role": self.get_role().value,
            "max_borrow_limit": self.max_borrow_limit,
            "active_borrows_count": len(self.active_borrowed_copy_ids),
            "unpaid_fines": self.unpaid_fines_balance,
            "security_deposit": self.security_deposit_balance,
            "is_suspended": self.is_suspended,
            "branch_id": self.branch_id,
        }


class Student(User):
    """
    Student user type with academic profile for smart priority allocation.
    """

    def __init__(
        self,
        user_id: str,
        name: str,
        email: str,
        academic_year: int = 1,
        major: str = "Computer Science",
        exam_date: Optional[date] = None,
        password_hash: str = "hashed_student_pwd",
        branch_id: str = "BRANCH-CENTRAL",
        max_borrow_limit: int = 4,
    ):
        super().__init__(
            user_id=user_id,
            name=name,
            email=email,
            password_hash=password_hash,
            max_borrow_limit=max_borrow_limit,
            branch_id=branch_id,
        )
        self.academic_year = academic_year  # 1st, 2nd, 3rd, 4th year
        self.major = major
        self.exam_date = exam_date

    def get_role(self) -> UserRole:
        return UserRole.STUDENT

    def get_permissions(self) -> Set[str]:
        return {
            "BOOK_SEARCH",
            "BOOK_RESERVE",
            "BOOK_READ_DIGITAL",
            "VIEW_PROFILE",
            "PAY_FINES",
        }

    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data.update({
            "academic_year": self.academic_year,
            "major": self.major,
            "exam_date": self.exam_date.isoformat() if self.exam_date else None,
        })
        return data


class Faculty(User):
    """
    Faculty member with higher borrow privileges and extended duration.
    """

    def __init__(
        self,
        user_id: str,
        name: str,
        email: str,
        department: str = "Computer Science & Engineering",
        password_hash: str = "hashed_faculty_pwd",
        branch_id: str = "BRANCH-CENTRAL",
    ):
        super().__init__(
            user_id=user_id,
            name=name,
            email=email,
            password_hash=password_hash,
            max_borrow_limit=10,
            branch_id=branch_id,
        )
        self.department = department

    def get_role(self) -> UserRole:
        return UserRole.FACULTY

    def get_permissions(self) -> Set[str]:
        return {
            "BOOK_SEARCH",
            "BOOK_RESERVE",
            "BOOK_READ_DIGITAL",
            "VIEW_PROFILE",
            "PAY_FINES",
            "FACULTY_PRIORITY_BORROW",
        }


class Librarian(User):
    """
    Librarian user responsible for circulation desk, inventory management, and inter-branch transfers.
    """

    def __init__(
        self,
        user_id: str,
        name: str,
        email: str,
        staff_code: str = "LIB-001",
        password_hash: str = "hashed_librarian_pwd",
        branch_id: str = "BRANCH-CENTRAL",
    ):
        super().__init__(
            user_id=user_id,
            name=name,
            email=email,
            password_hash=password_hash,
            max_borrow_limit=15,
            branch_id=branch_id,
        )
        self.staff_code = staff_code

    def get_role(self) -> UserRole:
        return UserRole.LIBRARIAN

    def get_permissions(self) -> Set[str]:
        return {
            "BOOK_SEARCH",
            "BOOK_ISSUE",
            "BOOK_RETURN",
            "BOOK_MANAGE_INVENTORY",
            "BOOK_TRANSFER_INITIATE",
            "BOOK_TRANSFER_RECEIVE",
            "BOOK_ALLOCATE",
            "BOOK_RESERVE",
            "BILLING_PAY",
            "INTEL_RECOMMENDATIONS",
            "INTEL_RISK_ASSESSMENT",
            "INTEL_LEARNING_PATH",
            "INTEL_GRAPH_TRAVERSE",
            "FINE_WAIVE_PARTIAL",
            "USER_VIEW_CIRCULATION",
        }


class Admin(User):
    """
    System Administrator with unrestricted access.
    """

    def __init__(
        self,
        user_id: str,
        name: str,
        email: str,
        password_hash: str = "hashed_admin_pwd",
        branch_id: str = "BRANCH-CENTRAL",
    ):
        super().__init__(
            user_id=user_id,
            name=name,
            email=email,
            password_hash=password_hash,
            max_borrow_limit=50,
            branch_id=branch_id,
        )

    def get_role(self) -> UserRole:
        return UserRole.ADMIN

    def get_permissions(self) -> Set[str]:
        return {"ALL"}
