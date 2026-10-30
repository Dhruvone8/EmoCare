import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { Navigation } from "@/components/Navigation";
import { Footer } from "@/components/Footer";
import { AuthProvider } from "@/context/AuthContext";
import { AuthModal } from "@/components/AuthModal";
import { DailyCheckInGate } from "@/components/DailyCheckInModal";
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

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={`${geistSans.variable} ${geistMono.variable}`}>
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          rel="stylesheet"
          href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200&display=swap"
        />
      </head>
      <body className="bg-background text-on-surface font-sans antialiased min-h-screen gradient-bg flex flex-col relative overflow-x-hidden">
        <AuthProvider>
          <Navigation />
          <main className="flex-grow w-full max-w-[1360px] mx-auto px-4 sm:px-6 md:px-8 lg:px-10 xl:px-12 py-6 sm:py-8 md:py-10 flex flex-col gap-6 sm:gap-8 md:gap-10 z-10 relative">
            {children}
          </main>
          <Footer />
          <AuthModal />
          <DailyCheckInGate />
        </AuthProvider>
      </body>
    </html>
  );
}
