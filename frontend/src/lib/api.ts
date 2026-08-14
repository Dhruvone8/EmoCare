/**
 * EmoCare API Client
 *
 * Ready-to-use fetch wrappers for all FastAPI endpoints.
 * Usage in any React component:
 *
 *   import { predictText, predictMultimodal } from "@/lib/api";
 *
 *   const result = await predictText("I feel overwhelmed");
 *   console.log(result.predicted_risk_tier);  // "Moderate"
 */

import type {
  HealthResponse,
  TextResponse,
  SpeechResponse,
  BehavioralRequest,
  BehavioralResponse,
  MultimodalResponse,
  MultimodalRequest,
  AssessmentSubmissionRequest,
  AssessmentResponse,
} from "@/types/api";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// ── Generic fetch helper ─────────────────────────────────────────────

class ApiError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(`API Error ${status}: ${detail}`);
    this.status = status;
    this.detail = detail;
  }
}

async function apiFetch<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const res = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers: {
      ...options.headers,
    },
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new ApiError(res.status, body.detail || res.statusText);
  }

  return res.json() as Promise<T>;
}

// ── Health Check ─────────────────────────────────────────────────────

export async function healthCheck(): Promise<HealthResponse> {
  return apiFetch<HealthResponse>("/health");
}

// ── Text Prediction ──────────────────────────────────────────────────

export async function predictText(text: string): Promise<TextResponse> {
  return apiFetch<TextResponse>("/api/predict/text", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });
}

// ── Speech Prediction ────────────────────────────────────────────────

export async function predictSpeech(
  audioBlob: Blob
): Promise<SpeechResponse> {
  const formData = new FormData();
  formData.append("audio", audioBlob, "recording.wav");

  return apiFetch<SpeechResponse>("/api/predict/speech", {
    method: "POST",
    body: formData,
  });
}

// ── Behavioral Prediction ────────────────────────────────────────────

export async function predictBehavioral(
  data: BehavioralRequest
): Promise<BehavioralResponse> {
  return apiFetch<BehavioralResponse>("/api/predict/behavioral", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
}

// ── Multimodal Fusion ────────────────────────────────────────────────

export async function predictMultimodal(
  request: MultimodalRequest
): Promise<MultimodalResponse> {
  const formData = new FormData();

  if (request.text) {
    formData.append("text", request.text);
  }

  if (request.audio) {
    formData.append("audio", request.audio, "recording.wav");
  }

  if (request.behavioral) {
    const b = request.behavioral;
    if (b.sleep_hours !== undefined)
      formData.append("sleep_hours", String(b.sleep_hours));
    if (b.sleep_quality !== undefined)
      formData.append("sleep_quality", String(b.sleep_quality));
    if (b.activity_level !== undefined)
      formData.append("activity_level", String(b.activity_level));
    if (b.social_interaction !== undefined)
      formData.append("social_interaction", String(b.social_interaction));
    if (b.stress_level !== undefined)
      formData.append("stress_level", String(b.stress_level));
    if (b.exercise_minutes !== undefined)
      formData.append("exercise_minutes", String(b.exercise_minutes));
    if (b.mood_rating !== undefined)
      formData.append("mood_rating", String(b.mood_rating));
  }

  return apiFetch<MultimodalResponse>("/api/predict/multimodal", {
    method: "POST",
    body: formData,
  });
}

// ── Assessment Prediction / Submission ───────────────────────────────

export async function submitAssessment(
  data: AssessmentSubmissionRequest
): Promise<AssessmentResponse> {
  return apiFetch<AssessmentResponse>("/api/assessment/submit", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
}

export { ApiError };

