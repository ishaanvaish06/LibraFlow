"""
Pydantic Data Transfer Objects (DTOs) & Request Schemas
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any


class UserLoginRequest(BaseModel):
    user_id: str
    password: str


class UserRegisterRequest(BaseModel):
    user_id: str
    name: str
    email: str
    password: str
    role: str = "STUDENT"
    academic_year: Optional[int] = 1
    major: Optional[str] = "Computer Science"
    branch_id: Optional[str] = "BRANCH-DELHI"


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    role: str
    name: str


class BookRegisterRequest(BaseModel):
    format_type: str = "PHYSICAL"
    isbn: str
    title: str
    authors: List[str]
    category: str
    publication_year: int = 2024
    rating: float = 4.5
    difficulty_level: str = "Intermediate"
    keywords: List[str] = []
    description: str = ""
    weight_grams: Optional[int] = 500
    page_count: Optional[int] = 400
    download_url: Optional[str] = None
    file_size_mb: Optional[float] = 10.0


class AddCopyRequest(BaseModel):
    copy_id: str
    branch_id: str = "BRANCH-DELHI"
    shelf_location: str = "A1-01"
    price: float = 500.0


class IssueBookRequest(BaseModel):
    copy_id: str
    user_id: str
    loan_days: int = 14


class ReturnBookRequest(BaseModel):
    copy_id: str
    is_late: bool = False
    is_damaged: bool = False


class SmartAllocationRequest(BaseModel):
    isbn: str
    user_id: str


class ReserveBookRequest(BaseModel):
    isbn: str
    user_id: str


class PayFineRequest(BaseModel):
    user_id: str
    amount: float
    payment_method: str = "UPI"
    payment_metadata: Dict[str, Any] = {}


class BranchTransferRequest(BaseModel):
    copy_id: str
    dest_branch_id: str
    requested_by: Optional[str] = None