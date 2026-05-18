"""CLI entrypoint for roast-my-code."""

from __future__ import annotations

from contextlib import nullcontext
import io
import logging
import os
from pathlib import Path
import tempfile
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from datetime import datetime
import zipfile

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from roast.analyzer import analyze
from roast.reporter import export_html_report, export_json_report, render_terminal_report
from roast.roaster import DEFAULT_GROQ_MODEL, DEFAULT_NIM_MODEL, generate_roast
from roast.scanner import scan_repo
from roast.history import save_history

app = typer.Typer(
    help="Brutally honest AI-powered code quality roaster.",
    add_completion=False,
    no_args_is_help=True,
)
console = Console()
LOGGER = logging.getLogger(__name__)
VALID_PROVIDERS = {"auto", "groq", "nim", "openai", "none"}
GITHUB_API_BASE = "https://api.github.com"


def _parse_github_target(value: str) -> tuple[str, str, str | None] | None:
    parsed = urlparse(value)
    if parsed.scheme != "https" or parsed.netloc != "github.com":
        return None

    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) < 2:
        raise RuntimeError("GitHub URL must point to a repository, e.g. https://github.com/owner/repo")

    owner = parts[0]
    repo = parts[1].removesuffix(".git")
    if len(parts) == 2:
        return owner, repo, None
    if len(parts) >= 4 and parts[2] == "tree":
        ref = "/".join(parts[3:]).strip() or None
        return owner, repo, ref
    raise RuntimeError("GitHub URL must point to a repository root or tree ref.")


def _github_headers() -> dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "roast-my-code",
    }
    github_token = os.getenv("GITHUB_TOKEN")
    if github_token:
        headers["Authorization"] = f"Bearer {github_token}"
    return headers


def _extract_archive_root(temp_dir_path: Path) -> Path:
    extracted_dirs = [child for child in temp_dir_path.iterdir() if child.is_dir()]
    if len(extracted_dirs) != 1:
        raise RuntimeError("GitHub archive had an unexpected layout.")
    return extracted_dirs[0]


def _download_github_archive(
    owner: str,
    repo: str,
    ref: str | None,
    temp_dir: tempfile.TemporaryDirectory[str],
) -> Path:
    archive_suffix = f"/{ref}" if ref else ""
    archive_url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/zipball{archive_suffix}"
    request = Request(archive_url, headers=_github_headers())

    try:
        with urlopen(request) as response:
            archive_bytes = response.read()
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        if exc.code == 404:
            hint = " If this repo is private, set GITHUB_TOKEN before running the CLI."
        else:
            hint = ""
        raise RuntimeError(f"Failed to download GitHub archive ({exc.code}).{hint} {detail}".strip()) from exc
    except URLError as exc:
        raise RuntimeError(f"Failed to reach GitHub archive endpoint: {exc.reason}") from exc

    try:
        with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
            archive.extractall(temp_dir.name)
    except zipfile.BadZipFile as exc:
        raise RuntimeError("GitHub archive download was not a valid zip file.") from exc

    return _extract_archive_root(Path(temp_dir.name))


def _resolve_scan_target(path_or_url: str) -> tuple[Path, tempfile.TemporaryDirectory[str] | None]:
    github_target = _parse_github_target(path_or_url)
    if github_target:
        temp_dir = tempfile.TemporaryDirectory(prefix="roast-my-code-")
        try:
            target_path = _download_github_archive(*github_target, temp_dir=temp_dir)
        except RuntimeError:
            temp_dir.cleanup()
            raise
        return target_path, temp_dir

    local_path = Path(path_or_url).expanduser().resolve()
    if not local_path.exists():
        raise RuntimeError(f"Path does not exist: {local_path}")
    if not local_path.is_dir():
        raise RuntimeError(f"Path is not a directory: {local_path}")
    return local_path, None


def _parse_extensions(raw_extensions: str) -> list[str]:
    parsed = [ext.strip() for ext in raw_extensions.split(",") if ext.strip()]
    return parsed or ["py", "js", "ts", "jsx", "tsx"]


def _provider_has_key(provider: str) -> bool:
    if provider == "groq":
        return bool(os.getenv("GROQ_API_KEY"))
    if provider == "nim":
        return bool(os.getenv("NVIDIA_NIM_API_KEY") or os.getenv("NIM_API_KEY"))
    if provider == "openai":
        return bool(os.getenv("OPENAI_API_KEY"))
    return False


def _validate_provider(value: str, option_name: str) -> str:
    normalized = value.strip().lower()
    if normalized not in VALID_PROVIDERS:
        raise RuntimeError(
            f"Invalid {option_name}: {value}. Use one of: auto, groq, nim, openai, none."
        )
    return normalized


def _validate_fail_under(value: int | None) -> int | None:
    if value is None:
        return None
    if not 0 <= value <= 100:
        raise RuntimeError("fail-under must be between 0 and 100.")
    return value


def _should_fail_quality_gate(overall_score: int, fail_under: int | None) -> bool:
    return fail_under is not None and overall_score < fail_under


