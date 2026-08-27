"use client";

import { useState, useRef, useCallback } from "react";
import { useAuth } from "@/context/AuthContext";
import { startSession, sendVoiceTherapy, endSession } from "@/lib/api";
import type {
  VoiceTherapyResponse,
  ToolInvocation,
  StartSessionResponse,
} from "@/types/api";

/* ── Types ─────────────────────────────────────────────────────────── */
interface ConversationTurn {
  id: string;
  userTranscript: string;
  assistantReply: string;
  audioBase64: string | null;
  speechEmotion: string | null;
  riskTier: "Low" | "Moderate" | "High";
  crisisActivated: boolean;
  toolsUsed: ToolInvocation[];
  timestamp: Date;
}

/* ── Emotion display helper ────────────────────────────────────────── */
function emotionEmoji(emotion: string | null): { emoji: string; label: string } {
  if (!emotion) return { emoji: "🎙️", label: "Processing..." };
  const map: Record<string, { emoji: string; label: string }> = {
    neutral: { emoji: "😌", label: "Calm" },
    calm: { emoji: "🧘", label: "Peaceful" },
    happy: { emoji: "😊", label: "Bright" },
    sad: { emoji: "🥺", label: "Sad" },
    angry: { emoji: "😤", label: "Tense" },
    fearful: { emoji: "😰", label: "Anxious" },
    disgust: { emoji: "😞", label: "Bothered" },
    surprised: { emoji: "😯", label: "Surprised" },
  };
  return map[emotion.toLowerCase()] || { emoji: "🎵", label: emotion };
}

