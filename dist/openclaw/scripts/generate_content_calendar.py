#!/usr/bin/env python3
"""Generate a Xiaohongshu content calendar using client inputs and playbook rules."""

from __future__ import annotations

import argparse
import re
from datetime import date
from pathlib import Path

from playbook_utils import has_rule, load_playbook_rules
from workspace_parsing import (
    extract_benchmark_accounts,
    extract_benchmark_notes,
    extract_keyword_map,
    extract_repeatable_patterns,
    extract_research_summary_points,
    extract_topic_architecture,
    parse_metadata,
    read_text,
)


def clean_topic(value: str) -> str:
    return value.replace("Optional ", "").strip()


def with_suffix(topic: str, suffix: str) -> str:
    topic = clean_topic(topic)
    if suffix in topic:
        return topic
    duplicate_markers = {
        "避坑清单": ["避坑", "清单"],
        "别再乱做": ["别再", "乱做"],
        "结果对比": ["对比", "结果"],
        "复盘总结": ["复盘", "总结"],
    }
    markers = duplicate_markers.get(suffix, [])
    if any(marker in topic for marker in markers):
        return topic
    return f"{topic}{suffix}"


def dedupe(items: list[str]) -> list[str]:
    seen = set()
    result = []
    for item in items:
        cleaned = clean_topic(item).strip()
        if not cleaned or cleaned.upper() == "TODO" or cleaned in seen:
            continue
        seen.add(cleaned)
        result.append(cleaned)
    return result


def build_content_seeds(strategy_markdown: str, analysis_markdown: str, fallback_topic: str) -> list[str]:
    topics = extract_topic_architecture(strategy_markdown)
    keyword_map = extract_keyword_map(analysis_markdown)
    benchmark_notes = extract_benchmark_notes(analysis_markdown)
    benchmark_keywords = [note.get("Keywords", "") for note in benchmark_notes]
    seeds = dedupe(topics + keyword_map["core"] + keyword_map["long_tail"] + benchmark_keywords)
    return seeds or [fallback_topic]


def build_title(topic: str, day_name: str, rules: dict[str, dict[str, object]]) -> str:
    short = has_rule(rules, "prefer-shorter-titles")
    question = has_rule(rules, "prefer-question-hooks")
    number = has_rule(rules, "prefer-number-hooks") and not question
    more_emoji = has_rule(rules, "allow-more-emoji", 3.0)
    less_emoji = has_rule(rules, "reduce-emoji-usage", 3.0)

    topic = clean_topic(topic)
    if question:
        title = f"{topic}到底怎么做？"
    elif number:
        title = f"3步讲清{topic}"
    else:
        defaults = {
            "D3": f"{topic}新手先看",
            "D4": with_suffix(topic, "避坑清单"),
            "D5": with_suffix(topic, "别再乱做"),
            "D6": with_suffix(topic, "结果对比"),
            "D7": with_suffix(topic, "复盘总结"),
        }
        title = defaults.get(day_name, f"{topic}怎么做")

    if more_emoji and not less_emoji:
        title += "✨"
    if short and len(title) > 16:
        title = title[:16].rstrip("，。！？?") + ("？" if question else "")
    return title


def infer_title_family(reference_title: str) -> str:
    if "？" in reference_title or "?" in reference_title:
        return "question"
    if any(char.isdigit() for char in reference_title):
        return "number"
    if any(token in reference_title for token in ["别再", "千万别", "不要"]):
        return "warning"
    if any(token in reference_title for token in ["对比", "VS", "vs"]):
        return "comparison"
    return "default"


def title_features(title: str) -> set[str]:
    features = set()
    if "？" in title or "?" in title:
        features.add("question")
    if any(char.isdigit() for char in title):
        features.add("number")
    if any(token in title for token in ["别再", "千万别", "不要", "避坑"]):
        features.add("warning")
    if any(token in title for token in ["对比", "差别", "VS", "vs"]):
        features.add("comparison")
    if any(token in title for token in ["怎么做", "怎么选", "先看", "攻略", "指南"]):
        features.add("intent")
    return features


