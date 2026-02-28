"""LLM roast generation."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import json
import os
from typing import Any

from openai import OpenAI

from roast.analyzer import AnalysisReport, Issue
from roast.scanner import FileResult


@dataclass(slots=True)
class RoastResult:
    headline: str
    roast_lines: list[str]
    verdict: str
    verdict_emoji: str


def _verdict_from_score(score: int) -> tuple[str, str]:
    if score >= 75:
        return "SHIP IT", "🚀"
    if score >= 40:
        return "NEEDS WORK", "🔨"
    return "BURN IT DOWN", "🔥"


def _severity_weight(issue: Issue) -> int:
    order = {"high": 0, "medium": 1, "low": 2}
    return order.get(issue.severity, 3)


def _top_issues(report: AnalysisReport, limit: int = 10) -> list[Issue]:
    return sorted(report.issues, key=lambda issue: (_severity_weight(issue), issue.file, issue.line or 0))[:limit]


def _worst_file(report: AnalysisReport) -> str | None:
    if not report.issues:
        return None
    counts = Counter(issue.file for issue in report.issues)
    return counts.most_common(1)[0][0]


def _sample_from_file(files: list[FileResult], target_path: str | None, max_lines: int = 30) -> str:
    if not target_path:
        return "No issues found; no worst-file sample available."
    for file in files:
        if file.path == target_path:
            return "\n".join(file.content.splitlines()[:max_lines]) or "<empty file>"
    return "Unable to locate worst file contents."


def _build_user_prompt(report: AnalysisReport, files: list[FileResult]) -> str:
    overall_score = report.scores.get("Overall", 0)
    top = _top_issues(report)
    issue_lines = [
        f"- {issue.file}:{issue.line or '-'} [{issue.severity}] {issue.description}"
        for issue in top
    ]
    issues_block = "\n".join(issue_lines) if issue_lines else "- No issues found."
    worst = _worst_file(report) or "None"
    sample = _sample_from_file(files, _worst_file(report))
    return (
        "Here is a summary of a codebase scan:\n"
        f"- Total files: {report.total_files}, Total lines: {report.total_lines}\n"
        f"- Overall score: {overall_score}/100\n"
        f"- Top issues found:\n{issues_block}\n"
        f"- Worst file: {worst}\n"
        f"- Sample of actual code from worst file:\n{sample}\n\n"
        "Generate:\n"
        "1. A one-liner headline roast\n"
        "2. 5-8 specific roast bullets\n"
        "3. A verdict: SHIP IT (score >= 75), NEEDS WORK (40-74), BURN IT DOWN (<40)\n\n"
        "Respond strictly as JSON with keys: headline, roast_lines, verdict, verdict_emoji."
    )


def _normalize_roast_payload(payload: dict[str, Any], overall_score: int) -> RoastResult:
    verdict, emoji = _verdict_from_score(overall_score)
    headline = str(payload.get("headline", "")).strip() or "Your code survived, your dignity did not."
    if len(headline.split()) > 15:
        headline = " ".join(headline.split()[:15])

    lines_raw = payload.get("roast_lines", [])
    if not isinstance(lines_raw, list):
        lines_raw = []
    roast_lines = [str(line).strip() for line in lines_raw if str(line).strip()]
    roast_lines = roast_lines[:8]
    if len(roast_lines) < 5:
        roast_lines.extend(_fallback_roast_lines(overall_score, needed=5 - len(roast_lines)))

    return RoastResult(
        headline=headline,
        roast_lines=roast_lines,
        verdict=verdict,
        verdict_emoji=emoji,
    )


def _fallback_roast_lines(overall_score: int, needed: int = 6) -> list[str]:
    pool = [
        "I found TODOs with a stronger roadmap than your architecture.",
        "Your variable names feel like keyboard smash with commit access.",
        "This repo has copy-paste confidence and production consequences.",
        "Error handling here is mostly spiritual, not technical.",
        "Half the functions read like improv, none land the punchline.",
        "The linter looked away and pretended not to know you.",
        "Magic numbers are everywhere except where logic should be.",
        "This code compiles, but so do regrets.",
    ]
    if overall_score >= 75:
        pool[0] = "The code is decent, but your TODOs still owe rent."
    elif overall_score < 40:
        pool[7] = "This codebase is one merge away from folklore."
    return pool[:needed]


def _generate_fallback_roast(report: AnalysisReport) -> RoastResult:
    overall_score = report.scores.get("Overall", 0)
    verdict, emoji = _verdict_from_score(overall_score)
    if overall_score >= 75:
        headline = "This code mostly behaves, unlike your naming choices."
    elif overall_score >= 40:
        headline = "Refactor roulette: spin once, cry twice."
    else:
        headline = "Your repo needs therapy, not another feature branch."
    return RoastResult(
        headline=headline,
        roast_lines=_fallback_roast_lines(overall_score, needed=6),
        verdict=verdict,
        verdict_emoji=emoji,
    )


def generate_roast(
    report: AnalysisReport,
    files: list[FileResult],
    model: str = "gpt-4o-mini",
    no_llm: bool = False,
) -> RoastResult:
    """Generate a roast using an LLM or deterministic fallback mode."""
    if no_llm:
        return _generate_fallback_roast(report)

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    overall_score = report.scores.get("Overall", 0)
    response = client.chat.completions.create(
        model=model,
        temperature=0.9,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a senior developer who has seen too much bad code. "
                    "You are brutally honest but funny, like a Gordon Ramsay for codebases. "
                    "Be specific, reference actual file names and issues. Never be generic. "
                    "Keep roast lines under 20 words each."
                ),
            },
            {"role": "user", "content": _build_user_prompt(report, files)},
        ],
    )
    content = response.choices[0].message.content or "{}"
    payload = json.loads(content)
    return _normalize_roast_payload(payload, overall_score)
