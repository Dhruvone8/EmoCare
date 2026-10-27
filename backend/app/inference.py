"""
Inference module — feature extraction and prediction for all modalities.

Handles:
  - Text: TF-IDF vectorization + linguistic marker extraction
  - Speech: librosa MFCC/prosodic feature extraction + emotion classification
  - Behavioral: feature vector construction from user-reported metrics
  - Fusion: late decision-level fusion with cross-modal disagreement detection
"""
import os
import io
import re
import logging
import tempfile
from typing import Optional

import numpy as np
import librosa

from .model_loader import models
from .schemas import (
    RiskProbabilities,
    LinguisticMarkers,
    TextResponse,
    SpeechResponse,
    SpeechEmotionDetail,
    BehavioralRequest,
    BehavioralResponse,
    MultimodalResponse,
    ModalityBreakdown,
)
from .recommendations import get_coping_recommendations
from .safety import has_acute_distress_signal

logger = logging.getLogger("emocare.inference")

LABEL_MAP = {0: "Low", 1: "Moderate", 2: "High"}
RISK_TO_IDX = {"Low": 0, "Moderate": 1, "High": 2}
URGENCY_RANK = {"STABLE": 0, "WARNING": 1, "CRITICAL": 2}
RANK_TO_URGENCY = {0: "STABLE", 1: "WARNING", 2: "CRITICAL"}
HIGH_RISK_THRESHOLD = 0.20
MODERATE_RISK_THRESHOLD = 0.35

# ── Linguistic marker word lists (DSM-5 / clinical NLP literature) ─────
FIRST_PERSON_PRONOUNS = {"i", "me", "my", "mine", "myself", "we", "us", "our", "ours"}
ABSOLUTIST_WORDS = {
    "always", "never", "completely", "totally", "absolutely", "entirely",
    "nothing", "everything", "everyone", "nobody", "all", "none",
    "definitely", "certainly", "constantly", "forever", "impossible",
}
NEGATION_WORDS = {
    "not", "no", "never", "neither", "nor", "nobody", "nothing",
    "nowhere", "don't", "doesn't", "didn't", "won't", "wouldn't",
    "can't", "cannot", "couldn't", "shouldn't", "isn't", "aren't",
    "wasn't", "weren't", "hasn't", "haven't", "hadn't",
}


# ═══════════════════════════════════════════════════════════════════════
# TEXT INFERENCE
# ═══════════════════════════════════════════════════════════════════════

def _extract_linguistic_markers(text: str) -> LinguisticMarkers:
    """Extract supplementary linguistic distress markers from raw text."""
    words = re.findall(r"[a-z']+", text.lower())
    n = max(len(words), 1)
    return LinguisticMarkers(
        first_person_rate=round(sum(1 for w in words if w in FIRST_PERSON_PRONOUNS) / n, 4),
        absolutist_rate=round(sum(1 for w in words if w in ABSOLUTIST_WORDS) / n, 4),
        negation_rate=round(sum(1 for w in words if w in NEGATION_WORDS) / n, 4),
        word_count=len(words),
    )


def _ordered_text_probabilities(raw_probs: np.ndarray) -> np.ndarray:
    if len(raw_probs) != 3:
        raise ValueError("Text classifier must output probabilities for three risk tiers")

    classes = getattr(models.text_clf, "classes_", None)
    if classes is None:
        return np.asarray(raw_probs, dtype=float)

    ordered: dict[str, float] = {}
    for index, label in enumerate(classes):
        if isinstance(label, (int, np.integer)):
            tier = LABEL_MAP.get(int(label))
        else:
            label_text = str(label)
            tier = LABEL_MAP.get(int(label_text)) if label_text.isdigit() else label_text.title()
        if tier in RISK_TO_IDX:
            ordered[tier] = float(raw_probs[index])

    if len(ordered) != 3:
        logger.warning("Unrecognized text classifier classes; using positional risk probabilities")
        return np.asarray(raw_probs, dtype=float)
    return np.array([ordered["Low"], ordered["Moderate"], ordered["High"]])


