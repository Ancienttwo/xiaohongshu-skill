#!/usr/bin/env python3
"""Render collected live-research data into the 02-competitor-analysis markdown."""

from __future__ import annotations

from datetime import datetime
from typing import Any


def table_cell(value: Any) -> str:
    text = str(value or "").replace("\n", " ").replace("|", "/").strip()
    return text or "Unknown"


def account_key(note: dict[str, str]) -> str:
    return note.get("user_id") or note.get("account") or "unknown"


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
