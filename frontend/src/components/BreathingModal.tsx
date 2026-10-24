"use client";

import React, { useState, useEffect } from "react";

/* ═══════════════════════════════════════════════════════════════════════
   CONFIGURABLE GUIDED BREATHING / YOGA VIDEO CONFIGURATION
   
   To replace the video with your preferred breathing or yoga video:
   1. YouTube URL or ID: Set `videoUrl` to any YouTube link, e.g.:
        "https://www.youtube.com/watch?v=199N27rP40c" (4-7-8 Breathing)
        "https://www.youtube.com/watch?v=Y4Z7Yq1j-aE" (Box Breathing)
        "https://www.youtube.com/watch?v=kU1R30t-z1k" (SOMA Yoga Breathwork)
   2. Direct Video File: Set `videoUrl` to any MP4 or WebM URL or local path:
        "/videos/my-breathing-exercise.mp4" (place in frontend/public/videos/)
        "https://cdn.example.com/breathing-yoga.mp4"
   ═══════════════════════════════════════════════════════════════════════ */

export interface BreathingVideoPreset {
  id: string;
  name: string;
  description: string;
  badge: string;
  videoUrl: string;
}

export const BREATHING_VIDEO_PRESETS: BreathingVideoPreset[] = [
  {
    id: "478-relax",
    name: "4-7-8 Calming Breathwork",
    description: "Inhale 4s • Hold 7s • Exhale 8s to calm the vagus nerve and release tension.",
    badge: "Most Relaxing",
    videoUrl: "https://www.youtube.com/watch?v=199N27rP40c",
  },
  {
    id: "box-breathing",
    name: "Box Breathing (Sama Vritti)",
    description: "Equal 4-4-4-4 counts used to restore mental clarity, focus, and emotional calm.",
    badge: "Focus & Balance",
    videoUrl: "https://www.youtube.com/watch?v=Y4Z7Yq1j-aE",
  },
  {
    id: "yoga-pranayama",
    name: "Deep Yoga Breathwork",
    description: "Gentle diaphragmatic pranayama to release somatic stress and center your body.",
    badge: "Somatic Grounding",
    videoUrl: "https://www.youtube.com/watch?v=kU1R30t-z1k",
  },
];

// Default primary video selected when user clicks Begin
export const DEFAULT_BREATHING_VIDEO_URL = BREATHING_VIDEO_PRESETS[0].videoUrl;

