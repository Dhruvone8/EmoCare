"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { healthCheck } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { BreathingModal } from "@/components/BreathingModal";
import type { HealthResponse } from "@/types/api";

interface BaselineAssessment {
  test_type: string;
  total_score: number;
  max_score: number;
  severity_band: string;
  risk_tier: "Low" | "Moderate" | "High";
  date: string;
}

function getGreeting(): string {
  const hour = new Date().getHours();
  if (hour < 12) return "Good morning";
  if (hour < 17) return "Good afternoon";
  return "Good evening";
}

export default function DashboardPage() {
  const { user } = useAuth();
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [baseline] = useState<BaselineAssessment | null>(() => {
    if (typeof window !== "undefined") {
      const stored = localStorage.getItem("emocare_last_assessment");
      if (stored) {
        try {
          return JSON.parse(stored);
        } catch {
          return null;
        }
      }
    }
    return null;
  });
  const [isBreathingModalOpen, setIsBreathingModalOpen] = useState(false);

  useEffect(() => {
    healthCheck()
      .then(setHealth)
      .catch(() => setHealth(null))
      .finally(() => setLoading(false));
  }, []);

  const systemReady =
    health && Object.values(health.models_loaded).every(Boolean);

  const userName =
    user?.user_metadata?.full_name?.split(" ")[0] ||
    user?.email?.split("@")[0] ||
    "Friend";

  return (
    <>
      {/* ── Welcome Section ───────────────────────────────────────── */}
      <section className="max-w-4xl space-y-3">
        <h1 className="font-sans text-3xl sm:text-4xl md:text-5xl font-bold text-on-surface tracking-tight leading-tight">
          <span>{getGreeting()}, {userName}.</span>{" "}
          <span className="inline-block transition-transform duration-300 hover:rotate-12 cursor-default select-none origin-bottom-right">
            👋
          </span>
          <br />
          <span className="bg-gradient-to-r from-primary via-primary-container to-secondary bg-clip-text text-transparent">
            How are you feeling today?
          </span>
        </h1>
        <p className="font-sans text-base sm:text-lg text-on-surface-variant max-w-2xl leading-relaxed">
          This is your safe space. Take a moment to check in with yourself —
          write, talk, or calibrate your emotional baseline.
        </p>
      </section>

      {/* ── Onboarding Banner (If no baseline test completed yet) ── */}
      {!baseline && (
        <section className="glass-panel rounded-2xl sm:rounded-3xl p-6 sm:p-8 bg-gradient-to-r from-primary/10 via-surface-bright/70 to-secondary-container/20 border border-primary/25 shadow-sanctuary hover:shadow-sanctuary-hover transition-all duration-300 relative overflow-hidden flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
          <div className="flex items-start gap-4 max-w-xl">
            <div className="p-3 sm:p-3.5 rounded-2xl bg-primary text-on-primary shadow-md shrink-0 flex items-center justify-center">
              <span className="material-symbols-outlined text-2xl sm:text-3xl">assignment_turned_in</span>
            </div>
            <div>
              <div className="inline-flex items-center gap-1.5 px-3 py-0.5 rounded-full bg-primary/15 text-primary text-xs font-semibold uppercase tracking-wider mb-2">
                <span>Step 1 • Onboarding</span>
              </div>
              <h2 className="text-xl sm:text-2xl font-bold text-on-surface tracking-tight">
                Calibrate Your Emotional Baseline
              </h2>
              <p className="text-sm text-on-surface-variant mt-1.5 leading-relaxed">
                Take the quick 2-minute clinical screening (PHQ-9 / GAD-7) so EmoCare can personalize its insights and support for your journey.
              </p>
            </div>
          </div>

          <Link
            href="/assessment"
            className="w-full md:w-auto px-6 sm:px-8 py-3.5 rounded-full bg-primary hover:bg-primary/90 text-on-primary font-semibold text-sm transition-all duration-200 shadow-md hover:shadow-lg hover:-translate-y-0.5 active:translate-y-0 active:scale-95 flex items-center justify-center gap-2 shrink-0 cursor-pointer"
          >
            <span>Start Self-Assessment</span>
            <span className="material-symbols-outlined text-base">arrow_forward</span>
          </Link>
        </section>
      )}

      {/* ── Main Grid ─────────────────────────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 sm:gap-8">
        {/* Left Column (7 cols on desktop) */}
        <div className="col-span-1 lg:col-span-7 flex flex-col gap-6 sm:gap-8">
          {/* Wellness Pulse Card */}
          <div className="glass-panel rounded-2xl p-6 sm:p-8 glass-panel-hover group relative overflow-hidden flex flex-col justify-between bg-surface-container-lowest border border-outline-variant/20 min-h-[290px]">
            {/* Subtle background glow */}
            <div className="absolute -top-24 -right-24 w-64 h-64 bg-primary-fixed-dim/30 rounded-full blur-3xl opacity-40 group-hover:opacity-70 transition-opacity duration-700 pointer-events-none" />
            
            <div className="relative z-10">
              <div className="flex items-center justify-between mb-5">
                <h2 className="font-sans text-xl sm:text-[22px] font-semibold text-on-surface leading-snug">
                  Your Wellness Pulse
                </h2>
                <div className="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center text-primary group-hover:scale-110 transition-transform duration-300">
                  <span
                    className="material-symbols-outlined text-2xl"
                    style={{ fontVariationSettings: "'FILL' 1" }}
                  >
                    favorite
                  </span>
                </div>
              </div>
              <div className="flex items-center gap-4 mb-4">
                <WellnessBadge
                  status={
                    loading
                      ? "loading"
                      : baseline
                      ? baseline.risk_tier === "Low"
                        ? "good"
                        : baseline.risk_tier === "Moderate"
                        ? "mixed"
                        : "tough"
                      : "good"
                  }
                />
              </div>
              <p className="font-sans text-sm sm:text-base text-on-surface-variant mt-2 max-w-lg leading-relaxed">
                {baseline ? (
                  <>
                    Baseline: <strong>{baseline.test_type.toUpperCase()}</strong> score of{" "}
                    <strong>
                      {baseline.total_score}/{baseline.max_score}
                    </strong>{" "}
                    ({baseline.severity_band}). Keep checking in to observe trends over time.
                  </>
                ) : (
                  "Take your initial self-assessment check-in to calibrate your real-time wellness pulse and track emotional trends."
                )}
              </p>
            </div>

            {baseline && (
              <div className="relative z-10 pt-4 mt-6 border-t border-outline-variant/15 flex justify-between items-center text-xs text-on-surface-variant">
                <span>Last assessed: {new Date(baseline.date).toLocaleDateString()}</span>
                <Link href="/assessment" className="text-primary font-semibold hover:underline flex items-center gap-1 transition-colors">
                  <span>Retake test</span>
                  <span className="material-symbols-outlined text-xs">refresh</span>
                </Link>
              </div>
            )}
          </div>

          {/* Daily Snapshot Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 sm:gap-6">
            <SnapshotCard
              icon="psychology"
              label="Baseline Screener"
              value={baseline ? `${baseline.risk_tier} Risk (${baseline.severity_band})` : "Not taken yet"}
              hint={baseline ? `${baseline.test_type.toUpperCase()} Score: ${baseline.total_score}/${baseline.max_score}` : "Take 2-min onboarding check-in"}
            />
            <SnapshotCard
              icon="edit_note"
              label="Journal"
              value={loading ? "..." : "Reflective space"}
              hint="Express your thoughts freely"
            />
            <SnapshotCard
              icon="mic"
              label="Voice"
              value={loading ? "..." : "Speech Emotion"}
              hint="Analyze tone and prosody"
            />
            <SnapshotCard
              icon="shield"
              label="EmoCare AI Status"
              value={
                loading
                  ? "..."
                  : systemReady
                    ? "Active & Ready"
                    : "Calibrating..."
              }
              hint={
                systemReady
                  ? "Multimodal engine connected"
                  : "Connecting backend"
              }
            />
          </div>
        </div>

        {/* Right Column (5 cols on desktop) */}
        <div className="col-span-1 lg:col-span-5 flex flex-col gap-6 sm:gap-8">
          {/* What would you like to do? */}
          <div className="glass-panel rounded-2xl p-5 sm:p-6 flex flex-col gap-3.5 bg-surface-container-lowest border border-outline-variant/20 shadow-sanctuary">
            <h3 className="font-sans text-lg sm:text-xl font-semibold text-on-surface mb-1">
              What would you like to do?
            </h3>
            <ActionCard
              href="/assessment"
              icon="assignment"
              iconBg="bg-primary/10"
              iconColor="text-primary"
              hoverBg="group-hover:bg-primary"
              hoverColor="group-hover:text-white"
              hoverArrow="group-hover:text-primary"
              title="Self-Assessment (PHQ-9 / GAD-7)"
              subtitle="Calibrate baseline depression/anxiety"
            />
            <ActionCard
              href="/journal"
              icon="edit_note"
              iconBg="bg-secondary/10"
              iconColor="text-secondary"
              hoverBg="group-hover:bg-secondary"
              hoverColor="group-hover:text-white"
              hoverArrow="group-hover:text-secondary"
              title="Write in your journal"
              subtitle="Express your thoughts freely"
            />
            <ActionCard
              href="/voice"
              icon="mic"
              iconBg="bg-tertiary-container/30"
              iconColor="text-tertiary"
              hoverBg="group-hover:bg-tertiary"
              hoverColor="group-hover:text-white"
              hoverArrow="group-hover:text-tertiary"
              title="Talk it out"
              subtitle="Share how you're feeling out loud"
            />
            <ActionCard
              href="/therapy/chat"
              icon="forum"
              iconBg="bg-primary/10"
              iconColor="text-primary"
              hoverBg="group-hover:bg-primary"
              hoverColor="group-hover:text-white"
              hoverArrow="group-hover:text-primary"
              title="Chat Therapy"
              subtitle="Guided conversation with CBT tools"
              isNew
            />
            <ActionCard
              href="/therapy/voice"
              icon="headset_mic"
              iconBg="bg-secondary/15"
              iconColor="text-secondary"
              hoverBg="group-hover:bg-secondary"
              hoverColor="group-hover:text-white"
              hoverArrow="group-hover:text-secondary"
              title="Voice Therapy"
              subtitle="Speak & listen — audio sanctuary"
              isNew
            />
            <ActionCard
              href="/checkin"
              icon="mood"
              iconBg="bg-surface-variant/70"
              iconColor="text-on-surface-variant"
              hoverBg="group-hover:bg-primary"
              hoverColor="group-hover:text-white"
              hoverArrow="group-hover:text-primary"
              title="Daily habits check-in"
              subtitle="Sleep, mood, and activity snapshot"
            />
          </div>

          {/* Supportive Card */}
          <div className="glass-panel rounded-2xl overflow-hidden group relative min-h-[220px] flex items-end shadow-sanctuary border border-outline-variant/20">
            <div className="absolute inset-0 z-0">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                alt="Serene background"
                className="w-full h-full object-cover opacity-50 mix-blend-luminosity group-hover:scale-105 transition-transform duration-1000 ease-out"
                src="https://lh3.googleusercontent.com/aida-public/AB6AXuDNK5o4Oim2WxpuRgUwVPtHIfniJ2UoAwq0zLt1IfnwVI_lHshXTSgL3jhXMjFGMaQfV-a7kx93Yv3v5x4fteWiaPnerldgW1IhDCR5c0E6FfzsA-c-o008UIP4MPYKnYN6iy6xdFaZZiRgtAl37PID9ZEZpcvpwuTaXz2n43D7wNtlwiDUL9ZSSFZ6qLng80ufkA5DbXK-ue1LV3gWbY0rp-3iEYnJK6ew1ea3g-snM_nLywrEtnD9tA"
              />
              <div className="absolute inset-0 bg-gradient-to-t from-surface-container-highest/95 via-surface/75 to-transparent" />
            </div>
            <div className="relative z-10 p-6 w-full backdrop-blur-[2px]">
              <div className="font-sans text-[11px] font-bold text-primary tracking-wider uppercase mb-1.5">
                Take a moment
              </div>
              <h3 className="font-sans text-xl font-bold text-on-surface mb-3 leading-snug">
                A small pause can help.
                <br />
                Try a 60-second breathing exercise.
              </h3>
              <button
                onClick={() => setIsBreathingModalOpen(true)}
                className="px-5 py-2 bg-primary text-on-primary rounded-full font-sans text-xs font-semibold hover:bg-primary/90 transition-all duration-200 shadow-xs hover:shadow-md hover:-translate-y-0.5 active:scale-95 w-max flex items-center gap-2 cursor-pointer"
              >
                <span>Begin</span>
                <span className="material-symbols-outlined text-sm">
                  play_arrow
                </span>
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* ── Guided Breathing Yoga Modal ─────────────────────────────── */}
      <BreathingModal
        isOpen={isBreathingModalOpen}
        onClose={() => setIsBreathingModalOpen(false)}
      />
    </>
  );
}

