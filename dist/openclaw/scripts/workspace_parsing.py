#!/usr/bin/env python3
"""Parsing helpers for Xiaohongshu workspace markdown artifacts."""

from __future__ import annotations

import re
from pathlib import Path


def read_text(path: Path) -> str:
    return path.read_text() if path.exists() else ""


def parse_metadata(markdown: str) -> dict[str, str]:
    metadata = {}
    for line in markdown.splitlines():
        if not line.startswith("- "):
            continue
        if ":" not in line:
            continue
        key, value = line[2:].split(":", 1)
        metadata[key.strip()] = value.strip()
    return metadata


def extract_section(markdown: str, heading: str) -> str:
    target = f"## {heading}"
    in_section = False
    lines = []
    for line in markdown.splitlines():
        stripped = line.strip()
        if stripped == target:
            in_section = True
            continue
        if in_section and stripped.startswith("## "):
            break
        if in_section:
            lines.append(line)
    return "\n".join(lines).strip()


def extract_bullets(section_text: str) -> list[str]:
    items = []
    for line in section_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("- "):
            value = stripped[2:].strip()
            if value and value.upper() != "TODO":
                items.append(value)
    return items


def extract_topic_architecture(strategy_markdown: str) -> list[str]:
    section = extract_section(strategy_markdown, "Topic Architecture")
    topics = []
    for item in extract_bullets(section):
        if ":" in item:
            _, value = item.split(":", 1)
            value = value.strip()
        else:
            value = item
        value = value.replace("Optional ", "").strip()
        if value and value.upper() != "TODO":
            topics.append(value)
    return topics


def extract_repeatable_patterns(analysis_markdown: str) -> list[str]:
    section = extract_section(analysis_markdown, "Repeatable Content Patterns")
    patterns = []
    for line in section.splitlines():
        stripped = line.strip()
        if re.match(r"^\d+\.\s+", stripped):
            _, value = stripped.split(".", 1)
            value = value.strip()
            if value and value.upper() != "TODO":
                patterns.append(value)
    return patterns


def extract_keyword_map(analysis_markdown: str) -> dict[str, list[str]]:
    result = {"core": [], "long_tail": [], "trigger": []}
    current = None
    for line in analysis_markdown.splitlines():
        stripped = line.strip()
        if stripped == "### Core Keywords":
            current = "core"
            continue
        if stripped == "### Long-tail Keywords":
            current = "long_tail"
            continue
        if stripped == "### Trigger Keywords":
            current = "trigger"
            continue
        if stripped.startswith("#"):
            current = None
            continue
        if current and stripped.startswith("- "):
            value = stripped[2:].strip()
            if value and value.upper() != "TODO":
                result[current].append(value)
    return result


def extract_research_summary_points(analysis_markdown: str) -> list[str]:
    section = extract_section(analysis_markdown, "Research Summary")
    points = []
    for item in extract_bullets(section):
        if ":" in item:
            _, value = item.split(":", 1)
            value = value.strip()
        else:
            value = item
        if value and value.upper() != "TODO":
            points.append(value)
    return points


def extract_markdown_table(analysis_markdown: str, heading: str) -> list[dict[str, str]]:
    section = extract_section(analysis_markdown, heading)
    lines = [line.strip() for line in section.splitlines() if line.strip().startswith("|")]
    if len(lines) < 3:
        return []

    headers = [item.strip() for item in lines[0].strip("|").split("|")]
    rows = []
    for line in lines[2:]:
        parts = [item.strip() for item in line.strip("|").split("|")]
        if len(parts) != len(headers):
            continue
        row = dict(zip(headers, parts))
        if any(value and value.upper() != "TODO" for value in row.values()):
            rows.append(row)
    return rows


def extract_benchmark_notes(analysis_markdown: str) -> list[dict[str, str]]:
    return extract_markdown_table(analysis_markdown, "Benchmark Notes")


def extract_benchmark_accounts(analysis_markdown: str) -> list[dict[str, str]]:
    return extract_markdown_table(analysis_markdown, "Benchmark Accounts")
