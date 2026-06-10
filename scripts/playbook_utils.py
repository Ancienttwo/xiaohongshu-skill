#!/usr/bin/env python3
"""Client playbook rules: lessons/*.json is the machine-readable source of truth.

`playbook.md` is a human-readable render of the lessons summary. Rules are
loaded from lessons when present; the markdown table is only a fallback for
hand-maintained playbooks without recorded lessons.
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from workspace_paths import profile_from_client_dir


TABLE_ROW_RE = re.compile(
    r"^\|\s*`?(?P<key>[^`|]+)`?\s*\|\s*(?P<type>[^|]+)\|\s*(?P<confidence>[^|]+)\|\s*(?P<occurrences>[^|]+)\|\s*(?P<rule>.+)\|$"
)


def parse_playbook_table(playbook_path: Path) -> dict[str, dict[str, object]]:
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


def summarize_lessons(client_dir: Path) -> dict[str, dict[str, object]]:
    grouped: dict[str, dict[str, object]] = {}
    lessons_dir = client_dir / "lessons"
    if not lessons_dir.is_dir():
        return grouped
    for lesson_file in sorted(lessons_dir.glob("*.json")):
        # A hand-edited or truncated lesson must not take down read-only
        # consumers such as score_health or the generators.
        try:
            lesson = json.loads(lesson_file.read_text())
            created_at = str(lesson["created_at"])
            items = [
                (str(item["key"]), str(item["type"]), str(item["description"]), str(item["rule"]))
                for item in lesson.get("patterns", [])
            ]
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            print(f"warning: skipping malformed lesson file {lesson_file}: {exc}", file=sys.stderr)
            continue
        for key, type_name, description, rule in items:
            entry = grouped.setdefault(
                key,
                {
                    "type": type_name,
                    "description": description,
                    "rule": rule,
                    "occurrences": 0,
                    "last_seen": created_at,
                },
            )
            entry["occurrences"] += 1
            entry["description"] = description
            entry["rule"] = rule
            entry["last_seen"] = created_at
    for entry in grouped.values():
        entry["confidence"] = min(10.0, round(1.5 + entry["occurrences"] * 1.5, 1))
    return grouped


def load_playbook_rules(playbook_path: Path) -> dict[str, dict[str, object]]:
    """Load rules for a client. Lessons win over hand-edited table rows per key."""
    rules = parse_playbook_table(playbook_path)
    rules.update(summarize_lessons(playbook_path.parent))
    return rules


def render_playbook(client_dir: Path, summary: dict[str, dict[str, object]]) -> Path:
    """Render playbook.md from the lessons summary, preserving hand-added rows.

    Table rows that exist only in the current playbook.md (no recorded lesson
    for that key) survive the rewrite; lessons win for keys they cover.
    """
    playbook_path = client_dir / "playbook.md"
    merged = parse_playbook_table(playbook_path)
    merged.update(summary)
    summary = merged
    lines = [
        "# Client Playbook",
        "",
        f"- Client Slug: {profile_from_client_dir(client_dir)}",
        f"- Last Updated: {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}",
        "",
    ]
    if not summary:
        lines.append("No client-specific rules yet.")
        playbook_path.write_text("\n".join(lines) + "\n")
        return playbook_path

    hard_rules = []
    soft_rules = []
    for key, entry in sorted(summary.items()):
        row = f"| `{key}` | {entry['type']} | {entry['confidence']:.1f} | {entry['occurrences']} | {entry['rule']} |"
        if entry["confidence"] >= 5.0:
            hard_rules.append(row)
        else:
            soft_rules.append(row)

    def table(section_name: str, rows: list[str]) -> list[str]:
        if not rows:
            return [f"## {section_name}", "", "None yet.", ""]
        return [
            f"## {section_name}",
            "",
            "| Key | Type | Confidence | Occurrences | Rule |",
            "|---|---|---:|---:|---|",
            *rows,
            "",
        ]

    lines.extend(table("Hard Rules", hard_rules))
    lines.extend(table("Soft Rules", soft_rules))
    playbook_path.write_text("\n".join(lines).rstrip() + "\n")
    return playbook_path


def has_rule(rules: dict[str, dict[str, object]], key: str, minimum_confidence: float = 3.0) -> bool:
    rule = rules.get(key)
    if not rule:
        return False
    return float(rule.get("confidence", 0.0)) >= minimum_confidence
