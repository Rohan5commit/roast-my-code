"""LLM roast generation."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import json
import os
import re
from typing import Any, Literal

from openai import OpenAI

from roast.analyzer import AnalysisReport, Issue
from roast.scanner import FileResult

Provider = Literal["auto", "groq", "nim", "openai", "none"]

DEFAULT_PRIMARY_PROVIDER = "groq"
DEFAULT_BACKUP_PROVIDER = "nim"
DEFAULT_GROQ_MODEL = "llama-3.3-70b-versatile"
DEFAULT_GROQ_FAST_MODEL = "llama-3.1-8b-instant"
DEFAULT_NIM_MODEL = "microsoft/phi-4-mini-instruct"
DEFAULT_OPENAI_MODEL = "gpt-4o-mini"


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


def _provider_api_key(provider: Provider) -> str | None:
    if provider == "groq":
        return os.getenv("GROQ_API_KEY")
    if provider == "nim":
        return os.getenv("NVIDIA_NIM_API_KEY") or os.getenv("NIM_API_KEY")
    if provider == "openai":
        return os.getenv("OPENAI_API_KEY")
    return None


def _provider_base_url(provider: Provider) -> str | None:
    if provider == "groq":
        return "https://api.groq.com/openai/v1"
    if provider == "nim":
        return "https://integrate.api.nvidia.com/v1"
    return None


def _default_model_for_provider(provider: Provider) -> str:
    if provider == "groq":
        return DEFAULT_GROQ_MODEL
    if provider == "nim":
        return DEFAULT_NIM_MODEL
    return DEFAULT_OPENAI_MODEL


def _extract_json_payload(content: str) -> dict[str, Any]:
    text = content.strip()
    try:
        payload = json.loads(text)
        if isinstance(payload, dict):
            return payload
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        raise ValueError("Model response was not valid JSON.")
    payload = json.loads(match.group(0))
    if not isinstance(payload, dict):
        raise ValueError("Model JSON payload must be an object.")
    return payload


def _build_provider_plan(
    provider: Provider,
    model: str | None,
    backup_provider: Provider,
    backup_model: str | None,
) -> list[tuple[Provider, str]]:
    plan: list[tuple[Provider, str]] = []

    if provider == "auto":
        plan = [
            ("groq", model or DEFAULT_GROQ_MODEL),
            ("groq", DEFAULT_GROQ_FAST_MODEL),
            ("nim", backup_model or DEFAULT_NIM_MODEL),
            ("openai", DEFAULT_OPENAI_MODEL),
        ]
    else:
        plan = [(provider, model or _default_model_for_provider(provider))]
        if backup_provider not in {"none", provider}:
            plan.append((backup_provider, backup_model or _default_model_for_provider(backup_provider)))

    seen: set[tuple[Provider, str]] = set()
    deduped: list[tuple[Provider, str]] = []
    for item in plan:
        if item in seen:
            continue
        seen.add(item)
        deduped.append(item)
    return deduped


def _call_roast_llm(
    provider: Provider,
    model: str,
    report: AnalysisReport,
    files: list[FileResult],
) -> RoastResult:
    api_key = _provider_api_key(provider)
    if not api_key:
        raise RuntimeError(f"Missing API key for provider '{provider}'.")

    base_url = _provider_base_url(provider)
    if base_url:
        client = OpenAI(api_key=api_key, base_url=base_url)
    else:
        client = OpenAI(api_key=api_key)

    overall_score = report.scores.get("Overall", 0)
    response = client.chat.completions.create(
        model=model,
        temperature=0.8,
        max_tokens=500,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a senior developer who has seen too much bad code. "
                    "You are brutally honest but funny, like a Gordon Ramsay for codebases. "
                    "Be specific, reference actual file names and issues. Never be generic. "
                    "Keep roast lines under 20 words each. "
                    "Return strict JSON only."
                ),
            },
            {"role": "user", "content": _build_user_prompt(report, files)},
        ],
    )
    content = response.choices[0].message.content or "{}"
    payload = _extract_json_payload(content)
    return _normalize_roast_payload(payload, overall_score)


def generate_roast(
    report: AnalysisReport,
    files: list[FileResult],
    model: str | None = None,
    no_llm: bool = False,
    provider: Provider = "auto",
    backup_provider: Provider = DEFAULT_BACKUP_PROVIDER,
    backup_model: str | None = None,
) -> RoastResult:
    """Generate a roast using an LLM or deterministic fallback mode."""
    if no_llm:
        return _generate_fallback_roast(report)

    plan = _build_provider_plan(provider, model, backup_provider, backup_model)
    errors: list[str] = []

    for provider_name, model_name in plan:
        try:
            return _call_roast_llm(provider_name, model_name, report, files)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{provider_name}:{model_name} -> {exc}")

    raise RuntimeError("All LLM providers failed. " + " | ".join(errors))