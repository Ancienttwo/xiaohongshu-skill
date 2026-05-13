#!/usr/bin/env python3
"""Collect live Xiaohongshu research through xiaohongshu-cli."""

from __future__ import annotations

import argparse
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from workspace_parsing import extract_bullets, extract_keyword_map, extract_section, parse_metadata, read_text
from xhs_cli_utils import DEFAULT_XHS_BINARY, XhsCliError, run_xhs_command, write_json


def slugify(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff]+", "-", value.strip()).strip("-").lower()
    return normalized or "xhs"


def table_cell(value: Any) -> str:
    text = str(value or "").replace("\n", " ").replace("|", "/").strip()
    return text or "Unknown"


def first_value(*values: Any) -> Any:
    for value in values:
        if value not in (None, "", [], {}):
            return value
    return ""


def deep_get(data: dict[str, Any], *path: str) -> Any:
    current: Any = data
    for key in path:
        if not isinstance(current, dict):
            return ""
        current = current.get(key)
    return current


def visible_count(value: Any) -> str:
    if value in (None, ""):
        return "0"
    return str(value)


def seed_keywords(brief_markdown: str, analysis_markdown: str, metadata: dict[str, str]) -> list[str]:
    candidates: list[str] = []
    for key in ["Industry", "Client Name"]:
        value = metadata.get(key, "").strip()
        if value and value.upper() != "TODO":
            candidates.append(value)

    main_vertical = extract_section(brief_markdown, "Main Vertical")
    if main_vertical and main_vertical.upper() != "TODO":
        candidates.append(main_vertical.splitlines()[0].strip())

    for section_name in ["Subtopics", "Offer", "Target Audience"]:
        candidates.extend(extract_bullets(extract_section(brief_markdown, section_name)))

    keyword_map = extract_keyword_map(analysis_markdown)
    candidates.extend(keyword_map.get("core", []))
    candidates.extend(keyword_map.get("long_tail", []))

    unique = []
    seen = set()
    for item in candidates:
        cleaned = item.strip()
        if not cleaned or cleaned.upper() == "TODO" or cleaned in seen:
            continue
        seen.add(cleaned)
        unique.append(cleaned)
    return unique


def note_card_from_item(item: dict[str, Any]) -> dict[str, Any]:
    note_card = item.get("note_card", {})
    return note_card if isinstance(note_card, dict) else {}


def extract_note_summary(item: dict[str, Any], keyword: str) -> dict[str, str]:
    card = note_card_from_item(item)
    user = first_value(card.get("user"), card.get("user_info"), item.get("user"))
    if not isinstance(user, dict):
        user = {}
    interact = first_value(card.get("interact_info"), item.get("interact_info"))
    if not isinstance(interact, dict):
        interact = {}

    note_id = first_value(item.get("id"), item.get("note_id"), card.get("note_id"), card.get("id"))
    title = first_value(card.get("display_title"), card.get("title"), item.get("title"), item.get("display_title"))
    account = first_value(
        user.get("nickname"),
        user.get("nick_name"),
        user.get("name"),
        card.get("nickname"),
        item.get("nickname"),
    )
    user_id = first_value(user.get("user_id"), user.get("id"), item.get("user_id"))
    desc = first_value(card.get("desc"), item.get("desc"), card.get("description"), item.get("description"))

    return {
        "note_id": str(note_id),
        "title": str(title or "Untitled note"),
        "account": str(account or "Unknown account"),
        "user_id": str(user_id or ""),
        "content_type": str(first_value(card.get("type"), item.get("type"), "note")),
        "cover_style": infer_cover_style(card),
        "visible_metrics": format_metrics(interact),
        "hook_angle": infer_hook_angle(str(title or ""), str(desc or "")),
        "keywords": keyword,
        "desc": str(desc or ""),
    }


def format_metrics(interact: dict[str, Any]) -> str:
    likes = first_value(interact.get("liked_count"), interact.get("like_count"), interact.get("likes"))
    collects = first_value(interact.get("collected_count"), interact.get("collect_count"), interact.get("collects"))
    comments = first_value(interact.get("comment_count"), interact.get("comments"))
    return f"likes={visible_count(likes)}, collects={visible_count(collects)}, comments={visible_count(comments)}"


