import Link from "next/link";

export function Footer() {
  return (
    <footer className="bg-surface/85 backdrop-blur-md border-t border-outline-variant/20 w-full mt-auto">
      <div className="flex flex-col sm:flex-row justify-between items-center w-full px-4 sm:px-6 md:px-8 lg:px-10 xl:px-12 py-6 gap-4">
        <div className="flex items-center gap-2 font-sans text-sm font-semibold text-primary">
          <span className="text-base">🌱</span>
          <span className="tracking-tight">EmoCare</span>
        </div>
        <div className="font-sans text-xs sm:text-sm text-on-surface-variant text-center sm:text-left">
          Your emotional wellness companion. Always here for you.
        </div>
        <nav className="flex items-center space-x-6">
          <Link
            href="#"
            className="font-sans text-xs sm:text-sm text-on-surface-variant hover:text-primary transition-colors duration-200"
          >
            Privacy
          </Link>
          <Link
            href="#"
            className="font-sans text-xs sm:text-sm text-on-surface-variant hover:text-primary transition-colors duration-200"
          >
            Support
          </Link>
        </nav>
      </div>
    </footer>
  );
}
