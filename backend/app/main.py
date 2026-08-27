"""
EmoCare FastAPI Backend — main.py

Multimodal Emotion-Aware AI system for early detection and support
of mental health distress using affective computing.

Endpoints:
  GET  /health                              — Server & model status
  POST /api/predict/text                    — Text distress analysis
  POST /api/predict/speech                  — Audio emotion detection
  POST /api/predict/behavioral              — Passive sensing risk analysis
  POST /api/predict/multimodal              — Full late fusion engine
  GET  /api/assessment/questions/{test_type} — PHQ-9 / GAD-7 questionnaire
  POST /api/assessment/submit               — Submit PHQ-9 / GAD-7 responses
  POST /api/therapy/session/start           — Start a therapy session
  POST /api/therapy/session/end             — End session & generate summary
  GET  /api/therapy/sessions/{user_id}      — List all user sessions
  GET  /api/therapy/session/{session_id}/messages — Get session messages
  POST /api/chat/message                    — Chat therapy turn
  POST /api/voice-therapy/interact          — Voice therapy turn
"""
import os
import logging
from contextlib import asynccontextmanager

# Auto-load .env from backend/ or root
try:
    from dotenv import load_dotenv
    backend_env = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".env"))
    root_env = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))
    if os.path.exists(backend_env):
        load_dotenv(backend_env)
    elif os.path.exists(root_env):
        load_dotenv(root_env)
    else:
        load_dotenv()
except ImportError:
    pass

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware


from .model_loader import models
from .schemas import (
    HealthResponse,
    TextRequest,
    TextResponse,
    SpeechResponse,
    BehavioralRequest,
    BehavioralResponse,
    MultimodalResponse,
    AssessmentSubmissionRequest,
    AssessmentResponse,
    StartSessionRequest,
    StartSessionResponse,
    ChatMessageRequest,
    ChatMessageResponse,
    EndSessionRequest,
    SessionSummaryResponse,
    UserSessionListResponse,
    VoiceTherapyResponse,
)
from .inference import predict_text, predict_speech, predict_behavioral, predict_multimodal
from .assessment import process_assessment, PHQ9_QUESTIONS, GAD7_QUESTIONS, RESPONSE_SCALE
from .db import (
    init_db,
    create_therapy_session,
    end_therapy_session,
    get_session_messages,
    get_recent_session_summaries,
    get_all_user_sessions,
)
from .therapy import process_chat_turn, generate_session_summary
from .engine.voice_therapy import process_voice_turn


# ── Logging ────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger("emocare")

# ── Model directory ────────────────────────────────────────────────────
MODELS_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "models"))


# ── Lifespan: load models & init DB on startup ────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Loading models from: {MODELS_ROOT}")
    models.load_all(MODELS_ROOT)
    init_db()
    logger.info("EmoCare backend ready.")
    yield
    logger.info("EmoCare backend shutting down.")



