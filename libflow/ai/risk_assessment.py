"""
Theft & Lost Book Risk Assessment Engine
Predicts probability of unreturned or damaged inventory based on historical behavioral signals.
"""
from typing import Dict, Any, List
from libflow.core.user import User


class TheftRiskPredictor:
    """
    Evaluates user borrowing history to generate a predictive Risk Score (0% to 100%).
    Triggers automated security deposit policies for high-risk profiles.
    """

    HIGH_RISK_THRESHOLD: float = 75.0  # Percentage
    MODERATE_RISK_THRESHOLD: float = 40.0

    @classmethod
    def evaluate_risk(cls, user: User) -> Dict[str, Any]:
        history = user.borrow_history
        total_borrows = len(history)

        # Baseline risk for new users
        if total_borrows == 0:
            risk_score = 15.0  # Moderate baseline for new accounts
            return {
                "user_id": user.user_id,
                "user_name": user.name,
                "risk_score_pct": risk_score,
                "risk_level": "LOW",
                "require_security_deposit": False,
                "recommended_deposit_amount": 0.0,
                "factors": ["New user account with no prior violation history."],
            }

        late_returns = len([b for b in history if b.get("is_late") is True])
        damaged_returns = len([b for b in history if b.get("is_damaged") is True])
        
        # 1. Late return ratio (weight: 40%)
        late_ratio = late_returns / total_borrows
        late_score = min(40.0, late_ratio * 40.0)

        # 2. Damaged / unreturned history (weight: 35%)
        damaged_score = min(35.0, damaged_returns * 25.0)

        # 3. Unpaid fines penalty (weight: 15%)
        fine_score = min(15.0, (user.unpaid_fines_balance / 200.0) * 15.0)

        # 4. Currently unreturned active items (weight: 10%)
        active_borrows = len(user.active_borrowed_copy_ids)
        active_score = min(10.0, (active_borrows / user.max_borrow_limit) * 10.0)

        total_risk_pct = round(late_score + damaged_score + fine_score + active_score, 1)
        total_risk_pct = min(100.0, max(0.0, total_risk_pct))

        factors = []
        if late_returns > 0:
            factors.append(f"{late_returns} past late returns ({round(late_ratio * 100, 1)}% of total).")
        if damaged_returns > 0:
            factors.append(f"{damaged_returns} previously damaged/lost items.")
        if user.unpaid_fines_balance > 0:
            factors.append(f"Outstanding fines balance of ${user.unpaid_fines_balance:.2f}.")

        # Risk Classification & Action
        if total_risk_pct >= cls.HIGH_RISK_THRESHOLD:
            level = "HIGH"
            require_deposit = True
            deposit_amount = 1000.0  # Standard security deposit
        elif total_risk_pct >= cls.MODERATE_RISK_THRESHOLD:
            level = "MODERATE"
            require_deposit = False
            deposit_amount = 300.0
        else:
            level = "LOW"
            require_deposit = False
            deposit_amount = 0.0

        return {
            "user_id": user.user_id,
            "user_name": user.name,
            "risk_score_pct": total_risk_pct,
            "risk_level": level,
            "require_security_deposit": require_deposit,
            "recommended_deposit_amount": deposit_amount,
            "factors": factors or ["Clean track record."],
        }
