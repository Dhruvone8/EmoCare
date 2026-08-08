"use client";

import { useState, useRef } from "react";
import { predictMultimodal } from "@/lib/api";
import type { MultimodalResponse, BehavioralRequest } from "@/types/api";

function translateOverallWellness(tier: string): { emoji: string; label: string; bg: string; border: string } {
  switch (tier) {
    case "High":
      return { emoji: "🧡", label: "We're a little worried about you", bg: "bg-rose-50", border: "border-rose-200" };
    case "Moderate":
      return { emoji: "💛", label: "Some mixed signals — let's check in", bg: "bg-amber-50", border: "border-amber-200" };
    default:
      return { emoji: "💚", label: "You're doing well overall", bg: "bg-emerald-50", border: "border-emerald-200" };
  }
}

function translateUrgency(urgency: string): string {
  switch (urgency) {
    case "CRITICAL":
      return "We strongly recommend talking to someone you trust";
    case "WARNING":
      return "There are a few things worth paying attention to";
    default:
      return "Everything looks stable right now";
  }
}

export default function InsightsPage() {
  const [text, setText] = useState("");
  const [audioBlob, setAudioBlob] = useState<Blob | null>(null);
  const [recording, setRecording] = useState(false);
  const [audioReady, setAudioReady] = useState(false);

  const [behavioral] = useState<BehavioralRequest>({
    sleep_hours: 7,
    sleep_quality: 3,
    activity_level: 3,
    social_interaction: 3,
    stress_level: 3,
    exercise_minutes: 30,
    mood_rating: 3,
  });

  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<MultimodalResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);

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
        setAudioReady(true);
        stream.getTracks().forEach((track) => track.stop());
      };
      mediaRecorderRef.current.start();
      setRecording(true);
    } catch {
      setError("Microphone access denied.");
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && recording) {
      mediaRecorderRef.current.stop();
      setRecording(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!text.trim() && !audioBlob) {
      setError("Please write something or record a voice clip first.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const res = await predictMultimodal({
        text: text.trim() || undefined,
        audio: audioBlob || undefined,
        behavioral,
      });
      setResult(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  const wellness = result ? translateOverallWellness(result.final_risk_tier) : null;

  return (
    <>
      {/* ── Header ─────────────────────────────────────────────────── */}
      <section className="max-w-3xl">
        <h1 className="font-sans text-[32px] md:text-[44px] font-semibold text-on-surface tracking-tight leading-tight mb-3">
          Your complete picture 🔮
        </h1>
        <p className="font-sans text-[18px] text-on-surface-variant max-w-2xl leading-7">
          We combine what you write, how you sound, and your daily habits to
          give you a fuller understanding of how you&apos;re doing.
        </p>
      </section>

      {/* ── Layout ─────────────────────────────────────────────────── */}
      <div className="grid grid-cols-1 md:grid-cols-12 gap-[var(--spacing-gutter)]">
        {/* Left: Inputs */}
        <form
          onSubmit={handleSubmit}
          className="col-span-1 md:col-span-5 flex flex-col gap-4"
        >
          {/* Text Input */}
          <div className="glass-panel rounded-xl p-5 bg-surface-container-lowest flex flex-col gap-3">
            <div className="flex items-center gap-2 text-primary font-sans text-sm font-medium">
              <span className="material-symbols-outlined text-base">edit_note</span>
              <span>How are you feeling?</span>
            </div>
            <textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder="Write a few words about how you're doing..."
              className="w-full h-24 bg-surface p-3 rounded-lg border border-outline-variant/20 font-sans text-sm text-on-surface outline-none resize-none"
            />
          </div>

          {/* Voice */}
          <div className="glass-panel rounded-xl p-5 bg-surface-container-lowest flex flex-col gap-3">
            <div className="flex items-center gap-2 text-secondary font-sans text-sm font-medium">
              <span className="material-symbols-outlined text-base">mic</span>
              <span>Share your voice (optional)</span>
            </div>
            <button
              type="button"
              onClick={recording ? stopRecording : startRecording}
              className={`w-full py-2.5 rounded-full font-sans text-[13px] font-medium flex items-center justify-center gap-2 transition-all ${
                recording
                  ? "bg-rose-500 text-white animate-pulse"
                  : audioReady
                    ? "bg-emerald-500/10 text-emerald-700 border border-emerald-500/30"
                    : "bg-secondary/10 text-secondary border border-secondary/20 hover:bg-secondary/20"
              }`}
            >
              <span className="material-symbols-outlined text-sm">
                {recording ? "stop" : audioReady ? "check_circle" : "mic"}
              </span>
              <span>
                {recording ? "Recording... tap to stop" : audioReady ? "Voice clip ready ✓" : "Record a short clip"}
              </span>
            </button>
          </div>

          {/* Submit */}
          <button
            type="submit"
            disabled={loading}
            className="w-full py-3.5 bg-primary text-on-primary rounded-full font-sans text-[14px] font-medium hover:bg-primary-container disabled:opacity-50 transition-all flex items-center justify-center gap-2 shadow-lg"
          >
            {loading ? (
              <>
                <div className="w-4 h-4 rounded-full border-2 border-on-primary border-t-transparent animate-spin" />
                <span>Putting it all together...</span>
              </>
            ) : (
              <span>See my insights</span>
            )}
          </button>

          {error && (
            <div className="p-4 rounded-lg bg-error-container text-on-error-container text-sm font-sans">
              {error}
            </div>
          )}
        </form>

        {/* Right: Results */}
        <div className="col-span-1 md:col-span-7 flex flex-col gap-4">
          {result && wellness ? (
            <>
              {/* Overall Wellness Card */}
              <div className={`glass-panel rounded-xl p-6 ${wellness.bg} border-2 ${wellness.border} flex flex-col gap-4`}>
                <div className="font-sans text-[13px] font-medium uppercase tracking-wider text-on-surface-variant">
                  Your overall wellness
                </div>
                <div className="flex items-center gap-4">
                  <span className="text-5xl">{wellness.emoji}</span>
                  <div>
                    <div className="font-sans text-[24px] font-semibold text-on-surface leading-tight">
                      {wellness.label}
                    </div>
                    <div className="font-sans text-[14px] text-on-surface-variant mt-1">
                      {translateUrgency(result.urgency_level)}
                    </div>
                  </div>
                </div>

                {/* Disagreement notice */}
                {result.low_confidence_flag && (
                  <div className="p-3 rounded-lg bg-amber-100/50 border border-amber-300/50 text-amber-800 text-[13px] font-sans flex items-start gap-2">
                    <span className="material-symbols-outlined text-sm mt-0.5">info</span>
                    <span>
                      Your words, voice, and daily patterns are telling us slightly different things.
                      That&apos;s normal — emotions are complex. We&apos;re showing you the best picture we can.
                    </span>
                  </div>
                )}
              </div>

              {/* Crisis Support (only when escalated) */}
              {result.escalate_to_human_reviewer && (
                <div className="glass-panel rounded-xl p-6 bg-rose-50 border border-rose-200 flex flex-col gap-3">
                  <div className="flex items-center gap-2 font-sans font-medium text-[15px] text-rose-800">
                    <span className="material-symbols-outlined text-rose-500">
                      favorite
                    </span>
                    <span>You don&apos;t have to face this alone</span>
                  </div>
                  <p className="font-sans text-[14px] text-rose-700 leading-relaxed">
                    If you&apos;re going through a difficult time, reaching out to someone
                    can make a real difference. Here are some people who are ready to listen:
                  </p>
                  <div className="space-y-2">
                    <HelplineCard name="iCall (India)" number="9152987821" />
                    <HelplineCard name="988 Lifeline (US/Canada)" number="988" />
                    <HelplineCard name="Samaritans (UK)" number="116 123" />
                  </div>
                </div>
              )}

              {/* Personalized Suggestions */}
              <div className="glass-panel rounded-xl p-6 bg-surface-container-lowest flex flex-col gap-3">
                <div className="font-sans text-[13px] font-medium uppercase tracking-wider text-on-surface-variant">
                  Things that might help right now
                </div>
                <div className="space-y-2">
                  {result.coping_recommendations.map((rec, i) => (
                    <div
                      key={i}
                      className="p-4 rounded-lg bg-surface border border-outline-variant/15 font-sans text-[14px] text-on-surface leading-relaxed flex items-start gap-3"
                    >
                      <span className="material-symbols-outlined text-primary text-base mt-0.5">
                        {i === 0 ? "self_improvement" : i === 1 ? "psychology" : i === 2 ? "directions_walk" : i === 3 ? "edit_note" : "support_agent"}
                      </span>
                      <span>{rec}</span>
                    </div>
                  ))}
                </div>
              </div>
            </>
          ) : (
            <div className="glass-panel rounded-xl p-8 bg-surface-container-lowest flex flex-col items-center justify-center text-center h-full min-h-[380px] gap-4">
              <span className="text-5xl">🔮</span>
              <div className="font-sans text-[20px] font-medium text-on-surface">
                See the bigger picture
              </div>
              <p className="font-sans text-[15px] text-on-surface-variant max-w-sm leading-relaxed">
                Share how you&apos;re feeling through text or voice, and we&apos;ll combine
                everything to give you a complete picture of your emotional wellbeing —
                along with personalized suggestions.
              </p>
            </div>
          )}
        </div>
      </div>
    </>
  );
}

function HelplineCard({ name, number }: { name: string; number: string }) {
  return (
    <a
      href={`tel:${number}`}
      className="flex items-center justify-between p-3 rounded-lg bg-white/60 border border-rose-200 hover:bg-white transition-colors"
    >
      <span className="font-sans text-[14px] font-medium text-rose-800">{name}</span>
      <span className="font-mono text-[14px] font-semibold text-rose-600">{number}</span>
    </a>
  );
}
