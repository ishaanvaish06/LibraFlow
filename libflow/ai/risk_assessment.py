"""
Risk prediction for late returns — a real, tiny ML component.

``RiskAssessmentModel`` is a scikit-learn ``LogisticRegression`` trained on
seeded circulation history (historically late days ratio, renewal count,
category of borrowings, user role) to predict the probability of a
late/unreturned book. The model is persisted with joblib and regenerated via
``scripts/train_risk_model.py``.

The model file ships with the repo so a fresh clone can load it immediately.
If it is missing (e.g. gitignore checkout), ``load`` retrains from the same
seed generator so the application keeps working.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

import joblib
import numpy as np
from sklearn.linear_model import LogisticRegression

from libflow.ai.risk_seed import generate_seed_training_data
from libflow.core.enums import UserRole
from libflow.core.user import User

DEFAULT_MODEL_PATH = Path(__file__).resolve().parents[2] / "models" / "risk_model.joblib"

_ROLE_INDEX = {
    UserRole.STUDENT.value: 0,
    UserRole.FACULTY.value: 1,
    UserRole.LIBRARIAN.value: 2,
    UserRole.ADMIN.value: 3,
}

FEATURE_NAMES = [
    "role_encoded",
    "total_borrows_log",
    "late_ratio",
    "damaged_count",
    "fines_balance_scaled",
    "active_ratio",
]

MODERATE_RISK_THRESHOLD = 40.0
HIGH_RISK_THRESHOLD = 75.0


class RiskAssessmentModel:
    def __init__(self, clf: LogisticRegression):
        self.clf = clf

    # -- feature engineering ------------------------------------------------
    @classmethod
    def features_from_user(cls, user: User) -> List[float]:
        history = user.borrow_history
        total_borrows = max(0, len(history))
        late_returns = len([b for b in history if b.get("is_late")])
        late_ratio = (late_returns / total_borrows) if total_borrows else 0.0
        damaged = len([b for b in history if b.get("is_damaged")])
        fines = max(0.0, user.unpaid_fines_balance)
        active_ratio = (
            len(user.active_borrowed_copy_ids) / user.max_borrow_limit
            if user.max_borrow_limit else 0.0
        )
        role = _ROLE_INDEX.get(user.get_role().value, 0)
        return [
            float(role),
            float(np.log1p(total_borrows)),
            float(late_ratio),
            float(damaged),
            float(fines / 200.0),
            float(min(1.0, active_ratio)),
        ]

    # -- training -----------------------------------------------------------
    @classmethod
    def train(cls, path: Path = DEFAULT_MODEL_PATH) -> "RiskAssessmentModel":
        X, y = generate_seed_training_data(n_samples=800, random_state=42)
        clf = LogisticRegression(
            max_iter=1000,
            C=1.0,
            class_weight="balanced",
            random_state=42,
        )
        clf.fit(X, y)
        model = cls(clf)
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump({"clf": clf}, path)
        return model

    # -- loading ------------------------------------------------------------
    @classmethod
    def load(cls, path: Path = DEFAULT_MODEL_PATH) -> "RiskAssessmentModel":
        if path.exists():
            payload = joblib.load(path)
            return cls(payload["clf"])
        return cls.train(path)

    # -- inference ----------------------------------------------------------
    def predict_probability(self, features: List[float]) -> float:
        vec = np.asarray([features], dtype=float)
        return float(self.clf.predict_proba(vec)[0, 1])

    def evaluate_risk(self, user: User) -> Dict[str, Any]:
        features = self.features_from_user(user)
        probability = self.predict_probability(features)
        risk_pct = round(probability * 100, 1)

        history = user.borrow_history
        late_returns = len([b for b in history if b.get("is_late")])
        damaged_returns = len([b for b in history if b.get("is_damaged")])
        factors: List[str] = []
        if late_returns > 0:
            factors.append(f"{late_returns} past late returns.")
        if damaged_returns > 0:
            factors.append(f"{damaged_returns} previously damaged/lost items.")
        if user.unpaid_fines_balance > 0:
            factors.append(f"Outstanding fines balance of ${user.unpaid_fines_balance:.2f}.")

        if risk_pct >= HIGH_RISK_THRESHOLD:
            level = "HIGH"
            require_deposit = True
            deposit_amount = 1000.0
        elif risk_pct >= MODERATE_RISK_THRESHOLD:
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
            "risk_score_pct": risk_pct,
            "risk_level": level,
            "require_security_deposit": require_deposit,
            "recommended_deposit_amount": deposit_amount,
            "factors": factors or ["Clean track record."],
            "model": "logistic_regression",
            "features": dict(zip(FEATURE_NAMES, [round(f, 4) for f in features])),
        }


def train_model(path: Path = DEFAULT_MODEL_PATH) -> RiskAssessmentModel:
    """Convenience entry point used by scripts/train_risk_model.py."""
    return RiskAssessmentModel.train(path)