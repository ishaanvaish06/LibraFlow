"""
FastAPI REST Application & OpenAPI Interface for LibraFlow
Exposes REST endpoints for all 14 unique features with JWT Auth & RBAC Middleware.
"""
from fastapi import FastAPI, Depends, HTTPException, Query, status
from typing import List, Optional, Dict, Any

from libflow.core.enums import UserRole
from libflow.core.factory import UserFactory
from libflow.core.branch import LibraryBranch
from libflow.storage.database import LibraryDatabase
from libflow.storage.cache import DistributedCache
from libflow.storage.lock_manager import ConcurrencyLockManager
from libflow.dsa.trie import AutocompleteTrie
from libflow.dsa.inverted_index import InvertedIndex
from libflow.dsa.graph import BookGraphEngine
from libflow.patterns.reservation_queue import BookReservationQueueManager
from libflow.patterns.observer_notification import (
    NotificationDispatcher,
    EmailNotificationService,
    SmsNotificationService,
    InAppNotificationService,
)
from libflow.patterns.singleton_logger import AuditLogger
from libflow.ai.recommendation_engine import AIRecommendationEngine
from libflow.ai.demand_forecaster import DemandForecaster
from libflow.distributed.branch_manager import MultiBranchManager
from libflow.services import CatalogService, CirculationService, BillingService, IntelligenceService

from libflow.api.schemas import (
    UserLoginRequest,
    UserRegisterRequest,
    TokenResponse,
    BookRegisterRequest,
    AddCopyRequest,
    IssueBookRequest,
    ReturnBookRequest,
    SmartAllocationRequest,
    ReserveBookRequest,
    PayFineRequest,
    BranchTransferRequest,
)
from libflow.api.auth import (
    create_access_token,
    get_current_user_claims,
    require_role,
    require_permission,
)

# 1. Initialize Singletons & Core State
db = LibraryDatabase()
cache = DistributedCache(capacity=5000)
lock_mgr = ConcurrencyLockManager()
trie = AutocompleteTrie()
index = InvertedIndex()
graph = BookGraphEngine()
dispatcher = NotificationDispatcher()

email_svc = EmailNotificationService()
sms_svc = SmsNotificationService()
inapp_svc = InAppNotificationService()
dispatcher.subscribe(email_svc)
dispatcher.subscribe(sms_svc)
dispatcher.subscribe(inapp_svc)

reservation_mgr = BookReservationQueueManager(notification_dispatcher=dispatcher)
forecaster = DemandForecaster()
recommender = AIRecommendationEngine(graph_engine=graph)
branch_mgr = MultiBranchManager()
audit_logger = AuditLogger()

# Orchestrator Services
catalog_svc = CatalogService(db, trie, index, cache)
circulation_svc = CirculationService(db, lock_mgr, cache, reservation_mgr, dispatcher, forecaster)
billing_svc = BillingService(db, reservation_mgr, dispatcher)
intelligence_svc = IntelligenceService(db, recommender, graph, forecaster)

# Seed default branches
for b_id, name, city in [
    ("BRANCH-DELHI", "Delhi Central Campus", "Delhi"),
    ("BRANCH-MUMBAI", "Mumbai Tech Library", "Mumbai"),
    ("BRANCH-PUNE", "Pune Research Wing", "Pune"),
]:
    br = LibraryBranch(branch_id=b_id, name=name, city=city)
    db.save_branch(br)
    branch_mgr.register_branch(br)

# Seed default Admin
default_admin = UserFactory.create_user(role="ADMIN", user_id="ADMIN-01", name="System Admin", email="admin@libraflow.org")
db.save_user(default_admin)