def _select_text_risk_tier(text: str, probs: np.ndarray) -> str:
    p_low, p_mod, p_high = (float(value) for value in probs)
    if p_high >= HIGH_RISK_THRESHOLD or has_acute_distress_signal(text):
        return "High"
    if p_mod >= MODERATE_RISK_THRESHOLD or (p_high + p_mod) >= 0.50:
        return "Moderate"
    return "Low"


def predict_text(text: str) -> TextResponse:
    """Run calibrated TF-IDF risk classification and linguistic marker extraction."""
    if models.tfidf_vectorizer is None or models.text_clf is None:
        models_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "models"))
        if os.path.exists(models_root):
            models.load_all(models_root)

    if models.tfidf_vectorizer is not None and models.text_clf is not None:
        feat = models.tfidf_vectorizer.transform([text])
        raw_probs = models.text_clf.predict_proba(feat)[0]
        probs = _ordered_text_probabilities(raw_probs)
    else:
        probs = np.array([0.9, 0.08, 0.02])

    predicted_tier = _select_text_risk_tier(text, probs)
    confidence = float(probs[RISK_TO_IDX[predicted_tier]])
    return TextResponse(
        predicted_risk_tier=predicted_tier,
        probabilities=RiskProbabilities(
            Low=float(probs[0]),
            Moderate=float(probs[1]),
            High=float(probs[2]),
        ),
        confidence=round(confidence, 4),
        linguistic_markers=_extract_linguistic_markers(text),
    )


# ═══════════════════════════════════════════════════════════════════════
# SPEECH INFERENCE
# ═══════════════════════════════════════════════════════════════════════

def _load_audio_waveform(audio_bytes: bytes, max_duration: float = 5.0) -> tuple[np.ndarray, int]:
    """
    Fast audio loader: decodes in-memory via soundfile when possible,
    falling back to librosa tempfile for webm/ogg/mp4. Clamps duration.
    """
    target_sr = 22050
    # Try fast in-memory decoding with soundfile first
    try:
        import soundfile as sf
        y, sr = sf.read(io.BytesIO(audio_bytes), dtype="float32")
        if y.ndim > 1:
            y = np.mean(y, axis=1)
        if sr != target_sr:
            y = librosa.resample(y, orig_sr=sr, target_sr=target_sr)
            sr = target_sr
        max_samples = int(max_duration * sr)
        if len(y) > max_samples:
            y = y[:max_samples]
        return y, sr
    except Exception:
        pass

    # Fallback to temp file with librosa (e.g. for webm/opus containers)
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp.write(audio_bytes)
        tmp_path = tmp.name

    try:
        y, sr = librosa.load(tmp_path, sr=target_sr, duration=max_duration)
        return y, sr
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def _extract_speech_features(y: np.ndarray, sr: int = 22050) -> dict[str, float]:
    """
    Extract all 95 acoustic features matching the trained speech emotion model.

    Feature breakdown (must match models.speech_feature_columns exactly):
      - mfcc_0_mean..mfcc_39_std  : 40 MFCCs × 2 stats = 80 features
      - pitch_mean, pitch_std, pitch_range : 3 features
      - rms_mean, rms_std                 : 2 features
      - zcr_mean, zcr_std                 : 2 features
      - spectral_centroid_mean/std        : 2 features
      - spectral_bandwidth_mean           : 1 feature
      - spectral_rolloff_mean             : 1 feature
      - chroma_mean, chroma_std           : 2 features (aggregated across all 12 bands)
      - duration_s                        : 1 feature
      - pause_ratio                       : 1 feature
                                    Total = 95 features
    """
    features: dict[str, float] = {}

    # ── 40 MFCCs (mean + std each) ──
    mfccs = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=40)
    for i in range(40):
        features[f"mfcc_{i}_mean"] = float(np.mean(mfccs[i]))
        features[f"mfcc_{i}_std"] = float(np.std(mfccs[i]))

    # ── Pitch (F0 via YIN) ──
    try:
        f0 = librosa.yin(y, fmin=65, fmax=2093, sr=sr)
        f0_valid = f0[~np.isnan(f0)]
        if len(f0_valid) > 0:
            features["pitch_mean"] = float(np.mean(f0_valid))
            features["pitch_std"] = float(np.std(f0_valid))
            features["pitch_range"] = float(np.max(f0_valid) - np.min(f0_valid))
        else:
            features["pitch_mean"] = 0.0
            features["pitch_std"] = 0.0
            features["pitch_range"] = 0.0
    except Exception:
        features["pitch_mean"] = 0.0
        features["pitch_std"] = 0.0
        features["pitch_range"] = 0.0

    # ── RMS Energy ──
    rms = librosa.feature.rms(y=y)[0]
    features["rms_mean"] = float(np.mean(rms))
    features["rms_std"] = float(np.std(rms))

    # ── Zero Crossing Rate ──
    zcr = librosa.feature.zero_crossing_rate(y)[0]
    features["zcr_mean"] = float(np.mean(zcr))
    features["zcr_std"] = float(np.std(zcr))

    # ── Spectral Centroid ──
    centroid = librosa.feature.spectral_centroid(y=y, sr=sr)[0]
    features["spectral_centroid_mean"] = float(np.mean(centroid))
    features["spectral_centroid_std"] = float(np.std(centroid))

    # ── Spectral Bandwidth ──
    bandwidth = librosa.feature.spectral_bandwidth(y=y, sr=sr)[0]
    features["spectral_bandwidth_mean"] = float(np.mean(bandwidth))

    # ── Spectral Rolloff ──
    rolloff = librosa.feature.spectral_rolloff(y=y, sr=sr)[0]
    features["spectral_rolloff_mean"] = float(np.mean(rolloff))

    # ── Chroma (aggregated across all 12 bands) ──
    chroma = librosa.feature.chroma_stft(y=y, sr=sr)
    features["chroma_mean"] = float(np.mean(chroma))
    features["chroma_std"] = float(np.std(chroma))

    # ── Duration ──
    features["duration_s"] = float(len(y) / max(sr, 1))

    # ── Pause Ratio (fraction of silent frames) ──
    silence_threshold = 0.01
    features["pause_ratio"] = float(np.mean(rms < silence_threshold))

    return features


