"""
Cross-Branch Inventory Rebalancing Engine.
Constrained multi-branch optimization for proactive inventory distribution.
Solves demand-supply imbalances across branches using graph traversal,
priority queues, and closed-loop outcome precision tracking.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import heapq
import math
from typing import Any, Dict, List, Optional

from libflow.ai.demand_forecaster import DemandForecaster
from libflow.core.book import BookCopy, PhysicalBook
from libflow.core.branch import LibraryBranch
from libflow.core.enums import BookStatus, TransferStatus
from libflow.distributed.branch_manager import MultiBranchManager
from libflow.distributed.event_bus import EventBus
from libflow.storage.repository import BookRepository, BranchRepository


@dataclass(order=True)
class TransferCandidate:
    priority: float  # Inverted for max-heap behavior
    isbn: str = field(compare=False)
    copy_id: str = field(compare=False)
    source_branch_id: str = field(compare=False)
    dest_branch_id: str = field(compare=False)
    predicted_gain: float = field(compare=False)
    transit_cost: float = field(compare=False)


class CrossBranchRebalancingEngine:
    """
    Autonomous Rebalancing Engine:
    Monitors demand velocity, optimizes inventory allocation across branch network,
    dispatches autonomous transfers via event bus, and tracks borrower checkout precision.
    """

    def __init__(
        self,
        book_repo: BookRepository,
        branch_repo: BranchRepository,
        branch_mgr: MultiBranchManager,
        forecaster: DemandForecaster,
        event_bus: Optional[EventBus] = None,
        max_transfers_per_branch: int = 3,
    ):
        self.book_repo = book_repo
        self.branch_repo = branch_repo
        self.branch_mgr = branch_mgr
        self.forecaster = forecaster
        self.event_bus = event_bus
        self.max_transfers_per_branch = max_transfers_per_branch

        # Autonomous transfer tracking: transfer_id -> metadata
        self.transfers_tracked: Dict[str, Dict[str, Any]] = {}
        # copy_id -> transfer_id (for fast lookup during checkout)
        self.copy_to_transfer: Dict[str, str] = {}

    def _branch_distance(self, b1: LibraryBranch, b2: LibraryBranch) -> float:
        """Haversine or Euclidean distance in km between two branches."""
        d_lat = b1.latitude - b2.latitude
        d_lon = b1.longitude - b2.longitude
        return round(math.hypot(d_lat, d_lon) * 111.0, 1)

    def calculate_rebalancing_plan(self, reference_date: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """
        Runs the optimization pass:
        1. Identifies destination branches with high/surge demand and 0 or low available stock.
        2. Identifies source branches with surplus copies (>1 available).
        3. Scores candidate transfers = (demand_pressure * 10) - (distance_km * 0.05).
        4. Selects highest-utility candidate moves up to branch transit constraints.
        """
        ref_date = reference_date.date() if reference_date else datetime.now().date()
        branches = {b.branch_id: b for b in self.branch_repo.list_branches()}
        all_books = self.book_repo.list_books()

        # Count in-flight transfers per branch to respect backpressure
        in_flight_dest: Dict[str, int] = {bid: 0 for bid in branches}
        for trf in self.branch_mgr.transfers.values():
            if trf.status == TransferStatus.IN_TRANSIT:
                in_flight_dest[trf.dest_branch_id] = in_flight_dest.get(trf.dest_branch_id, 0) + 1

        candidates_heap: List[TransferCandidate] = []

        for book in all_books:
            if not isinstance(book, PhysicalBook):
                continue
            isbn = book.isbn
            copies_by_branch: Dict[str, List[BookCopy]] = {bid: [] for bid in branches}
            for copy in book.copies.values():
                if copy.branch_id in copies_by_branch and copy.status == BookStatus.AVAILABLE:
                    copies_by_branch[copy.branch_id].append(copy)

            # Check each branch demand
            for dest_id, dest_branch in branches.items():
                if in_flight_dest.get(dest_id, 0) >= self.max_transfers_per_branch:
                    continue

                dest_forecast = self.forecaster.forecast_demand_at_branch(isbn, dest_id, ref_date)
                dest_avail = len(copies_by_branch[dest_id])

                # Needs rebalancing if SURGE or (MODERATE with 0 available copies)
                needs_stock = (
                    dest_forecast["demand_category"] == "SURGE" and dest_avail <= 1
                ) or (dest_forecast["demand_category"] == "MODERATE" and dest_avail == 0)

                if not needs_stock:
                    continue

                demand_weight = 250.0 if dest_forecast["demand_category"] == "SURGE" else 150.0

                # Look for source branch with surplus
                for source_id, source_branch in branches.items():
                    if source_id == dest_id:
                        continue
                    surplus_copies = copies_by_branch[source_id]
                    # Source must have at least 1 spare copy to give without stripping itself
                    if len(surplus_copies) < 2:
                        continue

                    dist_km = self._branch_distance(source_branch, dest_branch)
                    transit_cost = dist_km * 0.05
                    utility = demand_weight - transit_cost
                    if utility <= 0:
                        continue

                    candidate = TransferCandidate(
                        priority=-utility,
                        isbn=isbn,
                        copy_id=surplus_copies[0].copy_id,
                        source_branch_id=source_id,
                        dest_branch_id=dest_id,
                        predicted_gain=demand_weight,
                        transit_cost=transit_cost,
                    )
                    heapq.heappush(candidates_heap, candidate)

        # Build plan respecting constraints
        plan: List[Dict[str, Any]] = []
        allocated_copies: set[str] = set()

        while candidates_heap:
            cand = heapq.heappop(candidates_heap)
            if cand.copy_id in allocated_copies:
                continue
            if in_flight_dest.get(cand.dest_branch_id, 0) >= self.max_transfers_per_branch:
                continue

            allocated_copies.add(cand.copy_id)
            in_flight_dest[cand.dest_branch_id] = in_flight_dest.get(cand.dest_branch_id, 0) + 1

            plan.append({
                "isbn": cand.isbn,
                "copy_id": cand.copy_id,
                "source_branch_id": cand.source_branch_id,
                "dest_branch_id": cand.dest_branch_id,
                "utility_score": round(-cand.priority, 2),
                "transit_cost": round(cand.transit_cost, 2),
            })

        return plan

    def execute_rebalancing_plan(self, plan: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
        """
        Executes proposed transfers autonomously, dispatching events to event bus.
        """
        if plan is None:
            plan = self.calculate_rebalancing_plan()

        executed: List[Dict[str, Any]] = []

        for item in plan:
            copy = self.book_repo.get_copy(item["copy_id"])
            if not copy or copy.status != BookStatus.AVAILABLE:
                continue

            # Drive state machine
            transfer_req = self.branch_mgr.request_transfer(
                copy=copy,
                dest_branch_id=item["dest_branch_id"],
                requested_by="AUTONOMOUS_REBALANCER",
            )
            self.book_repo.save_copy(copy)

            # Record tracking metadata for outcome precision loop
            self.transfers_tracked[transfer_req.transfer_id] = {
                "transfer_id": transfer_req.transfer_id,
                "copy_id": copy.copy_id,
                "isbn": copy.book_isbn,
                "source_branch_id": transfer_req.source_branch_id,
                "dest_branch_id": transfer_req.dest_branch_id,
                "requested_at": datetime.now(timezone.utc).isoformat(),
                "arrived_at": None,
                "borrowed_at": None,
                "status": "IN_TRANSIT",
            }
            self.copy_to_transfer[copy.copy_id] = transfer_req.transfer_id

            # Emit event to bus
            if self.event_bus:
                self.event_bus.publish(
                    "transfer.requested",
                    {
                        "transfer_id": transfer_req.transfer_id,
                        "copy_id": copy.copy_id,
                        "isbn": copy.book_isbn,
                        "source_branch_id": transfer_req.source_branch_id,
                        "dest_branch_id": transfer_req.dest_branch_id,
                        "requested_by": "AUTONOMOUS_REBALANCER",
                    },
                )

            executed.append(transfer_req.to_dict())

        return executed

    def complete_transfer(self, transfer_id: str) -> Optional[Dict[str, Any]]:
        """Completes arrival of an in-transit copy at destination branch."""
        trf = self.branch_mgr.transfers.get(transfer_id)
        if not trf:
            return None
        copy = self.book_repo.get_copy(trf.copy_id)
        if not copy:
            return None

        self.branch_mgr.complete_transfer(transfer_id, copy)
        self.book_repo.save_copy(copy)

        if transfer_id in self.transfers_tracked:
            self.transfers_tracked[transfer_id]["status"] = "ARRIVED"
            self.transfers_tracked[transfer_id]["arrived_at"] = datetime.now(timezone.utc).isoformat()

        if self.event_bus:
            self.event_bus.publish(
                "transfer.completed",
                {"transfer_id": transfer_id, "copy_id": copy.copy_id, "dest_branch_id": trf.dest_branch_id},
            )

        return trf.to_dict()

    def record_checkout_hook(self, copy_id: str, branch_id: str) -> bool:
        """
        Feedback loop check:
        Called when a book is checked out. If this copy was autonomously moved to this branch
        and borrowed within 7 days of arrival, record a confirmed positive prediction.
        """
        trf_id = self.copy_to_transfer.get(copy_id)
        if not trf_id:
            return False

        meta = self.transfers_tracked.get(trf_id)
        if not meta or meta.get("dest_branch_id") != branch_id:
            return False

        arrived_iso = meta.get("arrived_at")
        if arrived_iso and not meta.get("borrowed_at"):
            try:
                arrived_time = datetime.fromisoformat(arrived_iso)
                # If checked out within 7 days of arrival
                if datetime.now(timezone.utc) - arrived_time <= timedelta(days=7):
                    meta["borrowed_at"] = datetime.now(timezone.utc).isoformat()
                    meta["status"] = "CHECKED_OUT"
                    return True
            except Exception:
                pass
        return False

    def get_outcome_metrics(self) -> Dict[str, Any]:
        """Calculates closed-loop precision metrics for autonomous transfers."""
        total = len(self.transfers_tracked)
        arrived = sum(1 for t in self.transfers_tracked.values() if t.get("arrived_at") is not None)
        borrowed = sum(1 for t in self.transfers_tracked.values() if t.get("borrowed_at") is not None)
        in_transit = sum(1 for t in self.transfers_tracked.values() if t.get("status") == "IN_TRANSIT")

        precision = round((borrowed / arrived) * 100, 1) if arrived > 0 else 0.0

        return {
            "total_autonomous_transfers": total,
            "arrived_at_destination": arrived,
            "checked_out_within_7d": borrowed,
            "in_transit": in_transit,
            "precision_rate_pct": precision,
            "tracked_transfers": list(self.transfers_tracked.values())[-10:],
        }
