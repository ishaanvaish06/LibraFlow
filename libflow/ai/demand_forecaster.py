"""
Demand & Peak Season Forecaster
Forecasts inventory contention using academic calendar cues and borrow frequency spikes.
"""
from typing import Dict, Any, List, Optional
from datetime import date
from collections import defaultdict


class DemandForecaster:
    """
    Predicts inventory contention and recommends proactive re-allocation.
    """

    def __init__(self):
        # isbn -> list of borrow date events
        self.borrow_history_dates: Dict[str, List[date]] = defaultdict(list)
        # (isbn, branch_id) -> list of borrow dates
        self.branch_borrow_dates: Dict[tuple[str, str], List[date]] = defaultdict(list)

    def record_checkout(self, isbn: str, checkout_date: date, branch_id: Optional[str] = None) -> None:
        self.borrow_history_dates[isbn].append(checkout_date)
        if branch_id:
            self.branch_borrow_dates[(isbn, branch_id)].append(checkout_date)

    def forecast_demand(self, isbn: str, reference_date: date) -> Dict[str, Any]:
        dates = self.borrow_history_dates.get(isbn, [])
        return self._calc_demand_metrics(isbn, dates, reference_date)

    def forecast_demand_at_branch(self, isbn: str, branch_id: str, reference_date: date) -> Dict[str, Any]:
        dates = self.branch_borrow_dates.get((isbn, branch_id), [])
        metrics = self._calc_demand_metrics(isbn, dates, reference_date)
        metrics["branch_id"] = branch_id
        return metrics

    def _calc_demand_metrics(self, isbn: str, dates: List[date], reference_date: date) -> Dict[str, Any]:
        recent_30_days = [d for d in dates if (reference_date - d).days <= 30]
        recent_7_days = [d for d in dates if (reference_date - d).days <= 7]

        velocity_30d = len(recent_30_days)
        velocity_7d = len(recent_7_days)

        # Estimate demand pressure
        if velocity_7d >= 5 or velocity_30d >= 15:
            demand_category = "SURGE"
            recommended_max_loan_days = 7  # Shorten borrow window during spikes
            fine_surge_multiplier = 1.5
        elif velocity_7d >= 2 or velocity_30d >= 6:
            demand_category = "MODERATE"
            recommended_max_loan_days = 14
            fine_surge_multiplier = 1.0
        else:
            demand_category = "NORMAL"
            recommended_max_loan_days = 21
            fine_surge_multiplier = 1.0

        return {
            "isbn": isbn,
            "demand_category": demand_category,
            "velocity_7d": velocity_7d,
            "velocity_30d": velocity_30d,
            "recommended_max_loan_days": recommended_max_loan_days,
            "fine_surge_multiplier": fine_surge_multiplier,
        }
