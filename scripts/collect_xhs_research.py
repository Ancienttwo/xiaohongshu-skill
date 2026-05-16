#!/usr/bin/env python3
"""Collect live Xiaohongshu research through xiaohongshu-cli."""

from __future__ import annotations

import argparse
import os
import random
import re
import time
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


TRANSIENT_ERROR_CODES = {"xhs_timeout", "empty_output", "non_json_output", "xhs_command_failed"}
BLOCKING_ERROR_CODES = {"verification_required", "need_verify", "ip_blocked", "not_authenticated", "session_expired", "no_cookie", "missing_cookie"}


SENSITIVE_EVIDENCE_KEYS = {
    "xsec_token",
    "token",
    "cookie",
    "cookies",
    "user_id",
    "userid",
    "avatar",
    "image",
    "image_list",
    "images",
    "cover",
    "url",
    "url_default",
    "url_pre",
    "ip_location",
}


def sanitize_evidence(payload: Any) -> Any:
    """Return a share-safer copy of xhs evidence without platform/user identifiers."""
    if isinstance(payload, dict):
        cleaned: dict[str, Any] = {}
        for key, value in payload.items():
            normalized = str(key).lower()
            if normalized in SENSITIVE_EVIDENCE_KEYS or "cookie" in normalized or "token" in normalized:
                continue
            cleaned[key] = sanitize_evidence(value)
        return cleaned
    if isinstance(payload, list):
        return [sanitize_evidence(item) for item in payload]
    return payload


def write_evidence(evidence_dir: Path, name: str, payload: Any) -> Path:
    path = evidence_dir / f"{name}.json"
    write_json(path, sanitize_evidence(payload))
    os.chmod(path, 0o600)
    return path


def sleep_between_commands(delay_min: float, delay_max: float) -> None:
    if delay_max <= 0:
        return
    lower = max(0.0, delay_min)
    upper = max(lower, delay_max)
    time.sleep(random.uniform(lower, upper))


def run_and_record(
    evidence_dir: Path,
    name: str,
    args: list[str],
    *,
    binary: str,
    timeout: int,
    retries: int = 0,
    delay_min: float = 0.0,
    delay_max: float = 0.0,
    command_delay_min: float = 0.0,
    command_delay_max: float = 0.0,
) -> tuple[Any | None, Path, dict[str, Any] | None]:
    last_path = evidence_dir / f"{name}.json"
    attempts = retries + 1
    for attempt in range(1, attempts + 1):
        attempt_name = name if attempt == attempts else f"{name}-attempt-{attempt}"
        try:
            result = run_xhs_command(args, binary=binary, timeout=timeout)
            path = write_evidence(
                evidence_dir,
                attempt_name,
                {
                    "command": ["xhs", *result.args],
                    "attempt": attempt,
                    "envelope": result.envelope,
                    "stderr": result.stderr,
                },
            )
            sleep_between_commands(command_delay_min, command_delay_max)
            return result.data, path, None
        except XhsCliError as exc:
            error = {
                "code": exc.code,
                "message": exc.message,
                "details": exc.details,
                "returncode": exc.returncode,
                "attempt": attempt,
            }
            last_path = write_evidence(
                evidence_dir,
                attempt_name,
                {
                    "command": ["xhs", *args],
                    "ok": False,
                    "error": error,
                },
            )
            if exc.code in BLOCKING_ERROR_CODES:
                return None, last_path, error
            if exc.code not in TRANSIENT_ERROR_CODES or attempt >= attempts:
                sleep_between_commands(command_delay_min, command_delay_max)
                return None, last_path, error
            sleep_between_commands(command_delay_min, command_delay_max)
            sleep_between_commands(delay_min, delay_max)
    return None, last_path, {"code": "unknown_failure", "message": "xhs command failed"}


def merge_note_detail(note: dict[str, str], detail_card: dict[str, Any]) -> None:
    """Merge richer `xhs read` details into a search-derived note summary."""
    title = first_value(
        detail_card.get("display_title"),
        detail_card.get("title"),
        note.get("title") if note.get("title") != "Untitled note" else "",
    )
    desc = first_value(detail_card.get("desc"), detail_card.get("description"), note.get("desc"))
    interact = first_value(detail_card.get("interact_info"), detail_card.get("interactions"))
    if not isinstance(interact, dict):
        interact = {}

    if title:
        note["title"] = str(title)
    if desc:
        note["desc"] = str(desc)
    if interact:
        note["visible_metrics"] = format_metrics(interact)
    note["content_type"] = str(first_value(detail_card.get("type"), detail_card.get("note_type"), note.get("content_type"), "note"))
    note["cover_style"] = infer_cover_style(detail_card) if detail_card else note.get("cover_style", "unknown cover")
    note["hook_angle"] = infer_hook_angle(note.get("title", ""), note.get("desc", ""))


