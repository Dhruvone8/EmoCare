"use client";

import React, { createContext, useContext, useEffect, useState } from "react";
import { User, Session, AuthError } from "@supabase/supabase-js";
import { supabase } from "@/lib/supabase";

interface AuthContextType {
  user: User | null;
  session: Session | null;
  loading: boolean;
  isAuthModalOpen: boolean;
  openAuthModal: (mode?: "login" | "signup") => void;
  closeAuthModal: () => void;
  authModalMode: "login" | "signup";
  setAuthModalMode: (mode: "login" | "signup") => void;
  signIn: (email: string, password: string) => Promise<{ error: AuthError | null }>;
  signUp: (email: string, password: string, fullName: string, age: number) => Promise<{ error: AuthError | null }>;
  signOut: () => Promise<void>;
}

/* Safe default for prerendering — used when AuthProvider is absent
   (e.g. during Next.js 16 _global-error static generation) */
const noop = () => {};
const noopAsync = async () => ({ error: null as AuthError | null });

const AUTH_DEFAULT: AuthContextType = {
  user: null,
  session: null,
  loading: true,
  isAuthModalOpen: false,
  openAuthModal: noop,
  closeAuthModal: noop,
  authModalMode: "login",
  setAuthModalMode: noop,
  signIn: noopAsync,
  signUp: noopAsync,
  signOut: async () => {},
};

const AuthContext = createContext<AuthContextType>(AUTH_DEFAULT);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);
  const [isAuthModalOpen, setIsAuthModalOpen] = useState(false);
  const [authModalMode, setAuthModalMode] = useState<"login" | "signup">("login");
  const [authNotice, setAuthNotice] = useState<string | null>(null);

  useEffect(() => {
    if (!authNotice) return;
    const timeout = window.setTimeout(() => setAuthNotice(null), 5000);
    return () => window.clearTimeout(timeout);
  }, [authNotice]);

  useEffect(() => {
    let isMounted = true;

    // 1. Get current active session
    supabase.auth
      .getSession()
      .then(({ data: { session } }) => {
        if (isMounted) {
          setSession(session);
          setUser(session?.user ?? null);
          setLoading(false);
        }
      })
      .catch((err) => {
        console.error("Failed to restore Supabase session:", err);
        if (isMounted) {
          setLoading(false);
        }
      });

    // 2. Listen for auth changes
    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, session) => {
      if (isMounted) {
        setSession(session);
        setUser(session?.user ?? null);
        setLoading(false);
      }
    });

    return () => {
      isMounted = false;
      subscription.unsubscribe();
    };
  }, []);

  const openAuthModal = (mode: "login" | "signup" = "login") => {
    setAuthModalMode(mode);
    setIsAuthModalOpen(true);
  };

  const closeAuthModal = () => {
    setIsAuthModalOpen(false);
  };

  const signIn = async (email: string, password: string) => {
    const normalizedEmail = email.trim().toLowerCase();
    const { data: current } = await supabase.auth.getSession();
    if (current.session?.user.email?.toLowerCase() === normalizedEmail) {
      setSession(current.session);
      setUser(current.session.user);
      setLoading(false);
      setAuthNotice(`Signed in as ${current.session.user.email ?? "your account"}.`);
      closeAuthModal();
      return { error: null };
    }

    const { data, error } = await supabase.auth.signInWithPassword({
      email: normalizedEmail,
      password,
    });
    if (error) return { error };
    if (!data.session) {
      return {
        error: new AuthError(
          "Sign-in did not create an active session. Please confirm your email and try again."
        ),
      };
    }

    const authenticatedUser = data.user ?? data.session.user;
    setSession(data.session);
    setUser(authenticatedUser);
    setLoading(false);
    setAuthNotice(`Signed in as ${authenticatedUser.email ?? "your account"}.`);
    closeAuthModal();
    return { error: null };
  };

  const signUp = async (email: string, password: string, fullName: string, age: number) => {
    const { data, error } = await supabase.auth.signUp({
      email,
      password,
      options: {
        data: {
          full_name: fullName,
          age: age,
        },
      },
    });
    if (!error && data.session) {
      const authenticatedUser = data.user ?? data.session.user;
      setSession(data.session);
      setUser(authenticatedUser);
      setLoading(false);
      setAuthNotice(`Account created. Signed in as ${authenticatedUser.email ?? "your account"}.`);
      closeAuthModal();
    }
    return { error };
  };

  const signOut = async () => {
    await supabase.auth.signOut();
    setSession(null);
    setUser(null);
    setLoading(false);
    setAuthNotice("You have been signed out.");
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        session,
        loading,
        isAuthModalOpen,
        openAuthModal,
        closeAuthModal,
        authModalMode,
        setAuthModalMode,
        signIn,
        signUp,
        signOut,
      }}
    >
      {children}
      {authNotice && (
        <div
          role="status"
          aria-live="polite"
          className="fixed bottom-4 left-4 right-4 sm:left-auto sm:right-6 sm:bottom-6 z-[80] flex items-center gap-3 rounded-2xl border border-emerald-500/25 bg-surface-container-lowest px-4 py-3 text-on-surface shadow-2xl sm:max-w-sm"
        >
          <span className="material-symbols-outlined text-emerald-600 shrink-0">check_circle</span>
          <span className="flex-1 font-sans text-sm leading-relaxed">{authNotice}</span>
          <button
            type="button"
            onClick={() => setAuthNotice(null)}
            className="p-1 rounded-full text-on-surface-variant hover:text-on-surface hover:bg-surface-variant/40 transition-colors"
            aria-label="Dismiss authentication notification"
          >
            <span className="material-symbols-outlined text-lg">close</span>
          </button>
        </div>
      )}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
