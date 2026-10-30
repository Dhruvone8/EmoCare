"use client";

import React, { useId, useState } from "react";
import {
  getLocalDateKey,
  predictBehavioral,
  saveDailyCheckIn,
} from "@/lib/api";
import type {
  BehavioralResponse,
  DailyCheckIn,
  DailyCheckInFormData,
} from "@/types/api";

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

const ENERGY_OPTIONS = [
  { value: 1, emoji: "🪫", label: "Very low" },
  { value: 2, emoji: "😪", label: "Low" },
  { value: 3, emoji: "😐", label: "Okay" },
  { value: 4, emoji: "⚡", label: "Energized" },
  { value: 5, emoji: "🌟", label: "Very high" },
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

interface DailyCheckInFormProps {
  variant?: "page" | "modal";
  onSaved?: (checkIn: DailyCheckIn) => void;
  onResult?: (result: BehavioralResponse | null) => void;
}

export function DailyCheckInForm({
  variant = "page",
  onSaved,
  onResult,
}: DailyCheckInFormProps) {
  const idPrefix = useId();
  const [formData, setFormData] = useState<DailyCheckInFormData>(() => ({
    mood_rating: 3,
    stress_level: 3,
    sleep_quality: 3,
    energy_level: 3,
    notes: "",
    ...(variant === "page"
      ? {
          sleep_hours: 7,
          activity_level: 3,
          social_interaction: 3,
          exercise_minutes: 30,
        }
      : {}),
  }));
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const updateField = <K extends keyof DailyCheckInFormData>(
    field: K,
    value: DailyCheckInFormData[K]
  ) => {
    setFormData((current) => ({ ...current, [field]: value }));
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setLoading(true);
    setError(null);
    setNotice(null);
    onResult?.(null);

    try {
      const saved = await saveDailyCheckIn({
        ...formData,
        notes: formData.notes.trim(),
        local_date: getLocalDateKey(),
      });

      if (onResult) {
        try {
          onResult(await predictBehavioral(formData));
          setNotice("Your check-in is saved for today.");
        } catch {
          setNotice(
            "Your check-in is saved, but personalized insights are unavailable right now."
          );
        }
      }
      onSaved?.(saved);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Your check-in could not be saved. Please try again."
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <form
      onSubmit={handleSubmit}
      className={
        variant === "page"
          ? "col-span-1 md:col-span-7 flex flex-col gap-4"
          : "flex flex-col gap-4"
      }
    >
      <div
        className={
          variant === "page"
            ? "glass-panel rounded-xl p-6 bg-surface-container-lowest flex flex-col gap-6"
            : "flex flex-col gap-5"
        }
      >
        <EmojiSelector
          label="How's your mood?"
          options={MOOD_OPTIONS}
          value={formData.mood_rating}
          onChange={(value) => updateField("mood_rating", value)}
        />
        <EmojiSelector
          label="How stressed do you feel?"
          options={STRESS_OPTIONS}
          value={formData.stress_level}
          onChange={(value) => updateField("stress_level", value)}
        />
        <EmojiSelector
          label="How did you sleep last night?"
          options={SLEEP_QUALITY_OPTIONS}
          value={formData.sleep_quality}
          onChange={(value) => updateField("sleep_quality", value)}
        />
        <EmojiSelector
          label="How is your energy today?"
          options={ENERGY_OPTIONS}
          value={formData.energy_level}
          onChange={(value) => updateField("energy_level", value)}
        />

        {variant === "page" && (
          <>
            <div className="flex flex-col gap-2">
              <label
                htmlFor={`${idPrefix}-sleep-hours`}
                className="font-sans text-[15px] font-medium text-on-surface"
              >
                Hours of sleep
              </label>
              <div className="flex items-center gap-3">
                <input
                  id={`${idPrefix}-sleep-hours`}
                  type="range"
                  min="0"
                  max="14"
                  step="0.5"
                  value={formData.sleep_hours ?? 7}
                  onChange={(event) =>
                    updateField("sleep_hours", parseFloat(event.target.value))
                  }
                  className="flex-1 accent-primary h-2 rounded-lg cursor-pointer"
                />
                <span className="font-mono text-[15px] font-semibold text-primary w-16 text-right">
                  {formData.sleep_hours ?? 7} hrs
                </span>
              </div>
            </div>

            <EmojiSelector
              label="Social interaction today?"
              options={SOCIAL_OPTIONS}
              value={formData.social_interaction ?? 3}
              onChange={(value) => updateField("social_interaction", value)}
            />
            <EmojiSelector
              label="Physical activity?"
              options={ACTIVITY_OPTIONS}
              value={formData.activity_level ?? 3}
              onChange={(value) => updateField("activity_level", value)}
            />

            <div className="flex flex-col gap-2">
              <label
                htmlFor={`${idPrefix}-exercise-minutes`}
                className="font-sans text-[15px] font-medium text-on-surface"
              >
                Exercise today (minutes)
              </label>
              <div className="flex items-center gap-3">
                <input
                  id={`${idPrefix}-exercise-minutes`}
                  type="range"
                  min="0"
                  max="120"
                  step="5"
                  value={formData.exercise_minutes ?? 0}
                  onChange={(event) =>
                    updateField(
                      "exercise_minutes",
                      parseInt(event.target.value, 10)
                    )
                  }
                  className="flex-1 accent-primary h-2 rounded-lg cursor-pointer"
                />
                <span className="font-mono text-[15px] font-semibold text-primary w-16 text-right">
                  {formData.exercise_minutes ?? 0} min
                </span>
              </div>
            </div>
          </>
        )}

        <div className="flex flex-col gap-2">
          <label
            htmlFor={`${idPrefix}-notes`}
            className="font-sans text-[15px] font-medium text-on-surface"
          >
            Anything you want to note? <span className="font-normal text-on-surface-variant">(optional)</span>
          </label>
          <textarea
            id={`${idPrefix}-notes`}
            rows={3}
            maxLength={1000}
            value={formData.notes}
            onChange={(event) => updateField("notes", event.target.value)}
            placeholder="A few words about your day..."
            className="w-full resize-y rounded-xl border border-outline-variant/25 bg-surface px-3 py-2.5 font-sans text-sm text-on-surface placeholder:text-on-surface-variant/60 focus:outline-none focus:ring-2 focus:ring-primary/40"
          />
        </div>

        <button
          type="submit"
          disabled={loading}
          className="w-full py-3 bg-primary text-on-primary rounded-full font-sans text-[14px] font-medium hover:bg-primary-container disabled:opacity-50 transition-all flex items-center justify-center gap-2 mt-2"
        >
          {loading ? (
            <>
              <div className="w-4 h-4 rounded-full border-2 border-on-primary border-t-transparent animate-spin" />
              <span>Saving...</span>
            </>
          ) : (
            <span>Complete check-in</span>
          )}
        </button>
      </div>

      {error && (
        <div role="alert" className="p-4 rounded-lg bg-error-container text-on-error-container text-sm font-sans">
          {error}
        </div>
      )}
      {notice && (
        <div role="status" className="p-4 rounded-lg bg-primary/10 text-on-surface text-sm font-sans">
          {notice}
        </div>
      )}
    </form>
  );
}

function EmojiSelector({
  label,
  options,
  value,
  onChange,
}: {
  label: string;
  options: { value: number; emoji: string; label: string }[];
  value: number;
  onChange: (value: number) => void;
}) {
  return (
    <fieldset className="min-w-0">
      <legend className="font-sans text-[15px] font-medium text-on-surface mb-2">
        {label}
      </legend>
      <div className="grid grid-cols-5 gap-1.5 sm:gap-2">
        {options.map((option) => (
          <button
            key={option.value}
            type="button"
            aria-pressed={value === option.value}
            aria-label={`${label}: ${option.label}`}
            onClick={() => onChange(option.value)}
            className={`min-w-0 flex flex-col items-center gap-1 py-3 px-1 rounded-xl border-2 transition-all duration-200 ${
              value === option.value
                ? "border-primary bg-primary/5 shadow-sm sm:scale-105"
                : "border-outline-variant/20 bg-surface hover:border-outline-variant/50"
            }`}
          >
            <span className="text-xl sm:text-2xl">{option.emoji}</span>
            <span className="font-sans text-[10px] sm:text-[11px] text-on-surface-variant leading-tight text-center">
              {option.label}
            </span>
          </button>
        ))}
      </div>
    </fieldset>
  );
}
