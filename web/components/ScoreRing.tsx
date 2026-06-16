"use client";

import { useEffect, useState } from "react";

interface ScoreRingProps {
  score: number;
  size?: number;
  showLabel?: boolean;
}

export default function ScoreRing({ score, size = 120, showLabel = true }: ScoreRingProps) {
  const [animated, setAnimated] = useState(false);
  const radius = (size - 16) / 2;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset = circumference - (score / 100) * circumference;

  const getColor = (score: number) => {
    if (score >= 75) return { stroke: "#3fb950", glow: "glow-green", label: "text-green-400" };
    if (score >= 40) return { stroke: "#d29922", glow: "glow-yellow", label: "text-yellow-400" };
    return { stroke: "#f85149", glow: "glow-red", label: "text-red-400" };
  };

  const color = getColor(score);

  useEffect(() => {
    const timer = setTimeout(() => setAnimated(true), 100);
    return () => clearTimeout(timer);
  }, []);

  return (
    <div className="relative inline-flex items-center justify-center">
      <svg
        width={size}
        height={size}
        className={`score-ring ${color.glow}`}
        role="img"
        aria-label={`Code quality score: ${score} out of 100`}
      >
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="#30363d"
          strokeWidth="8"
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={color.stroke}
          strokeWidth="8"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={animated ? strokeDashoffset : circumference}
          className="transition-all duration-1500 ease-out"
        />
      </svg>
      {showLabel && (
        <div className="absolute inset-0 flex flex-col items-center justify-center" aria-hidden="true">
          <span className={`text-3xl font-bold ${color.label}`}>{score}</span>
          <span className="text-xs text-roast-muted">/100</span>
        </div>
      )}
    </div>
  );
}