def _has_any_configured_llm_key(provider: str, backup_provider: str) -> bool:
    if provider == "auto":
        return any(_provider_has_key(name) for name in ("groq", "nim", "openai"))
    providers = [provider]
    if backup_provider != "none":
        providers.append(backup_provider)
    return any(_provider_has_key(name) for name in providers)


@app.command()
def roast(
    path_or_url: str = typer.Argument(..., metavar="PATH_OR_URL"),
    output: str = typer.Option(
        "./roast-report.html",
        "--output",
        "-o",
        help="Save HTML report to this path.",
    ),
    json_output: str | None = typer.Option(
        None,
        "--json-output",
        help="Save JSON report to this path.",
    ),
    model: str = typer.Option(
        DEFAULT_GROQ_MODEL,
        "--model",
        help="Primary LLM model (default tuned for Groq free tier).",
    ),
    provider: str = typer.Option(
        "auto",
        "--provider",
        help="Primary provider: auto, groq, nim, openai, none.",
    ),
    backup_provider: str = typer.Option(
        "nim",
        "--backup-provider",
        help="Backup provider: none, nim, groq, openai.",
    ),
    backup_model: str = typer.Option(
        DEFAULT_NIM_MODEL,
        "--backup-model",
        help="Backup provider model.",
    ),
    no_llm: bool = typer.Option(False, "--no-llm", help="Run static analysis only, skip LLM roast."),
    extensions: str = typer.Option(
        "py,js,ts,jsx,tsx",
        "--extensions",
        help="Comma-separated file extensions to scan.",
    ),
    include_config: bool = typer.Option(
        False,
        "--include-config",
        help="Include config and documentation files like .toml, .yml, and .md.",
    ),
    max_files: int = typer.Option(50, "--max-files", help="Max files to scan."),
    fail_under: int | None = typer.Option(
        None,
        "--fail-under",
        help="Exit with code 1 if the overall score falls below this threshold.",
    ),
) -> None:
    """Roast a local repository path or GitHub URL."""
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
    ext_list = _parse_extensions(extensions)

    try:
        provider = _validate_provider(provider, "provider")
        backup_provider = _validate_provider(backup_provider, "backup_provider")
        fail_under = _validate_fail_under(fail_under)
    except RuntimeError as exc:
        console.print(Panel(str(exc), title="Configuration Error", border_style="red"))
        raise typer.Exit(code=1)

    if provider == "none":
        provider = "auto"

    if not no_llm and not _has_any_configured_llm_key(provider, backup_provider):
        console.print(
            Panel(
                "[bold red]No LLM API keys found.[/]\n"
                "Set at least one:\n"
                "[cyan]export GROQ_API_KEY='...'[/cyan] (recommended free primary)\n"
                "[cyan]export NVIDIA_NIM_API_KEY='...'[/cyan] (recommended backup)\n"
                "[cyan]export OPENAI_API_KEY='...'[/cyan] (optional)\n"
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
            files = scan_repo(target_path, ext_list, max_files=max_files, include_config=include_config)
            progress.update(task_id, description=f"Running static analysis on {len(files)} files...")
            report = analyze(files)

        if not files:
            console.print("[yellow]No matching readable files were found. Report will be mostly empty.[/yellow]")

        if no_llm:
            roast_result = generate_roast(report, files, no_llm=True)
        else:
            with Progress(SpinnerColumn(), TextColumn("[bold magenta]{task.description}"), transient=True) as progress:
                progress.add_task("Calling LLM for roast generation...", total=None)
                try:
                    roast_result = generate_roast(
                        report,
                        files,
                        model=model,
                        no_llm=False,
                        provider=provider,
                        backup_provider=backup_provider,
                        backup_model=backup_model,
                    )
                except Exception as exc:  # noqa: BLE001
                    LOGGER.warning("LLM call failed (%s). Falling back to --no-llm mode.", exc)
                    console.print(
                        "[yellow]LLM roast failed. Falling back to static roast mode (--no-llm).[/yellow]"
                    )
                    roast_result = generate_roast(report, files, no_llm=True)

        export_html_report(report, roast_result, output_path=output)
        if json_output:
            export_json_report(report, roast_result, output_path=json_output)
        render_terminal_report(report, roast_result, output_path=output, console=console)
        
        # Save to history for trend tracking
        save_history({
            "timestamp": datetime.now().isoformat(),
            "scores": report.scores,
            "overall_score": report.scores.get("Overall", 0),
            "verdict": roast_result.verdict,
        })

        if json_output:
            console.print(f"[bold cyan]JSON report saved to: {Path(json_output).expanduser()}[/]")

        overall_score = report.scores.get("Overall", 0)
        if _should_fail_quality_gate(overall_score, fail_under):
            console.print(
                Panel(
                    f"Overall score {overall_score} is below required threshold {fail_under}.",
                    title="Quality Gate Failed",
                    border_style="red",
                )
            )
            raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
