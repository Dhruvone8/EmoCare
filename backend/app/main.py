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
  GET  /api/checkins/today                  — Get local-date check-in status
  POST /api/checkins                        — Save a daily check-in
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
from datetime import date
from typing import Optional
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

from fastapi import Depends, FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel


from .model_loader import models
from .schemas import (
    HealthResponse,
    TextRequest,
    TextResponse,
    SpeechResponse,
    BehavioralRequest,
    BehavioralResponse,
    MultimodalResponse,
    DailyCheckInRequest,
    DailyCheckInResponse,
    TodayCheckInResponse,
    AssessmentSubmissionRequest,
    AssessmentResponse,
    AssessmentHistoryResponse,
    AssessmentHistoryItem,
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
from .assessment import (
    process_assessment,
    process_assessment_async,
    PHQ9_QUESTIONS,
    GAD7_QUESTIONS,
    RESPONSE_SCALE,
    PHQ9_TIMEFRAME,
    GAD7_TIMEFRAME,
    FUNCTIONAL_DIFFICULTY_QUESTION,
    FUNCTIONAL_DIFFICULTY_OPTIONS,
    CLINICAL_DISCLAIMER,
)
from .db import (
    init_db,
    init_pg_pool,
    close_pg_pool,
    create_therapy_session,
    end_therapy_session,
    save_therapy_message,
    get_session_messages,
    get_recent_session_summaries,
    get_all_user_sessions,
    get_user_assessment_history,
    save_daily_checkin,
    get_daily_checkin,
)
from .therapy import process_chat_turn, generate_session_summary
from .engine.voice_therapy import process_voice_turn, generate_voice_greeting
from .auth import (
    AuthenticatedUser,
    create_guest_token,
    get_current_user,
    require_session_ownership,
    require_user_ownership,
)


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
    import asyncio
    from .engine.http_pool import warmup_connections, close_shared_client

    logger.info(f"Loading models from: {MODELS_ROOT}")
    models.load_all(MODELS_ROOT)
    init_db()
    # Initialize PostgreSQL connection pool (no-op if SQLite/no PG)
    init_pg_pool(minconn=1, maxconn=10)
    # Pre-warm HTTP connection pool in background for instant first voice turn
    asyncio.create_task(warmup_connections())
    logger.info("EmoCare backend ready.")
    yield
    close_pg_pool()
    await close_shared_client()
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


@app.post("/api/auth/guest")
async def issue_guest_token():
    """Issue a new server-generated identity for anonymous clinical sessions."""
    return create_guest_token()


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


@app.get("/api/checkins/today", response_model=TodayCheckInResponse)
async def get_today_daily_checkin(
    local_date: date,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """Return whether the authenticated user completed their local-date check-in."""
    try:
        check_in = get_daily_checkin(current_user.id, local_date)
    except Exception as e:
        logger.error(f"Daily check-in status unavailable: {e}")
        raise HTTPException(status_code=503, detail="Daily check-in is temporarily unavailable")

    return TodayCheckInResponse(
        local_date=local_date,
        completed=check_in is not None,
        check_in=DailyCheckInResponse(**check_in) if check_in else None,
    )


@app.post("/api/checkins", response_model=DailyCheckInResponse)
async def submit_daily_checkin(
    request: DailyCheckInRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """Save or update the authenticated user's check-in for their local calendar date."""
    try:
        check_in = save_daily_checkin(user_id=current_user.id, **request.model_dump())
    except Exception as e:
        logger.error(f"Daily check-in save unavailable: {e}")
        check_in = None
    if check_in is None:
        raise HTTPException(status_code=503, detail="Unable to save daily check-in right now")
    return DailyCheckInResponse(**check_in)


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
    Get validated questionnaire items, timeframes, response scales, and clinical instructions.
    """
    test_type_clean = test_type.lower().strip().replace("-", "")
    if test_type_clean == "phq9":
        return {
            "test_type": "phq9",
            "title": "PHQ-9 (Depression Screening)",
            "timeframe": PHQ9_TIMEFRAME,
            "scale": RESPONSE_SCALE,
            "questions": PHQ9_QUESTIONS,
            "functional_question": FUNCTIONAL_DIFFICULTY_QUESTION,
            "functional_options": FUNCTIONAL_DIFFICULTY_OPTIONS,
            "disclaimer": CLINICAL_DISCLAIMER,
        }
    elif test_type_clean == "gad7":
        return {
            "test_type": "gad7",
            "title": "GAD-7 (Anxiety Screening)",
            "timeframe": GAD7_TIMEFRAME,
            "scale": RESPONSE_SCALE,
            "questions": GAD7_QUESTIONS,
            "functional_question": FUNCTIONAL_DIFFICULTY_QUESTION,
            "functional_options": FUNCTIONAL_DIFFICULTY_OPTIONS,
            "disclaimer": CLINICAL_DISCLAIMER,
        }
    else:
        raise HTTPException(
            status_code=400,
            detail="Invalid test_type. Supported types: 'phq9', 'gad7'",
        )


@app.post("/api/assessment/submit", response_model=AssessmentResponse)
async def submit_assessment(
    request: AssessmentSubmissionRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Submit PHQ-9 or GAD-7 responses, calculate total score, map severity band & risk tier,
    evaluate clinical safety pathway, process contextual follow-up, persist attempt,
    and return evaluation summary with evidence-based next steps.
    """
    user_id = require_user_ownership(request.user_id, current_user)
    try:
        result = await process_assessment_async(
            user_id=user_id,
            test_type=request.test_type,
            responses=request.responses,
            follow_up_data=request.follow_up_data,
            safety_disclosure=request.safety_disclosure,
        )
        return AssessmentResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Assessment evaluation failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error evaluating assessment")


@app.get("/api/assessment/history/{user_id}", response_model=AssessmentHistoryResponse)
async def get_assessment_history(
    user_id: str,
    limit: int = 20,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """Retrieve the authenticated user's assessment history."""
    user_id = require_user_ownership(user_id, current_user)
    try:
        items = get_user_assessment_history(user_id=user_id, limit=limit)
        history_models = [AssessmentHistoryItem(**item) for item in items]
        return AssessmentHistoryResponse(
            user_id=user_id,
            history=history_models,
            count=len(history_models),
        )
    except Exception as e:
        logger.error(f"Failed to fetch assessment history for {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch assessment history")


# ═══════════════════════════════════════════════════════════════════════
# THERAPY SESSION ROUTES
# ═══════════════════════════════════════════════════════════════════════


@app.post("/api/therapy/session/start", response_model=StartSessionResponse)
async def start_therapy_session(
    request: StartSessionRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """Start an owned chat or voice therapy session."""
    user_id = require_user_ownership(request.user_id, current_user)
    session_id = create_therapy_session(
        user_id=user_id,
        mode=request.mode,
        objective=request.objective,
    )
    if session_id is None:
        raise HTTPException(status_code=500, detail="Failed to create therapy session")

    prior_summaries = []
    if not user_id.startswith("guest_"):
        prior_summaries = get_recent_session_summaries(user_id, limit=3)

    welcome_msg = (
        "Hi, it's good to have you here. What's been on your mind lately? "
        "We can take our time with whatever feels important to you today."
    )
    save_therapy_message(session_id, "assistant", welcome_msg)

    from datetime import datetime, timezone
    return StartSessionResponse(
        session_id=session_id,
        mode=request.mode,
        started_at=datetime.now(timezone.utc).isoformat(),
        current_stage="opening",
        stage_label="Opening Check-in",
        welcome_message=welcome_msg,
        prior_summaries=prior_summaries,
    )


@app.post("/api/therapy/session/end", response_model=SessionSummaryResponse)
async def end_therapy_session_route(
    request: EndSessionRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """End an owned session and generate its structured summary."""
    user_id = require_user_ownership(request.user_id, current_user)
    require_session_ownership(request.session_id, current_user)
    ended = end_therapy_session(request.session_id)
    if not ended:
        raise HTTPException(status_code=500, detail="Failed to end therapy session")

    summary = await generate_session_summary(
        session_id=request.session_id,
        user_id=user_id,
    )

    return SessionSummaryResponse(**summary)


@app.get("/api/therapy/sessions/{user_id}", response_model=UserSessionListResponse)
async def list_user_sessions(
    user_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """List the authenticated user's therapy sessions."""
    user_id = require_user_ownership(user_id, current_user)
    sessions = get_all_user_sessions(user_id)
    return UserSessionListResponse(sessions=sessions)


@app.get("/api/therapy/session/{session_id}/messages")
async def get_session_messages_route(
    session_id: int,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """Retrieve messages only from a session owned by the authenticated user."""
    require_session_ownership(session_id, current_user)
    messages = get_session_messages(session_id)
    return {"session_id": session_id, "messages": messages}


# ═══════════════════════════════════════════════════════════════════════
# CHAT THERAPY ROUTE
# ═══════════════════════════════════════════════════════════════════════


@app.post("/api/chat/message", response_model=ChatMessageResponse)
async def chat_therapy_message(
    request: ChatMessageRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """Process a chat turn only within the authenticated user's session."""
    user_id = require_user_ownership(request.user_id, current_user)
    require_session_ownership(request.session_id, current_user)
    result = await process_chat_turn(
        session_id=request.session_id,
        user_id=user_id,
        user_message=request.message,
        mode="chat",
    )

    return ChatMessageResponse(
        session_id=result["session_id"],
        reply=result["reply"],
        risk_tier=result["risk_tier"],
        urgency_level=result.get("urgency_level", "STABLE"),
        crisis_activated=result.get("crisis_activated", False),
        current_stage=result.get("current_stage"),
        stage_label=result.get("stage_label"),
        main_concern=result.get("main_concern"),
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
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """Process a voice turn only within the authenticated user's session."""
    user_id = require_user_ownership(user_id, current_user)
    require_session_ownership(session_id, current_user)
    audio_bytes = await audio.read()
    if len(audio_bytes) == 0:
        raise HTTPException(status_code=400, detail="Empty audio file")
    if len(audio_bytes) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Audio file too large (max 10 MB)")

    result = await process_voice_turn(
        session_id=session_id,
        user_id=user_id,
        audio_bytes=audio_bytes,
        filename=audio.filename or "audio.webm",
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


class VoiceGreetingRequest(BaseModel):
    session_id: int
    user_id: str
    time_of_day: Optional[str] = None


@app.post("/api/voice-therapy/greeting")
async def voice_therapy_greeting(
    request: VoiceGreetingRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """Generate a greeting only within the authenticated user's session."""
    user_id = require_user_ownership(request.user_id, current_user)
    require_session_ownership(request.session_id, current_user)
    return await generate_voice_greeting(
        session_id=request.session_id,
        user_id=user_id,
        time_of_day=request.time_of_day,
    )

