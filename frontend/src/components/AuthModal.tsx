"use client";

import React, { useState } from "react";
import type { AuthError } from "@supabase/supabase-js";
import { useAuth } from "@/context/AuthContext";

function isRateLimitError(error: AuthError): boolean {
  return (
    error.code === "over_email_rate_limit" ||
    error.code === "over_request_rate_limit" ||
    error.status === 429 ||
    error.message.toLowerCase().includes("rate limit")
  );
}

function getAuthErrorMessage(error: AuthError): string {
  if (isRateLimitError(error)) {
    return "Supabase has temporarily rate-limited authentication requests. You can retry, but requests may continue to fail until Supabase resets its limit.";
  }
  if (error.code === "email_not_confirmed") {
    return "Please confirm your email using the most recent message, then sign in.";
  }
  return error.message;
}

export function AuthModal() {
  const {
    isAuthModalOpen,
    closeAuthModal,
    authModalMode,
    setAuthModalMode,
    signIn,
    signUp,
  } = useAuth();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [age, setAge] = useState("");
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  const changeMode = (mode: "login" | "signup") => {
    setAuthModalMode(mode);
    setErrorMsg(null);
    setSuccessMsg(null);
  };

  const handleAuthError = (error: AuthError) => {
    setErrorMsg(getAuthErrorMessage(error));
  };

  if (!isAuthModalOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (loading) return;
    setErrorMsg(null);
    setSuccessMsg(null);

    const parsedAge = Number(age);
    if (
      authModalMode === "signup" &&
      (!/^\d+$/.test(age) ||
        !Number.isInteger(parsedAge) ||
        parsedAge < 10 ||
        parsedAge > 120)
    ) {
      setErrorMsg("Age must be a whole number between 10 and 120.");
      return;
    }

    setLoading(true);
    try {
      if (authModalMode === "signup") {
        const { error } = await signUp(email, password, fullName, parsedAge);
        if (error) {
          handleAuthError(error);
        } else {
          setSuccessMsg("Account created! Check your email to confirm if required.");
        }
      } else {
        const { error } = await signIn(email, password);
        if (error) handleAuthError(error);
      }
    } catch {
      setErrorMsg("The authentication service could not be reached. Please try again later.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 animate-in fade-in duration-200">
      <div
        className="relative w-full max-w-md bg-surface border border-outline-variant/30 rounded-2xl p-6 shadow-2xl text-on-surface"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Close Button */}
        <button
          onClick={closeAuthModal}
          className="absolute top-4 right-4 text-on-surface-variant hover:text-on-surface p-1 rounded-full hover:bg-surface-variant/40 transition-colors"
          aria-label="Close modal"
        >
          <span className="material-symbols-outlined text-xl">close</span>
        </button>

        {/* Header */}
        <div className="text-center mb-6">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-full bg-primary/10 text-primary mb-3">
            <span className="material-symbols-outlined text-2xl">spa</span>
          </div>
          <h2 className="text-2xl font-semibold tracking-tight text-primary">
            {authModalMode === "login" ? "Welcome Back" : "Begin Your Journey"}
          </h2>
          <p className="text-sm text-on-surface-variant mt-1">
            {authModalMode === "login"
              ? "Sign in to track your personal wellbeing and assessment history"
              : "Create an account to save your emotional reflections securely"}
          </p>
        </div>

        {/* Tab Switcher */}
        <div className="flex border-b border-outline-variant/20 mb-6">
          <button
            type="button"
            onClick={() => {
              changeMode("login");
              setErrorMsg(null);
            }}
            className={`flex-1 pb-3 text-sm font-medium transition-colors relative ${
              authModalMode === "login"
                ? "text-primary border-b-2 border-primary"
                : "text-on-surface-variant hover:text-on-surface"
            }`}
          >
            Sign In
          </button>
          <button
            type="button"
            onClick={() => {
              changeMode("signup");
              setErrorMsg(null);
            }}
            className={`flex-1 pb-3 text-sm font-medium transition-colors relative ${
              authModalMode === "signup"
                ? "text-primary border-b-2 border-primary"
                : "text-on-surface-variant hover:text-on-surface"
            }`}
          >
            Create Account
          </button>
        </div>

        {/* Feedback alerts */}
        {errorMsg && (
          <div className="mb-4 p-3 rounded-lg bg-error/10 border border-error/20 text-error text-xs flex items-center gap-2">
            <span className="material-symbols-outlined text-base">error</span>
            <span>{errorMsg}</span>
          </div>
        )}

        {successMsg && (
          <div className="mb-4 p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-600 dark:text-emerald-400 text-xs flex items-center gap-2">
            <span className="material-symbols-outlined text-base">check_circle</span>
            <span>{successMsg}</span>
          </div>
        )}

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          {authModalMode === "signup" && (
            <>
              <div>
                <label className="block text-xs font-medium text-on-surface-variant mb-1">
                  Full Name
                </label>
                <input
                  type="text"
                  required
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  placeholder="e.g. Alex Rivera"
                  className="w-full px-3 py-2 text-sm rounded-lg bg-surface-variant/40 border border-outline-variant/30 focus:outline-none focus:ring-2 focus:ring-primary/50 text-on-surface placeholder:text-on-surface-variant/50"
                />
              </div>

              <div>
                <label
                  htmlFor="signup-age"
                  className="block text-xs font-medium text-on-surface-variant mb-1"
                >
                  Age
                </label>
                <input
                  id="signup-age"
                  name="age"
                  type="number"
                  required
                  min={10}
                  max={120}
                  step={1}
                  inputMode="numeric"
                  value={age}
                  onChange={(e) => setAge(e.target.value)}
                  placeholder="e.g. 25"
                  className="w-full px-3 py-2 text-sm rounded-lg bg-surface-variant/40 border border-outline-variant/30 focus:outline-none focus:ring-2 focus:ring-primary/50 text-on-surface placeholder:text-on-surface-variant/50"
                />
              </div>
            </>
          )}

          <div>
            <label className="block text-xs font-medium text-on-surface-variant mb-1">
              Email Address
            </label>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              className="w-full px-3 py-2 text-sm rounded-lg bg-surface-variant/40 border border-outline-variant/30 focus:outline-none focus:ring-2 focus:ring-primary/50 text-on-surface placeholder:text-on-surface-variant/50"
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-on-surface-variant mb-1">
              Password
            </label>
            <input
              type="password"
              required
              minLength={6}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              className="w-full px-3 py-2 text-sm rounded-lg bg-surface-variant/40 border border-outline-variant/30 focus:outline-none focus:ring-2 focus:ring-primary/50 text-on-surface placeholder:text-on-surface-variant/50"
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full py-2.5 px-4 rounded-lg bg-primary hover:bg-primary/90 text-on-primary font-medium text-sm transition-all duration-150 shadow-md hover:shadow-lg disabled:opacity-50 flex items-center justify-center gap-2 mt-6 cursor-pointer"
          >
            {loading ? (
              <>
                <span className="material-symbols-outlined animate-spin text-sm">
                  progress_activity
                </span>
                <span>Processing...</span>
              </>
            ) : authModalMode === "login" ? (
              "Sign In"
            ) : (
              "Create Free Account"
            )}
          </button>
        </form>

        <div className="mt-6 text-center text-xs text-on-surface-variant">
          {authModalMode === "login" ? (
            <p>
              Don&apos;t have an account?{" "}
              <button
                type="button"
                onClick={() => changeMode("signup")}
                className="text-primary font-semibold hover:underline"
              >
                Sign Up
              </button>
            </p>
          ) : (
            <p>
              Already have an account?{" "}
              <button
                type="button"
                onClick={() => changeMode("login")}
                className="text-primary font-semibold hover:underline"
              >
                Sign In
              </button>
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