def infer_cover_style(card: dict[str, Any]) -> str:
    note_type = str(first_value(card.get("type"), card.get("note_type"), "")).lower()
    if "video" in note_type:
        return "video cover"
    if card.get("image_list") or card.get("cover"):
        return "image-led cover"
    return "unknown cover"


def infer_hook_angle(title: str, desc: str) -> str:
    text = f"{title} {desc}"
    if "?" in text or "？" in text:
        return "question-led hook"
    if re.search(r"\d|一|二|三|四|五|六|七|八|九|十", title):
        return "number/list hook"
    if any(word in text for word in ["避雷", "踩坑", "后悔", "不要"]):
        return "risk-avoidance hook"
    if any(word in text for word in ["教程", "方法", "步骤", "攻略"]):
        return "how-to hook"
    return "benefit-led hook"


def extract_comments(data: Any, limit: int) -> list[str]:
    if not isinstance(data, dict):
        return []
    candidates = first_value(data.get("comments"), data.get("comment_list"), data.get("items"))
    if not isinstance(candidates, list):
        return []
    comments = []
    for item in candidates[:limit]:
        if not isinstance(item, dict):
            continue
        content = first_value(item.get("content"), deep_get(item, "comment", "content"), item.get("text"))
        if content:
            comments.append(str(content))
    return comments


def write_evidence(evidence_dir: Path, name: str, payload: Any) -> Path:
    path = evidence_dir / f"{name}.json"
    write_json(path, payload)
    return path


def run_and_record(
    evidence_dir: Path,
    name: str,
    args: list[str],
    *,
    binary: str,
    timeout: int,
) -> tuple[Any | None, Path]:
    try:
        result = run_xhs_command(args, binary=binary, timeout=timeout)
        path = write_evidence(
            evidence_dir,
            name,
            {
                "command": ["xhs", *result.args],
                "envelope": result.envelope,
                "stderr": result.stderr,
            },
        )
        return result.data, path
    except XhsCliError as exc:
        path = write_evidence(
            evidence_dir,
            name,
            {
                "command": ["xhs", *args],
                "ok": False,
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.details,
                    "returncode": exc.returncode,
                },
            },
        )
        return None, path


def build_accounts(notes: list[dict[str, str]]) -> list[dict[str, str]]:
    accounts: dict[str, dict[str, str]] = {}
    for note in notes:
        key = note.get("user_id") or note.get("account") or "unknown"
        if key not in accounts:
            accounts[key] = {
                "account": note.get("account", "Unknown account"),
                "followers": "unknown",
                "persona": "inferred from live note sample",
                "bio": "not captured by search result",
                "cadence": "needs user-posts check if required",
                "buckets": note.get("keywords", ""),
                "notes": note.get("title", ""),
            }
        else:
            accounts[key]["notes"] = "; ".join(filter(None, [accounts[key]["notes"], note.get("title", "")]))[:220]
            if note.get("keywords") and note["keywords"] not in accounts[key]["buckets"]:
                accounts[key]["buckets"] = f"{accounts[key]['buckets']}, {note['keywords']}"
    return list(accounts.values())[:5]


def build_patterns(notes: list[dict[str, str]]) -> list[str]:
    by_angle: dict[str, int] = {}
    for note in notes:
        by_angle[note["hook_angle"]] = by_angle.get(note["hook_angle"], 0) + 1
    if not by_angle:
        return ["TODO"]
    ranked = sorted(by_angle.items(), key=lambda item: (-item[1], item[0]))
    return [f"{angle}: observed in {count} sampled notes" for angle, count in ranked[:3]]


