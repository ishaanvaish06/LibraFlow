"""
Intelligence Service: recommendations, risk scoring, and graph traversal.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from libflow.ai.demand_forecaster import DemandForecaster
from libflow.ai.risk_assessment import RiskAssessmentModel
from libflow.core.exceptions import UserNotFoundError
from libflow.dsa.graph import BookGraphEngine
from libflow.storage.repository import UserRepository


class IntelligenceService:
    def __init__(
        self,
        user_repo: UserRepository,
        recommender: Any,
        graph_engine: BookGraphEngine,
        forecaster: DemandForecaster,
        risk_model: Optional[RiskAssessmentModel] = None,
    ):
        self.user_repo = user_repo
        self.recommender = recommender
        self.graph_engine = graph_engine
        self.forecaster = forecaster
        self.risk_model = risk_model or RiskAssessmentModel.load()

    def get_recommendations_for_user(self, user_id: str, top_k: int = 5) -> List[Dict[str, Any]]:
        user = self.user_repo.get_user(user_id)
        if not user:
            raise UserNotFoundError(user_id)
        return self.recommender.recommend_for_user(user, top_k=top_k)

    def assess_user_theft_risk(self, user_id: str) -> Dict[str, Any]:
        user = self.user_repo.get_user(user_id)
        if not user:
            raise UserNotFoundError(user_id)
        return self.risk_model.evaluate_risk(user)

    def get_subject_learning_path(self, start_isbn: str, max_depth: int = 5) -> List[Dict[str, Any]]:
        return self.graph_engine.dfs_learning_path(start_isbn=start_isbn, max_depth=max_depth)

    def get_shortest_connection_path(self, from_isbn: str, to_isbn: str) -> Optional[List[Dict[str, Any]]]:
        return self.graph_engine.bfs_shortest_path(start_isbn=from_isbn, target_isbn=to_isbn)