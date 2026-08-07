"""
Coping recommendations and escalation alert logic.

Rule-based mapping: (risk_tier, detected_emotion) -> coping strategies.
Not LLM-based — avoids safety surface per project spec.
"""

# ── Static crisis resources ────────────────────────────────────────────
CRISIS_RESOURCES = [
    "Crisis Helpline (India): iCall — 9152987821",
    "Crisis Helpline (US): 988 Suicide & Crisis Lifeline — dial 988",
    "Crisis Helpline (UK): Samaritans — 116 123",
    "International Association for Suicide Prevention: https://www.iasp.info/resources/Crisis_Centres/",
    "If you are in immediate danger, please contact emergency services (112 / 911 / 999).",
]

# ── CBT-grounded coping strategy library ───────────────────────────────
COPING_STRATEGIES = {
    "grounding": [
        "Try the 5-4-3-2-1 grounding technique: Name 5 things you see, 4 you can touch, 3 you hear, 2 you smell, 1 you taste.",
        "Place both feet flat on the ground. Focus on the sensation of contact for 30 seconds.",
    ],
    "breathing": [
        "Practice box breathing: Inhale for 4 seconds, hold for 4, exhale for 4, hold for 4. Repeat 4 times.",
        "Try diaphragmatic breathing: Place one hand on your chest and one on your belly. Breathe so only your belly hand moves.",
    ],
    "cognitive_reframe": [
        "Write down the thought that is distressing you. Then ask: 'What evidence supports this? What evidence contradicts it?'",
        "Try the 'best friend test': If your best friend told you they were thinking this, what would you say to them?",
    ],
    "behavioral_activation": [
        "Identify one small, achievable activity you can do in the next 10 minutes (e.g., a short walk, making tea).",
        "Schedule one pleasant activity for today, even if brief — engagement reduces rumination.",
    ],
    "social_connection": [
        "Reach out to one person you trust — a friend, family member, or counselor. Connection is protective.",
        "If speaking feels hard, send a text message to someone you care about.",
    ],
    "journaling": [
        "Spend 5 minutes writing freely about how you feel right now. Don't edit — just let the words flow.",
        "Try a gratitude prompt: List 3 small things from today that you're grateful for, however minor.",
    ],
    "professional_help": [
        "Consider scheduling a session with a mental health professional or counselor.",
        "Many universities and workplaces offer free confidential counseling — check if yours does.",
    ],
}


def get_coping_recommendations(
    risk_tier: str,
    detected_emotion: str | None = None,
    urgency_level: str = "STABLE",
) -> list[str]:
    """
    Generate personalized coping recommendations based on risk tier and emotion.

    Returns 3-5 actionable recommendations. For CRITICAL urgency, crisis resources
    are always included at the top.
    """
    recommendations: list[str] = []

    # ── CRITICAL / HIGH: always lead with crisis resources & professional help ──
    if urgency_level == "CRITICAL" or risk_tier == "High":
        recommendations.append(CRISIS_RESOURCES[0])  # India helpline
        recommendations.append(CRISIS_RESOURCES[1])  # US helpline
        recommendations.append(CRISIS_RESOURCES[4])  # Emergency services
        recommendations.extend(COPING_STRATEGIES["grounding"][:1])
        recommendations.extend(COPING_STRATEGIES["breathing"][:1])
        recommendations.extend(COPING_STRATEGIES["professional_help"][:1])
        return recommendations[:6]

    # ── WARNING / MODERATE ──
    if urgency_level == "WARNING" or risk_tier == "Moderate":
        recommendations.extend(COPING_STRATEGIES["breathing"][:1])
        recommendations.extend(COPING_STRATEGIES["cognitive_reframe"][:1])

        # Emotion-specific additions
        if detected_emotion in ("sad", "fearful"):
            recommendations.extend(COPING_STRATEGIES["social_connection"][:1])
            recommendations.extend(COPING_STRATEGIES["journaling"][:1])
        elif detected_emotion in ("angry", "disgust"):
            recommendations.extend(COPING_STRATEGIES["grounding"][:1])
            recommendations.extend(COPING_STRATEGIES["behavioral_activation"][:1])
        else:
            recommendations.extend(COPING_STRATEGIES["behavioral_activation"][:1])
            recommendations.extend(COPING_STRATEGIES["journaling"][:1])

        recommendations.extend(COPING_STRATEGIES["professional_help"][:1])
        return recommendations[:5]

    # ── STABLE / LOW ──
    recommendations.extend(COPING_STRATEGIES["journaling"][:1])
    recommendations.extend(COPING_STRATEGIES["behavioral_activation"][:1])

    if detected_emotion in ("sad", "fearful"):
        recommendations.extend(COPING_STRATEGIES["breathing"][:1])
    elif detected_emotion in ("happy", "calm", "neutral"):
        recommendations.append(
            "You seem to be in a stable state. Keep up healthy routines — consistency is protective."
        )
    else:
        recommendations.extend(COPING_STRATEGIES["grounding"][:1])

    return recommendations[:4]