def _extract_prosodic_features(y: np.ndarray, sr: int = 22050) -> dict[str, float]:
    """Extract fast prosodic features for voice therapy display (not used in model prediction)."""
    # Fast pitch via autocorrelation/yin
    try:
        f0 = librosa.yin(y, fmin=65, fmax=2093, sr=sr)
        f0_valid = f0[~np.isnan(f0)]
        pitch_mean = float(np.mean(f0_valid)) if len(f0_valid) > 0 else 0.0
        pitch_variance = float(np.var(f0_valid)) if len(f0_valid) > 0 else 0.0
    except Exception:
        pitch_mean, pitch_variance = 0.0, 0.0

    # Speech rate proxy: number of onsets per second
    onset_frames = librosa.onset.onset_detect(y=y, sr=sr)
    duration = len(y) / sr
    speech_rate = float(len(onset_frames) / max(duration, 0.01))

    # Pause ratio: fraction of frames that are silent
    rms = librosa.feature.rms(y=y)[0]
    silence_threshold = 0.01
    pause_ratio = float(np.mean(rms < silence_threshold))

    return {
        "pitch_mean_hz": round(pitch_mean, 2),
        "pitch_variance": round(pitch_variance, 2),
        "speech_rate_onsets_per_sec": round(speech_rate, 2),
        "pause_ratio": round(pause_ratio, 4),
    }


