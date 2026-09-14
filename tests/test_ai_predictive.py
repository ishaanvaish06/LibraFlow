"""
Unit tests for the ML and predictive pieces: hybrid recommendations, the
joblib-shipped late-return risk model, and demand forecasting.
"""

from __future__ import annotations

from datetime import date, timedelta

from libflow.ai.demand_forecaster import DemandForecaster
from libflow.ai.recommendation_engine import RecommendationEngine
from libflow.ai.risk_assessment import DEFAULT_MODEL_PATH, RiskAssessmentModel
from libflow.core.book import PhysicalBook
from libflow.core.user import Student


def test_hybrid_recommendation_engine():
    recommender = RecommendationEngine()

    os_book = PhysicalBook(isbn="ISBN-OS", title="Operating Systems", authors=["Silberschatz"],
                           category="Systems", publication_year=2018, rating=4.8,
                           keywords=["Kernel", "Processes"])
    cn_book = PhysicalBook(isbn="ISBN-CN", title="Computer Networks", authors=["Tanenbaum"],
                           category="Systems", publication_year=2015, rating=4.7,
                           keywords=["Protocols", "TCP/IP"])
    db_book = PhysicalBook(isbn="ISBN-DB", title="Database Internals", authors=["Petrov"],
                           category="Systems", publication_year=2019, rating=4.9,
                           keywords=["Storage", "B-Tree"])
    bio_book = PhysicalBook(isbn="ISBN-BIO", title="Molecular Biology", authors=["Watson"],
                            category="Biology", publication_year=2010, rating=4.0)

    for b in (os_book, cn_book, db_book, bio_book):
        recommender.register_book(b)

    recommender.graph_engine.add_relation("ISBN-OS", "ISBN-CN", weight=0.9)
    recommender.graph_engine.add_relation("ISBN-OS", "ISBN-DB", weight=0.85)

    student = Student(user_id="U-ISHAAN", name="Ishaan", email="ishaan@test.com")
    recommender.record_user_interaction("U-ISHAAN", "ISBN-OS", rating=5.0)

    recs = recommender.recommend_for_user(student, top_k=2)
    assert len(recs) == 2
    isbns = [r["isbn"] for r in recs]
    assert "ISBN-OS" not in isbns  # already read -> excluded
    assert "ISBN-CN" in isbns and "ISBN-DB" in isbns  # graph-related systems books rank
    assert "ISBN-BIO" not in isbns  # unrelated category ranks below


def test_risk_model_scores_known_inputs():
    model = RiskAssessmentModel.load()

    clean = Student(user_id="U-CLEAN", name="Clean", email="clean@test.com")
    clean.add_borrow("C-1", "ISBN-1")
    clean.record_return("C-1", is_late=False, is_damaged=False)

    risky = Student(user_id="U-RISKY", name="Risky", email="risky@test.com")
    for i in range(4):
        risky.add_borrow(f"C-{i}", f"ISBN-{i}")
        risky.record_return(f"C-{i}", is_late=True, is_damaged=(i == 0))
    risky.add_fine(150.0)

    low = model.evaluate_risk(clean)
    high = model.evaluate_risk(risky)

    assert low["risk_score_pct"] < 40.0
    assert low["risk_level"] == "LOW"
    assert low["require_security_deposit"] is False

    assert high["risk_score_pct"] >= 75.0
    assert high["risk_level"] == "HIGH"
    assert high["require_security_deposit"] is True
    assert high["recommended_deposit_amount"] > 0
    assert high["features"]["late_ratio"] > low["features"]["late_ratio"]


def test_shipped_model_file_loads_and_predicts_probability():
    assert DEFAULT_MODEL_PATH.exists()
    model = RiskAssessmentModel.load(DEFAULT_MODEL_PATH)

    user = Student(user_id="U-PROBE", name="Probe", email="probe@test.com")
    prob = model.predict_probability(model.features_from_user(user))

    assert 0.0 <= prob <= 1.0

    result = model.evaluate_risk(user)
    assert set(result.keys()) >= {
        "user_id", "risk_score_pct", "risk_level",
        "require_security_deposit", "recommended_deposit_amount", "factors",
    }
    assert result["user_id"] == "U-PROBE"


def test_demand_forecaster_peak_velocity():
    forecaster = DemandForecaster()
    isbn = "ISBN-EXAM-PREP"
    today = date.today()

    for day_offset in range(6):
        forecaster.record_checkout(isbn, today - timedelta(days=day_offset % 3))

    forecast = forecaster.forecast_demand(isbn, today)
    assert forecast["demand_category"] == "SURGE"
    assert forecast["recommended_max_loan_days"] == 7
    assert forecast["fine_surge_multiplier"] == 1.5