#!/usr/bin/env python3
"""Score Xiaohongshu note performance from a metrics CSV file."""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from playbook_utils import has_rule, load_playbook_rules


DEFAULT_THRESHOLDS_PATH = Path(__file__).resolve().parent.parent / "assets" / "diagnosis-thresholds.json"

# Base schema merged under any thresholds file, so partial overrides work and
# a missing bundled asset still scores. Keep in sync with
# assets/diagnosis-thresholds.json and references/diagnosis-rubric.md.
DEFAULT_THRESHOLDS = {
    "traffic_tiers": [
        {"max_avg_views": 200, "tier": "Tier 1", "meaning": "Weak distribution or account not warmed"},
        {"max_avg_views": 500, "tier": "Tier 2", "meaning": "Basic distribution only"},
        {"max_avg_views": 2000, "tier": "Tier 3", "meaning": "Usable baseline but still fragile"},
        {"max_avg_views": 20000, "tier": "Tier 4", "meaning": "Healthy early traction"},
        {"max_avg_views": 100000, "tier": "Tier 5", "meaning": "Strong natural distribution"},
        {"max_avg_views": None, "tier": "Tier 6", "meaning": "Breakout performance"},
    ],
    "exit_criteria": {"min_notes": 5, "min_avg_views": 500, "min_avg_engagement_rate": 3.0},
    "warning_terms": ["warning", "violation", "limit", "suppression"],
}


def load_thresholds(path: Path | None = None) -> dict:
    """Load thresholds merged over DEFAULT_THRESHOLDS.

    An explicitly passed path must exist; the bundled default file may be
    absent. Top-level keys in the file override the defaults, so a partial
    override (e.g. only exit_criteria) is valid.
    """
    thresholds = dict(DEFAULT_THRESHOLDS)
    target = path or DEFAULT_THRESHOLDS_PATH
    if path is not None and not target.exists():
        raise SystemExit(f"Thresholds file not found: {target}")
    if target.exists():
        try:
            data = json.loads(target.read_text())
        except json.JSONDecodeError as exc:
            raise SystemExit(f"Invalid thresholds JSON in {target}: {exc}") from exc
        if not isinstance(data, dict):
            raise SystemExit(f"Thresholds file must be a JSON object: {target}")
        thresholds.update({key: value for key, value in data.items() if not key.startswith("_")})
    return thresholds


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


def traffic_tier(avg_views: float, thresholds: dict | None = None) -> tuple[str, str]:
    tiers = (thresholds or DEFAULT_THRESHOLDS)["traffic_tiers"]
    for tier in tiers:
        maximum = tier.get("max_avg_views")
        if maximum is None or avg_views < maximum:
            return tier["tier"], tier["meaning"]
    return tiers[-1]["tier"], tiers[-1]["meaning"]


def summarize_actions(
    avg_views: float,
    avg_engagement: float,
    warning_count: int,
    rules: dict[str, dict[str, object]],
    exit_criteria: dict | None = None,
) -> list[str]:
    exit_criteria = exit_criteria or DEFAULT_THRESHOLDS["exit_criteria"]
    actions = []
    if avg_views < exit_criteria["min_avg_views"]:
        if has_rule(rules, "reduce-daily-volume"):
            actions.append("Reduce posting volume and tighten topic-keyword fit before pushing more notes live.")
        else:
            actions.append("Tighten the niche and rework topic/keyword fit before increasing output.")
    if avg_engagement < exit_criteria["min_avg_engagement_rate"]:
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
    parser.add_argument("--thresholds", help="Path to a diagnosis-thresholds.json override")
    parser.add_argument(
        "--recent",
        type=int,
        default=10,
        help="Score only the most recent N metric rows so old notes do not dilute the diagnosis (0 = all rows)",
    )
    args = parser.parse_args()

    metrics_path = Path(args.metrics)
    output_path = Path(args.output)
    playbook_path = Path(args.playbook) if args.playbook else output_path.parent / "playbook.md"
    thresholds = load_thresholds(Path(args.thresholds) if args.thresholds else None)
    exit_criteria = thresholds["exit_criteria"]
    warning_terms = thresholds["warning_terms"]
    all_rows = read_metrics(metrics_path)
    if not all_rows:
        raise SystemExit("No metrics rows found. Provide at least one populated note row.")
    rows = all_rows[-args.recent:] if args.recent > 0 else all_rows

    note_count = len(rows)
    avg_views = sum(row.views for row in rows) / note_count
    avg_engagement = sum(row.engagement_rate for row in rows) / note_count
    tier_name, tier_meaning = traffic_tier(avg_views, thresholds)
    rules = load_playbook_rules(playbook_path)
    # Warnings are gate signals, not averages: scan every recorded row so a
    # violation just outside the --recent window cannot unblock monetization.
    warning_count = sum(
        1
        for row in all_rows
        if any(term in row.status_note.lower() for term in warning_terms)
    )
    passed = (
        note_count >= exit_criteria["min_notes"]
        and avg_views >= exit_criteria["min_avg_views"]
        and avg_engagement >= exit_criteria["min_avg_engagement_rate"]
        and warning_count == 0
    )
    actions = summarize_actions(avg_views, avg_engagement, warning_count, rules, exit_criteria)

    sorted_rows = sorted(rows, key=lambda row: row.views)[:3]
    report_lines = [
        "# 06 Health Report",
        "",
        f"- Last Updated: {date.today().isoformat()}",
        f"- Metrics Source: {metrics_path}",
        f"- Notes Analyzed: {note_count} (most recent of {len(all_rows)} recorded)",
        "",
        "## Summary",
        "",
        f"- Average Views: {avg_views:.0f}",
        f"- Average Engagement Rate: {avg_engagement:.2f}%",
        f"- Traffic Tier: {tier_name} ({tier_meaning})",
        f"- Warning Flags: {warning_count} (all {len(all_rows)} recorded rows scanned)",
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
            f"- At least {exit_criteria['min_notes']} notes recorded: {'yes' if note_count >= exit_criteria['min_notes'] else 'no'}",
            f"- Average views >= {exit_criteria['min_avg_views']}: {'yes' if avg_views >= exit_criteria['min_avg_views'] else 'no'}",
            f"- Average engagement rate >= {exit_criteria['min_avg_engagement_rate']:g}%: {'yes' if avg_engagement >= exit_criteria['min_avg_engagement_rate'] else 'no'}",
            f"- No warning signals in status notes: {'yes' if warning_count == 0 else 'no'}",
        ]
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(report_lines).rstrip() + "\n")
    print(f"written={output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