def relative_evidence_path(evidence_dir: Path, output_path: Path) -> str:
    try:
        return str(evidence_dir.resolve().relative_to(output_path.parent.resolve()))
    except ValueError:
        return str(evidence_dir)


def positive_int(value: str) -> int:
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return number


def bounded_int(maximum: int):
    def parser(value: str) -> int:
        number = positive_int(value)
        if number > maximum:
            raise argparse.ArgumentTypeError(f"must be <= {maximum}")
        return number
    return parser


def non_negative_float(value: str) -> float:
    number = float(value)
    if number < 0:
        raise argparse.ArgumentTypeError("must be a non-negative number")
    return number


def append_live_research(existing: str, live_markdown: str) -> str:
    live_body = live_markdown.split("\n", 1)[1].lstrip() if live_markdown.startswith("# 02 Competitor Analysis") else live_markdown
    marker = "## Live Research Evidence"
    if marker in existing:
        prefix = existing.split(marker, 1)[0].rstrip()
    else:
        prefix = existing.rstrip()
    return f"{prefix}\n\n{marker}\n\n{live_body}".rstrip() + "\n"


def account_key(note: dict[str, str]) -> str:
    return note.get("user_id") or note.get("account") or "unknown"


def extract_account_profile(data: Any) -> dict[str, str]:
    if not isinstance(data, dict):
        return {}
    user = first_value(data.get("user"), data.get("user_info"), data.get("profile"), data)
    if not isinstance(user, dict):
        return {}
    followers = first_value(
        user.get("followers"),
        user.get("follower_count"),
        user.get("fans"),
        user.get("fans_count"),
    )
    bio = first_value(user.get("desc"), user.get("description"), user.get("bio"), user.get("introduction"))
    nickname = first_value(user.get("nickname"), user.get("nick_name"), user.get("name"))
    return {
        "account": str(nickname or ""),
        "followers": str(followers or "unknown"),
        "bio": str(bio or "not captured by account page"),
    }


def extract_recent_post_titles(data: Any, limit: int = 5) -> list[str]:
    if not isinstance(data, dict):
        return []
    items = first_value(data.get("items"), data.get("notes"), data.get("note_list"))
    if not isinstance(items, list):
        return []
    titles: list[str] = []
    for item in items[:limit]:
        if not isinstance(item, dict):
            continue
        card = note_card_from_item(item) or item
        title = first_value(card.get("display_title"), card.get("title"), item.get("title"), item.get("display_title"))
        if title:
            titles.append(str(title))
    return titles


