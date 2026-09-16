"""
Billing & Fines Service: fine calculations, security deposits, and payments.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from libflow.core.exceptions import UserNotFoundError
from libflow.patterns.observer_notification import NotificationDispatcher, NotificationEvent
from libflow.patterns.reservation_queue import BookReservationQueueManager
from libflow.patterns.singleton_logger import AuditLogger
from libflow.patterns.strategy_fine import (
    DynamicDemandFineStrategy,
    FineCalculationStrategy,
)
from libflow.patterns.strategy_payment import (
    CardPaymentStrategy,
    PaymentProcessor,
    UpiPaymentStrategy,
    WalletPaymentStrategy,
)
from libflow.storage.repository import BookRepository, UserRepository


class BillingService:
    def __init__(
        self,
        book_repo: BookRepository,
        user_repo: UserRepository,
        reservation_mgr: BookReservationQueueManager,
        dispatcher: NotificationDispatcher,
    ):
        self.book_repo = book_repo
        self.user_repo = user_repo
        self.reservation_mgr = reservation_mgr
        self.dispatcher = dispatcher
        self.audit_logger = AuditLogger()
        self.user_wallets: Dict[str, float] = {}

        self.fine_strategy: FineCalculationStrategy = DynamicDemandFineStrategy(base_rate=10.0)
        self.payment_processor = PaymentProcessor(UpiPaymentStrategy())

    def set_fine_strategy(self, strategy: FineCalculationStrategy) -> None:
        self.fine_strategy = strategy

    def calculate_projected_fine(self, isbn: str, user_id: str, overdue_days: int) -> float:
        book = self.book_repo.get_book(isbn)
        user = self.user_repo.get_user(user_id)
        if not book or not user:
            return 0.0

        book_meta = {
            "pending_reservations_count": self.reservation_mgr.get_waiting_count(isbn),
            "rating": book.rating,
        }
        user_meta = {
            "past_late_returns_count": len([b for b in user.borrow_history if b.get("is_late")]),
        }
        return self.fine_strategy.calculate_fine(overdue_days, book_meta, user_meta)

    def charge_fine(self, user_id: str, isbn: str, overdue_days: int, actor_id: str = "SYSTEM") -> Dict[str, Any]:
        fine_amount = self.calculate_projected_fine(isbn, user_id, overdue_days)
        user = self.user_repo.get_user(user_id)
        if not user:
            raise UserNotFoundError(user_id)

        user.add_fine(fine_amount)
        self.user_repo.save_user(user)

        self.dispatcher.dispatch(NotificationEvent(
            event_type="OVERDUE_FINE_ACCRUED",
            recipient_id=user_id,
            message=(
                f"Overdue fine of ${fine_amount:.2f} accrued for book '{isbn}'. "
                f"Total balance: ${user.unpaid_fines_balance:.2f}."
            ),
            payload={"isbn": isbn, "amount": fine_amount, "balance": user.unpaid_fines_balance},
        ))
        self.audit_logger.log_event(
            actor_id=actor_id,
            action="CHARGE_FINE",
            resource_id=user_id,
            details={"isbn": isbn, "fine_amount": fine_amount, "new_balance": user.unpaid_fines_balance},
        )
        return {
            "user_id": user_id,
            "fine_charged": fine_amount,
            "total_unpaid_balance": user.unpaid_fines_balance,
        }

    def pay_fine(
        self,
        user_id: str,
        amount: float,
        payment_method: str = "UPI",
        payment_metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        user = self.user_repo.get_user(user_id)
        if not user:
            raise UserNotFoundError(user_id)

        method = payment_method.upper()
        if method == "UPI":
            self.payment_processor.set_strategy(UpiPaymentStrategy())
        elif method in ("CARD", "CREDIT_CARD", "DEBIT_CARD"):
            self.payment_processor.set_strategy(CardPaymentStrategy())
        elif method == "WALLET":
            self.payment_processor.set_strategy(WalletPaymentStrategy(self.user_wallets))
        else:
            from libflow.core.exceptions import InsufficientInputError

            raise InsufficientInputError(f"Unsupported payment method '{payment_method}'.")

        tx_result = self.payment_processor.execute_payment(amount, user_id, payment_metadata)
        if tx_result["status"] == "COMPLETED":
            paid_amount = user.pay_fine(amount)
            tx_result["applied_to_fine"] = paid_amount
            tx_result["remaining_unpaid_balance"] = user.unpaid_fines_balance
            self.user_repo.save_user(user)

            self.audit_logger.log_event(
                actor_id=user_id,
                action="PAY_FINE",
                resource_id=tx_result["transaction_id"],
                details={"amount": amount, "method": method, "remaining_balance": user.unpaid_fines_balance},
            )

        return tx_result
