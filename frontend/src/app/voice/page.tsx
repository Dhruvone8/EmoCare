"use client";

import { useState, useRef } from "react";
import { predictSpeech } from "@/lib/api";
import type { SpeechResponse } from "@/types/api";

function translateEmotion(emotion: string): { emoji: string; message: string } {
  const map: Record<string, { emoji: string; message: string }> = {
    neutral: { emoji: "😌", message: "You sound calm and collected" },
    calm: { emoji: "🧘", message: "Your voice feels peaceful and steady" },
    happy: { emoji: "😊", message: "There's a brightness in your voice" },
    sad: { emoji: "🥺", message: "You sound a little sad — it's okay to feel this way" },
    angry: { emoji: "😤", message: "There's some tension in your voice today" },
    fearful: { emoji: "😰", message: "You sound a bit anxious — take a deep breath" },
    disgust: { emoji: "😞", message: "Something seems to be bothering you" },
    surprised: { emoji: "😯", message: "You sound surprised or caught off guard" },
  };
  const lower = emotion.toLowerCase();
  return map[lower] || { emoji: "🎙️", message: `You're feeling ${emotion}` };
}

function getTopEmotions(probs: Record<string, number>, topN = 3) {
  return Object.entries(probs)
    .sort(([, a], [, b]) => b - a)
    .slice(0, topN);
}