def predict_speech(audio_bytes: bytes, include_prosodic: bool = True) -> SpeechResponse:
    """Extract MFCC features from audio, classify emotion, map to risk tier."""
    if not models.speech_clf or not models.speech_scaler or not models.speech_imputer:
        return SpeechResponse(
            predicted_risk_tier="Low",
            probabilities=RiskProbabilities(Low=0.8, Moderate=0.15, High=0.05),
            emotion_detail=SpeechEmotionDetail(
                detected_emotion="neutral",
                emotion_confidence=0.8,
                emotion_probabilities={"neutral": 0.8, "calm": 0.2},
            ),
            prosodic_features={
                "pitch_mean_hz": 0.0,
                "pitch_variance": 0.0,
                "speech_rate_onsets_per_sec": 0.0,
                "pause_ratio": 0.0,
            },
        )

    # Fast in-memory audio load (capped at 5s duration)
    y, sr = _load_audio_waveform(audio_bytes, max_duration=5.0)

    # Extract features from decoded audio
    raw_features = _extract_speech_features(y, sr)

    # Align to training feature columns
    feature_cols = models.speech_feature_columns
    feature_vector = np.array([[raw_features.get(col, 0.0) for col in feature_cols]])

    # Impute → Scale → Predict
    feature_vector = models.speech_imputer.transform(feature_vector)
    feature_vector = models.speech_scaler.transform(feature_vector)
    emotion_probs = models.speech_clf.predict_proba(feature_vector)[0]
    pred_emotion_idx = int(np.argmax(emotion_probs))
    pred_emotion = models.speech_label_encoder.inverse_transform([pred_emotion_idx])[0]

    # Map emotion → risk tier
    risk_tier = models.emotion_to_risk_map.get(pred_emotion, "Moderate")
    risk_idx = RISK_TO_IDX[risk_tier]

    # Build risk probability from emotion probabilities
    risk_probs = np.zeros(3)
    for i, emotion in enumerate(models.speech_classes):
        r = models.emotion_to_risk_map.get(emotion, "Moderate")
        risk_probs[RISK_TO_IDX[r]] += emotion_probs[i]

    # Normalize
    risk_probs = risk_probs / max(risk_probs.sum(), 1e-8)

    # Prosodic features (skipped during voice assistant turns for ultra-low latency)
    if include_prosodic:
        prosodic = _extract_prosodic_features(y, sr)
    else:
        prosodic = {
            "pitch_mean_hz": 0.0,
            "pitch_variance": 0.0,
            "speech_rate_onsets_per_sec": 0.0,
            "pause_ratio": 0.0,
        }

    # Emotion probabilities dict
    emotion_prob_dict = {
        models.speech_classes[i]: round(float(emotion_probs[i]), 4)
        for i in range(len(models.speech_classes))
    }

    return SpeechResponse(
        predicted_risk_tier=risk_tier,
        probabilities=RiskProbabilities(
            Low=round(float(risk_probs[0]), 4),
            Moderate=round(float(risk_probs[1]), 4),
            High=round(float(risk_probs[2]), 4),
        ),
        emotion_detail=SpeechEmotionDetail(
            detected_emotion=pred_emotion,
            emotion_confidence=round(float(np.max(emotion_probs)), 4),
            emotion_probabilities=emotion_prob_dict,
        ),
        prosodic_features=prosodic,
    )


# ═══════════════════════════════════════════════════════════════════════
# BEHAVIORAL INFERENCE
# ═══════════════════════════════════════════════════════════════════════

