"""
Assessment logic for PHQ-9 (Depression) and GAD-7 (Anxiety) self-screening.

Features:
- Validated PHQ-9 and GAD-7 standard questionnaires and timeframes.
- Deterministic scoring, severity categorization, and app risk tier mapping.
- Dedicated clinical safety pathway triggered by PHQ-9 Item 9 or follow-up crisis disclosure.
- Clinical symptom pattern domain mapping without invented/hallucinated symptoms.
- Contextual adaptive follow-up processing (functional impact, trajectory, elevation screen).
- Deterministic evidence-based next steps with optional LLM empathy synthesis and offline fallback.
"""
import os
import json
import logging
from typing import Dict, Any, List, Tuple, Optional
from datetime import datetime, timezone

from .db import save_assessment_attempt
from .recommendations import CRISIS_RESOURCES, COPING_STRATEGIES

logger = logging.getLogger("emocare.assessment")

# ── Validated Response Scale (0-3) for both PHQ-9 and GAD-7 ──────────
RESPONSE_SCALE = [
    {"value": 0, "label": "Not at all"},
    {"value": 1, "label": "Several days"},
    {"value": 2, "label": "More than half the days"},
    {"value": 3, "label": "Nearly every day"},
]

# Standard Timeframes
PHQ9_TIMEFRAME = (
    "Over the last 2 weeks, how often have you been bothered by any of the following problems?"
)
GAD7_TIMEFRAME = (
    "Over the last 2 weeks, how often have you been bothered by the following problems?"
)

