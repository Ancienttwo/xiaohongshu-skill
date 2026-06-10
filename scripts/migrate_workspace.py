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

from workspace_paths import PLATFORM, default_scan_root, is_profile_dir, looks_like_workspace


def find_legacy_workspaces(root: Path) -> list[tuple[Path, Path | None]]:
    """Return (legacy_dir, canonical_target) pairs found under the scan root.

    A target of None means the workspace was found but the profile name cannot
    be inferred, so it must be moved manually. Only directories that contain at
    least one standard workspace artifact are reported, so content
    subdirectories such as lessons/ or xhs-evidence/ are never proposed as
    profiles.
    """
    if root.name == "vault":
        root = root.parent
    vault = root / "vault"
    moves: list[tuple[Path, Path | None]] = []

    for platform_first in [root / PLATFORM, vault / PLATFORM]:
        if not platform_first.is_dir():
            continue
        if looks_like_workspace(platform_first):
            # The platform dir itself is a single legacy workspace; there is
            # no profile name to infer, so it cannot be moved automatically.
            moves.append((platform_first, None))
            continue
        for profile_dir in sorted(platform_first.iterdir()):
            if profile_dir.is_dir() and looks_like_workspace(profile_dir):
                moves.append((profile_dir, vault / profile_dir.name / PLATFORM))

    for profile_dir in sorted(root.iterdir()) if root.is_dir() else []:
        if not is_profile_dir(profile_dir):
            continue
        legacy = profile_dir / PLATFORM
        if legacy.is_dir() and looks_like_workspace(legacy):
            moves.append((legacy, vault / profile_dir.name / PLATFORM))

    return moves


def migrate(root: Path, *, apply: bool) -> int:
    moves = find_legacy_workspaces(root)
    if not moves:
        print("status=clean")
        return 0

    vault = (root.parent if root.name == "vault" else root) / "vault"
    manual = 0
    for source, target in moves:
        if target is None:
            manual += 1
            print(f"manual={source} (cannot infer profile; move it to {vault}/<profile>/{PLATFORM} yourself)")
            continue
        if target.exists():
            manual += 1
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
    elif manual:
        print(f"status=migrated-with-conflicts conflicts={manual}")
    else:
        print("status=migrated")
    return 1 if manual else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", help="Scan root (default: ~/.growth)")
    parser.add_argument("--apply", action="store_true", help="Actually move directories instead of dry-run")
    args = parser.parse_args()
    root = Path(args.root).expanduser().resolve() if args.root else default_scan_root()
    return migrate(root, apply=args.apply)


if __name__ == "__main__":
    raise SystemExit(main())
