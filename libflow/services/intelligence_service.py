"""
Intelligence Service: Unified Facade for Recommendations, Risk Scoring, and Graph Traversal
"""
from typing import Dict, Any, List, Optional
from libflow.storage.database import LibraryDatabase
from libflow.ai.recommendation_engine import AIRecommendationEngine
from libflow.ai.risk_assessment import TheftRiskPredictor
from libflow.ai.demand_forecaster import DemandForecaster
from libflow.dsa.graph import BookGraphEngine


class IntelligenceService:
    def __init__(
        self,
        db: LibraryDatabase,
        recommender: AIRecommendationEngine,
        graph_engine: BookGraphEngine,
        forecaster: DemandForecaster,
    ):
        self.db = db
        self.recommender = recommender
        self.graph_engine = graph_engine
        self.forecaster = forecaster

    def get_recommendations_for_user(self, user_id: str, top_k: int = 5) -> List[Dict[str, Any]]:
        user = self.db.get_user(user_id)
        if not user:
            raise ValueError(f"User '{user_id}' not found.")
        return self.recommender.recommend_for_user(user, top_k=top_k)

    def assess_user_theft_risk(self, user_id: str) -> Dict[str, Any]:
        user = self.db.get_user(user_id)
        if not user:
            raise ValueError(f"User '{user_id}' not found.")
        return TheftRiskPredictor.evaluate_risk(user)

    def get_subject_learning_path(self, start_isbn: str, max_depth: int = 5) -> List[Dict[str, Any]]:
        return self.graph_engine.dfs_learning_path(start_isbn=start_isbn, max_depth=max_depth)

    def get_shortest_connection_path(self, from_isbn: str, to_isbn: str) -> Optional[List[Dict[str, Any]]]:
        return self.graph_engine.bfs_shortest_path(start_isbn=from_isbn, target_isbn=to_isbn)
