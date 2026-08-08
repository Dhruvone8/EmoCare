import Link from "next/link";

export function Footer() {
  return (
    <footer className="bg-surface border-t border-outline-variant/20 w-full mt-auto">
      <div className="flex flex-col md:flex-row justify-between items-center w-full px-[var(--spacing-container-mobile)] md:px-[var(--spacing-container-desktop)] py-[var(--spacing-stack-md)] max-w-[1200px] mx-auto gap-4">
        <div className="font-sans text-[14px] font-medium text-primary">
          EmoCare
        </div>
        <div className="font-sans text-[13px] text-on-surface-variant text-center md:text-left">
          Your emotional wellness companion. Always here for you.
        </div>
        <nav className="flex space-x-6">
          <Link
            href="#"
            className="font-sans text-[13px] text-on-surface-variant hover:text-primary transition-colors"
          >
            Privacy
          </Link>
          <Link
            href="#"
            className="font-sans text-[13px] text-on-surface-variant hover:text-primary transition-colors"
          >
            Support
          </Link>
        </nav>
      </div>
    </footer>
  );
}
