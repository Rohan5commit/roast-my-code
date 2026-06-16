"use client";

import { useRouter } from "next/navigation";
import ScoreRing from "@/components/ScoreRing";

const FAMOUS_ROASTS = [
  { name: "django", url: "https://github.com/django/django", score: 82, verdict: "SHIP IT", emoji: " ", lines: 45000, files: 2800 },
  { name: "flask", url: "https://github.com/pallets/flask", score: 75, verdict: "SHIP IT", emoji: " ", lines: 12000, files: 180 },
  { name: "requests", url: "https://github.com/psf/requests", score: 68, verdict: "NEEDS WORK", emoji: " ", lines: 18000, files: 120 },
  { name: "fastapi", url: "https://github.com/tiangolo/fastapi", score: 78, verdict: "SHIP IT", emoji: " ", lines: 32000, files: 450 },
  { name: "numpy", url: "https://github.com/numpy/numpy", score: 85, verdict: "SHIP IT", emoji: " ", lines: 350000, files: 3200 },
  { name: "pandas", url: "https://github.com/pandas-dev/pandas", score: 72, verdict: "NEEDS WORK", emoji: " ", lines: 280000, files: 2100 },
  { name: "matplotlib", url: "https://github.com/matplotlib/matplotlib", score: 70, verdict: "NEEDS WORK", emoji: " ", lines: 180000, files: 2800 },
  { name: "scikit-learn", url: "https://github.com/scikit-learn/scikit-learn", score: 80, verdict: "SHIP IT", emoji: " ", lines: 220000, files: 1900 },
  { name: "react", url: "https://github.com/facebook/react", score: 88, verdict: "SHIP IT", emoji: " ", lines: 180000, files: 2400 },
];

export default function GalleryPage() {
  const router = useRouter();

  return (
    <main className="min-h-screen bg-roast-bg">
      <div className="border-b border-roast-border bg-roast-card/50">
        <div className="max-w-6xl mx-auto px-4 py-6 flex items-center justify-between">
          <button onClick={() => router.push("/")} className="text-roast-accent hover:text-roast-accent/80 font-medium">
            ← Back to Home
          </button>
          <h1 className="text-xl font-bold text-roast-text">Famous Repo Roasts</h1>
        </div>
      </div>

      <div className="max-w-6xl mx-auto px-4 py-12">
        <p className="text-center text-roast-muted mb-8">
          See how the most popular open source repos score. Click to view the full roast.
        </p>
        <div className="grid md:grid-cols-3 gap-6" role="list">
          {FAMOUS_ROASTS.map((roast) => (
            <div
              key={roast.name}
              role="listitem"
              tabIndex={0}
              onClick={() => router.push(`/roast/famous-${roast.name}`)}
              onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); router.push(`/roast/famous-${roast.name}`); } }}
              className="bg-roast-card border border-roast-border rounded-xl p-6 hover:border-roast-accent/50 transition-all cursor-pointer group"
            >
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-xl font-bold text-roast-text group-hover:text-roast-accent transition-colors">
                  {roast.name}
                </h3>
                <ScoreRing score={roast.score} size={60} />
              </div>
              <div className="text-roast-muted text-sm space-y-1">
                <div className="flex justify-between">
                  <span>Lines of code</span>
                  <span className="text-roast-text">{roast.lines.toLocaleString()}</span>
                </div>
                <div className="flex justify-between">
                  <span>Files</span>
                  <span className="text-roast-text">{roast.files.toLocaleString()}</span>
                </div>
              </div>
              <div className="mt-4 pt-4 border-t border-roast-border flex items-center justify-between">
                <span className="text-roast-muted">
                  {roast.emoji} {roast.verdict}
                </span>
                <span className="text-roast-accent text-sm group-hover:translate-x-1 transition-transform">
                  View Roast →
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>

      <footer className="border-t border-roast-border py-8 text-center text-roast-muted text-sm">
        <p>Roast scores are based on static analysis of code patterns, not LLM generation.</p>
      </footer>
    </main>
  );
}
