#!/usr/bin/env python3
"""Score Xiaohongshu note performance from a metrics CSV file."""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from playbook_utils import has_rule, load_playbook_rules


@dataclass
class NoteMetric:
    date: str
    note_title: str
    views: float
    likes: float
    collects: float
    comments: float
    shares: float
    content_type: str
    keyword: str
    status_note: str

    @property
    def engagement_rate(self) -> float:
        if self.views <= 0:
            return 0.0
        return (self.likes + self.collects + self.comments + self.shares) / self.views * 100


def to_float(value: str) -> float:
    value = (value or "").strip()
    if not value:
        return 0.0
    return float(value)


def read_metrics(path: Path) -> list[NoteMetric]:
    rows: list[NoteMetric] = []
    with path.open(newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            if not row.get("note_title"):
                continue
            rows.append(
                NoteMetric(
                    date=row.get("date", "").strip(),
                    note_title=row.get("note_title", "").strip(),
                    views=to_float(row.get("views", "")),
                    likes=to_float(row.get("likes", "")),
                    collects=to_float(row.get("collects", "")),
                    comments=to_float(row.get("comments", "")),
                    shares=to_float(row.get("shares", "")),
                    content_type=row.get("content_type", "").strip(),
                    keyword=row.get("keyword", "").strip(),
                    status_note=row.get("status_note", "").strip(),
                )
            )
    return rows


def traffic_tier(avg_views: float) -> tuple[str, str]:
    if avg_views < 200:
        return "Tier 1", "Weak distribution or account not warmed"
    if avg_views < 500:
        return "Tier 2", "Basic distribution only"
    if avg_views < 2000:
        return "Tier 3", "Usable baseline but still fragile"
    if avg_views < 20000:
        return "Tier 4", "Healthy early traction"
    if avg_views < 100000:
        return "Tier 5", "Strong natural distribution"
    return "Tier 6", "Breakout performance"


def summarize_actions(
    avg_views: float,
    avg_engagement: float,
    warning_count: int,
    rules: dict[str, dict[str, object]],
) -> list[str]:
    actions = []
    if avg_views < 500:
        if has_rule(rules, "reduce-daily-volume"):
            actions.append("Reduce posting volume and tighten topic-keyword fit before pushing more notes live.")
        else:
            actions.append("Tighten the niche and rework topic/keyword fit before increasing output.")
    if avg_engagement < 3:
        if has_rule(rules, "prefer-question-hooks"):
            actions.append("Rewrite titles into question-led hooks and sharpen the cover promise for the next batch.")
        elif has_rule(rules, "prefer-number-hooks"):
            actions.append("Rewrite titles around number-led hooks and make the cover promise more concrete.")
        else:
            actions.append("Rewrite titles and covers for stronger curiosity, clarity, and proof.")
    if has_rule(rules, "emphasize-keyword-fit"):
        actions.append("Audit keyword placement and search intent so every weak note maps to one clear query.")
    if has_rule(rules, "emphasize-cover-hook"):
        actions.append("Run a cover and hook pass on the weakest notes before changing the whole strategy.")
    if warning_count or has_rule(rules, "emphasize-compliance-review"):
        actions.append("Review risky claims, public profile copy, and note wording for suppression signals.")
    if not actions:
        actions.append("Keep the current cadence and start testing controlled conversion-oriented notes.")
    while len(actions) < 3:
        actions.append("Keep recording note metrics so the next health pass can confirm the trend.")
    return actions[:3]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metrics", required=True, help="Path to metrics.csv")
    parser.add_argument("--output", required=True, help="Path to 06-health-report.md")
    parser.add_argument("--playbook", help="Path to client playbook.md")
    args = parser.parse_args()

    metrics_path = Path(args.metrics)
    output_path = Path(args.output)
    playbook_path = Path(args.playbook) if args.playbook else output_path.parent / "playbook.md"
    rows = read_metrics(metrics_path)
    if not rows:
        raise SystemExit("No metrics rows found. Provide at least one populated note row.")

    note_count = len(rows)
    avg_views = sum(row.views for row in rows) / note_count
    avg_engagement = sum(row.engagement_rate for row in rows) / note_count
    tier_name, tier_meaning = traffic_tier(avg_views)
    rules = load_playbook_rules(playbook_path)
    warning_count = sum(
        1
        for row in rows
        if any(term in row.status_note.lower() for term in ("warning", "violation", "limit", "suppression"))
    )
    passed = note_count >= 5 and avg_views >= 500 and avg_engagement >= 3 and warning_count == 0
    actions = summarize_actions(avg_views, avg_engagement, warning_count, rules)

    sorted_rows = sorted(rows, key=lambda row: row.views)[:3]
    report_lines = [
        "# 06 Health Report",
        "",
        f"- Last Updated: {date.today().isoformat()}",
        f"- Metrics Source: {metrics_path}",
        f"- Notes Analyzed: {note_count}",
        "",
        "## Summary",
        "",
        f"- Average Views: {avg_views:.0f}",
        f"- Average Engagement Rate: {avg_engagement:.2f}%",
        f"- Traffic Tier: {tier_name} ({tier_meaning})",
        f"- Warning Flags: {warning_count}",
        f"- Exit Criteria: {'PASS' if passed else 'FAIL'}",
        f"- Playbook Rules Applied: {len(rules)}",
        "",
        "## Weakest Notes",
        "",
    ]
    for row in sorted_rows:
        report_lines.append(
            f"- {row.note_title}: {row.views:.0f} views, {row.engagement_rate:.2f}% engagement, keyword `{row.keyword or 'n/a'}`"
        )
    report_lines.extend(
        [
            "",
            "## Next Actions",
            "",
            f"1. {actions[0]}",
            f"2. {actions[1]}",
            f"3. {actions[2]}",
            "",
            "## Exit Criteria Check",
            "",
            f"- At least 5 notes recorded: {'yes' if note_count >= 5 else 'no'}",
            f"- Average views >= 500: {'yes' if avg_views >= 500 else 'no'}",
            f"- Average engagement rate >= 3%: {'yes' if avg_engagement >= 3 else 'no'}",
            f"- No warning signals in status notes: {'yes' if warning_count == 0 else 'no'}",
        ]
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(report_lines).rstrip() + "\n")
    print(f"written={output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
