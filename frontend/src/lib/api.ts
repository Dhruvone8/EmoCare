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
  AssessmentHistoryResponse,
  StartSessionRequest,
  StartSessionResponse,
  ChatMessageRequest,
  ChatMessageResponse,
  EndSessionRequest,
  SessionSummaryResponse,
  UserSessionListResponse,
  VoiceTherapyResponse,
} from "@/types/api";
import { supabase } from "@/lib/supabase";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const GUEST_STORAGE_KEY = "emocare_guest_session";

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

interface GuestSession {
  access_token: string;
  token_type: "bearer";
  user_id: string;
  expires_at: number;
}

interface ApiIdentity {
  accessToken: string;
  userId: string;
  isGuest: boolean;
}

let cachedGuestSession: GuestSession | null = null;
let guestSessionPromise: Promise<GuestSession> | null = null;

function isUsableGuestSession(value: unknown): value is GuestSession {
  if (!value || typeof value !== "object") return false;
  const session = value as Partial<GuestSession>;
  return (
    typeof session.access_token === "string" &&
    typeof session.user_id === "string" &&
    session.user_id.startsWith("guest_") &&
    typeof session.expires_at === "number" &&
    session.expires_at > Math.floor(Date.now() / 1000) + 30
  );
}

function clearGuestSession() {
  cachedGuestSession = null;
  if (typeof window !== "undefined") {
    window.localStorage.removeItem(GUEST_STORAGE_KEY);
  }
}

async function issueGuestSession(): Promise<GuestSession> {
  const res = await fetch(`${API_BASE}/api/auth/guest`, { method: "POST" });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new ApiError(res.status, body.detail || res.statusText);
  }

  const session: unknown = await res.json();
  if (!isUsableGuestSession(session)) {
    throw new ApiError(500, "Backend returned an invalid guest session");
  }

  cachedGuestSession = session;
  if (typeof window !== "undefined") {
    window.localStorage.setItem(GUEST_STORAGE_KEY, JSON.stringify(session));
  }
  return session;
}

async function getGuestSession(): Promise<GuestSession> {
  if (isUsableGuestSession(cachedGuestSession)) {
    return cachedGuestSession;
  }

  if (typeof window !== "undefined") {
    try {
      const stored: unknown = JSON.parse(
        window.localStorage.getItem(GUEST_STORAGE_KEY) || "null"
      );
      if (isUsableGuestSession(stored)) {
        cachedGuestSession = stored;
        return stored;
      }
    } catch {
      clearGuestSession();
    }
  }

  if (!guestSessionPromise) {
    guestSessionPromise = issueGuestSession().finally(() => {
      guestSessionPromise = null;
    });
  }
  return guestSessionPromise;
}

async function getApiIdentity(): Promise<ApiIdentity> {
  const {
    data: { session },
  } = await supabase.auth.getSession();

  if (session?.access_token && session.user?.id) {
    return {
      accessToken: session.access_token,
      userId: session.user.id,
      isGuest: false,
    };
  }

  const guest = await getGuestSession();
  return {
    accessToken: guest.access_token,
    userId: guest.user_id,
    isGuest: true,
  };
}

async function getAuthenticatedUserId(): Promise<string> {
  const identity = await getApiIdentity();
  return identity.userId;
}

async function apiFetch<T>(
  endpoint: string,
  options: RequestInit = {},
  retryGuest = true
): Promise<T> {
  const identity = await getApiIdentity();
  const headers = new Headers(options.headers);
  headers.set("Authorization", `Bearer ${identity.accessToken}`);

  const res = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers,
  });

  if (res.status === 401 && identity.isGuest && retryGuest) {
    clearGuestSession();
    return apiFetch<T>(endpoint, options, false);
  }

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
  const userId = await getAuthenticatedUserId();
  return apiFetch<AssessmentResponse>("/api/assessment/submit", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ...data, user_id: userId }),
  });
}

export async function getAssessmentHistory(
  _userId: string,
  limit: number = 20
): Promise<AssessmentHistoryResponse> {
  const userId = await getAuthenticatedUserId();
  return apiFetch<AssessmentHistoryResponse>(
    `/api/assessment/history/${encodeURIComponent(userId)}?limit=${limit}`
  );
}

export { ApiError };


// ═══════════════════════════════════════════════════════════════════════
// THERAPY SESSION & CHAT API
// ═══════════════════════════════════════════════════════════════════════

// ── Session Management ───────────────────────────────────────────────

export async function startSession(
  data: StartSessionRequest
): Promise<StartSessionResponse> {
  const userId = await getAuthenticatedUserId();
  return apiFetch<StartSessionResponse>("/api/therapy/session/start", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ...data, user_id: userId }),
  });
}

export async function endSession(
  data: EndSessionRequest
): Promise<SessionSummaryResponse> {
  const userId = await getAuthenticatedUserId();
  return apiFetch<SessionSummaryResponse>("/api/therapy/session/end", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ...data, user_id: userId }),
  });
}

export async function getUserSessions(
  _userId: string
): Promise<UserSessionListResponse> {
  void _userId;
  const userId = await getAuthenticatedUserId();
  return apiFetch<UserSessionListResponse>(
    `/api/therapy/sessions/${encodeURIComponent(userId)}`
  );
}

export async function getSessionMessages(
  sessionId: number
): Promise<{ messages: Array<{ role: string; content: string; timestamp: string }> }> {
  return apiFetch(`/api/therapy/session/${sessionId}/messages`);
}

// ── Chat Messages ────────────────────────────────────────────────────

export async function sendChatMessage(
  data: ChatMessageRequest
): Promise<ChatMessageResponse> {
  const userId = await getAuthenticatedUserId();
  return apiFetch<ChatMessageResponse>("/api/chat/message", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ...data, user_id: userId }),
  });
}

// ── Voice Therapy ────────────────────────────────────────────────────

export interface VoiceGreetingResponse {
  session_id: number;
  greeting_text: string;
  audio_base64: string | null;
}

export async function getVoiceGreeting(
  sessionId: number,
  _userId: string,
  timeOfDay?: string
): Promise<VoiceGreetingResponse> {
  const userId = await getAuthenticatedUserId();
  return apiFetch<VoiceGreetingResponse>("/api/voice-therapy/greeting", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      session_id: sessionId,
      user_id: userId,
      time_of_day: timeOfDay,
    }),
  });
}

export async function sendVoiceTherapy(
  sessionId: number,
  _userId: string,
  audioBlob: Blob
): Promise<VoiceTherapyResponse> {
  const userId = await getAuthenticatedUserId();
  const formData = new FormData();
  formData.append("session_id", String(sessionId));
  formData.append("user_id", userId);

  const ext = audioBlob.type.includes("wav")
    ? "wav"
    : audioBlob.type.includes("mp4")
    ? "mp4"
    : "webm";

  formData.append("audio", audioBlob, `voice_recording.${ext}`);

  return apiFetch<VoiceTherapyResponse>("/api/voice-therapy/interact", {
    method: "POST",
    body: formData,
  });
}
