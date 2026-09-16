"""
GoF Strategy Pattern for Multi-Channel Payment Processing
Supports UPI, Credit/Debit Cards, and Internal Digital Wallets
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import uuid
from datetime import datetime

from libflow.core.enums import PaymentMethod, PaymentStatus


class PaymentStrategy(ABC):
    """
    Abstract Strategy in Payment Strategy Pattern.
    """

    @abstractmethod
    def process_payment(self, amount: float, payer_id: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        pass


class UpiPaymentStrategy(PaymentStrategy):
    """
    UPI Payment Strategy (Virtual Payment Address / QR Flow).
    """

    def process_payment(self, amount: float, payer_id: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        vpa = metadata.get("vpa", f"{payer_id}@upi")
        if "@" not in vpa:
            return {
                "transaction_id": str(uuid.uuid4()),
                "status": PaymentStatus.FAILED.value,
                "amount": amount,
                "error": "Invalid UPI VPA address format.",
            }

        return {
            "transaction_id": f"UPI-{uuid.uuid4().hex[:10].upper()}",
            "method": PaymentMethod.UPI.value,
            "status": PaymentStatus.COMPLETED.value,
            "amount": amount,
            "payer_id": payer_id,
            "vpa": vpa,
            "timestamp": datetime.now().isoformat(),
        }


class CardPaymentStrategy(PaymentStrategy):
    """
    Card Payment Strategy (Simulating Stripe/PG Tokenized Charge).
    """

    def process_payment(self, amount: float, payer_id: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        card_last4 = metadata.get("card_last4", "4242")
        expiry = metadata.get("expiry", "12/28")

        if len(card_last4) != 4:
            return {
                "transaction_id": str(uuid.uuid4()),
                "status": PaymentStatus.FAILED.value,
                "amount": amount,
                "error": "Invalid card details provided.",
            }

        return {
            "transaction_id": f"CARD-{uuid.uuid4().hex[:10].upper()}",
            "method": PaymentMethod.CREDIT_CARD.value,
            "status": PaymentStatus.COMPLETED.value,
            "amount": amount,
            "payer_id": payer_id,
            "card_last4": card_last4,
            "timestamp": datetime.now().isoformat(),
        }


class WalletPaymentStrategy(PaymentStrategy):
    """
    Digital Wallet Payment Strategy using user's prepaid library balance.
    """

    def __init__(self, user_wallet_balances: Dict[str, float]):
        self.wallets = user_wallet_balances

    def process_payment(self, amount: float, payer_id: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        current_balance = self.wallets.get(payer_id, 0.0)
        if current_balance < amount:
            return {
                "transaction_id": str(uuid.uuid4()),
                "status": PaymentStatus.FAILED.value,
                "amount": amount,
                "payer_id": payer_id,
                "error": f"Insufficient wallet balance. Available: {current_balance}, Required: {amount}",
            }

        self.wallets[payer_id] = round(current_balance - amount, 2)
        return {
            "transaction_id": f"WLT-{uuid.uuid4().hex[:10].upper()}",
            "method": PaymentMethod.WALLET.value,
            "status": PaymentStatus.COMPLETED.value,
            "amount": amount,
            "payer_id": payer_id,
            "remaining_balance": self.wallets[payer_id],
            "timestamp": datetime.now().isoformat(),
        }


class PaymentProcessor:
    """
    Context in Strategy Pattern.
    """

    def __init__(self, strategy: PaymentStrategy):
        self._strategy = strategy

    def set_strategy(self, strategy: PaymentStrategy) -> None:
        self._strategy = strategy

    def execute_payment(self, amount: float, payer_id: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if amount <= 0:
            raise ValueError("Payment amount must be greater than 0.")
        return self._strategy.process_payment(amount, payer_id, metadata or {})
