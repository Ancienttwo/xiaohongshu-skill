# Changelog

## Unreleased

### Fixed

- `publish_note.py` no longer reports a successfully published note as a failure when the post-publish `my-notes` verification fails; verification problems are logged as `verify_error` and surfaced as `DONE_WITH_CONCERNS` so a retry cannot double-publish. The action log now records the real markdown-leak check result.
- `build_playbook.py` previously wrote a sectioned template that `load_playbook_rules` could not parse and that `learn_client_edits.py` would overwrite. It now renders `playbook.md` from `lessons/*.json`, which is the machine-readable source of truth; hand-edited table rows are still honored for keys without recorded lessons.
- Workspace path constants (`PLATFORM`, required files, vault roots, slugify) are defined once in `scripts/workspace_paths.py` instead of drifting copies across scripts.

### Changed

- `dist/` is no longer committed; build the OpenClaw bundle at release time with `scripts/build_openclaw.py`. CI verifies the bundle builds.
- `diagnose_workspace.py` only discovers the canonical `~/.growth/vault/<profile>/xiaohongshu/` layout and reports legacy directories on stderr. Use the new `scripts/migrate_workspace.py` (dry-run by default, `--apply` to move) to migrate the three historical layouts.
- Health-scoring thresholds (traffic tiers, exit criteria, warning terms) moved to `assets/diagnosis-thresholds.json`, shared by `score_health.py` and `diagnose_workspace.py`, and mirrored in `references/diagnosis-rubric.md`.
- `score_health.py` scores only the most recent 10 metric rows by default (`--recent`, `0` for all) so old notes do not dilute the diagnosis, and accepts `--thresholds` overrides.
- Shared logic extracted: `title_heuristics.py` (hook/family/feature detection), `research_report.py` (competitor-analysis rendering), `workspace_parsing.extract_calendar_rows`.

### Added

- GitHub Actions CI: unittest suite plus an OpenClaw bundle build check.
- Tests for content-calendar generation, client-edit learning, health scoring, the publish/verify flow, and workspace migration (39 tests total).

## 0.3.3

- Baseline release: launch/daily-ops/diagnosis workflows, live `xhs` research collector, publish boundary, playbook learning, and the OpenClaw distribution. See git history for details.
