# Learning from Client Edits

Use this reference to build and maintain a per-client playbook that captures preferences discovered through revisions.

## When to Trigger

Record a learning whenever the user or operator:

- Rewrites a title the agent generated
- Changes the content calendar order or content type
- Rejects a recommended persona or niche direction
- Overrides a diagnosis recommendation
- Adjusts posting cadence or timing
- Adds or removes hashtags from a note

## What to Capture

Each learning entry should include:

| Field | Description |
|---|---|
| Date | When the edit happened |
| Artifact | Which file was changed (e.g., 04-content-calendar.md) |
| Original | What the agent produced |
| Revision | What the operator changed it to |
| Rule | The inferred preference (one sentence) |
| Confidence | high (explicit correction), medium (pattern from 2+ edits), low (single silent change) |

## Where to Store

Each client workspace gets a `playbook.md` file:

```
clients/<client-slug>/playbook.md
```

Format:

```markdown
# Client Playbook — <client-name>

## Title Preferences
- Prefer question-style titles over number-style (high confidence, 2026-04-02)
- Always include emoji at end of title, never at start (medium confidence, 2026-04-03)

## Content Preferences
- Diary-style notes outperform checklist notes for this audience (medium confidence, 2026-04-05)
- Prefer 12:00 and 20:00 posting times, never before 10:00 (high confidence, 2026-04-02)

## Tone Preferences
- More casual than default — use 哈哈哈 instead of formal closings (high confidence, 2026-04-03)

## Rejected Approaches
- Do not use before/after comparison format — client finds it too aggressive (high confidence, 2026-04-04)
```

## How to Apply

1. Before generating new content calendar entries, read `playbook.md` if it exists.
2. Apply all high-confidence rules as constraints.
3. Apply medium-confidence rules as soft preferences (can override with justification).
4. Ignore low-confidence rules if they conflict with platform best practices.
5. When a low-confidence rule gets confirmed by a second edit, promote it to medium.

## Playbook Maintenance

- Review and prune the playbook when the client reaches 20+ entries.
- Remove rules that the client has contradicted with later edits.
- Merge overlapping rules into a single clearer statement.
- Never delete the playbook when regenerating other artifacts.

## Script Support

Run `build_playbook.py` to initialize or update the playbook from a diff of client edits:

```bash
python3 scripts/build_playbook.py \
  --client-dir clients/<client-slug>/ \
  --output clients/<client-slug>/playbook.md
```
