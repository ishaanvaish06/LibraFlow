"""Catalog, search and autocomplete routes."""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Query

from libflow.api.auth import require_permission
from libflow.api.dependencies import get_catalog_service, get_recommender
from libflow.api.schemas import AddCopyRequest, BookRegisterRequest
from libflow.core.exceptions import BookNotFoundError
from libflow.services.catalog_service import CatalogService

router = APIRouter(prefix="/api/v1/books", tags=["Catalog"])


@router.post("")
def register_book(
    req: BookRegisterRequest,
    catalog_svc: CatalogService = Depends(get_catalog_service),
    recommender=Depends(get_recommender),
    claims: Dict[str, Any] = Depends(require_permission("BOOK_MANAGE_INVENTORY")),
) -> Dict[str, Any]:
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


@router.post("/{isbn}/copies")
def add_book_copy(
    isbn: str,
    req: AddCopyRequest,
    catalog_svc: CatalogService = Depends(get_catalog_service),
    claims: Dict[str, Any] = Depends(require_permission("BOOK_MANAGE_INVENTORY")),
) -> Dict[str, Any]:
    copy = catalog_svc.add_physical_copy(
        isbn=isbn,
        copy_id=req.copy_id,
        branch_id=req.branch_id,
        shelf_location=req.shelf_location,
        price=req.price,
        actor_id=claims.get("sub", "ADMIN"),
    )
    return {"status": "SUCCESS", "copy": copy.to_dict()}


@router.get("/search")
def search_books(
    q: str = Query("", description="Keyword search across title, author, description, and keywords"),
    category: Optional[str] = None,
    author: Optional[str] = None,
    min_rating: Optional[float] = None,
    only_available: bool = False,
    limit: int = Query(20, ge=1, le=100, description="Maximum number of books to return"),
    offset: int = Query(0, ge=0, description="Offset into search results"),
    catalog_svc: CatalogService = Depends(get_catalog_service),
    claims: Dict[str, Any] = Depends(require_permission("BOOK_SEARCH")),
) -> Dict[str, Any]:
    all_results = catalog_svc.search_books(
        query=q,
        category=category,
        author=author,
        min_rating=min_rating,
        only_available=only_available,
    )
    paginated_results = all_results[offset : offset + limit]
    return {
        "query": q,
        "total_results": len(all_results),
        "limit": limit,
        "offset": offset,
        "results": paginated_results,
    }


@router.get("/autocomplete", tags=["Search Engine"])
def autocomplete(
    prefix: str = Query(..., min_length=1),
    catalog_svc: CatalogService = Depends(get_catalog_service),
    claims: Dict[str, Any] = Depends(require_permission("BOOK_SEARCH")),
) -> Dict[str, Any]:
    suggestions = catalog_svc.autocomplete(prefix=prefix)
    return {"prefix": prefix, "suggestions": suggestions}


@router.get("/{isbn}")
def get_book_details(
    isbn: str,
    catalog_svc: CatalogService = Depends(get_catalog_service),
    claims: Dict[str, Any] = Depends(require_permission("BOOK_SEARCH")),
) -> Dict[str, Any]:
    details = catalog_svc.get_book_details(isbn)
    if not details:
        raise BookNotFoundError(isbn)
    return details


@router.get("/public/search", tags=["Public Search"])
def public_search_books(
    q: str = Query("", description="Keyword search across title, author, description, and keywords"),
    category: Optional[str] = None,
    author: Optional[str] = None,
    min_rating: Optional[float] = None,
    only_available: bool = False,
    limit: int = Query(20, ge=1, le=100, description="Maximum number of books to return"),
    offset: int = Query(0, ge=0, description="Offset into search results"),
    catalog_svc: CatalogService = Depends(get_catalog_service),
) -> Dict[str, Any]:
    """Explicitly unauthenticated catalog search."""
    all_results = catalog_svc.search_books(
        query=q,
        category=category,
        author=author,
        min_rating=min_rating,
        only_available=only_available,
    )
    paginated_results = all_results[offset : offset + limit]
    return {
        "query": q,
        "total_results": len(all_results),
        "limit": limit,
        "offset": offset,
        "results": paginated_results,
    }