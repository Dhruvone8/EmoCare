"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import { DailyCheckInForm } from "@/components/DailyCheckInForm";
import { useAuth } from "@/context/AuthContext";
import { getLocalDateKey, getTodayCheckIn } from "@/lib/api";
import type { DailyCheckIn } from "@/types/api";

interface DailyCheckInModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSaved: (checkIn: DailyCheckIn) => void;
}

function DailyCheckInModal({
  isOpen,
  onClose,
  onSaved,
}: DailyCheckInModalProps) {
  useEffect(() => {
    if (!isOpen) return;

    const previousOverflow = document.body.style.overflow;
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    document.body.style.overflow = "hidden";
    window.addEventListener("keydown", handleKeyDown);

    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-navy/70 backdrop-blur-md p-3 sm:p-6 animate-sanctuary-in"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-labelledby="daily-checkin-title"
      aria-describedby="daily-checkin-description"
    >
      <div
        className="w-full max-w-2xl max-h-[92dvh] overflow-y-auto glass-panel-elevated rounded-2xl sm:rounded-3xl border border-outline-variant/20 shadow-2xl bg-surface-container-lowest text-on-surface p-4 sm:p-6"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-4 mb-5">
          <div className="flex items-start gap-3">
            <div className="w-10 h-10 rounded-full bg-primary/10 text-primary flex items-center justify-center shrink-0">
              <span className="material-symbols-outlined text-2xl">partly_cloudy_day</span>
            </div>
            <div>
              <h2 id="daily-checkin-title" className="font-sans text-xl sm:text-2xl font-semibold tracking-tight">
                How are you today?
              </h2>
              <p id="daily-checkin-description" className="font-sans text-sm text-on-surface-variant mt-1 leading-relaxed">
                A quick check-in helps personalize your wellbeing support.
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="w-9 h-9 rounded-full bg-surface-variant/40 hover:bg-surface-variant text-on-surface-variant hover:text-on-surface flex items-center justify-center transition-colors shrink-0"
            aria-label="Close daily check-in"
          >
            <span className="material-symbols-outlined text-xl">close</span>
          </button>
        </div>

        <DailyCheckInForm variant="modal" onSaved={onSaved} />

        <button
          type="button"
          onClick={onClose}
          className="w-full mt-3 py-2 font-sans text-sm text-on-surface-variant hover:text-on-surface transition-colors"
        >
          Maybe later
        </button>
      </div>
    </div>
  );
}

export function DailyCheckInGate() {
  const { user, loading, isAuthModalOpen } = useAuth();
  const userId = user?.id;
  const currentKey = userId ? `${userId}:${getLocalDateKey()}` : null;
  const [openForKey, setOpenForKey] = useState<string | null>(null);
  const activeKey = useRef<string | null>(null);
  const dismissedKey = useRef<string | null>(null);

  useEffect(() => {
    if (!userId) {
      activeKey.current = null;
      dismissedKey.current = null;
      return;
    }
    if (loading || isAuthModalOpen) return;

    let cancelled = false;
    const localDate = getLocalDateKey();
    const requestKey = `${userId}:${localDate}`;
    activeKey.current = requestKey;

    const checkToday = async () => {
      try {
        const status = await getTodayCheckIn(localDate);
        if (!cancelled) {
          setOpenForKey(
            !status.completed && dismissedKey.current !== requestKey
              ? requestKey
              : null
          );
        }
      } catch {
        if (!cancelled) setOpenForKey(null);
      }
    };

    void checkToday();
    return () => {
      cancelled = true;
    };
  }, [loading, userId, isAuthModalOpen]);

  const close = useCallback(() => {
    dismissedKey.current = activeKey.current;
    setOpenForKey(null);
  }, []);

  const saved = useCallback(() => {
    dismissedKey.current = activeKey.current;
    setOpenForKey(null);
  }, []);

  return (
    <DailyCheckInModal
      isOpen={!loading && !isAuthModalOpen && openForKey === currentKey && currentKey !== null}
      onClose={close}
      onSaved={saved}
    />
  );
}
