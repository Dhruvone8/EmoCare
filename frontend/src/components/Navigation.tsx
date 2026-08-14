"use client";

import React, { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/context/AuthContext";

const NAV_ITEMS = [
  { href: "/", label: "Home" },
  { href: "/assessment", label: "Assessment" },
  { href: "/journal", label: "Journal" },
  { href: "/voice", label: "Talk" },
  { href: "/checkin", label: "Habits" },
  { href: "/insights", label: "Insights" },
];


export function Navigation() {
  const pathname = usePathname();
  const { user, openAuthModal, signOut, loading } = useAuth();
  const [dropdownOpen, setDropdownOpen] = useState(false);

  const displayName =
    user?.user_metadata?.full_name ||
    user?.email?.split("@")[0] ||
    "User";

  return (
    <header className="bg-surface/80 backdrop-blur-md shadow-sm sticky top-0 z-40 w-full">
      <div className="flex justify-between items-center w-full px-[var(--spacing-container-mobile)] md:px-[var(--spacing-container-desktop)] py-4 max-w-[1200px] mx-auto">
        {/* Brand */}
        <Link
          href="/"
          className="font-sans text-[28px] md:text-[32px] font-semibold text-primary tracking-tighter leading-none flex items-center gap-2"
        >
          <span>🌱</span>
          <span>EmoCare</span>
        </Link>

        {/* Navigation (Desktop) */}
        <nav className="hidden md:flex items-center space-x-8">
          {NAV_ITEMS.map((item) => {
            const isActive = pathname === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`font-sans text-[13px] font-medium tracking-wide transition-all duration-200 ${
                  isActive
                    ? "text-primary border-b-2 border-primary pb-1"
                    : "text-on-surface-variant hover:text-primary"
                }`}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>

        {/* Auth Controls */}
        <div className="flex items-center space-x-3">
          {loading ? (
            <div className="w-8 h-8 rounded-full bg-surface-variant/40 animate-pulse" />
          ) : user ? (
            <div className="relative">
              <button
                onClick={() => setDropdownOpen(!dropdownOpen)}
                className="flex items-center gap-2 py-1.5 px-3 rounded-full bg-primary/10 hover:bg-primary/20 text-primary border border-primary/20 transition-all cursor-pointer text-xs font-medium"
                aria-label="User menu"
              >
                <span className="material-symbols-outlined text-lg">account_circle</span>
                <span className="max-w-[120px] truncate">{displayName}</span>
                <span className="material-symbols-outlined text-sm">
                  {dropdownOpen ? "expand_less" : "expand_more"}
                </span>
              </button>

              {/* User Dropdown */}
              {dropdownOpen && (
                <div
                  className="absolute right-0 mt-2 w-48 bg-surface border border-outline-variant/30 rounded-xl shadow-xl py-2 z-50 animate-in fade-in zoom-in-95 duration-150"
                  onClick={() => setDropdownOpen(false)}
                >
                  <div className="px-4 py-2 border-b border-outline-variant/20">
                    <p className="text-xs font-semibold text-on-surface truncate">
                      {displayName}
                    </p>
                    <p className="text-[11px] text-on-surface-variant truncate">
                      {user.email}
                    </p>
                  </div>
                  <Link
                    href="/insights"
                    className="flex items-center gap-2 px-4 py-2 text-xs text-on-surface hover:bg-surface-variant/40 transition-colors"
                  >
                    <span className="material-symbols-outlined text-base">insights</span>
                    <span>My History</span>
                  </Link>
                  <button
                    onClick={() => signOut()}
                    className="w-full text-left flex items-center gap-2 px-4 py-2 text-xs text-error hover:bg-error/10 transition-colors cursor-pointer"
                  >
                    <span className="material-symbols-outlined text-base">logout</span>
                    <span>Sign Out</span>
                  </button>
                </div>
              )}
            </div>
          ) : (
            <div className="flex items-center gap-2">
              <button
                onClick={() => openAuthModal("login")}
                className="text-xs font-medium text-on-surface-variant hover:text-primary px-3 py-1.5 rounded-full hover:bg-surface-variant/40 transition-colors cursor-pointer"
              >
                Sign In
              </button>
              <button
                onClick={() => openAuthModal("signup")}
                className="text-xs font-medium text-on-primary bg-primary hover:bg-primary/90 px-3.5 py-1.5 rounded-full shadow-sm transition-all cursor-pointer"
              >
                Get Started
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}

