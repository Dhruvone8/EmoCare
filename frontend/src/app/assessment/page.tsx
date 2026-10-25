"use client";

import React, { useState } from "react";
import { useAuth } from "@/context/AuthContext";
import { submitAssessment } from "@/lib/api";
import type { AssessmentResponse } from "@/types/api";
import { ConsentIntro } from "./components/ConsentIntro";
import { QuestionCard } from "./components/QuestionCard";
import { ReviewList } from "./components/ReviewList";
import { FollowUpStage, FollowUpFormData } from "./components/FollowUpStage";
import { SafetyModal, SafetyDisclosureData } from "./components/SafetyModal";
import { AssessmentResults } from "./components/AssessmentResults";

// Authoritative PHQ-9 (Kroenke, Spitzer, Williams, 2001)
const PHQ9_QUESTIONS = [
  "Little interest or pleasure in doing things",
  "Feeling down, depressed, or hopeless",
  "Trouble falling or staying asleep, or sleeping too much",
  "Feeling tired or having little energy",
  "Poor appetite or overeating",
  "Feeling bad about yourself — or that you are a failure or have let yourself or your family down",
  "Trouble concentrating on things, such as reading the newspaper or watching television",
  "Moving or speaking so slowly that other people could have noticed? Or the opposite — being so fidgety or restless that you have been moving around a lot more than usual",
  "Thoughts that you would be better off dead or of hurting yourself in some way",
];

const PHQ9_TIMEFRAME =
  "Over the last 2 weeks, how often have you been bothered by any of the following problems?";

// Authoritative GAD-7 (Spitzer, Kroenke, Williams, Löwe, 2006)
const GAD7_QUESTIONS = [
  "Feeling nervous, anxious, or on edge",
  "Not being able to stop or control worrying",
  "Worrying too much about different things",
  "Trouble relaxing",
  "Being so restless that it is hard to sit still",
  "Becoming easily annoyed or irritable",
  "Feeling afraid, as if something awful might happen",
];

const GAD7_TIMEFRAME =
  "Over the last 2 weeks, how often have you been bothered by the following problems?";

type ViewMode = "card" | "review" | "followup" | "results";