def normalize_title(title: str) -> str:
    title = re.sub(r"\s+", "", title.strip())
    title = title.replace("??", "？").replace("？？", "？")
    return title


def merge_trigger_topic(trigger: str, topic: str, suffix: str) -> str:
    trigger = clean_topic(trigger)
    topic = clean_topic(topic)
    if not trigger:
        return normalize_title(f"{topic}{suffix}")
    if topic in trigger:
        return normalize_title(f"{trigger}{suffix}")
    if trigger in topic:
        return normalize_title(f"{topic}{suffix}")
    overlap = ""
    max_len = min(len(trigger), len(topic))
    for size in range(max_len, 0, -1):
        if trigger.endswith(topic[:size]):
            overlap = topic[:size]
            break
    if overlap:
        return normalize_title(f"{trigger}{topic[len(overlap):]}{suffix}")
    return normalize_title(f"{trigger}{topic}{suffix}")


def build_title_candidates(
    topic: str,
    day_name: str,
    rules: dict[str, dict[str, object]],
    benchmark_note: dict[str, str] | None,
    trigger_keywords: list[str],
) -> list[str]:
    topic = clean_topic(topic)
    benchmark_title = benchmark_note.get("Note Title", "") if benchmark_note else ""
    family = infer_title_family(benchmark_title)

    candidates = [
        build_title(topic, day_name, rules),
        f"{topic}到底怎么做？",
        f"{topic}为什么总反复？",
        f"{topic}到底怎么选？",
        f"3步讲清{topic}",
        f"{topic}先看这3点",
        f"{topic}别再乱做了",
        f"{topic}新手最容易踩的坑",
        f"{topic}正确做法对比",
        f"{topic}结果差别有多大",
    ]

    if day_name in {"D4", "D5"}:
        candidates.extend([with_suffix(topic, "避坑清单"), f"{topic}最容易翻车的3步"])
    if day_name in {"D6", "D7"}:
        candidates.extend([with_suffix(topic, "复盘总结"), f"{topic}前后差别有多大"])

    for trigger in trigger_keywords[:3]:
        candidates.append(merge_trigger_topic(trigger, topic, "怎么做？"))
        candidates.append(merge_trigger_topic(trigger, topic, "攻略"))

    if family == "question":
        candidates.extend([f"{topic}为什么总不好？", f"{topic}到底哪里错了？"])
    elif family == "warning":
        candidates.extend([f"{topic}千万别这样做", f"{topic}避坑先看这篇"])
    elif family == "comparison":
        candidates.extend([f"{topic}正确做法对比", f"{topic}前后差别真的大"])
    elif family == "number":
        candidates.extend([f"{topic}3个关键点", f"3步搞懂{topic}"])

    deduped = []
    seen = set()
    for candidate in candidates:
        normalized = normalize_title(candidate)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)
    return deduped


def score_title_candidate(
    title: str,
    topic: str,
    rules: dict[str, dict[str, object]],
    benchmark_note: dict[str, str] | None,
    trigger_keywords: list[str],
) -> tuple[int, list[str]]:
    score = 0
    reasons = []
    features = title_features(title)
    benchmark_features = title_features(benchmark_note.get("Note Title", "")) if benchmark_note else set()

    if clean_topic(topic) in title:
        score += 4
        reasons.append("contains primary keyword")
    if len(title) <= 20:
        score += 2
        reasons.append("length <= 20")
    elif len(title) <= 24:
        score += 1
        reasons.append("length acceptable")
    else:
        score -= 1
        reasons.append("too long")

    if has_rule(rules, "prefer-question-hooks") and "question" in features:
        score += 3
        reasons.append("matches playbook question hook")
    if has_rule(rules, "prefer-number-hooks") and "number" in features:
        score += 3
        reasons.append("matches playbook number hook")
    if has_rule(rules, "prefer-shorter-titles") and len(title) <= 16:
        score += 1
        reasons.append("matches short-title preference")

    overlap = features & benchmark_features
    if overlap:
        score += 2
        reasons.append(f"matches benchmark hook family: {', '.join(sorted(overlap))}")

    if any(trigger in title for trigger in trigger_keywords):
        score += 1
        reasons.append("uses trigger keyword")
    if "intent" in features:
        score += 1
        reasons.append("clear action/search intent")
    if any(token in title for token in ["先看", "攻略", "避坑", "对比"]):
        score += 1
        reasons.append("strong Xiaohongshu packaging")

    return score, reasons


