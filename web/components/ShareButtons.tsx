"use client";

import { useState, useEffect } from "react";

interface ShareButtonsProps {
  score: number;
  repoName: string;
  roastId: string;
}

export default function ShareButtons({ score, repoName, roastId }: ShareButtonsProps) {
  const [copied, setCopied] = useState(false);
  const [shareUrl, setShareUrl] = useState("");

  useEffect(() => {
    setShareUrl(`${window.location.origin}/roast/${roastId}`);
  }, [roastId]);

  const tweetText = `I just got my code roasted and scored ${score}/100!  ${repoName} #RoastMyCode`;

  const copyLink = async () => {
    try {
      await navigator.clipboard.writeText(shareUrl);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      const textarea = document.createElement("textarea");
      textarea.value = shareUrl;
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand("copy");
      document.body.removeChild(textarea);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <div className="flex flex-wrap gap-3 justify-center">
      <a
        href={`https://x.com/intent/tweet?text=${encodeURIComponent(tweetText)}`}
        target="_blank"
        rel="noopener noreferrer"
        className="px-4 py-2 bg-[#1DA1F2] hover:bg-[#1a8cd8] text-white rounded-lg font-medium transition-colors"
      >
        Tweet This
      </a>
      <button
        onClick={copyLink}
        disabled={!shareUrl}
        className="px-4 py-2 bg-roast-card border border-roast-border hover:border-roast-accent text-roast-text rounded-lg font-medium transition-colors disabled:opacity-50"
      >
        {copied ? "Copied!" : "Copy Link"}
      </button>
    </div>
  );
}