export default function VoicePage() {
  const [recording, setRecording] = useState(false);
  const [audioBlob, setAudioBlob] = useState<Blob | null>(null);
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<SpeechResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [seconds, setSeconds] = useState(0);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaRecorderRef.current = new MediaRecorder(stream);
      chunksRef.current = [];

      mediaRecorderRef.current.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };

      mediaRecorderRef.current.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: "audio/wav" });
        setAudioBlob(blob);
        setAudioUrl(URL.createObjectURL(blob));
        stream.getTracks().forEach((track) => track.stop());
        if (timerRef.current) clearInterval(timerRef.current);
      };

      setSeconds(0);
      timerRef.current = setInterval(() => setSeconds((s) => s + 1), 1000);

      mediaRecorderRef.current.start();
      setRecording(true);
      setResult(null);
      setError(null);
    } catch {
      setError("We couldn't access your microphone. Please check your browser permissions.");
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && recording) {
      mediaRecorderRef.current.stop();
      setRecording(false);
      if (timerRef.current) clearInterval(timerRef.current);
    }
  };

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setAudioBlob(file);
      setAudioUrl(URL.createObjectURL(file));
      setResult(null);
      setError(null);
    }
  };

  const handleAnalyze = async () => {
    if (!audioBlob) return;
    setLoading(true);
    setError(null);
    try {
      const res = await predictSpeech(audioBlob);
      setResult(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  const emotionInfo = result
    ? translateEmotion(result.emotion_detail.detected_emotion)
    : null;

  const topEmotions = result
    ? getTopEmotions(result.emotion_detail.emotion_probabilities)
    : [];

  return (
    <>
      {/* ── Page Header ────────────────────────────────────────────── */}
      <section className="max-w-3xl">
        <h1 className="font-sans text-[32px] md:text-[44px] font-semibold text-on-surface tracking-tight leading-tight mb-3">
          Talk it out 🎙️
        </h1>
        <p className="font-sans text-[18px] text-on-surface-variant max-w-2xl leading-7">
          Sometimes it helps to just say it out loud. Speak naturally for 10–30
          seconds — about your day, your feelings, anything. We&apos;ll listen.
        </p>
      </section>

      {/* ── Main Grid ──────────────────────────────────────────────── */}
      <div className="grid grid-cols-1 md:grid-cols-12 gap-[var(--spacing-gutter)]">
        {/* Left: Recording Stage */}
        <div className="col-span-1 md:col-span-7 flex flex-col gap-4">
          <div className="glass-panel rounded-xl p-8 bg-surface-container-lowest flex flex-col items-center justify-center text-center min-h-[380px] gap-6 relative overflow-hidden">
            {/* Mic Button */}
            <div className="relative">
              {recording && (
                <>
                  <div className="absolute inset-0 rounded-full bg-primary/10 animate-ping scale-[1.8]" />
                  <div className="absolute inset-0 rounded-full bg-primary/20 animate-pulse scale-[1.4]" />
                </>
              )}
              <button
                onClick={recording ? stopRecording : startRecording}
                className={`relative w-28 h-28 rounded-full flex items-center justify-center transition-all duration-300 shadow-xl ${
                  recording
                    ? "bg-rose-500 text-white scale-110"
                    : "bg-primary text-on-primary hover:scale-105"
                }`}
              >
                <span className="material-symbols-outlined text-5xl">
                  {recording ? "stop" : "mic"}
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

            <div>
              <div className="font-sans text-[18px] font-medium text-on-surface">
                {recording
                  ? "Listening... speak naturally"
                  : audioBlob
                    ? "Your recording is ready ✓"
                    : "Tap the microphone to start"}
              </div>
              <p className="font-sans text-[14px] text-on-surface-variant mt-1">
                {recording
                  ? "Talk about how you're feeling today"
                  : "Or upload an existing recording"}
              </p>
            </div>

            {audioUrl && !recording && (
              <audio controls src={audioUrl} className="w-full max-w-sm" />
            )}

            {/* Actions */}
            <div className="flex items-center gap-3 flex-wrap justify-center">
              {!recording && (
                <label className="px-4 py-2 border border-outline-variant/30 rounded-full font-sans text-[13px] font-medium text-on-surface-variant hover:bg-surface-variant/50 cursor-pointer transition-colors">
                  Upload audio file
                  <input
                    type="file"
                    accept="audio/*"
                    onChange={handleFileUpload}
                    className="hidden"
                  />
                </label>
              )}
              {audioBlob && !recording && (
                <button
                  onClick={handleAnalyze}
                  disabled={loading}
                  className="px-6 py-2.5 bg-primary text-on-primary rounded-full font-sans text-[13px] font-medium hover:bg-primary-container disabled:opacity-50 transition-all flex items-center gap-2"
                >
                  {loading ? (
                    <>
                      <div className="w-4 h-4 rounded-full border-2 border-on-primary border-t-transparent animate-spin" />
                      <span>Listening closely...</span>
                    </>
                  ) : (
                    <span>See what we heard</span>
                  )}
                </button>
              )}
            </div>
          </div>

          {error && (
            <div className="p-4 rounded-lg bg-error-container text-on-error-container text-sm font-sans">
              {error}
            </div>
          )}
        </div>

        {/* Right: Emotion Insights */}
        <div className="col-span-1 md:col-span-5 flex flex-col gap-4">
          {result && emotionInfo ? (
            <>
              {/* Primary Emotion */}
              <div className="glass-panel rounded-xl p-6 bg-surface-container-lowest flex flex-col gap-4">
                <div className="font-sans text-[13px] font-medium uppercase tracking-wider text-on-surface-variant">
                  How you sound
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-4xl">{emotionInfo.emoji}</span>
                  <span className="font-sans text-[18px] font-medium text-on-surface leading-6">
                    {emotionInfo.message}
                  </span>
                </div>
              </div>

              {/* Top Emotions Simplified */}
              <div className="glass-panel rounded-xl p-6 bg-surface-container-lowest flex flex-col gap-3">
                <div className="font-sans text-[13px] font-medium uppercase tracking-wider text-on-surface-variant">
                  Emotional tones we picked up
                </div>
                {topEmotions.map(([emo, prob]) => {
                  const { emoji } = translateEmotion(emo);
                  return (
                    <div
                      key={emo}
                      className="flex items-center gap-3 p-3 rounded-lg bg-surface border border-outline-variant/15"
                    >
                      <span className="text-xl">{emoji}</span>
                      <span className="font-sans text-[15px] font-medium text-on-surface capitalize flex-1">
                        {emo}
                      </span>
                      <div className="w-24 h-2 rounded-full bg-surface-container-high overflow-hidden">
                        <div
                          className="h-full bg-primary transition-all duration-500 rounded-full"
                          style={{ width: `${Math.round(prob * 100)}%` }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* Suggestion */}
              {result.predicted_risk_tier !== "Low" && (
                <div className="glass-panel rounded-xl p-5 bg-primary/5 border border-primary/15 flex flex-col gap-2">
                  <div className="flex items-center gap-2 font-sans font-medium text-sm text-primary">
                    <span className="material-symbols-outlined text-base">
                      self_improvement
                    </span>
                    <span>A suggestion for you</span>
                  </div>
                  <p className="text-[14px] text-on-surface-variant leading-relaxed font-sans">
                    Try taking 5 slow, deep breaths. Inhale for 4 seconds, hold for 4, exhale for 4. It can help settle your nervous system.
                  </p>
                </div>
              )}
            </>
          ) : (
            <div className="glass-panel rounded-xl p-8 bg-surface-container-lowest flex flex-col items-center justify-center text-center h-full min-h-[300px] gap-3">
              <span className="text-4xl">🎧</span>
              <div className="font-sans text-[18px] font-medium text-on-surface">
                We&apos;re ready to listen
              </div>
              <p className="font-sans text-[14px] text-on-surface-variant max-w-xs leading-relaxed">
                Record or upload a voice clip, and we&apos;ll share what emotions we picked up from your tone.
              </p>
            </div>
          )}
        </div>
      </div>
    </>
  );
}
