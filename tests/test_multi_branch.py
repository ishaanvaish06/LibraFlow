"""
Unit Tests for Phase 6: Multi-Branch Network, Inter-Branch Transfers & Service Orchestration
"""
import pytest
from libflow.core.enums import TransferStatus, BookStatus
from libflow.core.branch import LibraryBranch
from libflow.core.book import PhysicalBook, BookCopy
from libflow.core.user import Student, Librarian
from libflow.distributed.branch_manager import MultiBranchManager
from libflow.distributed.event_bus import DistributedEventBus
from libflow.storage.database import LibraryDatabase
from libflow.storage.cache import DistributedCache
from libflow.storage.lock_manager import ConcurrencyLockManager
from libflow.dsa.trie import AutocompleteTrie
from libflow.dsa.inverted_index import InvertedIndex
from libflow.dsa.graph import BookGraphEngine
from libflow.patterns.reservation_queue import BookReservationQueueManager
from libflow.patterns.observer_notification import NotificationDispatcher
from libflow.ai.recommendation_engine import AIRecommendationEngine
from libflow.ai.demand_forecaster import DemandForecaster
from libflow.services import CatalogService, CirculationService, BillingService, IntelligenceService


def test_multi_branch_manager_transfer_lifecycle():
    mgr = MultiBranchManager()

    delhi = LibraryBranch(branch_id="BRANCH-DELHI", name="Delhi Central Library", city="Delhi")
    mumbai = LibraryBranch(branch_id="BRANCH-MUMBAI", name="Mumbai Tech Campus", city="Mumbai")
    pune = LibraryBranch(branch_id="BRANCH-PUNE", name="Pune Research Library", city="Pune")

    mgr.register_branch(delhi)
    mgr.register_branch(mumbai)
    mgr.register_branch(pune)

    assert len(mgr.list_all_branches()) == 3

    # Create a copy in Delhi
    copy = BookCopy(copy_id="COPY-DEL-1", book_isbn="ISBN-ALGO", branch_id="BRANCH-DELHI")
    assert copy.branch_id == "BRANCH-DELHI"
    assert copy.status == BookStatus.AVAILABLE

    # Request transfer to Mumbai
    req = mgr.request_transfer(copy, dest_branch_id="BRANCH-MUMBAI", requested_by="LIB-MUMBAI")
    assert req.status == TransferStatus.IN_TRANSIT
    assert copy.status == BookStatus.IN_TRANSIT

    # Complete transfer
    completed_req = mgr.complete_transfer(req.transfer_id, copy)
    assert completed_req.status == TransferStatus.COMPLETED
    assert copy.status == BookStatus.AVAILABLE
    assert copy.branch_id == "BRANCH-MUMBAI"


def test_end_to_end_service_orchestration():
    # Setup infrastructure
    db = LibraryDatabase()
    cache = DistributedCache()
    lock_mgr = ConcurrencyLockManager()
    trie = AutocompleteTrie()
    index = InvertedIndex()
    graph = BookGraphEngine()
    dispatcher = NotificationDispatcher()
    reservation_mgr = BookReservationQueueManager(notification_dispatcher=dispatcher)
    forecaster = DemandForecaster()
    recommender = AIRecommendationEngine(graph_engine=graph)

    catalog_svc = CatalogService(db, trie, index, cache)
    circulation_svc = CirculationService(db, lock_mgr, cache, reservation_mgr, dispatcher, forecaster)
    billing_svc = BillingService(db, reservation_mgr, dispatcher)
    intel_svc = IntelligenceService(db, recommender, graph, forecaster)

    # 1. Register users
    student = Student(user_id="U-100", name="Ishaan", email="ishaan@test.com", academic_year=3)
    db.save_user(student)

    # 2. Register book & copies
    book = catalog_svc.register_book(
        format_type="PHYSICAL",
        actor_id="ADMIN",
        isbn="978-0132350884",
        title="Clean Code",
        authors=["Robert C. Martin"],
        category="Software Engineering",
        publication_year=2008,
        rating=4.9,
    )
    copy = catalog_svc.add_physical_copy(isbn="978-0132350884", copy_id="CC-001", branch_id="BRANCH-DELHI")

    # 3. Autocomplete & search
    auto_res = catalog_svc.autocomplete("Clean")
    assert len(auto_res) >= 1
    assert auto_res[0]["id"] == "978-0132350884"

    search_res = catalog_svc.search_books("code")
    assert len(search_res) == 1

    # 4. Issue book
    tx = circulation_svc.issue_physical_book("CC-001", "U-100")
    assert tx["type"] == "BORROW"
    assert copy.status == BookStatus.ISSUED

    # 5. Fine calculation & payment
    fine_res = billing_svc.charge_fine("U-100", "978-0132350884", overdue_days=3)
    assert fine_res["fine_charged"] > 0

    pay_res = billing_svc.pay_fine("U-100", fine_res["fine_charged"], payment_method="UPI")
    assert pay_res["status"] == "COMPLETED"
    assert pay_res["remaining_unpaid_balance"] == 0.0

    # 6. Return book
    ret_res = circulation_svc.return_physical_book("CC-001")
    assert ret_res["status"] == "AVAILABLE"
