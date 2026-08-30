"""
GoF Strategy Pattern for Dynamic Fine Calculation
Formula: Fine = Base + Demand Factor + Popularity + User History Penalty
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from datetime import datetime


class FineCalculationStrategy(ABC):
    """
    Abstract Strategy in Strategy Pattern.
    """

    @abstractmethod
    def calculate_fine(
        self,
        overdue_days: int,
        book_metadata: Dict[str, Any],
        user_metadata: Dict[str, Any],
    ) -> float:
        """Calculates total fine amount for overdue book."""
        pass


class StandardFixedFineStrategy(FineCalculationStrategy):
    """
    Standard fixed daily fine (e.g., $1.00 / 10 INR per day).
    """

    def __init__(self, daily_rate: float = 10.0):
        self.daily_rate = daily_rate

    def calculate_fine(
        self,
        overdue_days: int,
        book_metadata: Dict[str, Any],
        user_metadata: Dict[str, Any],
    ) -> float:
        if overdue_days <= 0:
            return 0.0
        return round(overdue_days * self.daily_rate, 2)


class DynamicDemandFineStrategy(FineCalculationStrategy):
    """
    Dynamic fine scaling with book demand (reservation count) and book popularity rating.
    Example: Harry Potter in high exam season has 2x-3x higher daily late fees.
    """

    def __init__(self, base_rate: float = 10.0):
        self.base_rate = base_rate

    def calculate_fine(
        self,
        overdue_days: int,
        book_metadata: Dict[str, Any],
        user_metadata: Dict[str, Any],
    ) -> float:
        if overdue_days <= 0:
            return 0.0

        # Demand factor from waiting reservations
        pending_reservations = book_metadata.get("pending_reservations_count", 0)
        demand_multiplier = 1.0 + min(2.0, pending_reservations * 0.25)

        # Popularity factor from ratings (e.g. 5.0 rating = 1.2x)
        rating = book_metadata.get("rating", 4.0)
        popularity_multiplier = 1.0 + max(0.0, (rating - 3.0) * 0.1)

        # User past late return multiplier
        past_late_returns = user_metadata.get("past_late_returns_count", 0)
        history_penalty = 1.0 + min(1.5, past_late_returns * 0.1)

        total_daily_rate = self.base_rate * demand_multiplier * popularity_multiplier * history_penalty
        total_fine = overdue_days * total_daily_rate
        return round(total_fine, 2)


class TieredRiskFineStrategy(FineCalculationStrategy):
    """
    Tiered fine scaling with progressive rates for prolonged overdue periods.
    Days 1-3: Base rate
    Days 4-10: 1.5x Base rate
    Days 10+: 2.5x Base rate + Fixed replacement bond
    """

    def __init__(self, base_rate: float = 10.0):
        self.base_rate = base_rate

    def calculate_fine(
        self,
        overdue_days: int,
        book_metadata: Dict[str, Any],
        user_metadata: Dict[str, Any],
    ) -> float:
        if overdue_days <= 0:
            return 0.0

        fine = 0.0
        # Tier 1 (1 to 3 days)
        t1_days = min(3, overdue_days)
        fine += t1_days * self.base_rate

        # Tier 2 (4 to 10 days)
        if overdue_days > 3:
            t2_days = min(7, overdue_days - 3)
            fine += t2_days * (self.base_rate * 1.5)

        # Tier 3 (> 10 days)
        if overdue_days > 10:
            t3_days = overdue_days - 10
            fine += t3_days * (self.base_rate * 2.5)

        return round(fine, 2)
