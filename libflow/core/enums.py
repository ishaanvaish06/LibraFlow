"""
Core Enumerations for LibraFlow Domain Model
"""
from enum import Enum, auto


class BookFormat(str, Enum):
    PHYSICAL = "PHYSICAL"
    EBOOK = "EBOOK"
    AUDIOBOOK = "AUDIOBOOK"


class BookStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    RESERVED = "RESERVED"
    ISSUED = "ISSUED"
    IN_TRANSIT = "IN_TRANSIT"
    UNDER_REPAIR = "UNDER_REPAIR"
    LOST = "LOST"


class UserRole(str, Enum):
    STUDENT = "STUDENT"
    FACULTY = "FACULTY"
    LIBRARIAN = "LIBRARIAN"
    ADMIN = "ADMIN"


class ReservationStatus(str, Enum):
    PENDING = "PENDING"
    READY_FOR_PICKUP = "READY_FOR_PICKUP"
    FULFILLED = "FULFILLED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"


class PaymentMethod(str, Enum):
    UPI = "UPI"
    CREDIT_CARD = "CREDIT_CARD"
    DEBIT_CARD = "DEBIT_CARD"
    WALLET = "WALLET"
    CASH = "CASH"


class PaymentStatus(str, Enum):
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    REFUNDED = "REFUNDED"


class NotificationChannel(str, Enum):
    EMAIL = "EMAIL"
    SMS = "SMS"
    IN_APP = "IN_APP"
    WEBHOOK = "WEBHOOK"


class TransferStatus(str, Enum):
    REQUESTED = "REQUESTED"
    APPROVED = "APPROVED"
    IN_TRANSIT = "IN_TRANSIT"
    COMPLETED = "COMPLETED"
    REJECTED = "REJECTED"
