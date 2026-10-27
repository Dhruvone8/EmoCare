"""
Test: Multimodal fusion handles missing modalities without dilution.

Verifies that single-modality high-risk inputs are not dragged down to
Moderate/Low by missing modalities defaulting to [1/3, 1/3, 1/3].
"""
import pytest
from unittest.mock import patch, MagicMock
import numpy as np

from backend.app.inference import predict_multimodal
from backend.app.schemas import (
    BehavioralRequest,
    RiskProbabilities,
    TextResponse,
    LinguisticMarkers,
)


def _make_high_risk_text_result():
    """Mock text result with strong High-risk signal."""
    return TextResponse(
        predicted_risk_tier="High",
        probabilities=RiskProbabilities(Low=0.05, Moderate=0.10, High=0.85),
        confidence=0.85,
        linguistic_markers=LinguisticMarkers(
            first_person_rate=0.15,
            absolutist_rate=0.10,
            negation_rate=0.08,
            word_count=12,
        ),
    )


def test_single_text_modality_not_diluted():
    """High-risk text alone should produce High tier, not diluted to Moderate."""
    mock_result = _make_high_risk_text_result()

    with patch("backend.app.inference.predict_text", return_value=mock_result):
        with patch("backend.app.inference.models") as mock_models:
            mock_models.text_clf = MagicMock()
            mock_models.speech_clf = None
            mock_models.behavioral_clf = None

            result = predict_multimodal(text="I want to die, everything is hopeless")

    assert result.final_risk_tier == "High", (
        f"Single high-risk text modality produced {result.final_risk_tier}, "
        f"expected High (probs: L={result.probabilities.Low}, M={result.probabilities.Moderate}, H={result.probabilities.High})"
    )
    assert result.probabilities.High > 0.5


def test_behavioral_only_high_distress():
    """High-distress behavioral alone should produce High risk without needing text/speech models."""
    result = predict_multimodal(
        behavioral=BehavioralRequest(
            sleep_hours=2.0,
            sleep_quality=1.0,
            activity_level=1.0,
            social_interaction=1.0,
            stress_level=5.0,
            exercise_minutes=0.0,
            mood_rating=1.0,
        )
    )
    assert result.final_risk_tier == "High", (
        f"Extreme distress behavioral produced {result.final_risk_tier}"
    )


def test_no_modalities_returns_uniform():
    """No modalities at all should return uniform 1/3 probabilities."""
    result = predict_multimodal()
    assert abs(result.probabilities.Low - 1/3) < 0.01
    assert abs(result.probabilities.Moderate - 1/3) < 0.01
    assert abs(result.probabilities.High - 1/3) < 0.01


def test_behavioral_healthy_produces_low():
    """Healthy behavioral inputs alone should produce Low risk."""
    result = predict_multimodal(
        behavioral=BehavioralRequest(
            sleep_hours=8.0,
            sleep_quality=5.0,
            activity_level=5.0,
            social_interaction=5.0,
            stress_level=1.0,
            exercise_minutes=60.0,
            mood_rating=5.0,
        )
    )
    assert result.final_risk_tier == "Low", (
        f"Healthy behavioral produced {result.final_risk_tier}"
    )


def test_cross_modal_agreement_single_modality():
    """Single modality should have agreement = 1.0."""
    result = predict_multimodal(
        behavioral=BehavioralRequest(
            sleep_hours=5.0, stress_level=3.0, mood_rating=3.0,
        )
    )
    assert result.cross_modal_agreement == 1.0


def test_probabilities_sum_to_one():
    """Fused probabilities must sum to 1.0."""
    result = predict_multimodal(
        behavioral=BehavioralRequest(
            sleep_hours=5.0, stress_level=4.0, mood_rating=2.0,
        )
    )
    total = result.probabilities.Low + result.probabilities.Moderate + result.probabilities.High
    assert abs(total - 1.0) < 0.01, f"Fused probabilities sum to {total}"
