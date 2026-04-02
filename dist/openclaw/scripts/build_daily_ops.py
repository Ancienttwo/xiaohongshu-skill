#!/usr/bin/env python3
"""Generate a daily operations checklist from the client brief and content calendar."""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path


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


def parse_calendar_rows(markdown: str) -> list[dict[str, str]]:
    rows = []
    for line in markdown.splitlines():
        stripped = line.strip()
        if not stripped.startswith("| D"):
            continue
        parts = [part.strip() for part in stripped.strip("|").split("|")]
        if len(parts) < 7:
            continue
        rows.append(
            {
                "day": parts[0],
                "publish_count": parts[1],
                "title": parts[2],
                "content_type": parts[3],
                "keyword": parts[4],
                "cover_direction": parts[5],
                "publish_time": parts[6],
            }
        )
    return rows


def browse_rounds_for(day_name: str) -> int:
    if day_name in {"D1", "D2"}:
        return 3
    if day_name == "D3":
        return 2
    return 1


def task_lines(row: dict[str, str]) -> list[str]:
    day_name = row["day"]
    publish_count = row["publish_count"]
    title = row["title"]
    lines = [
        f"### {day_name}",
        "",
        f"- Browse Xiaohongshu normally for 30 minutes x {browse_rounds_for(day_name)}.",
        "- Search and interact within the chosen niche without spammy behavior.",
    ]
    if day_name in {"D1", "D2"}:
        lines.append("- Do not publish today.")
    else:
        lines.extend(
            [
                f"- Publish count target: {publish_count}.",
                f"- Planned titles: {title}.",
                f"- Planned content type: {row['content_type']}.",
                f"- Primary keywords: {row['keyword']}.",
                f"- Cover direction: {row['cover_direction']}.",
                f"- Planned publish time: {row['publish_time']}.",
                "- Check note indexability 10 minutes after publishing.",
                "- Reply to all genuine comments.",
            ]
        )
    if day_name == "D3":
        lines.extend(
            [
                "- Confirm the recommendation feed shows at least 3 relevant notes in two pages.",
                "- Update account name, avatar, and bio only after the vertical looks stable.",
            ]
        )
    lines.append("- Log abnormalities in metrics or account status before ending the day.")
    lines.append("")
    return lines


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--brief", required=True, help="Path to 01-client-brief.md")
    parser.add_argument("--calendar", required=True, help="Path to 04-content-calendar.md")
    parser.add_argument("--output", required=True, help="Path to 05-daily-ops.md")
    parser.add_argument(
        "--extend-to",
        type=int,
        default=7,
        choices=(7, 8, 9, 10),
        help="Generate through D7 by default, optionally extend to D8-D10",
    )
    args = parser.parse_args()

    brief_path = Path(args.brief)
    calendar_path = Path(args.calendar)
    output_path = Path(args.output)

    brief = brief_path.read_text()
    calendar = calendar_path.read_text()
    metadata = parse_metadata(brief)
    calendar_rows = parse_calendar_rows(calendar)

    if not calendar_rows:
        raise SystemExit("No calendar rows found in the markdown table.")

    rows_by_day = {row["day"]: row for row in calendar_rows}
    ordered_rows = []
    for day_num in range(1, args.extend_to + 1):
        day_name = f"D{day_num}"
        row = rows_by_day.get(day_name)
        if row is None and day_num > 7:
            row = {
                "day": day_name,
                "publish_count": "1",
                "title": "TBD extension note",
                "content_type": "extension",
                "keyword": "TBD",
                "cover_direction": "TBD",
                "publish_time": "20:00",
            }
        if row is not None:
            ordered_rows.append(row)

    lines = [
        "# 05 Daily Ops",
        "",
        f"- Client Name: {metadata.get('Client Name', 'Unknown')}",
        f"- Industry: {metadata.get('Industry', 'Unknown')}",
        f"- Generated: {date.today().isoformat()}",
        f"- Source Brief: {brief_path}",
        f"- Source Calendar: {calendar_path}",
        "",
        "## Daily Checklist",
        "",
    ]
    for row in ordered_rows:
        lines.extend(task_lines(row))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines).rstrip() + "\n")
    print(f"written={output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
