"use client";

import { useEffect, useState, useMemo } from "react";
import { useParams, useRouter } from "next/navigation";
import ScoreRing from "@/components/ScoreRing";
import IssueTable, { Issue } from "@/components/IssueTable";
import ShareButtons from "@/components/ShareButtons";

interface RoastData {
  id: string;
  url: string;
  repo_name: string;
  score: number;
  headline: string;
  verdict: string;
  verdict_emoji: string;
  files_scanned: number;
  total_lines: number;
  issues_count: number;
  issues: Issue[];
  roast_lines: string[];
  hotspot_files: { file: string; count: number }[];
  category_counts: Record<string, number>;
  severity_counts: Record<string, number>;
  created_at: string;
}

export default function RoastPage() {
  const params = useParams();
  const router = useRouter();
  const [data, setData] = useState<RoastData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();

    const fetchRoast = async () => {
      if (typeof window !== "undefined") {
        const cached = sessionStorage.getItem(`roast-${params.id}`);
        if (cached) {
          try {
            const parsed = JSON.parse(cached);
            if (parsed && parsed.score !== undefined) {
              setData(parsed);
              setLoading(false);
              return;
            }
          } catch {}
        }
      }

      try {
        const res = await fetch(`/api/roast?id=${params.id}`, { signal: controller.signal });
        if (!res.ok) {
          setError("not_found");
        } else {
          const result = await res.json();
          if (result.error) {
            setError("not_found");
          } else {
            setData(result);
            if (typeof window !== "undefined") {
              try {
                sessionStorage.setItem(`roast-${params.id}`, JSON.stringify(result));
              } catch {}
            }
          }
        }
      } catch (err) {
        if (err instanceof DOMException && err.name === "AbortError") return;
        setError("not_found");
      } finally {
        setLoading(false);
      }
    };
    fetchRoast();

    return () => controller.abort();
  }, [params.id]);

  const safeIssuesCount = useMemo(() => data?.issues_count || 1, [data?.issues_count]);

  if (loading) {
    return (
      <main className="min-h-screen bg-roast-bg flex items-center justify-center" role="status" aria-label="Loading roast results">
        <div className="text-center">
          <div className="animate-spin h-12 w-12 border-4 border-roast-accent border-t-transparent rounded-full mx-auto mb-4" />
          <p className="text-roast-muted">Loading roast...</p>
        </div>
      </main>
    );
  }

  if (error || !data) {
    return (
      <main className="min-h-screen bg-roast-bg flex items-center justify-center">
        <div className="text-center max-w-md">
          <h1 className="text-4xl font-bold mb-4 text-roast-text">Roast Not Found</h1>
          <p className="text-roast-muted mb-2">
            This roast doesn&apos;t exist or has expired.
          </p>
          <p className="text-roast-muted mb-8 text-sm">
            Roast results are generated fresh each time. Enter a GitHub URL on the home page to get a new roast.
          </p>
          <button onClick={() => router.push("/")} className="px-6 py-3 bg-roast-accent hover:bg-roast-accent/90 text-white rounded-lg font-medium">
            Roast a Repo
          </button>
        </div>
      </main>
    );
  }

  const repoName = data.repo_name || data.url.replace("https://github.com/", "");

  return (
    <main className="min-h-screen bg-roast-bg">
      <div className="border-b border-roast-border bg-roast-card/50">
        <div className="max-w-6xl mx-auto px-4 py-6 flex items-center justify-between">
          <button onClick={() => router.push("/")} className="text-roast-accent hover:text-roast-accent/80 font-medium">
            ← Roast Another
          </button>
          <a href={data.url} target="_blank" rel="noopener noreferrer" className="text-roast-muted hover:text-roast-text">
            {repoName} ↗
          </a>
        </div>
      </div>

      <div className="max-w-6xl mx-auto px-4 py-12 text-center animate-fade-in">
        <ScoreRing score={data.score} size={160} />
        <h1 className="text-4xl md:text-5xl font-bold mt-6 text-roast-text">{data.headline}</h1>
        <div className="mt-4 text-2xl">
          {data.verdict_emoji} <span className="font-bold text-roast-text">{data.verdict}</span>
        </div>
        <div className="flex justify-center gap-8 mt-6 text-roast-muted">
          <div><span className="text-2xl font-bold text-roast-text">{data.files_scanned}</span> files</div>
          <div><span className="text-2xl font-bold text-roast-text">{data.total_lines.toLocaleString()}</span> lines</div>
          <div><span className="text-2xl font-bold text-roast-text">{data.issues_count}</span> issues</div>
        </div>
      </div>

      <div className="max-w-4xl mx-auto px-4 py-8">
        <div className="bg-roast-card border border-roast-border rounded-xl p-8">
          <h2 className="text-2xl font-bold mb-6 text-roast-text">The Roast</h2>
          <div className="space-y-4">
            {data.roast_lines.map((line, i) => (
              <p key={`roast-${i}`} className="text-roast-text text-lg leading-relaxed animate-slide-up" style={{ animationDelay: `${i * 100}ms` }}>
                {line}
              </p>
            ))}
          </div>
        </div>
      </div>

      <div className="max-w-6xl mx-auto px-4 py-8">
        <div className="grid md:grid-cols-2 gap-6">
          <div className="bg-roast-card border border-roast-border rounded-xl p-6">
            <h3 className="text-lg font-bold mb-4 text-roast-text">By Severity</h3>
            <div className="space-y-3">
              {Object.entries(data.severity_counts).map(([severity, count]) => (
                <div key={severity} className="flex items-center justify-between">
                  <span className="capitalize text-roast-muted">{severity}</span>
                  <div className="flex items-center gap-3">
                    <div className="w-32 h-2 bg-roast-bg rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full ${
                          severity === "high" ? "bg-red-500" : severity === "medium" ? "bg-yellow-500" : "bg-blue-500"
                        }`}
                        style={{ width: `${(count / safeIssuesCount) * 100}%` }}
                      />
                    </div>
                    <span className="text-roast-text font-medium w-8 text-right">{count}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="bg-roast-card border border-roast-border rounded-xl p-6">
            <h3 className="text-lg font-bold mb-4 text-roast-text">By Category</h3>
            <div className="space-y-3">
              {Object.entries(data.category_counts).map(([category, count]) => (
                <div key={category} className="flex items-center justify-between">
                  <span className="text-roast-muted">{category}</span>
                  <div className="flex items-center gap-3">
                    <div className="w-32 h-2 bg-roast-bg rounded-full overflow-hidden">
                      <div
                        className="h-full bg-roast-accent rounded-full"
                        style={{ width: `${(count / safeIssuesCount) * 100}%` }}
                      />
                    </div>
                    <span className="text-roast-text font-medium w-8 text-right">{count}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {data.hotspot_files.length > 0 && (
        <div className="max-w-6xl mx-auto px-4 py-8">
          <div className="bg-roast-card border border-roast-border rounded-xl p-6">
            <h3 className="text-lg font-bold mb-4 text-roast-text">Hotspot Files</h3>
            <div className="space-y-2">
              {data.hotspot_files.map((file) => (
                <div key={file.file} className="flex items-center justify-between py-2 border-b border-roast-border/50 last:border-0">
                  <span className="font-mono text-sm text-roast-text truncate max-w-xs" title={file.file}>{file.file}</span>
                  <span className="text-roast-accent font-medium shrink-0 ml-2">{file.count} issues</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      <div className="max-w-6xl mx-auto px-4 py-8">
        <div className="bg-roast-card border border-roast-border rounded-xl p-6">
          <h2 className="text-2xl font-bold mb-6 text-roast-text">All Issues</h2>
          <IssueTable issues={data.issues} />
        </div>
      </div>

      <div className="max-w-6xl mx-auto px-4 py-8 text-center">
        <h3 className="text-xl font-bold mb-4 text-roast-text">Share Your Roast</h3>
        <div className="flex justify-center">
          <ShareButtons score={data.score} repoName={repoName} roastId={data.id} />
        </div>
      </div>

      <footer className="border-t border-roast-border py-8 text-center text-roast-muted text-sm">
        <p>Generated by Roast My Code</p>
      </footer>
    </main>
  );
}
