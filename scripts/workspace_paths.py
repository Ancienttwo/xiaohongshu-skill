#!/usr/bin/env python3
"""Single source of truth for vault layout constants and path helpers."""

from __future__ import annotations

import re
from pathlib import Path


PLATFORM = "xiaohongshu"

REQUIRED_FILES = [
    "01-client-brief.md",
    "02-competitor-analysis.md",
    "03-account-strategy.md",
    "04-content-calendar.md",
    "05-daily-ops.md",
    "06-health-report.md",
    "metrics.csv",
]

INTERNAL_PROFILE_DIRS = {"_library", "migrations", "published-posts", "social-board", "social-cron", "vault"}


def default_scan_root() -> Path:
    """Root scanned for workspaces, including legacy layouts."""
    return Path.home() / ".growth"


def default_vault_root() -> Path:
    """Canonical vault root where new workspaces are created."""
    return default_scan_root() / "vault"


def profile_from_client_dir(client_dir: Path) -> str:
    return client_dir.parent.name if client_dir.name == PLATFORM else client_dir.name


def normalize_client_dir(path: Path) -> Path:
    if (path / PLATFORM).is_dir():
        return path / PLATFORM
    return path


def slugify(value: str, *, keep_cjk: bool = False, fallback: str = "client") -> str:
    pattern = r"[^a-zA-Z0-9\u4e00-\u9fff]+" if keep_cjk else r"[^a-zA-Z0-9]+"
    normalized = re.sub(pattern, "-", value.strip()).strip("-").lower()
    normalized = re.sub(r"-{2,}", "-", normalized)
    return normalized or fallback
