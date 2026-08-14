"""
Pydantic schemas for EmoCare API request/response validation.

All response contracts are designed so the Next.js frontend can consume them
with strict TypeScript types — no ambiguous fields.
"""
from pydantic import BaseModel, Field
from typing import Optional


# ── Risk Probabilities (shared across all modality responses) ──────────
class RiskProbabilities(BaseModel):
    Low: float = Field(..., ge=0, le=1)
    Moderate: float = Field(..., ge=0, le=1)
    High: float = Field(..., ge=0, le=1)


# ── Linguistic Markers (supplementary text signal) ─────────────────────
class LinguisticMarkers(BaseModel):
    first_person_rate: float = Field(..., description="Ratio of first-person pronouns to total words")
    absolutist_rate: float = Field(..., description="Ratio of absolutist words (always, never, etc.)")
    negation_rate: float = Field(..., description="Ratio of negation words (not, no, never, etc.)")
    word_count: int


# ── Text Prediction ───────────────────────────────────────────────────
class TextRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=10000)


class TextResponse(BaseModel):
    predicted_risk_tier: str
    probabilities: RiskProbabilities
    confidence: float
    linguistic_markers: LinguisticMarkers


# ── Speech Prediction ─────────────────────────────────────────────────
class SpeechEmotionDetail(BaseModel):
    detected_emotion: str
    emotion_confidence: float
    emotion_probabilities: dict[str, float]


class SpeechResponse(BaseModel):
    predicted_risk_tier: str
    probabilities: RiskProbabilities
    emotion_detail: SpeechEmotionDetail
    prosodic_features: dict[str, float] = Field(
        default_factory=dict,
        description="Pitch variance, speech rate, pause duration"
    )


# ── Behavioral Prediction ─────────────────────────────────────────────
class BehavioralRequest(BaseModel):
    sleep_hours: Optional[float] = Field(None, ge=0, le=24)
    sleep_quality: Optional[float] = Field(None, ge=1, le=5, description="1=very poor, 5=excellent")
    activity_level: Optional[float] = Field(None, ge=1, le=5, description="1=sedentary, 5=very active")
    social_interaction: Optional[float] = Field(None, ge=1, le=5, description="1=isolated, 5=very social")
    stress_level: Optional[float] = Field(None, ge=1, le=5, description="1=no stress, 5=extreme stress")
    exercise_minutes: Optional[float] = Field(None, ge=0)
    mood_rating: Optional[float] = Field(None, ge=1, le=5, description="1=very low, 5=very high")


class BehavioralResponse(BaseModel):
    predicted_risk_tier: str
    probabilities: RiskProbabilities


# ── Multimodal Fusion ─────────────────────────────────────────────────
class ModalityBreakdown(BaseModel):
    text: Optional[TextResponse] = None
    speech: Optional[SpeechResponse] = None
    behavioral: Optional[BehavioralResponse] = None


class MultimodalResponse(BaseModel):
    final_risk_tier: str
    probabilities: RiskProbabilities
    confidence: float
    escalate_to_human_reviewer: bool
    urgency_level: str = Field(..., description="STABLE | WARNING | CRITICAL")
    cross_modal_agreement: float = Field(
        ..., ge=0, le=1,
        description="Agreement score between modalities (1.0 = full agreement)"
    )
    low_confidence_flag: bool = Field(
        ..., description="True when confidence is low or modalities disagree — defer to human judgment"
    )
    coping_recommendations: list[str]
    modality_breakdown: ModalityBreakdown


# ── Health Check ──────────────────────────────────────────────────────
class HealthResponse(BaseModel):
    status: str
    models_loaded: dict[str, bool]
    version: str = "1.0.0"


# ── Self-Assessment (PHQ-9 & GAD-7) ───────────────────────────────────
class AssessmentSubmissionRequest(BaseModel):
    user_id: str = Field(..., min_length=1, description="Unique user or session identifier")
    test_type: str = Field(..., description="'phq9' or 'gad7'")
    responses: list[int] = Field(..., description="List of responses (0-3 each, 9 items for PHQ-9, 7 for GAD-7)")


class AssessmentResponse(BaseModel):
    id: Optional[int] = None
    user_id: str
    test_type: str
    test_display_name: str
    total_score: int
    max_score: int
    severity_band: str
    risk_tier: str = Field(..., description="Mapped app risk tier: Low | Moderate | High")
    plain_language_summary: str
    timestamp: str

