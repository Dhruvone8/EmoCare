"""
Model loader — loads all trained .joblib artifacts from d:/EmoCare/models/ at startup.

This module is imported once by main.py and provides a singleton `Models` object
that the inference module consumes.
"""
import os
import json
import joblib
import logging

logger = logging.getLogger("emocare.model_loader")


class Models:
    """Container for all loaded ML models and associated artifacts."""

    def __init__(self):
        self.text_clf = None
        self.tfidf_vectorizer = None

        self.speech_clf = None
        self.speech_scaler = None
        self.speech_imputer = None
        self.speech_label_encoder = None
        self.speech_classes: list[str] = []
        self.speech_feature_columns: list[str] = []
        self.emotion_to_risk_map: dict[str, str] = {}

        self.behavioral_clf = None
        self.behavioral_imputer = None
        self.behavioral_scaler = None

        self.fusion_meta_clf = None

        self._loaded: dict[str, bool] = {}

    def load_all(self, models_root: str) -> None:
        """Load all model artifacts from the given root directory."""
        self._load_text(os.path.join(models_root, "text_mentalbert"))
        self._load_speech(os.path.join(models_root, "speech_classifier"))
        self._load_behavioral(os.path.join(models_root, "behavioral_classifier"))
        self._load_fusion(os.path.join(models_root, "fusion_engine"))

        loaded_count = sum(self._loaded.values())
        logger.info(f"Model loading complete: {loaded_count}/{len(self._loaded)} modules loaded")

    def _load_text(self, path: str) -> None:
        try:
            self.text_clf = joblib.load(os.path.join(path, "text_classifier.joblib"))
            self.tfidf_vectorizer = joblib.load(os.path.join(path, "tfidf_vectorizer.joblib"))
            self._loaded["text"] = True
            logger.info("Text model loaded successfully")
        except Exception as e:
            self._loaded["text"] = False
            logger.error(f"Failed to load text model: {e}")

    def _load_speech(self, path: str) -> None:
        try:
            self.speech_clf = joblib.load(os.path.join(path, "speech_emotion_model.joblib"))
            self.speech_scaler = joblib.load(os.path.join(path, "scaler.joblib"))
            self.speech_imputer = joblib.load(os.path.join(path, "imputer.joblib"))
            self.speech_label_encoder = joblib.load(os.path.join(path, "label_encoder.joblib"))

            with open(os.path.join(path, "metrics.json")) as f:
                meta = json.load(f)
            self.speech_classes = meta.get("classes", [])
            self.speech_feature_columns = meta.get("feature_columns", [])
            self.emotion_to_risk_map = meta.get("emotion_to_risk_map", {})

            self._loaded["speech"] = True
            logger.info(f"Speech model loaded ({len(self.speech_classes)} emotion classes)")
        except Exception as e:
            self._loaded["speech"] = False
            logger.error(f"Failed to load speech model: {e}")

    def _load_behavioral(self, path: str) -> None:
        try:
            self.behavioral_clf = joblib.load(os.path.join(path, "behavioral_classifier.joblib"))
            self.behavioral_imputer = joblib.load(os.path.join(path, "imputer.joblib"))
            self.behavioral_scaler = joblib.load(os.path.join(path, "scaler.joblib"))
            self._loaded["behavioral"] = True
            logger.info("Behavioral model loaded successfully")
        except Exception as e:
            self._loaded["behavioral"] = False
            logger.error(f"Failed to load behavioral model: {e}")

    def _load_fusion(self, path: str) -> None:
        try:
            self.fusion_meta_clf = joblib.load(os.path.join(path, "meta_fusion_classifier.joblib"))
            self._loaded["fusion"] = True
            logger.info("Fusion meta-classifier loaded successfully")
        except Exception as e:
            self._loaded["fusion"] = False
            logger.error(f"Failed to load fusion model: {e}")

    @property
    def loaded_status(self) -> dict[str, bool]:
        return dict(self._loaded)


# Singleton instance — populated by main.py on startup
models = Models()
