# xiaohongshu-skill

Execution-grade Xiaohongshu studio workflow for agencies and operators running account launches, daily operations, and low-traffic diagnosis.

This repository packages a Codex skill plus supporting references, templates, evals, and Python utilities. The workflow is designed around file-backed client workspaces so delivery can continue across sessions without losing state.

## What It Does

- Initializes a standard client workspace under `clients/<client-slug>/`
- Generates structured delivery artifacts for launch and daily ops
- Scores note performance from `metrics.csv` and writes a health report
- Diagnoses incomplete or stale client workspaces
- Learns recurring client edits and turns them into playbook rules
- Builds a distributable OpenClaw bundle in `dist/openclaw/`

## Workspace Model

Every client lives in one directory:

```text
clients/<client-slug>/
├── 01-client-brief.md
├── 02-competitor-analysis.md
├── 03-account-strategy.md
├── 04-content-calendar.md
├── 05-daily-ops.md
├── 06-health-report.md
├── metrics.csv
├── playbook.md
└── lessons/
```

The `clients/` directory is git-ignored so operator workspaces do not ship with the skill itself.

## Requirements

- Python 3
- No third-party Python packages are required for the bundled scripts

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
python3 scripts/diagnose_workspace.py --client-dir clients/clear-skin-lab
```

Check the full studio queue:

```bash
python3 scripts/diagnose_workspace.py --root . --all
```

Generate or refresh a health report:

```bash
python3 scripts/score_health.py \
  --metrics clients/clear-skin-lab/metrics.csv \
  --output clients/clear-skin-lab/06-health-report.md
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
4. Generate `03-account-strategy.md`
5. Generate `04-content-calendar.md`
6. Generate `05-daily-ops.md`
7. Leave `06-health-report.md` pending until metrics exist

### Run Daily Ops

1. Start with `diagnose_workspace.py`
2. Continue from the first incomplete artifact
3. Regenerate downstream files when upstream inputs change
4. Append note performance data to `metrics.csv`
5. Refresh `06-health-report.md` once there are at least 5 populated note rows

### Diagnose Underperforming Accounts

1. Normalize recent note performance into `metrics.csv`
2. Run `score_health.py`
3. Use the generated report to identify traffic tier, weakest notes, and next actions
4. Feed client revisions back into `playbook.md` using `learn_client_edits.py`

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
└── scripts/
```

Key files:

- `SKILL.md`: operating protocol, mode router, workflow contract
- `references/`: positioning, research, copywriting, compliance, diagnosis, and learning guides
- `assets/templates/`: starter artifacts used to create client workspaces
- `scripts/`: automation for workspace creation, planning, diagnosis, health scoring, and packaging
- `evals/evals.json`: regression checks for common operator scenarios

## Script Reference

- `scripts/init_client_workspace.py`: create a standard client folder from templates
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

It intentionally skips local caches such as `__pycache__`, `.DS_Store`, and the build script itself.