/* ── Page Component ────────────────────────────────────────────────── */
export default function VoiceTherapyPage() {
  const { user, openAuthModal } = useAuth();

  /* Session state */
  const [sessionId, setSessionId] = useState<number | null>(null);
  const [sessionStarting, setSessionStarting] = useState(false);
  const [sessionEnding, setSessionEnding] = useState(false);

  /* Recording state */
  const [recording, setRecording] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [seconds, setSeconds] = useState(0);

  /* Conversation state */
  const [turns, setTurns] = useState<ConversationTurn[]>([]);
  const [error, setError] = useState<string | null>(null);

  /* Summary state */
  const [summary, setSummary] = useState<{
    summary_text: string;
    concerns: string[];
    goals: string[];
    techniques_used: string[];
  } | null>(null);

  /* Refs */
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  const userId =
    user?.id || "guest_" + (typeof window !== "undefined" ? window.location.hostname : "anon");

  /* ── Start Session ────────────────────────────────────────────── */
  const handleStartSession = useCallback(async () => {
    setSessionStarting(true);
    setError(null);
    setSummary(null);
    try {
      const res = await startSession({
        user_id: userId,
        mode: "voice",
      });
      setSessionId(res.session_id);
      setTurns([]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start session.");
    } finally {
      setSessionStarting(false);
    }
  }, [userId]);

  /* ── Start Recording ──────────────────────────────────────────── */
  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaRecorderRef.current = new MediaRecorder(stream);
      chunksRef.current = [];

      mediaRecorderRef.current.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };

      mediaRecorderRef.current.onstop = async () => {
        const blob = new Blob(chunksRef.current, { type: "audio/wav" });
        stream.getTracks().forEach((track) => track.stop());
        if (timerRef.current) clearInterval(timerRef.current);

        /* Send to voice therapy endpoint */
        if (sessionId) {
          await processVoice(blob);
        }
      };

      setSeconds(0);
      timerRef.current = setInterval(() => setSeconds((s) => s + 1), 1000);

      mediaRecorderRef.current.start();
      setRecording(true);
      setError(null);
    } catch {
      setError(
        "Couldn't access your microphone. Please check browser permissions."
      );
    }
  };

  /* ── Stop Recording ───────────────────────────────────────────── */
  const stopRecording = () => {
    if (mediaRecorderRef.current && recording) {
      mediaRecorderRef.current.stop();
      setRecording(false);
      if (timerRef.current) clearInterval(timerRef.current);
    }
  };

  /* ── Process Voice ────────────────────────────────────────────── */
  const processVoice = async (blob: Blob) => {
    if (!sessionId) return;
    setProcessing(true);

    try {
      const res: VoiceTherapyResponse = await sendVoiceTherapy(
        sessionId,
        userId,
        blob
      );

      const turn: ConversationTurn = {
        id: `turn-${Date.now()}`,
        userTranscript: res.transcript,
        assistantReply: res.reply_text,
        audioBase64: res.reply_audio_base64,
        speechEmotion: res.speech_emotion,
        riskTier: res.risk_tier,
        crisisActivated: res.crisis_activated,
        toolsUsed: res.tools_used,
        timestamp: new Date(),
      };

      setTurns((prev) => [...prev, turn]);

      /* Auto-play TTS response if available */
      if (res.reply_audio_base64) {
        playAudio(res.reply_audio_base64);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Voice processing failed.");
    } finally {
      setProcessing(false);
    }
  };

  /* ── Play Audio ───────────────────────────────────────────────── */
  const playAudio = (base64: string) => {
    try {
      const audio = new Audio(`data:audio/mp3;base64,${base64}`);
      audioRef.current = audio;
      audio.play().catch(() => {
        /* Browser may block autoplay — user can manually play */
      });
    } catch {
      /* Audio playback not available */
    }
  };

  /* ── End Session ──────────────────────────────────────────────── */
  const handleEndSession = async () => {
    if (!sessionId) return;
    setSessionEnding(true);
    try {
      const res = await endSession({ session_id: sessionId, user_id: userId });
      setSummary(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to end session.");
    } finally {
      setSessionEnding(false);
    }
  };

  /* ── Reset ────────────────────────────────────────────────────── */
  const handleNewSession = () => {
    setSessionId(null);
    setTurns([]);
    setSummary(null);
    setError(null);
  };

  return (
    <div className="max-w-4xl mx-auto flex flex-col gap-6">
      {/* ── Header ─────────────────────────────────────────────── */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-sans text-[28px] md:text-[36px] font-semibold text-on-surface tracking-tight leading-tight flex items-center gap-3">
            <span
              className="material-symbols-outlined text-primary text-3xl"
              style={{ fontVariationSettings: "'FILL' 1" }}
            >
              headset_mic
            </span>
            <span>Voice Therapy</span>
          </h1>
          <p className="font-sans text-[15px] text-on-surface-variant mt-1">
            Speak naturally — we&apos;ll listen, understand, and respond with calming audio
          </p>
        </div>

        {sessionId && !summary && (
          <button
            onClick={handleEndSession}
            disabled={sessionEnding}
            className="px-4 py-2 text-xs font-medium rounded-full border border-outline-variant/30 text-on-surface-variant hover:text-error hover:border-error/30 hover:bg-error/5 transition-all cursor-pointer"
          >
            {sessionEnding ? "Ending..." : "End Session"}
          </button>
        )}
      </div>

      {/* ── Pre-session: Start ──────────────────────────────────── */}
      {!sessionId && !summary && (
        <div className="flex items-center justify-center min-h-[400px]">
          <div className="glass-panel-elevated rounded-2xl p-8 md:p-12 max-w-lg text-center flex flex-col items-center gap-6 animate-sanctuary-in">
            <div className="w-24 h-24 rounded-full bg-primary/10 flex items-center justify-center relative">
              <div className="absolute inset-0 rounded-full bg-primary/5 animate-breathe" />
              <span
                className="material-symbols-outlined text-primary text-5xl relative z-10"
                style={{ fontVariationSettings: "'FILL' 1" }}
              >
                mic
              </span>
            </div>
            <div>
              <h2 className="text-xl font-semibold text-on-surface mb-2">
                Your Audio Sanctuary
              </h2>
              <p className="text-sm text-on-surface-variant leading-relaxed max-w-sm">
                Speak freely about how you&apos;re feeling. We&apos;ll analyze both
                your words and your tone to understand you better, then respond
                with a calm, spoken reply.
              </p>
            </div>

            {!user && (
              <p className="text-xs text-on-surface-variant">
                <button
                  onClick={() => openAuthModal("login")}
                  className="text-primary font-medium hover:underline"
                >
                  Sign in
                </button>{" "}
                to save session history.
              </p>
            )}

            <button
              onClick={handleStartSession}
              disabled={sessionStarting}
              className="btn-sanctuary px-8 py-3.5 rounded-full text-sm font-medium flex items-center gap-2 cursor-pointer disabled:opacity-50"
            >
              {sessionStarting ? (
                <>
                  <div className="w-4 h-4 rounded-full border-2 border-on-primary border-t-transparent animate-spin" />
                  <span>Preparing...</span>
                </>
              ) : (
                <>
                  <span>Begin Voice Session</span>
                  <span className="material-symbols-outlined text-sm">
                    arrow_forward
                  </span>
                </>
              )}
            </button>
          </div>
        </div>
      )}

      {/* ── Active Voice Session ────────────────────────────────── */}
      {sessionId && !summary && (
        <div className="grid grid-cols-1 md:grid-cols-12 gap-[var(--spacing-gutter)]">
          {/* Left: Recording Stage */}
          <div className="col-span-1 md:col-span-7 flex flex-col gap-4">
            <div className="glass-panel rounded-xl p-8 bg-surface-container-lowest flex flex-col items-center justify-center text-center min-h-[350px] gap-6 relative overflow-hidden">
              {/* Ambient orb */}
              <div className="absolute top-[-60px] right-[-60px] w-48 h-48 bg-primary/5 rounded-full blur-3xl animate-float-ambient" />

              {/* Mic Button */}
              <div className="relative">
                {recording && (
                  <>
                    <div className="absolute inset-0 rounded-full bg-primary/10 animate-ping scale-[1.8]" />
                    <div className="absolute inset-0 rounded-full bg-primary/20 animate-breathe scale-[1.4]" />
                  </>
                )}
                {processing && (
                  <div className="absolute inset-0 rounded-full bg-primary/10 animate-pulse scale-[1.5]" />
                )}
                <button
                  onClick={recording ? stopRecording : startRecording}
                  disabled={processing}
                  className={`relative w-28 h-28 rounded-full flex items-center justify-center transition-all duration-300 shadow-xl cursor-pointer disabled:opacity-50 ${
                    recording
                      ? "bg-rose-500 text-white scale-110"
                      : processing
                      ? "bg-primary/70 text-on-primary"
                      : "bg-primary text-on-primary hover:scale-105"
                  }`}
                >
                  <span className="material-symbols-outlined text-5xl">
                    {recording ? "stop" : processing ? "hourglass_top" : "mic"}
                  </span>
                </button>
              </div>

              {/* Timer */}
              {recording && (
                <div className="font-mono text-[24px] text-primary font-medium tabular-nums">
                  {Math.floor(seconds / 60)
                    .toString()
                    .padStart(2, "0")}
                  :{(seconds % 60).toString().padStart(2, "0")}
                </div>
              )}

              {/* Status text */}
              <div>
                <div className="font-sans text-[18px] font-medium text-on-surface">
                  {recording
                    ? "Listening... speak naturally"
                    : processing
                    ? "Analyzing your voice..."
                    : "Tap to speak"}
                </div>
                <p className="font-sans text-[14px] text-on-surface-variant mt-1">
                  {recording
                    ? "Talk about how you're feeling today"
                    : processing
                    ? "Understanding your words and emotional tone"
                    : "Share what's on your mind"}
                </p>
              </div>

              {/* Processing animation */}
              {processing && (
                <div className="flex items-center gap-2">
                  <div className="animate-sanctuary-shimmer w-32 h-2 rounded-full" />
                </div>
              )}
            </div>

            {error && (
              <div className="p-3 rounded-xl bg-error/10 border border-error/20 text-error text-sm">
                {error}
              </div>
            )}
          </div>

          {/* Right: Conversation History */}
          <div className="col-span-1 md:col-span-5 flex flex-col gap-4">
            {turns.length > 0 ? (
              <div className="flex flex-col gap-4 max-h-[500px] overflow-y-auto pr-1">
                {turns.map((turn) => (
                  <VoiceTurnCard key={turn.id} turn={turn} onPlay={playAudio} />
                ))}
              </div>
            ) : (
              <div className="glass-panel rounded-xl p-8 bg-surface-container-lowest flex flex-col items-center justify-center text-center h-full min-h-[300px] gap-3">
                <span className="text-4xl">🎧</span>
                <div className="font-sans text-[18px] font-medium text-on-surface">
                  Ready to listen
                </div>
                <p className="font-sans text-[14px] text-on-surface-variant max-w-xs leading-relaxed">
                  Tap the microphone to start speaking. Your conversation will
                  appear here as we talk.
                </p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ── Session Summary ────────────────────────────────────── */}
      {summary && (
        <div className="flex items-center justify-center min-h-[400px]">
          <div className="glass-panel-elevated rounded-2xl p-8 max-w-lg w-full flex flex-col gap-5 animate-sanctuary-in">
            <div className="text-center">
              <div className="w-16 h-16 rounded-full bg-primary/10 flex items-center justify-center mx-auto mb-3">
                <span className="material-symbols-outlined text-primary text-3xl">
                  check_circle
                </span>
              </div>
              <h2 className="text-xl font-semibold text-on-surface mb-1">
                Voice Session Complete
              </h2>
              <p className="text-sm text-on-surface-variant">
                {turns.length} exchange{turns.length !== 1 ? "s" : ""} in this session
              </p>
            </div>

            <div className="p-4 rounded-xl bg-surface-variant/20 border border-outline-variant/15 text-sm text-on-surface leading-relaxed">
              {summary.summary_text}
            </div>

            {summary.techniques_used.length > 0 && (
              <div className="flex flex-wrap gap-2">
                {summary.techniques_used.map((t, i) => (
                  <span key={i} className="tool-badge text-xs font-medium text-primary px-3 py-1">
                    {t}
                  </span>
                ))}
              </div>
            )}

            <button
              onClick={handleNewSession}
              className="btn-sanctuary px-6 py-3 rounded-full text-sm font-medium cursor-pointer mx-auto mt-2"
            >
              Start New Session
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════════
   VOICE TURN CARD COMPONENT
   ═══════════════════════════════════════════════════════════════════════ */

function VoiceTurnCard({
  turn,
  onPlay,
}: {
  turn: ConversationTurn;
  onPlay: (base64: string) => void;
}) {
  const emotion = emotionEmoji(turn.speechEmotion);

  return (
    <div className="glass-panel rounded-xl p-4 flex flex-col gap-3 animate-sanctuary-in">
      {/* Emotion badge */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-lg">{emotion.emoji}</span>
          <span className="text-xs font-medium text-on-surface-variant uppercase tracking-wider">
            {emotion.label}
          </span>
        </div>
        <span className="text-[11px] text-on-surface-variant/50">
          {turn.timestamp.toLocaleTimeString([], {
            hour: "2-digit",
            minute: "2-digit",
          })}
        </span>
      </div>

      {/* User transcript */}
      <div className="p-3 rounded-lg bg-primary/5 border border-primary/10">
        <span className="text-[11px] uppercase tracking-wider text-primary font-medium block mb-1">
          You said
        </span>
        <p className="text-[14px] text-on-surface leading-relaxed">
          {turn.userTranscript}
        </p>
      </div>

      {/* Assistant reply */}
      <div className="p-3 rounded-lg bg-surface-variant/20 border border-outline-variant/10">
        <div className="flex items-center justify-between mb-1">
          <span className="text-[11px] uppercase tracking-wider text-on-surface-variant font-medium">
            EmoCare
          </span>
          {turn.audioBase64 && (
            <button
              onClick={() => onPlay(turn.audioBase64!)}
              className="flex items-center gap-1 text-[11px] text-primary font-medium hover:underline cursor-pointer"
            >
              <span className="material-symbols-outlined text-sm">
                play_circle
              </span>
              Play
            </button>
          )}
        </div>
        <p className="text-[14px] text-on-surface leading-relaxed">
          {turn.assistantReply}
        </p>
      </div>

      {/* Tools used */}
      {turn.toolsUsed.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {turn.toolsUsed.map((tool, i) => (
            <span
              key={i}
              className="tool-badge text-[10px] font-medium text-primary px-2 py-0.5 flex items-center gap-1"
            >
              <span className="material-symbols-outlined text-[11px]">
                build
              </span>
              {tool.tool_name.replace(/_/g, " ")}
            </span>
          ))}
        </div>
      )}

      {/* Crisis banner */}
      {turn.crisisActivated && (
        <div className="crisis-banner px-3 py-2 text-[12px] text-on-surface flex items-center gap-2">
          <span className="material-symbols-outlined text-sm text-risk-high">
            emergency
          </span>
          <span>Crisis support resources provided</span>
        </div>
      )}
    </div>
  );
}