/* ── Wellness Badge ────────────────────────────────────────────────── */
function WellnessBadge({ status }: { status: "good" | "mixed" | "tough" | "loading" }) {
  if (status === "loading") {
    return (
      <div className="flex items-center gap-3">
        <div className="w-4 h-4 rounded-full bg-outline animate-pulse" />
        <span className="font-sans text-sm text-on-surface-variant">Checking...</span>
      </div>
    );
  }

  const config = {
    good: { emoji: "💚", text: "You're doing well today", bg: "bg-emerald-500/10", border: "border-emerald-500/30" },
    mixed: { emoji: "💛", text: "A bit of a mixed day", bg: "bg-amber-500/10", border: "border-amber-500/30" },
    tough: { emoji: "🧡", text: "Today seems tough — we're here", bg: "bg-rose-500/10", border: "border-rose-500/30" },
  }[status];

  return (
    <div className={`flex items-center gap-2.5 px-4 py-2 rounded-full ${config.bg} border ${config.border} transition-all duration-300 shadow-xs`}>
      <span className="text-xl sm:text-2xl">{config.emoji}</span>
      <span className="font-sans text-sm sm:text-base font-semibold text-on-surface">{config.text}</span>
    </div>
  );
}

/* ── Snapshot Card ──────────────────────────────────────────────────── */
function SnapshotCard({
  icon,
  label,
  value,
  hint,
}: {
  icon: string;
  label: string;
  value: string;
  hint: string;
}) {
  return (
    <div className="glass-panel rounded-xl p-5 flex flex-col gap-2 bg-surface-container-lowest border border-outline-variant/20 hover:border-primary/30 hover:shadow-sanctuary-hover hover:-translate-y-0.5 transition-all duration-300 group">
      <div className="flex items-center gap-2 text-on-surface-variant">
        <div className="w-7 h-7 rounded-lg bg-surface-variant/40 group-hover:bg-primary/10 group-hover:text-primary transition-colors flex items-center justify-center">
          <span className="material-symbols-outlined text-base">{icon}</span>
        </div>
        <span className="font-sans text-[11px] font-bold uppercase tracking-wider text-on-surface-variant/80">
          {label}
        </span>
      </div>
      <div className="font-sans text-base font-semibold text-on-surface mt-1">
        {value}
      </div>
      <div className="font-sans text-xs text-on-surface-variant/85 leading-normal">
        {hint}
      </div>
    </div>
  );
}

