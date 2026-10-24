"""
Unit and Integration Tests for EmoCare Assessment Engine.

Covers:
- Exact validated questionnaire content and ordering for PHQ-9 and GAD-7.
- Response scales and timeframes.
- Deterministic scoring across all boundary thresholds.
- Input validation (incomplete arrays, invalid ranges, non-integers).
- Dedicated safety pathway (PHQ-9 Item 9 triggers and emergency escalation).
- Symptom breakdown accuracy (zero hallucinated symptoms).
- Contextual follow-up processing and mood elevation screening.
- Database persistence and historical retrieval for progress tracking.
- Separation of deterministic scoring from LLM outputs.
"""
import pytest
from datetime import datetime, timezone

from backend.app.assessment import (
    score_phq9,
    score_gad7,
    process_assessment,
    build_symptom_breakdown,
    process_follow_up_data,
    evaluate_safety_pathway,
    build_recommended_steps,
    PHQ9_QUESTIONS,
    GAD7_QUESTIONS,
    RESPONSE_SCALE,
    PHQ9_TIMEFRAME,
    GAD7_TIMEFRAME,
    FUNCTIONAL_DIFFICULTY_QUESTION,
    FUNCTIONAL_DIFFICULTY_OPTIONS,
    CLINICAL_DISCLAIMER,
)
from backend.app.db import (
    init_db,
    save_assessment_attempt,
    get_user_assessment_history,
)


# ── 1. Questionnaire Content & Ordering ──────────────────────────────────

def test_phq9_exact_content_and_length():
    """Verify PHQ-9 contains exactly 9 authoritative validated questions in exact order."""
    assert len(PHQ9_QUESTIONS) == 9

    expected_phq9 = [
        "Little interest or pleasure in doing things",
        "Feeling down, depressed, or hopeless",
        "Trouble falling or staying asleep, or sleeping too much",
        "Feeling tired or having little energy",
        "Poor appetite or overeating",
        "Feeling bad about yourself — or that you are a failure or have let yourself or your family down",
        "Trouble concentrating on things, such as reading the newspaper or watching television",
        "Moving or speaking so slowly that other people could have noticed? Or the opposite — being so fidgety or restless that you have been moving around a lot more than usual",
        "Thoughts that you would be better off dead or of hurting yourself in some way",
    ]
    assert PHQ9_QUESTIONS == expected_phq9
    assert "last 2 weeks" in PHQ9_TIMEFRAME.lower()


def test_gad7_exact_content_and_length():
    """Verify GAD-7 contains exactly 7 authoritative validated questions in exact order."""
    assert len(GAD7_QUESTIONS) == 7

    expected_gad7 = [
        "Feeling nervous, anxious, or on edge",
        "Not being able to stop or control worrying",
        "Worrying too much about different things",
        "Trouble relaxing",
        "Being so restless that it is hard to sit still",
        "Becoming easily annoyed or irritable",
        "Feeling afraid, as if something awful might happen",
    ]
    assert GAD7_QUESTIONS == expected_gad7
    assert "last 2 weeks" in GAD7_TIMEFRAME.lower()


def test_standard_response_scale():
    """Verify standard 4-point Likert scale (0-3) with exact labels."""
    assert len(RESPONSE_SCALE) == 4
    assert RESPONSE_SCALE[0] == {"value": 0, "label": "Not at all"}
    assert RESPONSE_SCALE[1] == {"value": 1, "label": "Several days"}
    assert RESPONSE_SCALE[2] == {"value": 2, "label": "More than half the days"}
    assert RESPONSE_SCALE[3] == {"value": 3, "label": "Nearly every day"}


# ── 2. PHQ-9 Scoring Boundaries & Validation ─────────────────────────────

