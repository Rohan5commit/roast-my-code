"""Tests for analyzer module."""

from roast.analyzer import AI_SLOP, CODE_QUALITY, STYLE, analyze
from roast.scanner import FileResult


def test_todo_comments_generate_ai_slop_issues() -> None:
    file = FileResult(
        path="app/main.py",
        content=(
            "# TODO: clean this\n"
            "x = 1\n"
            "# FIXME: replace later\n"
            "y = 2\n"
            "# HACK: temporary workaround\n"
        ),
        language="python",
        line_count=5,
    )
    report = analyze([file])
    todo_issues = [
        issue
        for issue in report.issues
        if issue.category == AI_SLOP and "TODO/FIXME/HACK marker" in issue.description
    ]
    assert len(todo_issues) == 3


def test_function_over_50_lines_generates_code_quality_issue() -> None:
    long_body = "\n".join("    x += 1" for _ in range(51))
    content = f"def massive_function():\n    x = 0\n{long_body}\n    return x\n"
    file = FileResult(
        path="app/logic.py",
        content=content,
        language="python",
        line_count=content.count("\n"),
    )
    report = analyze([file])
    long_fn_issues = [
        issue
        for issue in report.issues
        if issue.category == CODE_QUALITY and "exceeds 50 lines" in issue.description
    ]
    assert len(long_fn_issues) == 1


def test_scores_are_clamped_to_zero_minimum() -> None:
    slop_lines = "\n".join("# TODO: fix me" for _ in range(20))
    file = FileResult(
        path="bad/file.py",
        content=slop_lines,
        language="python",
        line_count=20,
    )
    report = analyze([file])
    assert report.scores[AI_SLOP] == 0
    assert report.scores[CODE_QUALITY] >= 0
    assert report.scores[STYLE] >= 0
    assert report.scores["Overall"] >= 0


def test_empty_files_are_handled_without_error() -> None:
    file = FileResult(
        path="empty.py",
        content="",
        language="python",
        line_count=0,
    )
    report = analyze([file])
    assert report.total_files == 1
    assert report.total_lines == 0
    assert report.issues == []
