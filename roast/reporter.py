"""Terminal, HTML, and JSON reporting."""

from __future__ import annotations

from collections import Counter
import json
from math import pi
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from roast.analyzer import AnalysisReport, Issue
from roast.roaster import RoastResult
from roast.history import get_history

HEADER_ART = r"""
██████╗  ██████╗  █████╗ ███████╗████████╗
██╔══██╗██╔═══██╗██╔══██╗██╔════╝╚══██╔══╝
██████╔╝██║   ██║███████║███████╗   ██║
██╔══██╗██║   ██║██╔══██║╚════██║   ██║
██║  ██║╚██████╔╝██║  ██║███████║   ██║
╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═╝╚══════╝   ╚═╝
"""


def _severity_order(issue: Issue) -> int:
    return {"high": 0, "medium": 1, "low": 2}.get(issue.severity, 3)


def _score_color(score: int) -> str:
    if score >= 75:
        return "green"
    if score >= 40:
        return "yellow"
    return "red"


def _badge_markdown_color(score: int) -> str:
    if score >= 75:
        return "brightgreen"
    if score >= 40:
        return "yellow"
    return "red"


def _score_bar(score: int, width: int = 24) -> str:
    filled = int((score / 100) * width)
    empty = width - filled
    color = _score_color(score)
    return f"[{color}]{'█' * filled}[/]{'░' * empty}"


def _issue_counts_by_severity(issues: list[Issue]) -> dict[str, int]:
    counts = {"high": 0, "medium": 0, "low": 0}
    for issue in issues:
        counts[issue.severity] = counts.get(issue.severity, 0) + 1
    return counts


def _issue_counts_by_category(issues: list[Issue]) -> dict[str, int]:
    ordered = Counter(issue.category for issue in issues)
    return dict(sorted(ordered.items(), key=lambda item: (-item[1], item[0].lower())))


def _hotspot_files(issues: list[Issue], limit: int = 5) -> list[dict[str, int | str]]:
    ranked = Counter(issue.file for issue in issues).most_common(limit)
    return [{"file": file_path, "issue_count": count} for file_path, count in ranked]


def build_report_payload(report: AnalysisReport, roast: RoastResult) -> dict[str, object]:
    overall_score = report.scores.get("Overall", 0)
    severity_counts = _issue_counts_by_severity(report.issues)
    category_counts = _issue_counts_by_category(report.issues)
    hotspots = _hotspot_files(report.issues)
    badge_color = _badge_markdown_color(overall_score)
    history = get_history()
    trend = [h["overall_score"] for h in history]

    return {
        "summary": {
            "total_files": report.total_files,
            "total_lines": report.total_lines,
            "total_issues": len(report.issues),
            "scores": report.scores,
        },
        "trend": trend,
        "counts": {
            "by_severity": severity_counts,
            "by_category": category_counts,
        },
        "hotspots": hotspots,
        "roast": {
            "headline": roast.headline,
            "roast_lines": roast.roast_lines,
            "verdict": roast.verdict,
            "verdict_emoji": roast.verdict_emoji,
        },
        "share": {
            "badge_markdown": f"![Roast Score](https://img.shields.io/badge/Roast_Score-{overall_score}-{badge_color})",
        },
        "issues": [
            {
                "file": issue.file,
                "line": issue.line,
                "category": issue.category,
                "severity": issue.severity,
                "description": issue.description,
            }
            for issue in sorted(report.issues, key=lambda item: (_severity_order(item), item.file, item.line or 0))
        ],
    }


