"""
GoF State Pattern Implementation for Book Copy Lifecycle
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING
from libflow.core.enums import BookStatus

if TYPE_CHECKING:
    from libflow.core.book import BookCopy


class BookCopyState(ABC):
    """
    Abstract State in State Pattern.
    Defines allowed state transitions and business rules.
    """

    @abstractmethod
    def get_status(self) -> BookStatus:
        pass

    def check_out(self, copy: BookCopy, borrower_id: str) -> None:
        raise ValueError(f"Cannot checkout book copy in state '{self.get_status().value}'.")

    def return_book(self, copy: BookCopy) -> None:
        raise ValueError(f"Cannot return book copy in state '{self.get_status().value}'.")

    def reserve(self, copy: BookCopy, reserver_id: str) -> None:
        raise ValueError(f"Cannot reserve book copy in state '{self.get_status().value}'.")

    def start_transfer(self, copy: BookCopy, destination_branch: str) -> None:
        raise ValueError(f"Cannot transfer book copy in state '{self.get_status().value}'.")

    def complete_transfer(self, copy: BookCopy) -> None:
        raise ValueError(f"Cannot complete transfer in state '{self.get_status().value}'.")

    def mark_lost(self, copy: BookCopy) -> None:
        copy.set_state(LostState())

    def mark_repair(self, copy: BookCopy) -> None:
        copy.set_state(UnderRepairState())

    def restore_available(self, copy: BookCopy) -> None:
        copy.set_state(AvailableState())


class AvailableState(BookCopyState):
    def get_status(self) -> BookStatus:
        return BookStatus.AVAILABLE

    def check_out(self, copy: BookCopy, borrower_id: str) -> None:
        copy.current_borrower_id = borrower_id
        copy.set_state(IssuedState())

    def reserve(self, copy: BookCopy, reserver_id: str) -> None:
        copy.current_reserver_id = reserver_id
        copy.set_state(ReservedState())

    def start_transfer(self, copy: BookCopy, destination_branch: str) -> None:
        copy.target_branch_id = destination_branch
        copy.set_state(InTransitState())


class ReservedState(BookCopyState):
    def get_status(self) -> BookStatus:
        return BookStatus.RESERVED

    def check_out(self, copy: BookCopy, borrower_id: str) -> None:
        if copy.current_reserver_id and copy.current_reserver_id != borrower_id:
            raise ValueError(f"Copy is reserved for user '{copy.current_reserver_id}', not '{borrower_id}'.")
        copy.current_reserver_id = None
        copy.current_borrower_id = borrower_id
        copy.set_state(IssuedState())

    def return_book(self, copy: BookCopy) -> None:
        copy.current_reserver_id = None
        copy.set_state(AvailableState())


class IssuedState(BookCopyState):
    def get_status(self) -> BookStatus:
        return BookStatus.ISSUED

    def return_book(self, copy: BookCopy) -> None:
        copy.current_borrower_id = None
        copy.set_state(AvailableState())


class InTransitState(BookCopyState):
    def get_status(self) -> BookStatus:
        return BookStatus.IN_TRANSIT

    def complete_transfer(self, copy: BookCopy) -> None:
        if copy.target_branch_id:
            copy.branch_id = copy.target_branch_id
            copy.target_branch_id = None
        copy.set_state(AvailableState())


class UnderRepairState(BookCopyState):
    def get_status(self) -> BookStatus:
        return BookStatus.UNDER_REPAIR

    def restore_available(self, copy: BookCopy) -> None:
        copy.set_state(AvailableState())


class LostState(BookCopyState):
    def get_status(self) -> BookStatus:
        return BookStatus.LOST

    def restore_available(self, copy: BookCopy) -> None:
        copy.current_borrower_id = None
        copy.current_reserver_id = None
        copy.set_state(AvailableState())
