"""
EmoCare FastAPI Backend — main.py

Multimodal Emotion-Aware AI system for early detection and support
of mental health distress using affective computing.

Endpoints:
  GET  /health                  — Server & model status
  POST /api/predict/text        — Text distress analysis
  POST /api/predict/speech      — Audio emotion detection
  POST /api/predict/behavioral  — Passive sensing risk analysis
  POST /api/predict/multimodal  — Full late fusion engine
"""
import os
import logging
from contextlib import asynccontextmanager

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
)
from .inference import predict_text, predict_speech, predict_behavioral, predict_multimodal

# ── Logging ────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger("emocare")

# ── Model directory ────────────────────────────────────────────────────
MODELS_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "models"))


# ── Lifespan: load models on startup ──────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Loading models from: {MODELS_ROOT}")
    models.load_all(MODELS_ROOT)
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
