"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import { useAuth } from "@/context/AuthContext";
import { startSession, sendVoiceTherapy, endSession, getVoiceGreeting } from "@/lib/api";
import type {
  VoiceTherapyResponse,
  ToolInvocation,
} from "@/types/api";

/* ── Conversation State Machine ────────────────────────────────────── */
type ConversationState =
  | "idle"              // Session not started or ended
  | "listening"         // Mic open, VAD active, waiting for speech
  | "user_speaking"     // User speech detected, capturing audio
  | "processing"        // Silence detected, turn sent to backend
  | "emocare_speaking"  // EmoCare TTS playing, mic muted to prevent echo
  | "paused";           // User manually paused hands-free mode

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

/* ── VAD Hysteresis Tuning Constants ─────────────────────────────────── */
const TARGET_SAMPLE_RATE = 16000;      // 16kHz mono — Whisper & SER native rate
const BASE_ONSET_THRESHOLD = 0.022;    // Speech onset trigger (Standard)
const HIGH_ONSET_THRESHOLD = 0.015;    // Speech onset trigger (High sensitivity)
const BASE_SUSTAIN_THRESHOLD = 0.011;  // Speech sustain threshold (Standard)
const HIGH_SUSTAIN_THRESHOLD = 0.008;  // Speech sustain threshold (High sensitivity)
const SILENCE_TIMEOUT_MS = 2000;       // 2.0s natural pause window (no cut-offs)
const MIN_SPEECH_DURATION_MS = 500;    // Reject sounds shorter than 0.5s (coughs/clicks)
const MIN_SPEECH_RMS = 0.012;          // Reject dead/near-silent recordings

/* ── WAV Encoding Helper ───────────────────────────────────────────── */
function encodeWAV(samples: Float32Array, sampleRate: number = 16000): Blob {
  const buffer = new ArrayBuffer(44 + samples.length * 2);
  const view = new DataView(buffer);

  /* RIFF identifier */
  writeString(view, 0, "RIFF");
  /* file length */
  view.setUint32(4, 36 + samples.length * 2, true);
  /* RIFF type */
  writeString(view, 8, "WAVE");
  /* format chunk identifier */
  writeString(view, 12, "fmt ");
  /* format chunk length */
  view.setUint32(16, 16, true);
  /* sample format (raw PCM) */
  view.setUint16(20, 1, true);
  /* channel count (1 = mono) */
  view.setUint16(22, 1, true);
  /* sample rate */
  view.setUint32(24, sampleRate, true);
  /* byte rate (sample rate * block align) */
  view.setUint32(28, sampleRate * 2, true);
  /* block align (channel count * bytes per sample) */
  view.setUint16(32, 2, true);
  /* bits per sample */
  view.setUint16(34, 16, true);
  /* data chunk identifier */
  writeString(view, 36, "data");
  /* data chunk length */
  view.setUint32(40, samples.length * 2, true);

  /* float32 (-1.0 to 1.0) to signed 16-bit PCM */
  let offset = 44;
  for (let i = 0; i < samples.length; i++) {
    const s = Math.max(-1, Math.min(1, samples[i]));
    view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7fff, true);
    offset += 2;
  }

  return new Blob([view], { type: "audio/wav" });
}

function writeString(view: DataView, offset: number, string: string) {
  for (let i = 0; i < string.length; i++) {
    view.setUint8(offset + i, string.charCodeAt(i));
  }
}

/* ── High-Quality Audio Downsampling Helper ─────────────────────────── */
function downsampleBuffer(buffer: Float32Array, inRate: number, outRate: number): Float32Array {
  if (inRate === outRate) return new Float32Array(buffer);
  const ratio = inRate / outRate;
  const outLength = Math.round(buffer.length / ratio);
  const result = new Float32Array(outLength);
  let offsetResult = 0;
  let offsetBuffer = 0;
  while (offsetResult < outLength) {
    const nextOffsetBuffer = Math.round((offsetResult + 1) * ratio);
    let accum = 0;
    let count = 0;
    for (let i = offsetBuffer; i < nextOffsetBuffer && i < buffer.length; i++) {
      accum += buffer[i];
      count++;
    }
    result[offsetResult] = count > 0 ? accum / count : buffer[offsetBuffer];
    offsetResult++;
    offsetBuffer = nextOffsetBuffer;
  }
  return result;
}

