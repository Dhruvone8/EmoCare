"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { useAuth } from "@/context/AuthContext";
import { startSession, sendChatMessage, endSession } from "@/lib/api";
import type {
  ChatMessageResponse,
  ToolInvocation,
  StartSessionResponse,
} from "@/types/api";

/* ── Types ─────────────────────────────────────────────────────────── */
interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  timestamp: Date;
  riskTier?: "Low" | "Moderate" | "High";
  crisisActivated?: boolean;
  toolsUsed?: ToolInvocation[];
}

/* ── Page Component ────────────────────────────────────────────────── */
export default function ChatTherapyPage() {
  const { user, openAuthModal } = useAuth();

  /* Session state */
  const [sessionId, setSessionId] = useState<number | null>(null);
  const [sessionStarting, setSessionStarting] = useState(false);
  const [sessionEnding, setSessionEnding] = useState(false);
  const [priorContext, setPriorContext] = useState<StartSessionResponse["prior_summaries"]>([]);
  const [currentStageLabel, setCurrentStageLabel] = useState<string>("Opening Check-in");

  /* Chat state */
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  /* Summary state */
  const [summary, setSummary] = useState<{
    summary_text: string;
    concerns: string[];
    goals: string[];
    techniques_used: string[];
    key_insights?: string[];
    action_steps?: string[];
  } | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const isSendingRef = useRef(false);

  const [guestId] = useState<string>(() => {
    if (typeof window !== "undefined") {
      let gid = localStorage.getItem("emocare_guest_id");
      if (!gid) {
        gid = "guest_" + Math.random().toString(36).substring(2, 10);
        localStorage.setItem("emocare_guest_id", gid);
      }
      return gid;
    }
    return "guest_client";
  });

  const userId = user?.id || guestId || "guest_client";

  /* ── Auto-scroll ──────────────────────────────────────────────── */
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  /* ── Start Session ────────────────────────────────────────────── */
  const handleStartSession = useCallback(async () => {
    setSessionStarting(true);
    setError(null);
    setSummary(null);
    try {
      const res = await startSession({
        user_id: userId,
        mode: "chat",
      });
      setSessionId(res.session_id);
      setPriorContext(res.prior_summaries);
      if (res.stage_label) {
        setCurrentStageLabel(res.stage_label);
      }
      const welcome =
        res.welcome_message ||
        "Hi, it's good to have you here. What's been on your mind lately? We can take our time with whatever feels important to you today.";
      setMessages([
        {
          id: "welcome",
          role: "assistant",
          content: welcome,
          timestamp: new Date(),
        },
      ]);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to start session."
      );
    } finally {
      setSessionStarting(false);
    }
  }, [userId]);

  /* ── Send Message ─────────────────────────────────────────────── */
  const handleSend = async () => {
    if (!input.trim() || !sessionId || sending || isSendingRef.current) return;

    isSendingRef.current = true;
    const userMessage: ChatMessage = {
      id: `user-${Date.now()}`,
      role: "user",
      content: input.trim(),
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setSending(true);
    setError(null);

    try {
      const res: ChatMessageResponse = await sendChatMessage({
        session_id: sessionId,
        user_id: userId,
        message: userMessage.content,
      });

      if (res.stage_label) {
        setCurrentStageLabel(res.stage_label);
      }

      const assistantMessage: ChatMessage = {
        id: `assistant-${Date.now()}`,
        role: "assistant",
        content: res.reply,
        timestamp: new Date(),
        riskTier: res.risk_tier,
        crisisActivated: res.crisis_activated,
        toolsUsed: res.tools_used,
      };

      setMessages((prev) => [...prev, assistantMessage]);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to send message."
      );
    } finally {
      setSending(false);
      isSendingRef.current = false;
      inputRef.current?.focus();
    }
  };

  /* ── End Session ──────────────────────────────────────────────── */
  const handleEndSession = async () => {
    if (!sessionId) return;
    setSessionEnding(true);
    try {
      const res = await endSession({
        session_id: sessionId,
        user_id: userId,
      });
      setSummary(res);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to end session."
      );
    } finally {
      setSessionEnding(false);
    }
  };

  /* ── Reset ────────────────────────────────────────────────────── */
  const handleNewSession = () => {
    setSessionId(null);
    setMessages([]);
    setSummary(null);
    setPriorContext([]);
    setError(null);
  };

  /* ── Key handler ──────────────────────────────────────────────── */
  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="max-w-4xl mx-auto flex flex-col h-[calc(100vh-200px)] min-h-[500px]">
      {/* ── Header ─────────────────────────────────────────────── */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="font-sans text-[28px] md:text-[36px] font-semibold text-on-surface tracking-tight leading-tight flex items-center gap-3">
            <span
              className="material-symbols-outlined text-primary text-3xl"
              style={{ fontVariationSettings: "'FILL' 1" }}
            >
              forum
            </span>
            <span>Chat Therapy</span>
          </h1>
          <p className="font-sans text-[15px] text-on-surface-variant mt-1">
            Guided conversation with evidence-based CBT techniques
          </p>
        </div>

        {sessionId && !summary && (
          <div className="flex items-center gap-2.5">
            {currentStageLabel && (
              <span className="tool-badge text-xs font-medium text-primary px-3 py-1.5 flex items-center gap-1.5">
                <span className="w-1.5 h-1.5 rounded-full bg-primary animate-pulse" />
                {currentStageLabel}
              </span>
            )}
            <button
              onClick={handleEndSession}
              disabled={sessionEnding}
              className="px-4 py-2 text-xs font-medium rounded-full border border-outline-variant/30 text-on-surface-variant hover:text-error hover:border-error/30 hover:bg-error/5 transition-all cursor-pointer"
            >
              {sessionEnding ? "Ending..." : "End Session"}
            </button>
          </div>
        )}
      </div>

      {/* ── Pre-session: Start ──────────────────────────────────── */}
      {!sessionId && !summary && (
        <div className="flex-1 flex items-center justify-center">
          <div className="glass-panel-elevated rounded-2xl p-8 md:p-12 max-w-lg text-center flex flex-col items-center gap-6 animate-sanctuary-in">
            <div className="w-20 h-20 rounded-full bg-primary/10 flex items-center justify-center">
              <span
                className="material-symbols-outlined text-primary text-4xl"
                style={{ fontVariationSettings: "'FILL' 1" }}
              >
                self_improvement
              </span>
            </div>
            <div>
              <h2 className="text-xl font-semibold text-on-surface mb-2">
                Begin Your Session
              </h2>
              <p className="text-sm text-on-surface-variant leading-relaxed max-w-sm">
                Start a guided therapy conversation. I&apos;ll use evidence-based CBT
                techniques — thought reframing, grounding exercises, and
                behavioral activation — to support you.
              </p>
            </div>

            {/* Prior context indicator */}
            {priorContext.length > 0 && (
              <div className="tool-badge text-xs text-on-surface-variant flex items-center gap-2">
                <span className="material-symbols-outlined text-sm text-primary">
                  history
                </span>
                <span>
                  {priorContext.length} previous session{priorContext.length > 1 ? "s" : ""} available for continuity
                </span>
              </div>
            )}

            {!user && (
              <p className="text-xs text-on-surface-variant">
                <button
                  onClick={() => openAuthModal("login")}
                  className="text-primary font-medium hover:underline"
                >
                  Sign in
                </button>{" "}
                to save session history across visits.
              </p>
            )}

            <button
              onClick={handleStartSession}
              disabled={sessionStarting}
              className="btn-sanctuary px-8 py-3.5 rounded-full text-sm font-medium flex items-center gap-2 cursor-pointer disabled:opacity-50"
            >
              {sessionStarting ? (
                <>
                  <div className="w-4 h-4 rounded-full border-2 border-on-primary border-t-transparent animate-spin" />
                  <span>Starting session...</span>
                </>
              ) : (
                <>
                  <span>Start Session</span>
                  <span className="material-symbols-outlined text-sm">
                    arrow_forward
                  </span>
                </>
              )}
            </button>
          </div>
        </div>
      )}

      {/* ── Active Chat ────────────────────────────────────────── */}
      {sessionId && !summary && (
        <>
          {/* Messages area */}
          <div className="flex-1 overflow-y-auto rounded-2xl glass-panel p-4 md:p-6 flex flex-col gap-3 mb-4">
            {messages.map((msg) => (
              <MessageBubble key={msg.id} message={msg} />
            ))}

            {/* Typing indicator */}
            {sending && (
              <div className="flex items-start gap-3 animate-sanctuary-in">
                <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center shrink-0">
                  <span className="material-symbols-outlined text-primary text-sm">
                    psychology
                  </span>
                </div>
                <div className="chat-bubble-assistant px-4 py-3 flex items-center gap-1.5">
                  <div className="typing-dot w-2 h-2 rounded-full bg-primary/50" />
                  <div className="typing-dot w-2 h-2 rounded-full bg-primary/50" />
                  <div className="typing-dot w-2 h-2 rounded-full bg-primary/50" />
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {/* Error */}
          {error && (
            <div className="p-3 rounded-xl bg-error/10 border border-error/20 text-error text-sm mb-3">
              {error}
            </div>
          )}

          {/* Input area */}
          <div className="glass-panel-elevated rounded-2xl p-3 flex items-end gap-3">
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Type your message... (Shift+Enter for new line)"
              rows={1}
              className="flex-1 bg-transparent resize-none border-none outline-none font-sans text-[15px] text-on-surface placeholder:text-outline/40 leading-6 py-2 px-2 max-h-32 overflow-y-auto"
              style={{ minHeight: "40px" }}
            />
            <button
              onClick={handleSend}
              disabled={!input.trim() || sending}
              className="w-10 h-10 rounded-full bg-primary text-on-primary flex items-center justify-center hover:bg-primary/90 disabled:opacity-30 transition-all shrink-0 cursor-pointer"
            >
              <span className="material-symbols-outlined text-lg">send</span>
            </button>
          </div>
        </>
      )}

      {/* ── Session Summary ────────────────────────────────────── */}
      {summary && (
        <div className="flex-1 flex items-center justify-center">
          <div className="glass-panel-elevated rounded-2xl p-8 max-w-lg w-full flex flex-col gap-5 animate-sanctuary-in">
            <div className="text-center">
              <div className="w-16 h-16 rounded-full bg-primary/10 flex items-center justify-center mx-auto mb-3">
                <span className="material-symbols-outlined text-primary text-3xl">
                  check_circle
                </span>
              </div>
              <h2 className="text-xl font-semibold text-on-surface mb-1">
                Session Complete
              </h2>
              <p className="text-sm text-on-surface-variant">
                Here&apos;s a summary of our conversation.
              </p>
            </div>

            <div className="p-4 rounded-xl bg-surface-variant/20 border border-outline-variant/15 text-sm text-on-surface leading-relaxed">
              {summary.summary_text}
            </div>

            {summary.techniques_used.length > 0 && (
              <div className="flex flex-col gap-2">
                <span className="text-xs font-medium uppercase tracking-wider text-on-surface-variant">
                  Techniques Used
                </span>
                <div className="flex flex-wrap gap-2">
                  {summary.techniques_used.map((t, i) => (
                    <span
                      key={i}
                      className="tool-badge text-xs font-medium text-primary px-3 py-1"
                    >
                      {t}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {summary.key_insights && summary.key_insights.length > 0 && (
              <div className="flex flex-col gap-2">
                <span className="text-xs font-medium uppercase tracking-wider text-on-surface-variant">
                  Key Insights
                </span>
                {summary.key_insights.map((insight, i) => (
                  <div
                    key={i}
                    className="flex items-start gap-2 text-sm text-on-surface"
                  >
                    <span className="material-symbols-outlined text-primary text-sm mt-0.5">
                      lightbulb
                    </span>
                    <span>{insight}</span>
                  </div>
                ))}
              </div>
            )}

            {summary.action_steps && summary.action_steps.length > 0 && (
              <div className="flex flex-col gap-2">
                <span className="text-xs font-medium uppercase tracking-wider text-on-surface-variant">
                  Action Steps
                </span>
                {summary.action_steps.map((step, i) => (
                  <div
                    key={i}
                    className="flex items-start gap-2 text-sm text-on-surface"
                  >
                    <span className="material-symbols-outlined text-primary text-sm mt-0.5">
                      check_circle_outline
                    </span>
                    <span>{step}</span>
                  </div>
                ))}
              </div>
            )}

            {summary.goals.length > 0 && (
              <div className="flex flex-col gap-2">
                <span className="text-xs font-medium uppercase tracking-wider text-on-surface-variant">
                  Goals Identified
                </span>
                {summary.goals.map((g, i) => (
                  <div
                    key={i}
                    className="flex items-start gap-2 text-sm text-on-surface"
                  >
                    <span className="material-symbols-outlined text-primary text-sm mt-0.5">
                      flag
                    </span>
                    <span>{g}</span>
                  </div>
                ))}
              </div>
            )}

            <button
              onClick={handleNewSession}
              className="btn-sanctuary px-6 py-3 rounded-full text-sm font-medium cursor-pointer mx-auto mt-2"
            >
              Start New Session
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════════
   MESSAGE BUBBLE COMPONENT
   ═══════════════════════════════════════════════════════════════════════ */

function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";

  return (
    <div
      className={`flex items-start gap-3 animate-sanctuary-in ${
        isUser ? "flex-row-reverse" : ""
      }`}
    >
      {/* Avatar */}
      <div
        className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 ${
          isUser
            ? "bg-primary text-on-primary"
            : "bg-primary/10 text-primary"
        }`}
      >
        <span className="material-symbols-outlined text-sm">
          {isUser ? "person" : "psychology"}
        </span>
      </div>

      {/* Bubble */}
      <div className="max-w-[80%] flex flex-col gap-1.5">
        <div
          className={`px-4 py-3 text-[14.5px] leading-relaxed ${
            isUser ? "chat-bubble-user" : "chat-bubble-assistant"
          }`}
        >
          {/* Render message content with line breaks */}
          {message.content.split("\n").map((line, i) => (
            <span key={i}>
              {line}
              {i < message.content.split("\n").length - 1 && <br />}
            </span>
          ))}
        </div>

        {/* Tools used badge */}
        {message.toolsUsed && message.toolsUsed.length > 0 && (
          <div className="flex flex-wrap gap-1.5 px-1">
            {message.toolsUsed.map((tool, i) => (
              <span
                key={i}
                className="tool-badge text-[11px] font-medium text-primary px-2 py-0.5 flex items-center gap-1"
              >
                <span className="material-symbols-outlined text-[12px]">
                  build
                </span>
                {tool.tool_name.replace(/_/g, " ")}
              </span>
            ))}
          </div>
        )}

        {/* Crisis indicator */}
        {message.crisisActivated && (
          <div className="crisis-banner px-3 py-2 text-[12px] text-on-surface flex items-center gap-2">
            <span className="material-symbols-outlined text-sm text-risk-high">
              emergency
            </span>
            <span>Crisis support resources provided</span>
          </div>
        )}

        {/* Timestamp */}
        <span
          className={`text-[11px] text-on-surface-variant/50 px-1 ${
            isUser ? "text-right" : ""
          }`}
        >
          {message.timestamp.toLocaleTimeString([], {
            hour: "2-digit",
            minute: "2-digit",
          })}
        </span>
      </div>
    </div>
  );
}
