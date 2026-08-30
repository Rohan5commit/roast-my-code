"""Custom linting rules loaded from a .roast.yaml config file."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class CustomRule:
    name: str
    pattern: str
    severity: str
    message: str
    category: str = "Code Quality"


def load_custom_rules(config_path: str | Path = ".roast.yaml") -> list[CustomRule]:
    """Load custom rules from a YAML config file.

    Returns an empty list if the file does not exist, is invalid, or
    encounters an error.
    """
    path = Path(config_path)
    if not path.exists():
        return []

    try:
        with path.open("r", encoding="utf-8") as fh:
            config: dict[str, Any] | None = yaml.safe_load(fh)
    except (yaml.YAMLError, OSError) as exc:
        LOGGER.warning("Failed to read custom rules from %s: %s", path, exc)
        return []

    if not config or "rules" not in config:
        return []

    rules: list[CustomRule] = []
    for idx, rule in enumerate(config["rules"]):
        try:
            rules.append(
                CustomRule(
                    name=rule["name"],
                    pattern=rule["pattern"],
                    severity=rule.get("severity", "medium"),
                    message=rule["message"],
                    category=rule.get("category", "Code Quality"),
                )
            )
        except KeyError as exc:
            LOGGER.warning(
                "Skipping malformed custom rule #%d in %s (missing key: %s)",
                idx + 1,
                path,
                exc,
            )
            continue
        # Validate the regex pattern at load time rather than at scan time.
        try:
            re.compile(rule["pattern"])
        except re.error as exc:
            LOGGER.warning(
                "Skipping custom rule %r in %s (invalid regex: %s)",
                rule.get("name", f"#{idx + 1}"),
                path,
                exc,
            )
            rules.pop()  # Remove the rule we just added
            continue

    return rules
