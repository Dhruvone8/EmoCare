"use client";

import React, { useState } from "react";

export interface SafetyDisclosureData {
  active_thoughts: boolean;
  immediate_intent: boolean;
  safe_person_nearby: boolean;
  notes?: string;
}

interface SafetyModalProps {
  isOpen: boolean;
  onProceed: (disclosure: SafetyDisclosureData) => void;
  onCancel: () => void;
}

export function SafetyModal({ isOpen, onProceed, onCancel }: SafetyModalProps) {
  const [activeThoughts, setActiveThoughts] = useState<boolean | null>(null);
  const [immediateIntent, setImmediateIntent] = useState<boolean | null>(null);
  const [safePersonNearby, setSafePersonNearby] = useState<boolean | null>(null);
  const [validationError, setValidationError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleContinue = () => {
    if (activeThoughts === null || immediateIntent === null) {
      setValidationError("Please answer the two brief safety check questions below so we can offer appropriate support.");
      return;
    }
    setValidationError(null);
    onProceed({
      active_thoughts: activeThoughts,
      immediate_intent: immediateIntent,
      safe_person_nearby: safePersonNearby ?? false,
    });
  };

  const isImminentDanger = activeThoughts === true || immediateIntent === true;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="safety-modal-title"
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-md overflow-y-auto animate-in fade-in duration-200"
    >
      <div className="relative w-full max-w-2xl bg-surface rounded-3xl border border-rose-500/30 p-6 sm:p-8 md:p-10 shadow-2xl flex flex-col gap-6 text-on-surface my-8">
        {/* Header */}
        <div className="flex items-start gap-4">
          <div className="p-3 rounded-2xl bg-rose-500/15 text-rose-600 dark:text-rose-400 border border-rose-500/30 shrink-0">
            <span className="material-symbols-outlined text-3xl" aria-hidden="true">
              favorite
            </span>
          </div>
          <div>
            <h2 id="safety-modal-title" className="text-xl sm:text-2xl font-bold tracking-tight text-on-surface">
              We Care About Your Safety
            </h2>
            <p className="text-sm text-on-surface-variant mt-1 leading-relaxed">
              You indicated experiencing thoughts of being better off dead or hurting yourself. We take this very seriously, and we want to ensure you have immediate access to safe, compassionate support.
            </p>
          </div>
        </div>

        {/* Verified Crisis Resources Box */}
        <div className="p-5 rounded-2xl bg-rose-500/10 border border-rose-500/25 flex flex-col gap-3">
          <div className="flex items-center gap-2 text-rose-700 dark:text-rose-300 font-semibold text-sm">
            <span className="material-symbols-outlined text-lg" aria-hidden="true">
              support_agent
            </span>
            <span>Free, Confidential 24/7 Crisis Helplines</span>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 text-xs text-on-surface-variant">
            <div className="p-2.5 rounded-xl bg-surface/70 border border-outline-variant/20 flex flex-col">
              <strong className="text-on-surface">US & Canada (Lifeline)</strong>
              <span>Call or Text <strong>988</strong></span>
              <span className="text-[11px] opacity-75">Toll-free, 24/7, confidential</span>
            </div>
            <div className="p-2.5 rounded-xl bg-surface/70 border border-outline-variant/20 flex flex-col">
              <strong className="text-on-surface">Crisis Text Line (Global)</strong>
              <span>Text <strong>HOME</strong> to <strong>741741</strong></span>
              <span className="text-[11px] opacity-75">Free crisis text support</span>
            </div>
            <div className="p-2.5 rounded-xl bg-surface/70 border border-outline-variant/20 flex flex-col">
              <strong className="text-on-surface">India (Tele-MANAS & iCall)</strong>
              <span>Call <strong>14416</strong> or <strong>9152987821</strong></span>
              <span className="text-[11px] opacity-75">National mental health helplines</span>
            </div>
            <div className="p-2.5 rounded-xl bg-surface/70 border border-outline-variant/20 flex flex-col">
              <strong className="text-on-surface">Immediate Emergency Services</strong>
              <span>Dial <strong>112</strong> / <strong>911</strong> / <strong>999</strong></span>
              <span className="text-[11px] opacity-75">Or go to nearest emergency room</span>
            </div>
          </div>
          <p className="text-[11px] text-on-surface-variant/80 italic">
            Notice: EmoCare is an automated software application and <strong>does not provide live human monitoring</strong>. If you are in immediate danger, please reach out to emergency responders directly.
          </p>
        </div>

        {/* Structured Safety Clarification */}
        <div className="space-y-4 pt-2 border-t border-outline-variant/20">
          <h3 className="text-sm font-semibold text-on-surface">
            Help us understand your current situation:
          </h3>

          {/* Question A: Active thoughts */}
          <div className="space-y-2">
            <label className="text-xs sm:text-sm font-medium text-on-surface block">
              1. Are you experiencing active thoughts of ending your life right now?
            </label>
            <div className="grid grid-cols-2 gap-3" role="radiogroup" aria-label="Active thoughts">
              <button
                type="button"
                onClick={() => setActiveThoughts(false)}
                className={`p-3 rounded-xl border text-xs sm:text-sm font-medium transition-all text-left ${
                  activeThoughts === false
                    ? "bg-primary/15 border-primary text-primary"
                    : "bg-surface-variant/20 border-outline-variant/20 hover:border-outline-variant/40"
                }`}
              >
                No — these are passive or occasional thoughts
              </button>
              <button
                type="button"
                onClick={() => setActiveThoughts(true)}
                className={`p-3 rounded-xl border text-xs sm:text-sm font-medium transition-all text-left ${
                  activeThoughts === true
                    ? "bg-rose-500/20 border-rose-500 text-rose-600 dark:text-rose-400 font-semibold"
                    : "bg-surface-variant/20 border-outline-variant/20 hover:border-outline-variant/40"
                }`}
              >
                Yes — I am having active thoughts right now
              </button>
            </div>
          </div>

          {/* Question B: Immediate plan */}
          <div className="space-y-2">
            <label className="text-xs sm:text-sm font-medium text-on-surface block">
              2. Do you have an immediate plan or intent to harm yourself?
            </label>
            <div className="grid grid-cols-2 gap-3" role="radiogroup" aria-label="Immediate plan">
              <button
                type="button"
                onClick={() => setImmediateIntent(false)}
                className={`p-3 rounded-xl border text-xs sm:text-sm font-medium transition-all text-left ${
                  immediateIntent === false
                    ? "bg-primary/15 border-primary text-primary"
                    : "bg-surface-variant/20 border-outline-variant/20 hover:border-outline-variant/40"
                }`}
              >
                No — I do not have a plan or intent
              </button>
              <button
                type="button"
                onClick={() => setImmediateIntent(true)}
                className={`p-3 rounded-xl border text-xs sm:text-sm font-medium transition-all text-left ${
                  immediateIntent === true
                    ? "bg-rose-500/20 border-rose-500 text-rose-600 dark:text-rose-400 font-semibold"
                    : "bg-surface-variant/20 border-outline-variant/20 hover:border-outline-variant/40"
                }`}
              >
                Yes — I have a plan or intent
              </button>
            </div>
          </div>

          {/* Question C: Safe person nearby */}
          <div className="space-y-2">
            <label className="text-xs sm:text-sm font-medium text-on-surface block">
              3. Is there a trusted friend, family member, or doctor you can reach out to right now?
            </label>
            <div className="grid grid-cols-2 gap-3" role="radiogroup" aria-label="Safe person nearby">
              <button
                type="button"
                onClick={() => setSafePersonNearby(true)}
                className={`p-2.5 rounded-xl border text-xs font-medium transition-all ${
                  safePersonNearby === true
                    ? "bg-primary/15 border-primary text-primary"
                    : "bg-surface-variant/20 border-outline-variant/20"
                }`}
              >
                Yes, I have support available
              </button>
              <button
                type="button"
                onClick={() => setSafePersonNearby(false)}
                className={`p-2.5 rounded-xl border text-xs font-medium transition-all ${
                  safePersonNearby === false
                    ? "bg-amber-500/15 border-amber-500 text-amber-700 dark:text-amber-400"
                    : "bg-surface-variant/20 border-outline-variant/20"
                }`}
              >
                No, I feel isolated right now
              </button>
            </div>
          </div>
        </div>

        {/* Warning if danger */}
        {isImminentDanger && (
          <div className="p-4 rounded-xl bg-rose-600 text-white font-medium text-xs leading-relaxed flex items-center gap-3">
            <span className="material-symbols-outlined text-2xl shrink-0" aria-hidden="true">
              crisis_alert
            </span>
            <span>
              Please step away from this screening and connect with a human crisis responder right now. Dial <strong>988</strong> or your local emergency number. Your life has immense value.
            </span>
          </div>
        )}

        {validationError && (
          <div className="p-3 rounded-xl bg-error/10 border border-error/20 text-error text-xs" role="alert">
            {validationError}
          </div>
        )}

        {/* Actions */}
        <div className="flex flex-col sm:flex-row items-center justify-between gap-3 pt-4 border-t border-outline-variant/20">
          <button
            type="button"
            onClick={onCancel}
            className="w-full sm:w-auto px-5 py-2.5 rounded-full border border-outline-variant/40 text-on-surface-variant text-xs font-medium hover:bg-surface-variant/40 transition-colors cursor-pointer"
          >
            ← Review & Change Answer
          </button>

          <button
            type="button"
            onClick={handleContinue}
            className={`w-full sm:w-auto px-7 py-3 rounded-full text-xs font-semibold transition-all shadow-md flex items-center justify-center gap-2 cursor-pointer ${
              isImminentDanger
                ? "bg-rose-600 hover:bg-rose-700 text-white"
                : "bg-primary hover:bg-primary/90 text-on-primary"
            }`}
          >
            <span>Acknowledge & Continue</span>
            <span className="material-symbols-outlined text-sm" aria-hidden="true">
              arrow_forward
            </span>
          </button>
        </div>
      </div>
    </div>
  );
}