def build_markdown(
    *,
    metadata: dict[str, str],
    keywords: list[str],
    notes: list[dict[str, str]],
    comments_by_note: dict[str, list[str]],
    evidence_dir: Path,
) -> str:
    accounts = build_accounts(notes)
    patterns = build_patterns(notes)
    core_keywords = keywords[:5] or [metadata.get("Industry", "小红书")]
    long_tail = [note["title"] for note in notes[:5]]
    trigger_keywords = sorted({note["hook_angle"] for note in notes})[:5] or ["TODO"]
    comment_count = sum(len(items) for items in comments_by_note.values())

    lines = [
        "# 02 Competitor Analysis",
        "",
        f"- Client Name: {metadata.get('Client Name', 'Unknown')}",
        f"- Industry: {metadata.get('Industry', 'Unknown')}",
        f"- Research Date: {datetime.now().date().isoformat()}",
        "- Research Source: xhs-cli live research",
        f"- Research Evidence: {evidence_dir}",
        f"- Search Keywords: {', '.join(keywords) if keywords else 'TODO'}",
        "",
        "## Research Goal",
        "",
        f"- Find benchmark accounts and notes that can support a {metadata.get('Industry', '小红书')} launch.",
        "- Prefer transferable patterns over celebrity outliers.",
        "",
        "## Seed Search Keywords",
        "",
    ]
    lines.extend(f"- {keyword}" for keyword in (keywords or ["TODO"]))
    lines.extend(
        [
            "",
            "## Benchmark Accounts",
            "",
            "| Account | Followers | Persona | Bio Structure | Posting Cadence | Content Buckets | Notes |",
            "|---|---:|---|---|---|---|---|",
        ]
    )
    if accounts:
        lines.extend(
            "| {account} | {followers} | {persona} | {bio} | {cadence} | {buckets} | {notes} |".format(
                account=table_cell(account["account"]),
                followers=table_cell(account["followers"]),
                persona=table_cell(account["persona"]),
                bio=table_cell(account["bio"]),
                cadence=table_cell(account["cadence"]),
                buckets=table_cell(account["buckets"]),
                notes=table_cell(account["notes"]),
            )
            for account in accounts
        )
    else:
        lines.append("| TODO | TODO | TODO | TODO | TODO | TODO | TODO |")

    lines.extend(
        [
            "",
            "## Benchmark Notes",
            "",
            "| Account | Note Title | Content Type | Cover Style | Visible Metrics | Hook Angle | Keywords |",
            "|---|---|---|---|---|---|---|",
        ]
    )
    if notes:
        lines.extend(
            "| {account} | {title} | {content_type} | {cover_style} | {metrics} | {hook} | {keywords} |".format(
                account=table_cell(note["account"]),
                title=table_cell(note["title"]),
                content_type=table_cell(note["content_type"]),
                cover_style=table_cell(note["cover_style"]),
                metrics=table_cell(note["visible_metrics"]),
                hook=table_cell(note["hook_angle"]),
                keywords=table_cell(note["keywords"]),
            )
            for note in notes
        )
    else:
        lines.append("| TODO | TODO | TODO | TODO | TODO | TODO | TODO |")

    lines.extend(
        [
            "",
            "## Keyword Map",
            "",
            "### Core Keywords",
            "",
        ]
    )
    lines.extend(f"- {keyword}" for keyword in core_keywords)
    lines.extend(["", "### Long-tail Keywords", ""])
    lines.extend(f"- {keyword}" for keyword in (long_tail or ["TODO"]))
    lines.extend(["", "### Trigger Keywords", ""])
    lines.extend(f"- {keyword}" for keyword in trigger_keywords)

    lines.extend(["", "## Repeatable Content Patterns", ""])
    lines.extend(f"{index}. {pattern}" for index, pattern in enumerate(patterns, 1))
    lines.extend(
        [
            "",
            "## Research Summary",
            "",
            f"- What title patterns work repeatedly: {patterns[0] if patterns else 'TODO'}",
            f"- What posting cadence seems sustainable: Search results alone do not prove cadence; verify with user-posts before using cadence as strategy.",
            f"- What hooks or covers deserve copying: {', '.join(trigger_keywords) if trigger_keywords else 'TODO'}",
            f"- What keyword opportunities look under-served: compare sampled titles against {', '.join(core_keywords[:3]) if core_keywords else 'TODO'}.",
            f"- Evidence captured: {len(notes)} notes, {len(accounts)} accounts, {comment_count} comments.",
        ]
    )
    if comments_by_note:
        lines.extend(["", "## Comment Signals", ""])
        for note_id, comments in comments_by_note.items():
            lines.append(f"- {note_id}: {' / '.join(table_cell(comment) for comment in comments)}")

    return "\n".join(lines).rstrip() + "\n"


