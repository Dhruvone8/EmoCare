import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { Navigation } from "@/components/Navigation";
import { Footer } from "@/components/Footer";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-sans",
  subsets: ["latin"],
  display: "swap",
});

const geistMono = Geist_Mono({
  variable: "--font-mono",
  subsets: ["latin"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "EmoCare — Emotional Wellness Sanctuary",
  description:
    "AI-powered affective computing for early emotional insight and support. An intelligent system for early detection & support of mental health distress.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${geistSans.variable} ${geistMono.variable}`}>
      <head>
        <link
          href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&display=swap"
          rel="stylesheet"
        />
      </head>
      <body className="bg-background text-on-surface font-sans antialiased min-h-screen gradient-bg flex flex-col relative overflow-x-hidden">
        <Navigation />
        <main className="flex-grow w-full max-w-[1200px] mx-auto px-[var(--spacing-container-mobile)] md:px-[var(--spacing-container-desktop)] py-[var(--spacing-stack-lg)] flex flex-col gap-[var(--spacing-stack-lg)] z-10 relative">
          {children}
        </main>
        <Footer />
      </body>
    </html>
  );
}
