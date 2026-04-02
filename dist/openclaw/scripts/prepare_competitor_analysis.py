#!/usr/bin/env python3
"""Prepare a competitor-analysis workspace with playbook-aware research priorities."""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

from playbook_utils import has_rule, load_playbook_rules
from workspace_parsing import extract_bullets, extract_section, parse_metadata, read_text


def seed_keywords(brief_markdown: str, metadata: dict[str, str]) -> list[str]:
    candidates = []
    current_industry = metadata.get("Industry")
    if current_industry and current_industry.upper() != "TODO":
        candidates.append(current_industry)

    for section_name in ["Main Vertical", "Subtopics", "Offer", "Target Audience"]:
        if section_name.startswith("Main"):
            section_text = extract_section(brief_markdown, "Main Vertical")
            if section_text and section_text.upper() != "TODO":
                candidates.append(section_text.splitlines()[0].strip())
            continue
        section_text = extract_section(brief_markdown, section_name)
        candidates.extend(extract_bullets(section_text))

    unique = []
    seen = set()
    for item in candidates:
        item = item.strip()
        if not item or item.upper() == "TODO" or item in seen:
            continue
        seen.add(item)
        unique.append(item)
    return unique[:5]


def research_priorities(rules: dict[str, dict[str, object]]) -> list[str]:
    priorities = [
        "Capture 3-5 benchmark accounts in the same vertical or adjacent purchase intent.",
        "Record 15+ benchmark notes with exact title structure, hook angle, and visible metrics.",
        "Map core keywords, long-tail keywords, and trigger keywords before writing strategy.",
    ]
    if has_rule(rules, "prefer-question-hooks"):
        priorities.append("Bias the benchmark note sample toward question-led titles and note where they outperform plain statements.")
    if has_rule(rules, "prefer-number-hooks"):
        priorities.append("Track which benchmark notes use number-led hooks and whether they earn more saves or clicks.")
    if has_rule(rules, "reduce-daily-volume"):
        priorities.append("Prefer benchmark accounts that win with lower but steadier posting volume rather than brute-force frequency.")
    if has_rule(rules, "emphasize-cover-hook"):
        priorities.append("Capture cover layouts and title-cover match quality, not just note topics.")
    if has_rule(rules, "emphasize-keyword-fit"):
        priorities.append("Rank benchmark notes by search intent clarity and keyword placement quality.")
    return priorities


def playbook_focus_summary(rules: dict[str, dict[str, object]]) -> list[str]:
    focus = []
    if has_rule(rules, "prefer-question-hooks"):
        focus.append("Question-led hooks are a client preference. Tag benchmark titles that open with a pain-point question.")
    if has_rule(rules, "prefer-number-hooks"):
        focus.append("Number-led hooks are a client preference. Tag benchmark titles that promise steps, lists, or counts.")
    if has_rule(rules, "reduce-daily-volume"):
        focus.append("Client prefers lower posting volume. Prioritize benchmark accounts that perform without high daily output.")
    if has_rule(rules, "emphasize-cover-hook"):
        focus.append("Client cares about cover-hook quality. Capture cover style and promise clarity for every strong note.")
    if has_rule(rules, "emphasize-keyword-fit"):
        focus.append("Client wants stronger keyword fit. Record exact searchable phrasing, not paraphrases.")
    return focus or ["No client-specific research bias yet. Use the default research rubric."]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--brief", required=True, help="Path to 01-client-brief.md")
    parser.add_argument("--output", required=True, help="Path to 02-competitor-analysis.md")
    parser.add_argument("--playbook", help="Path to playbook.md")
    args = parser.parse_args()

    brief_path = Path(args.brief)
    output_path = Path(args.output)
    playbook_path = Path(args.playbook) if args.playbook else output_path.parent / "playbook.md"

    brief_markdown = read_text(brief_path)
    metadata = parse_metadata(brief_markdown)
    rules = load_playbook_rules(playbook_path)
    keywords = seed_keywords(brief_markdown, metadata)
    priorities = research_priorities(rules)
    focus = playbook_focus_summary(rules)

    lines = [
        "# 02 Competitor Analysis",
        "",
        f"- Client Name: {metadata.get('Client Name', 'Unknown')}",
        f"- Industry: {metadata.get('Industry', 'Unknown')}",
        f"- Research Date: {date.today().isoformat()}",
        "- Research Source: TODO",
        f"- Playbook Rules Applied: {len(rules)}",
        "",
        "## Research Goal",
        "",
        f"- Find benchmark accounts and notes that can support a {metadata.get('Industry', '小红书')} launch.",
        "- Prefer transferable patterns over celebrity outliers.",
        "",
        "## Seed Search Keywords",
        "",
    ]
    lines.extend(f"- {item}" for item in (keywords or [metadata.get("Industry", "小红书")]))
    lines.extend(
        [
            "",
            "## Playbook Focus",
            "",
        ]
    )
    lines.extend(f"- {item}" for item in focus)
    lines.extend(
        [
            "",
            "## Research Priorities",
            "",
        ]
    )
    lines.extend(f"{idx}. {item}" for idx, item in enumerate(priorities, 1))
    lines.extend(
        [
            "",
            "## Benchmark Accounts",
            "",
            "| Account | Followers | Persona | Bio Structure | Posting Cadence | Content Buckets | Notes |",
            "|---|---:|---|---|---|---|---|",
            "| TODO | TODO | TODO | TODO | TODO | TODO | TODO |",
            "| TODO | TODO | TODO | TODO | TODO | TODO | TODO |",
            "| TODO | TODO | TODO | TODO | TODO | TODO | TODO |",
            "",
            "## Benchmark Notes",
            "",
            "| Account | Note Title | Content Type | Cover Style | Visible Metrics | Hook Angle | Keywords |",
            "|---|---|---|---|---|---|---|",
            "| TODO | TODO | TODO | TODO | TODO | TODO | TODO |",
            "| TODO | TODO | TODO | TODO | TODO | TODO | TODO |",
            "| TODO | TODO | TODO | TODO | TODO | TODO | TODO |",
            "",
            "## Keyword Map",
            "",
            "### Core Keywords",
            "",
            "- TODO",
            "",
            "### Long-tail Keywords",
            "",
            "- TODO",
            "",
            "### Trigger Keywords",
            "",
            "- TODO",
            "",
            "## Repeatable Content Patterns",
            "",
            "1. TODO",
            "2. TODO",
            "3. TODO",
            "",
            "## Research Summary",
            "",
            "- What title patterns work repeatedly: TODO",
            "- What posting cadence seems sustainable: TODO",
            "- What hooks or covers deserve copying: TODO",
            "- What keyword opportunities look under-served: TODO",
        ]
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines).rstrip() + "\n")
    print(f"written={output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
