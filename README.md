# xiaohongshu-skill

Execution-grade Xiaohongshu studio workflow for agencies and operators running account launches, daily operations, and low-traffic diagnosis.

This repository packages a Codex skill plus supporting references, templates, evals, and Python utilities. The workflow is designed around file-backed client workspaces so delivery can continue across sessions without losing state.

## What It Does

- Initializes a standard client workspace under `users/<user-slug>/.xiaohongshu/`
- Uses `xiaohongshu-cli` for live Xiaohongshu search, note reads, comments, and account evidence
- Generates structured delivery artifacts for launch and daily ops
- Scores note performance from `metrics.csv` and writes a health report
- Diagnoses incomplete or stale client workspaces
- Learns recurring client edits and turns them into playbook rules
- Builds a distributable OpenClaw bundle in `dist/openclaw/`

## Workspace Model

Every client lives in one directory:

```text
users/<user-slug>/.xiaohongshu/
├── 01-client-brief.md
├── 02-competitor-analysis.md
├── 03-account-strategy.md
├── 04-content-calendar.md
├── 05-daily-ops.md
├── 06-health-report.md
├── metrics.csv
├── playbook.md
├── xhs-action-log.md
├── xhs-evidence/
└── lessons/
```

The `users/*/.xiaohongshu/` workspace directory is git-ignored so operator workspaces do not ship with the skill itself.

## Requirements

- Python 3.10+ for the `xiaohongshu-cli` runtime
- `xiaohongshu-cli>=0.6.4` with the `xhs` command available on `PATH`
- No third-party Python packages are imported by the bundled scripts; live Xiaohongshu access is delegated to the external `xhs` process

Install or upgrade the hard dependency:

```bash
uv tool install xiaohongshu-cli
uv tool upgrade xiaohongshu-cli
```

If `uv` is unavailable, `pipx install xiaohongshu-cli` is a fallback. This repo does not vendor the upstream CLI.

Preflight:

```bash
# read-only research path: search/read/comments/user/user-posts/etc.
python3 scripts/check_xhs_dependency.py --research --auth

# write-capable workflows such as publishing still require full command coverage
python3 scripts/check_xhs_dependency.py --auth
```

`--auth` requires a valid local Xiaohongshu session. Use `xhs login` or `xhs login --qrcode`; do not paste raw cookies into project files or chat logs.

## Quick Start

Initialize a new client workspace:

```bash
python3 scripts/init_client_workspace.py \
  --client "Clear Skin Lab" \
  --industry "Skincare" \
  --root .
```

Check what is missing for one client:

```bash
python3 scripts/diagnose_workspace.py --client-dir users/clear-skin-lab/.xiaohongshu
```

Check the full studio queue:

```bash
python3 scripts/diagnose_workspace.py --root . --all
```

Collect live Xiaohongshu research into the competitor analysis:

```bash
python3 scripts/collect_xhs_research.py \
  --brief users/clear-skin-lab/.xiaohongshu/01-client-brief.md \
  --output users/clear-skin-lab/.xiaohongshu/02-competitor-analysis.md
```

Generate or refresh a health report:

```bash
python3 scripts/score_health.py \
  --metrics users/clear-skin-lab/.xiaohongshu/metrics.csv \
  --output users/clear-skin-lab/.xiaohongshu/06-health-report.md
```

Build the OpenClaw distribution:

```bash
python3 scripts/build_openclaw.py
```

## Main Workflows

### Launch New Client

1. Initialize the workspace with `init_client_workspace.py`
2. Complete `01-client-brief.md`
3. Generate `02-competitor-analysis.md`
4. Run `check_xhs_dependency.py --research --auth` and `collect_xhs_research.py` when live evidence is available
5. Generate `03-account-strategy.md`
6. Generate `04-content-calendar.md`
7. Generate `05-daily-ops.md`
8. Leave `06-health-report.md` pending until metrics exist

### Run Daily Ops

1. Start with `diagnose_workspace.py`
2. Continue from the first incomplete artifact
3. Refresh stale live research through `xhs` when authenticated
4. Regenerate downstream files when upstream inputs change
5. Append note performance data to `metrics.csv`
6. Refresh `06-health-report.md` once there are at least 5 populated note rows

### Diagnose Underperforming Accounts

1. Normalize recent note performance into `metrics.csv`
2. Run `score_health.py`
3. Use the generated report to identify traffic tier, weakest notes, and next actions
4. Feed client revisions back into `playbook.md` using `learn_client_edits.py`

`metrics.csv` remains the source of truth for diagnosis. Only use `xhs my-notes --json` to fill own-note identifiers or visible live data when the user explicitly authorizes using the logged-in account.

### Explicit XHS Actions

Read-only commands (`search`, `read`, `comments`, `user`, `user-posts`, `my-notes`, `topics`, `hot`) may run as part of live research after auth preflight.

Write commands (`post`, `delete`, `like`, `favorite`, `comment`, `reply`, `follow`, `unfollow`) require an explicit user request for that specific action. Before a write command, confirm the active account with `xhs whoami --json`; after it runs, append the result or error code to `users/<user-slug>/.xiaohongshu/xhs-action-log.md`.

## Repository Layout

```text
.
├── SKILL.md
├── VERSION
├── LICENSE
├── agents/
├── assets/templates/
├── dist/openclaw/
├── evals/evals.json
├── references/
├── scripts/
└── tests/
```

Key files:

- `SKILL.md`: operating protocol, mode router, workflow contract
- `references/`: positioning, research, copywriting, compliance, diagnosis, and learning guides
- `assets/templates/`: starter artifacts used to create client workspaces
- `scripts/`: automation for workspace creation, planning, diagnosis, health scoring, and packaging
- `tests/`: source-repo verification for the `xhs` integration wrappers
- `evals/evals.json`: regression checks for common operator scenarios

## Script Reference

- `scripts/init_client_workspace.py`: create a standard client folder from templates
- `scripts/check_xhs_dependency.py`: verify `xiaohongshu-cli>=0.6.4`, read-only research commands via `--research`, full write-capable commands by default, and optional auth
- `scripts/xhs_cli_utils.py`: run `xhs --json` and validate the `ok/schema_version/data/error` envelope
- `scripts/collect_xhs_research.py`: collect live search, note, and comment evidence into `02-competitor-analysis.md`
- `scripts/prepare_competitor_analysis.py`: generate a research brief for `02-competitor-analysis.md`
- `scripts/generate_account_strategy.py`: generate `03-account-strategy.md`
- `scripts/generate_content_calendar.py`: generate `04-content-calendar.md`
- `scripts/build_daily_ops.py`: generate `05-daily-ops.md`
- `scripts/score_health.py`: write `06-health-report.md` from metrics
- `scripts/diagnose_workspace.py`: inspect missing, incomplete, or stale work
- `scripts/learn_client_edits.py`: capture repeat client preferences into lessons and playbook rules
- `scripts/build_playbook.py`: rebuild `playbook.md` from captured lessons
- `scripts/build_openclaw.py`: assemble the shipping bundle in `dist/openclaw/`

## Distribution

`scripts/build_openclaw.py` copies the shipping subset of the repository into `dist/openclaw/`:

- `SKILL.md`
- `VERSION`
- `LICENSE`
- `assets/`
- `references/`
- `scripts/`

It intentionally skips source-repo tests, local caches such as `__pycache__`, `.DS_Store`, and the build script itself.