def test_phq9_scoring_boundaries():
    """
    Test deterministic PHQ-9 boundaries:
      0-4: Minimal
      5-9: Mild
      10-14: Moderate
      15-19: Moderately severe
      20-27: Severe
    """
    # Score 0 (Minimal, Low risk)
    score, sev, risk, _, safety, q9 = score_phq9([0] * 9)
    assert score == 0 and sev == "Minimal" and risk == "Low" and not safety and q9 == 0

    # Score 4 (Minimal boundary, Low risk)
    score, sev, risk, _, safety, _ = score_phq9([1, 1, 1, 1, 0, 0, 0, 0, 0])
    assert score == 4 and sev == "Minimal" and risk == "Low" and not safety

    # Score 5 (Mild boundary, Low risk)
    score, sev, risk, _, safety, _ = score_phq9([1, 1, 1, 1, 1, 0, 0, 0, 0])
    assert score == 5 and sev == "Mild" and risk == "Low" and not safety

    # Score 9 (Mild boundary, Low risk)
    score, sev, risk, _, safety, _ = score_phq9([2, 2, 2, 2, 1, 0, 0, 0, 0])
    assert score == 9 and sev == "Mild" and risk == "Low" and not safety

    # Score 10 (Moderate boundary, Moderate risk)
    score, sev, risk, _, safety, _ = score_phq9([2, 2, 2, 2, 2, 0, 0, 0, 0])
    assert score == 10 and sev == "Moderate" and risk == "Moderate" and not safety

    # Score 14 (Moderate boundary, Moderate risk)
    score, sev, risk, _, safety, _ = score_phq9([2, 2, 2, 2, 2, 2, 2, 0, 0])
    assert score == 14 and sev == "Moderate" and risk == "Moderate" and not safety

    # Score 15 (Moderately severe boundary, High risk)
    score, sev, risk, _, safety, _ = score_phq9([3, 3, 3, 3, 3, 0, 0, 0, 0])
    assert score == 15 and sev == "Moderately severe" and risk == "High" and not safety

    # Score 19 (Moderately severe boundary, High risk)
    score, sev, risk, _, safety, _ = score_phq9([3, 3, 3, 3, 3, 2, 2, 0, 0])
    assert score == 19 and sev == "Moderately severe" and risk == "High" and not safety

    # Score 20 (Severe boundary, High risk)
    score, sev, risk, _, safety, _ = score_phq9([3, 3, 3, 3, 3, 3, 2, 0, 0])
    assert score == 20 and sev == "Severe" and risk == "High" and not safety

    # Score 27 (Max score, Severe, High risk, safety alert because Q9=3)
    score, sev, risk, _, safety, q9 = score_phq9([3] * 9)
    assert score == 27 and sev == "Severe" and risk == "High" and safety and q9 == 3


def test_phq9_input_validation():
    """Verify PHQ-9 rejects incomplete responses and invalid values."""
    # Incomplete (less than 9 items)
    with pytest.raises(ValueError, match="PHQ-9 requires exactly 9 responses"):
        score_phq9([1, 2, 3])

    with pytest.raises(ValueError, match="PHQ-9 requires exactly 9 responses"):
        score_phq9([0] * 8)

    # Too many items
    with pytest.raises(ValueError, match="PHQ-9 requires exactly 9 responses"):
        score_phq9([0] * 10)

    # Invalid range (> 3)
    with pytest.raises(ValueError, match="integers between 0 and 3"):
        score_phq9([0, 0, 0, 0, 0, 0, 0, 0, 4])

    # Negative integer
    with pytest.raises(ValueError, match="integers between 0 and 3"):
        score_phq9([0, 0, 0, 0, 0, 0, 0, 0, -1])

    # None / non-integer
    with pytest.raises(ValueError, match="integers between 0 and 3"):
        score_phq9([0, 0, 0, 0, None, 0, 0, 0, 0])  # type: ignore


# ── 3. GAD-7 Scoring Boundaries & Validation ─────────────────────────────

def test_gad7_scoring_boundaries():
    """
    Test deterministic GAD-7 boundaries:
      0-4: Minimal
      5-9: Mild
      10-14: Moderate
      15-21: Severe
    """
    # Score 0 (Minimal, Low risk)
    score, sev, risk, _ = score_gad7([0] * 7)
    assert score == 0 and sev == "Minimal" and risk == "Low"

    # Score 4 (Minimal boundary, Low risk)
    score, sev, risk, _ = score_gad7([1, 1, 1, 1, 0, 0, 0])
    assert score == 4 and sev == "Minimal" and risk == "Low"

    # Score 5 (Mild boundary, Low risk)
    score, sev, risk, _ = score_gad7([1, 1, 1, 1, 1, 0, 0])
    assert score == 5 and sev == "Mild" and risk == "Low"

    # Score 9 (Mild boundary, Low risk)
    score, sev, risk, _ = score_gad7([2, 2, 2, 2, 1, 0, 0])
    assert score == 9 and sev == "Mild" and risk == "Low"

    # Score 10 (Moderate boundary, Moderate risk)
    score, sev, risk, _ = score_gad7([2, 2, 2, 2, 2, 0, 0])
    assert score == 10 and sev == "Moderate" and risk == "Moderate"

    # Score 14 (Moderate boundary, Moderate risk)
    score, sev, risk, _ = score_gad7([2] * 7)
    assert score == 14 and sev == "Moderate" and risk == "Moderate"

    # Score 15 (Severe boundary, High risk)
    score, sev, risk, _ = score_gad7([3, 3, 3, 3, 3, 0, 0])
    assert score == 15 and sev == "Severe" and risk == "High"

    # Score 21 (Max score, Severe, High risk)
    score, sev, risk, _ = score_gad7([3] * 7)
    assert score == 21 and sev == "Severe" and risk == "High"


