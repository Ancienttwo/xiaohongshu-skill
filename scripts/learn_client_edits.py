#!/usr/bin/env python3
"""Learn recurring client edit preferences from Xiaohongshu workspace artifacts."""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


EMOJI_RE = re.compile(
    "["
    "\U0001F300-\U0001F5FF"
    "\U0001F600-\U0001F64F"
    "\U0001F680-\U0001F6FF"
    "\U0001F900-\U0001F9FF"
    "\U00002600-\U000026FF"
    "\U00002700-\U000027BF"
    "]",
    flags=re.UNICODE,
)


def read_text(path: Path) -> str:
    return path.read_text()


def extract_calendar_rows(markdown: str) -> list[dict[str, str]]:
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
                "keyword": parts[4],
            }
        )
    return rows


def extract_next_actions(markdown: str) -> list[str]:
    in_section = False
    actions = []
    for line in markdown.splitlines():
        stripped = line.strip()
        if stripped == "## Next Actions":
            in_section = True
            continue
        if in_section and stripped.startswith("## "):
            break
        if in_section and re.match(r"^\d+\.\s+", stripped):
            actions.append(re.sub(r"^\d+\.\s+", "", stripped))
    return actions


def emoji_count(text: str) -> int:
    return len(EMOJI_RE.findall(text))


def numeric_count(text: str) -> int:
    return len(re.findall(r"\d", text))


def question_count(text: str) -> int:
    return text.count("?") + text.count("？")


def avg_title_length(rows: list[dict[str, str]]) -> float:
    titles = [row["title"].replace("/", " ").strip() for row in rows if row["title"] and row["title"] != "-"]
    if not titles:
        return 0.0
    return sum(len(title) for title in titles) / len(titles)


def total_publish_count(rows: list[dict[str, str]]) -> int:
    total = 0
    for row in rows:
        try:
            total += int(row["publish_count"])
        except ValueError:
            continue
    return total


def detect_calendar_patterns(draft: str, final: str) -> list[dict[str, str]]:
    draft_rows = extract_calendar_rows(draft)
    final_rows = extract_calendar_rows(final)
    patterns = []
    draft_avg_title = avg_title_length(draft_rows)
    final_avg_title = avg_title_length(final_rows)
    if final_avg_title and draft_avg_title - final_avg_title >= 2:
        patterns.append(
            pattern(
                "title", "prefer-shorter-titles",
                "Client shortened the average planned title length.",
                "Keep Xiaohongshu titles tighter and remove extra modifiers before finalizing the content calendar.",
            )
        )
    elif final_avg_title - draft_avg_title >= 2:
        patterns.append(
            pattern(
                "title", "allow-longer-titles",
                "Client expanded planned titles to carry more context.",
                "Allow slightly longer Xiaohongshu titles when the extra context improves clarity or search fit.",
            )
        )

    draft_publish = total_publish_count(draft_rows)
    final_publish = total_publish_count(final_rows)
    if draft_publish - final_publish >= 2:
        patterns.append(
            pattern(
                "cadence", "reduce-daily-volume",
                "Client reduced the total publish count in the calendar.",
                "Prefer a lower daily posting volume when quality is at risk or proof assets are limited.",
            )
        )
    elif final_publish - draft_publish >= 2:
        patterns.append(
            pattern(
                "cadence", "increase-daily-volume",
                "Client increased the total publish count in the calendar.",
                "Use a denser posting cadence when the client can sustain the quality bar.",
            )
        )

    patterns.extend(detect_text_bias_patterns(draft, final))
    return patterns


def detect_health_patterns(draft: str, final: str) -> list[dict[str, str]]:
    patterns = []
    draft_actions = extract_next_actions(draft)
    final_actions = extract_next_actions(final)
    if draft_actions and final_actions:
        draft_avg = sum(len(item) for item in draft_actions) / len(draft_actions)
        final_avg = sum(len(item) for item in final_actions) / len(final_actions)
        if draft_avg - final_avg >= 10:
            patterns.append(
                pattern(
                    "diagnosis", "prefer-shorter-next-actions",
                    "Client rewrote health report actions into shorter directives.",
                    "Keep diagnosis next actions short, direct, and operational rather than overly explanatory.",
                )
            )
    categories = {
        "emphasize-keyword-fit": ["keyword", "关键词", "topic", "选题", "niche", "赛道"],
        "emphasize-cover-hook": ["cover", "标题", "hook", "封面"],
        "emphasize-compliance-review": ["compliance", "risk", "违规", "限流", "warning", "suppression"],
    }
    for key, words in categories.items():
        draft_hits = sum(draft.lower().count(word.lower()) for word in words)
        final_hits = sum(final.lower().count(word.lower()) for word in words)
        if final_hits - draft_hits >= 2:
            descriptions = {
                "emphasize-keyword-fit": (
                    "diagnosis", "Client added more keyword and topic-fit corrections.",
                    "Emphasize keyword fit, topic selection, and niche alignment in future diagnosis next actions.",
                ),
                "emphasize-cover-hook": (
                    "diagnosis", "Client added more cover or title hook corrections.",
                    "Emphasize title hooks and cover revisions when diagnosing weak note performance.",
                ),
                "emphasize-compliance-review": (
                    "diagnosis", "Client strengthened compliance or suppression review steps.",
                    "Escalate compliance and suppression checks whenever the health report shows weak distribution.",
                ),
            }
            type_name, description, rule = descriptions[key]
            patterns.append(pattern(type_name, key, description, rule))
    patterns.extend(detect_text_bias_patterns(draft, final))
    return patterns


