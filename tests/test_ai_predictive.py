"""
Unit Tests for Phase 4: AI/ML & Predictive Intelligence Engines
"""
from datetime import date, timedelta
from libflow.core.book import PhysicalBook
from libflow.core.user import Student
from libflow.dsa.graph import BookGraphEngine
from libflow.ai.recommendation_engine import AIRecommendationEngine
from libflow.ai.risk_assessment import TheftRiskPredictor
from libflow.ai.demand_forecaster import DemandForecaster


def test_ai_hybrid_recommendation_engine():
    graph = BookGraphEngine()
    recommender = AIRecommendationEngine(graph_engine=graph)

    # Register catalogue
    b_os = PhysicalBook(isbn="ISBN-OS", title="Operating Systems", authors=["Silberschatz"], category="Systems", publication_year=2018, rating=4.8, keywords=["Kernel", "Processes"])
    b_cn = PhysicalBook(isbn="ISBN-CN", title="Computer Networks", authors=["Tanenbaum"], category="Systems", publication_year=2015, rating=4.7, keywords=["Protocols", "TCP/IP"])
    b_db = PhysicalBook(isbn="ISBN-DB", title="Database Internals", authors=["Petrov"], category="Systems", publication_year=2019, rating=4.9, keywords=["Storage", "B-Tree"])
    b_bio = PhysicalBook(isbn="ISBN-BIO", title="Molecular Biology", authors=["Watson"], category="Biology", publication_year=2010, rating=4.0)

    for b in [b_os, b_cn, b_db, b_bio]:
        recommender.register_book(b)

    # Establish graph relations
    graph.add_relation("ISBN-OS", "ISBN-CN", weight=0.9)
    graph.add_relation("ISBN-OS", "ISBN-DB", weight=0.85)

    # User Ishaan borrows Operating Systems
    student = Student(user_id="U-ISHAAN", name="Ishaan", email="ishaan@test.com")
    recommender.record_user_interaction("U-ISHAAN", "ISBN-OS", rating=5.0)

    # Generate recommendations
    recs = recommender.recommend_for_user(student, top_k=3)
    assert len(recs) >= 2
    rec_isbns = [r["isbn"] for r in recs]

    # Both related systems books should rank at top, biology book at bottom/excluded
    assert "ISBN-CN" in rec_isbns or "ISBN-DB" in rec_isbns
    assert "ISBN-OS" not in rec_isbns  # Already read


def test_theft_and_lost_risk_prediction():
    # Low-risk user
    clean_user = Student(user_id="U-CLEAN", name="Clean Student", email="clean@test.com")
    clean_user.add_borrow("C-1", "ISBN-1")
    clean_user.record_return("C-1", is_late=False, is_damaged=False)

    risk_clean = TheftRiskPredictor.evaluate_risk(clean_user)
    assert risk_clean["risk_level"] == "LOW"
    assert risk_clean["require_security_deposit"] is False

    # High-risk user (frequent late returns, damaged item, unpaid fines)
    risky_user = Student(user_id="U-RISKY", name="Risky Borrower", email="risky@test.com")
    for i in range(4):
        risky_user.add_borrow(f"C-{i}", f"ISBN-{i}")
        risky_user.record_return(f"C-{i}", is_late=True, is_damaged=(i == 0))
    risky_user.add_fine(150.0)

    risk_high = TheftRiskPredictor.evaluate_risk(risky_user)
    assert risk_high["risk_score_pct"] >= 75.0
    assert risk_high["risk_level"] == "HIGH"
    assert risk_high["require_security_deposit"] is True
    assert risk_high["recommended_deposit_amount"] > 0


def test_demand_forecaster_peak_velocity():
    forecaster = DemandForecaster()
    isbn = "ISBN-EXAM-PREP"
    today = date.today()

    # Simulate spike of 6 borrows in last 3 days
    for day_offset in range(6):
        forecaster.record_checkout(isbn, today - timedelta(days=day_offset % 3))

    forecast = forecaster.forecast_demand(isbn, today)
    assert forecast["demand_category"] == "SURGE"
    assert forecast["recommended_max_loan_days"] == 7
    assert forecast["fine_surge_multiplier"] == 1.5
