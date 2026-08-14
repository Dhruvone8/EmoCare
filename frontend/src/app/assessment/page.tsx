"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import { submitAssessment } from "@/lib/api";
import type { AssessmentResponse } from "@/types/api";

const SCALE_OPTIONS = [
  { value: 0, label: "Not at all", subtext: "0 days" },
  { value: 1, label: "Several days", subtext: "1-6 days" },
  { value: 2, label: "More than half the days", subtext: "7-11 days" },
  { value: 3, label: "Nearly every day", subtext: "12-14 days" },
];

const PHQ9_QUESTIONS = [
  "Little interest or pleasure in doing things",
  "Feeling down, depressed, or hopeless",
  "Trouble falling or staying asleep, or sleeping too much",
  "Feeling tired or having little energy",
  "Poor appetite or overeating",
  "Feeling bad about yourself — or that you are a failure or have let yourself or your family down",
  "Trouble concentrating on things, such as reading the newspaper or watching television",
  "Moving or speaking so slowly that other people could have noticed? Or the opposite — being so fidgety or restless",
  "Thoughts that you would be better off dead or of hurting yourself in some way",
];

const GAD7_QUESTIONS = [
  "Feeling nervous, anxious, or on edge",
  "Not being able to stop or control worrying",
  "Worrying too much about different things",
  "Trouble relaxing",
  "Being so restless that it is hard to sit still",
  "Becoming easily annoyed or irritable",
  "Feeling afraid, as if something awful might happen",
];

