/**
 * EmoCare API Type Definitions
 *
 * These interfaces mirror the FastAPI Pydantic schemas exactly.
 * Any component that consumes API responses gets full type-safety.
 */

// ── Risk Probabilities (shared across all modality responses) ─────────
export interface RiskProbabilities {
  Low: number;
  Moderate: number;
  High: number;
}

// ── Linguistic Markers (supplementary text signal) ────────────────────
export interface LinguisticMarkers {
  /** Ratio of first-person pronouns (I, me, my, etc.) to total words */
  first_person_rate: number;
  /** Ratio of absolutist words (always, never, completely, etc.) */
  absolutist_rate: number;
  /** Ratio of negation words (not, no, never, don't, etc.) */
  negation_rate: number;
  word_count: number;
}

// ── Text Prediction ──────────────────────────────────────────────────
export interface TextRequest {
  text: string;
}

export interface TextResponse {
  predicted_risk_tier: "Low" | "Moderate" | "High";
  probabilities: RiskProbabilities;
  confidence: number;
  linguistic_markers: LinguisticMarkers;
}

// ── Speech Prediction ────────────────────────────────────────────────
export interface SpeechEmotionDetail {
  detected_emotion: string;
  emotion_confidence: number;
  emotion_probabilities: Record<string, number>;
}

export interface ProsodicFeatures {
  pitch_mean_hz: number;
  pitch_variance: number;
  speech_rate_onsets_per_sec: number;
  pause_ratio: number;
}

export interface SpeechResponse {
  predicted_risk_tier: "Low" | "Moderate" | "High";
  probabilities: RiskProbabilities;
  emotion_detail: SpeechEmotionDetail;
  prosodic_features: ProsodicFeatures;
}

// ── Behavioral Prediction ────────────────────────────────────────────
export interface BehavioralRequest {
  sleep_hours?: number;
  sleep_quality?: number;   // 1-5
  activity_level?: number;  // 1-5
  social_interaction?: number; // 1-5
  stress_level?: number;    // 1-5
  exercise_minutes?: number;
  mood_rating?: number;     // 1-5
}

export interface BehavioralResponse {
  predicted_risk_tier: "Low" | "Moderate" | "High";
  probabilities: RiskProbabilities;
}

// ── Multimodal Fusion ────────────────────────────────────────────────
export interface ModalityBreakdown {
  text: TextResponse | null;
  speech: SpeechResponse | null;
  behavioral: BehavioralResponse | null;
}

export interface MultimodalResponse {
  final_risk_tier: "Low" | "Moderate" | "High";
  probabilities: RiskProbabilities;
  confidence: number;
  escalate_to_human_reviewer: boolean;
  /** STABLE | WARNING | CRITICAL */
  urgency_level: "STABLE" | "WARNING" | "CRITICAL";
  /** Agreement score between modalities (1.0 = full agreement) */
  cross_modal_agreement: number;
  /** True when confidence is low or modalities disagree — defer to human judgment */
  low_confidence_flag: boolean;
  coping_recommendations: string[];
  modality_breakdown: ModalityBreakdown;
}

// ── Health Check ─────────────────────────────────────────────────────
export interface HealthResponse {
  status: string;
  models_loaded: Record<string, boolean>;
  version: string;
}

// ── Self-Assessment (PHQ-9 & GAD-7) ───────────────────────────────────
export interface AssessmentSubmissionRequest {
  user_id: string;
  test_type: "phq9" | "gad7";
  responses: number[];
}

export interface AssessmentResponse {
  id?: number | null;
  user_id: string;
  test_type: string;
  test_display_name: string;
  total_score: number;
  max_score: number;
  severity_band: string;
  risk_tier: "Low" | "Moderate" | "High";
  plain_language_summary: string;
  timestamp: string;
}

// ── Multimodal Request (used by the API client) ──────────────────────
export interface MultimodalRequest {
  text?: string;
  audio?: Blob;
  behavioral?: BehavioralRequest;
}

