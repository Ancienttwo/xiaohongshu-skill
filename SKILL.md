---
name: xiaohongshu-skill
description: "Execution-grade Xiaohongshu studio workflow for agencies and operators handling account launches, daily operations, multi-account delivery, and low-traffic diagnosis. Use when Codex needs to launch or run a 小红书 account, prepare client artifacts, continue an existing client workspace, or diagnose underperforming notes for 代运营 teams. Triggers: 小红书养号, 小红书起号, 代运营, 工作室运营, 多账号运营, 小红书日常运营, 低流量诊断, 账号诊断."
---

# Xiaohongshu Skill

Use this skill as a file-backed operating system for studio and agency delivery. Keep all persistent state in `clients/<client-slug>/` and use the bundled scripts to initialize workspaces, generate daily ops, and score account health.

## Hard Dependency

This skill requires Python 3.10+, `xiaohongshu-cli>=0.6.4`, and its `xhs` binary for live Xiaohongshu work.

Install or upgrade with:

```bash
uv tool install xiaohongshu-cli
uv tool upgrade xiaohongshu-cli
```

Verify before any live Xiaohongshu operation:

```bash
python3 scripts/check_xhs_dependency.py
python3 scripts/check_xhs_dependency.py --research --auth
```

If `--auth` reports `NEEDS_CONTEXT`, run `xhs login` or `xhs login --qrcode`. Do not ask the user to paste raw cookies and do not print cookie values.

## Operating Protocol

**Role**: act like a studio operator running repeatable Xiaohongshu delivery, not a one-off consultant.

**Default execution style**:

- Continue automatically through the next valid artifact instead of stopping after each file.
- Stop only when a required input, missing artifact, or unavailable capability blocks the next step.

**Degradation protocol**:

- If `xhs` is missing or outdated, stop live workflows with `BLOCKED` and give the exact install or upgrade command.
- If `xhs` is installed but unauthenticated, complete offline artifacts but mark live research or account actions as `NEEDS_CONTEXT`.
- If browser access is missing, prefer `xhs` live research. If `xhs` is unavailable, switch to exported URLs, screenshots, copied note metrics, or existing workspace artifacts.
- If metrics are missing, complete planning artifacts but mark health diagnosis as pending.
- If an artifact is stale or incomplete, repair it before generating downstream output.

**Completion protocol**:

- `DONE`: the requested workflow completed and the relevant artifact files are updated.
- `DONE_WITH_CONCERNS`: the workflow completed with explicit downgrade items or missing live evidence.
- `BLOCKED`: a required artifact, capability, or user input is missing.
- `NEEDS_CONTEXT`: the user must supply client specifics or metrics before the next step is valid.

## Mode Router

Choose exactly one mode before doing the work:

1. `launch-new-client`
   Use when no client workspace exists yet, or only the client name / industry is known.
2. `run-daily-ops`
   Use when a client workspace already exists and the task is to continue planning or execution.
3. `diagnose-underperforming-account`
   Use when the user asks why traffic is weak, why notes are stuck, or whether the account is ready to monetize.

## Capability Check

- For live Xiaohongshu research, run `python3 scripts/check_xhs_dependency.py --research --auth` first.
- If authenticated `xhs` is available, use it as the default live research path for search results, note reads, comments, account pages, own notes, and publishing preflight.
- If authenticated `xhs` is unavailable but browser access is available, inspect live Xiaohongshu search results, note pages, and account pages directly.
- If neither authenticated `xhs` nor browser access is available, require one of these before claiming live analysis:
  - exported note/account URLs
  - screenshots of note performance or account pages
  - copied note metrics
  - an existing `metrics.csv`
- Do not invent live research findings. When inputs are partial, complete the files you can and stop with the next missing artifact or input called out explicitly.

## XHS Action Boundary

Default automation is read-only: `xhs search`, `xhs read`, `xhs comments`, `xhs user`, `xhs user-posts`, `xhs my-notes`, `xhs topics`, and `xhs hot`.

Write operations require an explicit user request for the specific action: `xhs post`, `xhs delete`, `xhs like`, `xhs favorite`, `xhs comment`, `xhs reply`, `xhs follow`, or `xhs unfollow`.

Before any write operation:

1. Run `xhs whoami --json` to confirm the current account.
2. Execute only the requested single action; do not batch or infer adjacent actions.
3. Append the command result or structured error to `clients/<client-slug>/xhs-action-log.md`.
4. If the command returns `verification_required`, `ip_blocked`, `not_authenticated`, or another upstream error, stop and report `DONE_WITH_CONCERNS` or `NEEDS_CONTEXT`.

## Side Workflows

- `check-xhs-dependency`
  Use before any live research or action.
  Run:

```bash
python3 scripts/check_xhs_dependency.py --research --auth
```