# ── FastAPI App ────────────────────────────────────────────────────────
app = FastAPI(
    title="EmoCare API",
    description=(
        "Multimodal Emotion-Aware AI system for early detection and support "
        "of mental health distress. Analyzes text, speech, and behavioral "
        "inputs to produce risk classifications with human-reviewed escalation alerts."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# ── CORS (allow Next.js frontend on localhost:3000) ────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ═══════════════════════════════════════════════════════════════════════
# ROUTES
# ═══════════════════════════════════════════════════════════════════════


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Server health check and model loading status."""
    return HealthResponse(
        status="ok",
        models_loaded=models.loaded_status,
    )


@app.post("/api/predict/text", response_model=TextResponse)
async def api_predict_text(request: TextRequest):
    """
    Analyze text for mental health distress risk.

    Returns risk tier (Low/Moderate/High) with probabilities,
    confidence score, and supplementary linguistic markers
    (first-person pronoun rate, absolutist language rate, negation density).
    """
    if not models.text_clf:
        raise HTTPException(status_code=503, detail="Text model not loaded")
    return predict_text(request.text)


@app.post("/api/predict/speech", response_model=SpeechResponse)
async def api_predict_speech(audio: UploadFile = File(...)):
    """
    Analyze uploaded audio file for speech emotion and risk tier.

    Accepts .wav, .mp3, .webm, .ogg audio files.
    Returns detected emotion, emotion probabilities, mapped risk tier,
    and prosodic features (pitch variance, speech rate, pause ratio).
    """
    if not models.speech_clf:
        raise HTTPException(status_code=503, detail="Speech model not loaded")

    content = await audio.read()
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Empty audio file")
    if len(content) > 10 * 1024 * 1024:  # 10 MB limit
        raise HTTPException(status_code=413, detail="Audio file too large (max 10 MB)")

    return predict_speech(content)


@app.post("/api/predict/behavioral", response_model=BehavioralResponse)
async def api_predict_behavioral(request: BehavioralRequest):
    """
    Analyze self-reported behavioral metrics for risk tier prediction.

    Accepts sleep, activity, social, stress, exercise, and mood ratings.
    All fields are optional — missing fields default to neutral values.
    """
    if not models.behavioral_clf:
        raise HTTPException(status_code=503, detail="Behavioral model not loaded")
    return predict_behavioral(request)


@app.post("/api/predict/multimodal", response_model=MultimodalResponse)
async def api_predict_multimodal(
    text: str = Form(default=None),
    audio: UploadFile = File(default=None),
    sleep_hours: float = Form(default=None),
    sleep_quality: float = Form(default=None),
    activity_level: float = Form(default=None),
    social_interaction: float = Form(default=None),
    stress_level: float = Form(default=None),
    exercise_minutes: float = Form(default=None),
    mood_rating: float = Form(default=None),
):
    """
    Full multimodal late fusion analysis.

    Accepts any combination of text, audio file, and behavioral metrics.
    At least one modality must be provided.

    Returns:
    - Final fused risk tier with probabilities
    - Cross-modal agreement score (flags when modalities disagree)
    - Human escalation trigger with urgency level
    - Personalized coping recommendations (CBT-based, rule-driven)
    - Per-modality breakdown
    """
    audio_bytes = None
    behavioral = None

    if audio is not None:
        audio_bytes = await audio.read()
        if len(audio_bytes) == 0:
            audio_bytes = None

    # Build behavioral request if any behavioral field is provided
    behavioral_fields = {
        "sleep_hours": sleep_hours,
        "sleep_quality": sleep_quality,
        "activity_level": activity_level,
        "social_interaction": social_interaction,
        "stress_level": stress_level,
        "exercise_minutes": exercise_minutes,
        "mood_rating": mood_rating,
    }
    if any(v is not None for v in behavioral_fields.values()):
        behavioral = BehavioralRequest(**behavioral_fields)

    # At least one modality required
    if not text and audio_bytes is None and behavioral is None:
        raise HTTPException(
            status_code=400,
            detail="At least one modality (text, audio, or behavioral) must be provided",
        )

    return predict_multimodal(text=text, audio_bytes=audio_bytes, behavioral=behavioral)


# ═══════════════════════════════════════════════════════════════════════
# SELF-ASSESSMENT ROUTES (PHQ-9 & GAD-7)
# ═══════════════════════════════════════════════════════════════════════


@app.get("/api/assessment/questions/{test_type}")
async def get_assessment_questions(test_type: str):
    """
    Get questionnaire items and scoring scales for PHQ-9 or GAD-7.
    """
    test_type_clean = test_type.lower().strip().replace("-", "")
    if test_type_clean == "phq9":
        return {
            "test_type": "phq9",
            "title": "PHQ-9 (Depression Screening)",
            "timeframe": "Over the last 2 weeks, how often have you been bothered by any of the following problems?",
            "scale": RESPONSE_SCALE,
            "questions": PHQ9_QUESTIONS,
        }
    elif test_type_clean == "gad7":
        return {
            "test_type": "gad7",
            "title": "GAD-7 (Anxiety Screening)",
            "timeframe": "Over the last 2 weeks, how often have you been bothered by the following problems?",
            "scale": RESPONSE_SCALE,
            "questions": GAD7_QUESTIONS,
        }
    else:
        raise HTTPException(
            status_code=400,
            detail="Invalid test_type. Supported types: 'phq9', 'gad7'",
        )


@app.post("/api/assessment/submit", response_model=AssessmentResponse)
async def submit_assessment(request: AssessmentSubmissionRequest):
    """
    Submit PHQ-9 or GAD-7 responses, calculate total score, map severity band & risk tier,
    store to PostgreSQL, and return evaluation summary.
    """
    try:
        result = process_assessment(
            user_id=request.user_id,
            test_type=request.test_type,
            responses=request.responses,
        )
        return AssessmentResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Assessment evaluation failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error evaluating assessment")


# ═══════════════════════════════════════════════════════════════════════
# THERAPY SESSION ROUTES
# ═══════════════════════════════════════════════════════════════════════


@app.post("/api/therapy/session/start", response_model=StartSessionResponse)
async def start_therapy_session(request: StartSessionRequest):
    """
    Start a new therapy session (chat or voice).

    Returns session ID and the user's most recent session summaries
    for continuity context display on the frontend.
    """
    session_id = create_therapy_session(
        user_id=request.user_id,
        mode=request.mode,
        objective=request.objective,
    )
    if session_id is None:
        raise HTTPException(status_code=500, detail="Failed to create therapy session")

    # Load prior session summaries for continuity banner
    prior_summaries = get_recent_session_summaries(request.user_id, limit=3)

    from datetime import datetime, timezone
    return StartSessionResponse(
        session_id=session_id,
        mode=request.mode,
        started_at=datetime.now(timezone.utc).isoformat(),
        prior_summaries=prior_summaries,
    )


@app.post("/api/therapy/session/end", response_model=SessionSummaryResponse)
async def end_therapy_session_route(request: EndSessionRequest):
    """
    End a therapy session: mark as ended, generate structured summary,
    and persist it to session_summaries for future memory context.
    """
    # Mark session as ended
    ended = end_therapy_session(request.session_id)
    if not ended:
        raise HTTPException(status_code=500, detail="Failed to end therapy session")

    # Generate and persist summary
    summary = await generate_session_summary(
        session_id=request.session_id,
        user_id=request.user_id,
    )

    return SessionSummaryResponse(**summary)


@app.get("/api/therapy/sessions/{user_id}", response_model=UserSessionListResponse)
async def list_user_sessions(user_id: str):
    """
    List all therapy sessions for a user (with summaries if available).
    Used by the /insights page to display session history.
    """
    sessions = get_all_user_sessions(user_id)
    return UserSessionListResponse(sessions=sessions)


@app.get("/api/therapy/session/{session_id}/messages")
async def get_session_messages_route(session_id: int):
    """
    Retrieve all messages for a specific therapy session.
    Returns messages in chronological order.
    """
    messages = get_session_messages(session_id)
    return {"session_id": session_id, "messages": messages}


# ═══════════════════════════════════════════════════════════════════════
# CHAT THERAPY ROUTE
# ═══════════════════════════════════════════════════════════════════════


@app.post("/api/chat/message", response_model=ChatMessageResponse)
async def chat_therapy_message(request: ChatMessageRequest):
    """
    Process a single chat therapy turn.

    Safety pipeline:
    1. Classifies user text for risk BEFORE the LLM sees it
    2. If High/Critical → bypasses LLM, returns deterministic crisis protocol
    3. Otherwise → invokes LLM with tool-calling access to CBT catalog
    """
    result = await process_chat_turn(
        session_id=request.session_id,
        user_id=request.user_id,
        user_message=request.message,
        mode="chat",
    )

    return ChatMessageResponse(
        session_id=result["session_id"],
        reply=result["reply"],
        risk_tier=result["risk_tier"],
        urgency_level=result.get("urgency_level", "STABLE"),
        crisis_activated=result.get("crisis_activated", False),
        tools_used=result.get("tools_used", []),
    )


# ═══════════════════════════════════════════════════════════════════════
# VOICE THERAPY ROUTE
# ═══════════════════════════════════════════════════════════════════════


@app.post("/api/voice-therapy/interact", response_model=VoiceTherapyResponse)
async def voice_therapy_interact(
    session_id: int = Form(...),
    user_id: str = Form(...),
    audio: UploadFile = File(...),
):
    """
    Full voice therapy pipeline:

    1. Receives audio from the user
    2. Parallel processing: Whisper STT + SER acoustic emotion analysis
    3. Text risk classification on transcript
    4. Multimodal safety gate (acoustic OR text risk High → crisis protocol)
    5. Voice-mode LLM response (no markdown, spoken cadence)
    6. ElevenLabs TTS on reply → base64 audio
    """
    # Read and validate audio
    audio_bytes = await audio.read()
    if len(audio_bytes) == 0:
        raise HTTPException(status_code=400, detail="Empty audio file")
    if len(audio_bytes) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Audio file too large (max 10 MB)")

    result = await process_voice_turn(
        session_id=session_id,
        user_id=user_id,
        audio_bytes=audio_bytes,
    )

    return VoiceTherapyResponse(
        session_id=result["session_id"],
        transcript=result["transcript"],
        reply_text=result["reply_text"],
        reply_audio_base64=result.get("reply_audio_base64"),
        risk_tier=result["risk_tier"],
        urgency_level=result.get("urgency_level", "STABLE"),
        crisis_activated=result.get("crisis_activated", False),
        speech_emotion=result.get("speech_emotion"),
        tools_used=result.get("tools_used", []),
    )
