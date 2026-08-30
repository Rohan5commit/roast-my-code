"""Scan history for trend tracking across multiple runs."""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path


def _get_history_dir() -> Path:
    cache_dir = os.environ.get("XDG_CACHE_HOME", str(Path.home() / ".cache"))
    return Path(cache_dir) / "roast-my-code" / "history"


HISTORY_DIR = _get_history_dir()


def save_history(report_data: dict) -> None:
    """Persist a scan result for later trend comparison."""
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = HISTORY_DIR / f"scan_{timestamp}.json"
    with filepath.open("w", encoding="utf-8") as fh:
        json.dump(report_data, fh)


def get_history() -> list[dict]:
    """Return all previously saved scan results, newest last."""
    if not HISTORY_DIR.exists():
        return []

    history: list[dict] = []
    for filepath in sorted(HISTORY_DIR.glob("scan_*.json")):
        try:
            with filepath.open("r", encoding="utf-8") as fh:
                history.append(json.load(fh))
        except (json.JSONDecodeError, OSError):
            continue
    return history
