"use client";

import { useState } from "react";
import { DailyCheckInForm } from "@/components/DailyCheckInForm";
import type { BehavioralResponse } from "@/types/api";

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
  const [result, setResult] = useState<BehavioralResponse | null>(null);
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
        <DailyCheckInForm variant="page" onResult={setResult} />

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
