"use client";

import { useState } from "react";

interface RoastInputProps {
  onSubmit: (url: string) => void;
  isLoading: boolean;
}

const GITHUB_URL_REGEX = /^https?:\/\/(www\.)?github\.com\/[^/]+\/[^/]+/;

export default function RoastInput({ onSubmit, isLoading }: RoastInputProps) {
  const [url, setUrl] = useState("");
  const [urlError, setUrlError] = useState<string | null>(null);

  const validateAndSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = url.trim();
    if (!trimmed) return;

    if (!GITHUB_URL_REGEX.test(trimmed)) {
      setUrlError("Please enter a valid GitHub repo URL (e.g. https://github.com/owner/repo)");
      return;
    }

    setUrlError(null);
    onSubmit(trimmed);
  };

  return (
    <form onSubmit={validateAndSubmit} className="max-w-2xl mx-auto" noValidate>
      <div className="flex gap-3">
        <div className="flex-1 relative">
          <label htmlFor="github-url" className="sr-only">GitHub repository URL</label>
          <input
            id="github-url"
            type="url"
            value={url}
            onChange={(e) => { setUrl(e.target.value); setUrlError(null); }}
            placeholder="https://github.com/owner/repo"
            className="w-full px-5 py-4 bg-roast-card border border-roast-border rounded-xl text-roast-text placeholder-roast-muted focus:outline-none focus:border-roast-accent focus:ring-1 focus:ring-roast-accent transition-colors text-lg"
            disabled={isLoading}
            aria-describedby={urlError ? "url-error" : undefined}
            aria-invalid={urlError ? "true" : undefined}
          />
        </div>
        <button
          type="submit"
          disabled={isLoading || !url.trim()}
          className="px-8 py-4 bg-roast-accent hover:bg-roast-accent/90 disabled:bg-roast-accent/50 text-white font-bold rounded-xl transition-all text-lg disabled:cursor-not-allowed"
        >
          {isLoading ? (
            <span className="flex items-center gap-2">
              <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
              </svg>
              Roasting...
            </span>
          ) : (
            "Roast This Repo"
          )}
        </button>
      </div>
      {urlError && (
        <p id="url-error" className="text-red-400 text-sm mt-2 text-center" role="alert">{urlError}</p>
      )}
      <p className="text-center text-roast-muted text-sm mt-3">
        Supports public GitHub repos. No installation required.
      </p>
    </form>
  );
}
