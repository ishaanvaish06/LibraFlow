"""
Unit Tests for Phase 3: GoF Design Patterns & Business Logic
"""
from libflow.patterns.strategy_fine import (
    StandardFixedFineStrategy,
    DynamicDemandFineStrategy,
    TieredRiskFineStrategy,
)
from libflow.patterns.strategy_payment import (
    UpiPaymentStrategy,
    CardPaymentStrategy,
    WalletPaymentStrategy,
    PaymentProcessor,
)
from libflow.patterns.observer_notification import (
    NotificationDispatcher,
    EmailNotificationService,
    SmsNotificationService,
    InAppNotificationService,
    NotificationEvent,
)
from libflow.patterns.reservation_queue import BookReservationQueueManager
from libflow.patterns.singleton_logger import AuditLogger


def test_fine_calculation_strategies():
    book_meta_normal = {"pending_reservations_count": 0, "rating": 3.5}
    book_meta_high_demand = {"pending_reservations_count": 5, "rating": 4.8}
    user_meta = {"past_late_returns_count": 2}

    # 1. Fixed strategy
    fixed_strat = StandardFixedFineStrategy(daily_rate=10.0)
    assert fixed_strat.calculate_fine(5, book_meta_normal, user_meta) == 50.0

    # 2. Dynamic strategy (Demand and popularity increase fine)
    dynamic_strat = DynamicDemandFineStrategy(base_rate=10.0)
    fine_normal = dynamic_strat.calculate_fine(5, book_meta_normal, user_meta)
    fine_demand = dynamic_strat.calculate_fine(5, book_meta_high_demand, user_meta)
    assert fine_demand > fine_normal

    # 3. Tiered risk strategy
    tiered_strat = TieredRiskFineStrategy(base_rate=10.0)
    assert tiered_strat.calculate_fine(2, book_meta_normal, user_meta) == 20.0  # 2 * 10
    assert tiered_strat.calculate_fine(5, book_meta_normal, user_meta) == 30.0 + (2 * 15.0)  # 30 + 30 = 60


def test_payment_processor_strategies():
    # UPI
    upi = UpiPaymentStrategy()
    processor = PaymentProcessor(upi)
    res_upi = processor.execute_payment(amount=150.0, payer_id="user1", metadata={"vpa": "user1@okhdfcbank"})
    assert res_upi["status"] == "COMPLETED"
    assert "UPI-" in res_upi["transaction_id"]

    # Card
    card = CardPaymentStrategy()
    processor.set_strategy(card)
    res_card = processor.execute_payment(amount=200.0, payer_id="user1", metadata={"card_last4": "1234"})
    assert res_card["status"] == "COMPLETED"
    assert "CARD-" in res_card["transaction_id"]

    # Wallet
    wallets = {"user1": 300.0}
    wallet_strat = WalletPaymentStrategy(wallets)
    processor.set_strategy(wallet_strat)

    res_w = processor.execute_payment(amount=100.0, payer_id="user1")
    assert res_w["status"] == "COMPLETED"
    assert wallets["user1"] == 200.0

    # Insufficient funds
    res_fail = processor.execute_payment(amount=500.0, payer_id="user1")
    assert res_fail["status"] == "FAILED"


def test_observer_notifications():
    dispatcher = NotificationDispatcher()
    email_svc = EmailNotificationService()
    sms_svc = SmsNotificationService()
    inapp_svc = InAppNotificationService()

    dispatcher.subscribe(email_svc)
    dispatcher.subscribe(sms_svc)
    dispatcher.subscribe(inapp_svc)

    event = NotificationEvent(
        event_type="BOOK_ISSUED",
        recipient_id="STU-001",
        message="Operating Systems has been checked out successfully.",
        payload={"isbn": "ISBN-OS", "phone": "+91-9876543210"},
    )
    dispatcher.dispatch(event)

    assert len(email_svc.sent_emails) == 1
    assert email_svc.sent_emails[0]["to"] == "STU-001"
    assert len(sms_svc.sent_sms) == 1
    assert sms_svc.sent_sms[0]["phone"] == "+91-9876543210"
    assert len(inapp_svc.get_user_notifications("STU-001")) == 1


def test_reservation_queue_auto_assignment():
    dispatcher = NotificationDispatcher()
    inapp_svc = InAppNotificationService()
    dispatcher.subscribe(inapp_svc)

    mgr = BookReservationQueueManager(notification_dispatcher=dispatcher)

    # Alice and Bob reserve the same book
    res1 = mgr.reserve_book("ISBN-CLEAN", "ALICE")
    res2 = mgr.reserve_book("ISBN-CLEAN", "BOB")

    assert mgr.get_waiting_count("ISBN-CLEAN") == 2

    # A copy is returned!
    assigned = mgr.handle_copy_returned("ISBN-CLEAN", "COPY-001")
    assert assigned is not None
    assert assigned.user_id == "ALICE"  # Alice is first
    assert assigned.assigned_copy_id == "COPY-001"
    assert mgr.get_waiting_count("ISBN-CLEAN") == 1

    # Alice should have received an In-App notification
    notifs = inapp_svc.get_user_notifications("ALICE")
    assert len(notifs) == 1
    assert "ready for pickup" in notifs[0]["message"]


def test_singleton_audit_logger():
    logger1 = AuditLogger()
    logger2 = AuditLogger()
    assert logger1 is logger2

    logger1.clear()
    logger1.log_event("USER-1", "BOOK_BORROW", "COPY-100", {"isbn": "ISBN-OS"})
    logger2.log_event("USER-2", "PAY_FINE", "TX-1", {"amount": 50.0})

    logs = logger1.get_logs()
    assert len(logs) == 2
    assert logs[0]["action"] == "BOOK_BORROW"
    assert logs[1]["action"] == "PAY_FINE"
