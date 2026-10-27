"""
Test: Acoustic feature extraction alignment with trained speech emotion model.

Verifies that _extract_speech_features produces exactly the 95 features
expected by models.speech_feature_columns, with zero missing columns.
"""
import numpy as np
import pytest
import json
import os


@pytest.fixture
def expected_feature_columns():
    """Load the feature column names the trained model expects."""
    metrics_path = os.path.join(
        os.path.dirname(__file__), "..", "models", "speech_classifier", "metrics.json"
    )
    with open(metrics_path) as f:
        meta = json.load(f)
    return meta["feature_columns"]


@pytest.fixture
def synth_waveform():
    """Generate a 3-second synthesized test waveform at 22050 Hz."""
    sr = 22050
    duration = 3.0
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    # Mix two tones with some noise to exercise all feature extractors
    y = 0.5 * np.sin(2 * np.pi * 220 * t) + 0.3 * np.sin(2 * np.pi * 440 * t)
    y += 0.1 * np.random.randn(len(y))
    return y.astype(np.float32), sr


def test_feature_extraction_matches_model_columns(expected_feature_columns, synth_waveform):
    """All 95 features the model needs must be present with no extras or missing."""
    from backend.app.inference import _extract_speech_features

    y, sr = synth_waveform
    features = _extract_speech_features(y, sr)

    expected_set = set(expected_feature_columns)
    extracted_set = set(features.keys())

    missing = expected_set - extracted_set
    extra = extracted_set - expected_set

    assert len(missing) == 0, f"Missing {len(missing)} features: {sorted(missing)}"
    assert len(extra) == 0, f"Extra {len(extra)} features not expected by model: {sorted(extra)}"
    assert len(features) == 95, f"Expected 95 features, got {len(features)}"


def test_feature_values_are_finite(synth_waveform):
    """All extracted feature values must be finite floats (no NaN/Inf)."""
    from backend.app.inference import _extract_speech_features

    y, sr = synth_waveform
    features = _extract_speech_features(y, sr)

    for name, value in features.items():
        assert isinstance(value, float), f"{name} is {type(value)}, expected float"
        assert np.isfinite(value), f"{name} = {value} is not finite"


def test_feature_vector_alignment(expected_feature_columns, synth_waveform):
    """Feature vector built via .get(col, 0.0) must have zero zero-filled gaps."""
    from backend.app.inference import _extract_speech_features

    y, sr = synth_waveform
    features = _extract_speech_features(y, sr)

    feature_vector = [features.get(col, 0.0) for col in expected_feature_columns]
    # None of these should be the 0.0 fallback for columns that were actually computed
    zero_filled_count = sum(
        1 for col in expected_feature_columns if col not in features
    )
    assert zero_filled_count == 0, (
        f"{zero_filled_count} columns filled with 0.0 fallback (missing from extraction)"
    )
    assert len(feature_vector) == 95


def test_mfcc_range_spans_40(synth_waveform):
    """MFCCs should cover indices 0-39 (40 coefficients)."""
    from backend.app.inference import _extract_speech_features

    y, sr = synth_waveform
    features = _extract_speech_features(y, sr)

    for i in range(40):
        assert f"mfcc_{i}_mean" in features, f"Missing mfcc_{i}_mean"
        assert f"mfcc_{i}_std" in features, f"Missing mfcc_{i}_std"
