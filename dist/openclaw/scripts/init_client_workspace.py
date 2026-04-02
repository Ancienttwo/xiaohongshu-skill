#!/usr/bin/env python3
"""Initialize a Xiaohongshu client workspace from bundled templates."""

from __future__ import annotations

import argparse
import re
import shutil
from datetime import date
from pathlib import Path


TEMPLATE_MAP = {
    "client-brief.md": "01-client-brief.md",
    "competitor-analysis.md": "02-competitor-analysis.md",
    "account-strategy.md": "03-account-strategy.md",
    "content-calendar.md": "04-content-calendar.md",
    "daily-ops-checklist.md": "05-daily-ops.md",
    "health-report.md": "06-health-report.md",
    "metrics-template.csv": "metrics.csv",
    "client-playbook.md": "playbook.md",
}


def slugify(value: str) -> str:
    normalized = value.strip().lower()
    normalized = re.sub(r"[^a-z0-9]+", "-", normalized)
    normalized = re.sub(r"-{2,}", "-", normalized).strip("-")
    return normalized or "client"


def render_template(path: Path, replacements: dict[str, str]) -> str:
    content = path.read_text()
    for key, value in replacements.items():
        content = content.replace(f"{{{{{key}}}}}", value)
    return content


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--client", required=True, help="Client or brand name")
    parser.add_argument("--industry", required=True, help="Industry or vertical")
    parser.add_argument("--root", required=True, help="Skill root containing assets/templates")
    parser.add_argument("--force", action="store_true", help="Overwrite existing files")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    template_root = root / "assets" / "templates"
    if not template_root.exists():
        raise SystemExit(f"Template directory not found: {template_root}")

    client_slug = slugify(args.client)
    client_dir = root / "clients" / client_slug
    client_dir.mkdir(parents=True, exist_ok=True)
    (client_dir / "lessons").mkdir(exist_ok=True)

    replacements = {
        "CLIENT_NAME": args.client,
        "CLIENT_SLUG": client_slug,
        "INDUSTRY": args.industry,
        "DATE": date.today().isoformat(),
    }

    written = []
    for template_name, output_name in TEMPLATE_MAP.items():
        source = template_root / template_name
        target = client_dir / output_name
        if target.exists() and not args.force:
            continue
        if source.suffix == ".csv":
            shutil.copyfile(source, target)
        else:
            target.write_text(render_template(source, replacements))
        written.append(target)

    print(f"client_dir={client_dir}")
    for path in written:
        print(f"created={path}")
    print(f"created_dir={client_dir / 'lessons'}")
    if not written:
        print("created=none")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