def render_terminal_report(
    report: AnalysisReport,
    roast: RoastResult,
    output_path: str | Path,
    console: Console | None = None,
) -> None:
    """Render the terminal scorecard with Rich."""
    console = console or Console()
    console.print(Panel.fit(Text(HEADER_ART, style="bold magenta"), title="🔥 ROAST-MY-CODE", border_style="red"))

    score_table = Table(title="Score Card", box=box.SIMPLE_HEAVY)
    score_table.add_column("Category", style="bold")
    score_table.add_column("Score", justify="right")
    score_table.add_column("Bar Chart")
    for category in ("AI Slop", "Code Quality", "Style", "Overall"):
        score = report.scores.get(category, 0)
        score_table.add_row(
            category,
            f"[{_score_color(score)}]{score}[/]",
            _score_bar(score),
        )
    console.print(score_table)

    severity_counts = _issue_counts_by_severity(report.issues)
    category_counts = _issue_counts_by_category(report.issues)
    hotspots = _hotspot_files(report.issues, limit=3)
    category_summary = ", ".join(f"{name}: {count}" for name, count in category_counts.items()) or "No categories to summarize."
    hotspot_summary = ", ".join(f"{item['file']} ({item['issue_count']})" for item in hotspots) or "No hotspots found."
    console.print(
        Panel.fit(
            Text.from_markup(
                f"[bold red]High:[/] {severity_counts['high']}  [bold yellow]Medium:[/] {severity_counts['medium']}  [bold green]Low:[/] {severity_counts['low']}\n"
                f"[bold]Categories:[/] {category_summary}\n"
                f"[bold]Hotspots:[/] {hotspot_summary}"
            ),
            title="Summary",
            border_style="cyan",
        )
    )

    issues_table = Table(title="Top 10 Issues", box=box.SIMPLE)
    issues_table.add_column("File", overflow="fold")
    issues_table.add_column("Line", justify="right", width=6)
    issues_table.add_column("Severity", width=8)
    issues_table.add_column("Description", overflow="fold")

    top_issues = sorted(report.issues, key=lambda issue: (_severity_order(issue), issue.file, issue.line or 0))[:10]
    if not top_issues:
        issues_table.add_row("-", "-", "-", "No issues found. Miracles happen.")
    for issue in top_issues:
        row_style = {"high": "bold red", "medium": "yellow", "low": "white"}.get(issue.severity, "white")
        issues_table.add_row(
            issue.file,
            str(issue.line) if issue.line is not None else "-",
            issue.severity.upper(),
            issue.description,
            style=row_style,
        )
    console.print(issues_table)

    console.print(Panel.fit(Text(roast.headline, style="bold yellow"), title="Roast Headline", border_style="yellow"))
    for line in roast.roast_lines:
        console.print(f"🔥 {line}")

    verdict_color = {"SHIP IT": "green", "NEEDS WORK": "yellow", "BURN IT DOWN": "red"}.get(roast.verdict, "white")
    verdict_text = Text(f"{roast.verdict_emoji} {roast.verdict} {roast.verdict_emoji}", style=f"bold {verdict_color}")
    console.print(Panel.fit(verdict_text, title="Verdict", border_style=verdict_color))

    console.print(f"\n[bold cyan]HTML report saved to: {Path(output_path)}[/]")

    overall_score = report.scores.get("Overall", 0)
    tweet_text = f"My+codebase+scored+{overall_score}/100+🔥+roast-my-code+github.com/Rohan5commit/roast-my-code"
    tweet_url = f"https://twitter.com/intent/tweet?text={tweet_text}"
    console.print(f"\n[bold magenta]Post your score → [link={tweet_url}]{tweet_url}[/link][/]")


def _badge_color(score: int) -> str:
    if score >= 75:
        return "#2ea043"
    if score >= 40:
        return "#d29922"
    return "#f85149"


def export_html_report(
    report: AnalysisReport,
    roast: RoastResult,
    output_path: str | Path,
) -> Path:
    """Render a single self-contained HTML report."""
    template_dir = Path(__file__).resolve().parent / "templates"
    env = Environment(
        loader=FileSystemLoader(str(template_dir)),
        autoescape=select_autoescape(enabled_extensions=("html",)),
    )
    template = env.get_template("report.html")

    payload = build_report_payload(report, roast)
    overall_score = report.scores.get("Overall", 0)
    radius = 90
    circumference = 2 * pi * radius
    dash_offset = circumference * (1 - (overall_score / 100))
    
    rendered = template.render(
        payload=payload,
        report=report,
        roast=roast,
        overall_score=overall_score,
        score_items=[
            {
                "name": "AI Slop",
                "value": report.scores.get("AI Slop", 0),
                "color": _badge_color(report.scores.get("AI Slop", 0)),
            },
            {
                "name": "Code Quality",
                "value": report.scores.get("Code Quality", 0),
                "color": _badge_color(report.scores.get("Code Quality", 0)),
            },
            {
                "name": "Style",
                "value": report.scores.get("Style", 0),
                "color": _badge_color(report.scores.get("Style", 0)),
            },
        ],
        issues=payload["issues"],
        severity_counts=payload["counts"]["by_severity"],
        category_counts=payload["counts"]["by_category"],
        hotspots=payload["hotspots"],
        total_issues=payload["summary"]["total_issues"],
        score_ring_circumference=f"{circumference:.2f}",
        score_ring_offset=f"{dash_offset:.2f}",
        overall_color=_badge_color(overall_score),
        badge_markdown=payload["share"]["badge_markdown"],
    )

    output = Path(output_path).expanduser().resolve()
    output.write_text(rendered, encoding="utf-8")
    return output


def export_json_report(
    report: AnalysisReport,
    roast: RoastResult,
    output_path: str | Path,
) -> Path:
    """Export a machine-readable JSON report."""
    payload = build_report_payload(report, roast)
    output = Path(output_path).expanduser().resolve()
    output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return output
