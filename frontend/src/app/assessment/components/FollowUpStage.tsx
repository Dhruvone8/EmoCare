"use client";

import React, { useState } from "react";

export interface FollowUpFormData {
  functional_difficulty: string;
  impact_areas: string[];
  duration: string;
  trajectory: string;
  prior_history: string;
  elevation_screen: string;
  life_factors: string[];
  coping_goals: string[];
}

interface FollowUpStageProps {
  testType: "phq9" | "gad7";
  initialTotalScore: number;
  q9Endorsed: boolean;
  onSubmit: (data: FollowUpFormData) => void;
  onBackToScreening: () => void;
  isSubmitting: boolean;
}

const IMPACT_AREA_OPTIONS = [
  "Work or academic studies",
  "Sleep quality & feeling rested",
  "Relationships with family or friends",
  "Concentration & making decisions",
  "Daily self-care, meals, or hygiene",
  "Physical energy & stamina",
];

const LIFE_FACTOR_OPTIONS = [
  "Academic or workplace stress",
  "Recent major life transition or loss",
  "Physical health condition or chronic pain",
  "Financial or housing uncertainty",
  "Relationship or family friction",
  "Sleep schedule disruption",
];

const COPING_GOAL_OPTIONS = [
  "Learning self-guided CBT & grounding tools",
  "Connecting with a licensed therapist or doctor",
  "Establishing consistent sleep & daily routines",
  "Reaching out to trusted friends or family",
  "Quiet emotional reflection & journaling",
];

