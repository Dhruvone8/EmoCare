"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { healthCheck } from "@/lib/api";
import type { HealthResponse } from "@/types/api";

function getGreeting(): string {
  const hour = new Date().getHours();
  if (hour < 12) return "Good morning";
  if (hour < 17) return "Good afternoon";
  return "Good evening";
}

export default function DashboardPage() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    healthCheck()
      .then(setHealth)
      .catch(() => setHealth(null))
      .finally(() => setLoading(false));
  }, []);

  const systemReady =
    health && Object.values(health.models_loaded).every(Boolean);

  return (
    <>
      {/* ── Welcome Section ───────────────────────────────────────── */}
      <section className="max-w-3xl">
        <h1 className="font-sans text-[32px] md:text-[48px] font-semibold text-on-surface tracking-tight leading-tight mb-[var(--spacing-stack-sm)]">
          {getGreeting()}. 👋
          <br />
          <span className="text-primary/70">
            How are you feeling today?
          </span>
        </h1>
        <p className="font-sans text-[18px] text-on-surface-variant max-w-2xl mt-4 leading-7">
          This is your safe space. Take a moment to check in with yourself —
          write, talk, or simply reflect.
        </p>
      </section>

      {/* ── Main Grid ─────────────────────────────────────────────── */}
      <div className="grid grid-cols-1 md:grid-cols-12 gap-[var(--spacing-gutter)]">
        {/* Left Column (7 cols) */}
        <div className="col-span-1 md:col-span-7 flex flex-col gap-[var(--spacing-gutter)]">
          {/* Wellness Pulse Card */}
          <div className="glass-panel rounded-xl p-8 glass-panel-hover group relative overflow-hidden h-full min-h-[280px] flex flex-col justify-between bg-surface-container-lowest border-outline-variant/20">
            {/* Subtle background glow */}
            <div className="absolute -top-24 -right-24 w-64 h-64 bg-tertiary-fixed/30 rounded-full blur-3xl opacity-50 group-hover:opacity-80 transition-opacity duration-700" />
            <div className="relative z-10">
              <div className="flex items-center justify-between mb-6">
                <h2 className="font-sans text-[22px] font-medium text-on-surface leading-8">
                  Your Wellness Pulse
                </h2>
                <span
                  className="material-symbols-outlined text-primary text-3xl"
                  style={{ fontVariationSettings: "'FILL' 1" }}
                >
                  favorite
                </span>
              </div>
              <div className="flex items-center gap-4 mb-4">
                <WellnessBadge status={loading ? "loading" : "good"} />
              </div>
              <p className="font-sans text-[16px] text-on-surface-variant mt-2 max-w-md leading-7">
                {loading
                  ? "Checking in on your signals..."
                  : "Your recent signals look stable. Keep doing what you're doing — and remember, it's okay to have off days too."}
              </p>
            </div>
          </div>

          {/* Daily Snapshot Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-[var(--spacing-gutter)]">
            <SnapshotCard
              icon="edit_note"
              label="Journal"
              value={loading ? "..." : "Feeling positive"}
              hint="Last entry was calm and reflective"
            />
            <SnapshotCard
              icon="mic"
              label="Voice"
              value={loading ? "..." : "Calm & steady"}
              hint="Your tone sounds relaxed"
            />
            <SnapshotCard
              icon="check_circle"
              label="Daily check-in"
              value={loading ? "..." : "Completed"}
              hint="Logged 2 hours ago"
            />
            <SnapshotCard
              icon="shield"
              label="EmoCare status"
              value={
                loading
                  ? "..."
                  : systemReady
                    ? "Watching over you"
                    : "Setting up..."
              }
              hint={
                systemReady
                  ? "All systems are active"
                  : "Some features loading"
              }
            />
          </div>
        </div>

        {/* Right Column (5 cols) */}
        <div className="col-span-1 md:col-span-5 flex flex-col gap-[var(--spacing-gutter)]">
          {/* What would you like to do? */}
          <div className="glass-panel rounded-xl p-6 flex flex-col gap-4 bg-surface-container-lowest">
            <h3 className="font-sans text-[20px] font-medium text-on-surface mb-1 leading-8">
              What would you like to do?
            </h3>
            <ActionCard
              href="/journal"
              icon="edit_note"
              iconBg="bg-primary-container/20"
              iconColor="text-primary"
              hoverBg="group-hover:bg-primary"
              hoverColor="group-hover:text-on-primary"
              hoverArrow="group-hover:text-primary"
              title="Write in your journal"
              subtitle="Express your thoughts freely"
            />
            <ActionCard
              href="/voice"
              icon="mic"
              iconBg="bg-secondary-container/30"
              iconColor="text-secondary"
              hoverBg="group-hover:bg-secondary"
              hoverColor="group-hover:text-on-secondary"
              hoverArrow="group-hover:text-secondary"
              title="Talk it out"
              subtitle="Share how you're feeling out loud"
            />
            <ActionCard
              href="/checkin"
              icon="mood"
              iconBg="bg-tertiary-fixed/50"
              iconColor="text-tertiary"
              hoverBg="group-hover:bg-tertiary"
              hoverColor="group-hover:text-on-tertiary"
              hoverArrow="group-hover:text-tertiary"
              title="Daily check-in"
              subtitle="A quick wellness snapshot"
            />
          </div>

          {/* Supportive Card */}
          <div className="glass-panel rounded-xl overflow-hidden group relative min-h-[200px] flex items-end">
            <div className="absolute inset-0 z-0">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                alt="Serene background"
                className="w-full h-full object-cover opacity-60 mix-blend-luminosity group-hover:scale-105 transition-transform duration-1000 ease-out"
                src="https://lh3.googleusercontent.com/aida-public/AB6AXuDNK5o4Oim2WxpuRgUwVPtHIfniJ2UoAwq0zLt1IfnwVI_lHshXTSgL3jhXMjFGMaQfV-a7kx93Yv3v5x4fteWiaPnerldgW1IhDCR5c0E6FfzsA-c-o008UIP4MPYKnYN6iy6xdFaZZiRgtAl37PID9ZEZpcvpwuTaXz2n43D7wNtlwiDUL9ZSSFZ6qLng80ufkA5DbXK-ue1LV3gWbY0rp-3iEYnJK6ew1ea3g-snM_nLywrEtnD9tA"
              />
              <div className="absolute inset-0 bg-gradient-to-t from-surface-container-highest/90 via-surface/60 to-transparent" />
            </div>
            <div className="relative z-10 p-6 w-full backdrop-blur-[2px]">
              <div className="font-sans text-[12px] font-medium text-primary tracking-wider uppercase mb-2 leading-4">
                Take a moment
              </div>
              <h3 className="font-sans text-[22px] font-medium text-on-surface mb-3 leading-snug">
                A small pause can help.
                <br />
                Try a 60-second breathing exercise.
              </h3>
              <button className="px-6 py-2 bg-primary text-on-primary rounded-full font-sans text-[13px] font-medium hover:bg-surface-tint transition-colors w-max flex items-center gap-2">
                <span>Begin</span>
                <span className="material-symbols-outlined text-sm">
                  play_arrow
                </span>
              </button>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}