export default function AssessmentPage() {
  const { user, openAuthModal } = useAuth();

  // Test Selection & Consent
  const [testType, setTestType] = useState<"phq9" | "gad7">("phq9");
  const [consentGiven, setConsentGiven] = useState(false);

  // Critical fix: Answers start completely UNANSWERED (null)
  // Completely separate state for PHQ-9 and GAD-7 so tab switching preserves answers
  const [phq9Responses, setPhq9Responses] = useState<(number | null)[]>(
    new Array(9).fill(null)
  );
  const [gad7Responses, setGad7Responses] = useState<(number | null)[]>(
    new Array(7).fill(null)
  );

  // Navigation & View mode
  const [currentQuestionIndex, setCurrentQuestionIndex] = useState(0);
  const [viewMode, setViewMode] = useState<ViewMode>("card");

  // Safety pathway state
  const [safetyModalOpen, setSafetyModalOpen] = useState(false);
  const [safetyDisclosure, setSafetyDisclosure] = useState<SafetyDisclosureData | null>(null);

  // Submission & Results
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<AssessmentResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [validationError, setValidationError] = useState<string | null>(null);

  const activeQuestions = testType === "phq9" ? PHQ9_QUESTIONS : GAD7_QUESTIONS;
  const activeTimeframe = testType === "phq9" ? PHQ9_TIMEFRAME : GAD7_TIMEFRAME;
  const activeResponses = testType === "phq9" ? phq9Responses : gad7Responses;

  // Handle Tab Switch (preserves responses for both tests)
  const handleTestTypeChange = (type: "phq9" | "gad7") => {
    if (type === testType) return;
    setTestType(type);
    setCurrentQuestionIndex(0);
    setViewMode("card");
    setValidationError(null);
    setError(null);
  };

  // Option selection
  const handleOptionSelect = (questionIndex: number, value: number) => {
    setValidationError(null);

    if (testType === "phq9") {
      const updated = [...phq9Responses];
      updated[questionIndex] = value;
      setPhq9Responses(updated);

      // Clinical Safety Pathway Trigger: Item 9 endorsed (> 0)
      if (questionIndex === 8 && value > 0 && !safetyDisclosure) {
        setSafetyModalOpen(true);
      }
    } else {
      const updated = [...gad7Responses];
      updated[questionIndex] = value;
      setGad7Responses(updated);
    }
  };

  // Next / Continue button logic
  const handleNext = () => {
    const currentAnswer = activeResponses[currentQuestionIndex];
    if (currentAnswer === null) {
      setValidationError("Please select an answer to continue.");
      return;
    }
    setValidationError(null);

    if (currentQuestionIndex < activeQuestions.length - 1) {
      setCurrentQuestionIndex((prev) => prev + 1);
    } else {
      // Check if all questions are answered
      const allDone = activeResponses.every((r) => r !== null);
      if (allDone) {
        setViewMode("followup");
      } else {
        setViewMode("review");
      }
    }
  };

  const handlePrev = () => {
    setValidationError(null);
    if (currentQuestionIndex > 0) {
      setCurrentQuestionIndex((prev) => prev - 1);
    }
  };

  const handleJumpToQuestion = (qIndex: number) => {
    setValidationError(null);
    setCurrentQuestionIndex(qIndex);
    setViewMode("card");
  };

  const handleProceedToFollowUp = () => {
    const incompleteIndex = activeResponses.findIndex((r) => r === null);
    if (incompleteIndex !== -1) {
      setValidationError(
        `Question ${incompleteIndex + 1} is unanswered. All questions must be completed.`
      );
      return;
    }
    setValidationError(null);
    setViewMode("followup");
  };

  // Handle final submission from Contextual Follow-up
  const handleFollowUpSubmit = async (followUpData: FollowUpFormData) => {
    // Verify no unanswered items
    if (activeResponses.some((r) => r === null)) {
      setError("Assessment is incomplete. Please answer all screening questions.");
      setViewMode("review");
      return;
    }

    setLoading(true);
    setError(null);

    const userId = user?.id || "guest_" + Math.random().toString(36).substring(7);

    try {
      const validResponses = activeResponses as number[];

      const res = await submitAssessment({
        user_id: userId,
        test_type: testType,
        responses: validResponses,
        follow_up_data: followUpData,
        safety_disclosure: safetyDisclosure ? { ...safetyDisclosure } : undefined,
      });

      setResult(res);
      setViewMode("results");

      // Save to localStorage for Home Dashboard baseline display
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

  // Retake or switch assessment
  const handleRetake = (type: "phq9" | "gad7") => {
    setTestType(type);
    if (type === "phq9") {
      setPhq9Responses(new Array(9).fill(null));
    } else {
      setGad7Responses(new Array(7).fill(null));
    }
    setSafetyDisclosure(null);
    setCurrentQuestionIndex(0);
    setResult(null);
    setError(null);
    setValidationError(null);
    setViewMode("card");
  };

  // Approximate tentative score for adaptive branching
  const currentAnsweredScores = activeResponses.filter((r): r is number => r !== null);
  const currentTotal = currentAnsweredScores.reduce((a, b) => a + b, 0);
  const q9Val = testType === "phq9" ? phq9Responses[8] : 0;

  return (
    <div className="max-w-4xl mx-auto flex flex-col gap-6 sm:gap-8 pb-12 w-full">
      {/* ── Page Header ────────────────────────────────────────────── */}
      <section className="text-center max-w-2xl mx-auto px-4">
        <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-primary/10 text-primary text-xs font-semibold uppercase tracking-wider mb-3 border border-primary/20">
          <span>🌿</span>
          <span>Standardized Clinical Self-Screening</span>
        </div>
        <h1 className="text-3xl sm:text-4xl md:text-5xl font-extrabold text-on-surface tracking-tight leading-tight mb-2">
          Emotional Health Check-in
        </h1>
        <p className="text-sm sm:text-base md:text-lg text-on-surface-variant leading-relaxed">
          Validated questionnaires (PHQ-9 & GAD-7) to calibrate your emotional baseline and guide supportive care.
        </p>
      </section>

      {/* ── Step 0: Informed Consent & Clinical Disclaimer ─────────── */}
      {!consentGiven && (
        <ConsentIntro
          user={user}
          onConsent={() => setConsentGiven(true)}
          openAuthModal={openAuthModal}
        />
      )}

      {/* ── Active Assessment Workflow ─────────────────────────────── */}
      {consentGiven && viewMode !== "results" && (
        <div className="flex flex-col gap-6">
          {/* Test Switcher Tabs */}
          <div className="glass-panel rounded-2xl p-2 bg-surface/50 border border-outline-variant/20 flex gap-2">
            <button
              type="button"
              onClick={() => handleTestTypeChange("phq9")}
              className={`flex-1 py-3 px-3 sm:px-4 rounded-xl font-semibold text-xs sm:text-sm transition-all flex items-center justify-center gap-2 cursor-pointer ${
                testType === "phq9"
                  ? "bg-primary text-on-primary shadow-md"
                  : "text-on-surface-variant hover:bg-surface-variant/40"
              }`}
            >
              <span className="material-symbols-outlined text-lg" aria-hidden="true">
                psychology
              </span>
              <span>PHQ-9 Depression Screener</span>
              {phq9Responses.some((r) => r !== null) && (
                <span className="w-2 h-2 rounded-full bg-emerald-400 shrink-0" title="Responses recorded" />
              )}
            </button>

            <button
              type="button"
              onClick={() => handleTestTypeChange("gad7")}
              className={`flex-1 py-3 px-3 sm:px-4 rounded-xl font-semibold text-xs sm:text-sm transition-all flex items-center justify-center gap-2 cursor-pointer ${
                testType === "gad7"
                  ? "bg-primary text-on-primary shadow-md"
                  : "text-on-surface-variant hover:bg-surface-variant/40"
              }`}
            >
              <span className="material-symbols-outlined text-lg" aria-hidden="true">
                air
              </span>
              <span>GAD-7 Anxiety Screener</span>
              {gad7Responses.some((r) => r !== null) && (
                <span className="w-2 h-2 rounded-full bg-emerald-400 shrink-0" title="Responses recorded" />
              )}
            </button>
          </div>

          {/* View Mode 1: Question-by-Question Accessible Card */}
          {viewMode === "card" && (
            <QuestionCard
              questionNumber={currentQuestionIndex + 1}
              totalQuestions={activeQuestions.length}
              questionText={activeQuestions[currentQuestionIndex]}
              timeframe={activeTimeframe}
              selectedValue={activeResponses[currentQuestionIndex]}
              onSelect={(val) => handleOptionSelect(currentQuestionIndex, val)}
              onNext={handleNext}
              onPrev={handlePrev}
              onReviewMode={() => setViewMode("review")}
              isFirst={currentQuestionIndex === 0}
              isLast={currentQuestionIndex === activeQuestions.length - 1}
              validationError={validationError}
            />
          )}

          {/* View Mode 2: Review All Answers List */}
          {viewMode === "review" && (
            <ReviewList
              testType={testType}
              questions={activeQuestions}
              responses={activeResponses}
              onSelectOption={handleOptionSelect}
              onJumpToQuestion={handleJumpToQuestion}
              onProceedToFollowUp={handleProceedToFollowUp}
              onBackToCard={() => setViewMode("card")}
              validationError={validationError}
            />
          )}

          {/* View Mode 3: Adaptive Follow-Up Stage */}
          {viewMode === "followup" && (
            <FollowUpStage
              testType={testType}
              initialTotalScore={currentTotal}
              q9Endorsed={Boolean(q9Val && q9Val > 0)}
              onSubmit={handleFollowUpSubmit}
              onBackToScreening={() => setViewMode("review")}
              isSubmitting={loading}
            />
          )}

          {/* Global API or Submission Error */}
          {error && (
            <div className="p-4 rounded-xl bg-error/10 border border-error/25 text-error text-xs sm:text-sm flex items-center gap-2">
              <span className="material-symbols-outlined text-base shrink-0" aria-hidden="true">
                error
              </span>
              <span>{error}</span>
            </div>
          )}
        </div>
      )}

      {/* ── View Mode 4: Comprehensive Upgraded Results Page ────────── */}
      {viewMode === "results" && result && (
        <AssessmentResults
          result={result}
          onRetake={handleRetake}
          openAuthModal={openAuthModal}
          isGuest={!user}
        />
      )}

      {/* ── Clinical Safety Modal (Dedicated Pathway) ────────────────── */}
      <SafetyModal
        isOpen={safetyModalOpen}
        onProceed={(disclosure) => {
          setSafetyDisclosure(disclosure);
          setSafetyModalOpen(false);
        }}
        onCancel={() => {
          // Reset Q9 answer to null so user can reconsider without being blocked
          if (testType === "phq9") {
            const updated = [...phq9Responses];
            updated[8] = null;
            setPhq9Responses(updated);
          }
          setSafetyModalOpen(false);
        }}
      />
    </div>
  );
}
