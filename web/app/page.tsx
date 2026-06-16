"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import RoastInput from "@/components/RoastInput";
import ScoreRing from "@/components/ScoreRing";

const FAMOUS_ROASTS = [
  { name: "requests", score: 68, verdict: "NEEDS WORK", emoji: " " },
  { name: "django", score: 82, verdict: "SHIP IT", emoji: " " },
  { name: "flask", score: 75, verdict: "SHIP IT", emoji: " " },
];

export default function Home() {
  const router = useRouter();
  const [isRoasting, setIsRoasting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleRoast = async (url: string) => {
    setIsRoasting(true);
    setError(null);

    try {
      const response = await fetch("/api/roast", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url }),
      });

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.error || "Failed to roast this repo");
      }

      const data = await response.json();
      if (typeof window !== "undefined") {
        sessionStorage.setItem(`roast-${data.id}`, JSON.stringify(data));
      }
      router.push(`/roast/${data.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
      setIsRoasting(false);
    }
  };

  return (
    <main className="min-h-screen bg-roast-bg">
      <div className="relative overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-b from-roast-accent/5 to-transparent" />
        <div className="relative max-w-5xl mx-auto px-4 pt-20 pb-16">
          <div className="text-center mb-12">
            <h1 className="text-5xl md:text-7xl font-bold mb-6 bg-gradient-to-r from-roast-accent to-orange-500 bg-clip-text text-transparent">
              Roast My Code
            </h1>
            <p className="text-xl md:text-2xl text-roast-muted max-w-2xl mx-auto text-balance">
              The AI that roasts your codebase so your teammates don&apos;t have to.
            </p>
          </div>

          <RoastInput onSubmit={handleRoast} isLoading={isRoasting} />

          {error && (
            <div className="mt-4 p-4 bg-roast-accent/10 border border-roast-accent/30 rounded-lg text-center text-roast-accent animate-fade-in" role="alert">
              {error}
            </div>
          )}
        </div>
      </div>

      <div className="max-w-5xl mx-auto px-4 py-16">
        <div className="grid md:grid-cols-3 gap-8">
          {[
            { title: "Paste & Roast", desc: "Just paste a GitHub URL. We handle the rest." },
            { title: "Brutally Honest", desc: "AI-powered analysis with Gordon Ramsay energy." },
            { title: "Share the Pain", desc: "Get a shareable link and badge for your README." },
          ].map((feature, i) => (
            <div key={i} className="p-6 bg-roast-card border border-roast-border rounded-xl hover:border-roast-accent/50 transition-colors">
              <h3 className="text-lg font-semibold mb-2 text-roast-text">{feature.title}</h3>
              <p className="text-roast-muted">{feature.desc}</p>
            </div>
          ))}
        </div>
      </div>

      <div className="max-w-5xl mx-auto px-4 py-16 border-t border-roast-border">
        <h2 className="text-3xl font-bold text-center mb-8 text-roast-text">Famous Repo Roasts</h2>
        <div className="grid md:grid-cols-3 gap-6">
          {FAMOUS_ROASTS.map((roast) => (
            <div
              key={roast.name}
              tabIndex={0}
              role="button"
              onClick={() => router.push(`/roast/famous-${roast.name}`)}
              onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); router.push(`/roast/famous-${roast.name}`); } }}
              className="p-6 bg-roast-card border border-roast-border rounded-xl text-center hover:border-roast-accent/50 transition-all cursor-pointer"
            >
              <ScoreRing score={roast.score} size={80} />
              <h3 className="text-xl font-bold mt-4 text-roast-text">{roast.name}</h3>
              <p className="text-roast-muted mt-1">
                {roast.emoji} {roast.verdict}
              </p>
            </div>
          ))}
        </div>
        <div className="text-center mt-8">
          <button onClick={() => router.push("/gallery")} className="text-roast-accent hover:text-roast-accent/80 font-medium">
            View All Famous Roasts →
          </button>
        </div>
      </div>

      <footer className="border-t border-roast-border py-8 text-center text-roast-muted text-sm">
        <p>Built with Python, Next.js, and questionable humor.</p>
        <p className="mt-2">
          <a href="https://github.com/Rohan5commit/roast-my-code" className="text-roast-accent hover:underline" target="_blank" rel="noopener noreferrer">
            Star on GitHub
          </a>
        </p>
      </footer>
    </main>
  );
}
