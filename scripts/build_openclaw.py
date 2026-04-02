#!/usr/bin/env python3
"""Build an OpenClaw-compatible distribution from the root skill package."""

from __future__ import annotations

import shutil
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parent.parent
DIST_ROOT = SKILL_ROOT / "dist" / "openclaw"
COPY_ITEMS = [
    "SKILL.md",
    "VERSION",
    "LICENSE",
    "assets",
    "references",
    "scripts",
]
SKIP_NAMES = {
    "__pycache__",
    ".DS_Store",
    "build_openclaw.py",
}


def reset_dist() -> None:
    if DIST_ROOT.exists():
        shutil.rmtree(DIST_ROOT)
    DIST_ROOT.mkdir(parents=True, exist_ok=True)


def ignore_filter(_dir: str, names: list[str]) -> set[str]:
    ignored = set()
    for name in names:
        if name in SKIP_NAMES or name.endswith(".pyc"):
            ignored.add(name)
    return ignored


def copy_item(name: str) -> None:
    source = SKILL_ROOT / name
    target = DIST_ROOT / name
    if source.is_dir():
        shutil.copytree(source, target, ignore=ignore_filter)
    else:
        shutil.copy2(source, target)


def main() -> int:
    reset_dist()
    for name in COPY_ITEMS:
        copy_item(name)
    print(f"written={DIST_ROOT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
