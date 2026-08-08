"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV_ITEMS = [
  { href: "/", label: "Home" },
  { href: "/journal", label: "Journal" },
  { href: "/voice", label: "Talk" },
  { href: "/checkin", label: "Check-in" },
  { href: "/insights", label: "Insights" },
];

export function Navigation() {
  const pathname = usePathname();

  return (
    <header className="bg-surface/80 backdrop-blur-md shadow-sm sticky top-0 z-50 w-full">
      <div className="flex justify-between items-center w-full px-[var(--spacing-container-mobile)] md:px-[var(--spacing-container-desktop)] py-4 max-w-[1200px] mx-auto">
        {/* Brand */}
        <Link
          href="/"
          className="font-sans text-[28px] md:text-[32px] font-semibold text-primary tracking-tighter leading-none"
        >
          EmoCare
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

        {/* Trailing Icons */}
        <div className="flex items-center space-x-2 text-primary">
          <button
            aria-label="Notifications"
            className="hover:text-primary-container transition-colors p-2 rounded-full hover:bg-surface-variant/50"
          >
            <span
              className="material-symbols-outlined"
              style={{ fontVariationSettings: "'FILL' 0" }}
            >
              notifications
            </span>
          </button>
          <button
            aria-label="Profile"
            className="hover:text-primary-container transition-colors p-2 rounded-full hover:bg-surface-variant/50"
          >
            <span
              className="material-symbols-outlined"
              style={{ fontVariationSettings: "'FILL' 0" }}
            >
              account_circle
            </span>
          </button>
        </div>
      </div>
    </header>
  );
}