/* ── Helper: Extract YouTube Embed URL or detect Direct Video ───────── */
function getEmbedInfo(url: string): { isYouTube: boolean; embedUrl?: string; directUrl?: string } {
  const trimmed = url.trim();

  // YouTube detection
  const regExp = /(?:youtube\.com\/(?:[^\/]+\/.+\/|(?:v|e(?:mbed)?)\/|.*[?&]v=)|youtu\.be\/)([^"&?\/\s]{11})/i;
  const match = trimmed.match(regExp);

  if (match && match[1]) {
    return {
      isYouTube: true,
      embedUrl: `https://www.youtube-nocookie.com/embed/${match[1]}?autoplay=1&rel=0&modestbranding=1&playsinline=1`,
    };
  }

  // Raw 11-char YouTube ID fallback
  if (/^[a-zA-Z0-9_-]{11}$/.test(trimmed)) {
    return {
      isYouTube: true,
      embedUrl: `https://www.youtube-nocookie.com/embed/${trimmed}?autoplay=1&rel=0&modestbranding=1&playsinline=1`,
    };
  }

  // Direct MP4 / WebM / local video file
  return {
    isYouTube: false,
    directUrl: trimmed,
  };
}

interface BreathingModalProps {
  isOpen: boolean;
  onClose: () => void;
  initialVideoUrl?: string;
}

export function BreathingModal({
  isOpen,
  onClose,
  initialVideoUrl = DEFAULT_BREATHING_VIDEO_URL,
}: BreathingModalProps) {
  const [activeVideoUrl, setActiveVideoUrl] = useState(initialVideoUrl);
  const [activePresetId, setActivePresetId] = useState(BREATHING_VIDEO_PRESETS[0].id);

  // Close on Escape key press
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    if (isOpen) {
      window.addEventListener("keydown", handleKeyDown);
      document.body.style.overflow = "hidden";
    }
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
      document.body.style.overflow = "unset";
    };
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const embedInfo = getEmbedInfo(activeVideoUrl);
  const activePreset = BREATHING_VIDEO_PRESETS.find((p) => p.id === activePresetId) || BREATHING_VIDEO_PRESETS[0];

  const handleSelectPreset = (preset: BreathingVideoPreset) => {
    setActivePresetId(preset.id);
    setActiveVideoUrl(preset.videoUrl);
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-navy/70 backdrop-blur-md p-3 sm:p-6 animate-sanctuary-in"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-labelledby="breathing-exercise-title"
    >
      <div
        className="relative w-full max-w-4xl glass-panel-elevated rounded-2xl sm:rounded-3xl border border-outline-variant/20 shadow-2xl bg-surface-container-lowest text-on-surface overflow-hidden flex flex-col max-h-[92vh]"
        onClick={(e) => e.stopPropagation()}
      >
        {/* ── Modal Header ────────────────────────────────────────── */}
        <div className="flex items-center justify-between p-4 sm:p-5 border-b border-outline-variant/15 shrink-0 bg-surface/50">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-primary/10 text-primary flex items-center justify-center shrink-0">
              <span
                className="material-symbols-outlined text-2xl"
                style={{ fontVariationSettings: "'FILL' 1" }}
              >
                self_improvement
              </span>
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 id="breathing-exercise-title" className="font-sans text-lg sm:text-xl font-bold text-on-surface">
                  Guided Breathing Sanctuary
                </h2>
                <span className="hidden sm:inline-block px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-primary/10 text-primary border border-primary/20">
                  {activePreset.badge}
                </span>
              </div>
              <p className="font-sans text-xs text-on-surface-variant line-clamp-1 mt-0.5">
                {activePreset.description}
              </p>
            </div>
          </div>

          {/* Close Button */}
          <button
            onClick={onClose}
            className="w-9 h-9 rounded-full bg-surface-variant/40 hover:bg-surface-variant text-on-surface-variant hover:text-on-surface flex items-center justify-center transition-colors cursor-pointer shrink-0 ml-2"
            aria-label="Close breathing exercise"
          >
            <span className="material-symbols-outlined text-xl">close</span>
          </button>
        </div>

        {/* ── Preset Tabs (Desktop & Mobile) ──────────────────────── */}
        <div className="flex items-center gap-2 px-4 py-2.5 border-b border-outline-variant/10 bg-surface-container-low/40 overflow-x-auto shrink-0 scrollbar-none">
          <span className="text-xs text-on-surface-variant font-medium shrink-0 mr-1 flex items-center gap-1">
            <span className="material-symbols-outlined text-sm text-primary">tune</span>
            <span>Technique:</span>
          </span>
          {BREATHING_VIDEO_PRESETS.map((preset) => {
            const isSelected = activePresetId === preset.id;
            return (
              <button
                key={preset.id}
                onClick={() => handleSelectPreset(preset)}
                className={`px-3 py-1.5 rounded-full text-xs font-medium whitespace-nowrap transition-all duration-200 cursor-pointer flex items-center gap-1.5 shrink-0 ${
                  isSelected
                    ? "bg-primary text-on-primary shadow-xs"
                    : "bg-surface-container/60 text-on-surface-variant hover:bg-surface-container hover:text-on-surface border border-outline-variant/15"
                }`}
              >
                <span>{preset.name}</span>
              </button>
            );
          })}
        </div>

        {/* ── Video Player Stage ──────────────────────────────────── */}
        <div className="relative w-full aspect-video bg-black flex items-center justify-center overflow-hidden">
          {embedInfo.isYouTube && embedInfo.embedUrl ? (
            <iframe
              src={embedInfo.embedUrl}
              title={activePreset.name}
              allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
              allowFullScreen
              className="w-full h-full border-0"
            />
          ) : embedInfo.directUrl ? (
            <video
              src={embedInfo.directUrl}
              controls
              autoPlay
              playsInline
              loop
              className="w-full h-full object-contain"
            >
              Your browser does not support the video tag.
            </video>
          ) : (
            <div className="text-white text-sm">Video source not found.</div>
          )}
        </div>

        {/* ── Footer Guidance & Actions ───────────────────────────── */}
        <div className="p-4 sm:p-5 flex flex-col sm:flex-row items-center justify-between gap-3 bg-surface/40 border-t border-outline-variant/15 shrink-0">
          <div className="flex items-center gap-3 text-xs text-on-surface-variant text-center sm:text-left">
            <span className="material-symbols-outlined text-primary text-xl hidden sm:inline-block">
              air
            </span>
            <span>
              Follow the rhythmic breath prompts on screen. Let your shoulders drop, relax your jaw, and breathe deeply.
            </span>
          </div>

          <button
            onClick={onClose}
            className="w-full sm:w-auto px-6 py-2.5 rounded-full bg-primary hover:bg-primary/90 text-on-primary font-semibold text-xs transition-all duration-200 shadow-sm hover:shadow-md cursor-pointer shrink-0 flex items-center justify-center gap-1.5"
          >
            <span>Done with Exercise</span>
            <span className="material-symbols-outlined text-sm">check</span>
          </button>
        </div>
      </div>
    </div>
  );
}