def predict_behavioral(req: BehavioralRequest) -> BehavioralResponse:
    """
    Predict risk tier from self-reported behavioral metrics.

    Uses a calibrated lifestyle distress index instead of zero-padding
    into the 50-feature StudentLife sensor model. Each survey dimension
    is mapped to a 0-1 distress contribution, then aggregated into
    softmax-normalized risk probabilities.
    """
    # Extract values with neutral defaults
    sleep_hours = req.sleep_hours if req.sleep_hours is not None else 7.0
    sleep_quality = req.sleep_quality if req.sleep_quality is not None else 3.0
    activity_level = req.activity_level if req.activity_level is not None else 3.0
    social_interaction = req.social_interaction if req.social_interaction is not None else 3.0
    stress_level = req.stress_level if req.stress_level is not None else 3.0
    exercise_minutes = req.exercise_minutes if req.exercise_minutes is not None else 30.0
    mood_rating = req.mood_rating if req.mood_rating is not None else 3.0

    # ── Compute individual distress contributions (each 0.0 – 1.0) ──
    # Sleep deficit: less sleep → higher distress (7h baseline, 3h floor)
    sleep_deficit = np.clip((7.0 - sleep_hours) / 4.0, 0.0, 1.0)
    # Sleep quality: lower quality → higher distress
    sleep_quality_distress = np.clip((5.0 - sleep_quality) / 4.0, 0.0, 1.0)
    # Stress: higher → worse
    stress_distress = np.clip((stress_level - 1.0) / 4.0, 0.0, 1.0)
    # Mood: lower → worse
    mood_distress = np.clip((5.0 - mood_rating) / 4.0, 0.0, 1.0)
    # Social isolation: lower interaction → worse
    social_distress = np.clip((5.0 - social_interaction) / 4.0, 0.0, 1.0)
    # Activity: lower → worse
    activity_distress = np.clip((5.0 - activity_level) / 4.0, 0.0, 1.0)
    # Exercise: less than 20min → increasing distress
    exercise_distress = np.clip((20.0 - min(exercise_minutes, 60.0)) / 20.0, 0.0, 1.0)

    # ── Weighted aggregate distress score ──
    # Weights reflect clinical significance (stress and mood most predictive)
    weights = {
        "stress": 0.25,
        "mood": 0.20,
        "sleep_deficit": 0.15,
        "sleep_quality": 0.10,
        "social": 0.12,
        "activity": 0.08,
        "exercise": 0.10,
    }
    distress_score = (
        weights["stress"] * stress_distress
        + weights["mood"] * mood_distress
        + weights["sleep_deficit"] * sleep_deficit
        + weights["sleep_quality"] * sleep_quality_distress
        + weights["social"] * social_distress
        + weights["activity"] * activity_distress
        + weights["exercise"] * exercise_distress
    )

    # ── Map to risk probabilities via softmax-like transformation ──
    # Scale distress_score (0-1) into logits for [Low, Moderate, High]
    # At distress=0: strongly Low; at distress=1: strongly High
    temperature = 3.0
    logits = np.array([
        temperature * (1.0 - distress_score),   # Low logit
        temperature * 0.5,                       # Moderate baseline
        temperature * distress_score,            # High logit
    ])
    exp_logits = np.exp(logits - np.max(logits))  # numerical stability
    probs = exp_logits / exp_logits.sum()

    pred_idx = int(np.argmax(probs))

    return BehavioralResponse(
        predicted_risk_tier=LABEL_MAP[pred_idx],
        probabilities=RiskProbabilities(
            Low=round(float(probs[0]), 4),
            Moderate=round(float(probs[1]), 4),
            High=round(float(probs[2]), 4),
        ),
    )


# ═══════════════════════════════════════════════════════════════════════
# MULTIMODAL FUSION
# ═══════════════════════════════════════════════════════════════════════

def _compute_cross_modal_agreement(modality_tiers: list[str]) -> float:
    """
    Compute agreement score between available modalities.
    1.0 = all agree, 0.0 = all different.
    """
    if len(modality_tiers) <= 1:
        return 1.0
    n = len(modality_tiers)
    # Pairwise agreement
    agreements = sum(1 for i in range(n) for j in range(i + 1, n) if modality_tiers[i] == modality_tiers[j])
    total_pairs = n * (n - 1) / 2
    return round(agreements / max(total_pairs, 1), 4)