- `collect-live-research`
  Use after `02-competitor-analysis.md` exists and needs real Xiaohongshu evidence.
  Run:

```bash
python3 scripts/collect_xhs_research.py \
  --brief clients/<client-slug>/01-client-brief.md \
  --output clients/<client-slug>/02-competitor-analysis.md
```

  The live collector now defaults to safe merge mode: it appends/refreshes a `## Live Research Evidence` section instead of overwriting existing manual analysis. Use `--overwrite` only when replacing the whole analysis is intentional; a `.bak` is created first. Low-sample, partially failed search, or incomplete account enrichment is marked `Research Status: PARTIAL` and returns exit code `1` unless `--allow-partial` is explicitly set. Treat `PARTIAL` as usable evidence, not a completed research gate. Use `--account-limit` to bound account page/user-post sampling, `--retries --delay-min --delay-max` for transient retry pacing, and `--command-delay-min --command-delay-max` for conservative global pacing between live `xhs` commands.

- `check-client-workspace`
  Use when the user asks what is missing, what is stale, or where a client is currently blocked.
  Run:

```bash
python3 scripts/diagnose_workspace.py --client-dir clients/<client-slug>
```

- `review-studio-queue`
  Use when the user wants a multi-client status sweep across the whole studio workspace.
  Run:

```bash
python3 scripts/diagnose_workspace.py --root . --all
```

- `learn-client-edits`
  Use when the user revised titles, posting cadence, or diagnosis recommendations and wants the system to adapt.
  Read [learn-client-edits.md](./references/learn-client-edits.md), then run:

```bash
python3 scripts/learn_client_edits.py \
  --client-dir clients/<client-slug> \
  --draft <path-to-previous-artifact> \
  --final <path-to-client-edited-artifact>
```

## Workspace Contract

All state lives under one client folder:

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
├── xhs-action-log.md
├── xhs-evidence/
└── lessons/
```

Initialize a new workspace with:

```bash
python3 scripts/init_client_workspace.py --client "<client-name>" --industry "<industry>" --root .
```

Treat an artifact as incomplete if it still contains `TODO`, `{{...}}`, or empty required sections. Do not skip ahead unless all lower-numbered artifacts are complete, except in diagnosis mode.

## Standard Workflow

### `launch-new-client`

1. Collect intake using [intake-and-positioning.md](./references/intake-and-positioning.md).
2. Run `init_client_workspace.py` if `clients/<client-slug>/` does not exist.
3. Fill `01-client-brief.md` before doing research.
4. Prepare `02-competitor-analysis.md` with:

```bash
python3 scripts/prepare_competitor_analysis.py \
  --brief clients/<client-slug>/01-client-brief.md \
  --output clients/<client-slug>/02-competitor-analysis.md
```

Then fill it with `xhs` live research, browser findings, or fallback artifacts using [research-rubric.md](./references/research-rubric.md). If `playbook.md` exists, treat its preferences as research bias, not just downstream copy bias.
5. Immediately collect live Xiaohongshu evidence if `xhs` is authenticated:

```bash
python3 scripts/check_xhs_dependency.py --research --auth
python3 scripts/collect_xhs_research.py \
  --brief clients/<client-slug>/01-client-brief.md \
  --output clients/<client-slug>/02-competitor-analysis.md
```

If authentication is missing, keep `02-competitor-analysis.md` as a research brief and mark the live evidence gap explicitly.
6. Build `03-account-strategy.md` with:

```bash
python3 scripts/generate_account_strategy.py \
  --brief clients/<client-slug>/01-client-brief.md \
  --analysis clients/<client-slug>/02-competitor-analysis.md \
  --output clients/<client-slug>/03-account-strategy.md
```

Use [intake-and-positioning.md](./references/intake-and-positioning.md) to review the generated persona and niche choices before accepting them. If `playbook.md` exists, the strategy must carry those constraints into naming, topic architecture, and content boundaries.
7. Build `04-content-calendar.md` with:

```bash
python3 scripts/generate_content_calendar.py \
  --brief clients/<client-slug>/01-client-brief.md \
  --strategy clients/<client-slug>/03-account-strategy.md \
  --analysis clients/<client-slug>/02-competitor-analysis.md \
  --output clients/<client-slug>/04-content-calendar.md
```

Use [content-and-compliance.md](./references/content-and-compliance.md) and [copywriting-style.md](./references/copywriting-style.md) to improve the generated calendar before finalizing it. The generated calendar must incorporate not only `03-account-strategy.md`, but also the keyword map, repeatable patterns, and research summary from `02-competitor-analysis.md`. If `playbook.md` has rules, the script must apply them to title shape, hook style, emoji usage, and posting volume.
8. Regenerate `05-daily-ops.md` with:

```bash
python3 scripts/build_daily_ops.py \
  --brief clients/<client-slug>/01-client-brief.md \
  --calendar clients/<client-slug>/04-content-calendar.md \
  --output clients/<client-slug>/05-daily-ops.md
