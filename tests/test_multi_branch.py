"""
Unit tests for the multi-branch transfer lifecycle and full service
orchestration through the repository-backed container.
"""

from __future__ import annotations

import pytest

from libflow.core.enums import BookStatus, TransferStatus


def test_multi_branch_manager_transfer_lifecycle(container):
    mgr = container.branch_mgr
    assert len(mgr.list_all_branches()) == 3

    copy = container.book_repo.get_copy("CC-DEL-02")
    assert copy.branch_id == "BRANCH-DELHI"
    assert copy.status == BookStatus.AVAILABLE

    req = mgr.request_transfer(copy, dest_branch_id="BRANCH-MUMBAI", requested_by="LIB-SARAH")
    assert req.status == TransferStatus.IN_TRANSIT
    assert copy.status == BookStatus.IN_TRANSIT

    completed = mgr.complete_transfer(req.transfer_id, copy)
    assert completed.status == TransferStatus.COMPLETED
    assert copy.status == BookStatus.AVAILABLE
    assert copy.branch_id == "BRANCH-MUMBAI"

    # Transfers to an unknown branch are rejected.
    with pytest.raises(ValueError, match="does not exist"):
        mgr.request_transfer(copy, dest_branch_id="BRANCH-NOPE", requested_by="LIB-SARAH")


def test_transfer_persists_state(container):
    # A transfer through the branch manager must also persist to the repo
    # so other services observe the new location.
    copy = container.book_repo.get_copy("CC-DEL-02")
    req = container.branch_mgr.request_transfer(
        copy, dest_branch_id="BRANCH-PUNE", requested_by="LIB-SARAH"
    )
    container.branch_mgr.complete_transfer(req.transfer_id, copy)
    container.book_repo.save_copy(copy)

    persisted = container.book_repo.get_copy("CC-DEL-02")
    assert persisted.branch_id == "BRANCH-PUNE"


def test_end_to_end_service_orchestration(container):
    catalog_svc = container.catalog_svc
    circulation_svc = container.circulation_svc
    billing_svc = container.billing_svc

    # Register a fresh student.
    from libflow.core.factory import UserFactory

    student = UserFactory.create_user(
        role="STUDENT", user_id="U-100", name="Ishaan", email="ishaan@test.com",
        password="passw0rd", academic_year=3,
    )
    container.user_repo.save_user(student)

    # Register a book + copy.
    book = catalog_svc.register_book(
        format_type="PHYSICAL", actor_id="ADMIN-01", isbn="978-0132350884",
        title="Clean Code", authors=["Robert C. Martin"],
        category="Software Engineering", publication_year=2008, rating=4.9,
    )
    container.recommender.register_book(book)
    copy = catalog_svc.add_physical_copy(
        isbn="978-0132350884", copy_id="CC-001", branch_id="BRANCH-DELHI"
    )

    assert len(catalog_svc.autocomplete("Clean")) >= 1
    assert len(catalog_svc.search_books("code")) >= 1

    tx = circulation_svc.issue_physical_book("CC-001", "U-100", actor_id="ADMIN-01")
    assert tx["type"] == "BORROW"
    assert copy.status == BookStatus.ISSUED

    fine = billing_svc.charge_fine("U-100", "978-0132350884", overdue_days=3)
    assert fine["fine_charged"] > 0

    pay = billing_svc.pay_fine("U-100", fine["fine_charged"], payment_method="UPI")
    assert pay["status"] == "COMPLETED"
    assert pay["remaining_unpaid_balance"] == 0.0

    ret = circulation_svc.return_physical_book("CC-001", actor_id="ADMIN-01")
    assert ret["status"] == "AVAILABLE"


def test_branches_are_registered_and_listed(container):
    branches = {b.branch_id for b in container.branch_repo.list_branches()}
    assert branches == {"BRANCH-DELHI", "BRANCH-MUMBAI", "BRANCH-PUNE"}


def test_user_borrow_limit_blocks_issue(container):
    from libflow.core.factory import UserFactory
    from libflow.core.exceptions import UserNotEligibleError

    maxed = UserFactory.create_user(
        role="STUDENT", user_id="U-MAXED", name="Maxed", email="m@test.com",
        password="x", academic_year=1,
    )
    for i in range(50):
        maxed.add_borrow(f"F-{i}", f"I-{i}")
    container.user_repo.save_user(maxed)

    with pytest.raises(UserNotEligibleError):
        container.circulation_svc.issue_physical_book("CC-DEL-02", "U-MAXED", actor_id="ADMIN-01")