def select_title_pack(
    topic: str,
    day_name: str,
    rules: dict[str, dict[str, object]],
    benchmark_note: dict[str, str] | None,
    trigger_keywords: list[str],
) -> list[dict[str, object]]:
    scored = []
    for candidate in build_title_candidates(topic, day_name, rules, benchmark_note, trigger_keywords):
        score, reasons = score_title_candidate(candidate, topic, rules, benchmark_note, trigger_keywords)
        scored.append({"title": candidate, "score": score, "reasons": reasons})
    scored.sort(key=lambda item: (-int(item["score"]), len(str(item["title"])), str(item["title"])))
    return scored[:3]


def make_title_variants(
    topic: str,
    day_name: str,
    rules: dict[str, dict[str, object]],
    benchmark_note: dict[str, str] | None,
) -> list[str]:
    topic = clean_topic(topic)
    variants = [build_title(topic, day_name, rules)]
    family = infer_title_family(benchmark_note.get("Note Title", "")) if benchmark_note else "default"
    if has_rule(rules, "prefer-question-hooks") or family == "question":
        variants.append(f"{topic}为什么总反复？")
        variants.append(f"{topic}到底怎么选？")
    elif has_rule(rules, "prefer-number-hooks") or family == "number":
        variants.append(f"3步讲清{topic}")
        variants.append(f"{topic}先看这3点")
    elif family == "warning":
        variants.append(f"{topic}别再乱做了")
        variants.append(f"{topic}新手最容易踩的坑")
    elif family == "comparison":
        variants.append(f"{topic}前后差别有多大")
        variants.append(f"{topic}正确做法对比")
    else:
        variants.append(f"{topic}新手先看")
        variants.append(f"{topic}避坑清单")

    deduped = []
    seen = set()
    for item in variants:
        if item not in seen:
            seen.add(item)
            deduped.append(item)
    return deduped[:3]


def publish_count_for_day(day_name: str, rules: dict[str, dict[str, object]]) -> int:
    if day_name in {"D1", "D2"}:
        return 0
    if day_name == "D3":
        return 1
    if has_rule(rules, "reduce-daily-volume"):
        return 1
    if has_rule(rules, "increase-daily-volume"):
        return 3
    return 2


def content_types_for_day(day_name: str, count: int) -> str:
    defaults = {
        "D3": ["how-to"],
        "D4": ["checklist", "proof", "comparison"],
        "D5": ["myth-busting", "diary", "checklist"],
        "D6": ["proof", "comparison", "how-to"],
        "D7": ["checklist", "diary", "proof"],
    }
    items = defaults.get(day_name, ["how-to"])
    return " / ".join(items[:count])


def cover_direction(topic: str, rules: dict[str, dict[str, object]]) -> str:
    if has_rule(rules, "emphasize-cover-hook"):
        return f"{topic}强对比封面"
    return f"{topic}结果导向封面"


def cover_direction_from_benchmark(
    topic: str,
    rules: dict[str, dict[str, object]],
    benchmark_note: dict[str, str] | None,
) -> str:
    if benchmark_note:
        cover_style = benchmark_note.get("Cover Style", "").strip()
        if cover_style and cover_style.upper() != "TODO":
            return f"{cover_style} + {clean_topic(topic)}主题"
    return cover_direction(topic, rules)


def choose_benchmark_note(topic: str, benchmark_notes: list[dict[str, str]], day_index: int) -> dict[str, str] | None:
    if not benchmark_notes:
        return None
    normalized_topic = clean_topic(topic)
    for note in benchmark_notes:
        keywords = note.get("Keywords", "")
        note_title = note.get("Note Title", "")
        if normalized_topic and (normalized_topic in keywords or normalized_topic in note_title):
            return note
    return benchmark_notes[day_index % len(benchmark_notes)]


