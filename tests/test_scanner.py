"""Tests for scanner behavior."""

from roast.scanner import scan_repo


def test_scan_repo_includes_config_files_only_when_requested(tmp_path) -> None:
    (tmp_path / "app.py").write_text("print('hi')\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("# project\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")

    code_only = scan_repo(tmp_path, ["py"], max_files=10)
    with_config = scan_repo(tmp_path, ["py"], max_files=10, include_config=True)

    assert [file.path for file in code_only] == ["app.py"]
    assert {file.path for file in with_config} == {"app.py", "README.md", "pyproject.toml"}
