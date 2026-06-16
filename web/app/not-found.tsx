"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

export default function NotFound() {
  const router = useRouter();

  useEffect(() => {
    document.title = "404 - Roast My Code";
  }, []);

  return (
    <main className="min-h-screen bg-roast-bg flex items-center justify-center">
      <div className="text-center max-w-md">
        <h1 className="text-6xl font-bold mb-4 text-roast-accent">404</h1>
        <p className="text-roast-muted mb-8">
          This page doesn&apos;t exist. Even code has its limits.
        </p>
        <button
          onClick={() => router.push("/")}
          className="px-6 py-3 bg-roast-accent hover:bg-roast-accent/90 text-white rounded-lg font-medium"
        >
          Go Home
        </button>
      </div>
    </main>
  );
}
