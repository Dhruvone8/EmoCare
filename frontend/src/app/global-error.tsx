"use client";

import React from "react";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <html lang="en">
      <body className="bg-slate-900 text-white min-h-screen flex items-center justify-center p-6">
        <div className="max-w-md w-full bg-slate-800 rounded-xl p-8 border border-slate-700 text-center shadow-xl">
          <h2 className="text-xl font-bold mb-4 text-red-400">An unexpected error occurred</h2>
          <p className="text-slate-300 text-sm mb-6">
            {error?.message || "Something went wrong while rendering the application."}
          </p>
          <button
            onClick={() => reset()}
            className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg transition-colors font-medium text-sm"
          >
            Try again
          </button>
        </div>
      </body>
    </html>
  );
}
