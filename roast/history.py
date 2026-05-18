import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List

HISTORY_DIR = Path(".roast/history")

def save_history(report_data: Dict):
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = HISTORY_DIR / f"scan_{timestamp}.json"
    with open(filepath, "w") as f:
        json.dump(report_data, f)

def get_history() -> List[Dict]:
    if not HISTORY_DIR.exists():
        return []
    
    history = []
    for filepath in sorted(HISTORY_DIR.glob("scan_*.json")):
        with open(filepath, "r") as f:
            try:
                history.append(json.load(f))
            except json.JSONDecodeError:
                continue
    return history
