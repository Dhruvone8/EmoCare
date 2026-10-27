"use client";

import React from "react";
import { STANDARD_SCALE_OPTIONS } from "./QuestionCard";

interface ReviewListProps {
  testType: "phq9" | "gad7";
  questions: string[];
  responses: (number | null)[];
  onSelectOption: (qIndex: number, val: number) => void;
  onJumpToQuestion: (qIndex: number) => void;
  onProceedToFollowUp: () => void;
  onBackToCard: () => void;
  validationError?: string | null;
}

export function ReviewList({
  testType,
  questions,
  responses,
  onSelectOption,
  onJumpToQuestion,
  onProceedToFollowUp,
  onBackToCard,
  validationError,
}: ReviewListProps) {
  const answeredCount = responses.filter((r) => r !== null).length;
  const allAnswered = answeredCount === questions.length;

  return (
    <div className="glass-panel rounded-3xl p-6 sm:p-8 md:p-10 bg-surface/75 border border-outline-variant/30 backdrop-blur-md shadow-2xl flex flex-col gap-6 animate-in fade-in duration-200">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 border-b border-outline-variant/20">
        <div>
          <h2 className="text-xl sm:text-2xl font-bold text-on-surface">
            Review Your Answers ({testType.toUpperCase()})
          </h2>
          <p className="text-xs sm:text-sm text-on-surface-variant mt-0.5">
            Check your selections below. You can change any answer or click a question to return to single-card view.
          </p>
        </div>

        <div className="flex items-center gap-2 self-start sm:self-auto">
          <span
            className={`px-3 py-1 rounded-full text-xs font-semibold ${
              allAnswered
                ? "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border border-emerald-500/30"
                : "bg-amber-500/15 text-amber-700 dark:text-amber-400 border border-amber-500/30"
            }`}
          >
            {answeredCount} of {questions.length} answered
          </span>
        </div>
      </div>

      {/* Questions list */}
      <div className="flex flex-col gap-4">
        {questions.map((q, idx) => {
          const val = responses[idx];
          const isAnswered = val !== null;

          return (
            <div
              key={idx}
              className={`p-4 sm:p-5 rounded-2xl border transition-all ${
                isAnswered
                  ? "bg-surface-variant/20 border-outline-variant/25"
                  : "bg-amber-500/5 border-amber-500/40 ring-1 ring-amber-500/30"
              }`}
            >
              <div className="flex items-start justify-between gap-3 mb-3">
                <div className="flex items-start gap-3">
                  <span className="font-mono text-xs font-bold text-primary bg-primary/10 px-2 py-0.5 rounded-md shrink-0 mt-0.5">
                    Q{idx + 1}
                  </span>
                  <span className="text-sm sm:text-base font-medium text-on-surface leading-snug">
                    {q}
                  </span>
                </div>

                <button
                  type="button"
                  onClick={() => onJumpToQuestion(idx)}
                  className="text-[11px] text-primary hover:underline font-semibold shrink-0 cursor-pointer"
                >
                  Focus
                </button>
              </div>

              {/* 4 Choices */}
              <div
                role="radiogroup"
                aria-label={`Question ${idx + 1}: ${q}`}
                className="grid grid-cols-2 sm:grid-cols-4 gap-2"
              >
                {STANDARD_SCALE_OPTIONS.map((opt) => {
                  const isSelected = val === opt.value;
                  return (
                    <button
                      key={opt.value}
                      type="button"
                      role="radio"
                      aria-checked={isSelected}
                      onClick={() => onSelectOption(idx, opt.value)}
                      className={`p-2.5 rounded-xl border text-left text-xs transition-all cursor-pointer flex items-center justify-between gap-1.5 focus:outline-none focus:ring-2 focus:ring-primary ${
                        isSelected
                          ? "bg-primary/15 border-primary text-primary font-semibold shadow-xs"
                          : "bg-surface/80 border-outline-variant/20 hover:border-outline-variant/40 text-on-surface"
                      }`}
                    >
                      <span>
                        {opt.value} — {opt.label}
                      </span>
                      {isSelected && (
                        <span className="material-symbols-outlined text-primary text-sm shrink-0" aria-hidden="true">
                          check
                        </span>
                      )}
                    </button>
                  );
                })}
              </div>

              {!isAnswered && (
                <p className="text-[11px] text-amber-600 dark:text-amber-400 mt-2 flex items-center gap-1 font-medium">
                  <span className="material-symbols-outlined text-xs" aria-hidden="true">
                    priority_high
                  </span>
                  <span>Answer required before advancing</span>
                </p>
              )}
            </div>
          );
        })}
      </div>

      {validationError && (
        <div className="p-3.5 rounded-xl bg-error/10 border border-error/25 text-error text-xs flex items-center gap-2" role="alert">
          <span className="material-symbols-outlined text-base shrink-0" aria-hidden="true">
            warning
          </span>
          <span>{validationError}</span>
        </div>
      )}

      {/* Bottom controls */}
      <div className="pt-4 border-t border-outline-variant/20 flex flex-col sm:flex-row items-center justify-between gap-3">
        <button
          type="button"
          onClick={onBackToCard}
          className="w-full sm:w-auto px-5 py-2.5 rounded-full border border-outline-variant/40 text-on-surface-variant hover:text-on-surface hover:bg-surface-variant/30 text-xs font-medium transition-colors flex items-center justify-center gap-1.5 cursor-pointer"
        >
          <span className="material-symbols-outlined text-sm" aria-hidden="true">
            arrow_back
          </span>
          <span>Back to Question Card</span>
        </button>

        <button
          type="button"
          onClick={onProceedToFollowUp}
          disabled={!allAnswered}
          className="w-full sm:w-auto px-7 py-3 rounded-full bg-primary hover:bg-primary/90 text-on-primary font-medium text-xs sm:text-sm transition-all shadow-md hover:shadow-lg disabled:opacity-40 disabled:pointer-events-none flex items-center justify-center gap-2 cursor-pointer focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2"
        >
          <span>Continue to Contextual Follow-Up</span>
          <span className="material-symbols-outlined text-sm" aria-hidden="true">
            arrow_forward
          </span>
        </button>
      </div>
    </div>
  );
}