/* ── Wellness Badge ────────────────────────────────────────────────── */
function WellnessBadge({ status }: { status: "good" | "mixed" | "tough" | "loading" }) {
  if (status === "loading") {
    return (
      <div className="flex items-center gap-3">
        <div className="w-4 h-4 rounded-full bg-outline animate-pulse" />
        <span className="font-sans text-[16px] text-on-surface-variant">Checking...</span>
      </div>
    );
  }

  const config = {
    good: { emoji: "💚", text: "You're doing well today", bg: "bg-emerald-500/10", border: "border-emerald-500/30" },
    mixed: { emoji: "💛", text: "A bit of a mixed day", bg: "bg-amber-500/10", border: "border-amber-500/30" },
    tough: { emoji: "🧡", text: "Today seems tough — we're here", bg: "bg-rose-500/10", border: "border-rose-500/30" },
  }[status];

  return (
    <div className={`flex items-center gap-3 px-5 py-2.5 rounded-full ${config.bg} border ${config.border}`}>
      <span className="text-2xl">{config.emoji}</span>
      <span className="font-sans text-[18px] font-medium text-on-surface">{config.text}</span>
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
    <div className="glass-panel rounded-lg p-5 flex flex-col gap-2">
      <div className="flex items-center gap-2 text-on-surface-variant mb-1">
        <span className="material-symbols-outlined text-sm">{icon}</span>
        <span className="font-sans text-[12px] font-medium uppercase tracking-wider text-xs">
          {label}
        </span>
      </div>
      <div className="font-sans text-[16px] font-medium text-on-surface leading-6">
        {value}
      </div>
      <div className="font-sans text-[13px] text-on-surface-variant leading-5">
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
}) {
  return (
    <Link
      href={href}
      className="group flex items-center justify-between p-4 rounded-lg bg-surface border border-outline-variant/20 hover:border-primary/50 hover:bg-surface-container-low transition-all duration-300"
    >
      <div className="flex items-center gap-4">
        <div
          className={`w-10 h-10 rounded-full ${iconBg} flex items-center justify-center ${iconColor} ${hoverBg} ${hoverColor} transition-colors`}
        >
          <span
            className="material-symbols-outlined"
            style={{ fontVariationSettings: "'FILL' 1" }}
          >
            {icon}
          </span>
        </div>
        <div>
          <div className="font-sans text-[16px] font-medium text-on-surface leading-6">
            {title}
          </div>
          <div className="font-sans text-[14px] text-on-surface-variant leading-5">
            {subtitle}
          </div>
        </div>
      </div>
      <span
        className={`material-symbols-outlined text-outline-variant ${hoverArrow} group-hover:translate-x-1 transition-all`}
      >
        arrow_forward
      </span>
    </Link>
  );
}
