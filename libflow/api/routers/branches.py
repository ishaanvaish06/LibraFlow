"""Branch listing and inter-branch transfer routes."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends

from libflow.api.auth import require_permission
from libflow.api.dependencies import get_book_repository, get_branch_manager, get_branch_repository
from libflow.api.schemas import BranchTransferRequest
from libflow.core.exceptions import BranchNotFoundError, CopyNotFoundError
from libflow.distributed.branch_manager import MultiBranchManager
from libflow.storage.repository import BookRepository, BranchRepository

router = APIRouter(prefix="/api/v1/branches", tags=["Branches"])


@router.get("")
def list_all_branches(
    branch_repo: BranchRepository = Depends(get_branch_repository),
) -> Dict[str, Any]:
    branches = branch_repo.list_branches()
    return {"branches": [b.to_dict() for b in branches], "total_branches": len(branches)}


@router.post("/transfer")
def transfer_copy(
    req: BranchTransferRequest,
    branch_mgr: MultiBranchManager = Depends(get_branch_manager),
    branch_repo: BranchRepository = Depends(get_branch_repository),
    book_repo: BookRepository = Depends(get_book_repository),
    claims: Dict[str, Any] = Depends(require_permission("BOOK_TRANSFER_INITIATE")),
) -> Dict[str, Any]:
    dest = branch_repo.get_branch(req.dest_branch_id)
    if not dest:
        raise BranchNotFoundError(req.dest_branch_id)
    branch_mgr.register_branch(dest)

    copy = book_repo.get_copy(req.copy_id)
    if not copy:
        raise CopyNotFoundError(req.copy_id)
    if copy.branch_id not in branch_mgr.branches:
        # Source branch not yet registered locally — pull it from the repo.
        source = branch_repo.get_branch(copy.branch_id)
        if source:
            branch_mgr.register_branch(source)

    requested_by = req.requested_by or claims.get("sub", "")
    transfer = branch_mgr.request_transfer(copy, req.dest_branch_id, requested_by)
    book_repo.save_copy(copy)
    return {"status": "SUCCESS", "transfer": transfer.to_dict()}
