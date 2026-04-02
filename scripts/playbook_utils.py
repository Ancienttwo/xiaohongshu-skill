#!/usr/bin/env python3
"""Helpers for reading client playbook rules from markdown tables."""

from __future__ import annotations

import re
from pathlib import Path


TABLE_ROW_RE = re.compile(
    r"^\|\s*`?(?P<key>[^`|]+)`?\s*\|\s*(?P<type>[^|]+)\|\s*(?P<confidence>[^|]+)\|\s*(?P<occurrences>[^|]+)\|\s*(?P<rule>.+)\|$"
)


def load_playbook_rules(playbook_path: Path) -> dict[str, dict[str, object]]:
    if not playbook_path.exists():
        return {}
    rules: dict[str, dict[str, object]] = {}
    for line in playbook_path.read_text().splitlines():
        match = TABLE_ROW_RE.match(line.strip())
        if not match:
            continue
        key = match.group("key").strip()
        if key.lower() == "key":
            continue
        if set(key) <= {"-"}:
            continue
        try:
            confidence = float(match.group("confidence").strip())
        except ValueError:
            confidence = 0.0
        try:
            occurrences = int(match.group("occurrences").strip())
        except ValueError:
            occurrences = 0
        rules[key] = {
            "type": match.group("type").strip(),
            "confidence": confidence,
            "occurrences": occurrences,
            "rule": match.group("rule").strip(),
        }
    return rules


def has_rule(rules: dict[str, dict[str, object]], key: str, minimum_confidence: float = 3.0) -> bool:
    rule = rules.get(key)
    if not rule:
        return False
    return float(rule.get("confidence", 0.0)) >= minimum_confidence
