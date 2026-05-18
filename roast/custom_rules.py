import yaml
import re
import os
from dataclasses import dataclass
from typing import List, Optional

@dataclass
class CustomRule:
    name: str
    pattern: str
    severity: str
    message: str
    category: str = "Code Quality"

def load_custom_rules(config_path: str = ".roast.yaml") -> List[CustomRule]:
    try:
        if not os.path.exists(config_path):
            return []
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)
            if not config or "rules" not in config:
                return []
            
            rules = []
            for r in config["rules"]:
                rules.append(CustomRule(
                    name=r["name"],
                    pattern=r["pattern"],
                    severity=r.get("severity", "medium"),
                    message=r["message"],
                    category=r.get("category", "Code Quality")
                ))
            return rules
    except Exception as e:
        print(f"Error loading custom rules: {e}")
        return []