export default function VoiceTherapyPage() {
  const { user, openAuthModal } = useAuth();

  /* Session state */
  const [sessionId, setSessionId] = useState<number | null>(null);
  const [sessionStarting, setSessionStarting] = useState(false);
  const [sessionEnding, setSessionEnding] = useState(false);

  /* Conversation state machine */
  const [conversationState, setConversationState] = useState<ConversationState>("idle");
  const [highSensitivity, setHighSensitivity] = useState(false);
  const [silenceRemaining, setSilenceRemaining] = useState<number>(0);
  const [audioLevel, setAudioLevel] = useState<number>(0);
  const [sessionDuration, setSessionDuration] = useState<number>(0);

  /* Conversation history */
  const [turns, setTurns] = useState<ConversationTurn[]>([]);
  const [latestReply, setLatestReply] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  /* Summary state */
  const [summary, setSummary] = useState<{
    summary_text: string;
    concerns: string[];
    goals: string[];
    techniques_used: string[];
  } | null>(null);

  /* Refs for audio pipeline */
  const sessionIdRef = useRef<number | null>(null);
  const stateRef = useRef<ConversationState>("idle");
  const streamRef = useRef<MediaStream | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const scriptNodeRef = useRef<ScriptProcessorNode | null>(null);
  const sourceNodeRef = useRef<MediaStreamAudioSourceNode | null>(null);

  /* PCM audio capture buffers */
  const preRollChunksRef = useRef<Float32Array[]>([]);
  const speechChunksRef = useRef<Float32Array[]>([]);
  const onsetDebounceCountRef = useRef<number>(0);
  const speechStartTimeRef = useRef<number>(0);
  const lastSpeechTimeRef = useRef<number>(0);

  const isRequestInFlightRef = useRef<boolean>(false);
  const audioElementRef = useRef<HTMLAudioElement | null>(null);
  const sessionTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const historyEndRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    stateRef.current = conversationState;
  }, [conversationState]);

  useEffect(() => {
    sessionIdRef.current = sessionId;
  }, [sessionId]);

  // Auto-scroll turn history
  useEffect(() => {
    historyEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [turns, latestReply, conversationState]);

  const userId =
    user?.id || "guest_" + (typeof window !== "undefined" ? window.location.hostname : "anon");

  /* ── Resume Listening Helper ──────────────────────────────────────── */
  const resumeListening = useCallback(() => {
    if (stateRef.current === "idle" || stateRef.current === "paused") return;

    // Unmute hardware mic track
    if (streamRef.current) {
      streamRef.current.getAudioTracks().forEach((track) => {
        track.enabled = true;
      });
    }

    // Reset speech buffers
    speechChunksRef.current = [];
    preRollChunksRef.current = [];
    onsetDebounceCountRef.current = 0;
    speechStartTimeRef.current = 0;
    lastSpeechTimeRef.current = 0;
    setSilenceRemaining(0);

    stateRef.current = "listening";
    setConversationState("listening");
  }, []);

  /* ── Play EmoCare Response with Echo Prevention ────────────────────── */
  const playEmoCareResponse = useCallback((base64Audio: string) => {
    stateRef.current = "emocare_speaking";
    setConversationState("emocare_speaking");

    // 100% Echo Prevention: Mute hardware mic track during TTS playback
    if (streamRef.current) {
      streamRef.current.getAudioTracks().forEach((track) => {
        track.enabled = false;
      });
    }

    try {
      const audio = new Audio(`data:audio/mp3;base64,${base64Audio}`);
      audioElementRef.current = audio;

      const finishPlayback = () => {
        // Delay 350ms for room acoustics / speaker reverb to dissipate
        setTimeout(() => {
          resumeListening();
        }, 350);
      };

      audio.onended = finishPlayback;
      audio.onerror = () => {
        resumeListening();
      };

      audio.play().catch(() => {
        resumeListening();
      });
    } catch {
      resumeListening();
    }
  }, [resumeListening]);

  /* ── Send Turn to Backend ─────────────────────────────────────────── */
  const sendTurnToBackend = useCallback(async (wavBlob: Blob) => {
    if (!sessionIdRef.current || isRequestInFlightRef.current) return;
    isRequestInFlightRef.current = true;
    stateRef.current = "processing";
    setConversationState("processing");

    // Mute mic track during backend processing
    if (streamRef.current) {
      streamRef.current.getAudioTracks().forEach((t) => {
        t.enabled = false;
      });
    }

    try {
      const res: VoiceTherapyResponse = await sendVoiceTherapy(
        sessionIdRef.current,
        userId,
        wavBlob
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
      setLatestReply(res.reply_text);
      setError(null);

      // Play audio response automatically
      if (res.reply_audio_base64) {
        playEmoCareResponse(res.reply_audio_base64);
      } else {
        resumeListening();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Voice processing failed.");
      resumeListening();
    } finally {
      isRequestInFlightRef.current = false;
    }
  }, [userId, playEmoCareResponse, resumeListening]);

  /* ── Finalize User Turn ───────────────────────────────────────────── */
  const finalizeUserTurn = useCallback(() => {
    if (isRequestInFlightRef.current) return;

    const chunks = speechChunksRef.current;
    speechChunksRef.current = [];

    if (!chunks.length) {
      resumeListening();
      return;
    }

    // Combine all downsampled chunks
    let totalSamples = 0;
    for (const c of chunks) totalSamples += c.length;

    const combined = new Float32Array(totalSamples);
    let offset = 0;
    for (const c of chunks) {
      combined.set(c, offset);
      offset += c.length;
    }

    // Verify minimum audio duration (at least 0.45s = 7,200 samples)
    if (combined.length < 7200) {
      resumeListening();
      return;
    }

    // Check RMS energy of the speech recording
    let sumSq = 0;
    for (let i = 0; i < combined.length; i++) {
      sumSq += combined[i] * combined[i];
    }
    const rms = Math.sqrt(sumSq / combined.length);

    if (rms < MIN_SPEECH_RMS) {
      // Discard silent or near-silent recording locally
      resumeListening();
      return;
    }

    // Encode to 100% compliant 16kHz mono WAV
    const wavBlob = encodeWAV(combined, TARGET_SAMPLE_RATE);
    sendTurnToBackend(wavBlob);
  }, [resumeListening, sendTurnToBackend]);

  /* ── Start Local Audio & VAD Pipeline ─────────────────────────────── */
  const startAudioPipeline = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });
      streamRef.current = stream;

      const AudioCtx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      const ctx = new AudioCtx();
      audioContextRef.current = ctx;

      const sourceNode = ctx.createMediaStreamSource(stream);
      sourceNodeRef.current = sourceNode;

      // ScriptProcessor captures raw PCM audio directly without container corruption
      const bufferSize = 4096;
      const scriptNode = ctx.createScriptProcessor(bufferSize, 1, 1);
      scriptNodeRef.current = scriptNode;

      sourceNode.connect(scriptNode);
      scriptNode.connect(ctx.destination);

      scriptNode.onaudioprocess = (e) => {
        const inputData = e.inputBuffer.getChannelData(0);

        // Compute RMS energy on raw buffer
        let sumSq = 0;
        for (let i = 0; i < inputData.length; i++) {
          sumSq += inputData[i] * inputData[i];
        }
        const rms = Math.sqrt(sumSq / inputData.length);
        setAudioLevel(Math.min(rms * 5.0, 1.0));

        const currentState = stateRef.current;
        if (currentState === "idle" || currentState === "processing" || currentState === "emocare_speaking" || currentState === "paused") {
          return;
        }

        // Downsample input chunk to 16kHz mono
        const downsampled = downsampleBuffer(inputData, ctx.sampleRate, TARGET_SAMPLE_RATE);
        const now = Date.now();
        const onsetThresh = highSensitivity ? HIGH_ONSET_THRESHOLD : BASE_ONSET_THRESHOLD;
        const sustainThresh = highSensitivity ? HIGH_SUSTAIN_THRESHOLD : BASE_SUSTAIN_THRESHOLD;

        if (currentState === "listening") {
          if (rms >= onsetThresh) {
            onsetDebounceCountRef.current++;
            // Require 2 consecutive frames (~100ms) of sound above onset threshold
            if (onsetDebounceCountRef.current >= 2) {
              stateRef.current = "user_speaking";
              setConversationState("user_speaking");
              speechStartTimeRef.current = now;
              lastSpeechTimeRef.current = now;

              // Prepend entire 400ms pre-roll buffer so opening syllable is never clipped
              speechChunksRef.current = [...preRollChunksRef.current, downsampled];
              preRollChunksRef.current = [];
              onsetDebounceCountRef.current = 0;
              setSilenceRemaining(2.0);
            }
          } else {
            onsetDebounceCountRef.current = 0;
            // Maintain 400ms pre-roll circular buffer
            preRollChunksRef.current.push(downsampled);
            // 400ms at 16kHz is ~6,400 samples
            let totalPreRoll = 0;
            for (const c of preRollChunksRef.current) totalPreRoll += c.length;
            while (totalPreRoll > 6400 && preRollChunksRef.current.length > 1) {
              const removed = preRollChunksRef.current.shift();
              if (removed) totalPreRoll -= removed.length;
            }
          }
        } else if (currentState === "user_speaking") {
          speechChunksRef.current.push(downsampled);

          if (rms >= sustainThresh) {
            // User is actively speaking (even quiet/trailing syllables)
            lastSpeechTimeRef.current = now;
            setSilenceRemaining(2.0);
          } else {
            // Silence detected mid-speech
            const silenceElapsed = now - lastSpeechTimeRef.current;
            const remaining = Math.max(0, (SILENCE_TIMEOUT_MS - silenceElapsed) / 1000);
            setSilenceRemaining(Number(remaining.toFixed(1)));

            if (silenceElapsed >= SILENCE_TIMEOUT_MS) {
              const speechDuration = lastSpeechTimeRef.current - speechStartTimeRef.current;
              if (speechDuration >= MIN_SPEECH_DURATION_MS) {
                // Completed valid speech turn! Finalize WAV and send.
                finalizeUserTurn();
              } else {
                // Short noise/throat clear (<0.5s) — discard without calling backend
                speechChunksRef.current = [];
                stateRef.current = "listening";
                setConversationState("listening");
                setSilenceRemaining(0);
              }
            }
          }
        }
      };

      stateRef.current = "listening";
      setConversationState("listening");
      setError(null);
    } catch {
      setError("Microphone access is needed for Voice Therapy. Please check browser permissions.");
    }
  }, [finalizeUserTurn, highSensitivity]);

  /* ── Teardown Audio Pipeline ──────────────────────────────────────── */
  const teardownAudioPipeline = () => {
    if (audioElementRef.current) {
      audioElementRef.current.pause();
      audioElementRef.current = null;
    }
    if (scriptNodeRef.current) {
      scriptNodeRef.current.disconnect();
      scriptNodeRef.current = null;
    }
    if (sourceNodeRef.current) {
      sourceNodeRef.current.disconnect();
      sourceNodeRef.current = null;
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }
    if (audioContextRef.current) {
      audioContextRef.current.close().catch(() => {});
      audioContextRef.current = null;
    }
    if (sessionTimerRef.current) {
      clearInterval(sessionTimerRef.current);
      sessionTimerRef.current = null;
    }
    setAudioLevel(0);
    setSilenceRemaining(0);
  };

  /* ── Start Therapy Session ────────────────────────────────────────── */
  const handleStartSession = useCallback(async () => {
    setSessionStarting(true);
    setError(null);
    setSummary(null);
    setLatestReply(null);
    try {
      const res = await startSession({
        user_id: userId,
        mode: "voice",
      });
      setSessionId(res.session_id);
      sessionIdRef.current = res.session_id;
      setTurns([]);
      setSessionDuration(0);

      sessionTimerRef.current = setInterval(() => {
        setSessionDuration((s) => s + 1);
      }, 1000);

      // Determine local time of day for greeting
      const hour = new Date().getHours();
      const tod = hour >= 5 && hour < 12 ? "morning" : hour >= 12 && hour < 17 ? "afternoon" : "evening";

      // 1. Initialize microphone stream & audio nodes
      await startAudioPipeline();

      // 2. Fetch proactive therapist opening greeting with speech
      try {
        const greeting = await getVoiceGreeting(res.session_id, userId, tod);
        if (greeting && greeting.greeting_text) {
          const openingTurn: ConversationTurn = {
            id: `greeting-${Date.now()}`,
            userTranscript: "Session opened",
            assistantReply: greeting.greeting_text,
            audioBase64: greeting.audio_base64,
            speechEmotion: "calm",
            riskTier: "Low",
            crisisActivated: false,
            toolsUsed: [],
            timestamp: new Date(),
          };
          setTurns([openingTurn]);
          setLatestReply(greeting.greeting_text);

          if (greeting.audio_base64) {
            playEmoCareResponse(greeting.audio_base64);
          } else {
            resumeListening();
          }
        }
      } catch (greetErr) {
        console.warn("Could not fetch greeting audio, falling back to listening:", greetErr);
        resumeListening();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start voice therapy session.");
    } finally {
      setSessionStarting(false);
    }
  }, [userId, playEmoCareResponse, resumeListening, startAudioPipeline]);

  /* ── End Therapy Session ──────────────────────────────────────────── */
  const handleEndSession = async () => {
    if (!sessionId) return;
    setSessionEnding(true);
    teardownAudioPipeline();
    stateRef.current = "idle";
    setConversationState("idle");

    try {
      const res = await endSession({ session_id: sessionId, user_id: userId });
      setSummary(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to generate session summary.");
    } finally {
      setSessionEnding(false);
    }
  };

  /* ── Interrupt Assistant Playback ─────────────────────────────────── */
  const handleInterrupt = () => {
    if (audioElementRef.current) {
      audioElementRef.current.pause();
      audioElementRef.current.currentTime = 0;
    }
    resumeListening();
  };

  /* ── Toggle Pause Hands-Free ──────────────────────────────────────── */
  const handleTogglePause = () => {
    if (conversationState === "paused") {
      resumeListening();
    } else {
      if (audioElementRef.current) {
        audioElementRef.current.pause();
      }
      if (streamRef.current) {
        streamRef.current.getAudioTracks().forEach((t) => {
          t.enabled = false;
        });
      }
      stateRef.current = "paused";
      setConversationState("paused");
    }
  };

  /* ── Play Any Saved Turn Audio ────────────────────────────────────── */
  const playSavedAudio = (base64Audio: string) => {
    try {
      const audio = new Audio(`data:audio/mp3;base64,${base64Audio}`);
      audio.play().catch(() => {});
    } catch {}
  };

  useEffect(() => {
    return () => {
      teardownAudioPipeline();
    };
  }, []);

  return (
    <div className="max-w-5xl mx-auto flex flex-col gap-6 animate-sanctuary-in">
      {/* ── Top Header ─────────────────────────────────────────────── */}
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="font-sans text-[28px] md:text-[36px] font-semibold text-on-surface tracking-tight leading-tight flex items-center gap-3">
            <span
              className="material-symbols-outlined text-primary text-3xl"
              style={{ fontVariationSettings: "'FILL' 1" }}
            >
              record_voice_over
            </span>
            <span>Hands-Free Voice Therapy</span>
          </h1>
          <p className="font-sans text-[15px] text-on-surface-variant mt-1">
            Continuous, hands-free conversation with intelligent voice activity and silence detection.
          </p>
        </div>

        {sessionId && !summary && (
          <div className="flex items-center gap-3">
            {/* Session Timer */}
            <div className="px-3.5 py-1.5 rounded-full bg-surface-container border border-outline-variant/20 text-xs font-mono text-on-surface font-medium tabular-nums flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
              <span>
                {Math.floor(sessionDuration / 60)
                  .toString()
                  .padStart(2, "0")}
                :{(sessionDuration % 60).toString().padStart(2, "0")}
              </span>
            </div>

            {/* Pause / Resume Button */}
            <button
              onClick={handleTogglePause}
              className={`px-4 py-2 text-xs font-medium rounded-full border transition-all cursor-pointer flex items-center gap-1.5 ${
                conversationState === "paused"
                  ? "bg-primary text-on-primary border-primary hover:bg-primary/90"
                  : "border-outline-variant/30 text-on-surface-variant hover:text-on-surface hover:bg-surface-variant/20"
              }`}
            >
              <span className="material-symbols-outlined text-[16px]">
                {conversationState === "paused" ? "play_arrow" : "pause"}
              </span>
              <span>{conversationState === "paused" ? "Resume" : "Pause"}</span>
            </button>

            {/* End Session */}
            <button
              onClick={handleEndSession}
              disabled={sessionEnding}
              className="px-4 py-2 text-xs font-medium rounded-full border border-outline-variant/30 text-on-surface-variant hover:text-error hover:border-error/30 hover:bg-error/5 transition-all cursor-pointer"
            >
              {sessionEnding ? "Ending..." : "End Session"}
            </button>
          </div>
        )}
      </div>

      {/* ── Pre-Session Setup Screen ────────────────────────────────── */}
      {!sessionId && !summary && (
        <div className="flex items-center justify-center min-h-[460px]">
          <div className="glass-panel-elevated rounded-2xl p-8 md:p-12 max-w-lg text-center flex flex-col items-center gap-6 animate-sanctuary-in">
            <div className="w-24 h-24 rounded-full bg-primary/10 flex items-center justify-center relative">
              <div className="absolute inset-0 rounded-full bg-primary/5 animate-breathe" />
              <span
                className="material-symbols-outlined text-primary text-5xl relative z-10"
                style={{ fontVariationSettings: "'FILL' 1" }}
              >
                graphic_eq
              </span>
            </div>

            <div>
              <h2 className="text-2xl font-semibold text-on-surface mb-2">
                Your Voice Sanctuary
              </h2>
              <p className="text-sm text-on-surface-variant leading-relaxed max-w-sm">
                A seamless, natural therapy conversation. When you begin, the microphone
                will automatically listen, detect when you speak and pause, and reply in a calm, spoken voice.
              </p>
            </div>

            <div className="w-full bg-surface-container/40 p-4 rounded-xl border border-outline-variant/15 flex flex-col gap-2.5 text-left text-xs text-on-surface-variant">
              <div className="flex items-center gap-2">
                <span className="material-symbols-outlined text-primary text-[18px]">check_circle</span>
                <span>Automatic voice-activity and turn detection (no button pressing)</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="material-symbols-outlined text-primary text-[18px]">check_circle</span>
                <span>2.0s conversational pause window allows thinking without interruptions</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="material-symbols-outlined text-primary text-[18px]">check_circle</span>
                <span>Direct 16kHz PCM audio ensures 100% accurate Whisper transcription</span>
              </div>
            </div>

            {!user && (
              <p className="text-xs text-on-surface-variant">
                <button
                  onClick={() => openAuthModal("login")}
                  className="text-primary font-medium hover:underline cursor-pointer"
                >
                  Sign in
                </button>{" "}
                to save session history to your account.
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
                  <span>Activating Microphone...</span>
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

      {/* ── Active Continuous Session ───────────────────────────────── */}
      {sessionId && !summary && (
        <div className="grid grid-cols-1 md:grid-cols-12 gap-6 items-start">
          {/* Left Column: Dynamic Visualizer Stage */}
          <div className="col-span-1 md:col-span-7 flex flex-col gap-4">
            <div className="glass-panel rounded-2xl p-8 bg-surface-container-lowest flex flex-col items-center justify-center text-center min-h-[460px] gap-6 relative overflow-hidden">
              {/* Ambient Glow Aura */}
              <div
                className={`absolute w-72 h-72 rounded-full blur-3xl transition-all duration-700 pointer-events-none ${
                  conversationState === "listening"
                    ? "bg-primary/10 top-[-80px] right-[-80px] animate-float-ambient"
                    : conversationState === "user_speaking"
                    ? "bg-violet-500/15 top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 scale-125"
                    : conversationState === "processing"
                    ? "bg-amber-400/15 top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 animate-pulse"
                    : conversationState === "emocare_speaking"
                    ? "bg-emerald-500/15 top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 animate-breathe"
                    : "bg-surface-variant/20"
                }`}
              />

              {/* Status Badge */}
              <div className="z-10 flex items-center gap-2">
                {conversationState === "listening" && (
                  <span className="px-3.5 py-1.5 rounded-full text-xs font-medium bg-primary/10 text-primary border border-primary/20 flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-primary animate-ping" />
                    <span>Listening for your voice</span>
                  </span>
                )}
                {conversationState === "user_speaking" && (
                  <span className="px-3.5 py-1.5 rounded-full text-xs font-medium bg-violet-500/10 text-violet-700 border border-violet-500/20 flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-violet-600 animate-pulse" />
                    <span>User Speaking</span>
                  </span>
                )}
                {conversationState === "processing" && (
                  <span className="px-3.5 py-1.5 rounded-full text-xs font-medium bg-amber-500/10 text-amber-700 border border-amber-500/20 flex items-center gap-2">
                    <span className="w-3.5 h-3.5 border-2 border-amber-600 border-t-transparent rounded-full animate-spin" />
                    <span>Reflecting &amp; Understanding</span>
                  </span>
                )}
                {conversationState === "emocare_speaking" && (
                  <span className="px-3.5 py-1.5 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-700 border border-emerald-500/20 flex items-center gap-2">
                    <span className="material-symbols-outlined text-[16px] text-emerald-600 animate-pulse">
                      volume_up
                    </span>
                    <span>EmoCare Speaking</span>
                  </span>
                )}
                {conversationState === "paused" && (
                  <span className="px-3.5 py-1.5 rounded-full text-xs font-medium bg-surface-variant text-on-surface-variant flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-outline" />
                    <span>Microphone Paused</span>
                  </span>
                )}
              </div>

              {/* ── Dynamic Center Sanctuary Orb ────────────────────── */}
              <div className="relative flex items-center justify-center my-2">
                {/* Visualizer Halo Rings */}
                {conversationState === "listening" && (
                  <>
                    <div className="absolute w-44 h-44 rounded-full border border-primary/20 animate-breathe" />
                    <div className="absolute w-56 h-56 rounded-full border border-primary/10 animate-breathe" style={{ animationDelay: "1s" }} />
                  </>
                )}

                {conversationState === "user_speaking" && (
                  <>
                    <div
                      className="absolute w-48 h-48 rounded-full bg-violet-500/10 transition-transform duration-75"
                      style={{
                        transform: `scale(${1 + audioLevel * 0.4})`,
                      }}
                    />
                    <div
                      className="absolute w-56 h-56 rounded-full border border-violet-400/30 transition-transform duration-75"
                      style={{
                        transform: `scale(${1 + audioLevel * 0.6})`,
                      }}
                    />
                  </>
                )}

                {conversationState === "emocare_speaking" && (
                  <>
                    <div className="absolute w-48 h-48 rounded-full bg-emerald-500/10 animate-breathe" />
                    <div className="absolute w-56 h-56 rounded-full border border-emerald-500/25 animate-ping" style={{ animationDuration: "3s" }} />
                  </>
                )}

                {conversationState === "processing" && (
                  <div className="absolute w-48 h-48 rounded-full border-2 border-dashed border-amber-400/50 animate-spin" style={{ animationDuration: "8s" }} />
                )}

                {/* Central Action Sphere */}
                <div
                  className={`w-32 h-32 rounded-full flex flex-col items-center justify-center shadow-xl transition-all duration-300 relative z-10 ${
                    conversationState === "listening"
                      ? "bg-primary text-on-primary shadow-primary/25"
                      : conversationState === "user_speaking"
                      ? "bg-violet-600 text-white shadow-violet-500/35"
                      : conversationState === "processing"
                      ? "bg-amber-500 text-white shadow-amber-500/25"
                      : conversationState === "emocare_speaking"
                      ? "bg-emerald-600 text-white shadow-emerald-500/30"
                      : "bg-surface-variant text-on-surface-variant"
                  }`}
                  style={{
                    transform:
                      conversationState === "user_speaking"
                        ? `scale(${1 + Math.min(audioLevel * 0.25, 0.2)})`
                        : "scale(1)",
                  }}
                >
                  <span className="material-symbols-outlined text-4xl">
                    {conversationState === "listening"
                      ? "mic"
                      : conversationState === "user_speaking"
                      ? "graphic_eq"
                      : conversationState === "processing"
                      ? "psychology"
                      : conversationState === "emocare_speaking"
                      ? "volume_up"
                      : "mic_off"}
                  </span>
                </div>
              </div>

              {/* ── Status Guidance & Pause Indicators ──────────────── */}
              <div className="z-10 max-w-md flex flex-col items-center gap-1.5">
                {conversationState === "listening" && (
                  <>
                    <div className="font-sans text-[18px] font-medium text-on-surface">
                      Listening... Speak whenever you&apos;re ready
                    </div>
                    <p className="font-sans text-[13px] text-on-surface-variant">
                      Hands-free mode active. Share your thoughts naturally without clicking.
                    </p>
                  </>
                )}

                {conversationState === "user_speaking" && (
                  <>
                    <div className="font-sans text-[18px] font-medium text-on-surface flex items-center gap-2">
                      <span>Listening to you</span>
                      {/* Equalizer bars */}
                      <span className="flex items-end gap-1 h-4">
                        <span
                          className="w-1 bg-violet-600 rounded-full transition-all duration-75"
                          style={{ height: `${Math.max(4, audioLevel * 16)}px` }}
                        />
                        <span
                          className="w-1 bg-violet-600 rounded-full transition-all duration-75"
                          style={{ height: `${Math.max(6, audioLevel * 20)}px` }}
                        />
                        <span
                          className="w-1 bg-violet-600 rounded-full transition-all duration-75"
                          style={{ height: `${Math.max(4, audioLevel * 14)}px` }}
                        />
                      </span>
                    </div>

                    {/* Silence Countdown Indicator */}
                    {silenceRemaining < 2.0 && silenceRemaining > 0 && (
                      <div className="mt-1 flex items-center gap-2 px-3 py-1 rounded-full bg-violet-50 border border-violet-200 text-xs font-medium text-violet-800">
                        <span>Natural pause detected</span>
                        <span className="font-mono tabular-nums">({silenceRemaining}s)</span>
                      </div>
                    )}

                    <p className="font-sans text-[13px] text-on-surface-variant mt-0.5">
                      Pause when finished, or tap &ldquo;Send Now&rdquo; to respond immediately.
                    </p>

                    <button
                      onClick={finalizeUserTurn}
                      className="mt-2 px-4 py-1.5 text-xs font-medium rounded-full bg-violet-100 text-violet-800 hover:bg-violet-200 transition-colors cursor-pointer flex items-center gap-1.5"
                    >
                      <span className="material-symbols-outlined text-[15px]">send</span>
                      <span>Send Now</span>
                    </button>
                  </>
                )}

                {conversationState === "processing" && (
                  <>
                    <div className="font-sans text-[18px] font-medium text-on-surface">
                      Reflecting on your words...
                    </div>
                    <p className="font-sans text-[13px] text-on-surface-variant">
                      Analyzing vocal emotion and preparing thoughtful guidance
                    </p>
                    <div className="w-36 h-1.5 rounded-full bg-surface-container overflow-hidden mt-2">
                      <div className="animate-sanctuary-shimmer w-full h-full" />
                    </div>
                  </>
                )}

                {conversationState === "emocare_speaking" && (
                  <>
                    <div className="font-sans text-[18px] font-medium text-on-surface">
                      EmoCare is speaking
                    </div>
                    <p className="font-sans text-[13px] text-on-surface-variant">
                      Mic is automatically paused to prevent echo. It will resume when audio finishes.
                    </p>
                    <button
                      onClick={handleInterrupt}
                      className="mt-2 px-4 py-1.5 text-xs font-medium rounded-full border border-emerald-600/30 text-emerald-800 hover:bg-emerald-50 transition-colors cursor-pointer flex items-center gap-1.5"
                    >
                      <span className="material-symbols-outlined text-[15px]">pan_tool</span>
                      <span>Interrupt &amp; Speak</span>
                    </button>
                  </>
                )}

                {conversationState === "paused" && (
                  <>
                    <div className="font-sans text-[18px] font-medium text-on-surface">
                      Voice conversation paused
                    </div>
                    <p className="font-sans text-[13px] text-on-surface-variant">
                      Take a break or step away. Tap resume whenever you wish to continue.
                    </p>
                    <button
                      onClick={handleTogglePause}
                      className="mt-2 px-6 py-2 text-xs font-medium rounded-full bg-primary text-on-primary hover:bg-primary/90 transition-colors cursor-pointer"
                    >
                      Resume Listening
                    </button>
                  </>
                )}
              </div>

              {/* ── Subtitle / Latest Speech Preview ─────────────────── */}
              {latestReply && conversationState === "emocare_speaking" && (
                <div className="z-10 p-3.5 rounded-xl bg-surface-variant/30 border border-outline-variant/15 max-w-md text-center text-xs text-on-surface leading-relaxed animate-sanctuary-in">
                  &ldquo;{latestReply}&rdquo;
                </div>
              )}

              {/* ── Settings Bar (Sensitivity) ──────────────────────── */}
              <div className="mt-auto pt-4 border-t border-outline-variant/10 w-full flex items-center justify-between text-xs text-on-surface-variant">
                <div className="flex items-center gap-2">
                  <span className="material-symbols-outlined text-[16px] text-primary">
                    tune
                  </span>
                  <span>Mic Sensitivity:</span>
                  <button
                    onClick={() => setHighSensitivity(!highSensitivity)}
                    className="font-medium text-primary hover:underline cursor-pointer"
                  >
                    {highSensitivity ? "High (Quiet Voice)" : "Standard"}
                  </button>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-emerald-500" />
                  <span>16kHz PCM Active</span>
                </div>
              </div>
            </div>

            {error && (
              <div className="p-3.5 rounded-xl bg-error/10 border border-error/20 text-error text-sm flex items-center justify-between">
                <span>{error}</span>
                <button
                  onClick={() => setError(null)}
                  className="text-xs font-medium underline cursor-pointer"
                >
                  Dismiss
                </button>
              </div>
            )}
          </div>

          {/* Right Column: Live Conversation Stream */}
          <div className="col-span-1 md:col-span-5 flex flex-col gap-4">
            <div className="flex items-center justify-between">
              <h2 className="font-sans text-[15px] font-semibold text-on-surface flex items-center gap-2">
                <span className="material-symbols-outlined text-primary text-[18px]">forum</span>
                <span>Session Exchange ({turns.length})</span>
              </h2>
            </div>

            {turns.length > 0 ? (
              <div className="flex flex-col gap-4 max-h-[520px] overflow-y-auto pr-1">
                {turns.map((turn) => (
                  <VoiceTurnCard
                    key={turn.id}
                    turn={turn}
                    onPlay={playSavedAudio}
                  />
                ))}
                <div ref={historyEndRef} />
              </div>
            ) : (
              <div className="glass-panel rounded-2xl p-8 bg-surface-container-lowest flex flex-col items-center justify-center text-center h-[460px] gap-3">
                <div className="w-14 h-14 rounded-full bg-primary/10 flex items-center justify-center text-primary">
                  <span className="material-symbols-outlined text-2xl">hearing</span>
                </div>
                <div className="font-sans text-[16px] font-medium text-on-surface">
                  Waiting for your first words
                </div>
                <p className="font-sans text-[13px] text-on-surface-variant max-w-xs leading-relaxed">
                  Speak into your microphone. Your transcript, vocal emotion analysis, and EmoCare&apos;s responses will appear here automatically.
                </p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ── Session Summary Modal ────────────────────────────────────── */}
      {summary && (
        <div className="flex items-center justify-center min-h-[440px]">
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
                {turns.length} exchange{turns.length !== 1 ? "s" : ""} recorded in this session
              </p>
            </div>

            <div className="p-4 rounded-xl bg-surface-variant/20 border border-outline-variant/15 text-sm text-on-surface leading-relaxed">
              {summary.summary_text}
            </div>

            {summary.techniques_used.length > 0 && (
              <div className="flex flex-wrap gap-2">
                {summary.techniques_used.map((tech, i) => (
                  <span
                    key={i}
                    className="tool-badge text-xs font-medium text-primary px-3 py-1"
                  >
                    {tech}
                  </span>
                ))}
              </div>
            )}

            <button
              onClick={() => {
                setSessionId(null);
                setSummary(null);
                setTurns([]);
                setError(null);
              }}
              className="btn-sanctuary px-6 py-3 rounded-full text-sm font-medium cursor-pointer mx-auto mt-2"
            >
              Start New Voice Session
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
      {/* Emotion & Time Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-base">{emotion.emoji}</span>
          <span className="text-xs font-medium text-on-surface-variant uppercase tracking-wider">
            {emotion.label} Tone
          </span>
        </div>
        <span className="text-[11px] text-on-surface-variant/60 font-mono">
          {turn.timestamp.toLocaleTimeString([], {
            hour: "2-digit",
            minute: "2-digit",
          })}
        </span>
      </div>

      {/* User Transcript */}
      <div className="p-3 rounded-lg bg-primary/5 border border-primary/10">
        <span className="text-[10px] uppercase tracking-wider text-primary font-semibold block mb-1">
          You said
        </span>
        <p className="text-[13.5px] text-on-surface leading-relaxed">
          {turn.userTranscript}
        </p>
      </div>

      {/* Assistant Reply */}
      <div className="p-3 rounded-lg bg-surface-variant/20 border border-outline-variant/10">
        <div className="flex items-center justify-between mb-1">
          <span className="text-[10px] uppercase tracking-wider text-on-surface-variant font-semibold">
            EmoCare
          </span>
          {turn.audioBase64 && (
            <button
              onClick={() => onPlay(turn.audioBase64!)}
              className="flex items-center gap-1 text-[11px] text-primary font-medium hover:underline cursor-pointer"
            >
              <span className="material-symbols-outlined text-[15px]">
                play_circle
              </span>
              <span>Replay Audio</span>
            </button>
          )}
        </div>
        <p className="text-[13.5px] text-on-surface leading-relaxed">
          {turn.assistantReply}
        </p>
      </div>

      {/* Tools Used Badges */}
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

      {/* Crisis Banner */}
      {turn.crisisActivated && (
        <div className="crisis-banner px-3 py-2 text-[12px] text-on-surface flex items-center gap-2">
          <span className="material-symbols-outlined text-sm text-risk-high">
            emergency
          </span>
          <span>Crisis support resources activated</span>
        </div>
      )}
    </div>
  );
}
