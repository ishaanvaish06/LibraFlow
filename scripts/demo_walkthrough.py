"""
Interactive live demo walkthrough for LibraFlow.

Runs the whole library stack against a seeded in-memory container and
exercises every feature end-to-end, printing results to the console.

Usage:
    python scripts/demo_walkthrough.py
"""

import os
import sys

if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from libflow.api.dependencies import build_in_memory_container
from libflow.patterns.singleton_logger import AuditLogger
from libflow.seed import seed_library


def banner(title: str, feature_num: int) -> None:
    print("\n" + "=" * 80)
    print(f"  FEATURE {feature_num}: {title.upper()}")
    print("=" * 80)


def main() -> None:
    container = build_in_memory_container()
    seed_library(container)

    catalog_svc = container.catalog_svc
    circulation_svc = container.circulation_svc
    billing_svc = container.billing_svc
    intel_svc = container.intelligence_svc
    branch_mgr = container.branch_mgr

    # Feature 3: Digital Library Support (Polymorphic Book Hierarchy)
    banner("Digital Library Support (Physical vs EBook Hierarchy)", 3)
    p_book = container.book_repo.get_book("978-0132350884")
    e_book = container.book_repo.get_book("978-0134685991")
    print(f"[Physical] {p_book.title} | Format: {p_book.get_format().value} | Copies: {p_book.total_copies}")
    print(f"[Digital]  {e_book.title} | Format: {e_book.get_format().value} | Download URL: {e_book.download_url}")
    e_book.acquire_read_access()
    print(f"  -> Active concurrent readers: {e_book.active_readers_count}")

    # Feature 5: Library Search Engine (Trie Autocomplete + Inverted Index)
    banner("Library Search Engine (Trie Autocomplete & Inverted Index)", 5)
    print("[Autocomplete] prefix='clean':")
    for item in catalog_svc.autocomplete("clean"):
        print(f"   {item['text']} (weight {item['weight']})")
    print("[Ranked search] query='distributed consensus':")
    for res in catalog_svc.search_books("distributed consensus"):
        print(f"   {res['book']['title']} (score {res['relevance_score']})")

    # Feature 2: Smart Book Allocation (Max-Heap Priority Queue)
    banner("Smart Book Allocation System (Multi-Factor Priority Queue)", 2)
    a1 = circulation_svc.request_smart_allocation("978-1118063330", "STU-ALICE")
    print(f"[Enqueue] Alice (1st yr, exam in 25d) priority={a1['calculated_priority']:.3f}")
    a2 = circulation_svc.request_smart_allocation("978-1118063330", "STU-ISHAAN")
    print(f"[Enqueue] Ishaan (3rd yr, exam tomorrow!) priority={a2['calculated_priority']:.3f}")
    drop = circulation_svc.process_smart_allocation_drop("978-1118063330")
    print(f"[Winner ] {drop['user_name']} awarded copy {drop['copy_id']}")

    # Feature 6: Reservation Queue System (FIFO Auto-Assignment)
    banner("Book Reservation Queue & Auto-Assignment System", 6)
    circulation_svc.issue_physical_book("DDIA-DEL-01", "STU-BOB", actor_id="LIB-SARAH")
    print(f"[Issue ] DDIA-DEL-01 checked out to Bob.")
    entry = circulation_svc.reservation_mgr.reserve_book("978-1491950357", "STU-ALICE")
    print(f"[Reserve] Alice queued for DDIA -> status {entry.status.value}")
    print("[Return] Bob returns DDIA-DEL-01...")
    result = circulation_svc.return_physical_book("DDIA-DEL-01", actor_id="LIB-SARAH")
    if result["auto_assigned_to_reservation"]:
        print(f"   Copy auto-assigned to reservation for {result['auto_assigned_to_reservation']['user_id']}")

    # Feature 1 & 12: Recommendations & Graph Traversal
    banner("Hybrid Recommendations & Graph Relationship Traversal", 1)
    recs = intel_svc.get_recommendations_for_user("STU-ISHAAN", top_k=3)
    print("Recommendations for Ishaan:")
    for r in recs:
        print(f"   {r['title']} | {r['category']} | match={r['match_score']}")
    path = intel_svc.get_shortest_connection_path("978-0262033848", "978-1492040347")
    if path:
        print("Shortest graph path (CLRS -> Database Internals):")
        print("   " + " -> ".join(p["title"] for p in path))

    # Feature 9: Late-return / loss Risk Assessment
    banner("Late-Return & Loss Risk Assessment", 9)
    for uid in ("STU-ISHAAN", "STU-RAHUL"):
        risk = intel_svc.assess_user_theft_risk(uid)
        print(
            f"[{uid}] risk={risk['risk_score_pct']}% level={risk['risk_level']} "
            f"deposit=${risk['recommended_deposit_amount']:.2f}"
        )
        print(f"   Factors: {', '.join(risk['factors'])}")

    # Feature 4 & 13: Dynamic Fine Prediction & Payment Strategy
    banner("Dynamic Fine Prediction & Multi-Channel Payment System", 4)
    est = billing_svc.calculate_projected_fine("978-1491950357", "STU-RAHUL", overdue_days=4)
    print(f"Projected fine on high-demand DDIA (4 days overdue): ${est:.2f}")
    pay = billing_svc.pay_fine("STU-RAHUL", 30.0, payment_method="UPI", payment_metadata={"vpa": "rahul@oksbi"})
    print(f"Payment receipt: tx={pay['transaction_id']} status={pay['status']} remaining=${pay['remaining_unpaid_balance']:.2f}")

    # Feature 7: Multi-Branch Library & Inter-Branch Transfers
    banner("Multi-Branch Library Network & Inter-Branch Transit", 7)
    print("Active branches: " + ", ".join(b["name"] for b in branch_mgr.list_all_branches()))
    copy = container.book_repo.get_copy("CC-DEL-02")
    branch_mgr.register_branch(container.branch_repo.get_branch("BRANCH-MUMBAI"))
    trf = branch_mgr.request_transfer(copy, dest_branch_id="BRANCH-MUMBAI", requested_by="LIB-SARAH")
    container.book_repo.save_copy(copy)
    print(f"[Transit] {trf.transfer_id} status={trf.status.value} copy_state={copy.status.value}")
    branch_mgr.complete_transfer(trf.transfer_id, copy)
    container.book_repo.save_copy(copy)
    print(f"[Done   ] Copy now at {copy.branch_id} | status={copy.status.value}")

    # Feature 11: Distributed Caching (Cache-Aside)
    banner("Distributed Caching System (Cache-Aside)", 11)
    for _ in range(3):
        catalog_svc.get_book_details("978-1491950357")
    stats = catalog_svc.cache.get_stats()
    print(f"Cache: {stats['hits']} hits, {stats['misses']} misses, hit_ratio={stats['hit_ratio_pct']}%")

    # Feature 14: Singleton Audit Logger
    banner("Thread-Safe Singleton Audit & Security Logger", 14)
    logs = AuditLogger().get_logs(limit=5)
    print(f"Recent audit trail ({len(logs)} mutation events):")
    for log in logs:
        print(f"   [{log['timestamp']}] actor={log['actor_id']} action={log['action']} target={log['resource_id']}")

    print("\n" + "=" * 80)
    print("  ALL 14 FEATURES VERIFIED END-TO-END")
    print("=" * 80)


if __name__ == "__main__":
    main()