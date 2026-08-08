"use client";

import { useState } from "react";
import { predictBehavioral } from "@/lib/api";
import type { BehavioralResponse, BehavioralRequest } from "@/types/api";

const MOOD_OPTIONS = [
  { value: 1, emoji: "😞", label: "Really low" },
  { value: 2, emoji: "😕", label: "Not great" },
  { value: 3, emoji: "😐", label: "Okay" },
  { value: 4, emoji: "🙂", label: "Pretty good" },
  { value: 5, emoji: "😊", label: "Great" },
];

const STRESS_OPTIONS = [
  { value: 1, emoji: "🧘", label: "Relaxed" },
  { value: 2, emoji: "😌", label: "Mild" },
  { value: 3, emoji: "😐", label: "Moderate" },
  { value: 4, emoji: "😰", label: "High" },
  { value: 5, emoji: "🤯", label: "Overwhelmed" },
];

const SLEEP_QUALITY_OPTIONS = [
  { value: 1, emoji: "😴", label: "Terrible" },
  { value: 2, emoji: "😪", label: "Poor" },
  { value: 3, emoji: "🛏️", label: "Okay" },
  { value: 4, emoji: "😌", label: "Good" },
  { value: 5, emoji: "✨", label: "Great" },
];

const SOCIAL_OPTIONS = [
  { value: 1, emoji: "🏠", label: "Alone all day" },
  { value: 2, emoji: "👤", label: "Minimal" },
  { value: 3, emoji: "💬", label: "Some" },
  { value: 4, emoji: "👥", label: "Good amount" },
  { value: 5, emoji: "🎉", label: "Very social" },
];

const ACTIVITY_OPTIONS = [
  { value: 1, emoji: "🛋️", label: "Sedentary" },
  { value: 2, emoji: "🚶", label: "Light" },
  { value: 3, emoji: "🏃", label: "Moderate" },
  { value: 4, emoji: "💪", label: "Active" },
  { value: 5, emoji: "🏋️", label: "Very active" },
];

function translateRisk(tier: string): { emoji: string; title: string; message: string; bg: string; border: string } {
  switch (tier) {
    case "High":
      return {
        emoji: "🧡",
        title: "Today seems tough",
        message: "Based on your answers, it looks like you're going through a challenging time. That's completely valid — here are some things that might help.",
        bg: "bg-rose-50",
        border: "border-rose-200",
      };
    case "Moderate":
      return {
        emoji: "💛",
        title: "A bit of a mixed day",
        message: "Some things seem okay, others less so. It's normal to have days like this. Small adjustments can make a difference.",
        bg: "bg-amber-50",
        border: "border-amber-200",
      };
    default:
      return {
        emoji: "💚",
        title: "You're doing well today",
        message: "Your lifestyle patterns look healthy. Keep up the good habits — consistency is what matters most.",
        bg: "bg-emerald-50",
        border: "border-emerald-200",
      };
  }
}

