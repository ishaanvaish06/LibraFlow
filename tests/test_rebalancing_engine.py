"""
Tests for the Cross-Branch Inventory Rebalancing Engine & Closed-Loop Metrics.
"""

from __future__ import annotations

from datetime import date

from libflow.ai.demand_forecaster import DemandForecaster
from libflow.ai.rebalancer import CrossBranchRebalancingEngine
from libflow.core.book import PhysicalBook, BookCopy
from libflow.core.branch import LibraryBranch
from libflow.core.enums import BookStatus
from libflow.distributed.branch_manager import MultiBranchManager
from libflow.distributed.event_bus import InMemoryEventBus
from libflow.storage.inmemory import InMemoryBookRepository, InMemoryBranchRepository
from tests.conftest import auth_headers


def test_rebalancing_engine_optimization_and_outcome_precision():
    book_repo = InMemoryBookRepository()
    branch_repo = InMemoryBranchRepository()
    branch_mgr = MultiBranchManager()
    forecaster = DemandForecaster()
    bus = InMemoryEventBus()

    # 1. Register branches
    delhi = LibraryBranch("BRANCH-DELHI", "Delhi Campus", "Delhi", latitude=28.6139, longitude=77.2090)
    mumbai = LibraryBranch("BRANCH-MUMBAI", "Mumbai Campus", "Mumbai", latitude=19.0760, longitude=72.8777)
    branch_repo.save_branch(delhi)
    branch_repo.save_branch(mumbai)
    branch_mgr.register_branch(delhi)
    branch_mgr.register_branch(mumbai)

    # 2. Add book with copies: 2 copies in Delhi, 0 in Mumbai
    book = PhysicalBook(
        isbn="978-0132350884",
        title="Clean Code",
        authors=["Robert C. Martin"],
        category="Software Engineering",
        publication_year=2008,
        publisher="Prentice Hall",
        description="Clean code guide",
        rating=4.7,
        difficulty_level="INTERMEDIATE",
        keywords=["Clean", "Code"],
        weight_grams=600,
        page_count=464,
    )
    copy1 = BookCopy("CC-DEL-01", "978-0132350884", branch_id="BRANCH-DELHI", shelf_location="A1", price=35.0)
    copy2 = BookCopy("CC-DEL-02", "978-0132350884", branch_id="BRANCH-DELHI", shelf_location="A2", price=35.0)
    book.add_copy(copy1)
    book.add_copy(copy2)
    book_repo.save_book(book)

    # 3. Simulate high demand (SURGE) at Mumbai branch
    today = date.today()
    for _ in range(6):
        forecaster.record_checkout("978-0132350884", today, branch_id="BRANCH-MUMBAI")

    # 4. Instantiate rebalancing engine
    rebalancer = CrossBranchRebalancingEngine(
        book_repo=book_repo,
        branch_repo=branch_repo,
        branch_mgr=branch_mgr,
        forecaster=forecaster,
        event_bus=bus,
    )

    # Calculate rebalancing plan
    plan = rebalancer.calculate_rebalancing_plan()
    assert len(plan) == 1
    item = plan[0]
    assert item["isbn"] == "978-0132350884"
    assert item["source_branch_id"] == "BRANCH-DELHI"
    assert item["dest_branch_id"] == "BRANCH-MUMBAI"
    assert item["utility_score"] > 0

    # 5. Execute plan
    events = []
    bus.subscribe("transfer.requested", lambda p: events.append(p))

    transfers = rebalancer.execute_rebalancing_plan(plan)
    assert len(transfers) == 1
    trf_id = transfers[0]["transfer_id"]
    assert len(events) == 1
    assert events[0]["transfer_id"] == trf_id

    # Copy should now be IN_TRANSIT
    transferred_copy = book_repo.get_copy(item["copy_id"])
    assert transferred_copy.status == BookStatus.IN_TRANSIT

    # 6. Complete transfer (arrival at Mumbai)
    arrived = rebalancer.complete_transfer(trf_id)
    assert arrived is not None
    assert transferred_copy.branch_id == "BRANCH-MUMBAI"
    assert transferred_copy.status == BookStatus.AVAILABLE

    # 7. Check initial metrics before checkout
    metrics = rebalancer.get_outcome_metrics()
    assert metrics["arrived_at_destination"] == 1
    assert metrics["checked_out_within_7d"] == 0
    assert metrics["precision_rate_pct"] == 0.0

    # 8. Simulate checkout of the rebalanced copy at Mumbai
    hit = rebalancer.record_checkout_hook(transferred_copy.copy_id, "BRANCH-MUMBAI")
    assert hit is True

    # 9. Verify outcome metrics now show 100% precision
    final_metrics = rebalancer.get_outcome_metrics()
    assert final_metrics["checked_out_within_7d"] == 1
    assert final_metrics["precision_rate_pct"] == 100.0


def test_rebalance_api_endpoints(client, admin_token):
    headers = auth_headers(admin_token)

    # 1. Inspect plan endpoint
    plan_resp = client.get("/api/v1/rebalance/plan", headers=headers)
    assert plan_resp.status_code == 200
    assert "plan" in plan_resp.json()

    # 2. Run rebalance
    run_resp = client.post("/api/v1/rebalance/run", headers=headers)
    assert run_resp.status_code == 200
    assert "transfers" in run_resp.json()

    # 3. Query metrics
    metrics_resp = client.get("/api/v1/rebalance/metrics", headers=headers)
    assert metrics_resp.status_code == 200
    mdata = metrics_resp.json()["metrics"]
    assert "precision_rate_pct" in mdata
    assert "total_autonomous_transfers" in mdata
