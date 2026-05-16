#!/usr/bin/env python3
"""Initialize or append to a client playbook file."""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

TEMPLATE = """# Client Playbook — {client_name}

> Auto-generated on {date}. Update this file whenever the operator revises agent output.

## Title Preferences

- (no preferences recorded yet)

## Content Preferences

- (no preferences recorded yet)

## Tone Preferences

- (no preferences recorded yet)

## Rejected Approaches

- (no preferences recorded yet)

## Posting Schedule Preferences

- (no preferences recorded yet)
"""


def extract_client_name(client_dir: Path) -> str:
    brief = client_dir / "01-client-brief.md"
    if brief.exists():
        for line in brief.read_text().splitlines():
            if line.startswith("- Client Name:"):
                return line.split(":", 1)[1].strip()
    return client_dir.parent.name if client_dir.name == ".xiaohongshu" else client_dir.name


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--client-dir", required=True, help="Path to users/<user-slug>/.xiaohongshu/")
    parser.add_argument("--output", help="Output path (default: <client-dir>/playbook.md)")
    args = parser.parse_args()

    client_dir = Path(args.client_dir).resolve()
    output = Path(args.output) if args.output else client_dir / "playbook.md"

    if output.exists():
        print(f"exists={output}")
        print("Playbook already exists. Edit it manually or append entries.")
        return 0

    client_name = extract_client_name(client_dir)
    content = TEMPLATE.format(client_name=client_name, date=date.today().isoformat())

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(content)
    print(f"created={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