def test_gad7_input_validation():
    """Verify GAD-7 rejects incomplete responses and invalid values."""
    with pytest.raises(ValueError, match="GAD-7 requires exactly 7 responses"):
        score_gad7([1, 2, 3])

    with pytest.raises(ValueError, match="GAD-7 requires exactly 7 responses"):
        score_gad7([0] * 6)

    with pytest.raises(ValueError, match="integers between 0 and 3"):
        score_gad7([0, 0, 0, 0, 0, 0, 5])

    with pytest.raises(ValueError, match="integers between 0 and 3"):
        score_gad7([0, 0, 0, 0, 0, 0, -2])


# ── 4. Dedicated Clinical Safety Pathway ─────────────────────────────────

def test_phq9_item9_safety_escalation():
    """
    CRITICAL: Any positive score on Question 9 (self-harm thoughts)
    must trigger the safety alert, even when the overall score is Minimal.
    """
    # Total score 1 (Q9 = 1, all others 0) -> Severity Minimal, but risk escalated to Moderate
    score, sev, risk, _, safety, q9 = score_phq9([0, 0, 0, 0, 0, 0, 0, 0, 1])
    assert score == 1
    assert sev == "Minimal"
    assert safety is True
    assert q9 == 1
    assert risk == "Moderate"  # Escalated from Low!

    # Q9 = 2, total score 2 -> Escalated to High risk
    score, sev, risk, _, safety, q9 = score_phq9([0, 0, 0, 0, 0, 0, 0, 0, 2])
    assert score == 2
    assert sev == "Minimal"
    assert safety is True
    assert q9 == 2
    assert risk == "High"  # Escalated to High due to Q9 >= 2

    # Q9 = 0, total score 4 -> No safety alert
    score, sev, risk, _, safety, q9 = score_phq9([1, 1, 1, 1, 0, 0, 0, 0, 0])
    assert score == 4
    assert safety is False
    assert q9 == 0
    assert risk == "Low"


def test_evaluate_safety_pathway_with_disclosure():
    """Verify safety pathway handles structured safety disclosure and emergency escalation."""
    # Active emergency disclosure
    disclosure = {
        "active_thoughts": True,
        "immediate_intent": True,
        "safe_person_nearby": False,
    }
    details = evaluate_safety_pathway(
        test_type="phq9",
        responses=[0, 0, 0, 0, 0, 0, 0, 0, 1],
        safety_disclosure=disclosure,
    )
    assert details["safety_alert"] is True
    assert details["active_emergency"] is True
    assert details["urgency_level"] == "CRITICAL"
    assert len(details["crisis_resources"]) > 0


# ── 5. Symptom Pattern Breakdown (Zero Hallucinated Symptoms) ────────────

def test_symptom_breakdown_phq9():
    """Verify reported items match user's exact selections without hallucination."""
    responses = [2, 0, 1, 0, 3, 0, 0, 0, 0]
    breakdown = build_symptom_breakdown("phq9", responses)

    assert breakdown["reported_count"] == 3
    assert breakdown["unreported_count"] == 6

    reported_item_numbers = [item["item_number"] for item in breakdown["reported_items"]]
    assert reported_item_numbers == [1, 3, 5]

    # Q1 score 2
    assert breakdown["reported_items"][0]["score"] == 2
    assert breakdown["reported_items"][0]["frequency_label"] == "More than half the days"

    # Q5 score 3
    assert breakdown["reported_items"][2]["score"] == 3
    assert breakdown["reported_items"][2]["frequency_label"] == "Nearly every day"

    # Check domains
    domains = breakdown["domains"]
    assert "core_mood" in domains
    assert "somatic_energy" in domains
    assert "cognitive_psychomotor" in domains
    assert "safety_ideation" in domains
    assert domains["safety_ideation"]["endorsed"] is False


