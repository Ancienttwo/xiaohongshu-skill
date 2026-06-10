#!/usr/bin/env python3
"""Rebuild playbook.md from captured lessons.

lessons/*.json is the machine-readable source of truth; playbook.md is the
human-readable render that the generators and SKILL.md workflows consume.
Running this with no recorded lessons writes an empty-rules playbook.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from playbook_utils import render_playbook, summarize_lessons


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--client-dir", required=True, help="Path to ~/.growth/vault/<profile>/xiaohongshu/")
    args = parser.parse_args()

    client_dir = Path(args.client_dir).expanduser().resolve()
    summary = summarize_lessons(client_dir)
    playbook_path = render_playbook(client_dir, summary)
    print(f"playbook={playbook_path}")
    print(f"rules={len(summary)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
