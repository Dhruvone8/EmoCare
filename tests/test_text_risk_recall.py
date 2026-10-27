from types import SimpleNamespace

import numpy as np

from backend.app.inference import predict_text
from backend.app.model_loader import models
from backend.app.therapy import _is_crisis_signal

ACUTE_DISTRESS_STATEMENTS = [
    "I feel completely hopeless and exhausted with life.",
    "I don't see any point in going on anymore.",
    "I want to die and never wake up again.",
    "I have been thinking about suicide every night.",
    "I want to end my life.",
    "Everyone would be better off without me.",
    "I feel like a burden and nothing will ever improve.",
    "There is no way out of this pain.",
    "I can't do this anymore; life feels unbearable.",
    "I am worthless and completely alone.",
    "Nothing matters anymore and I have no future.",
    "I feel empty, hopeless, and unable to keep going.",
    "I wish I could disappear forever.",
    "I have given up on life.",
    "I can't escape this constant despair.",
    "I cry all day and see no reason to live.",
    "I feel trapped with no hope of things getting better.",
    "My life is over; there is nothing left for me.",
    "I am overwhelmed by sadness and cannot function anymore.",
    "I have no energy to face another day and no hope at all.",
    "I think about harming myself to make the pain stop.",
    "I want to kill myself.",
    "I have a plan to hurt myself tonight.",
    "I don't want to be alive anymore.",
    "The world would be better without me in it.",
    "I feel completely broken and beyond help.",
    "Every day is unbearable and I am losing the will to live.",
    "There is nothing to look forward to and no reason to stay.",
    "I cannot see a future for myself and feel utterly hopeless.",
    "I am in so much emotional pain that I just want it all to end.",
]


def test_acute_distress_high_risk_recall_is_at_least_90_percent():
    predictions = [predict_text(text).predicted_risk_tier for text in ACUTE_DISTRESS_STATEMENTS]
    high_risk_count = predictions.count("High")
    recall = high_risk_count / len(ACUTE_DISTRESS_STATEMENTS)
    misses = [
        text
        for text, tier in zip(ACUTE_DISTRESS_STATEMENTS, predictions)
        if tier != "High"
    ]
    assert recall >= 0.90, f"High-risk recall={recall:.3f}; misses={misses}"


class DummyVectorizer:
    def transform(self, texts):
        return texts


class DummyClassifier:
    def __init__(self, probabilities, classes=(0, 1, 2)):
        self.probabilities = probabilities
        self.classes_ = np.array(classes)

    def predict_proba(self, _features):
        return np.array([self.probabilities])


def predict_with_probabilities(monkeypatch, text, probabilities, classes=(0, 1, 2)):
    monkeypatch.setattr(models, "tfidf_vectorizer", DummyVectorizer())
    monkeypatch.setattr(models, "text_clf", DummyClassifier(probabilities, classes))
    return predict_text(text)


def test_probability_order_follows_classifier_classes(monkeypatch):
    result = predict_with_probabilities(
        monkeypatch,
        "A neutral statement.",
        [0.21, 0.10, 0.69],
        classes=("High", "Moderate", "Low"),
    )
    assert result.probabilities.High == 0.21
    assert result.probabilities.Moderate == 0.10
    assert result.probabilities.Low == 0.69
    assert result.predicted_risk_tier == "High"
    assert result.confidence == 0.21


def test_asymmetric_decision_boundaries(monkeypatch):
    high = predict_with_probabilities(
        monkeypatch,
        "A neutral statement.",
        [0.45, 0.35, 0.20],
    )
    assert high.predicted_risk_tier == "High"

    moderate = predict_with_probabilities(
        monkeypatch,
        "A neutral statement.",
        [0.55, 0.35, 0.10],
    )
    assert moderate.predicted_risk_tier == "Moderate"

    combined = predict_with_probabilities(
        monkeypatch,
        "A neutral statement.",
        [0.50, 0.30, 0.20],
    )
    assert combined.predicted_risk_tier == "High"

    low = predict_with_probabilities(
        monkeypatch,
        "A neutral statement.",
        [0.80, 0.15, 0.05],
    )
    assert low.predicted_risk_tier == "Low"


def test_negated_hopelessness_does_not_trigger_lexical_override(monkeypatch):
    result = predict_with_probabilities(
        monkeypatch,
        "I no longer feel hopeless; things are getting better.",
        [0.80, 0.15, 0.05],
    )
    assert result.predicted_risk_tier == "Low"


def test_crisis_detection_stays_distinct_from_general_sadness():
    assert _is_crisis_signal("I am thinking about suicide") is True
    assert _is_crisis_signal("I feel sad about the argument") is False
