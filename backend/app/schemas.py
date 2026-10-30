"""
Pydantic schemas for EmoCare API request/response validation.

All response contracts are designed so the Next.js frontend can consume them
with strict TypeScript types — no ambiguous fields.
"""
from datetime import date
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


# ── Daily Check-ins ─────────────────────────────────────────────────────
class DailyCheckInRequest(BaseModel):
    local_date: date
    mood_rating: int = Field(..., ge=1, le=5)
    stress_level: int = Field(..., ge=1, le=5)
    sleep_quality: int = Field(..., ge=1, le=5)
    energy_level: int = Field(..., ge=1, le=5)
    sleep_hours: Optional[float] = Field(None, ge=0, le=24)
    activity_level: Optional[int] = Field(None, ge=1, le=5)
    social_interaction: Optional[int] = Field(None, ge=1, le=5)
    exercise_minutes: Optional[float] = Field(None, ge=0)
    notes: str = Field(default="", max_length=1000)


class DailyCheckInResponse(DailyCheckInRequest):
    id: int
    user_id: str
    created_at: str
    updated_at: str


class TodayCheckInResponse(BaseModel):
    local_date: date
    completed: bool
    check_in: Optional[DailyCheckInResponse] = None


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
    follow_up_data: Optional[dict] = Field(default=None, description="Contextual follow-up responses")
    safety_disclosure: Optional[dict] = Field(default=None, description="Safety verification responses if Q9 endorsed")


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
    safety_alert: bool = False
    safety_details: Optional[dict] = None
    symptom_breakdown: Optional[dict] = None
    follow_up_summary: Optional[dict] = None
    recommended_steps: list[str] = Field(default_factory=list)
    clinical_disclaimer: str = (
        "EmoCare self-assessments are standardized screening tools intended for informational "
        "and reflective support. They do not constitute a clinical diagnosis or medical evaluation. "
        "Please consult a qualified healthcare professional or licensed mental health provider for clinical evaluation."
    )


class AssessmentHistoryItem(BaseModel):
    id: Optional[int] = None
    user_id: str
    test_type: str
    total_score: int
    max_score: int
    severity_band: str
    risk_tier: str
    safety_flag: bool = False
    q9_score: Optional[int] = 0
    timestamp: str
    llm_summary: Optional[str] = None


class AssessmentHistoryResponse(BaseModel):
    user_id: str
    history: list[AssessmentHistoryItem]
    count: int


# ═══════════════════════════════════════════════════════════════════════
# THERAPY SESSION & CHAT SCHEMAS
# ═══════════════════════════════════════════════════════════════════════

class StartSessionRequest(BaseModel):
    user_id: str = Field(..., min_length=1)
    mode: str = Field(..., description="'chat' or 'voice'")
    objective: Optional[str] = Field(None, description="Optional session objective or topic")


class StartSessionResponse(BaseModel):
    session_id: int
    mode: str
    started_at: str
    current_stage: str = "opening"
    stage_label: str = "Opening Check-in"
    welcome_message: Optional[str] = None
    prior_summaries: list[dict] = Field(
        default_factory=list,
        description="Most recent 1–3 session summaries for continuity context"
    )


class ChatMessageRequest(BaseModel):
    session_id: int
    user_id: str = Field(..., min_length=1)
    message: str = Field(..., min_length=1, max_length=10000)


class ToolInvocation(BaseModel):
    tool_name: str
    tool_input: dict = Field(default_factory=dict)
    tool_output: str = ""


class ChatMessageResponse(BaseModel):
    session_id: int
    reply: str
    risk_tier: str = Field(..., description="Risk tier of the user's message: Low | Moderate | High")
    urgency_level: str = Field("STABLE", description="STABLE | WARNING | CRITICAL")
    crisis_activated: bool = Field(False, description="True if crisis protocol was triggered")
    current_stage: Optional[str] = None
    stage_label: Optional[str] = None
    main_concern: Optional[str] = None
    tools_used: list[ToolInvocation] = Field(
        default_factory=list,
        description="Deterministic CBT/crisis tools invoked by the LLM for this turn"
    )


class EndSessionRequest(BaseModel):
    session_id: int
    user_id: str = Field(..., min_length=1)


class SessionSummaryResponse(BaseModel):
    session_id: int
    summary_text: str
    concerns: list[str] = Field(default_factory=list)
    goals: list[str] = Field(default_factory=list)
    techniques_used: list[str] = Field(default_factory=list)
    key_insights: list[str] = Field(default_factory=list)
    action_steps: list[str] = Field(default_factory=list)


class UserSessionListResponse(BaseModel):
    sessions: list[dict] = Field(default_factory=list)


# ═══════════════════════════════════════════════════════════════════════
# VOICE THERAPY SCHEMAS
# ═══════════════════════════════════════════════════════════════════════

class VoiceTherapyResponse(BaseModel):
    session_id: int
    transcript: str = Field(..., description="Whisper-transcribed user speech")
    reply_text: str = Field(..., description="LLM reply text (voice-optimized: no markdown)")
    reply_audio_base64: Optional[str] = Field(
        None, description="Base64-encoded TTS audio (ElevenLabs) or null if TTS unavailable"
    )
    risk_tier: str
    urgency_level: str = "STABLE"
    crisis_activated: bool = False
    speech_emotion: Optional[str] = Field(None, description="Detected speech emotion from SER model")
    tools_used: list[ToolInvocation] = Field(default_factory=list)
