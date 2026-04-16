"""Tests for CLI helpers."""

import pytest

from roast.cli import _parse_github_target, _should_fail_quality_gate, _validate_fail_under


def test_parse_github_target_supports_repo_root() -> None:
    assert _parse_github_target("https://github.com/octocat/hello-world") == (
        "octocat",
        "hello-world",
        None,
    )


def test_parse_github_target_supports_tree_ref() -> None:
    assert _parse_github_target("https://github.com/octocat/hello-world/tree/feature/demo") == (
        "octocat",
        "hello-world",
        "feature/demo",
    )


def test_parse_github_target_rejects_non_repo_paths() -> None:
    with pytest.raises(RuntimeError):
        _parse_github_target("https://github.com/octocat/hello-world/issues/1")


def test_validate_fail_under_requires_score_range() -> None:
    assert _validate_fail_under(0) == 0
    assert _validate_fail_under(100) == 100
    with pytest.raises(RuntimeError):
        _validate_fail_under(101)


def test_should_fail_quality_gate_only_when_below_threshold() -> None:
    assert not _should_fail_quality_gate(70, None)
    assert not _should_fail_quality_gate(70, 70)
    assert _should_fail_quality_gate(69, 70)