def build_accounts(notes: list[dict[str, str]], account_details: dict[str, dict[str, str]] | None = None) -> list[dict[str, str]]:
    account_details = account_details or {}
    accounts: dict[str, dict[str, str]] = {}
    for note in notes:
        key = account_key(note)
        details = account_details.get(key, {})
        if key not in accounts:
            recent_posts = details.get("recent_posts", "")
            note_titles = recent_posts or note.get("title", "")
            accounts[key] = {
                "account": details.get("account") or note.get("account", "Unknown account"),
                "followers": details.get("followers") or "unknown",
                "persona": "inferred from live account and note sample" if details else "inferred from live note sample",
                "bio": details.get("bio") or "not captured by search result",
                "cadence": details.get("cadence") or "needs user-posts check if required",
                "buckets": note.get("keywords", ""),
                "notes": note_titles,
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
    account_details: dict[str, dict[str, str]],
    evidence_path: str,
    research_status: str,
    limitations: list[str],
) -> str:
    accounts = build_accounts(notes, account_details)
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
        f"- Research Status: {research_status}",
        f"- Research Evidence: {evidence_path}",
        f"- Search Keywords: {', '.join(keywords) if keywords else 'TODO'}",
        "",
        "## Research Limitations",
        "",
    ]
    lines.extend(f"- {item}" for item in (limitations or ["No blocking limitations detected."]))
    lines.extend([
        "",
        "## Research Goal",
        "",
        f"- Find benchmark accounts and notes that can support a {metadata.get('Industry', '小红书')} launch.",
        "- Prefer transferable patterns over celebrity outliers.",
        "",
        "## Seed Search Keywords",
        "",
    ])
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
    failures_by_keyword: list[dict[str, str]] = []
    empty_keywords: list[str] = []
    hard_blocked = False
    for index, keyword in enumerate(keywords, 1):
        data, _path, error = run_and_record(
            evidence_dir,
            f"{index:02d}-search-{slugify(keyword)}",
            ["search", keyword, "--sort", args.sort, "--type", args.note_type, "--page", str(args.page)],
            binary=args.xhs_binary,
            timeout=args.timeout,
            retries=args.retries,
            delay_min=args.delay_min,
            delay_max=args.delay_max,
            command_delay_min=args.command_delay_min,
            command_delay_max=args.command_delay_max,
        )
        if not isinstance(data, dict):
            search_failures += 1
            reason = str((error or {}).get("code") or "invalid_response")
            failures_by_keyword.append({"keyword": keyword, "reason": reason})
            if reason in BLOCKING_ERROR_CODES:
                hard_blocked = True
                break
            continue
        items = data.get("items", [])
        if not isinstance(items, list):
            failures_by_keyword.append({"keyword": keyword, "reason": "invalid_items"})
            continue
        if not items:
            empty_keywords.append(keyword)
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

    if hard_blocked and not notes:
        print("BLOCKED: xhs live research hit an authentication, verification, or IP limit error.")
        print(f"evidence_dir={evidence_dir}")
        return 2

    if not notes and search_failures == len(keywords):
        print("BLOCKED: xhs live research failed for every seed keyword.")
        print(f"evidence_dir={evidence_dir}")
        return 2

    read_targets = [note for note in notes if note.get("note_id")][: args.read_limit]
    for index, note in enumerate(read_targets, 1):
        note_id = note["note_id"]
        data, _path, error = run_and_record(
            evidence_dir,
            f"{index:02d}-read-{slugify(note_id)}",
            ["read", note_id],
            binary=args.xhs_binary,
            timeout=args.timeout,
            retries=args.retries,
            delay_min=args.delay_min,
            delay_max=args.delay_max,
            command_delay_min=args.command_delay_min,
            command_delay_max=args.command_delay_max,
        )
        if isinstance(data, dict):
            detail_card = data.get("note_card", data)
            if isinstance(detail_card, dict):
                merge_note_detail(note, detail_card)

    comments_by_note: dict[str, list[str]] = {}
    for index, note in enumerate(read_targets[: args.comment_notes], 1):
        note_id = note["note_id"]
        data, _path, error = run_and_record(
            evidence_dir,
            f"{index:02d}-comments-{slugify(note_id)}",
            ["comments", note_id],
            binary=args.xhs_binary,
            timeout=args.timeout,
            retries=args.retries,
            delay_min=args.delay_min,
            delay_max=args.delay_max,
            command_delay_min=args.command_delay_min,
            command_delay_max=args.command_delay_max,
        )
        comments = extract_comments(data, args.comments_per_note)
        if comments:
            comments_by_note[note_id] = comments

    account_details: dict[str, dict[str, str]] = {}
    account_enrichment_limitations: list[str] = []
    unique_accounts: list[tuple[str, str]] = []
    seen_accounts: set[str] = set()
    for note in notes:
        key = account_key(note)
        user_id = note.get("user_id", "")
        if user_id and key not in seen_accounts:
            seen_accounts.add(key)
            unique_accounts.append((key, user_id))

    if notes and args.account_limit > 0 and not unique_accounts:
        account_enrichment_limitations.append("Account enrichment unavailable: sampled search results did not expose user_id.")

    for index, (key, user_id) in enumerate(unique_accounts[: args.account_limit], 1):
        profile_data, _path, profile_error = run_and_record(
            evidence_dir,
            f"{index:02d}-user-{slugify(user_id)}",
            ["user", user_id],
            binary=args.xhs_binary,
            timeout=args.timeout,
            retries=args.retries,
            delay_min=args.delay_min,
            delay_max=args.delay_max,
            command_delay_min=args.command_delay_min,
            command_delay_max=args.command_delay_max,
        )
        profile = extract_account_profile(profile_data)
        if profile_error:
            account_enrichment_limitations.append(
                f"Account profile enrichment failed for sampled account {index}: {profile_error.get('code', 'unknown_error')}"
            )
        elif not profile:
            account_enrichment_limitations.append(f"Account profile enrichment returned no usable fields for sampled account {index}.")

        posts_data, _path, posts_error = run_and_record(
            evidence_dir,
            f"{index:02d}-user-posts-{slugify(user_id)}",
            ["user-posts", user_id],
            binary=args.xhs_binary,
            timeout=args.timeout,
            retries=args.retries,
            delay_min=args.delay_min,
            delay_max=args.delay_max,
            command_delay_min=args.command_delay_min,
            command_delay_max=args.command_delay_max,
        )
        recent_titles = extract_recent_post_titles(posts_data)
        if posts_error:
            account_enrichment_limitations.append(
                f"Account recent-post enrichment failed for sampled account {index}: {posts_error.get('code', 'unknown_error')}"
            )
        elif not recent_titles:
            account_enrichment_limitations.append(f"Account recent-post enrichment returned no titles for sampled account {index}.")
        else:
            profile["recent_posts"] = "; ".join(recent_titles)[:220]
            profile["cadence"] = f"{len(recent_titles)} sampled recent posts"
        if profile:
            account_details[key] = profile

    accounts = build_accounts(notes, account_details)
    limitations: list[str] = []
    for failure in failures_by_keyword:
        limitations.append(f"Failed keyword: {failure['keyword']} — reason: {failure['reason']}")
    for keyword in empty_keywords:
        limitations.append(f"Empty keyword: {keyword}")
    limitations.extend(account_enrichment_limitations)
    if len(notes) < args.min_notes:
        limitations.append(f"Sample size below rubric: {len(notes)}/{args.min_notes} notes captured")
    if len(accounts) < args.min_accounts:
        limitations.append(f"Benchmark account coverage below rubric: {len(accounts)}/{args.min_accounts} accounts captured")

    research_status = "PARTIAL" if limitations else "COMPLETE"
    live_markdown = build_markdown(
        metadata=metadata,
        keywords=keywords,
        notes=notes,
        comments_by_note=comments_by_note,
        account_details=account_details,
        evidence_path=relative_evidence_path(evidence_dir, output_path),
        research_status=research_status,
        limitations=limitations,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists() and analysis_markdown.strip() and not args.overwrite:
        output_path.write_text(append_live_research(analysis_markdown, live_markdown))
    else:
        if output_path.exists() and analysis_markdown.strip() and args.overwrite:
            backup_path = output_path.with_suffix(output_path.suffix + ".bak")
            backup_path.write_text(analysis_markdown)
        output_path.write_text(live_markdown)
    print(f"written={output_path}")
    print(f"evidence_dir={evidence_dir}")
    print(f"notes={len(notes)}")
    if research_status == "PARTIAL" and not args.allow_partial:
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--brief", required=True, help="Path to 01-client-brief.md")
    parser.add_argument("--output", required=True, help="Path to 02-competitor-analysis.md")
    parser.add_argument("--evidence-dir", help="Directory for raw xhs JSON evidence")
    parser.add_argument("--xhs-binary", default=DEFAULT_XHS_BINARY, help="Path or name of xhs executable")
    parser.add_argument("--max-keywords", type=bounded_int(10), default=3, help="Maximum seed keywords to search")
    parser.add_argument("--results-per-keyword", type=bounded_int(20), default=5, help="Maximum search results kept per keyword")
    parser.add_argument("--read-limit", type=bounded_int(10), default=3, help="Maximum notes to read after search")
    parser.add_argument("--comment-notes", type=bounded_int(5), default=2, help="Maximum notes to sample comments from")
    parser.add_argument("--comments-per-note", type=bounded_int(20), default=5, help="Maximum comments summarized per sampled note")
    parser.add_argument("--sort", default="popular", choices=["general", "popular", "latest"], help="xhs search sort")
    parser.add_argument("--note-type", default="all", choices=["all", "video", "image"], help="xhs search note type")
    parser.add_argument("--page", type=positive_int, default=1, help="xhs search page")
    parser.add_argument("--timeout", type=positive_int, default=90, help="Per-command timeout in seconds")
    parser.add_argument("--account-limit", type=bounded_int(5), default=3, help="Maximum accounts to enrich via xhs user and user-posts")
    parser.add_argument("--retries", type=bounded_int(3), default=0, help="Retry transient xhs command failures this many times")
    parser.add_argument("--delay-min", type=non_negative_float, default=0.0, help="Minimum delay between retry attempts in seconds")
    parser.add_argument("--delay-max", type=non_negative_float, default=0.0, help="Maximum delay between retry attempts in seconds")
    parser.add_argument("--command-delay-min", type=non_negative_float, default=0.0, help="Minimum global delay after each xhs command in seconds")
    parser.add_argument("--command-delay-max", type=non_negative_float, default=0.0, help="Maximum global delay after each xhs command in seconds")
    parser.add_argument("--min-notes", type=positive_int, default=15, help="Minimum notes required for COMPLETE research status")
    parser.add_argument("--min-accounts", type=positive_int, default=3, help="Minimum accounts required for COMPLETE research status")
    parser.add_argument("--allow-partial", action="store_true", help="Return success even when research status is PARTIAL")
    parser.add_argument("--overwrite", action="store_true", help="Replace output file instead of appending a Live Research Evidence section")
    args = parser.parse_args(argv)
    return collect_research(args)


if __name__ == "__main__":
    raise SystemExit(main())
