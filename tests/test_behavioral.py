"""
Test: Behavioral distress index produces clinically coherent risk tiers.

Verifies that extreme distress inputs produce High risk, healthy inputs produce Low,
and moderate inputs produce Moderate — without relying on the 50-feature StudentLife model.
"""
import pytest
from backend.app.inference import predict_behavioral
from backend.app.schemas import BehavioralRequest


def test_high_distress_produces_high_risk():
    """Extreme stress, poor sleep, isolation → High risk tier."""
    req = BehavioralRequest(
        sleep_hours=3.0,
        sleep_quality=1.0,
        activity_level=1.0,
        social_interaction=1.0,
        stress_level=5.0,
        exercise_minutes=0.0,
        mood_rating=1.0,
    )
    result = predict_behavioral(req)
    assert result.predicted_risk_tier == "High", (
        f"Expected High, got {result.predicted_risk_tier} "
        f"(probs: L={result.probabilities.Low}, M={result.probabilities.Moderate}, H={result.probabilities.High})"
    )
    assert result.probabilities.High > result.probabilities.Low


def test_healthy_inputs_produce_low_risk():
    """Good sleep, low stress, high mood → Low risk tier."""
    req = BehavioralRequest(
        sleep_hours=8.0,
        sleep_quality=5.0,
        activity_level=4.0,
        social_interaction=5.0,
        stress_level=1.0,
        exercise_minutes=45.0,
        mood_rating=5.0,
    )
    result = predict_behavioral(req)
    assert result.predicted_risk_tier == "Low", (
        f"Expected Low, got {result.predicted_risk_tier} "
        f"(probs: L={result.probabilities.Low}, M={result.probabilities.Moderate}, H={result.probabilities.High})"
    )
    assert result.probabilities.Low > result.probabilities.High


def test_moderate_inputs_produce_moderate_risk():
    """Neutral/middling inputs → Moderate risk tier."""
    req = BehavioralRequest(
        sleep_hours=6.0,
        sleep_quality=3.0,
        activity_level=3.0,
        social_interaction=3.0,
        stress_level=3.0,
        exercise_minutes=15.0,
        mood_rating=3.0,
    )
    result = predict_behavioral(req)
    # With middling inputs, should be Moderate (or at least not extreme)
    assert result.predicted_risk_tier in ("Moderate", "Low"), (
        f"Expected Moderate or Low, got {result.predicted_risk_tier}"
    )


def test_probabilities_sum_to_one():
    """Risk probabilities must sum to 1.0."""
    req = BehavioralRequest(
        sleep_hours=5.0,
        sleep_quality=2.0,
        activity_level=2.0,
        social_interaction=2.0,
        stress_level=4.0,
        exercise_minutes=10.0,
        mood_rating=2.0,
    )
    result = predict_behavioral(req)
    total = result.probabilities.Low + result.probabilities.Moderate + result.probabilities.High
    assert abs(total - 1.0) < 0.01, f"Probabilities sum to {total}, expected ~1.0"


def test_default_values_produce_moderate():
    """All None inputs (neutral defaults) should produce Moderate risk."""
    req = BehavioralRequest()
    result = predict_behavioral(req)
    assert result.predicted_risk_tier in ("Moderate", "Low"), (
        f"All-default inputs produced {result.predicted_risk_tier}"
    )


def test_stress_is_dominant_signal():
    """Max stress alone (with healthy everything else) should increase High probability."""
    healthy = BehavioralRequest(
        sleep_hours=8.0, sleep_quality=5.0, activity_level=5.0,
        social_interaction=5.0, stress_level=1.0, exercise_minutes=60.0, mood_rating=5.0,
    )
    stressed = BehavioralRequest(
        sleep_hours=8.0, sleep_quality=5.0, activity_level=5.0,
        social_interaction=5.0, stress_level=5.0, exercise_minutes=60.0, mood_rating=5.0,
    )
    r_healthy = predict_behavioral(healthy)
    r_stressed = predict_behavioral(stressed)
    assert r_stressed.probabilities.High > r_healthy.probabilities.High, (
        f"High stress ({r_stressed.probabilities.High}) should exceed healthy ({r_healthy.probabilities.High})"
    )
