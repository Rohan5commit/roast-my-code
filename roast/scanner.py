"""Repository scanning utilities."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import logging
from typing import Iterable

LOGGER = logging.getLogger(__name__)

SKIP_DIRS = {"node_modules", ".git", "__pycache__", "dist", "build", "venv", ".venv"}
CONFIG_EXTENSIONS = {
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".ini",
    ".cfg",
    ".md",
}

LANGUAGE_BY_EXTENSION = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".jsx": "javascript",
    ".tsx": "typescript",
    ".java": "java",
    ".go": "go",
    ".rs": "rust",
    ".rb": "ruby",
    ".php": "php",
    ".c": "c",
    ".cpp": "cpp",
    ".h": "c-header",
}


@dataclass(slots=True)
class FileResult:
    path: str
    content: str
    language: str
    line_count: int


def _normalize_extensions(extensions: Iterable[str]) -> set[str]:
    normalized: set[str] = set()
    for ext in extensions:
        clean = ext.strip().lower()
        if not clean:
            continue
        if not clean.startswith("."):
            clean = f".{clean}"
        normalized.add(clean)
    return normalized


def _is_binary_file(path: Path) -> bool:
    try:
        with path.open("rb") as fh:
            chunk = fh.read(4096)
    except OSError:
        return True
    return b"\x00" in chunk


def _infer_language(path: Path) -> str:
    ext = path.suffix.lower()
    return LANGUAGE_BY_EXTENSION.get(ext, ext.lstrip(".") or "text")


def _is_config_file(path: Path) -> bool:
    if path.suffix.lower() in CONFIG_EXTENSIONS:
        return True
    return path.name.lower() in {
        "package-lock.json",
        "yarn.lock",
        "pnpm-lock.yaml",
        "poetry.lock",
        "pylintrc",
        "eslint.config.js",
    }


def _should_skip_path(path: Path) -> bool:
    lowered_parts = {part.lower() for part in path.parts}
    if lowered_parts & SKIP_DIRS:
        return True
    name = path.name.lower()
    return name == ".env" or name.startswith(".env.")


def scan_repo(path: str | Path, extensions: Iterable[str], max_files: int) -> list[FileResult]:
    """Scan a repository path and return parsed source files."""
    root = Path(path).expanduser().resolve()
    ext_filter = _normalize_extensions(extensions)
    candidates: list[tuple[int, Path]] = []

    for file_path in root.rglob("*"):
        if not file_path.is_file():
            continue
        if _should_skip_path(file_path.relative_to(root)):
            continue
        if ext_filter and file_path.suffix.lower() not in ext_filter:
            continue
        priority = 1 if _is_config_file(file_path) else 0
        candidates.append((priority, file_path))

    candidates.sort(key=lambda item: (item[0], str(item[1]).lower()))
    results: list[FileResult] = []

    for _, file_path in candidates:
        if len(results) >= max_files:
            break
        relative_path = file_path.relative_to(root)

        if _is_binary_file(file_path):
            LOGGER.warning("Skipping binary file: %s", relative_path)
            continue

        try:
            content = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            LOGGER.warning("Skipping unreadable file (encoding): %s", relative_path)
            continue
        except OSError as exc:
            LOGGER.warning("Skipping unreadable file (%s): %s", exc.__class__.__name__, relative_path)
            continue

        line_count = content.count("\n") + (1 if content else 0)
        if line_count > 500:
            LOGGER.warning("Skipping too large to roast (>500 lines): %s", relative_path)
            continue

        results.append(
            FileResult(
                path=str(relative_path),
                content=content,
                language=_infer_language(file_path),
                line_count=line_count,
            )
        )

    return results
