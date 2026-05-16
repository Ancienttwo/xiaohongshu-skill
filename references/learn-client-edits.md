# Learn Client Edits

Use this reference when a client revises one of the generated artifacts and wants future output to match that preference.

## Goal

Turn repeated client edits into explicit operating rules inside `users/<user-slug>/.xiaohongshu/playbook.md`.

## Supported Edit Sources

The first version supports these artifact types well:

- `04-content-calendar.md`
- `05-daily-ops.md`
- `06-health-report.md`

It can still run on other markdown files, but the strongest signal comes from title, cadence, and diagnosis edits.

## Workflow

1. Keep the machine-generated file as the draft.
2. Save the client-edited file separately.
3. Run:

```bash
python3 scripts/learn_client_edits.py \
  --client-dir users/<user-slug>/.xiaohongshu \
  --draft <draft-path> \
  --final <final-path>
```

4. Read the generated lesson summary and refreshed `playbook.md`.
5. Apply hard rules from `playbook.md` the next time you update content calendars or health reports.

## What The Script Learns

It extracts recurring preferences such as:

- shorter or longer titles
- more or fewer emoji
- stronger number-led hooks
- stronger question-led hooks
- lower or higher posting volume
- stronger emphasis on keyword fit
- stronger emphasis on cover and hook revisions
- stronger emphasis on compliance or risk review
- preference for shorter, more direct action items

## How To Use The Playbook

- Rules with confidence `>= 5.0` are hard defaults.
- Rules with confidence `3.0-4.9` are strong preferences.
- Rules below `3.0` are weak signals and should not override current evidence.

If a new client edit contradicts an old rule, rerun the script and trust the updated confidence and `last_seen` values.
