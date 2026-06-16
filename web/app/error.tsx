"use client";

import { useEffect } from "react";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <main className="min-h-screen bg-roast-bg flex items-center justify-center">
      <div className="text-center max-w-md">
        <h1 className="text-4xl font-bold mb-4 text-roast-text">Something went wrong</h1>
        <p className="text-roast-muted mb-8">
          An unexpected error occurred. Please try again.
        </p>
        <button
          onClick={() => reset()}
          className="px-6 py-3 bg-roast-accent hover:bg-roast-accent/90 text-white rounded-lg font-medium"
        >
          Try Again
        </button>
      </div>
    </main>
  );
}