export function FollowUpStage({
  testType,
  initialTotalScore,
  q9Endorsed,
  onSubmit,
  onBackToScreening,
  isSubmitting,
}: FollowUpStageProps) {
  // Branching flag: Minimal score with no self-harm gets concise 3-question flow
  const isMinimal = initialTotalScore <= 4 && !q9Endorsed;

  const [functionalDifficulty, setFunctionalDifficulty] = useState<string>("Not difficult at all");
  const [impactAreas, setImpactAreas] = useState<string[]>([]);
  const [duration, setDuration] = useState<string>("< 2 weeks");
  const [trajectory, setTrajectory] = useState<string>("Staying about the same");
  const [priorHistory, setPriorHistory] = useState<string>("First time experiencing this level of distress");
  const [elevationScreen, setElevationScreen] = useState<string>("No, never");
  const [lifeFactors, setLifeFactors] = useState<string[]>([]);
  const [copingGoals, setCopingGoals] = useState<string[]>([
    "Learning self-guided CBT & grounding tools",
  ]);

  const toggleMultiSelect = (item: string, current: string[], setter: (v: string[]) => void) => {
    if (current.includes(item)) {
      setter(current.filter((x) => x !== item));
    } else {
      setter([...current, item]);
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSubmit({
      functional_difficulty: functionalDifficulty,
      impact_areas: impactAreas,
      duration: isMinimal ? "Not specified" : duration,
      trajectory: isMinimal ? "Stable" : trajectory,
      prior_history: isMinimal ? "No distress" : priorHistory,
      elevation_screen: isMinimal ? "No, never" : elevationScreen,
      life_factors: lifeFactors,
      coping_goals: copingGoals,
    });
  };

  return (
    <form
      onSubmit={handleSubmit}
      className="glass-panel rounded-3xl p-6 sm:p-8 md:p-10 bg-surface/75 border border-outline-variant/30 backdrop-blur-md shadow-2xl flex flex-col gap-8 animate-in fade-in duration-200"
    >
      {/* Header */}
      <div className="flex flex-col gap-2 pb-4 border-b border-outline-variant/20">
        <div className="flex items-center gap-2">
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-primary/10 text-primary text-xs font-semibold uppercase tracking-wider border border-primary/20">
            <span>🌿</span>
            <span>Adaptive Follow-Up Stage</span>
          </span>
          <span className="text-xs text-on-surface-variant">
            Separate from validated {testType.toUpperCase()} score
          </span>
        </div>
        <h2 className="text-2xl sm:text-3xl font-bold text-on-surface tracking-tight">
          Contextual Wellbeing Check
        </h2>
        <p className="text-sm text-on-surface-variant leading-relaxed">
          Standardized questionnaires capture frequency, but personal context shapes care navigation.
          These brief follow-up questions help calibrate recommendations to your real-world circumstances.
        </p>
      </div>

      {/* Question 1: Global Functional Difficulty */}
      <div className="space-y-3">
        <label className="text-sm sm:text-base font-semibold text-on-surface block">
          1. How difficult have these emotional challenges made it for you to do your work, take care of things at home, or get along with other people?
        </label>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5" role="radiogroup" aria-label="Functional difficulty">
          {[
            "Not difficult at all",
            "Somewhat difficult",
            "Very difficult",
            "Extremely difficult",
          ].map((opt) => {
            const isSelected = functionalDifficulty === opt;
            return (
              <button
                key={opt}
                type="button"
                role="radio"
                aria-checked={isSelected}
                onClick={() => setFunctionalDifficulty(opt)}
                className={`p-3 rounded-xl border text-left text-xs font-medium transition-all cursor-pointer ${
                  isSelected
                    ? "bg-primary/15 border-primary text-primary font-semibold shadow-xs"
                    : "bg-surface/80 border-outline-variant/25 hover:border-outline-variant/50 text-on-surface"
                }`}
              >
                {opt}
              </button>
            );
          })}
        </div>
      </div>

      {/* Question 2: Specific Impact Areas (Multi-select) */}
      <div className="space-y-3">
        <label className="text-sm sm:text-base font-semibold text-on-surface block">
          2. Which areas of everyday living are currently most impacted? <span className="text-xs text-on-surface-variant font-normal">(Select all that apply)</span>
        </label>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
          {IMPACT_AREA_OPTIONS.map((area) => {
            const isSelected = impactAreas.includes(area);
            return (
              <button
                key={area}
                type="button"
                onClick={() => toggleMultiSelect(area, impactAreas, setImpactAreas)}
                className={`p-3 rounded-xl border text-left text-xs transition-all flex items-center justify-between cursor-pointer ${
                  isSelected
                    ? "bg-primary/15 border-primary text-primary font-semibold"
                    : "bg-surface/80 border-outline-variant/20 hover:border-outline-variant/50 text-on-surface"
                }`}
              >
                <span>{area}</span>
                <span className="material-symbols-outlined text-sm" aria-hidden="true">
                  {isSelected ? "check_box" : "check_box_outline_blank"}
                </span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Non-minimal branches */}
      {!isMinimal && (
        <>
          {/* Question 3: Duration & Trajectory */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-6 pt-2 border-t border-outline-variant/20">
            <div className="space-y-2.5">
              <label className="text-xs sm:text-sm font-semibold text-on-surface block">
                3a. How long have you been experiencing these symptoms?
              </label>
              <div className="grid grid-cols-2 gap-2">
                {[
                  "Less than 2 weeks",
                  "2 weeks to 1 month",
                  "1 to 6 months",
                  "Longer than 6 months",
                ].map((dur) => (
                  <button
                    key={dur}
                    type="button"
                    onClick={() => setDuration(dur)}
                    className={`p-2.5 rounded-xl border text-left text-xs transition-all cursor-pointer ${
                      duration === dur
                        ? "bg-primary/15 border-primary text-primary font-semibold"
                        : "bg-surface/80 border-outline-variant/25 text-on-surface"
                    }`}
                  >
                    {dur}
                  </button>
                ))}
              </div>
            </div>

            <div className="space-y-2.5">
              <label className="text-xs sm:text-sm font-semibold text-on-surface block">
                3b. Compared to a few weeks ago, are they:
              </label>
              <div className="grid grid-cols-2 gap-2">
                {[
                  "Improving",
                  "Staying about the same",
                  "Getting more difficult",
                  "Fluctuating up and down",
                ].map((traj) => (
                  <button
                    key={traj}
                    type="button"
                    onClick={() => setTrajectory(traj)}
                    className={`p-2.5 rounded-xl border text-left text-xs transition-all cursor-pointer ${
                      trajectory === traj
                        ? "bg-primary/15 border-primary text-primary font-semibold"
                        : "bg-surface/80 border-outline-variant/25 text-on-surface"
                    }`}
                  >
                    {traj}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Question 4: Prior history */}
          <div className="space-y-3 pt-2 border-t border-outline-variant/20">
            <label className="text-xs sm:text-sm font-semibold text-on-surface block">
              4. Have you experienced similar periods in the past, or are you currently receiving professional care?
            </label>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
              {[
                "First time experiencing this level of distress",
                "I have experienced similar episodes in the past",
                "Currently seeing a counselor or therapist",
                "Currently taking prescribed mental health medication",
              ].map((item) => (
                <button
                  key={item}
                  type="button"
                  onClick={() => setPriorHistory(item)}
                  className={`p-3 rounded-xl border text-left text-xs transition-all cursor-pointer ${
                    priorHistory === item
                      ? "bg-primary/15 border-primary text-primary font-semibold"
                      : "bg-surface/80 border-outline-variant/25 text-on-surface"
                  }`}
                >
                  {item}
                </button>
              ))}
            </div>
          </div>

          {/* Question 5: Mood Elevation Screening (Hypomania / Bipolar Differential) */}
          <div className="space-y-3 pt-2 border-t border-outline-variant/20">
            <div className="flex items-start gap-2">
              <span className="material-symbols-outlined text-primary text-base mt-0.5" aria-hidden="true">
                tune
              </span>
              <div>
                <label className="text-xs sm:text-sm font-semibold text-on-surface block">
                  5. Mood Variation Screen: Have you ever experienced a distinct period of several days where you felt unusually energetic, irritable, or &apos;wired&apos;—needing much less sleep than usual, with racing thoughts or taking impulsive risks?
                </label>
                <p className="text-[11px] text-on-surface-variant/80 mt-0.5">
                  This helps clinical providers distinguish between unipolar and bipolar spectrum patterns.
                </p>
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5" role="radiogroup">
              {[
                "No, never",
                "Yes, once or twice in the past",
                "Yes, multiple times or recently",
              ].map((opt) => (
                <button
                  key={opt}
                  type="button"
                  role="radio"
                  aria-checked={elevationScreen === opt}
                  onClick={() => setElevationScreen(opt)}
                  className={`p-3 rounded-xl border text-left text-xs transition-all cursor-pointer ${
                    elevationScreen === opt
                      ? "bg-primary/15 border-primary text-primary font-semibold"
                      : "bg-surface/80 border-outline-variant/25 text-on-surface"
                  }`}
                >
                  {opt}
                </button>
              ))}
            </div>
          </div>
        </>
      )}

      {/* Contributing Life Circumstances */}
      <div className="space-y-3 pt-2 border-t border-outline-variant/20">
        <label className="text-xs sm:text-sm font-semibold text-on-surface block">
          {isMinimal ? "3" : "6"}. Are any of these life factors contributing to how you feel right now? <span className="text-xs text-on-surface-variant font-normal">(Optional)</span>
        </label>
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2.5">
          {LIFE_FACTOR_OPTIONS.map((factor) => {
            const isSelected = lifeFactors.includes(factor);
            return (
              <button
                key={factor}
                type="button"
                onClick={() => toggleMultiSelect(factor, lifeFactors, setLifeFactors)}
                className={`p-2.5 rounded-xl border text-left text-xs transition-all flex items-center justify-between cursor-pointer ${
                  isSelected
                    ? "bg-primary/15 border-primary text-primary font-semibold"
                    : "bg-surface/80 border-outline-variant/20 text-on-surface"
                }`}
              >
                <span>{factor}</span>
                <span className="material-symbols-outlined text-xs" aria-hidden="true">
                  {isSelected ? "check_box" : "check_box_outline_blank"}
                </span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Coping Goals */}
      <div className="space-y-3 pt-2 border-t border-outline-variant/20">
        <label className="text-xs sm:text-sm font-semibold text-on-surface block">
          {isMinimal ? "4" : "7"}. What kind of support feels most relevant to you today?
        </label>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
          {COPING_GOAL_OPTIONS.map((goal) => {
            const isSelected = copingGoals.includes(goal);
            return (
              <button
                key={goal}
                type="button"
                onClick={() => toggleMultiSelect(goal, copingGoals, setCopingGoals)}
                className={`p-3 rounded-xl border text-left text-xs transition-all flex items-center justify-between cursor-pointer ${
                  isSelected
                    ? "bg-primary/15 border-primary text-primary font-semibold"
                    : "bg-surface/80 border-outline-variant/20 text-on-surface"
                }`}
              >
                <span>{goal}</span>
                <span className="material-symbols-outlined text-xs" aria-hidden="true">
                  {isSelected ? "check_box" : "check_box_outline_blank"}
                </span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Controls */}
      <div className="pt-4 border-t border-outline-variant/20 flex flex-col sm:flex-row items-center justify-between gap-3">
        <button
          type="button"
          onClick={onBackToScreening}
          className="w-full sm:w-auto px-5 py-2.5 rounded-full border border-outline-variant/40 text-on-surface-variant hover:text-on-surface hover:bg-surface-variant/30 text-xs font-medium transition-colors flex items-center justify-center gap-1.5 cursor-pointer"
        >
          <span className="material-symbols-outlined text-sm" aria-hidden="true">
            arrow_back
          </span>
          <span>Back to Screening Questions</span>
        </button>

        <button
          type="submit"
          disabled={isSubmitting}
          className="w-full sm:w-auto px-8 py-3.5 rounded-full bg-primary hover:bg-primary/90 text-on-primary font-medium text-sm transition-all shadow-lg hover:shadow-xl disabled:opacity-50 flex items-center justify-center gap-2 cursor-pointer focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2"
        >
          {isSubmitting ? (
            <>
              <span className="material-symbols-outlined animate-spin text-lg" aria-hidden="true">
                progress_activity
              </span>
              <span>Analyzing & Synthesizing Results...</span>
            </>
          ) : (
            <>
              <span>Complete Screening & View Report</span>
              <span className="material-symbols-outlined text-base" aria-hidden="true">
                check_circle
              </span>
            </>
          )}
        </button>
      </div>
    </form>
  );
}
