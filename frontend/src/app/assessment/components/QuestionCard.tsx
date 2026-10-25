"use client";

import React, { useEffect, useRef } from "react";

export const STANDARD_SCALE_OPTIONS = [
  { value: 0, label: "Not at all" },
  { value: 1, label: "Several days" },
  { value: 2, label: "More than half the days" },
  { value: 3, label: "Nearly every day" },
];

interface QuestionCardProps {
  questionNumber: number;
  totalQuestions: number;
  questionText: string;
  timeframe: string;
  selectedValue: number | null;
  onSelect: (value: number) => void;
  onNext: () => void;
  onPrev: () => void;
  onReviewMode: () => void;
  isFirst: boolean;
  isLast: boolean;
  validationError?: string | null;
}

export function QuestionCard({
  questionNumber,
  totalQuestions,
  questionText,
  timeframe,
  selectedValue,
  onSelect,
  onNext,
  onPrev,
  onReviewMode,
  isFirst,
  isLast,
  validationError,
}: QuestionCardProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  // Keyboard navigation: 0, 1, 2, 3 or Enter to advance
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Don't intercept if user is typing in an input
      if (
        document.activeElement?.tagName === "INPUT" ||
        document.activeElement?.tagName === "TEXTAREA"
      ) {
        return;
      }

      if (e.key === "0" || e.key === "1" || e.key === "2" || e.key === "3") {
        onSelect(parseInt(e.key, 10));
      } else if (e.key === "ArrowRight" || (e.key === "Enter" && selectedValue !== null)) {
        onNext();
      } else if (e.key === "ArrowLeft" && !isFirst) {
        onPrev();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [selectedValue, isFirst, onNext, onPrev, onSelect]);

  const progressPercent = Math.round((questionNumber / totalQuestions) * 100);

  return (
    <div
      ref={containerRef}
      className="glass-panel rounded-3xl p-6 sm:p-8 md:p-10 bg-surface/75 border border-outline-variant/30 backdrop-blur-md shadow-2xl flex flex-col gap-6 animate-in fade-in zoom-in-98 duration-150"
    >
      {/* Top Header & Progress */}
      <div className="flex flex-col gap-3">
        <div className="flex items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <span className="font-mono text-xs font-bold text-primary bg-primary/10 px-2.5 py-1 rounded-full border border-primary/20">
              Question {questionNumber} of {totalQuestions}
            </span>
            {selectedValue !== null && (
              <span className="text-xs text-emerald-600 dark:text-emerald-400 flex items-center gap-1 font-medium">
                <span className="material-symbols-outlined text-sm" aria-hidden="true">
                  check_circle
                </span>
                <span>Answered</span>
              </span>
            )}
          </div>

          <button
            type="button"
            onClick={onReviewMode}
            className="text-xs text-on-surface-variant hover:text-primary font-medium transition-colors flex items-center gap-1 cursor-pointer focus:outline-none focus:underline"
          >
            <span className="material-symbols-outlined text-sm" aria-hidden="true">
              checklist
            </span>
            <span>Review All Answers</span>
          </button>
        </div>

        {/* Visual Progress Bar */}
        <div
          className="w-full h-1.5 rounded-full bg-surface-variant/40 overflow-hidden"
          role="progressbar"
          aria-valuenow={progressPercent}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label={`Question ${questionNumber} of ${totalQuestions}`}
        >
          <div
            className="h-full bg-gradient-to-r from-primary to-primary/80 transition-all duration-300 rounded-full"
            style={{ width: `${progressPercent}%` }}
          />
        </div>
      </div>

      {/* Timeframe reminder */}
      <p className="text-xs text-on-surface-variant italic">
        {timeframe}
      </p>

      {/* Question Text */}
      <fieldset className="flex flex-col gap-6 border-0 p-0 m-0">
        <legend className="text-lg sm:text-xl md:text-2xl font-semibold text-on-surface leading-snug">
          {questionText}
        </legend>

        {/* 4 Accessible Radio Choices */}
        <div
          role="radiogroup"
          aria-label={questionText}
          className="grid grid-cols-1 sm:grid-cols-2 gap-3"
        >
          {STANDARD_SCALE_OPTIONS.map((opt) => {
            const isSelected = selectedValue === opt.value;
            return (
              <button
                key={opt.value}
                type="button"
                role="radio"
                aria-checked={isSelected}
                tabIndex={0}
                onClick={() => onSelect(opt.value)}
                className={`p-4 sm:p-5 rounded-2xl border text-left transition-all cursor-pointer flex items-center justify-between gap-3 group relative focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 ${
                  isSelected
                    ? "bg-primary/15 border-primary text-primary shadow-md ring-1 ring-primary/40 font-semibold"
                    : "bg-surface/80 border-outline-variant/30 hover:border-outline-variant/60 hover:bg-surface-variant/20 text-on-surface"
                }`}
              >
                <div className="flex items-center gap-3">
                  <span
                    className={`w-7 h-7 rounded-full flex items-center justify-center font-mono text-xs font-bold transition-all shrink-0 ${
                      isSelected
                        ? "bg-primary text-on-primary shadow-sm"
                        : "bg-surface-variant/50 text-on-surface-variant group-hover:bg-primary/15 group-hover:text-primary"
                    }`}
                  >
                    {opt.value}
                  </span>
                  <span className="text-sm sm:text-base leading-tight">
                    {opt.label}
                  </span>
                </div>

                {isSelected ? (
                  <span className="material-symbols-outlined text-primary text-xl shrink-0" aria-hidden="true">
                    radio_button_checked
                  </span>
                ) : (
                  <span className="material-symbols-outlined text-outline-variant/50 text-xl shrink-0 group-hover:text-outline-variant" aria-hidden="true">
                    radio_button_unchecked
                  </span>
                )}
              </button>
            );
          })}
        </div>
      </fieldset>

      {/* Validation Message */}
      {validationError && (
        <div
          className="p-3.5 rounded-xl bg-error/10 border border-error/25 text-error text-xs flex items-center gap-2 animate-in fade-in"
          role="alert"
        >
          <span className="material-symbols-outlined text-base shrink-0" aria-hidden="true">
            warning
          </span>
          <span>{validationError}</span>
        </div>
      )}

      {/* Bottom Controls: Back, Continue / Review */}
      <div className="pt-4 border-t border-outline-variant/20 flex flex-col sm:flex-row items-center justify-between gap-3">
        <button
          type="button"
          onClick={onPrev}
          disabled={isFirst}
          className="w-full sm:w-auto px-5 py-2.5 rounded-full border border-outline-variant/40 text-on-surface-variant hover:text-on-surface hover:bg-surface-variant/30 text-xs font-medium transition-all disabled:opacity-30 disabled:pointer-events-none flex items-center justify-center gap-1.5 cursor-pointer"
        >
          <span className="material-symbols-outlined text-sm" aria-hidden="true">
            arrow_back
          </span>
          <span>Back</span>
        </button>

        <div className="flex items-center gap-3 w-full sm:w-auto">
          <span className="hidden md:inline text-[11px] text-on-surface-variant/70">
            Tip: Press 0–3 or Enter
          </span>

          <button
            type="button"
            onClick={onNext}
            className="w-full sm:w-auto px-7 py-3 rounded-full bg-primary hover:bg-primary/90 text-on-primary font-medium text-xs sm:text-sm transition-all shadow-md hover:shadow-lg flex items-center justify-center gap-2 cursor-pointer focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2"
          >
            <span>{isLast ? "Proceed to Contextual Follow-Up" : "Continue"}</span>
            <span className="material-symbols-outlined text-sm" aria-hidden="true">
              arrow_forward
            </span>
          </button>
        </div>
      </div>
    </div>
  );
}
