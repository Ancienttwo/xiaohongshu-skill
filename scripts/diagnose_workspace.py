#!/usr/bin/env python3
"""Inspect Xiaohongshu client workspaces and report missing or stale artifacts."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


REQUIRED_FILES = [
    "01-client-brief.md",
    "02-competitor-analysis.md",
    "03-account-strategy.md",
    "04-content-calendar.md",
    "05-daily-ops.md",
    "06-health-report.md",
    "metrics.csv",
]


def count_metric_rows(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open(newline="") as handle:
        reader = csv.DictReader(handle)
        return sum(1 for row in reader if row.get("note_title", "").strip())


def is_incomplete(path: Path) -> bool:
    if not path.exists():
        return False
    if path.suffix == ".csv":
        return count_metric_rows(path) == 0
    content = path.read_text()
    return "TODO" in content or "{{" in content


def evaluate_client_dir(client_dir: Path) -> dict[str, object]:
    client_slug = client_dir.parent.name if client_dir.name == ".xiaohongshu" else client_dir.name
    missing = []
    incomplete = []
    optional = {
        "playbook_exists": (client_dir / "playbook.md").exists(),
        "lessons_count": len(list((client_dir / "lessons").glob("*.json"))) if (client_dir / "lessons").exists() else 0,
    }
    for name in REQUIRED_FILES:
        path = client_dir / name
        if not path.exists():
            missing.append(name)
        elif is_incomplete(path):
            incomplete.append(name)

    metrics_path = client_dir / "metrics.csv"
    health_path = client_dir / "06-health-report.md"
    metric_rows = count_metric_rows(metrics_path)
    health_stale = (
        metrics_path.exists()
        and health_path.exists()
        and metric_rows >= 5
        and metrics_path.stat().st_mtime > health_path.stat().st_mtime
    )

    if missing:
        recommended_mode = "launch-new-client"
        next_step = missing[0]
    elif incomplete:
        recommended_mode = "run-daily-ops"
        next_step = incomplete[0]
    elif metric_rows >= 5 and (not health_path.exists() or health_stale):
        recommended_mode = "diagnose-underperforming-account"
        next_step = "06-health-report.md"
    else:
        recommended_mode = "run-daily-ops"
        next_step = "workspace-ready"

    priority_score = (
        len(missing) * 10
        + len(incomplete) * 4
        + (6 if health_stale else 0)
        + (3 if metric_rows >= 5 and not health_stale and next_step == "workspace-ready" else 0)
        + (2 if not optional["playbook_exists"] else 0)
    )
    if next_step == "workspace-ready":
        status = "ready"
    elif missing:
        status = "blocked"
    else:
        status = "in_progress"

    return {
        "client_slug": client_slug,
        "client_dir": str(client_dir),
        "missing_files": missing,
        "incomplete_files": incomplete,
        "metric_rows": metric_rows,
        "health_report_stale": health_stale,
        "recommended_mode": recommended_mode,
        "next_step": next_step,
        "priority_score": priority_score,
        "status": status,
        **optional,
    }


def print_text_report(result: dict[str, object]) -> None:
    print(f"client_slug={result['client_slug']}")
    print(f"recommended_mode={result['recommended_mode']}")
    print(f"next_step={result['next_step']}")
    print(f"status={result['status']}")
    print(f"priority_score={result['priority_score']}")
    print(f"metric_rows={result['metric_rows']}")
    print(f"health_report_stale={str(result['health_report_stale']).lower()}")
    print(f"playbook_exists={str(result['playbook_exists']).lower()}")
    print(f"lessons_count={result['lessons_count']}")
    if result["missing_files"]:
        print("missing_files=" + ",".join(result["missing_files"]))
    if result["incomplete_files"]:
        print("incomplete_files=" + ",".join(result["incomplete_files"]))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--client-dir", help="Path to one client workspace")
    parser.add_argument("--root", help="Skill root containing users/<user-slug>/.xiaohongshu/ workspaces")
    parser.add_argument("--all", action="store_true", help="Diagnose all client workspaces under --root")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of text")
    args = parser.parse_args()

    if args.all:
        if not args.root:
            raise SystemExit("--all requires --root.")
        users_root = Path(args.root).resolve() / "users"
        if users_root.exists():
            workspace_dirs = [path / ".xiaohongshu" for path in sorted(users_root.iterdir()) if (path / ".xiaohongshu").is_dir()]
        else:
            workspace_dirs = []
        results = [evaluate_client_dir(path) for path in workspace_dirs]
        results.sort(key=lambda item: (-int(item["priority_score"]), str(item["client_slug"])))
        if args.json:
            print(json.dumps(results, ensure_ascii=False, indent=2))
        else:
            for idx, result in enumerate(results):
                if idx:
                    print("---")
                print_text_report(result)
        return 0

    if not args.client_dir:
        raise SystemExit("Provide --client-dir or use --root with --all.")

    result = evaluate_client_dir(Path(args.client_dir).resolve())
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print_text_report(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
