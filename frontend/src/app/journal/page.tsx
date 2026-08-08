"use client";

import { useState } from "react";
import { predictText } from "@/lib/api";
import type { TextResponse } from "@/types/api";

const PROMPTS = [
  "What's one thing that made you smile today?",
  "How did your body feel when you woke up this morning?",
  "What's been on your mind lately?",
  "Describe a moment from today that stands out.",
  "If you could change one thing about today, what would it be?",
];

function getRandomPrompt() {
  return PROMPTS[Math.floor(Math.random() * PROMPTS.length)];
}

function translateMood(tier: string): { emoji: string; label: string; color: string } {
  switch (tier) {
    case "High":
      return { emoji: "🧡", label: "It sounds like you're going through a tough time", color: "text-rose-600" };
    case "Moderate":
      return { emoji: "💛", label: "There's some heaviness in your words — that's okay", color: "text-amber-600" };
    default:
      return { emoji: "💚", label: "Your writing feels calm and grounded", color: "text-emerald-600" };
  }
}

function translateLinguisticInsight(markers: TextResponse["linguistic_markers"]): string[] {
  const insights: string[] = [];

  if (markers.first_person_rate > 0.1) {
    insights.push("You seem to be reflecting inward today — self-awareness is a strength.");
  }
  if (markers.absolutist_rate > 0.05) {
    insights.push("You're using some strong, absolute words. It might help to look at things from different angles.");
  }
  if (markers.negation_rate > 0.08) {
    insights.push("There's some negativity coming through. Remember, feelings aren't permanent — they pass.");
  }

  if (insights.length === 0) {
    insights.push("Your language feels balanced and thoughtful. Keep expressing yourself like this.");
  }

  return insights;
}

export default function JournalPage() {
  const [text, setText] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<TextResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [prompt] = useState(getRandomPrompt);

  const wordCount = text.trim() ? text.trim().split(/\s+/).length : 0;

  const handleAnalyze = async () => {
    if (!text.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const res = await predictText(text);
      setResult(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  const mood = result ? translateMood(result.predicted_risk_tier) : null;
  const insights = result ? translateLinguisticInsight(result.linguistic_markers) : [];

  return (
    <>
      {/* ── Page Header ────────────────────────────────────────────── */}
      <section className="max-w-3xl">
        <h1 className="font-sans text-[32px] md:text-[44px] font-semibold text-on-surface tracking-tight leading-tight mb-3">
          Write how you feel ✍️
        </h1>
        <p className="font-sans text-[18px] text-on-surface-variant max-w-2xl leading-7">
          There are no rules here. Write whatever comes to mind — a sentence, a
          paragraph, or just a few words. We&apos;ll gently reflect back what we
          notice.
        </p>
      </section>

      {/* ── Journal Layout ─────────────────────────────────────────── */}
      <div className="grid grid-cols-1 md:grid-cols-12 gap-[var(--spacing-gutter)]">
        {/* Left: Writing Space */}
        <div className="col-span-1 md:col-span-7 flex flex-col gap-4">
          <div className="glass-panel rounded-xl p-6 bg-surface-container-lowest flex flex-col gap-4 min-h-[380px]">
            {/* Journal prompt */}
            <div className="flex items-center gap-2 text-primary/60 text-sm font-sans">
              <span className="material-symbols-outlined text-base">lightbulb</span>
              <span className="italic">{prompt}</span>
            </div>

            <textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder="Start writing here..."
              className="w-full h-64 bg-transparent resize-none border-none outline-none font-sans text-[18px] text-on-surface placeholder:text-outline/40 leading-8"
            />

            <div className="flex items-center justify-between pt-4 border-t border-outline-variant/20">
              <div className="font-sans text-[13px] text-on-surface-variant">
                {wordCount} words
              </div>
              <button
                onClick={handleAnalyze}
                disabled={loading || !text.trim()}
                className="px-6 py-2.5 bg-primary text-on-primary rounded-full font-sans text-[13px] font-medium hover:bg-primary-container disabled:opacity-50 transition-all flex items-center gap-2"
              >
                {loading ? (
                  <>
                    <div className="w-4 h-4 rounded-full border-2 border-on-primary border-t-transparent animate-spin" />
                    <span>Reflecting...</span>
                  </>
                ) : (
                  <>
                    <span>Save & Reflect</span>
                    <span className="material-symbols-outlined text-sm">
                      auto_awesome
                    </span>
                  </>
                )}
              </button>
            </div>
          </div>
          {error && (
            <div className="p-4 rounded-lg bg-error-container text-on-error-container text-sm font-sans">
              {error}
            </div>
          )}
        </div>

        {/* Right: Insights */}
        <div className="col-span-1 md:col-span-5 flex flex-col gap-4">
          {result && mood ? (
            <>
              {/* Mood Card */}
              <div className="glass-panel rounded-xl p-6 bg-surface-container-lowest flex flex-col gap-4">
                <div className="font-sans text-[13px] font-medium uppercase tracking-wider text-on-surface-variant">
                  How your writing feels
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-3xl">{mood.emoji}</span>
                  <span className={`font-sans text-[18px] font-medium ${mood.color} leading-6`}>
                    {mood.label}
                  </span>
                </div>
              </div>

              {/* Gentle Insights */}
              <div className="glass-panel rounded-xl p-6 bg-surface-container-lowest flex flex-col gap-3">
                <div className="font-sans text-[13px] font-medium uppercase tracking-wider text-on-surface-variant">
                  What we noticed
                </div>
                {insights.map((insight, i) => (
                  <div
                    key={i}
                    className="p-4 rounded-lg bg-surface border border-outline-variant/15 text-[15px] font-sans text-on-surface leading-relaxed flex items-start gap-3"
                  >
                    <span className="material-symbols-outlined text-primary text-base mt-0.5">
                      spa
                    </span>
                    <span>{insight}</span>
                  </div>
                ))}
              </div>

              {/* Supportive suggestion */}
              {result.predicted_risk_tier === "High" && (
                <div className="glass-panel rounded-xl p-5 bg-rose-50 border border-rose-200 text-rose-900 flex flex-col gap-2">
                  <div className="flex items-center gap-2 font-sans font-medium text-sm">
                    <span className="material-symbols-outlined text-rose-500 text-base">
                      favorite
                    </span>
                    <span>You don&apos;t have to carry this alone</span>
                  </div>
                  <p className="text-xs leading-relaxed text-rose-800">
                    If you&apos;re feeling overwhelmed, talking to someone can help. Reach out to a trusted friend, family member, or a helpline.
                  </p>
                </div>
              )}
            </>
          ) : (
            <div className="glass-panel rounded-xl p-8 bg-surface-container-lowest flex flex-col items-center justify-center text-center h-full min-h-[300px] gap-3">
              <span className="material-symbols-outlined text-4xl text-outline/40">
                auto_awesome
              </span>
              <div className="font-sans text-[18px] font-medium text-on-surface">
                Your reflections will appear here
              </div>
              <p className="font-sans text-[14px] text-on-surface-variant max-w-xs leading-relaxed">
                Start writing on the left — when you&apos;re ready, click &quot;Save & Reflect&quot; and we&apos;ll share what we noticed.
              </p>
            </div>
          )}
        </div>
      </div>
    </>
  );
}