def detect_text_bias_patterns(draft: str, final: str) -> list[dict[str, str]]:
    patterns = []
    draft_emoji = emoji_count(draft)
    final_emoji = emoji_count(final)
    if draft_emoji > final_emoji:
        patterns.append(
            pattern(
                "expression", "reduce-emoji-usage",
                "Client removed emoji from the revised artifact.",
                "Use fewer emoji and keep the copy cleaner unless the client explicitly wants a playful style.",
            )
        )
    elif final_emoji > draft_emoji:
        patterns.append(
            pattern(
                "expression", "allow-more-emoji",
                "Client added emoji into the revised artifact.",
                "Allow moderate emoji usage when it improves scanning or platform-native tone.",
            )
        )

    if numeric_count(final) - numeric_count(draft) >= 2:
        patterns.append(
            pattern(
                "title", "prefer-number-hooks",
                "Client added more numeric hooks in the revised copy.",
                "Prefer number-led hooks when drafting titles and structured note ideas.",
            )
        )
    if question_count(final) - question_count(draft) >= 2:
        patterns.append(
            pattern(
                "title", "prefer-question-hooks",
                "Client added more question-led phrasing.",
                "Use question-led hooks more often in titles and diagnostic summaries.",
            )
        )
    return patterns


def detect_generic_patterns(draft: str, final: str) -> list[dict[str, str]]:
    patterns = detect_text_bias_patterns(draft, final)
    draft_lines = [line.strip() for line in draft.splitlines() if line.strip()]
    final_lines = [line.strip() for line in final.splitlines() if line.strip()]
    if draft_lines and final_lines:
        draft_avg = sum(len(line) for line in draft_lines) / len(draft_lines)
        final_avg = sum(len(line) for line in final_lines) / len(final_lines)
        if draft_avg - final_avg >= 8:
            patterns.append(
                pattern(
                    "expression", "prefer-shorter-lines",
                    "Client shortened average line length in the revised artifact.",
                    "Prefer shorter lines and tighter phrasing when drafting client-facing Xiaohongshu artifacts.",
                )
            )
    return patterns


def detect_patterns(draft_path: Path, final_path: Path) -> list[dict[str, str]]:
    draft = read_text(draft_path)
    final = read_text(final_path)
    name = draft_path.name.lower() + " " + final_path.name.lower()
    if "content-calendar" in name or "daily-ops" in name:
        return dedupe_patterns(detect_calendar_patterns(draft, final))
    if "health-report" in name:
        return dedupe_patterns(detect_health_patterns(draft, final))
    return dedupe_patterns(detect_generic_patterns(draft, final))


def dedupe_patterns(patterns: list[dict[str, str]]) -> list[dict[str, str]]:
    seen = {}
    for item in patterns:
        seen[item["key"]] = item
    return list(seen.values())


def pattern(type_name: str, key: str, description: str, rule: str) -> dict[str, str]:
    return {"type": type_name, "key": key, "description": description, "rule": rule}


def write_lesson(client_dir: Path, draft_path: Path, final_path: Path, patterns: list[dict[str, str]]) -> Path:
    lessons_dir = client_dir / "lessons"
    lessons_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lesson_path = lessons_dir / f"{timestamp}.json"
    payload = {
        "created_at": timestamp,
        "draft": str(draft_path),
        "final": str(final_path),
        "patterns": patterns,
    }
    lesson_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    return lesson_path


def summarize_lessons(client_dir: Path) -> dict[str, dict[str, object]]:
    grouped: dict[str, dict[str, object]] = {}
    for lesson_file in sorted((client_dir / "lessons").glob("*.json")):
        lesson = json.loads(lesson_file.read_text())
        for item in lesson.get("patterns", []):
            entry = grouped.setdefault(
                item["key"],
                {
                    "type": item["type"],
                    "description": item["description"],
                    "rule": item["rule"],
                    "occurrences": 0,
                    "last_seen": lesson["created_at"],
                },
            )
            entry["occurrences"] += 1
            entry["description"] = item["description"]
            entry["rule"] = item["rule"]
            entry["last_seen"] = lesson["created_at"]
    for entry in grouped.values():
        entry["confidence"] = min(10.0, round(1.5 + entry["occurrences"] * 1.5, 1))
    return grouped


def write_playbook(client_dir: Path, summary: dict[str, dict[str, object]]) -> Path:
    playbook_path = client_dir / "playbook.md"
    lines = [
        "# Client Playbook",
        "",
        f"- Client Slug: {client_dir.name}",
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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--client-dir", required=True, help="Path to the client workspace")
    parser.add_argument("--draft", help="Path to the original generated artifact")
    parser.add_argument("--final", help="Path to the client-edited artifact")
    parser.add_argument("--summarize", action="store_true", help="Rebuild playbook from existing lessons only")
    parser.add_argument("--json", action="store_true", help="Emit JSON summary")
    args = parser.parse_args()

    client_dir = Path(args.client_dir).resolve()
    if args.summarize:
        summary = summarize_lessons(client_dir)
        playbook_path = write_playbook(client_dir, summary)
        payload = {"playbook": str(playbook_path), "rules": summary}
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print(f"playbook={playbook_path}")
            print(f"rules={len(summary)}")
        return 0

    if not args.draft or not args.final:
        raise SystemExit("Provide --draft and --final, or use --summarize.")

    draft_path = Path(args.draft).resolve()
    final_path = Path(args.final).resolve()
    patterns = detect_patterns(draft_path, final_path)
    lesson_path = write_lesson(client_dir, draft_path, final_path, patterns)
    summary = summarize_lessons(client_dir)
    playbook_path = write_playbook(client_dir, summary)

    payload = {
        "lesson": str(lesson_path),
        "playbook": str(playbook_path),
        "patterns": patterns,
        "rules": summary,
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"lesson={lesson_path}")
        print(f"playbook={playbook_path}")
        print(f"patterns={len(patterns)}")
        for item in patterns:
            print(f"pattern={item['key']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
