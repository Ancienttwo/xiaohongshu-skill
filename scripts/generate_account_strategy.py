#!/usr/bin/env python3
"""Generate a playbook-aware account strategy from brief and competitor analysis."""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

from playbook_utils import has_rule, load_playbook_rules
from workspace_parsing import (
    extract_bullets,
    extract_keyword_map,
    extract_repeatable_patterns,
    extract_section,
    extract_topic_architecture,
    parse_metadata,
    read_text,
)


def first_non_todo(values: list[str], fallback: str) -> str:
    for value in values:
        cleaned = value.strip()
        if cleaned and cleaned.upper() != "TODO":
            return cleaned
    return fallback


def choose_persona(brief_markdown: str) -> tuple[str, str, str]:
    offer = extract_section(brief_markdown, "Offer").lower()
    proof_assets = extract_section(brief_markdown, "Proof Assets").lower()
    operating_capacity = extract_section(brief_markdown, "Operating Capacity").lower()

    if any(token in offer for token in ["品牌", "brand", "product", "产品", "store", "店"]):
        return (
            "Founder/operator",
            "The client has a concrete offer and needs commercial credibility without sounding like pure advertising.",
            "Practical, direct, still personal.",
        )
    if any(token in proof_assets for token in ["案例", "case", "before", "after", "testimonial", "证言", "results"]):
        return (
            "Expert mentor",
            "The client has proof assets that can support education-led trust building.",
            "Helpful, clear, lightly authoritative.",
        )
    if any(token in operating_capacity for token in ["camera", "露脸", "video", "拍"]):
        return (
            "Diary-style practitioner",
            "The client can appear regularly, which supports diary-style trust building.",
            "Warm, personal, experience-led.",
        )
    return (
        "Curated brand voice",
        "The team needs a repeatable multi-editor voice with low dependence on one face or founder story.",
        "Consistent, friendly, operational.",
    )


def generate_name_candidates(industry: str, main_vertical: str, core_keywords: list[str]) -> list[str]:
    seed = first_non_todo([main_vertical, *core_keywords], industry)
    candidates = [
        f"{seed}研究所",
        f"{seed}笔记",
        f"{seed}指南",
    ]
    deduped = []
    seen = set()
    for item in candidates:
        if item not in seen:
            seen.add(item)
            deduped.append(item)
    return deduped[:3]


def derive_subtopics(brief_markdown: str, analysis_markdown: str, industry: str) -> list[str]:
    brief_subtopics = extract_bullets(extract_section(brief_markdown, "Subtopics"))
    if brief_subtopics:
        return [item for item in brief_subtopics if item.upper() != "TODO"][:5]

    patterns = extract_repeatable_patterns(analysis_markdown)
    if patterns:
        return patterns[:5]

    keywords = extract_keyword_map(analysis_markdown)
    combined = keywords["core"][:3] + keywords["long_tail"][:2]
    if combined:
        return combined[:5]

    return [industry, f"{industry}避坑", f"{industry}清单"]


def playbook_constraints(rules: dict[str, dict[str, object]]) -> list[str]:
    constraints = []
    if has_rule(rules, "reduce-daily-volume"):
        constraints.append("Keep the strategy narrow enough to support low-volume, high-confidence publishing.")
    if has_rule(rules, "prefer-question-hooks"):
        constraints.append("Favor topic buckets that naturally support pain-point questions.")
    if has_rule(rules, "prefer-number-hooks"):
        constraints.append("Favor topic buckets that can be expressed as steps, lists, or structured comparisons.")
    if has_rule(rules, "emphasize-cover-hook"):
        constraints.append("Choose angles with a visually obvious before/after, warning, or contrast promise.")
    if has_rule(rules, "emphasize-keyword-fit"):
        constraints.append("Bias the strategy toward high-intent searchable phrases over vague inspiration topics.")
    return constraints or ["No client-specific strategy constraints yet. Use the default positioning rules."]


def strategy_do_more(patterns: list[str], rules: dict[str, dict[str, object]]) -> str:
    base = []
    if patterns:
        base.append(f"Reuse these benchmark patterns where they fit: {', '.join(patterns[:3])}.")
    if has_rule(rules, "prefer-question-hooks"):
        base.append("Frame note ideas as pain-point questions.")
    if has_rule(rules, "emphasize-keyword-fit"):
        base.append("Keep every content bucket anchored to one searchable phrase.")
    return " ".join(base) or "Stay tightly focused on one niche and repeat proven content patterns."