def test_symptom_breakdown_gad7():
    """Verify GAD-7 domain breakdown."""
    responses = [3, 2, 0, 1, 0, 0, 0]
    breakdown = build_symptom_breakdown("gad7", responses)

    assert breakdown["reported_count"] == 3
    assert breakdown["unreported_count"] == 4
    assert breakdown["domains"]["core_worry"]["score"] == 5  # Q1(3) + Q2(2) + Q3(0)


# ── 6. Contextual Follow-Up & Adaptive Processing ────────────────────────

def test_process_follow_up_data():
    """Verify follow-up processing captures functional difficulty and elevation screen."""
    data = {
        "functional_difficulty": "Very difficult",
        "impact_areas": ["Work or academic studies", "Sleep quality & feeling rested"],
        "duration": "1 to 6 months",
        "trajectory": "Getting more difficult",
        "prior_history": "I have experienced similar episodes in the past",
        "elevation_screen": "Yes, once or twice in the past",
        "life_factors": ["Academic or workplace stress"],
        "coping_goals": ["Connecting with a licensed therapist or doctor"],
    }
    summary = process_follow_up_data(data)
    assert summary["completed"] is True
    assert summary["functional_difficulty"] == "Very difficult"
    assert summary["elevation_screen_endorsed"] is True
    assert summary["elevation_screen_note"] is not None
    assert "bipolar" in summary["elevation_screen_note"].lower() or "mood" in summary["elevation_screen_note"].lower()


def test_follow_up_empty():
    """Verify empty follow-up data handles gracefully without crashing."""
    summary = process_follow_up_data(None)
    assert summary["completed"] is False
    assert summary["functional_difficulty"] == "Not specified"
    assert summary["elevation_screen_endorsed"] is False


# ── 7. Recommended Next Steps Engine ─────────────────────────────────────

def test_build_recommended_steps():
    """Verify tier-appropriate recommended steps include crisis contacts when safety is triggered."""
    follow_up = {"elevation_screen_endorsed": True}

    # Severe with active emergency
    steps_severe = build_recommended_steps(
        test_type="phq9",
        severity_band="Severe",
        risk_tier="High",
        safety_alert=True,
        active_emergency=True,
        follow_up_summary=follow_up,
    )
    assert any("988" in s for s in steps_severe)
    assert any("Professional consultation" in s for s in steps_severe)

    # Minimal without safety alert
    steps_minimal = build_recommended_steps(
        test_type="phq9",
        severity_band="Minimal",
        risk_tier="Low",
        safety_alert=False,
        active_emergency=False,
        follow_up_summary={"elevation_screen_endorsed": False},
    )
    assert not any("988" in s for s in steps_minimal)
    assert any("Track trends" in s for s in steps_minimal)


# ── 8. Full Assessment Processing & Separation from LLM ──────────────────

def test_process_assessment_full():
    """
    Verify complete synchronous assessment processing:
    Deterministic scores must remain exact and independent of LLM or text generation.
    """
    user_id = "test_user_integration_123"
    responses = [2, 1, 2, 1, 0, 1, 0, 0, 0]  # Total: 7 (Mild, Low risk)

    res = process_assessment(
        user_id=user_id,
        test_type="phq9",
        responses=responses,
        follow_up_data={"functional_difficulty": "Somewhat difficult"},
    )

    assert res["user_id"] == user_id
    assert res["test_type"] == "phq9"
    assert res["total_score"] == 7
    assert res["max_score"] == 27
    assert res["severity_band"] == "Mild"
    assert res["risk_tier"] == "Low"
    assert res["safety_alert"] is False
    assert res["symptom_breakdown"]["reported_count"] == 5
    assert res["follow_up_summary"]["functional_difficulty"] == "Somewhat difficult"
    assert "clinical diagnosis" in res["clinical_disclaimer"].lower()
    assert res["id"] is not None


# ── 9. Database Persistence & History Retrieval ──────────────────────────

