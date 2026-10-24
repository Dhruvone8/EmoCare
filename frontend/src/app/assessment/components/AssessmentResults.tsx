"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import type { AssessmentResponse, AssessmentHistoryItem } from "@/types/api";
import { getAssessmentHistory } from "@/lib/api";

interface AssessmentResultsProps {
  result: AssessmentResponse;
  onRetake: (testType: "phq9" | "gad7") => void;
  openAuthModal: (mode: "login" | "signup") => void;
  isGuest: boolean;
}

export function AssessmentResults({
  result,
  onRetake,
  openAuthModal,
  isGuest,
}: AssessmentResultsProps) {
  const [history, setHistory] = useState<AssessmentHistoryItem[]>([]);
  const [loadingHistory, setLoadingHistory] = useState(
    Boolean(result.user_id && !result.user_id.startsWith("guest_"))
  );
  const [activeTab, setActiveTab] = useState<"summary" | "symptoms" | "context" | "progress">("summary");

  // Load history if user_id is provided
  useEffect(() => {
    let isMounted = true;
    if (result.user_id && !result.user_id.startsWith("guest_")) {
      getAssessmentHistory(result.user_id, 10)
        .then((res) => {
          if (isMounted) {
            setHistory(res.history || []);
            setLoadingHistory(false);
          }
        })
        .catch((err) => {
          console.warn("Could not load assessment history:", err);
          if (isMounted) {
            setLoadingHistory(false);
          }
        });
    }
    return () => {
      isMounted = false;
    };
  }, [result.user_id]);

  // Compute previous score comparison
  const previousSameTest = history.find(
    (h) => h.id !== result.id && h.test_type.toLowerCase() === result.test_type.toLowerCase()
  );

  const scoreDiff = previousSameTest ? result.total_score - previousSameTest.total_score : null;

  const isPhq = result.test_type.toLowerCase().startsWith("phq");
  const otherTestType: "phq9" | "gad7" = isPhq ? "gad7" : "phq9";

  return (
    <div className="glass-panel rounded-3xl p-6 sm:p-8 md:p-10 bg-surface/85 border border-outline-variant/30 backdrop-blur-md shadow-2xl flex flex-col gap-8 animate-in fade-in zoom-in-95 duration-200">
      {/* ── Top Header ────────────────────────────────────────── */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 pb-6 border-b border-outline-variant/20">
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 rounded-2xl bg-primary/10 text-primary flex items-center justify-center text-2xl shrink-0">
            📊
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-xs font-semibold uppercase tracking-wider text-primary">
                Screening Report
              </span>
              <span className="text-xs text-on-surface-variant">•</span>
              <span className="text-xs text-on-surface-variant">
                {new Date(result.timestamp).toLocaleDateString(undefined, {
                  month: "short",
                  day: "numeric",
                  year: "numeric",
                })}
              </span>
            </div>
            <h1 className="text-2xl sm:text-3xl font-bold text-on-surface tracking-tight">
              {result.test_display_name}
            </h1>
          </div>
        </div>

        <div className="flex items-center gap-2 self-stretch sm:self-auto justify-end">
          <button
            type="button"
            onClick={() => onRetake(otherTestType)}
            className="px-4 py-2 rounded-full border border-primary/30 text-primary hover:bg-primary/10 text-xs font-medium transition-colors cursor-pointer"
          >
            Take {isPhq ? "GAD-7" : "PHQ-9"}
          </button>
        </div>
      </div>

      {/* ── Safety Alert Banner (if item 9 endorsed or crisis flagged) ── */}
      {result.safety_alert && (
        <div className="p-5 sm:p-6 rounded-2xl bg-rose-500/15 border border-rose-500/35 flex flex-col gap-3 text-on-surface shadow-md">
          <div className="flex items-start gap-3">
            <span className="material-symbols-outlined text-rose-600 dark:text-rose-400 text-2xl shrink-0 mt-0.5" aria-hidden="true">
              emergency
            </span>
            <div>
              <h3 className="text-base font-bold text-rose-700 dark:text-rose-300">
                Support & Safety Pathway Active
              </h3>
              <p className="text-xs sm:text-sm text-on-surface-variant mt-1 leading-relaxed">
                You reported thoughts of hurting yourself or feeling you would be better off dead. Regardless of your total screening score, your life and safety are our foremost priority.
              </p>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-2">
            <div className="p-3 rounded-xl bg-surface/80 border border-rose-500/20 text-xs flex flex-col">
              <strong className="text-rose-600 dark:text-rose-400">988 Lifeline (US & Canada)</strong>
              <span className="font-mono text-sm font-bold text-on-surface mt-0.5">Call or Text 988</span>
              <span className="text-[11px] text-on-surface-variant/80">Available 24/7, free, confidential</span>
            </div>
            <div className="p-3 rounded-xl bg-surface/80 border border-rose-500/20 text-xs flex flex-col">
              <strong className="text-rose-600 dark:text-rose-400">Crisis Text Line</strong>
              <span className="font-mono text-sm font-bold text-on-surface mt-0.5">Text HOME to 741741</span>
              <span className="text-[11px] text-on-surface-variant/80">Free text crisis support</span>
            </div>
            <div className="p-3 rounded-xl bg-surface/80 border border-rose-500/20 text-xs flex flex-col">
              <strong className="text-rose-600 dark:text-rose-400">Emergency Services</strong>
              <span className="font-mono text-sm font-bold text-on-surface mt-0.5">Call 112 / 911 / 999</span>
              <span className="text-[11px] text-on-surface-variant/80">Immediate urgent response</span>
            </div>
          </div>
        </div>
      )}

      {/* ── Key Score Metrics ─────────────────────────────────── */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        {/* Total Score */}
        <div className="p-5 sm:p-6 rounded-2xl bg-surface-variant/25 border border-outline-variant/25 flex flex-col items-center justify-center text-center">
          <span className="text-xs uppercase tracking-wider text-on-surface-variant font-medium">
            Total Score
          </span>
          <div className="text-4xl font-extrabold text-primary mt-1 font-mono tracking-tight">
            {result.total_score}
            <span className="text-base text-on-surface-variant font-normal"> / {result.max_score}</span>
          </div>
          {scoreDiff !== null && (
            <span
              className={`text-[11px] mt-1 font-semibold flex items-center gap-1 ${
                scoreDiff < 0
                  ? "text-emerald-600 dark:text-emerald-400"
                  : scoreDiff > 0
                  ? "text-amber-600 dark:text-amber-400"
                  : "text-on-surface-variant"
              }`}
            >
              <span className="material-symbols-outlined text-xs" aria-hidden="true">
                {scoreDiff < 0 ? "trending_down" : scoreDiff > 0 ? "trending_up" : "remove"}
              </span>
              <span>
                {scoreDiff > 0 ? `+${scoreDiff}` : scoreDiff} vs previous check-in
              </span>
            </span>
          )}
        </div>

        {/* Severity Band */}
        <div className="p-5 sm:p-6 rounded-2xl bg-surface-variant/25 border border-outline-variant/25 flex flex-col items-center justify-center text-center">
          <span className="text-xs uppercase tracking-wider text-on-surface-variant font-medium">
            Severity Classification
          </span>
          <div className="text-2xl font-bold text-on-surface mt-1">
            {result.severity_band}
          </div>
          <span className="text-[11px] text-on-surface-variant/80 mt-1">
            {isPhq
              ? "Cutoffs: 0-4 Minimal, 5-9 Mild, 10-14 Mod, 15-19 Mod Sev, 20-27 Sev"
              : "Cutoffs: 0-4 Minimal, 5-9 Mild, 10-14 Mod, 15-21 Severe"}
          </span>
        </div>

        {/* App Risk Tier */}
        <div className="p-5 sm:p-6 rounded-2xl bg-surface-variant/25 border border-outline-variant/25 flex flex-col items-center justify-center text-center">
          <span className="text-xs uppercase tracking-wider text-on-surface-variant font-medium">
            Care Navigation Tier
          </span>
          <div className="text-2xl font-bold mt-1 flex items-center justify-center gap-2">
            <span>
              {result.risk_tier === "Low" ? "🟢" : result.risk_tier === "Moderate" ? "🟡" : "🔴"}
            </span>
            <span className="text-on-surface">{result.risk_tier}</span>
          </div>
          <span className="text-[11px] text-on-surface-variant/80 mt-1">
            {result.risk_tier === "Low"
              ? "Self-care & lifestyle support"
              : result.risk_tier === "Moderate"
              ? "Guided CBT & counseling consult"
              : "Professional clinical evaluation advised"}
          </span>
        </div>
      </div>

      {/* ── Section Navigation Tabs ───────────────────────────── */}
      <div className="flex border-b border-outline-variant/20 gap-2 overflow-x-auto pb-1">
        {[
          { id: "summary", label: "Executive Summary", icon: "subject" },
          { id: "symptoms", label: "Symptom Breakdown", icon: "checklist" },
          { id: "context", label: "Daily Functioning & Context", icon: "psychology" },
          { id: "progress", label: "Progress Tracking", icon: "timeline" },
        ].map((tab) => (
          <button
            key={tab.id}
            type="button"
            onClick={() => setActiveTab(tab.id as "summary" | "symptoms" | "context" | "progress")}
            className={`px-4 py-2.5 rounded-xl text-xs sm:text-sm font-semibold transition-all flex items-center gap-2 shrink-0 cursor-pointer ${
              activeTab === tab.id
                ? "bg-primary text-on-primary shadow-sm"
                : "text-on-surface-variant hover:bg-surface-variant/40"
            }`}
          >
            <span className="material-symbols-outlined text-base" aria-hidden="true">
              {tab.icon}
            </span>
            <span>{tab.label}</span>
          </button>
        ))}
      </div>

      {/* ── TAB 1: EXECUTIVE SUMMARY ──────────────────────────── */}
      {activeTab === "summary" && (
        <div className="flex flex-col gap-6 animate-in fade-in duration-150">
          {/* Supportive Reflection Card */}
          <div className="p-6 rounded-2xl bg-primary/10 border border-primary/25 flex flex-col gap-3">
            <h3 className="text-sm font-bold text-primary flex items-center gap-2">
              <span className="material-symbols-outlined text-lg" aria-hidden="true">
                auto_awesome
              </span>
              <span>Reflective Summary</span>
            </h3>
            <p className="text-sm leading-relaxed text-on-surface whitespace-pre-line">
              {result.plain_language_summary}
            </p>
          </div>

          {/* Actionable Next Steps */}
          <div className="space-y-3">
            <h3 className="text-base font-bold text-on-surface flex items-center gap-2">
              <span className="material-symbols-outlined text-primary text-xl" aria-hidden="true">
                assignment_turned_in
              </span>
              <span>Recommended Next Steps</span>
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {(result.recommended_steps || []).map((step, sIdx) => (
                <div
                  key={sIdx}
                  className="p-4 rounded-xl bg-surface-variant/20 border border-outline-variant/20 text-xs sm:text-sm text-on-surface flex items-start gap-3"
                >
                  <span className="w-5 h-5 rounded-full bg-primary/15 text-primary text-xs font-bold flex items-center justify-center shrink-0 mt-0.5">
                    {sIdx + 1}
                  </span>
                  <span className="leading-relaxed">{step}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Quick Companion Actions */}
          <div className="p-5 rounded-2xl bg-surface-variant/20 border border-outline-variant/20 flex flex-col sm:flex-row items-center justify-between gap-4">
            <div className="space-y-1 text-center sm:text-left">
              <h4 className="text-sm font-semibold text-on-surface">
                Support Your Emotional Balance
              </h4>
              <p className="text-xs text-on-surface-variant">
                Try a brief grounding session or externalize your thoughts in the daily journal.
              </p>
            </div>
            <div className="flex items-center gap-2.5 w-full sm:w-auto">
              <Link
                href="/journal"
                className="flex-1 sm:flex-none px-4 py-2.5 rounded-full border border-primary/40 text-primary hover:bg-primary/10 text-xs font-medium text-center transition-colors"
              >
                Open Journal
              </Link>
              <Link
                href="/therapy/chat"
                className="flex-1 sm:flex-none px-4 py-2.5 rounded-full bg-primary hover:bg-primary/90 text-on-primary text-xs font-medium text-center transition-colors shadow-sm"
              >
                Talk with Companion
              </Link>
            </div>
          </div>
        </div>
      )}

      {/* ── TAB 2: SYMPTOM BREAKDOWN ─────────────────────────── */}
      {activeTab === "symptoms" && (
        <div className="flex flex-col gap-6 animate-in fade-in duration-150">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-base font-bold text-on-surface">
                Reported Symptom Patterns
              </h3>
              <p className="text-xs text-on-surface-variant">
                Based strictly on the answers you provided. Unreported symptoms are not assumed.
              </p>
            </div>
            <span className="text-xs font-semibold px-2.5 py-1 rounded-full bg-surface-variant/40 text-on-surface-variant">
              {result.symptom_breakdown?.reported_count ?? 0} elevated items
            </span>
          </div>

          {/* Clinical Domains */}
          {result.symptom_breakdown?.domains && (
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
              {Object.entries(result.symptom_breakdown.domains).map(([key, domain]) => (
                <div
                  key={key}
                  className="p-4 rounded-xl bg-surface-variant/25 border border-outline-variant/20 flex flex-col justify-between gap-2"
                >
                  <div>
                    <span className="text-xs font-semibold text-on-surface block">
                      {domain.label}
                    </span>
                    {domain.summary && (
                      <span className="text-[11px] text-on-surface-variant/80 block mt-0.5">
                        {domain.summary}
                      </span>
                    )}
                  </div>
                  <div className="flex items-center justify-between pt-2 border-t border-outline-variant/15 text-xs">
                    <span className="text-on-surface-variant">Domain Score:</span>
                    <span className="font-mono font-bold text-primary">
                      {domain.score} / {domain.max}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Detailed Item List */}
          <div className="space-y-3">
            <h4 className="text-xs font-bold uppercase tracking-wider text-on-surface-variant">
              Reported Symptoms ({result.symptom_breakdown?.reported_items.length ?? 0})
            </h4>
            <div className="flex flex-col gap-2">
              {result.symptom_breakdown?.reported_items.map((item) => (
                <div
                  key={item.item_number}
                  className="p-3.5 rounded-xl bg-surface/70 border border-outline-variant/20 flex items-center justify-between gap-3 text-xs sm:text-sm"
                >
                  <div className="flex items-center gap-2.5">
                    <span className="font-mono text-xs font-bold text-primary bg-primary/10 px-2 py-0.5 rounded-md shrink-0">
                      Q{item.item_number}
                    </span>
                    <span className="text-on-surface font-medium">{item.question}</span>
                  </div>
                  <span
                    className={`px-2.5 py-1 rounded-full text-xs font-semibold shrink-0 ${
                      item.score === 3
                        ? "bg-rose-500/15 text-rose-600 dark:text-rose-400 border border-rose-500/25"
                        : item.score === 2
                        ? "bg-amber-500/15 text-amber-700 dark:text-amber-400 border border-amber-500/25"
                        : "bg-primary/10 text-primary border border-primary/20"
                    }`}
                  >
                    {item.frequency_label} ({item.score})
                  </span>
                </div>
              ))}

              {(!result.symptom_breakdown?.reported_items ||
                result.symptom_breakdown.reported_items.length === 0) && (
                <div className="p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-xs text-emerald-700 dark:text-emerald-300">
                  No elevated symptoms were endorsed (&quot;Not at all&quot; selected for all items).
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ── TAB 3: FUNCTIONING & CONTEXT ─────────────────────── */}
      {activeTab === "context" && (
        <div className="flex flex-col gap-6 animate-in fade-in duration-150">
          <div>
            <h3 className="text-base font-bold text-on-surface">
              Daily Functioning & Contextual Findings
            </h3>
            <p className="text-xs text-on-surface-variant">
              How emotional factors interface with your daily life, routines, and life stressors.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Global Difficulty */}
            <div className="p-5 rounded-2xl bg-surface-variant/25 border border-outline-variant/20 flex flex-col gap-2">
              <span className="text-xs font-semibold text-primary uppercase tracking-wider">
                Functional Impairment
              </span>
              <div className="text-lg font-bold text-on-surface">
                {result.follow_up_summary?.functional_difficulty || "Not specified"}
              </div>
              <p className="text-xs text-on-surface-variant leading-relaxed">
                Reflects reported difficulty managing studying, employment, domestic tasks, or interpersonal relationships.
              </p>
            </div>

            {/* Duration & Trajectory */}
            <div className="p-5 rounded-2xl bg-surface-variant/25 border border-outline-variant/20 flex flex-col gap-2">
              <span className="text-xs font-semibold text-primary uppercase tracking-wider">
                Duration & Course
              </span>
              <div className="text-lg font-bold text-on-surface">
                {result.follow_up_summary?.duration !== "Not specified"
                  ? `${result.follow_up_summary?.duration} • ${result.follow_up_summary?.trajectory}`
                  : "Not specified"}
              </div>
              <p className="text-xs text-on-surface-variant leading-relaxed">
                Prior history: <strong>{result.follow_up_summary?.prior_history || "None noted"}</strong>
              </p>
            </div>

            {/* Impacted Areas */}
            <div className="p-5 rounded-2xl bg-surface-variant/25 border border-outline-variant/20 flex flex-col gap-2">
              <span className="text-xs font-semibold text-primary uppercase tracking-wider">
                Specific Impact Areas
              </span>
              {result.follow_up_summary?.impact_areas && result.follow_up_summary.impact_areas.length > 0 ? (
                <div className="flex flex-wrap gap-1.5 mt-1">
                  {result.follow_up_summary.impact_areas.map((area, idx) => (
                    <span
                      key={idx}
                      className="px-2.5 py-1 rounded-full bg-primary/10 text-primary text-xs font-medium border border-primary/20"
                    >
                      {area}
                    </span>
                  ))}
                </div>
              ) : (
                <span className="text-xs text-on-surface-variant">No specific areas marked</span>
              )}
            </div>

            {/* Coping Goals */}
            <div className="p-5 rounded-2xl bg-surface-variant/25 border border-outline-variant/20 flex flex-col gap-2">
              <span className="text-xs font-semibold text-primary uppercase tracking-wider">
                Identified Coping Goals
              </span>
              {result.follow_up_summary?.coping_goals && result.follow_up_summary.coping_goals.length > 0 ? (
                <div className="flex flex-wrap gap-1.5 mt-1">
                  {result.follow_up_summary.coping_goals.map((goal, idx) => (
                    <span
                      key={idx}
                      className="px-2.5 py-1 rounded-full bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 text-xs font-medium border border-emerald-500/20"
                    >
                      {goal}
                    </span>
                  ))}
                </div>
              ) : (
                <span className="text-xs text-on-surface-variant">No specific goals marked</span>
              )}
            </div>
          </div>

          {/* Bipolar / Mood Elevation Note */}
          {result.follow_up_summary?.elevation_screen_endorsed && (
            <div className="p-4 rounded-2xl bg-amber-500/10 border border-amber-500/25 flex items-start gap-3 text-xs sm:text-sm text-on-surface">
              <span className="material-symbols-outlined text-amber-600 dark:text-amber-400 text-xl shrink-0 mt-0.5" aria-hidden="true">
                info
              </span>
              <div>
                <strong className="text-amber-700 dark:text-amber-400 block font-semibold mb-1">
                  Clinical Care Navigation Consideration
                </strong>
                <p className="leading-relaxed text-on-surface-variant">
                  {result.follow_up_summary.elevation_screen_note ||
                    "Periods of unusually elevated energy or decreased sleep were reported. Sharing this with a qualified clinician is advised for proper differential diagnostic evaluation."}
                </p>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── TAB 4: PROGRESS TRACKING ──────────────────────────── */}
      {activeTab === "progress" && (
        <div className="flex flex-col gap-6 animate-in fade-in duration-150">
          <div>
            <h3 className="text-base font-bold text-on-surface">
              Screening History & Trajectory
            </h3>
            <p className="text-xs text-on-surface-variant">
              Track how your self-screening scores evolve over successive check-ins.
            </p>
          </div>

          {isGuest && (
            <div className="p-4 rounded-2xl bg-primary/10 border border-primary/25 flex flex-col sm:flex-row items-center justify-between gap-3 text-xs">
              <span>
                You took this check-in as a guest. Create an account to preserve long-term history and trend charts.
              </span>
              <button
                type="button"
                onClick={() => openAuthModal("signup")}
                className="px-4 py-2 rounded-full bg-primary text-on-primary font-semibold shrink-0 cursor-pointer"
              >
                Create Account
              </button>
            </div>
          )}

          {loadingHistory ? (
            <div className="py-8 text-center text-xs text-on-surface-variant flex items-center justify-center gap-2">
              <span className="material-symbols-outlined animate-spin text-sm" aria-hidden="true">
                progress_activity
              </span>
              <span>Loading past check-ins...</span>
            </div>
          ) : history.length > 0 ? (
            <div className="flex flex-col gap-3">
              {history.map((h, idx) => (
                <div
                  key={h.id || idx}
                  className={`p-4 rounded-xl border flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 text-xs ${
                    h.id === result.id
                      ? "bg-primary/10 border-primary ring-1 ring-primary/30"
                      : "bg-surface-variant/20 border-outline-variant/20"
                  }`}
                >
                  <div className="flex items-center gap-3">
                    <span className="font-mono font-bold text-sm text-primary px-2.5 py-1 rounded-lg bg-surface/80 border border-outline-variant/20">
                      {h.total_score} / {h.max_score}
                    </span>
                    <div>
                      <strong className="text-on-surface block text-sm">
                        {h.test_type.toUpperCase()} • {h.severity_band}
                      </strong>
                      <span className="text-[11px] text-on-surface-variant">
                        {new Date(h.timestamp).toLocaleString(undefined, {
                          dateStyle: "medium",
                          timeStyle: "short",
                        })}
                      </span>
                    </div>
                  </div>

                  <div className="flex items-center gap-2 self-end sm:self-auto">
                    {h.safety_flag && (
                      <span className="px-2 py-0.5 rounded-full bg-rose-500/15 text-rose-600 dark:text-rose-400 text-[11px] font-semibold border border-rose-500/25">
                        Safety Alert
                      </span>
                    )}
                    <span className="px-2.5 py-1 rounded-full bg-surface/80 text-on-surface-variant font-medium border border-outline-variant/20">
                      Tier: {h.risk_tier}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="p-6 rounded-2xl bg-surface-variant/15 border border-outline-variant/20 text-center text-xs text-on-surface-variant">
              This is your first recorded self-assessment in this profile. Regular check-ins every 2–4 weeks will illustrate your wellbeing trajectory over time.
            </div>
          )}

          {/* Progress Disclaimer */}
          <p className="text-[11px] text-on-surface-variant/80 italic leading-relaxed pt-2 border-t border-outline-variant/15">
            <strong>Trajectory Disclaimer:</strong> Natural symptom fluctuations, life circumstances, and external stressors all influence scores over time. Observed score changes reflect your subjective check-in patterns and do not prove that any single tool caused clinical change.
          </p>
        </div>
      )}

      {/* ── Prominent Clinical Disclaimer ─────────────────────── */}
      <div className="p-4 rounded-xl bg-surface-variant/15 border border-outline-variant/20 text-[11px] text-on-surface-variant/90 leading-relaxed">
        <strong>Clinical Disclaimer:</strong> {result.clinical_disclaimer}
      </div>

      {/* ── Bottom Actions ────────────────────────────────────── */}
      <div className="pt-4 border-t border-outline-variant/20 flex flex-col sm:flex-row items-center justify-between gap-4">
        <button
          type="button"
          onClick={() => onRetake(result.test_type as "phq9" | "gad7")}
          className="text-xs text-on-surface-variant hover:text-primary font-medium flex items-center gap-1.5 cursor-pointer"
        >
          <span className="material-symbols-outlined text-sm" aria-hidden="true">
            restart_alt
          </span>
          <span>Retake this assessment</span>
        </button>

        <div className="flex items-center gap-3 w-full sm:w-auto">
          {isGuest && (
            <button
              type="button"
              onClick={() => openAuthModal("signup")}
              className="w-full sm:w-auto px-5 py-2.5 rounded-full border border-primary/40 text-primary text-xs font-semibold hover:bg-primary/10 transition-colors cursor-pointer"
            >
              Sign Up to Save Trends
            </button>
          )}

          <Link
            href="/"
            className="w-full sm:w-auto px-6 py-2.5 rounded-full bg-primary hover:bg-primary/90 text-on-primary text-xs sm:text-sm font-semibold transition-all shadow-md hover:shadow-lg flex items-center justify-center gap-1.5"
          >
            <span>Return to Dashboard</span>
            <span className="material-symbols-outlined text-sm" aria-hidden="true">
              arrow_forward
            </span>
          </Link>
        </div>
      </div>
    </div>
  );
}