/* ── Action Card ───────────────────────────────────────────────────── */
function ActionCard({
  href,
  icon,
  iconBg,
  iconColor,
  hoverBg,
  hoverColor,
  hoverArrow,
  title,
  subtitle,
  isNew,
}: {
  href: string;
  icon: string;
  iconBg: string;
  iconColor: string;
  hoverBg: string;
  hoverColor: string;
  hoverArrow: string;
  title: string;
  subtitle: string;
  isNew?: boolean;
}) {
  return (
    <Link
      href={href}
      className="group flex items-center justify-between p-3.5 sm:p-4 rounded-xl bg-surface border border-outline-variant/20 hover:border-primary/35 hover:bg-surface-container-low/60 hover:shadow-xs hover:-translate-y-0.5 transition-all duration-200 relative cursor-pointer"
    >
      <div className="flex items-center gap-3.5">
        <div
          className={`w-10 h-10 rounded-xl ${iconBg} flex items-center justify-center ${iconColor} ${hoverBg} ${hoverColor} group-hover:scale-105 transition-all duration-200 shrink-0`}
        >
          <span
            className="material-symbols-outlined text-xl"
            style={{ fontVariationSettings: "'FILL' 1" }}
          >
            {icon}
          </span>
        </div>
        <div>
          <div className="font-sans text-sm sm:text-base font-semibold text-on-surface flex items-center gap-2 group-hover:text-primary transition-colors duration-200">
            {title}
            {isNew && (
              <span className="text-[10px] font-bold uppercase tracking-wider text-primary bg-primary/15 px-2 py-0.5 rounded-full">
                New
              </span>
            )}
          </div>
          <div className="font-sans text-xs sm:text-sm text-on-surface-variant">
            {subtitle}
          </div>
        </div>
      </div>
      <span
        className={`material-symbols-outlined text-outline-variant ${hoverArrow} group-hover:translate-x-1 group-hover:text-primary transition-all duration-200 shrink-0 ml-2`}
      >
        arrow_forward
      </span>
    </Link>
  );
}