def test_db_persistence_and_history():
    """Verify saving assessment attempts and retrieving history."""
    init_db()
    user_id = f"test_hist_user_{int(datetime.now(timezone.utc).timestamp())}"

    # Attempt 1: GAD-7 (Score: 10, Moderate)
    save_assessment_attempt(
        user_id=user_id,
        test_type="gad7",
        responses=[2, 2, 2, 2, 2, 0, 0],
        total_score=10,
        severity_band="Moderate",
        risk_tier="Moderate",
        safety_flag=False,
        q9_score=0,
    )

    # Attempt 2: PHQ-9 (Score: 16, Moderately severe, with safety alert)
    save_assessment_attempt(
        user_id=user_id,
        test_type="phq9",
        responses=[2, 2, 2, 2, 2, 2, 2, 1, 1],
        total_score=16,
        severity_band="Moderately severe",
        risk_tier="High",
        safety_flag=True,
        q9_score=1,
    )

    history = get_user_assessment_history(user_id=user_id, limit=5)
    assert len(history) == 2

    # Newest attempt is first (Attempt 2)
    latest = history[0]
    assert latest["user_id"] == user_id
    assert latest["test_type"] == "phq9"
    assert latest["total_score"] == 16
    assert latest["severity_band"] == "Moderately severe"
    assert latest["safety_flag"] is True
    assert latest["q9_score"] == 1

    # Oldest attempt is second (Attempt 1)
    earlier = history[1]
    assert earlier["test_type"] == "gad7"
    assert earlier["total_score"] == 10
    assert earlier["severity_band"] == "Moderate"
    assert earlier["safety_flag"] is False


# ── 10. FastAPI Route Integration Tests ──────────────────────────────────

def test_fastapi_assessment_routes():
    """Verify HTTP endpoints for questions, submission, and history via TestClient."""
    from fastapi.testclient import TestClient
    from backend.app.main import app

    client = TestClient(app)

    # 1. Questions Endpoint
    res_phq = client.get("/api/assessment/questions/phq9")
    assert res_phq.status_code == 200
    data_phq = res_phq.json()
    assert len(data_phq["questions"]) == 9
    assert len(data_phq["scale"]) == 4

    res_gad = client.get("/api/assessment/questions/gad7")
    assert res_gad.status_code == 200
    data_gad = res_gad.json()
    assert len(data_gad["questions"]) == 7

    res_invalid = client.get("/api/assessment/questions/invalid_test")
    assert res_invalid.status_code == 400

    # 2. Submission Endpoint
    test_user = f"test_api_user_{int(datetime.now(timezone.utc).timestamp())}"
    payload = {
        "user_id": test_user,
        "test_type": "phq9",
        "responses": [1, 2, 1, 0, 1, 0, 0, 0, 0],
        "follow_up_data": {
            "functional_difficulty": "Somewhat difficult",
            "duration": "2 weeks to 1 month",
        },
    }
    submit_res = client.post("/api/assessment/submit", json=payload)
    assert submit_res.status_code == 200
    submit_data = submit_res.json()
    assert submit_data["total_score"] == 5
    assert submit_data["severity_band"] == "Mild"
    assert submit_data["risk_tier"] == "Low"
    assert submit_data["safety_alert"] is False
    assert submit_data["follow_up_summary"]["functional_difficulty"] == "Somewhat difficult"

    # 3. Safety Trigger Endpoint
    safety_payload = {
        "user_id": test_user,
        "test_type": "phq9",
        "responses": [0, 0, 0, 0, 0, 0, 0, 0, 2],  # Q9=2
        "safety_disclosure": {
            "active_thoughts": False,
            "immediate_intent": False,
            "safe_person_nearby": True,
        },
    }
    safety_res = client.post("/api/assessment/submit", json=safety_payload)
    assert safety_res.status_code == 200
    safety_data = safety_res.json()
    assert safety_data["safety_alert"] is True
    assert safety_data["risk_tier"] == "High"
    assert len(safety_data["safety_details"]["crisis_resources"]) > 0

    # 4. History Endpoint
    hist_res = client.get(f"/api/assessment/history/{test_user}")
    assert hist_res.status_code == 200
    hist_data = hist_res.json()
    assert hist_data["count"] >= 2
    assert hist_data["history"][0]["user_id"] == test_user
