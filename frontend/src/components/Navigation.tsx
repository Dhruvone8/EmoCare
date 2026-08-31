"use client";

import React, { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/context/AuthContext";

interface NavItem {
  href: string;
  label: string;
  icon: string;
  isNew?: boolean;
}

const NAV_ITEMS: NavItem[] = [
  { href: "/", label: "Home", icon: "home" },
  { href: "/assessment", label: "Assessment", icon: "assignment" },
  { href: "/checkin", label: "Check-in", icon: "mood" },
  { href: "/journal", label: "Journal", icon: "edit_note" },
  { href: "/therapy/chat", label: "Chat AI", icon: "forum", isNew: true },
  { href: "/therapy/voice", label: "Voice AI", icon: "headset_mic", isNew: true },
  { href: "/insights", label: "Insights", icon: "insights" },
];

export function Navigation() {
  const pathname = usePathname();
  const { user, openAuthModal, signOut, loading } = useAuth();
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const displayName =
    user?.user_metadata?.full_name ||
    user?.email?.split("@")[0] ||
    "User";

  return (
    <header className="sticky top-0 z-50 w-full transition-all duration-300">
      {/* Glass navigation bar */}
      <div className="bg-surface/85 backdrop-blur-xl border-b border-outline-variant/20 shadow-[0_2px_20px_rgba(15,23,42,0.04)]">
        <div className="w-full px-4 sm:px-6 md:px-8 lg:px-10 xl:px-12 h-16 flex items-center justify-between gap-4">
          
          {/* Brand Logo - Extreme Left Boundary */}
          <Link
            href="/"
            className="flex items-center gap-2.5 group shrink-0 select-none transition-transform duration-200 active:scale-95"
          >
            <span className="text-2xl transition-transform duration-300 ease-out group-hover:scale-110 drop-shadow-xs">
              🌱
            </span>
            <span className="font-sans text-xl sm:text-[22px] font-bold tracking-tight text-on-surface group-hover:text-primary transition-colors duration-200">
              EmoCare
            </span>
          </Link>

          {/* Navigation Links (Desktop) - Centered */}
          <nav className="hidden lg:flex items-center justify-center gap-1 xl:gap-1.5 flex-1 px-4">
            {NAV_ITEMS.map((item) => {
              const isActive =
                item.href === "/"
                  ? pathname === "/"
                  : pathname === item.href || (pathname?.startsWith(item.href) ?? false);

              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`relative font-sans text-[13px] font-medium tracking-normal px-3.5 py-1.5 rounded-full transition-all duration-200 flex items-center gap-1.5 whitespace-nowrap shrink-0 select-none ${
                    isActive
                      ? "text-primary bg-primary/10 font-semibold shadow-xs"
                      : "text-on-surface-variant/80 hover:text-primary hover:bg-surface-variant/50 hover:shadow-xs active:scale-95"
                  }`}
                >
                  <span
                    className="material-symbols-outlined text-[17px] leading-none shrink-0 transition-transform duration-200 group-hover:scale-105"
                    style={{ fontVariationSettings: isActive ? "'FILL' 1" : "'FILL' 0" }}
                  >
                    {item.icon}
                  </span>
                  <span>{item.label}</span>
                  {item.isNew && (
                    <span className="flex h-1.5 w-1.5 relative shrink-0 ml-0.5">
                      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-primary opacity-75"></span>
                      <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-primary"></span>
                    </span>
                  )}
                </Link>
              );
            })}
          </nav>

          {/* Right Section: Auth & Mobile Menu Button - Extreme Right Boundary */}
          <div className="flex items-center gap-2 sm:gap-3 shrink-0">
            {/* Auth Controls */}
            {loading ? (
              <div className="w-8 h-8 rounded-full bg-surface-variant/40 animate-pulse" />
            ) : user ? (
              <div className="relative">
                <button
                  onClick={() => setDropdownOpen(!dropdownOpen)}
                  className="flex items-center gap-2 py-1.5 px-3.5 rounded-full bg-primary/8 hover:bg-primary/15 text-primary border border-primary/15 transition-all duration-200 hover:shadow-xs active:scale-95 cursor-pointer text-xs font-semibold select-none"
                  aria-label="User menu"
                >
                  <span className="material-symbols-outlined text-lg leading-none">account_circle</span>
                  <span className="max-w-[110px] truncate hidden sm:inline">{displayName}</span>
                  <span className="material-symbols-outlined text-sm leading-none transition-transform duration-200">
                    {dropdownOpen ? "expand_less" : "expand_more"}
                  </span>
                </button>

                {/* User Dropdown */}
                {dropdownOpen && (
                  <div
                    className="absolute right-0 mt-2 w-56 glass-panel-elevated rounded-2xl py-2 z-50 animate-sanctuary-in shadow-xl border border-outline-variant/20 bg-surface/95 backdrop-blur-xl"
                    onClick={() => setDropdownOpen(false)}
                  >
                    <div className="px-4 py-3 border-b border-outline-variant/15">
                      <p className="text-xs font-bold text-on-surface truncate">
                        {displayName}
                      </p>
                      <p className="text-[11px] text-on-surface-variant truncate mt-0.5">
                        {user.email}
                      </p>
                    </div>
                    <Link
                      href="/insights"
                      className="flex items-center gap-2.5 px-4 py-2.5 text-xs font-medium text-on-surface hover:text-primary hover:bg-surface-variant/40 transition-colors duration-150"
                    >
                      <span className="material-symbols-outlined text-base">insights</span>
                      <span>My Insights & History</span>
                    </Link>
                    <button
                      onClick={() => signOut()}
                      className="w-full text-left flex items-center gap-2.5 px-4 py-2.5 text-xs font-medium text-error hover:bg-error/10 transition-colors duration-150 cursor-pointer"
                    >
                      <span className="material-symbols-outlined text-base">logout</span>
                      <span>Sign Out</span>
                    </button>
                  </div>
                )}
              </div>
            ) : (
              <div className="flex items-center gap-2 sm:gap-2.5">
                <button
                  onClick={() => openAuthModal("login")}
                  className="text-xs sm:text-[13px] font-semibold text-on-surface-variant hover:text-primary px-3.5 sm:px-4 py-1.5 rounded-full hover:bg-surface-variant/50 transition-all duration-200 active:scale-95 cursor-pointer whitespace-nowrap"
                >
                  Sign In
                </button>
                <button
                  onClick={() => openAuthModal("signup")}
                  className="text-xs sm:text-[13px] font-semibold text-white bg-primary hover:bg-primary/90 px-4 sm:px-5 py-1.5 rounded-full shadow-xs hover:shadow-md hover:-translate-y-0.5 active:translate-y-0 active:scale-95 transition-all duration-200 cursor-pointer whitespace-nowrap"
                >
                  Get Started
                </button>
              </div>
            )}

            {/* Mobile hamburger menu toggle */}
            <button
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="lg:hidden p-2 rounded-full hover:bg-surface-variant/40 transition-colors duration-200 text-on-surface-variant focus:outline-none cursor-pointer"
              aria-label="Toggle navigation"
            >
              <span className="material-symbols-outlined text-2xl leading-none">
                {mobileMenuOpen ? "close" : "menu"}
              </span>
            </button>
          </div>
        </div>
      </div>

      {/* Mobile Navigation Drawer */}
      {mobileMenuOpen && (
        <div className="lg:hidden bg-surface/95 backdrop-blur-2xl border-b border-outline-variant/20 shadow-lg px-4 py-3 animate-sanctuary-in space-y-1">
          {NAV_ITEMS.map((item) => {
            const isActive =
              item.href === "/"
                ? pathname === "/"
                : pathname === item.href || (pathname?.startsWith(item.href) ?? false);

            return (
              <Link
                key={item.href}
                href={item.href}
                onClick={() => setMobileMenuOpen(false)}
                className={`flex items-center justify-between px-4 py-2.5 rounded-xl text-sm font-medium transition-all duration-150 ${
                  isActive
                    ? "text-primary bg-primary/10 font-semibold shadow-xs"
                    : "text-on-surface-variant hover:text-primary hover:bg-surface-variant/30 active:scale-[0.99]"
                }`}
              >
                <div className="flex items-center gap-3">
                  <span
                    className="material-symbols-outlined text-lg leading-none"
                    style={{ fontVariationSettings: isActive ? "'FILL' 1" : "'FILL' 0" }}
                  >
                    {item.icon}
                  </span>
                  <span>{item.label}</span>
                </div>
                {item.isNew && (
                  <span className="text-[10px] font-bold uppercase tracking-wider text-primary bg-primary/15 px-2 py-0.5 rounded-full">
                    New
                  </span>
                )}
              </Link>
            );
          })}
        </div>
      )}
    </header>
  );
}