export default function CheckinPage() {
  const [formData, setFormData] = useState<BehavioralRequest>({
    sleep_hours: 7,
    sleep_quality: 3,
    activity_level: 3,
    social_interaction: 3,
    stress_level: 3,
    exercise_minutes: 30,
    mood_rating: 3,
  });

  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<BehavioralResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const res = await predictBehavioral(formData);
      setResult(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  const riskInfo = result ? translateRisk(result.predicted_risk_tier) : null;

  return (
    <>
      {/* ── Page Header ────────────────────────────────────────────── */}
      <section className="max-w-3xl">
        <h1 className="font-sans text-[32px] md:text-[44px] font-semibold text-on-surface tracking-tight leading-tight mb-3">
          How was your day? 🌤️
        </h1>
        <p className="font-sans text-[18px] text-on-surface-variant max-w-2xl leading-7">
          A quick check-in about your sleep, mood, and daily habits. It only
          takes a minute.
        </p>
      </section>

      {/* ── Layout ─────────────────────────────────────────────────── */}
      <div className="grid grid-cols-1 md:grid-cols-12 gap-[var(--spacing-gutter)]">
        {/* Left: Form */}
        <form
          onSubmit={handleSubmit}
          className="col-span-1 md:col-span-7 flex flex-col gap-4"
        >
          <div className="glass-panel rounded-xl p-6 bg-surface-container-lowest flex flex-col gap-6">
            {/* Mood */}
            <EmojiSelector
              label="How's your mood?"
              options={MOOD_OPTIONS}
              value={formData.mood_rating || 3}
              onChange={(val) => setFormData({ ...formData, mood_rating: val })}
            />

            {/* Stress */}
            <EmojiSelector
              label="How stressed do you feel?"
              options={STRESS_OPTIONS}
              value={formData.stress_level || 3}
              onChange={(val) => setFormData({ ...formData, stress_level: val })}
            />

            {/* Sleep Quality */}
            <EmojiSelector
              label="How did you sleep last night?"
              options={SLEEP_QUALITY_OPTIONS}
              value={formData.sleep_quality || 3}
              onChange={(val) => setFormData({ ...formData, sleep_quality: val })}
            />

            {/* Sleep Hours */}
            <div className="flex flex-col gap-2">
              <label className="font-sans text-[15px] font-medium text-on-surface">
                Hours of sleep
              </label>
              <div className="flex items-center gap-3">
                <input
                  type="range"
                  min="0"
                  max="14"
                  step="0.5"
                  value={formData.sleep_hours || 7}
                  onChange={(e) =>
                    setFormData({ ...formData, sleep_hours: parseFloat(e.target.value) })
                  }
                  className="flex-1 accent-primary h-2 rounded-lg cursor-pointer"
                />
                <span className="font-mono text-[15px] font-semibold text-primary w-16 text-right">
                  {formData.sleep_hours} hrs
                </span>
              </div>
            </div>

            {/* Social */}
            <EmojiSelector
              label="Social interaction today?"
              options={SOCIAL_OPTIONS}
              value={formData.social_interaction || 3}
              onChange={(val) => setFormData({ ...formData, social_interaction: val })}
            />

            {/* Activity */}
            <EmojiSelector
              label="Physical activity?"
              options={ACTIVITY_OPTIONS}
              value={formData.activity_level || 3}
              onChange={(val) => setFormData({ ...formData, activity_level: val })}
            />

            {/* Exercise Minutes */}
            <div className="flex flex-col gap-2">
              <label className="font-sans text-[15px] font-medium text-on-surface">
                Exercise today (minutes)
              </label>
              <div className="flex items-center gap-3">
                <input
                  type="range"
                  min="0"
                  max="120"
                  step="5"
                  value={formData.exercise_minutes || 0}
                  onChange={(e) =>
                    setFormData({ ...formData, exercise_minutes: parseInt(e.target.value, 10) })
                  }
                  className="flex-1 accent-primary h-2 rounded-lg cursor-pointer"
                />
                <span className="font-mono text-[15px] font-semibold text-primary w-16 text-right">
                  {formData.exercise_minutes} min
                </span>
              </div>
            </div>

            {/* Submit */}
            <button
              type="submit"
              disabled={loading}
              className="w-full py-3 bg-primary text-on-primary rounded-full font-sans text-[14px] font-medium hover:bg-primary-container disabled:opacity-50 transition-all flex items-center justify-center gap-2 mt-2"
            >
              {loading ? (
                <>
                  <div className="w-4 h-4 rounded-full border-2 border-on-primary border-t-transparent animate-spin" />
                  <span>Thinking...</span>
                </>
              ) : (
                <span>Complete check-in</span>
              )}
            </button>
          </div>

          {error && (
            <div className="p-4 rounded-lg bg-error-container text-on-error-container text-sm font-sans">
              {error}
            </div>
          )}
        </form>

        {/* Right: Results */}
        <div className="col-span-1 md:col-span-5 flex flex-col gap-4">
          {result && riskInfo ? (
            <>
              {/* Main Insight Card */}
              <div className={`glass-panel rounded-xl p-6 ${riskInfo.bg} border ${riskInfo.border} flex flex-col gap-4`}>
                <div className="flex items-center gap-3">
                  <span className="text-3xl">{riskInfo.emoji}</span>
                  <span className="font-sans text-[20px] font-medium text-on-surface">
                    {riskInfo.title}
                  </span>
                </div>
                <p className="font-sans text-[15px] text-on-surface-variant leading-relaxed">
                  {riskInfo.message}
                </p>
              </div>

              {/* Tips */}
              <div className="glass-panel rounded-xl p-6 bg-surface-container-lowest flex flex-col gap-3">
                <div className="font-sans text-[13px] font-medium uppercase tracking-wider text-on-surface-variant">
                  Things that might help
                </div>
                {result.predicted_risk_tier === "High" ? (
                  <>
                    <TipCard text="Try going to bed 30 minutes earlier tonight." icon="bedtime" />
                    <TipCard text="A 10-minute walk outside can shift your mood." icon="directions_walk" />
                    <TipCard text="Reach out to someone you trust — even a short text helps." icon="chat" />
                  </>
                ) : result.predicted_risk_tier === "Moderate" ? (
                  <>
                    <TipCard text="Try a 5-minute breathing exercise before bed." icon="self_improvement" />
                    <TipCard text="Limit screen time in the last hour before sleep." icon="phone_disabled" />
                  </>
                ) : (
                  <>
                    <TipCard text="Keep up your good sleep routine!" icon="thumb_up" />
                    <TipCard text="Stay connected with the people who matter to you." icon="favorite" />
                  </>
                )}
              </div>
            </>
          ) : (
            <div className="glass-panel rounded-xl p-8 bg-surface-container-lowest flex flex-col items-center justify-center text-center h-full min-h-[300px] gap-3">
              <span className="text-4xl">🌤️</span>
              <div className="font-sans text-[18px] font-medium text-on-surface">
                Your daily snapshot
              </div>
              <p className="font-sans text-[14px] text-on-surface-variant max-w-xs leading-relaxed">
                Answer the questions on the left and we&apos;ll share personalized insights about your day.
              </p>
            </div>
          )}
        </div>
      </div>
    </>
  );
}

/* ── Emoji Selector ────────────────────────────────────────────────── */
function EmojiSelector({
  label,
  options,
  value,
  onChange,
}: {
  label: string;
  options: { value: number; emoji: string; label: string }[];
  value: number;
  onChange: (val: number) => void;
}) {
  return (
    <div className="flex flex-col gap-2">
      <label className="font-sans text-[15px] font-medium text-on-surface">
        {label}
      </label>
      <div className="flex gap-2">
        {options.map((opt) => (
          <button
            key={opt.value}
            type="button"
            onClick={() => onChange(opt.value)}
            className={`flex-1 flex flex-col items-center gap-1 py-3 px-1 rounded-xl border-2 transition-all duration-200 ${
              value === opt.value
                ? "border-primary bg-primary/5 shadow-sm scale-105"
                : "border-outline-variant/20 bg-surface hover:border-outline-variant/50"
            }`}
          >
            <span className="text-2xl">{opt.emoji}</span>
            <span className="font-sans text-[11px] text-on-surface-variant leading-tight text-center">
              {opt.label}
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}

/* ── Tip Card ──────────────────────────────────────────────────────── */
function TipCard({ text, icon }: { text: string; icon: string }) {
  return (
    <div className="p-3 rounded-lg bg-surface border border-outline-variant/15 flex items-start gap-3">
      <span className="material-symbols-outlined text-primary text-base mt-0.5">
        {icon}
      </span>
      <span className="font-sans text-[14px] text-on-surface leading-relaxed">
        {text}
      </span>
    </div>
  );
}
