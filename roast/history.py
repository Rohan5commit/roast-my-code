import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List

def _get_history_dir() -> Path:
    cache_dir = os.environ.get("XDG_CACHE_HOME", str(Path.home() / ".cache"))
    return Path(cache_dir) / "roast-my-code" / "history"

HISTORY_DIR = _get_history_dir()

def save_history(report_data: Dict):
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = HISTORY_DIR / f"scan_{timestamp}.json"
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(report_data, f)

def get_history() -> List[Dict]:
    if not HISTORY_DIR.exists():
        return []
    
    history = []
    for filepath in sorted(HISTORY_DIR.glob("scan_*.json")):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                history.append(json.load(f))
        except (json.JSONDecodeError, OSError):
            continue
    return history
