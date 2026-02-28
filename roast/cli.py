"""CLI entrypoint for roast-my-code."""

from __future__ import annotations

from contextlib import nullcontext
import logging
import os
from pathlib import Path
import tempfile

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from roast.analyzer import analyze
from roast.reporter import export_html_report, render_terminal_report
from roast.roaster import generate_roast
from roast.scanner import scan_repo

app = typer.Typer(
    help="Brutally honest AI-powered code quality roaster.",
    add_completion=False,
    no_args_is_help=True,
)
console = Console()
LOGGER = logging.getLogger(__name__)


def _is_github_url(value: str) -> bool:
    return value.startswith("https://github.com")


def _resolve_scan_target(path_or_url: str) -> tuple[Path, tempfile.TemporaryDirectory[str] | None]:
    if _is_github_url(path_or_url):
        from git import Repo
        from git.exc import GitCommandError

        temp_dir = tempfile.TemporaryDirectory(prefix="roast-my-code-")
        try:
            Repo.clone_from(path_or_url, temp_dir.name)
        except GitCommandError as exc:
            temp_dir.cleanup()
            raise RuntimeError(f"Failed to clone GitHub URL: {exc}") from exc
        return Path(temp_dir.name), temp_dir

    local_path = Path(path_or_url).expanduser().resolve()
    if not local_path.exists():
        raise RuntimeError(f"Path does not exist: {local_path}")
    if not local_path.is_dir():
        raise RuntimeError(f"Path is not a directory: {local_path}")
    return local_path, None


def _parse_extensions(raw_extensions: str) -> list[str]:
    parsed = [ext.strip() for ext in raw_extensions.split(",") if ext.strip()]
    return parsed or ["py", "js", "ts", "jsx", "tsx"]


@app.command()
def roast(
    path_or_url: str = typer.Argument(..., metavar="PATH_OR_URL"),
    output: str = typer.Option(
        "./roast-report.html",
        "--output",
        "-o",
        help="Save HTML report to this path.",
    ),
    model: str = typer.Option("gpt-4o-mini", "--model", help="LLM model to use."),
    no_llm: bool = typer.Option(False, "--no-llm", help="Run static analysis only, skip LLM roast."),
    extensions: str = typer.Option(
        "py,js,ts,jsx,tsx",
        "--extensions",
        help="Comma-separated file extensions to scan.",
    ),
    max_files: int = typer.Option(50, "--max-files", help="Max files to scan."),
) -> None:
    """Roast a local repository path or GitHub URL."""
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
    ext_list = _parse_extensions(extensions)

    if not no_llm and not os.getenv("OPENAI_API_KEY"):
        console.print(
            Panel(
                "[bold red]OPENAI_API_KEY is not set.[/]\n"
                "Set it first, for example:\n"
                "[cyan]export OPENAI_API_KEY='your-key-here'[/]\n"
                "Or run with [cyan]--no-llm[/] to skip AI roast generation.",
                title="Configuration Error",
                border_style="red",
            )
        )
        raise typer.Exit(code=1)

    try:
        target_path, temp_dir = _resolve_scan_target(path_or_url)
    except RuntimeError as exc:
        console.print(Panel(str(exc), title="Input Error", border_style="red"))
        raise typer.Exit(code=1)

    context = nullcontext() if temp_dir is None else temp_dir

    with context:
        with Progress(SpinnerColumn(), TextColumn("[bold cyan]{task.description}"), transient=True) as progress:
            task_id = progress.add_task("Scanning repository...", total=None)
            files = scan_repo(target_path, ext_list, max_files=max_files)
            progress.update(task_id, description=f"Running static analysis on {len(files)} files...")
            report = analyze(files)

        if not files:
            console.print("[yellow]No matching readable files were found. Report will be mostly empty.[/yellow]")

        if no_llm:
            roast_result = generate_roast(report, files, model=model, no_llm=True)
        else:
            with Progress(SpinnerColumn(), TextColumn("[bold magenta]{task.description}"), transient=True) as progress:
                progress.add_task("Calling LLM for roast generation...", total=None)
                try:
                    roast_result = generate_roast(report, files, model=model, no_llm=False)
                except Exception as exc:  # noqa: BLE001
                    LOGGER.warning("LLM call failed (%s). Falling back to --no-llm mode.", exc)
                    console.print(
                        "[yellow]LLM roast failed. Falling back to static roast mode (--no-llm).[/yellow]"
                    )
                    roast_result = generate_roast(report, files, model=model, no_llm=True)

        export_html_report(report, roast_result, output_path=output)
        render_terminal_report(report, roast_result, output_path=output, console=console)


if __name__ == "__main__":
    app()