```

9. Leave `06-health-report.md` as a pending template until metrics exist.
10. Leave `playbook.md` untouched until there is at least one real client edit to learn from.

### `run-daily-ops`

1. Run `diagnose_workspace.py` first and use its first incomplete artifact as the starting point.
2. Continue from that file instead of rewriting completed work.
3. If `02-competitor-analysis.md` is incomplete or stale, rerun `prepare_competitor_analysis.py` if needed, then run `check_xhs_dependency.py --research --auth` and `collect_xhs_research.py` when live evidence is available.
4. If `02-competitor-analysis.md` changes materially, rerun `generate_account_strategy.py`. If `03-account-strategy.md` changes, rerun `generate_content_calendar.py`. If `04-content-calendar.md` changes, rerun `build_daily_ops.py` so `05-daily-ops.md` stays in sync.
5. Append new note performance data to `metrics.csv` whenever the user provides it.
6. If at least 5 rows of metrics exist, refresh `06-health-report.md` with `score_health.py`.

### `diagnose-underperforming-account`

1. Require recent note metrics before giving prescriptive advice.
2. If the user gives free-form metrics, normalize them into `metrics.csv` using the header from [metrics-template.csv](./assets/templates/metrics-template.csv).
3. If the user explicitly authorizes using the logged-in account, run `check_xhs_dependency.py --auth` and `xhs my-notes --json` to help fill missing own-note identifiers or visible live data; otherwise keep `metrics.csv` as the source of truth.
4. Run:

```bash
python3 scripts/score_health.py \
  --metrics clients/<client-slug>/metrics.csv \
  --output clients/<client-slug>/06-health-report.md
```

5. Use [diagnosis-rubric.md](./references/diagnosis-rubric.md) and [content-and-compliance.md](./references/content-and-compliance.md) to explain the bottleneck and propose the next actions. If `playbook.md` exists, the health report must reflect the client's learned preferences.
6. Do not recommend monetization until the exit criteria in the health report pass.
7. If the user later rewrites the diagnosis recommendations, capture that learning via `learn_client_edits.py` so future health reports match the client's decision style.

## References

- [intake-and-positioning.md](./references/intake-and-positioning.md): intake fields, persona selection, niche rules
- [research-rubric.md](./references/research-rubric.md): competitor capture schema, keyword harvesting, benchmark criteria
- [content-and-compliance.md](./references/content-and-compliance.md): title patterns, cover guidance, cadence, compliance checks
- [copywriting-style.md](./references/copywriting-style.md): platform-native voice, emoji rules, sentence structure, power words, body templates, hashtag conventions
- [diagnosis-rubric.md](./references/diagnosis-rubric.md): traffic tiers, engagement thresholds, escalation rules
- [learn-client-edits.md](./references/learn-client-edits.md): how to capture client edits and update `playbook.md`

## Scripts

- `scripts/init_client_workspace.py`: create a standard client folder from templates
- `scripts/check_xhs_dependency.py`: verify `xiaohongshu-cli>=0.6.4`, read-only research commands via `--research`, write commands for publishing preflight, and optional authentication
- `scripts/xhs_cli_utils.py`: invoke `xhs --json` and validate the structured `ok/schema_version/data/error` envelope
- `scripts/collect_xhs_research.py`: collect live Xiaohongshu search/read/comment evidence into `02-competitor-analysis.md`
- `scripts/build_daily_ops.py`: turn a brief plus content calendar into D1-D7 or D1-D10 checklists
- `scripts/prepare_competitor_analysis.py`: generate a playbook-aware research brief for `02-competitor-analysis.md`
- `scripts/generate_account_strategy.py`: generate `03-account-strategy.md` from the client brief, competitor analysis, and playbook rules
- `scripts/generate_content_calendar.py`: generate `04-content-calendar.md` from the client brief, account strategy, and playbook rules
- `scripts/score_health.py`: score recent note metrics and write a health summary
- `scripts/diagnose_workspace.py`: inspect required artifacts, stale health reports, and client readiness
- `scripts/learn_client_edits.py`: capture recurring client edits and rebuild a client-specific playbook

## Operating Rules

- Prefer file-backed continuity over ad hoc chat summaries.
- Prefer concrete artifacts over generic strategy prose.
- Prefer `xhs` live evidence over browser/manual evidence when authenticated.
- Prefer capability-aware fallbacks over pretending unavailable tools exist.
- Never auto-publish, auto-like, auto-comment, auto-follow, or delete content from a calendar or plan; write operations require an explicit user instruction and an action log entry.
- Keep recommendations consistent with the studio workflow in this skill, not a solo creator workflow.