export default function AssessmentPage() {
  const router = useRouter();
  const { user, openAuthModal } = useAuth();

  const [testType, setTestType] = useState<"phq9" | "gad7">("phq9");
  const [consentGiven, setConsentGiven] = useState(false);
  const [responses, setResponses] = useState<number[]>(new Array(9).fill(0));
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<AssessmentResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const questions = testType === "phq9" ? PHQ9_QUESTIONS : GAD7_QUESTIONS;

  const handleTestTypeChange = (type: "phq9" | "gad7") => {
    setTestType(type);
    setResponses(new Array(type === "phq9" ? 9 : 7).fill(0));
    setResult(null);
    setError(null);
  };

  const handleOptionSelect = (questionIndex: number, value: number) => {
    const updated = [...responses];
    updated[questionIndex] = value;
    setResponses(updated);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    const userId = user?.id || "guest_onboarding_" + Math.random().toString(36).substring(7);

    try {
      const res = await submitAssessment({
        user_id: userId,
        test_type: testType,
        responses: responses.slice(0, questions.length),
      });
      setResult(res);

      // Save to localStorage so the home dashboard can immediately reflect baseline
      if (typeof window !== "undefined") {
        localStorage.setItem(
          "emocare_last_assessment",
          JSON.stringify({
            test_type: testType,
            total_score: res.total_score,
            max_score: res.max_score,
            severity_band: res.severity_band,
            risk_tier: res.risk_tier,
            date: new Date().toISOString(),
          })
        );
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to submit assessment.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto flex flex-col gap-8 pb-12">
      {/* ── Header ────────────────────────────────────────────── */}
      <section className="text-center max-w-2xl mx-auto">
        <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-primary/10 text-primary text-xs font-semibold uppercase tracking-wider mb-4 border border-primary/20">
          <span>🌿</span>
          <span>Onboarding & Baseline Check-in</span>
        </div>
        <h1 className="text-3xl md:text-5xl font-semibold text-on-surface tracking-tight leading-tight mb-3">
          Self-Assessment Check-in
        </h1>
        <p className="text-base md:text-lg text-on-surface-variant leading-relaxed">
          Calibrate your personal AI companion with standard, research-backed emotional health questionnaires.
        </p>
      </section>

      {/* ── Disclaimer & Consent Step ─────────────────────────── */}
      {!consentGiven && (
        <div className="glass-panel rounded-2xl p-6 md:p-8 border border-outline-variant/30 bg-surface/60 backdrop-blur-md flex flex-col gap-6 shadow-xl">
          <div className="flex items-start gap-4">
            <div className="p-3 rounded-xl bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20">
              <span className="material-symbols-outlined text-2xl">info</span>
            </div>
            <div>
              <h2 className="text-lg md:text-xl font-semibold text-on-surface mb-2">
                Before You Begin: Academic Project Disclaimer
              </h2>
              <ul className="text-sm text-on-surface-variant space-y-2 list-disc list-inside leading-relaxed">
                <li>
                  <strong>Screening Tool Only:</strong> EmoCare is an affective computing research project and supportive companion. It is <u>not</u> a clinical diagnostic tool or medical device.
                </li>
                <li>
                  <strong>Tracking Trends:</strong> Your assessment results are securely stored in your personal profile to help you reflect on wellbeing patterns over time.
                </li>
                <li>
                  <strong>Immediate Crisis Support:</strong> If you are in severe distress or thinking of self-harm, please reach out to emergency services or call/text <strong>988</strong> (US/Canada) or <strong>112/911</strong>.
                </li>
              </ul>
            </div>
          </div>

          <div className="pt-4 border-t border-outline-variant/20 flex flex-col sm:flex-row items-center justify-between gap-4">
            <p className="text-xs text-on-surface-variant">
              {user ? (
                <>Logged in as <strong>{user.email}</strong></>
              ) : (
                <>You can take this as a guest or <button onClick={() => openAuthModal("signup")} className="text-primary font-semibold hover:underline">sign in</button> to save your trends.</>
              )}
            </p>
            <button
              onClick={() => setConsentGiven(true)}
              className="w-full sm:w-auto px-8 py-3 rounded-full bg-primary hover:bg-primary/90 text-on-primary font-medium text-sm transition-all shadow-md hover:shadow-lg flex items-center justify-center gap-2 cursor-pointer"
            >
              <span>I Understand & Wish to Proceed</span>
              <span className="material-symbols-outlined text-sm">arrow_forward</span>
            </button>
          </div>
        </div>
      )}

      {/* ── Questionnaire Form ─────────────────────────────────── */}
      {consentGiven && !result && (
        <div className="flex flex-col gap-6">
          {/* Test Switcher */}
          <div className="glass-panel rounded-2xl p-2 bg-surface/50 border border-outline-variant/20 flex gap-2">
            <button
              type="button"
              onClick={() => handleTestTypeChange("phq9")}
              className={`flex-1 py-3 px-4 rounded-xl font-medium text-sm transition-all flex items-center justify-center gap-2 cursor-pointer ${
                testType === "phq9"
                  ? "bg-primary text-on-primary shadow-md"
                  : "text-on-surface-variant hover:bg-surface-variant/40"
              }`}
            >
              <span className="material-symbols-outlined text-lg">psychology</span>
              <span>PHQ-9 (Depression Screening)</span>
            </button>
            <button
              type="button"
              onClick={() => handleTestTypeChange("gad7")}
              className={`flex-1 py-3 px-4 rounded-xl font-medium text-sm transition-all flex items-center justify-center gap-2 cursor-pointer ${
                testType === "gad7"
                  ? "bg-primary text-on-primary shadow-md"
                  : "text-on-surface-variant hover:bg-surface-variant/40"
              }`}
            >
              <span className="material-symbols-outlined text-lg">air</span>
              <span>GAD-7 (Anxiety Screening)</span>
            </button>
          </div>

          <div className="glass-panel rounded-2xl p-6 md:p-8 bg-surface/70 border border-outline-variant/30 backdrop-blur-md shadow-xl">
            <div className="mb-6">
              <h2 className="text-xl font-semibold text-on-surface mb-1">
                {testType === "phq9" ? "PHQ-9 Depression Screener" : "GAD-7 Anxiety Screener"}
              </h2>
              <p className="text-sm text-on-surface-variant">
                Over the <strong>last 2 weeks</strong>, how often have you been bothered by any of the following problems?
              </p>
            </div>

            <form onSubmit={handleSubmit} className="flex flex-col gap-8">
              {questions.map((q, qIndex) => (
                <div
                  key={qIndex}
                  className="p-5 rounded-xl bg-surface-variant/20 border border-outline-variant/20 flex flex-col gap-4"
                >
                  <div className="flex items-start gap-3">
                    <span className="font-mono text-xs font-bold text-primary bg-primary/10 px-2 py-1 rounded-md">
                      Q{qIndex + 1}
                    </span>
                    <span className="text-sm md:text-base font-medium text-on-surface leading-snug">
                      {q}
                    </span>
                  </div>

                  {/* 4 Choices */}
                  <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-2.5">
                    {SCALE_OPTIONS.map((opt) => {
                      const isSelected = responses[qIndex] === opt.value;
                      return (
                        <button
                          key={opt.value}
                          type="button"
                          onClick={() => handleOptionSelect(qIndex, opt.value)}
                          className={`p-3 rounded-lg border text-left transition-all cursor-pointer flex flex-col justify-between gap-1 ${
                            isSelected
                              ? "bg-primary/15 border-primary text-primary shadow-sm"
                              : "bg-surface/80 border-outline-variant/20 hover:border-outline-variant/50 text-on-surface"
                          }`}
                        >
                          <span className="text-xs font-semibold">
                            {opt.value} — {opt.label}
                          </span>
                          <span className="text-[11px] text-on-surface-variant/70">
                            {opt.subtext}
                          </span>
                        </button>
                      );
                    })}
                  </div>
                </div>
              ))}

              {error && (
                <div className="p-4 rounded-xl bg-error/10 border border-error/20 text-error text-sm">
                  {error}
                </div>
              )}

              <button
                type="submit"
                disabled={loading}
                className="w-full py-3.5 px-6 rounded-full bg-primary hover:bg-primary/90 text-on-primary font-medium text-base transition-all shadow-lg hover:shadow-xl disabled:opacity-50 flex items-center justify-center gap-2 cursor-pointer"
              >
                {loading ? (
                  <>
                    <span className="material-symbols-outlined animate-spin text-lg">
                      progress_activity
                    </span>
                    <span>Analyzing responses...</span>
                  </>
                ) : (
                  <>
                    <span>Submit & Calculate Baseline</span>
                    <span className="material-symbols-outlined text-lg">check_circle</span>
                  </>
                )}
              </button>
            </form>
          </div>
        </div>
      )}

      {/* ── Results View ─────────────────────────────────────────── */}
      {result && (
        <div className="glass-panel rounded-2xl p-6 md:p-10 bg-surface/80 border border-outline-variant/30 backdrop-blur-md shadow-2xl flex flex-col gap-8 animate-in fade-in zoom-in-95 duration-200">
          <div className="text-center max-w-lg mx-auto">
            <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-primary/10 text-primary mb-4 text-3xl">
              📊
            </div>
            <h2 className="text-2xl md:text-3xl font-semibold text-on-surface mb-2">
              Your Assessment Baseline
            </h2>
            <p className="text-sm text-on-surface-variant">
              {result.test_display_name} • Evaluated {new Date(result.timestamp).toLocaleDateString()}
            </p>
          </div>

          {/* Metric Highlights */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div className="p-5 rounded-xl bg-surface-variant/30 border border-outline-variant/20 text-center">
              <span className="text-xs uppercase tracking-wider text-on-surface-variant font-medium">
                Total Score
              </span>
              <div className="text-3xl font-bold text-primary mt-1 font-mono">
                {result.total_score} <span className="text-sm text-on-surface-variant font-normal">/ {result.max_score}</span>
              </div>
            </div>

            <div className="p-5 rounded-xl bg-surface-variant/30 border border-outline-variant/20 text-center">
              <span className="text-xs uppercase tracking-wider text-on-surface-variant font-medium">
                Severity Band
              </span>
              <div className="text-xl font-bold text-on-surface mt-1">
                {result.severity_band}
              </div>
            </div>

            <div className="p-5 rounded-xl bg-surface-variant/30 border border-outline-variant/20 text-center">
              <span className="text-xs uppercase tracking-wider text-on-surface-variant font-medium">
                App Risk Tier
              </span>
              <div className="text-xl font-bold mt-1 flex items-center justify-center gap-1.5">
                <span>{result.risk_tier === "Low" ? "🟢" : result.risk_tier === "Moderate" ? "🟡" : "🔴"}</span>
                <span>{result.risk_tier}</span>
              </div>
            </div>
          </div>

          {/* Supportive Plain-Language Interpretation */}
          <div
            className={`p-6 rounded-2xl border ${
              result.risk_tier === "Low"
                ? "bg-emerald-500/10 border-emerald-500/30 text-on-surface"
                : result.risk_tier === "Moderate"
                ? "bg-amber-500/10 border-amber-500/30 text-on-surface"
                : "bg-rose-500/10 border-rose-500/30 text-on-surface"
            }`}
          >
            <h3 className="text-base font-semibold mb-2 flex items-center gap-2">
              <span className="material-symbols-outlined">lightbulb</span>
              <span>Understanding Your Results</span>
            </h3>
            <p className="text-sm leading-relaxed text-on-surface-variant">
              {result.plain_language_summary}
            </p>
          </div>

          {/* Actions */}
          <div className="flex flex-col sm:flex-row items-center justify-between gap-4 pt-4 border-t border-outline-variant/20">
            <button
              onClick={() => {
                setResult(null);
                setResponses(new Array(questions.length).fill(0));
              }}
              className="text-xs text-on-surface-variant hover:text-primary font-medium cursor-pointer"
            >
              ← Re-take or choose another test
            </button>

            <div className="flex items-center gap-3 w-full sm:w-auto">
              {!user && (
                <button
                  onClick={() => openAuthModal("signup")}
                  className="px-5 py-2.5 rounded-full border border-primary/40 text-primary text-xs font-medium hover:bg-primary/10 transition-colors cursor-pointer"
                >
                  Create Account to Save Trends
                </button>
              )}
              <Link
                href="/"
                className="px-6 py-2.5 rounded-full bg-primary hover:bg-primary/90 text-on-primary text-xs font-medium transition-all shadow-md hover:shadow-lg flex items-center justify-center gap-1.5"
              >
                <span>Continue to Dashboard</span>
                <span className="material-symbols-outlined text-sm">arrow_forward</span>
              </Link>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
