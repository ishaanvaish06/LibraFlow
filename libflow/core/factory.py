"""
Factory Pattern Implementation for Book & User Instantiation
"""
from typing import Dict, Any, List, Optional
from datetime import date

from libflow.core.enums import BookFormat, UserRole
from libflow.core.book import Book, PhysicalBook, EBook, AudioBook, BookCopy
from libflow.core.user import User, Student, Faculty, Librarian, Admin
from libflow.core.passwords import hash_password


class BookFactory:
    """
    Factory class providing a unified interface to instantiate polymorphic Book objects.
    """

    @staticmethod
    def create_book(format_type: BookFormat | str, **kwargs: Any) -> Book:
        if isinstance(format_type, str):
            format_type = BookFormat(format_type.upper())

        if format_type == BookFormat.PHYSICAL:
            return PhysicalBook(
                isbn=kwargs["isbn"],
                title=kwargs["title"],
                authors=kwargs.get("authors", ["Unknown"]),
                category=kwargs.get("category", "General"),
                publication_year=kwargs.get("publication_year", 2024),
                publisher=kwargs.get("publisher", "Standard Press"),
                description=kwargs.get("description", ""),
                rating=kwargs.get("rating", 4.0),
                difficulty_level=kwargs.get("difficulty_level", "Intermediate"),
                keywords=kwargs.get("keywords", []),
                weight_grams=kwargs.get("weight_grams", 500),
                page_count=kwargs.get("page_count", 400),
            )
        elif format_type == BookFormat.EBOOK:
            return EBook(
                isbn=kwargs["isbn"],
                title=kwargs["title"],
                authors=kwargs.get("authors", ["Unknown"]),
                category=kwargs.get("category", "General"),
                publication_year=kwargs.get("publication_year", 2024),
                download_url=kwargs.get("download_url", f"https://cdn.libraflow.org/ebooks/{kwargs['isbn']}.pdf"),
                file_size_mb=kwargs.get("file_size_mb", 15.5),
                file_format=kwargs.get("file_format", "PDF"),
                drm_protected=kwargs.get("drm_protected", True),
                max_concurrent_downloads=kwargs.get("max_concurrent_downloads", 100),
                publisher=kwargs.get("publisher", "Standard Press"),
                description=kwargs.get("description", ""),
                rating=kwargs.get("rating", 4.0),
                difficulty_level=kwargs.get("difficulty_level", "Intermediate"),
                keywords=kwargs.get("keywords", []),
            )
        elif format_type == BookFormat.AUDIOBOOK:
            return AudioBook(
                isbn=kwargs["isbn"],
                title=kwargs["title"],
                authors=kwargs.get("authors", ["Unknown"]),
                category=kwargs.get("category", "General"),
                publication_year=kwargs.get("publication_year", 2024),
                stream_url=kwargs.get("stream_url", f"https://audio.libraflow.org/{kwargs['isbn']}.m4a"),
                duration_minutes=kwargs.get("duration_minutes", 360),
                narrator=kwargs.get("narrator", "Studio Voice"),
                publisher=kwargs.get("publisher", "Standard Press"),
                description=kwargs.get("description", ""),
                rating=kwargs.get("rating", 4.0),
                difficulty_level=kwargs.get("difficulty_level", "Intermediate"),
                keywords=kwargs.get("keywords", []),
            )
        else:
            raise ValueError(f"Unsupported book format: {format_type}")


class UserFactory:
    """
    Factory class providing a unified interface to instantiate polymorphic User objects.
    """

    @staticmethod
    def create_user(role: UserRole | str, **kwargs: Any) -> User:
        if isinstance(role, str):
            role = UserRole(role.upper())

        user_id = kwargs["user_id"]
        name = kwargs["name"]
        email = kwargs["email"]
        branch_id = kwargs.get("branch_id", "BRANCH-CENTRAL")

        # Accept a raw password (preferred) or a pre-hashed value.
        if "password" in kwargs:
            pwd = hash_password(kwargs["password"])
        else:
            pwd = kwargs.get("password_hash", "default_hash")

        if role == UserRole.STUDENT:
            exam_date_val = kwargs.get("exam_date")
            if isinstance(exam_date_val, str):
                exam_date_val = date.fromisoformat(exam_date_val)
            return Student(
                user_id=user_id,
                name=name,
                email=email,
                academic_year=kwargs.get("academic_year", 1),
                major=kwargs.get("major", "Computer Science"),
                exam_date=exam_date_val,
                password_hash=pwd,
                branch_id=branch_id,
            )
        elif role == UserRole.FACULTY:
            return Faculty(
                user_id=user_id,
                name=name,
                email=email,
                department=kwargs.get("department", "Computer Science & Engineering"),
                password_hash=pwd,
                branch_id=branch_id,
            )
        elif role == UserRole.LIBRARIAN:
            return Librarian(
                user_id=user_id,
                name=name,
                email=email,
                staff_code=kwargs.get("staff_code", f"LIB-{user_id}"),
                password_hash=pwd,
                branch_id=branch_id,
            )
        elif role == UserRole.ADMIN:
            return Admin(
                user_id=user_id,
                name=name,
                email=email,
                password_hash=pwd,
                branch_id=branch_id,
            )
        else:
            raise ValueError(f"Unsupported user role: {role}")