# 2. FastAPI Application Configuration
app = FastAPI(
    title="LibraFlow: Smart AI-Powered Distributed Library Management System",
    description="Production-grade, design-pattern-driven Library Management Platform featuring OOP, DSA In-Memory Engines, AI Hybrid Recommendations, Dynamic Fines, Smart Allocation, and RBAC.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)


# ==========================================
# AUTH & USER ENDPOINTS
# ==========================================

@app.post("/api/v1/auth/register", tags=["Authentication"])
def register_user(req: UserRegisterRequest):
    if db.get_user(req.user_id):
        raise HTTPException(status_code=400, detail=f"User '{req.user_id}' already exists.")
    user = UserFactory.create_user(
        role=req.role,
        user_id=req.user_id,
        name=req.name,
        email=req.email,
        academic_year=req.academic_year or 1,
        major=req.major or "Computer Science",
        branch_id=req.branch_id or "BRANCH-DELHI",
    )
    db.save_user(user)
    return {"status": "SUCCESS", "user": user.to_dict()}


@app.post("/api/v1/auth/login", response_model=TokenResponse, tags=["Authentication"])
def login_user(req: UserLoginRequest):
    user = db.get_user(req.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    token = create_access_token(user)
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user_id=user.user_id,
        role=user.get_role().value,
        name=user.name,
    )


@app.get("/api/v1/auth/me", tags=["Authentication"])
def get_current_profile(claims: Dict[str, Any] = Depends(get_current_user_claims)):
    user_id = claims.get("sub")
    user = db.get_user(user_id)
    if not user:
        return claims
    return user.to_dict()


# ==========================================
# CATALOG & SEARCH ENDPOINTS (Features 3 & 5)
# ==========================================

@app.post("/api/v1/books", tags=["Catalog"])
def register_book(req: BookRegisterRequest, claims: Dict[str, Any] = Depends(require_permission("BOOK_MANAGE_INVENTORY"))):
    book = catalog_svc.register_book(
        format_type=req.format_type,
        actor_id=claims.get("sub", "ADMIN"),
        isbn=req.isbn,
        title=req.title,
        authors=req.authors,
        category=req.category,
        publication_year=req.publication_year,
        rating=req.rating,
        difficulty_level=req.difficulty_level,
        keywords=req.keywords,
        description=req.description,
        weight_grams=req.weight_grams or 500,
        page_count=req.page_count or 400,
        download_url=req.download_url or f"https://cdn.libraflow.org/{req.isbn}.pdf",
        file_size_mb=req.file_size_mb or 12.0,
    )
    recommender.register_book(book)
    return {"status": "SUCCESS", "book": book.to_dict()}


@app.post("/api/v1/books/{isbn}/copies", tags=["Catalog"])
def add_book_copy(isbn: str, req: AddCopyRequest, claims: Dict[str, Any] = Depends(require_permission("BOOK_MANAGE_INVENTORY"))):
    copy = catalog_svc.add_physical_copy(
        isbn=isbn,
        copy_id=req.copy_id,
        branch_id=req.branch_id,
        shelf_location=req.shelf_location,
        price=req.price,
        actor_id=claims.get("sub", "ADMIN"),
    )
    return {"status": "SUCCESS", "copy": copy.to_dict()}


@app.get("/api/v1/books/search", tags=["Search Engine"])
def search_books(
    q: str = Query("", description="Keyword search across title, author, description, and keywords"),
    category: Optional[str] = None,
    author: Optional[str] = None,
    min_rating: Optional[float] = None,
    only_available: bool = False,
):
    results = catalog_svc.search_books(
        query=q,
        category=category,
        author=author,
        min_rating=min_rating,
        only_available=only_available,
    )
    return {"query": q, "total_results": len(results), "results": results}


@app.get("/api/v1/books/autocomplete", tags=["Search Engine"])
def autocomplete(prefix: str = Query(..., min_length=1)):
    suggestions = catalog_svc.autocomplete(prefix=prefix)
    return {"prefix": prefix, "suggestions": suggestions}


@app.get("/api/v1/books/{isbn}", tags=["Catalog"])
def get_book_details(isbn: str):
    details = catalog_svc.get_book_details(isbn)
    if not details:
        raise HTTPException(status_code=404, detail="Book not found.")
    return details


# ==========================================
# CIRCULATION & SMART ALLOCATION (Features 2 & 6)
# ==========================================

@app.post("/api/v1/circulation/issue", tags=["Circulation"])
def issue_book(req: IssueBookRequest, claims: Dict[str, Any] = Depends(require_permission("BOOK_ISSUE"))):
    try:
        tx = circulation_svc.issue_physical_book(
            copy_id=req.copy_id,
            user_id=req.user_id,
            actor_id=claims.get("sub", "LIBRARIAN"),
            loan_days=req.loan_days,
        )
        recommender.record_user_interaction(req.user_id, tx["isbn"])
        return {"status": "SUCCESS", "transaction": tx}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/v1/circulation/return", tags=["Circulation"])
def return_book(req: ReturnBookRequest, claims: Dict[str, Any] = Depends(require_permission("BOOK_RETURN"))):
    try:
        res = circulation_svc.return_physical_book(
            copy_id=req.copy_id,
            actor_id=claims.get("sub", "LIBRARIAN"),
            is_late=req.is_late,
            is_damaged=req.is_damaged,
        )
        return {"status": "SUCCESS", "result": res}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/v1/circulation/smart-allocation/request", tags=["Smart Allocation Engine"])
def request_smart_allocation(req: SmartAllocationRequest):
    try:
        alloc_res = circulation_svc.request_smart_allocation(isbn=req.isbn, user_id=req.user_id)
        return {"status": "ENQUEUED_IN_PRIORITY_QUEUE", "allocation": alloc_res}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/v1/circulation/smart-allocation/drop/{isbn}", tags=["Smart Allocation Engine"])
def trigger_smart_allocation_drop(isbn: str, claims: Dict[str, Any] = Depends(require_permission("BOOK_ISSUE"))):
    result = circulation_svc.process_smart_allocation_drop(isbn)
    if not result:
        return {"status": "NO_DROP_MATCHED", "message": "No pending priority requests or available copies."}
    return {"status": "SUCCESS", "drop": result}


@app.post("/api/v1/circulation/reserve", tags=["Reservation Queue"])
def reserve_book(req: ReserveBookRequest):
    entry = reservation_mgr.reserve_book(isbn=req.isbn, user_id=req.user_id)
    return {"status": "SUCCESS", "reservation": entry.to_dict()}


# ==========================================
# AI & INTELLIGENCE (Features 1, 9 & 12)
# ==========================================

@app.get("/api/v1/intelligence/recommendations/{user_id}", tags=["AI Recommendation Engine"])
def get_recommendations(user_id: str, top_k: int = 5):
    try:
        recs = intelligence_svc.get_recommendations_for_user(user_id, top_k=top_k)
        return {"user_id": user_id, "recommendations": recs}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/api/v1/intelligence/risk-assessment/{user_id}", tags=["Theft & Risk Engine"])
def assess_user_theft_risk(user_id: str):
    try:
        assessment = intelligence_svc.assess_user_theft_risk(user_id)
        return {"status": "SUCCESS", "assessment": assessment}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/api/v1/intelligence/learning-path/{isbn}", tags=["Graph Engine"])
def get_learning_path(isbn: str, depth: int = 5):
    path = intelligence_svc.get_subject_learning_path(start_isbn=isbn, max_depth=depth)
    return {"start_isbn": isbn, "path": path}


@app.get("/api/v1/intelligence/shortest-path", tags=["Graph Engine"])
def get_shortest_path(from_isbn: str, to_isbn: str):
    path = intelligence_svc.get_shortest_connection_path(from_isbn=from_isbn, to_isbn=to_isbn)
    return {"from_isbn": from_isbn, "to_isbn": to_isbn, "path": path}


# ==========================================
# BILLING, DYNAMIC FINES & PAYMENTS (Features 4 & 13)
# ==========================================

@app.get("/api/v1/billing/fine-estimate", tags=["Billing & Fines"])
def estimate_fine(isbn: str, user_id: str, overdue_days: int = 1):
    fine = billing_svc.calculate_projected_fine(isbn, user_id, overdue_days)
    return {"isbn": isbn, "user_id": user_id, "overdue_days": overdue_days, "estimated_fine": fine}


@app.post("/api/v1/billing/pay", tags=["Billing & Fines"])
def pay_fine(req: PayFineRequest):
    try:
        res = billing_svc.pay_fine(
            user_id=req.user_id,
            amount=req.amount,
            payment_method=req.payment_method,
            payment_metadata=req.payment_metadata,
        )
        return {"status": "SUCCESS", "receipt": res}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ==========================================
# MULTI-BRANCH & TRANSFERS (Feature 7)
# ==========================================

@app.get("/api/v1/branches", tags=["Multi-Branch Network"])
def list_branches():
    return {"branches": branch_mgr.list_all_branches()}


@app.post("/api/v1/branches/transfer", tags=["Multi-Branch Network"])
def initiate_transfer(req: BranchTransferRequest, claims: Dict[str, Any] = Depends(require_permission("BOOK_TRANSFER_INITIATE"))):
    copy = db.get_copy(req.copy_id)
    if not copy:
        raise HTTPException(status_code=404, detail="Copy not found.")
    try:
        tx = branch_mgr.request_transfer(copy, req.dest_branch_id, req.requested_by)
        return {"status": "TRANSFER_INITIATED", "transfer": tx.to_dict()}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ==========================================
# NOTIFICATIONS & AUDIT LOGS (Features 10 & 14)
# ==========================================

@app.get("/api/v1/notifications/{user_id}", tags=["Notifications"])
def get_user_notifications(user_id: str):
    return {"user_id": user_id, "notifications": inapp_svc.get_user_notifications(user_id)}


@app.get("/api/v1/audit/logs", tags=["Audit & Security"])
def get_audit_logs(limit: int = 50, claims: Dict[str, Any] = Depends(require_role(["ADMIN"]))):
    return {"logs": audit_logger.get_logs(limit=limit)}


@app.get("/api/v1/system/cache-stats", tags=["Distributed Cache"])
def get_cache_stats():
    return {"cache_stats": cache.get_stats()}
