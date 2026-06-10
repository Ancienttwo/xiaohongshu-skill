#!/usr/bin/env python3
"""Migrate legacy Xiaohongshu workspace layouts into the canonical vault layout.

Canonical layout: ~/.growth/vault/<profile>/xiaohongshu/

Legacy layouts handled:
- ~/.growth/xiaohongshu/<profile>            (platform-first, pre-vault)
- ~/.growth/<profile>/xiaohongshu            (profile under root, pre-vault)
- ~/.growth/vault/xiaohongshu/<profile>      (platform-first inside vault)

Dry-run by default; pass --apply to move directories.
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from workspace_paths import INTERNAL_PROFILE_DIRS, PLATFORM, default_scan_root


def find_legacy_workspaces(root: Path) -> list[tuple[Path, Path]]:
    """Return (legacy_dir, canonical_target) pairs found under the scan root."""
    vault = root / "vault"
    moves: list[tuple[Path, Path]] = []

    platform_first = root / PLATFORM
    if platform_first.is_dir():
        for profile_dir in sorted(platform_first.iterdir()):
            if profile_dir.is_dir():
                moves.append((profile_dir, vault / profile_dir.name / PLATFORM))

    for profile_dir in sorted(root.iterdir()) if root.is_dir() else []:
        if not profile_dir.is_dir():
            continue
        if profile_dir.name in INTERNAL_PROFILE_DIRS or profile_dir.name == PLATFORM or profile_dir.name.startswith("_"):
            continue
        legacy = profile_dir / PLATFORM
        if legacy.is_dir():
            moves.append((legacy, vault / profile_dir.name / PLATFORM))

    vault_platform_first = vault / PLATFORM
    if vault_platform_first.is_dir():
        for profile_dir in sorted(vault_platform_first.iterdir()):
            if profile_dir.is_dir():
                moves.append((profile_dir, vault / profile_dir.name / PLATFORM))

    return moves


def migrate(root: Path, *, apply: bool) -> int:
    moves = find_legacy_workspaces(root)
    if not moves:
        print("status=clean")
        return 0

    conflicts = 0
    for source, target in moves:
        if target.exists():
            conflicts += 1
            print(f"conflict={source} -> {target} (target exists; merge manually)")
            continue
        if apply:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(source), str(target))
            print(f"moved={source} -> {target}")
        else:
            print(f"would_move={source} -> {target}")

    if not apply:
        print("status=dry-run (re-run with --apply to migrate)")
    elif conflicts:
        print(f"status=migrated-with-conflicts conflicts={conflicts}")
    else:
        print("status=migrated")
    return 1 if conflicts else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", help="Scan root (default: ~/.growth)")
    parser.add_argument("--apply", action="store_true", help="Actually move directories instead of dry-run")
    args = parser.parse_args()
    root = Path(args.root).expanduser().resolve() if args.root else default_scan_root()
    return migrate(root, apply=args.apply)


if __name__ == "__main__":
    raise SystemExit(main())