def strategy_avoid(rules: dict[str, dict[str, object]]) -> str:
    warnings = [
        "Avoid mixed-topic posting, generic inspiration content, and anything that reads like an ad too early."
    ]
    if has_rule(rules, "reduce-daily-volume"):
        warnings.append("Do not plan a high-volume schedule that the client cannot sustain.")
    if has_rule(rules, "emphasize-cover-hook"):
        warnings.append("Avoid note angles that have no obvious cover promise or visual contrast.")
    return " ".join(warnings)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--brief", required=True, help="Path to 01-client-brief.md")
    parser.add_argument("--analysis", required=True, help="Path to 02-competitor-analysis.md")
    parser.add_argument("--output", required=True, help="Path to 03-account-strategy.md")
    parser.add_argument("--playbook", help="Path to playbook.md")
    args = parser.parse_args()

    brief_path = Path(args.brief)
    analysis_path = Path(args.analysis)
    output_path = Path(args.output)
    playbook_path = Path(args.playbook) if args.playbook else output_path.parent / "playbook.md"

    brief_markdown = read_text(brief_path)
    analysis_markdown = read_text(analysis_path)
    brief_meta = parse_metadata(brief_markdown)
    rules = load_playbook_rules(playbook_path)
    keywords = extract_keyword_map(analysis_markdown)
    repeatable_patterns = extract_repeatable_patterns(analysis_markdown)

    industry = brief_meta.get("Industry", "小红书")
    main_vertical = first_non_todo(
        [extract_section(brief_markdown, "Main Vertical"), *keywords["core"]],
        industry,
    )
    subtopics = derive_subtopics(brief_markdown, analysis_markdown, industry)
    persona, why_it_fits, voice = choose_persona(brief_markdown)
    name_candidates = generate_name_candidates(industry, main_vertical, keywords["core"])
    bio_keyword = first_non_todo(keywords["core"], main_vertical)
    bio_draft = f"{bio_keyword}经验分享｜持续更新实操、避坑和结果复盘"
    profile_signals = "真人头像或稳定 IP 头像；bio 只写赛道与价值，不留联系方式。"

    constraints = playbook_constraints(rules)
    compliance_risks = [
        "Public bio, captions, and comments must not include contact details.",
        "Do not stack unrelated keywords or broad lifestyle topics into the same account.",
        "Do not use exaggerated claims that cannot be supported by proof assets or client results.",
    ]

    lines = [
        "# 03 Account Strategy",
        "",
        f"- Client Name: {brief_meta.get('Client Name', 'Unknown')}",
        f"- Industry: {industry}",
        f"- Updated: {date.today().isoformat()}",
        f"- Source Brief: {brief_path}",
        f"- Source Analysis: {analysis_path}",
        f"- Playbook Rules Applied: {len(rules)}",
        "",
        "## Persona",
        "",
        f"- Chosen Persona: {persona}",
        f"- Why It Fits: {why_it_fits}",
        f"- Voice: {voice}",
        "",
        "## Search Positioning",
        "",
        "- Account Name Candidates:",
        *(f"  - {item}" for item in name_candidates),
        f"- Bio Draft: {bio_draft}",
        f"- Profile Signals: {profile_signals}",
        "",
        "## Topic Architecture",
        "",
        f"- Main Vertical: {main_vertical}",
    ]

    for idx, topic in enumerate(subtopics[:5], start=1):
        prefix = "Optional " if idx > 3 else ""
        lines.append(f"- {prefix}Subtopic {idx}: {topic}")

    lines.extend(
        [
            "",
            "## Content Boundaries",
            "",
            f"- Do more of: {strategy_do_more(repeatable_patterns, rules)}",
            f"- Avoid: {strategy_avoid(rules)}",
            "",
            "## Playbook Constraints",
            "",
        ]
    )
    lines.extend(f"- {item}" for item in constraints)
    lines.extend(
        [
            "",
            "## Compliance Risks",
            "",
        ]
    )
    lines.extend(f"{idx}. {item}" for idx, item in enumerate(compliance_risks, 1))
    lines.extend(
        [
            "",
            "## Approval Notes",
            "",
            "- Confirm the chosen persona and naming direction before generating the content calendar.",
            "- Confirm whether the benchmark patterns identified in research are truly transferable to this client's proof assets and team capacity.",
        ]
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines).rstrip() + "\n")
    print(f"written={output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
