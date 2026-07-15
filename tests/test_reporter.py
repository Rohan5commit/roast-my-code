"""Tests for reporter helpers."""

from roast.analyzer import AnalysisReport, Issue
from roast.reporter import build_report_payload
from roast.roaster import RoastResult


def test_build_report_payload_includes_counts_and_hotspots() -> None:
    report = AnalysisReport(
        total_files=3,
        total_lines=120,
        issues=[
            Issue(file="app/main.py", line=10, category="AI Slop", severity="high", description="TODO found"),
            Issue(file="app/main.py", line=22, category="AI Slop", severity="medium", description="Magic number"),
            Issue(file="app/api.py", line=8, category="Style", severity="low", description="Missing docstring"),
        ],
        scores={"AI Slop": 78, "Code Quality": 65, "Security": 85, "Style": 92, "Overall": 81},
    )
    roast = RoastResult(
        headline="Amazingly survivable.",
        roast_lines=["Line one", "Line two", "Line three", "Line four", "Line five"],
        remediations=["Fix this", "Do that"],
        verdict="SHIP IT",
        verdict_emoji="🚀",
    )

    payload = build_report_payload(report, roast)

    assert payload["summary"]["total_issues"] == 3
    assert payload["counts"]["by_severity"]["high"] == 1
    assert payload["counts"]["by_severity"]["medium"] == 1
    assert payload["counts"]["by_severity"]["low"] == 1
    assert payload["counts"]["by_category"]["AI Slop"] == 2
    assert payload["hotspots"][0] == {"file": "app/main.py", "issue_count": 2}
    assert "brightgreen" in payload["share"]["badge_markdown"]