def predict_multimodal(
    text: Optional[str] = None,
    audio_bytes: Optional[bytes] = None,
    behavioral: Optional[BehavioralRequest] = None,
) -> MultimodalResponse:
    """
    Run all available modalities, fuse via weighted late fusion across
    only the modalities that are present, check cross-modal agreement,
    and generate escalation + coping output.

    Modality weights (normalized across available inputs):
      - Text:       0.45 (most clinically predictive for distress screening)
      - Speech:     0.35 (prosodic/emotional cues)
      - Behavioral: 0.20 (self-reported lifestyle survey)
    """
    text_result: Optional[TextResponse] = None
    speech_result: Optional[SpeechResponse] = None
    behavioral_result: Optional[BehavioralResponse] = None

    # Canonical modality weights (will be normalized across available modalities)
    MODALITY_WEIGHTS = {"text": 0.45, "speech": 0.35, "behavioral": 0.20}

    # Collect probability vectors and weights only from available modalities
    available_probs: list[tuple[str, np.ndarray, float]] = []
    modality_tiers: list[str] = []
    detected_emotion: Optional[str] = None

    # ── Run available modalities ──
    if text and models.text_clf is not None:
        text_result = predict_text(text)
        p = text_result.probabilities
        text_probs = np.array([p.Low, p.Moderate, p.High])
        available_probs.append(("text", text_probs, MODALITY_WEIGHTS["text"]))
        modality_tiers.append(text_result.predicted_risk_tier)

    if audio_bytes and models.speech_clf is not None:
        speech_result = predict_speech(audio_bytes)
        p = speech_result.probabilities
        speech_probs = np.array([p.Low, p.Moderate, p.High])
        available_probs.append(("speech", speech_probs, MODALITY_WEIGHTS["speech"]))
        modality_tiers.append(speech_result.predicted_risk_tier)
        detected_emotion = speech_result.emotion_detail.detected_emotion

    if behavioral:
        behavioral_result = predict_behavioral(behavioral)
        p = behavioral_result.probabilities
        behavioral_probs = np.array([p.Low, p.Moderate, p.High])
        available_probs.append(("behavioral", behavioral_probs, MODALITY_WEIGHTS["behavioral"]))
        modality_tiers.append(behavioral_result.predicted_risk_tier)

    # ── Weighted Fusion (only available modalities) ──
    if len(available_probs) == 0:
        # No modalities provided — return uniform uncertainty
        fusion_probs = np.array([1 / 3, 1 / 3, 1 / 3])
    elif len(available_probs) == 1:
        # Single modality: use its probability vector directly
        _, fusion_probs, _ = available_probs[0]
    else:
        # Multi-modality: weighted average, normalized across available weights
        total_weight = sum(w for _, _, w in available_probs)
        fusion_probs = np.zeros(3)
        for _, probs, weight in available_probs:
            fusion_probs += (weight / total_weight) * probs

    pred_idx = int(np.argmax(fusion_probs))
    final_tier = LABEL_MAP[pred_idx]
    confidence = float(np.max(fusion_probs))

    # ── Cross-modal agreement check ──
    agreement = _compute_cross_modal_agreement(modality_tiers)

    # ── Low-confidence / disagreement flag ──
    # Flag when: confidence < 0.5 OR cross-modal agreement < 0.5
    low_confidence_flag = confidence < 0.5 or agreement < 0.5

    # ── Escalation logic ──
    high_risk_prob = float(fusion_probs[2])
    HIGH_RISK_THRESHOLD = 0.35
    escalate = high_risk_prob >= HIGH_RISK_THRESHOLD

    if high_risk_prob >= 0.6:
        urgency = "CRITICAL"
    elif escalate:
        urgency = "WARNING"
    else:
        urgency = "STABLE"

    # Override: if low confidence flag is set, escalate for human review
    if low_confidence_flag and not escalate:
        escalate = True
        urgency = RANK_TO_URGENCY[max(URGENCY_RANK.get(urgency, 0), URGENCY_RANK["WARNING"])]

    # ── Coping recommendations ──
    recommendations = get_coping_recommendations(
        risk_tier=final_tier,
        detected_emotion=detected_emotion,
        urgency_level=urgency,
    )

    return MultimodalResponse(
        final_risk_tier=final_tier,
        probabilities=RiskProbabilities(
            Low=round(float(fusion_probs[0]), 4),
            Moderate=round(float(fusion_probs[1]), 4),
            High=round(float(fusion_probs[2]), 4),
        ),
        confidence=round(confidence, 4),
        escalate_to_human_reviewer=escalate,
        urgency_level=urgency,
        cross_modal_agreement=agreement,
        low_confidence_flag=low_confidence_flag,
        coping_recommendations=recommendations,
        modality_breakdown=ModalityBreakdown(
            text=text_result,
            speech=speech_result,
            behavioral=behavioral_result,
        ),
    )