def collect_research(args: argparse.Namespace) -> int:
    brief_path = Path(args.brief)
    output_path = Path(args.output)
    analysis_markdown = read_text(output_path)
    brief_markdown = read_text(brief_path)
    metadata = parse_metadata(brief_markdown)
    keywords = seed_keywords(brief_markdown, analysis_markdown, metadata)[: args.max_keywords]

    if not keywords:
        raise SystemExit("NEEDS_CONTEXT: 01-client-brief.md 缺少可搜索的行业、主题或受众关键词。")

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    evidence_dir = Path(args.evidence_dir) if args.evidence_dir else output_path.parent / "xhs-evidence" / timestamp
    evidence_dir.mkdir(parents=True, exist_ok=True)

    notes: list[dict[str, str]] = []
    seen_note_ids: set[str] = set()
    search_failures = 0
    for index, keyword in enumerate(keywords, 1):
        data, _path = run_and_record(
            evidence_dir,
            f"{index:02d}-search-{slugify(keyword)}",
            ["search", keyword, "--sort", args.sort, "--type", args.note_type, "--page", str(args.page)],
            binary=args.xhs_binary,
            timeout=args.timeout,
        )
        if not isinstance(data, dict):
            search_failures += 1
            continue
        items = data.get("items", [])
        if not isinstance(items, list):
            continue
        for item in items[: args.results_per_keyword]:
            if not isinstance(item, dict):
                continue
            note = extract_note_summary(item, keyword)
            note_id = note.get("note_id", "")
            dedupe_key = note_id or f"{note['account']}::{note['title']}"
            if dedupe_key in seen_note_ids:
                continue
            seen_note_ids.add(dedupe_key)
            notes.append(note)

    if not notes and search_failures == len(keywords):
        print("BLOCKED: xhs live research failed for every seed keyword.")
        print(f"evidence_dir={evidence_dir}")
        return 2

    read_targets = [note for note in notes if note.get("note_id")][: args.read_limit]
    for index, note in enumerate(read_targets, 1):
        note_id = note["note_id"]
        data, _path = run_and_record(
            evidence_dir,
            f"{index:02d}-read-{slugify(note_id)}",
            ["read", note_id],
            binary=args.xhs_binary,
            timeout=args.timeout,
        )
        if isinstance(data, dict):
            detail_card = data.get("note_card", data)
            if isinstance(detail_card, dict):
                note["desc"] = str(first_value(note.get("desc"), detail_card.get("desc"), detail_card.get("description")))

    comments_by_note: dict[str, list[str]] = {}
    for index, note in enumerate(read_targets[: args.comment_notes], 1):
        note_id = note["note_id"]
        data, _path = run_and_record(
            evidence_dir,
            f"{index:02d}-comments-{slugify(note_id)}",
            ["comments", note_id],
            binary=args.xhs_binary,
            timeout=args.timeout,
        )
        comments = extract_comments(data, args.comments_per_note)
        if comments:
            comments_by_note[note_id] = comments

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        build_markdown(
            metadata=metadata,
            keywords=keywords,
            notes=notes,
            comments_by_note=comments_by_note,
            evidence_dir=evidence_dir,
        )
    )
    print(f"written={output_path}")
    print(f"evidence_dir={evidence_dir}")
    print(f"notes={len(notes)}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--brief", required=True, help="Path to 01-client-brief.md")
    parser.add_argument("--output", required=True, help="Path to 02-competitor-analysis.md")
    parser.add_argument("--evidence-dir", help="Directory for raw xhs JSON evidence")
    parser.add_argument("--xhs-binary", default=DEFAULT_XHS_BINARY, help="Path or name of xhs executable")
    parser.add_argument("--max-keywords", type=int, default=3, help="Maximum seed keywords to search")
    parser.add_argument("--results-per-keyword", type=int, default=5, help="Maximum search results kept per keyword")
    parser.add_argument("--read-limit", type=int, default=3, help="Maximum notes to read after search")
    parser.add_argument("--comment-notes", type=int, default=2, help="Maximum notes to sample comments from")
    parser.add_argument("--comments-per-note", type=int, default=5, help="Maximum comments summarized per sampled note")
    parser.add_argument("--sort", default="popular", choices=["general", "popular", "latest"], help="xhs search sort")
    parser.add_argument("--note-type", default="all", choices=["all", "video", "image"], help="xhs search note type")
    parser.add_argument("--page", type=int, default=1, help="xhs search page")
    parser.add_argument("--timeout", type=int, default=90, help="Per-command timeout in seconds")
    args = parser.parse_args(argv)
    return collect_research(args)


if __name__ == "__main__":
    raise SystemExit(main())
