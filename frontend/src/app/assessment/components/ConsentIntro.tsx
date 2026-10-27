"use client";

import React from "react";
import type { User } from "@supabase/supabase-js";

interface ConsentIntroProps {
  user: User | null;
  onConsent: () => void;
  openAuthModal: (mode: "login" | "signup") => void;
}

export function ConsentIntro({ user, onConsent, openAuthModal }: ConsentIntroProps) {
  return (
    <div className="glass-panel rounded-2xl p-6 sm:p-8 md:p-10 border border-outline-variant/30 bg-surface/70 backdrop-blur-md flex flex-col gap-6 shadow-xl animate-in fade-in duration-200">
      <div className="flex items-start gap-4">
        <div className="p-3 rounded-2xl bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20 shrink-0">
          <span className="material-symbols-outlined text-2xl" aria-hidden="true">
            clinical_notes
          </span>
        </div>
        <div className="space-y-3">
          <h2 className="text-xl sm:text-2xl font-semibold text-on-surface tracking-tight">
            Before You Begin: Purpose & Clinical Boundaries
          </h2>
          <p className="text-sm text-on-surface-variant leading-relaxed">
            Standard self-screening instruments (PHQ-9 and GAD-7) offer structured insights into your
            emotional patterns over the past two weeks. Please take a moment to review how this tool works
            and how your data is protected:
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="p-4 rounded-xl bg-surface-variant/25 border border-outline-variant/20 flex flex-col gap-2">
          <div className="flex items-center gap-2 text-primary font-semibold text-sm">
            <span className="material-symbols-outlined text-base" aria-hidden="true">
              analytics
            </span>
            <span>Screening, Not Diagnosis</span>
          </div>
          <p className="text-xs text-on-surface-variant leading-relaxed">
            These questions quantify reported symptoms. They are <strong>not a medical diagnosis</strong>. Formal diagnosis requires evaluation by a licensed physician or mental health professional.
          </p>
        </div>

        <div className="p-4 rounded-xl bg-surface-variant/25 border border-outline-variant/20 flex flex-col gap-2">
          <div className="flex items-center gap-2 text-primary font-semibold text-sm">
            <span className="material-symbols-outlined text-base" aria-hidden="true">
              lock
            </span>
            <span>Privacy & Ownership</span>
          </div>
          <p className="text-xs text-on-surface-variant leading-relaxed">
            You may complete this screening as a guest or logged-in user. Responses are stored in your profile database to track your personal wellbeing trajectory over time.
          </p>
        </div>

        <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/20 flex flex-col gap-2">
          <div className="flex items-center gap-2 text-rose-600 dark:text-rose-400 font-semibold text-sm">
            <span className="material-symbols-outlined text-base" aria-hidden="true">
              emergency
            </span>
            <span>Immediate Crisis Support</span>
          </div>
          <p className="text-xs text-on-surface-variant leading-relaxed">
            EmoCare provides automated self-care guidance and <strong>does not provide live human crisis monitoring</strong>. If you feel unsafe or are having thoughts of suicide, please call or text <strong>988</strong> (US/Canada), <strong>112/911</strong> (Emergency), or <strong>14416</strong> (India).
          </p>
        </div>
      </div>

      <div className="pt-4 border-t border-outline-variant/20 flex flex-col sm:flex-row items-center justify-between gap-4">
        <div className="text-xs text-on-surface-variant text-center sm:text-left">
          {user ? (
            <span>
              Signed in as <strong className="text-on-surface">{user.email}</strong>. Results will be saved to your account.
            </span>
          ) : (
            <span>
              You are completing this as a guest.{" "}
              <button
                type="button"
                onClick={() => openAuthModal("login")}
                className="text-primary font-semibold hover:underline cursor-pointer"
              >
                Sign in
              </button>{" "}
              or{" "}
              <button
                type="button"
                onClick={() => openAuthModal("signup")}
                className="text-primary font-semibold hover:underline cursor-pointer"
              >
                create an account
              </button>{" "}
              to sync your history.
            </span>
          )}
        </div>

        <button
          type="button"
          onClick={onConsent}
          className="w-full sm:w-auto px-8 py-3 rounded-full bg-primary hover:bg-primary/90 text-on-primary font-medium text-sm transition-all shadow-md hover:shadow-lg flex items-center justify-center gap-2 cursor-pointer focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2"
        >
          <span>I Understand & Wish to Proceed</span>
          <span className="material-symbols-outlined text-base" aria-hidden="true">
            arrow_forward
          </span>
        </button>
      </div>
    </div>
  );
}
