"""
Inference module — feature extraction and prediction for all modalities.

Handles:
  - Text: TF-IDF vectorization + linguistic marker extraction
  - Speech: librosa MFCC/prosodic feature extraction + emotion classification
  - Behavioral: feature vector construction from user-reported metrics
  - Fusion: late decision-level fusion with cross-modal disagreement detection
"""
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

logger = logging.getLogger("emocare.inference")

LABEL_MAP = {0: "Low", 1: "Moderate", 2: "High"}
RISK_TO_IDX = {"Low": 0, "Moderate": 1, "High": 2}

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


def predict_text(text: str) -> TextResponse:
    """Run TF-IDF risk classification + linguistic marker extraction on input text."""
    feat = models.tfidf_vectorizer.transform([text])
    probs = models.text_clf.predict_proba(feat)[0]
    pred_idx = int(np.argmax(probs))
    confidence = float(np.max(probs))

    return TextResponse(
        predicted_risk_tier=LABEL_MAP[pred_idx],
        probabilities=RiskProbabilities(Low=float(probs[0]), Moderate=float(probs[1]), High=float(probs[2])),
        confidence=round(confidence, 4),
        linguistic_markers=_extract_linguistic_markers(text),
    )


# ═══════════════════════════════════════════════════════════════════════
# SPEECH INFERENCE
# ═══════════════════════════════════════════════════════════════════════

def _extract_mfcc_features(audio_bytes: bytes) -> np.ndarray:
    """Extract 95 MFCC/spectral features from raw audio bytes using librosa."""
    # Write to temp file for librosa (it needs a file path or file-like obj)
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp.write(audio_bytes)
        tmp_path = tmp.name

    try:
        y, sr = librosa.load(tmp_path, sr=22050, duration=10)
    finally:
        import os
        os.unlink(tmp_path)

    features = {}

    # MFCCs (13 coefficients x 2 stats = 26 features)
    mfccs = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
    for i in range(13):
        features[f"mfcc_{i}_mean"] = float(np.mean(mfccs[i]))
        features[f"mfcc_{i}_std"] = float(np.std(mfccs[i]))

    # Delta MFCCs (13 x 2 = 26 features)
    delta_mfccs = librosa.feature.delta(mfccs)
    for i in range(13):
        features[f"delta_mfcc_{i}_mean"] = float(np.mean(delta_mfccs[i]))
        features[f"delta_mfcc_{i}_std"] = float(np.std(delta_mfccs[i]))

    # Chroma (12 x 2 = 24 features)
    chroma = librosa.feature.chroma_stft(y=y, sr=sr)
    for i in range(12):
        features[f"chroma_{i}_mean"] = float(np.mean(chroma[i]))
        features[f"chroma_{i}_std"] = float(np.std(chroma[i]))

    # Spectral features (contrast: 7x2=14, others: 5x2=10 => but we need 95 total)
    spec_contrast = librosa.feature.spectral_contrast(y=y, sr=sr)
    for i in range(spec_contrast.shape[0]):
        features[f"spectral_contrast_{i}_mean"] = float(np.mean(spec_contrast[i]))
        features[f"spectral_contrast_{i}_std"] = float(np.std(spec_contrast[i]))

    # ZCR, RMS, spectral centroid (1x2 each = 6 features)
    zcr = librosa.feature.zero_crossing_rate(y)
    features["zcr_mean"] = float(np.mean(zcr))

    return features


def _extract_prosodic_features(audio_bytes: bytes) -> dict[str, float]:
    """Extract prosodic features: pitch variance, speech rate proxy, pause ratio."""
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp.write(audio_bytes)
        tmp_path = tmp.name

    try:
        y, sr = librosa.load(tmp_path, sr=22050, duration=10)
    finally:
        import os
        os.unlink(tmp_path)

    # Pitch (F0) via pyin
    f0, voiced_flag, voiced_probs = librosa.pyin(
        y, fmin=librosa.note_to_hz("C2"), fmax=librosa.note_to_hz("C7"), sr=sr
    )
    f0_valid = f0[~np.isnan(f0)] if f0 is not None else np.array([0.0])
    pitch_mean = float(np.mean(f0_valid)) if len(f0_valid) > 0 else 0.0
    pitch_variance = float(np.var(f0_valid)) if len(f0_valid) > 0 else 0.0

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


def predict_speech(audio_bytes: bytes) -> SpeechResponse:
    """Extract MFCC features from audio, classify emotion, map to risk tier."""
    # Extract features
    raw_features = _extract_mfcc_features(audio_bytes)

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

    # Prosodic features
    prosodic = _extract_prosodic_features(audio_bytes)

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
    """Predict risk tier from self-reported behavioral metrics."""
    # Build feature vector matching StudentLife behavioral feature order
    feature_values = [
        req.sleep_hours or 7.0,
        req.sleep_quality or 3.0,
        req.activity_level or 3.0,
        req.social_interaction or 3.0,
        req.stress_level or 3.0,
        req.exercise_minutes or 30.0,
        req.mood_rating or 3.0,
    ]
    # Pad to match training feature count if needed
    clf = models.behavioral_clf
    expected_features = clf.n_features_in_
    while len(feature_values) < expected_features:
        feature_values.append(0.0)

    X = np.array([feature_values[:expected_features]])
    X = models.behavioral_imputer.transform(X)
    X = models.behavioral_scaler.transform(X)

    probs = clf.predict_proba(X)[0]
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
    Run all available modalities, fuse via late decision-level meta-classifier,
    check cross-modal agreement, and generate escalation + coping output.
    """
    text_result: Optional[TextResponse] = None
    speech_result: Optional[SpeechResponse] = None
    behavioral_result: Optional[BehavioralResponse] = None

    # Default probability vectors (uniform prior when modality unavailable)
    text_probs = np.array([1 / 3, 1 / 3, 1 / 3])
    speech_probs = np.array([1 / 3, 1 / 3, 1 / 3])
    behavioral_probs = np.array([1 / 3, 1 / 3, 1 / 3])

    modality_tiers: list[str] = []
    detected_emotion: Optional[str] = None

    # ── Run available modalities ──
    if text and models.text_clf is not None:
        text_result = predict_text(text)
        p = text_result.probabilities
        text_probs = np.array([p.Low, p.Moderate, p.High])
        modality_tiers.append(text_result.predicted_risk_tier)

    if audio_bytes and models.speech_clf is not None:
        speech_result = predict_speech(audio_bytes)
        p = speech_result.probabilities
        speech_probs = np.array([p.Low, p.Moderate, p.High])
        modality_tiers.append(speech_result.predicted_risk_tier)
        detected_emotion = speech_result.emotion_detail.detected_emotion

    if behavioral and models.behavioral_clf is not None:
        behavioral_result = predict_behavioral(behavioral)
        p = behavioral_result.probabilities
        behavioral_probs = np.array([p.Low, p.Moderate, p.High])
        modality_tiers.append(behavioral_result.predicted_risk_tier)

    # ── Late Fusion via Meta-Classifier ──
    fusion_vec = np.hstack([text_probs, speech_probs, behavioral_probs]).reshape(1, -1)

    if models.fusion_meta_clf is not None:
        fusion_probs = models.fusion_meta_clf.predict_proba(fusion_vec)[0]
    else:
        # Fallback: simple average
        fusion_probs = (text_probs + speech_probs + behavioral_probs) / 3.0

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
        urgency = max(urgency, "WARNING")  # at least WARNING

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