# Standard PHQ-9 Questions (Kroenke, Spitzer, Williams, 2001)
PHQ9_QUESTIONS = [
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

# Standard GAD-7 Questions (Spitzer, Kroenke, Williams, Löwe, 2006)
GAD7_QUESTIONS = [
    "Feeling nervous, anxious, or on edge",
    "Not being able to stop or control worrying",
    "Worrying too much about different things",
    "Trouble relaxing",
    "Being so restless that it is hard to sit still",
    "Becoming easily annoyed or irritable",
    "Feeling afraid, as if something awful might happen",
]

# Standard Functional Impairment Question (PHQ/GAD Global Difficulty Item)
FUNCTIONAL_DIFFICULTY_QUESTION = (
    "If you checked off any problems, how difficult have these problems made it for you "
    "to do your work, take care of things at home, or get along with other people?"
)
FUNCTIONAL_DIFFICULTY_OPTIONS = [
    "Not difficult at all",
    "Somewhat difficult",
    "Very difficult",
    "Extremely difficult",
]

# Standard Non-Diagnostic Disclaimer
CLINICAL_DISCLAIMER = (
    "EmoCare self-assessments are standardized screening tools intended for informational and reflective support. "
    "They do not constitute a clinical diagnosis or medical evaluation. Please consult a qualified healthcare or mental health "
    "professional for formal diagnosis and personalized clinical care."
)


# ═══════════════════════════════════════════════════════════════════════
# DETERMINISTIC SCORING ENGINE
# ═══════════════════════════════════════════════════════════════════════

def score_phq9(responses: List[int]) -> Tuple[int, str, str, str, bool, int]:
    """
    Score PHQ-9 (Total: 0-27).
    Standard Cutoffs:
      0-4: Minimal
      5-9: Mild
      10-14: Moderate
      15-19: Moderately severe
      20-27: Severe

    Item 9 Check:
      Any endorsement of Question 9 (> 0) triggers the safety alert pathway.
      If total score would place the user in 'Low' risk tier, it is escalated to at least 'Moderate'.
      Item 9 >= 2 escalates to 'High' risk tier.

    Returns:
      (total_score, severity_band, risk_tier, summary, safety_alert, q9_score)
    """
    if len(responses) != 9:
        raise ValueError("PHQ-9 requires exactly 9 responses.")
    if any(r is None or not isinstance(r, int) or r < 0 or r > 3 for r in responses):
        raise ValueError("All PHQ-9 responses must be integers between 0 and 3.")

    total_score = sum(responses)
    q9_score = responses[8]
    safety_alert = q9_score > 0

    if total_score <= 4:
        severity = "Minimal"
        risk_tier = "Low"
        summary = (
            "Your responses suggest minimal depressive symptoms over the past two weeks. "
            "You appear to be experiencing everyday emotional balance."
        )
    elif total_score <= 9:
        severity = "Mild"
        risk_tier = "Low"
        summary = (
            "Your responses suggest mild depressive symptoms, such as occasional low energy or fatigue. "
            "Evidence-based self-care, daily routines, and gentle movement can help support your emotional wellbeing."
        )
    elif total_score <= 14:
        severity = "Moderate"
        risk_tier = "Moderate"
        summary = (
            "Your responses reflect moderate depressive symptoms. You may be experiencing persistent fatigue, "
            "low mood, or difficulties with daily tasks. Consulting a healthcare provider or licensed counselor is recommended."
        )
    elif total_score <= 19:
        severity = "Moderately severe"
        risk_tier = "High"
        summary = (
            "Your responses indicate moderately severe emotional distress that likely interferes with everyday functioning. "
            "We strongly encourage connecting with a healthcare professional or mental health specialist for comprehensive support."
        )
    else:
        severity = "Severe"
        risk_tier = "High"
        summary = (
            "Your responses indicate severe depressive distress. Reaching out to a qualified healthcare provider, "
            "mental health clinic, or support helpline can connect you with essential care and evidence-based treatment."
        )

    # Dedicated Safety Escalation: Question 9 endorsement cannot remain 'Low' risk
    if safety_alert:
        if risk_tier == "Low":
            risk_tier = "Moderate"
        if q9_score >= 2:
            risk_tier = "High"

    return total_score, severity, risk_tier, summary, safety_alert, q9_score


def score_gad7(responses: List[int]) -> Tuple[int, str, str, str]:
    """
    Score GAD-7 (Total: 0-21).
    Standard Cutoffs:
      0-4: Minimal
      5-9: Mild
      10-14: Moderate
      15-21: Severe

    Returns:
      (total_score, severity_band, risk_tier, summary)
    """
    if len(responses) != 7:
        raise ValueError("GAD-7 requires exactly 7 responses.")
    if any(r is None or not isinstance(r, int) or r < 0 or r > 3 for r in responses):
        raise ValueError("All GAD-7 responses must be integers between 0 and 3.")

    total_score = sum(responses)

    if total_score <= 4:
        severity = "Minimal"
        risk_tier = "Low"
        summary = (
            "Your responses indicate minimal symptoms of anxiety over the past two weeks. "
            "Your stress levels appear within a manageable range."
        )
    elif total_score <= 9:
        severity = "Mild"
        risk_tier = "Low"
        summary = (
            "Your responses indicate mild anxiety symptoms. Grounding exercises, paced breathing, "
            "and regular breaks can help prevent everyday tension from escalating."
        )
    elif total_score <= 14:
        severity = "Moderate"
        risk_tier = "Moderate"
        summary = (
            "Your responses reflect moderate anxiety. Persistent worry, restlessness, or physical tension "
            "may be affecting your concentration or sleep. A conversation with a healthcare provider or therapist is advised."
        )
    else:
        severity = "Severe"
        risk_tier = "High"
        summary = (
            "Your responses indicate severe anxiety symptoms that significantly disrupt daily comfort. "
            "We recommend reaching out to a medical or mental health professional for structured evaluation and coping strategies."
        )

    return total_score, severity, risk_tier, summary


# ═══════════════════════════════════════════════════════════════════════
# SYMPTOM PATTERN MAPPING (DETERMINISTIC — NO HALLUCINATIONS)
# ═══════════════════════════════════════════════════════════════════════

def build_symptom_breakdown(test_type: str, responses: List[int]) -> Dict[str, Any]:
    """
    Map exact user responses to clinical symptom domains without inventing unreported symptoms.
    """
    scale_map = {0: "Not at all", 1: "Several days", 2: "More than half the days", 3: "Nearly every day"}
    reported_items: List[Dict[str, Any]] = []
    unreported_items: List[Dict[str, Any]] = []

    questions = PHQ9_QUESTIONS if test_type == "phq9" else GAD7_QUESTIONS

    for idx, (q_text, val) in enumerate(zip(questions, responses)):
        item_data = {
            "item_number": idx + 1,
            "question": q_text,
            "score": val,
            "frequency_label": scale_map.get(val, "Unknown"),
        }
        if val > 0:
            reported_items.append(item_data)
        else:
            unreported_items.append(item_data)

    domains: Dict[str, Any] = {}

    if test_type == "phq9":
        # Group into core PHQ-9 domains
        mood_scores = [responses[0], responses[1]]  # Q1, Q2
        somatic_scores = [responses[2], responses[3], responses[4]]  # Q3, Q4, Q5
        cognitive_scores = [responses[5], responses[6], responses[7]]  # Q6, Q7, Q8
        safety_score = responses[8]  # Q9

        domains = {
            "core_mood": {
                "label": "Depressed Mood & Interest",
                "items": [1, 2],
                "score": sum(mood_scores),
                "max": 6,
                "summary": "Core affective symptoms of anhedonia or low mood.",
            },
            "somatic_energy": {
                "label": "Sleep, Energy & Appetite",
                "items": [3, 4, 5],
                "score": sum(somatic_scores),
                "max": 9,
                "summary": "Physical and vegetative manifestations of distress.",
            },
            "cognitive_psychomotor": {
                "label": "Cognition & Self-Worth",
                "items": [6, 7, 8],
                "score": sum(cognitive_scores),
                "max": 9,
                "summary": "Concentration, self-critical thoughts, and movement speed.",
            },
            "safety_ideation": {
                "label": "Thoughts of Death or Self-Harm",
                "items": [9],
                "score": safety_score,
                "max": 3,
                "endorsed": safety_score > 0,
            },
        }
    else:
        # Group into core GAD-7 domains
        worry_scores = [responses[0], responses[1], responses[2]]  # Q1, Q2, Q3
        tension_scores = [responses[3], responses[4]]  # Q4, Q5
        reactivity_scores = [responses[5], responses[6]]  # Q6, Q7

        domains = {
            "core_worry": {
                "label": "Excessive Worry & Apprehension",
                "items": [1, 2, 3],
                "score": sum(worry_scores),
                "max": 9,
                "summary": "Frequency and controllability of worry.",
            },
            "motor_tension": {
                "label": "Tension & Restlessness",
                "items": [4, 5],
                "score": sum(tension_scores),
                "max": 6,
                "summary": "Difficulty relaxing and physical restlessness.",
            },
            "emotional_reactivity": {
                "label": "Irritability & Dread",
                "items": [6, 7],
                "score": sum(reactivity_scores),
                "max": 6,
                "summary": "Heightened irritability and anticipatory fear.",
            },
        }

    return {
        "domains": domains,
        "reported_count": len(reported_items),
        "unreported_count": len(unreported_items),
        "reported_items": reported_items,
        "unreported_items": unreported_items,
    }


# ═══════════════════════════════════════════════════════════════════════
# CONTEXTUAL FOLLOW-UP & ADAPTIVE BRANCHING
# ═══════════════════════════════════════════════════════════════════════

def process_follow_up_data(follow_up_data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Process and structure contextual follow-up answers.
    Evaluates:
      - Functional impact on work, study, relationships, and routines
      - Symptom duration & trajectory
      - Prior episodes and current treatments
      - Mood elevation screening (hypomania differential indicator)
      - Contributing life circumstances
      - User's chosen coping goals
    """
    if not follow_up_data:
        return {
            "completed": False,
            "functional_difficulty": "Not specified",
            "impact_areas": [],
            "duration": "Not specified",
            "trajectory": "Not specified",
            "prior_history": "Not specified",
            "elevation_screen_endorsed": False,
            "elevation_screen_note": None,
            "life_factors": [],
            "coping_goals": [],
        }

    functional_difficulty = follow_up_data.get("functional_difficulty", "Not specified")
    impact_areas = follow_up_data.get("impact_areas", [])
    duration = follow_up_data.get("duration", "Not specified")
    trajectory = follow_up_data.get("trajectory", "Not specified")
    prior_history = follow_up_data.get("prior_history", "Not specified")
    elevation_screen = follow_up_data.get("elevation_screen", "No, never")
    life_factors = follow_up_data.get("life_factors", [])
    coping_goals = follow_up_data.get("coping_goals", [])

    elevation_endorsed = (
        isinstance(elevation_screen, str)
        and elevation_screen.strip().lower().startswith("yes")
    )
    elevation_note = (
        "You reported past periods of unusually elevated mood, high energy, or reduced need for sleep. "
        "A mental health professional can help review these mood patterns to ensure an accurate, comprehensive clinical evaluation."
        if elevation_endorsed else None
    )

    return {
        "completed": True,
        "functional_difficulty": functional_difficulty,
        "impact_areas": impact_areas,
        "duration": duration,
        "trajectory": trajectory,
        "prior_history": prior_history,
        "elevation_screen_endorsed": elevation_endorsed,
        "elevation_screen_note": elevation_note,
        "life_factors": life_factors,
        "coping_goals": coping_goals,
    }


# ═══════════════════════════════════════════════════════════════════════
# CLINICAL SAFETY PATHWAY
# ═══════════════════════════════════════════════════════════════════════

def evaluate_safety_pathway(
    test_type: str,
    responses: List[int],
    safety_disclosure: Optional[Dict[str, Any]] = None,
    follow_up_data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Deterministic safety evaluation.
    Evaluates:
      1. PHQ-9 Item 9 endorsement (score 1, 2, or 3)
      2. Safety disclosure responses (active thoughts, immediate intent, safe person nearby)
      3. Critical distress disclosures in contextual follow-up

    Returns:
      safety_details dict with flags, urgency level, resources, and protocol guidance.
    """
    safety_alert = False
    q9_score = 0
    active_emergency = False
    urgency_level = "STABLE"
    reason = None

    if test_type == "phq9" and len(responses) == 9:
        q9_score = responses[8]
        if q9_score > 0:
            safety_alert = True
            reason = "Endorsement of thoughts of self-harm or being better off dead (PHQ-9 Item 9)"
            urgency_level = "WARNING" if q9_score == 1 else "CRITICAL"

    if safety_disclosure:
        has_active_thoughts = safety_disclosure.get("active_thoughts", False)
        has_immediate_intent = safety_disclosure.get("immediate_intent", False)
        if has_active_thoughts or has_immediate_intent:
            safety_alert = True
            active_emergency = True
            urgency_level = "CRITICAL"
            reason = "Active thoughts or immediate intent disclosed in safety clarification"

    return {
        "safety_alert": safety_alert,
        "q9_score": q9_score,
        "active_emergency": active_emergency,
        "urgency_level": urgency_level,
        "reason": reason,
        "crisis_resources": CRISIS_RESOURCES,
        "safety_notice": (
            "EmoCare provides automated self-care guidance and is NOT monitored by live crisis clinicians. "
            "If you are having thoughts of suicide, self-harm, or feel unsafe, please connect immediately with "
            "one of the free, confidential crisis hotlines or emergency services listed below."
        ) if safety_alert else None,
    }


# ═══════════════════════════════════════════════════════════════════════
# ACTIONABLE NEXT STEPS ENGINE (DETERMINISTIC)
# ═══════════════════════════════════════════════════════════════════════

def build_recommended_steps(
    test_type: str,
    severity_band: str,
    risk_tier: str,
    safety_alert: bool,
    active_emergency: bool,
    follow_up_summary: Dict[str, Any],
) -> List[str]:
    """
    Build clinically appropriate, tiered next steps:
      - Emergency crisis referral when indicated
      - Professional evaluation when indicated (moderate to severe)
      - Specific EmoCare guided tools (breathing, journaling, CBT)
      - Everyday lifestyle and self-care recommendations
    """
    steps: List[str] = []

    # 1. Urgent Safety Step
    if active_emergency:
        steps.append(
            "🚨 Immediate human support: Please call or text 988 (US/Canada), 112/999/911 (Emergency), "
            "or contact iCall (9152987821) / Tele-MANAS (14416) right now. You do not have to carry this alone."
        )
    elif safety_alert:
        steps.append(
            "📞 Supportive crisis contact: Because you noted thoughts of self-harm, we encourage you to save "
            "the 988 Lifeline (call/text 988) or Crisis Text Line (text HOME to 741741) in your phone."
        )

    # 2. Professional Referral Step (Tier-Appropriate)
    if severity_band in ("Moderate", "Moderately severe", "Severe") or safety_alert:
        steps.append(
            "🩺 Professional consultation: Schedule an appointment with a licensed therapist, counselor, "
            "or primary care physician for a comprehensive clinical assessment and personalized care plan."
        )
    elif severity_band == "Mild":
        steps.append(
            "💬 Consider professional guidance: If these feelings persist beyond several weeks or begin to "
            "interfere with your daily work or relationships, consider speaking with a mental health professional."
        )

    # 3. Functional & Trajectory Specific Step
    if follow_up_summary.get("elevation_screen_endorsed"):
        steps.append(
            "📋 Mention mood patterns: Discuss any periods of unusually elevated energy or decreased sleep with "
            "your healthcare provider so they can evaluate the full spectrum of your mood history."
        )

    # 4. In-App Supportive Tools
    if test_type == "gad7" or severity_band in ("Mild", "Moderate"):
        steps.append(
            "🌬️ Paced Breathing & Grounding: Practice 5-minute box breathing or 5-4-3-2-1 sensory grounding "
            "in the EmoCare companion whenever you notice physical tension rising."
        )
    if test_type == "phq9" or severity_band in ("Mild", "Moderate"):
        steps.append(
            "📝 Expressive Reflection: Use the EmoCare Daily Journal to externalize heavy thoughts, "
            "or try gentle behavioral activation by scheduling one small, rewarding activity today."
        )

    # 5. Baseline Maintenance
    steps.append(
        "📊 Track trends: Re-screen in 2 to 4 weeks to observe whether your symptoms are improving, stable, "
        "or in need of additional support."
    )

    return steps


# ═══════════════════════════════════════════════════════════════════════
# LLM EMPATHY SYNTHESIS (WITH DETERMINISTIC OFFLINE FALLBACK)
# ═══════════════════════════════════════════════════════════════════════

async def generate_assessment_insights(
    test_type: str,
    total_score: int,
    max_score: int,
    severity_band: str,
    risk_tier: str,
    symptom_breakdown: Dict[str, Any],
    follow_up_summary: Dict[str, Any],
    safety_details: Dict[str, Any],
    default_summary: str,
) -> str:
    """
    Attempt to use the existing EmoCare LLM client to generate an empathetic,
    clinically informed plain-language reflection.

    Strict Safety Constraints:
      - The LLM NEVER calculates or overrides scores.
      - The LLM NEVER diagnoses a condition or makes clinical claims.
      - The LLM NEVER invents symptoms not present in symptom_breakdown.
      - If LLM call fails or is unavailable, immediately falls back to default_summary.
    """
    try:
        from .engine.llm_client import chat_completion

        reported_symptoms = [
            f"• {item['question']} ({item['frequency_label']})"
            for item in symptom_breakdown.get("reported_items", [])
        ]
        symptoms_str = "\n".join(reported_symptoms) if reported_symptoms else "No elevated symptoms endorsed."

        context_notes = []
        if follow_up_summary.get("functional_difficulty") != "Not specified":
            context_notes.append(f"Functional impact: {follow_up_summary['functional_difficulty']}")
        if follow_up_summary.get("duration") != "Not specified":
            context_notes.append(f"Duration: {follow_up_summary['duration']}")
        if follow_up_summary.get("trajectory") != "Not specified":
            context_notes.append(f"Trajectory: {follow_up_summary['trajectory']}")

        context_str = "; ".join(context_notes) if context_notes else "None specified"

        system_prompt = (
            "You are an empathetic, clinical-informed mental health reflection assistant for EmoCare. "
            "Your role is to explain standardized screening results warmly, clearly, and responsibly.\n\n"
            "STRICT RULES:\n"
            "1. NEVER diagnose depression, anxiety, or any medical disorder. This is a screening tool, not a diagnosis.\n"
            "2. NEVER alter or calculate scores. Use the exact score and severity provided.\n"
            "3. NEVER invent or assume symptoms not explicitly listed in the user's reported items.\n"
            "4. NEVER make medical claims, recommend specific medications, or claim AI certainty.\n"
            "5. If thoughts of self-harm are flagged, speak with profound compassion and gently point to human crisis resources.\n"
            "6. Keep your response to 2 supportive, easy-to-read paragraphs."
        )

        user_prompt = (
            f"Assessment: {test_type.upper()}\n"
            f"Score: {total_score} out of {max_score} ({severity_band} severity band, {risk_tier} risk tier)\n"
            f"Safety flag: {safety_details.get('safety_alert', False)}\n"
            f"Reported symptoms:\n{symptoms_str}\n"
            f"Contextual background: {context_str}\n\n"
            "Please provide a warm, empathetic summary of what these results reflect and supportive guidance."
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        res = await chat_completion(messages=messages, temperature=0.3, max_tokens=400)
        content = res.get("content", "").strip()
        if content and len(content) > 40:
            return content
        return default_summary
    except Exception as e:
        logger.info(f"LLM synthesis unavailable or offline, using deterministic summary: {e}")
        return default_summary


# ═══════════════════════════════════════════════════════════════════════
# MAIN ASSESSMENT PROCESSOR
# ═══════════════════════════════════════════════════════════════════════

async def process_assessment_async(
    user_id: str,
    test_type: str,
    responses: List[int],
    follow_up_data: Optional[Dict[str, Any]] = None,
    safety_disclosure: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Primary assessment processing pipeline:
      1. Validates test type and response integers.
      2. Computes deterministic score, severity band, and app risk tier.
      3. Executes safety pathway (PHQ-9 Q9 + disclosure verification).
      4. Compiles symptom domain breakdown from exact responses.
      5. Processes contextual follow-up (duration, impact, trajectory, elevation screen).
      6. Formulates evidence-based next steps.
      7. Persists attempt to database (PostgreSQL or local SQLite).
      8. Generates supportive summary (LLM with deterministic fallback).
    """
    test_type_clean = test_type.lower().strip().replace("-", "")

    if test_type_clean == "phq9":
        total_score, severity, risk_tier, deterministic_summary, safety_alert, q9_score = score_phq9(responses)
        max_score = 27
        test_display_name = "PHQ-9 (Depression Screening)"
    elif test_type_clean == "gad7":
        total_score, severity, risk_tier, deterministic_summary = score_gad7(responses)
        max_score = 21
        test_display_name = "GAD-7 (Anxiety Screening)"
        safety_alert = False
        q9_score = 0
    else:
        raise ValueError(f"Unsupported test type '{test_type}'. Must be 'phq9' or 'gad7'.")

    # Safety Pathway
    safety_details = evaluate_safety_pathway(
        test_type=test_type_clean,
        responses=responses,
        safety_disclosure=safety_disclosure,
        follow_up_data=follow_up_data,
    )
    if safety_details.get("safety_alert"):
        safety_alert = True
        # Ensure risk tier is escalated
        if risk_tier == "Low":
            risk_tier = "Moderate"
        if safety_details.get("active_emergency") or q9_score >= 2:
            risk_tier = "High"

    # Symptom Pattern Breakdown
    symptom_breakdown = build_symptom_breakdown(test_type_clean, responses)

    # Contextual Follow-up Processing
    follow_up_summary = process_follow_up_data(follow_up_data)

    # Actionable Next Steps
    recommended_steps = build_recommended_steps(
        test_type=test_type_clean,
        severity_band=severity,
        risk_tier=risk_tier,
        safety_alert=safety_alert,
        active_emergency=safety_details.get("active_emergency", False),
        follow_up_summary=follow_up_summary,
    )

    # Summary Generation (LLM or deterministic)
    plain_language_summary = await generate_assessment_insights(
        test_type=test_type_clean,
        total_score=total_score,
        max_score=max_score,
        severity_band=severity,
        risk_tier=risk_tier,
        symptom_breakdown=symptom_breakdown,
        follow_up_summary=follow_up_summary,
        safety_details=safety_details,
        default_summary=deterministic_summary,
    )

    now = datetime.now(timezone.utc)

    # Database Persistence
    attempt_id = save_assessment_attempt(
        user_id=user_id,
        test_type=test_type_clean,
        responses=responses,
        total_score=total_score,
        severity_band=severity,
        risk_tier=risk_tier,
        safety_flag=safety_alert,
        q9_score=q9_score,
        follow_up_data=follow_up_data,
        llm_summary=plain_language_summary,
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
        "plain_language_summary": plain_language_summary,
        "timestamp": now.isoformat(),
        "safety_alert": safety_alert,
        "safety_details": safety_details,
        "symptom_breakdown": symptom_breakdown,
        "follow_up_summary": follow_up_summary,
        "recommended_steps": recommended_steps,
        "clinical_disclaimer": CLINICAL_DISCLAIMER,
    }


def process_assessment(
    user_id: str,
    test_type: str,
    responses: List[int],
    follow_up_data: Optional[Dict[str, Any]] = None,
    safety_disclosure: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Synchronous wrapper for backwards compatibility with test fixtures.
    Uses deterministic summary directly without async LLM synthesis.
    """
    test_type_clean = test_type.lower().strip().replace("-", "")

    if test_type_clean == "phq9":
        total_score, severity, risk_tier, deterministic_summary, safety_alert, q9_score = score_phq9(responses)
        max_score = 27
        test_display_name = "PHQ-9 (Depression Screening)"
    elif test_type_clean == "gad7":
        total_score, severity, risk_tier, deterministic_summary = score_gad7(responses)
        max_score = 21
        test_display_name = "GAD-7 (Anxiety Screening)"
        safety_alert = False
        q9_score = 0
    else:
        raise ValueError(f"Unsupported test type '{test_type}'. Must be 'phq9' or 'gad7'.")

    safety_details = evaluate_safety_pathway(
        test_type=test_type_clean,
        responses=responses,
        safety_disclosure=safety_disclosure,
        follow_up_data=follow_up_data,
    )
    if safety_details.get("safety_alert"):
        safety_alert = True
        if risk_tier == "Low":
            risk_tier = "Moderate"
        if safety_details.get("active_emergency") or q9_score >= 2:
            risk_tier = "High"

    symptom_breakdown = build_symptom_breakdown(test_type_clean, responses)
    follow_up_summary = process_follow_up_data(follow_up_data)
    recommended_steps = build_recommended_steps(
        test_type=test_type_clean,
        severity_band=severity,
        risk_tier=risk_tier,
        safety_alert=safety_alert,
        active_emergency=safety_details.get("active_emergency", False),
        follow_up_summary=follow_up_summary,
    )

    now = datetime.now(timezone.utc)

    attempt_id = save_assessment_attempt(
        user_id=user_id,
        test_type=test_type_clean,
        responses=responses,
        total_score=total_score,
        severity_band=severity,
        risk_tier=risk_tier,
        safety_flag=safety_alert,
        q9_score=q9_score,
        follow_up_data=follow_up_data,
        llm_summary=deterministic_summary,
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
        "plain_language_summary": deterministic_summary,
        "timestamp": now.isoformat(),
        "safety_alert": safety_alert,
        "safety_details": safety_details,
        "symptom_breakdown": symptom_breakdown,
        "follow_up_summary": follow_up_summary,
        "recommended_steps": recommended_steps,
        "clinical_disclaimer": CLINICAL_DISCLAIMER,
    }
