"""
Multi-Branch Network Manager & Inter-Branch Transfer State Machine
Supports geographically distributed campus branches (e.g. Delhi, Mumbai, Pune).
"""
from typing import Dict, List, Optional, Any
import uuid
from datetime import datetime

from libflow.core.enums import TransferStatus
from libflow.core.branch import LibraryBranch
from libflow.core.book import PhysicalBook, BookCopy


class InterBranchTransferRequest:
    def __init__(
        self,
        transfer_id: str,
        copy_id: str,
        isbn: str,
        source_branch_id: str,
        dest_branch_id: str,
        requested_by: str,
    ):
        self.transfer_id = transfer_id
        self.copy_id = copy_id
        self.isbn = isbn
        self.source_branch_id = source_branch_id
        self.dest_branch_id = dest_branch_id
        self.requested_by = requested_by
        self.status = TransferStatus.REQUESTED
        self.created_at = datetime.now()
        self.completed_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "transfer_id": self.transfer_id,
            "copy_id": self.copy_id,
            "isbn": self.isbn,
            "source_branch_id": self.source_branch_id,
            "dest_branch_id": self.dest_branch_id,
            "requested_by": self.requested_by,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


class MultiBranchManager:
    """
    Coordinates multi-branch inventory, inter-branch requests, and physical copy transit.
    """

    def __init__(self):
        self.branches: Dict[str, LibraryBranch] = {}
        self.transfers: Dict[str, InterBranchTransferRequest] = {}

    def register_branch(self, branch: LibraryBranch) -> None:
        self.branches[branch.branch_id] = branch

    def get_branch(self, branch_id: str) -> Optional[LibraryBranch]:
        return self.branches.get(branch_id)

    def request_transfer(
        self,
        copy: BookCopy,
        dest_branch_id: str,
        requested_by: str,
    ) -> InterBranchTransferRequest:
        if dest_branch_id not in self.branches:
            raise ValueError(f"Destination branch '{dest_branch_id}' does not exist.")
        if copy.branch_id == dest_branch_id:
            raise ValueError(f"Copy is already located at branch '{dest_branch_id}'.")

        # Initiate transfer on copy
        copy.start_transfer(dest_branch_id)

        tx_id = f"TRF-{uuid.uuid4().hex[:8].upper()}"
        req = InterBranchTransferRequest(
            transfer_id=tx_id,
            copy_id=copy.copy_id,
            isbn=copy.book_isbn,
            source_branch_id=copy.branch_id,
            dest_branch_id=dest_branch_id,
            requested_by=requested_by,
        )
        req.status = TransferStatus.IN_TRANSIT
        self.transfers[tx_id] = req
        return req

    def complete_transfer(self, transfer_id: str, copy: BookCopy) -> InterBranchTransferRequest:
        req = self.transfers.get(transfer_id)
        if not req:
            raise ValueError(f"Transfer request '{transfer_id}' not found.")
        if req.status != TransferStatus.IN_TRANSIT:
            raise ValueError(f"Transfer '{transfer_id}' is not in transit.")

        copy.complete_transfer()
        req.status = TransferStatus.COMPLETED
        req.completed_at = datetime.now()
        return req

    def list_all_branches(self) -> List[Dict[str, Any]]:
        return [b.to_dict() for b in self.branches.values()]
