"""
Assessment logic for PHQ-9 (Depression) and GAD-7 (Anxiety) self-screening.

Includes standard questionnaires, scoring rules, severity band mapping,
app risk tier conversion (Low / Moderate / High), and supportive, plain-language summaries.
"""
from typing import Dict, Any, List, Tuple
from datetime import datetime, timezone
from .db import save_assessment_attempt

# Common response scale (0-3) for both PHQ-9 and GAD-7
RESPONSE_SCALE = [
    {"value": 0, "label": "Not at all"},
    {"value": 1, "label": "Several days"},
    {"value": 2, "label": "More than half the days"},
    {"value": 3, "label": "Nearly every day"},
]

# Standard PHQ-9 Questions (Patient Health Questionnaire - 9)
PHQ9_QUESTIONS = [
    "1. Little interest or pleasure in doing things",
    "2. Feeling down, depressed, or hopeless",
    "3. Trouble falling or staying asleep, or sleeping too much",
    "4. Feeling tired or having little energy",
    "5. Poor appetite or overeating",
    "6. Feeling bad about yourself — or that you are a failure or have let yourself or your family down",
    "7. Trouble concentrating on things, such as reading the newspaper or watching television",
    "8. Moving or speaking so slowly that other people could have noticed? Or the opposite — being so fidgety or restless that you have been moving around a lot more than usual",
    "9. Thoughts that you would be better off dead or of hurting yourself in some way",
]

# Standard GAD-7 Questions (Generalized Anxiety Disorder - 7)
GAD7_QUESTIONS = [
    "1. Feeling nervous, anxious, or on edge",
    "2. Not being able to stop or control worrying",
    "3. Worrying too much about different things",
    "4. Trouble relaxing",
    "5. Being so restless that it is hard to sit still",
    "6. Becoming easily annoyed or irritable",
    "7. Feeling afraid, as if something awful might happen",
]


def score_phq9(responses: List[int]) -> Tuple[int, str, str, str]:
    """
    Score PHQ-9 (Total: 0-27).
    Returns: (total_score, severity_band, risk_tier, plain_language_summary)
    """
    if len(responses) != 9:
        raise ValueError("PHQ-9 requires exactly 9 responses.")
    if any(r < 0 or r > 3 for r in responses):
        raise ValueError("All PHQ-9 responses must be integers between 0 and 3.")

    total_score = sum(responses)

    if total_score <= 4:
        severity = "Minimal or None"
        risk_tier = "Low"
        summary = "Your responses suggest minimal or no depressive distress. You seem to be experiencing day-to-day emotional balance."
    elif total_score <= 9:
        severity = "Mild"
        risk_tier = "Low"
        summary = "Your responses suggest mild signs of low mood or fatigue. Practicing daily self-care, mindfulness, or light physical movement may be helpful."
    elif total_score <= 14:
        severity = "Moderate"
        risk_tier = "Moderate"
        summary = "Your responses reflect moderate emotional distress. You may be feeling persistent fatigue or low mood. Consider speaking with a counselor or trusted support person."
    elif total_score <= 19:
        severity = "Moderately Severe"
        risk_tier = "High"
        summary = "Your responses indicate notable emotional strain and difficulty with daily routines. We encourage connecting with a healthcare or mental health professional for guidance."
    else:
        severity = "Severe"
        risk_tier = "High"
        summary = "Your responses suggest significant distress. Reaching out to a healthcare professional or supportive helpline can provide valuable care and structured assistance."

    return total_score, severity, risk_tier, summary


def score_gad7(responses: List[int]) -> Tuple[int, str, str, str]:
    """
    Score GAD-7 (Total: 0-21).
    Returns: (total_score, severity_band, risk_tier, plain_language_summary)
    """
    if len(responses) != 7:
        raise ValueError("GAD-7 requires exactly 7 responses.")
    if any(r < 0 or r > 3 for r in responses):
        raise ValueError("All GAD-7 responses must be integers between 0 and 3.")

    total_score = sum(responses)

    if total_score <= 4:
        severity = "Minimal Anxiety"
        risk_tier = "Low"
        summary = "Your responses indicate minimal anxiety. Your stress levels appear manageable."
    elif total_score <= 9:
        severity = "Mild Anxiety"
        risk_tier = "Low"
        summary = "Your responses indicate mild anxiety. Simple breathing exercises, regular breaks, and grounding techniques can help keep stress in check."
    elif total_score <= 14:
        severity = "Moderate Anxiety"
        risk_tier = "Moderate"
        summary = "Your responses reflect moderate anxiety. Worry or tension might be impacting your daily focus. Consider exploring stress reduction techniques or consulting a mental health professional."
    else:
        severity = "Severe Anxiety"
        risk_tier = "High"
        summary = "Your responses suggest heightened anxiety levels. We encourage consulting with a qualified healthcare or mental health provider for supportive strategies."

    return total_score, severity, risk_tier, summary


def process_assessment(user_id: str, test_type: str, responses: List[int]) -> Dict[str, Any]:
    """
    Score the assessment, map to risk tier, persist to PostgreSQL, and format response.
    """
    test_type_clean = test_type.lower().strip().replace("-", "")
    if test_type_clean == "phq9":
        total_score, severity, risk_tier, summary = score_phq9(responses)
        max_score = 27
        test_display_name = "PHQ-9 (Depression Screening)"
    elif test_type_clean == "gad7":
        total_score, severity, risk_tier, summary = score_gad7(responses)
        max_score = 21
        test_display_name = "GAD-7 (Anxiety Screening)"
    else:
        raise ValueError(f"Unsupported test type '{test_type}'. Must be 'phq9' or 'gad7'.")

    now = datetime.now(timezone.utc)
    attempt_id = save_assessment_attempt(
        user_id=user_id,
        test_type=test_type_clean,
        responses=responses,
        total_score=total_score,
        severity_band=severity,
        risk_tier=risk_tier,
        timestamp=now,
    )

    return {
        "id": attempt_id,
        "user_id": user_id,
        "test_type": test_type_clean,
        "test_display_name": test_display_name,
        "total_score": total_score,
        "max_score": max_score,
        "severity_band": severity,
        "risk_tier": risk_tier,
        "plain_language_summary": summary,
        "timestamp": now.isoformat(),
    }