def publish_times(count: int) -> str:
    slots = {
        1: "20:00",
        2: "12:00 / 20:00",
        3: "10:00 / 15:00 / 20:00",
    }
    return slots.get(count, "20:00")


def day_outline(
    day_name: str,
    topic: str,
    rules: dict[str, dict[str, object]],
    pattern_hint: str | None,
    summary_hint: str | None,
    benchmark_note: dict[str, str] | None,
    selected_titles: list[dict[str, object]],
) -> str:
    title_variants = selected_titles or [{"title": build_title(topic, day_name, rules), "score": 0, "reasons": []}]
    lines = [
        f"### {day_name}",
        "",
        f"- Hook: {title_variants[0]['title']}",
        f"- Selected title score: {title_variants[0]['score']}",
        f"- Title variants: {' | '.join(item['title'] for item in title_variants[1:]) if len(title_variants) > 1 else 'none'}",
        f"- Main keyword: {clean_topic(topic)}",
        "- Proof element: add one result, comparison, or concrete observation.",
    ]
    lines.append(
        f"- Title selection rationale: {'; '.join(title_variants[0]['reasons']) if title_variants[0]['reasons'] else 'default fallback'}"
    )
    if benchmark_note:
        lines.append(
            f"- Reference benchmark note: {benchmark_note.get('Note Title', 'n/a')} ({benchmark_note.get('Hook Angle', 'n/a')} / {benchmark_note.get('Cover Style', 'n/a')})"
        )
    if pattern_hint:
        lines.append(f"- Borrowed benchmark pattern: {pattern_hint}")
    if summary_hint:
        lines.append(f"- Research angle to preserve: {summary_hint}")
    if has_rule(rules, "prefer-question-hooks"):
        lines.append("- CTA: ask one direct question in the note ending.")
    elif has_rule(rules, "prefer-number-hooks"):
        lines.append("- CTA: summarize the note into a numbered takeaway.")
    else:
        lines.append("- CTA: use a soft save-or-comment invitation.")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--brief", required=True, help="Path to 01-client-brief.md")
    parser.add_argument("--strategy", required=True, help="Path to 03-account-strategy.md")
    parser.add_argument("--analysis", help="Path to 02-competitor-analysis.md")
    parser.add_argument("--output", required=True, help="Path to 04-content-calendar.md")
    parser.add_argument("--playbook", help="Path to playbook.md")
    args = parser.parse_args()

    brief_path = Path(args.brief)
    strategy_path = Path(args.strategy)
    output_path = Path(args.output)
    analysis_path = Path(args.analysis) if args.analysis else output_path.parent / "02-competitor-analysis.md"
    playbook_path = Path(args.playbook) if args.playbook else output_path.parent / "playbook.md"

    brief = read_text(brief_path)
    strategy = read_text(strategy_path)
    analysis = read_text(analysis_path)
    metadata = parse_metadata(brief)
    strategy_meta = parse_metadata(strategy)
    rules = load_playbook_rules(playbook_path)
    fallback_topic = strategy_meta.get("Main Vertical") or metadata.get("Industry") or "小红书起号"
    if not fallback_topic or fallback_topic.upper() == "TODO":
        fallback_topic = metadata.get("Industry") or "小红书起号"
    topics = build_content_seeds(strategy, analysis, fallback_topic)
    keyword_map = extract_keyword_map(analysis)
    patterns = extract_repeatable_patterns(analysis)
    summary_points = extract_research_summary_points(analysis)
    benchmark_notes = extract_benchmark_notes(analysis)
    benchmark_accounts = extract_benchmark_accounts(analysis)
    trigger_keywords = keyword_map["trigger"]

    days = ["D1", "D2", "D3", "D4", "D5", "D6", "D7"]
    rows = []
    outlines = []
    topic_index = 0
    benchmark_anchors = []
    for day_offset, day_name in enumerate(days):
        count = publish_count_for_day(day_name, rules)
        if count == 0:
            rows.append(f"| {day_name} | 0 | - | nurture only | - | - | - |")
            continue
        day_topics = []
        for _ in range(count):
            day_topics.append(topics[topic_index % len(topics)])
            topic_index += 1
        chosen_note = choose_benchmark_note(day_topics[0], benchmark_notes, day_offset)
        selected_title_packs = [
            select_title_pack(topic, day_name, rules, chosen_note, trigger_keywords) for topic in day_topics
        ]
        titles = " / ".join(pack[0]["title"] for pack in selected_title_packs)
        keywords = " / ".join(clean_topic(topic) for topic in day_topics)
        cover = " / ".join(cover_direction_from_benchmark(topic, rules, chosen_note) for topic in day_topics)
        pattern_hint = patterns[(topic_index - 1) % len(patterns)] if patterns else None
        summary_hint = summary_points[(topic_index - 1) % len(summary_points)] if summary_points else None
        rows.append(
            f"| {day_name} | {count} | {titles} | {content_types_for_day(day_name, count)} | {keywords} | {cover} | {publish_times(count)} |"
        )
        outlines.append(
            day_outline(
                day_name,
                day_topics[0],
                rules,
                pattern_hint,
                summary_hint,
                chosen_note,
                selected_title_packs[0],
            )
        )
        if chosen_note:
            benchmark_anchors.append(
                f"- {day_name}: {chosen_note.get('Note Title', 'n/a')} | hook `{chosen_note.get('Hook Angle', 'n/a')}` | cover `{chosen_note.get('Cover Style', 'n/a')}`"
            )

    cadence_line = "- D4-D7: 1-3 notes per day, spaced at least 4 hours apart"
    if has_rule(rules, "reduce-daily-volume"):
        cadence_line = "- D4-D7: 1 note per day by default; only increase volume when quality and proof assets are strong"
    elif has_rule(rules, "increase-daily-volume"):
        cadence_line = "- D4-D7: up to 3 notes per day when the team can sustain quality and proof"

    lines = [
        "# 04 Content Calendar",
        "",
        f"- Client Name: {metadata.get('Client Name', 'Unknown')}",
        f"- Industry: {metadata.get('Industry', 'Unknown')}",
        f"- Updated: {date.today().isoformat()}",
        f"- Source Brief: {brief_path}",
        f"- Source Strategy: {strategy_path}",
        f"- Source Analysis: {analysis_path}",
        f"- Playbook Rules Applied: {len(rules)}",
        "",
        "## Publishing Rules",
        "",
        "- D1-D2: no posting",
        "- D3: first educational note",
        cadence_line,
        "- D8-D10: optional extension only if health criteria are weak",
        "",
        "## Research Signals",
        "",
        f"- Core keywords: {', '.join(keyword_map['core']) if keyword_map['core'] else 'pending research'}",
        f"- Long-tail keywords: {', '.join(keyword_map['long_tail'][:5]) if keyword_map['long_tail'] else 'pending research'}",
        f"- Trigger keywords: {', '.join(keyword_map['trigger'][:3]) if keyword_map['trigger'] else 'pending research'}",
        f"- Repeatable patterns: {', '.join(patterns[:3]) if patterns else 'pending research'}",
        f"- Research summary focus: {'; '.join(summary_points[:2]) if summary_points else 'pending research'}",
        f"- Benchmark accounts captured: {len(benchmark_accounts)}",
        f"- Benchmark notes captured: {len(benchmark_notes)}",
        "",
        "## Benchmark Note Anchors",
        "",
        *(benchmark_anchors or ["- pending research"]),
        "",
        "## Calendar",
        "",
        "| Day | Publish Count | Title | Content Type | Keyword | Cover Direction | Publish Time |",
        "|---|---:|---|---|---|---|---|",
        *rows,
        "",
        "## Note Outlines",
        "",
        *outlines,
    ]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines).rstrip() + "\n")
    print(f"written={output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
