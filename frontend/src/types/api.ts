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
export interface AssessmentFollowUpData {
  functional_difficulty: string;
  impact_areas: string[];
  duration: string;
  trajectory: string;
  prior_history: string;
  elevation_screen: string;
  life_factors: string[];
  coping_goals: string[];
}

export interface AssessmentSafetyDisclosure {
  active_thoughts: boolean;
  immediate_intent: boolean;
  safe_person_nearby: boolean;
  notes?: string;
}

export interface AssessmentSubmissionRequest {
  user_id: string;
  test_type: "phq9" | "gad7";
  responses: number[];
  follow_up_data?: AssessmentFollowUpData;
  safety_disclosure?: AssessmentSafetyDisclosure;
}

export interface SymptomDomainItem {
  item_number: number;
  question: string;
  score: number;
  frequency_label: string;
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
  safety_alert?: boolean;
  safety_details?: {
    safety_alert: boolean;
    q9_score?: number;
    active_emergency?: boolean;
    urgency_level?: string;
    reason?: string | null;
    crisis_resources?: string[];
    safety_notice?: string | null;
  };
  symptom_breakdown?: {
    domains: Record<
      string,
      { label: string; score: number; max: number; items: number[]; summary?: string; endorsed?: boolean }
    >;
    reported_count: number;
    unreported_count: number;
    reported_items: SymptomDomainItem[];
    unreported_items: SymptomDomainItem[];
  };
  follow_up_summary?: {
    completed: boolean;
    functional_difficulty: string;
    impact_areas: string[];
    duration: string;
    trajectory: string;
    prior_history: string;
    elevation_screen_endorsed: boolean;
    elevation_screen_note?: string | null;
    life_factors: string[];
    coping_goals: string[];
  };
  recommended_steps?: string[];
  clinical_disclaimer?: string;
}

export interface AssessmentHistoryItem {
  id?: number | null;
  user_id: string;
  test_type: string;
  total_score: number;
  max_score: number;
  severity_band: string;
  risk_tier: string;
  safety_flag: boolean;
  q9_score?: number;
  timestamp: string;
  llm_summary?: string;
}

export interface AssessmentHistoryResponse {
  user_id: string;
  history: AssessmentHistoryItem[];
  count: number;
}

// ── Multimodal Request (used by the API client) ──────────────────────
export interface MultimodalRequest {
  text?: string;
  audio?: Blob;
  behavioral?: BehavioralRequest;
}


// ═══════════════════════════════════════════════════════════════════════
// THERAPY SESSION & CHAT TYPES
// ═══════════════════════════════════════════════════════════════════════

// ── Session Management ───────────────────────────────────────────────
export interface StartSessionRequest {
  user_id: string;
  mode: "chat" | "voice";
  objective?: string;
}

export interface StartSessionResponse {
  session_id: number;
  mode: string;
  started_at: string;
  current_stage?: string;
  stage_label?: string;
  welcome_message?: string;
  prior_summaries: Array<{
    summary_text?: string;
    concerns?: string[];
    goals?: string[];
    techniques_used?: string[];
  }>;
}

export interface EndSessionRequest {
  session_id: number;
  user_id: string;
}

export interface SessionSummaryResponse {
  session_id: number;
  summary_text: string;
  concerns: string[];
  goals: string[];
  techniques_used: string[];
  key_insights?: string[];
  action_steps?: string[];
}

export interface UserSessionListResponse {
  sessions: Array<{
    id?: number;
    session_id?: number;
    user_id?: string;
    mode: string;
    started_at: string;
    ended_at?: string | null;
    message_count?: number;
    objective?: string;
    summary_text?: string;
  }>;
}

// ── Chat Messages ────────────────────────────────────────────────────
export interface ChatMessageRequest {
  session_id: number;
  user_id: string;
  message: string;
}

export interface ToolInvocation {
  tool_name: string;
  tool_input: Record<string, unknown>;
  tool_output: string;
}

export interface ChatMessageResponse {
  session_id: number;
  reply: string;
  risk_tier: "Low" | "Moderate" | "High";
  urgency_level: "STABLE" | "WARNING" | "CRITICAL";
  crisis_activated: boolean;
  current_stage?: string;
  stage_label?: string;
  main_concern?: string | null;
  tools_used: ToolInvocation[];
}

// ── Voice Therapy ────────────────────────────────────────────────────
export interface VoiceTherapyResponse {
  session_id: number;
  transcript: string;
  reply_text: string;
  reply_audio_base64: string | null;
  risk_tier: "Low" | "Moderate" | "High";
  urgency_level: "STABLE" | "WARNING" | "CRITICAL";
  crisis_activated: boolean;
  speech_emotion: string | null;
  tools_used: ToolInvocation[];
}
